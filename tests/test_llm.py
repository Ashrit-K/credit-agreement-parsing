import json
import pytest
from pydantic import SecretStr
from credit_agreement_extractor.config import OpenCodeSettings
from credit_agreement_extractor.llm import OpenCodeClient, LlmError, estimate_cost


class Response:
    def __init__(self, data): self.data = data
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self): return json.dumps(self.data).encode()


def test_configurable_timeout_reaches_transport():
    timeouts = []
    def opener(request, timeout):
        timeouts.append(timeout)
        return Response({'model':'gpt-6-luna', 'status':'completed',
                         'output':[{'type':'message','content':[{'type':'output_text','text':'{}'}]}]})
    client = OpenCodeClient(OpenCodeSettings(api_key=SecretStr('key')),
                            opener=opener, timeout_seconds=300)
    client.complete('system', {}, model='gpt-6-luna')
    assert timeouts == [300]


@pytest.mark.parametrize('timeout', [0, -1, True, float('inf'), float('nan')])
def test_invalid_timeout_rejected_before_request(timeout):
    with pytest.raises(ValueError):
        OpenCodeClient(timeout_seconds=timeout)


@pytest.mark.parametrize('model', ['gpt-6-luna', 'deepseek-v4.1-flash'])
def test_output_allowance_reaches_reasoning_transport(model):
    payloads = []
    def opener(request, timeout):
        payloads.append(json.loads(request.data))
        return Response({'model':model,'status':'completed',
                         'output':[{'type':'message','content':[{'type':'output_text','text':'{}'}]}],
                         'choices':[{'finish_reason':'stop','message':{'content':'{}'}}]})
    client = OpenCodeClient(OpenCodeSettings(api_key=SecretStr('key')),
                            opener=opener, max_output_tokens=32768)
    client.complete('system',{},model=model)
    payload = payloads[0]
    assert payload.get('max_output_tokens',payload.get('max_tokens')) == 32768


@pytest.mark.parametrize('limit', [0, -1, True, 12.5])
def test_invalid_output_allowance_rejected(limit):
    with pytest.raises(ValueError):
        OpenCodeClient(max_output_tokens=limit)


@pytest.mark.parametrize('model,style', [('gpt-5.6-luna','responses'), ('qwen3.8-max','chat_completions')])
def test_endpoint_payload_normalization(model, style):
    requests = []
    def opener(request, timeout):
        requests.append(request)
        return Response({'model': model, 'status':'completed', 'usage':{'input_tokens':12,'output_tokens':3},
                         'output':[{'type':'message','content':[{'type':'output_text','text':'{}'}]}],
                         'choices':[{'finish_reason':'stop','message':{'content':'{}'}}]})
    client = OpenCodeClient(OpenCodeSettings(api_key=SecretStr('test-key')), opener=opener)
    result = client.complete('system', {'chunks':[]}, model=model)
    payload = json.loads(requests[0].data)
    assert requests[0].get_header('User-agent') == 'CreditAgreementParser/0.1'
    assert requests[0].full_url.endswith('/responses' if style == 'responses' else '/chat/completions')
    assert result.text == '{}'
    assert result.api_style == style
    if style == 'responses': assert payload['reasoning']['effort'] == 'medium'


def test_unknown_model_fails_without_explicit_override():
    client = OpenCodeClient(OpenCodeSettings(api_key=SecretStr('key')))
    with pytest.raises(ValueError): client.complete('s', {}, model='invented')


def test_cached_input_cost_and_unknown():
    usage = {'input_tokens':100,'output_tokens':20,'input_tokens_details':{'cached_tokens':40},
             'output_tokens_details':{'reasoning_tokens':10}}
    rates = {'input_per_million':1, 'cached_input_per_million':0.5,'output_per_million':2,
             'date':'2026-10-01','source':'test','currency':'USD'}
    assert estimate_cost(usage, rates)['amount'] == pytest.approx(0.00012)
    assert estimate_cost({}, rates)['kind'] == 'unknown'


@pytest.mark.parametrize('status,retryable', [(403,False),(401,False),(429,True),(500,True)])
def test_http_errors_are_sanitized(status,retryable,tmp_path):
    import urllib.error
    import io
    def opener(request,timeout):
        raise urllib.error.HTTPError(request.full_url,status,'SECRET-KEY',{},io.BytesIO(b'SECRET-KEY'))
    client=OpenCodeClient(OpenCodeSettings(api_key=SecretStr('SECRET-KEY')),opener=opener)
    with pytest.raises(LlmError) as error:
        client.complete('s',{},debug=True,trace_root=tmp_path)
    assert error.value.retryable==retryable
    assert 'SECRET-KEY' not in str(error.value)
    assert 'SECRET-KEY' not in ''.join(p.read_text() for p in tmp_path.rglob('*.json*'))


def test_non_object_response_is_retryable_and_logged(tmp_path):
    client=OpenCodeClient(OpenCodeSettings(api_key=SecretStr('key')),opener=lambda *a,**k:Response([]))
    with pytest.raises(LlmError) as error: client.complete('s',{},run_id='invalid',trace_root=tmp_path)
    assert error.value.retryable
    rows=[json.loads(line) for line in (tmp_path/'invalid'/'events.jsonl').read_text().splitlines()]
    assert any(row['event']=='llm_attempt' and row['status']=='failed' for row in rows)


def test_provider_reported_cost_takes_precedence(tmp_path):
    raw={'model':'gpt-5.6-luna','status':'completed','usage':{'input_tokens':1,'output_tokens':1},
         'cost':{'amount':0.002,'currency':'USD'},
         'output':[{'type':'message','content':[{'type':'output_text','text':'{}'}]}]}
    client=OpenCodeClient(OpenCodeSettings(api_key=SecretStr('key')),opener=lambda *a,**k:Response(raw))
    assert client.complete('s',{},trace_root=tmp_path).cost=={'kind':'reported','amount':0.002,'currency':'USD'}


def test_default_luna_rates_are_dated_and_handle_cache_write():
    from credit_agreement_extractor.llm import DEFAULT_PRICING
    rates=DEFAULT_PRICING['gpt-5.6-luna']
    result=estimate_cost({'input_tokens':423,'output_tokens':110},rates)
    assert result['amount']==pytest.approx(0.0002166)
    assert result['pricing_date']=='2026-10-01'
    assert estimate_cost({'input_tokens':272001,'output_tokens':1},rates)['kind']=='unknown'
    result=estimate_cost({'input_tokens':100,'output_tokens':0,
                          'input_tokens_details':{'cached_tokens':20,'cache_write_tokens':30}},rates)
    assert result['amount']==pytest.approx((50*0.20+20*0.02+30*0.25)/1e6)


@pytest.mark.parametrize('output',[42,[42],[{'type':'message','content':None}],[{'type':'message','content':[42]}]])
def test_malformed_responses_content_is_retryable(output,tmp_path):
    raw={'model':'gpt-5.6-luna','status':'completed','output':output}
    client=OpenCodeClient(OpenCodeSettings(api_key=SecretStr('key')),opener=lambda *a,**k:Response(raw))
    with pytest.raises(LlmError) as error: client.complete('s',{},trace_root=tmp_path)
    assert error.value.retryable


def test_responses_preserves_xhigh(tmp_path):
    requests = []
    def opener(request, timeout):
        requests.append(json.loads(request.data))
        return Response({'model':'gpt-5.6-luna','status':'completed','output':[
            {'type':'message','content':[{'type':'output_text','text':'{}'}]}]})
    client = OpenCodeClient(OpenCodeSettings(api_key=SecretStr('key')), opener=opener)
    client.complete('s', {}, model='gpt-5.6-luna', reasoning_effort='xhigh', trace_root=tmp_path)
    assert requests[0]['reasoning']['effort'] == 'xhigh'


def test_messages_high_normalizes_cache_usage_and_does_not_log_thinking(tmp_path):
    requests = []
    def opener(request, timeout):
        requests.append(request)
        return Response({'model':'qwen3.8-flash','id':'msg-test','stop_reason':'end_turn',
            'usage':{'input_tokens':10,'output_tokens':5,'cache_read_input_tokens':20,
                     'cache_creation_input_tokens':30},
            'content':[{'type':'thinking','thinking':'DO-NOT-LOG','signature':'HIDDEN'},
                       {'type':'text','text':'{}'}]})
    rates = {'date':'2026-10-01','source':'test','currency':'USD',
             'input_per_million':1,'output_per_million':2,
             'cached_input_per_million':0.1,'cache_write_per_million':1.25}
    client = OpenCodeClient(OpenCodeSettings(api_key=SecretStr('SECRET')), opener=opener,
                            pricing={'qwen3.8-flash':rates})
    result = client.complete('s', {}, model='qwen3.8-flash', reasoning_effort='high',
                             debug=True, trace_root=tmp_path)
    payload = json.loads(requests[0].data)
    assert requests[0].full_url.endswith('/messages')
    assert requests[0].get_header('Anthropic-version') == '2023-06-01'
    assert payload['thinking'] == {'type':'enabled','budget_tokens':16000}
    assert payload['max_tokens'] > payload['thinking']['budget_tokens']
    assert result.text == '{}' and result.api_style == 'messages'
    assert result.usage['input_tokens'] == 60
    assert result.cost['amount'] == pytest.approx((10+2+37.5+10)/1e6)
    logs = ''.join(p.read_text() for p in tmp_path.rglob('*.json*'))
    assert 'DO-NOT-LOG' not in logs and 'HIDDEN' not in logs and 'SECRET' not in logs


def test_chat_debug_does_not_log_hidden_reasoning(tmp_path):
    raw = {'model':'deepseek-v4-flash', 'choices':[{'finish_reason':'stop',
           'message':{'content':'{}','reasoning_content':'HIDDEN-CHAIN'}}]}
    client = OpenCodeClient(OpenCodeSettings(api_key=SecretStr('key')),
                            opener=lambda *a,**k:Response(raw))
    client.complete('s', {}, model='deepseek-v4-flash', debug=True, trace_root=tmp_path)
    assert 'HIDDEN-CHAIN' not in ''.join(p.read_text() for p in tmp_path.rglob('*.json*'))


@pytest.mark.parametrize('effort', ['low', 'medium', 'xhigh'])
def test_messages_does_not_silently_translate_unsupported_efforts(effort, tmp_path):
    def opener(*args, **kwargs):
        pytest.fail('Unsupported effort must fail before sending a paid request')
    client = OpenCodeClient(OpenCodeSettings(api_key=SecretStr('key')), opener=opener)
    with pytest.raises(ValueError, match='Messages supports'):
        client.complete('s', {}, model='qwen3.8-flash', reasoning_effort=effort, trace_root=tmp_path)


def test_messages_disabled_and_incomplete_usage_is_logged_once(tmp_path):
    requests=[]
    def opener(request, timeout):
        requests.append(json.loads(request.data))
        return Response({'model':'qwen3.8-flash','stop_reason':'max_tokens',
                         'usage':{'input_tokens':2,'output_tokens':3}, 'content':[]})
    client = OpenCodeClient(OpenCodeSettings(api_key=SecretStr('key')), opener=opener)
    with pytest.raises(LlmError, match='incomplete'):
        client.complete('s', {}, model='qwen3.8-flash', reasoning_effort='none',
                        run_id='incomplete', trace_root=tmp_path)
    assert requests[0]['thinking'] == {'type':'disabled'}
    events=[json.loads(line) for line in (tmp_path/'incomplete/events.jsonl').read_text().splitlines()]
    paid=[e for e in events if e['event']=='llm_attempt']
    assert len(paid)==1 and paid[0]['usage']['output_tokens']==3
