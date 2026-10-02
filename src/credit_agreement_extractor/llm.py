"""Shared OpenCode transport: normalize endpoint differences, not legal meaning."""
from __future__ import annotations
from dataclasses import dataclass
import json
import math
import time
import urllib.request
import urllib.error
from .config import OpenCodeSettings
from .tracing import current_trace, traced

# Explicit routes keep unrecognized models from silently using a wrong API.
MODEL_ROUTES = {'gpt-5.6-luna':'responses', 'gpt-5.6-sol':'responses',
                'gpt-5.6-terra':'responses', 'gpt-6-luna':'responses',
                'qwen3.8-max':'chat_completions', 'qwen3.8-flash':'messages',
                'deepseek-v4.1-flash':'chat_completions',
                'deepseek-v4-pro':'chat_completions', 'deepseek-v4-flash':'chat_completions'}

# Dated gateway list-price snapshot, not a claim about a user's final bill.
# Overrides can replace this mapping; an empty mapping disables estimates.
# Unknown models/tiers remain unknown rather than inheriting Luna pricing.
DEFAULT_PRICING = {'gpt-5.6-luna': {
    'date':'2026-10-01', 'source':'https://opencode.ai/docs/zen/#pricing',
    'currency':'USD', 'input_per_million':0.20, 'output_per_million':1.20,
    'cached_input_per_million':0.02, 'cache_write_per_million':0.25,
    'max_input_tokens':272000}}


class LlmError(RuntimeError):
    def __init__(self, message, *, retryable=False, status=None):
        super().__init__(message)
        self.retryable, self.status = retryable, status


@dataclass(frozen=True)
class LlmResponse:
    text: str
    model: str
    api_style: str
    usage: dict
    latency_seconds: float
    cost: dict
    response_id: str | None = None


def visible_response(value):
    """Strip provider thinking before debug persistence, retaining usage counts.

    A raw provider response can contain chain-of-thought even when we never
    requested a reasoning summary. Never persist those blocks or signatures.
    This is a logging view only; parsing still uses the original in memory.
    """
    if isinstance(value, dict):
        if value.get('type') in ('thinking', 'redacted_thinking', 'reasoning'):
            return {'type': value['type'], 'omitted': True}
        hidden = {'reasoning_content', 'reasoning_details', 'thinking', 'signature',
                  'encrypted_content', 'redacted_data'}
        return {k: visible_response(v) for k, v in value.items() if k not in hidden}
    if isinstance(value, list):
        return [visible_response(v) for v in value]
    return value


def estimate_cost(usage, rates=None):
    """Use explicit dated gateway rates only; missing data is not free usage."""
    if not rates or not all(k in rates for k in ('date','source','currency','input_per_million','output_per_million')):
        return {'kind':'unknown','amount':None}
    inputs, outputs = usage.get('input_tokens'), usage.get('output_tokens')
    if not isinstance(inputs, int) or not isinstance(outputs, int) or min(inputs, outputs) < 0:
        return {'kind':'unknown','amount':None}
    if inputs > rates.get('max_input_tokens',float('inf')):
        return {'kind':'unknown','amount':None}
    cached = (usage.get('input_tokens_details') or {}).get('cached_tokens', 0) or 0
    written = (usage.get('input_tokens_details') or {}).get('cache_write_tokens', 0) or 0
    if cached and 'cached_input_per_million' not in rates:
        return {'kind':'unknown','amount':None}
    if not isinstance(cached, int) or not 0 <= cached <= inputs:
        return {'kind':'unknown','amount':None}
    if not isinstance(written,int) or written < 0 or written+cached > inputs or written and 'cache_write_per_million' not in rates:
        return {'kind':'unknown','amount':None}
    # Reasoning tokens are a detail of output_tokens, not an additional charge.
    amount = ((inputs-cached-written)*rates['input_per_million'] + cached*rates.get('cached_input_per_million',0)
              + written*rates.get('cache_write_per_million',0)
              + outputs*rates['output_per_million']) / 1_000_000
    return {'kind':'estimated','amount':amount,'currency':rates['currency'],
            'pricing_date':rates['date'],'pricing_source':rates['source']}


class OpenCodeClient:
    def __init__(self, settings=None, *, opener=None, pricing=None, timeout_seconds=60,
                 max_output_tokens=8192):
        # High-effort non-streaming responses may legitimately exceed a minute.
        # This transport setting changes neither the prompt nor cache identity.
        if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds) or timeout_seconds <= 0):
            raise ValueError('timeout_seconds must be a positive finite number.')
        self.timeout_seconds = timeout_seconds
        if type(max_output_tokens) is not int or max_output_tokens <= 0:
            raise ValueError('max_output_tokens must be a positive integer.')
        self.max_output_tokens = max_output_tokens
        self.settings = settings or OpenCodeSettings()
        self.opener = opener or urllib.request.urlopen
        self.pricing = DEFAULT_PRICING if pricing is None else pricing

    @traced('C')
    def complete(self, system, evidence, *, model=None, reasoning_effort='medium',
                 api_style=None, debug=False, run_id=None, trace_root='tmp/runs'):
        model = model or self.settings.model or 'gpt-5.6-luna'
        style = api_style or MODEL_ROUTES.get(model)
        if style not in ('responses','chat_completions','messages'):
            raise ValueError('Unknown model route: supply an explicit supported api_style.')
        if reasoning_effort not in ('none','minimal','low','medium','high','xhigh'):
            raise ValueError('Unsupported reasoning effort.')
        key = self.settings.api_key
        if key is None or not key.get_secret_value().strip():
            raise ValueError('OPENCODE_API_KEY is required.')
        content = json.dumps(evidence, ensure_ascii=False)
        if style == 'responses':
            payload = {'model':model,'instructions':system,'input':content,'store':False,
                       'reasoning':{'effort':reasoning_effort},'max_output_tokens':self.max_output_tokens}
            endpoint = '/responses'
        elif style == 'chat_completions':
            payload = {'model':model,'messages':[{'role':'system','content':system},
                       {'role':'user','content':content}], 'max_tokens':self.max_output_tokens,
                       'response_format':{'type':'json_object'}}
            # Do not claim a reasoning override was honored by an open model
            # unless it is explicitly supplied to that endpoint.
            if reasoning_effort != 'none': payload['reasoning_effort'] = reasoning_effort
            endpoint = '/chat/completions'
        else:
            # OpenCode's non-adaptive Messages high variant uses a 16k thinking
            # budget. This is a budget mapping, not a native reasoning_effort
            # dial. Other tiers are rejected rather than silently translated.
            # Source: anomalyco/opencode, provider/transform.ts Messages variants.
            if reasoning_effort not in ('none', 'high'):
                raise ValueError('Messages supports none or high (16000-token thinking budget).')
            payload = {'model':model, 'system':system,
                       'messages':[{'role':'user','content':content}],
                       'max_tokens':32768 if reasoning_effort == 'high' else 8192,
                       'thinking':{'type':'enabled','budget_tokens':16000}
                       if reasoning_effort == 'high' else {'type':'disabled'}}
            endpoint = '/messages'
        trace = current_trace()
        trace.snapshot('C-request', {'api_style':style,'payload':payload})
        headers = {'Content-Type':'application/json','User-Agent':'CreditAgreementParser/0.1'}
        if style == 'messages':
            headers.update({'x-api-key':key.get_secret_value(),'anthropic-version':'2023-06-01'})
        else:
            headers['Authorization'] = 'Bearer '+key.get_secret_value()
        request = urllib.request.Request(str(self.settings.base_url).rstrip('/') + endpoint,
                  data=json.dumps(payload).encode(), headers=headers, method='POST')
        started = time.monotonic()
        try:
            with self.opener(request, timeout=self.timeout_seconds) as response:
                raw = json.load(response)
        except urllib.error.HTTPError as error:
            trace.event('llm_attempt', {'model':model,'api_style':style,'status':'failed',
                        'http_status':error.code,'latency_seconds':time.monotonic()-started,
                        'cost':{'kind':'unknown','amount':None}})
            # Never expose or persist an untrusted error body that may echo auth.
            raise LlmError(f'OpenCode HTTP {error.code}',retryable=error.code==429 or error.code>=500,
                           status=error.code) from None
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            trace.event('llm_attempt', {'model':model,'api_style':style,'status':'failed',
                        'error_type':type(error).__name__,'latency_seconds':time.monotonic()-started,
                        'cost':{'kind':'unknown','amount':None}})
            raise LlmError('OpenCode connection failure',retryable=True) from None
        except (ValueError, TypeError):
            trace.event('llm_attempt', {'model':model,'api_style':style,'status':'failed',
                        'error_type':'InvalidResponseJSON','latency_seconds':time.monotonic()-started,
                        'cost':{'kind':'unknown','amount':None}})
            raise LlmError('OpenCode returned invalid response JSON',retryable=True) from None
        if not isinstance(raw,dict) or not isinstance(raw.get('usage',{}),dict):
            trace.event('llm_attempt', {'model':model,'api_style':style,'status':'failed',
                        'error_type':'InvalidResponseEnvelope','latency_seconds':time.monotonic()-started,
                        'cost':{'kind':'unknown','amount':None}})
            raise LlmError('OpenCode returned invalid response envelope',retryable=True)
        trace.snapshot('C-response', visible_response(raw))
        usage = raw.get('usage') or {}
        if style == 'chat_completions':
            usage = {**usage,'input_tokens':usage.get('prompt_tokens',usage.get('input_tokens')),
                     'output_tokens':usage.get('completion_tokens',usage.get('output_tokens')),
                     'input_tokens_details':usage.get('prompt_tokens_details',{}),
                     'output_tokens_details':usage.get('completion_tokens_details',{})}
        elif style == 'messages':
            # Messages input_tokens excludes cache reads/writes. Our unified
            # total includes them; estimate_cost then charges each bucket once.
            inputs = [usage.get('input_tokens'), usage.get('cache_read_input_tokens', 0),
                      usage.get('cache_creation_input_tokens', 0)]
            usage = {**usage, 'input_tokens':sum(inputs)
                     if all(type(n) is int and n >= 0 for n in inputs) else None,
                     'input_tokens_details':{'cached_tokens':inputs[1],
                                             'cache_write_tokens':inputs[2]}}
        cost = estimate_cost(usage, self.pricing.get(model))
        # Only an explicit currency/amount object can mean reported cost. A
        # bare number has ambiguous units and is intentionally not interpreted.
        reported = raw.get('cost')
        if (isinstance(reported,dict) and isinstance(reported.get('amount'),(int,float))
            and not isinstance(reported['amount'],bool) and math.isfinite(reported['amount'])
            and reported['amount'] >= 0 and isinstance(reported.get('currency'),str)
            and reported['currency']):
            cost = {'kind':'reported','amount':reported['amount'],'currency':reported['currency']}
        latency = time.monotonic()-started
        trace.event('llm_attempt', {'model':raw.get('model',model),'api_style':style,'status':'received',
                                  'usage':usage,'cost':cost,'latency_seconds':latency})
        try:
            if style == 'responses':
                if raw.get('status') not in (None,'completed'):
                    raise LlmError('OpenCode response incomplete',retryable=True)
                text = ''.join(p.get('text','') for i in raw.get('output',[]) if i.get('type')=='message'
                               for p in i.get('content',[]) if p.get('type')=='output_text')
            elif style == 'chat_completions':
                choices = raw.get('choices') or []
                if not choices or choices[0].get('finish_reason') != 'stop':
                    raise LlmError('OpenCode chat response incomplete',retryable=True)
                text = choices[0].get('message',{}).get('content','')
            else:
                if raw.get('stop_reason') != 'end_turn':
                    raise LlmError('OpenCode messages response incomplete',retryable=True)
                text = ''.join(block.get('text','') for block in raw.get('content', [])
                               if block.get('type') == 'text')
        except (AttributeError,TypeError,KeyError,IndexError):
            # The paid attempt/usage was recorded above; do not count it twice.
            trace.event('llm_response_invalid', {'model':model,'api_style':style})
            raise LlmError('OpenCode response content malformed',retryable=True) from None
        if not isinstance(text, str) or not text:
            raise LlmError('OpenCode returned no text',retryable=True)
        return LlmResponse(text,raw.get('model') or 'unknown',style,usage,latency,cost,raw.get('id'))
