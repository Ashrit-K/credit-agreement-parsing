"""Explicit whole-pipeline composition; standalone stages remain standalone."""
from pathlib import Path

from .chunking import build_chunks
from .conversion import convert_document
from .orchestrator import extract_credit_terms
from .topic_map import build_topic_map
from .topic_reflection import reflect_topics
from .tracing import current_trace, traced


@traced('pipeline')
def run_pipeline(path: str | Path, *, client=None, model='deepseek-v4-pro',
                 reasoning_effort='high', classification_model=None,
                 classification_reasoning_effort='medium', use_hierarchy=True,
                 debug=False, run_id=None, trace_root='tmp/runs', generated_root=None) -> dict:
    """Convert, classify, map and extract through existing public boundaries.

    The direct D call is the readiness signal. No background worker, queue or
    paid work is hidden inside B3. Each stage must return successfully before
    the next is invoked; nested spans share the runner's generated/provided ID.
    Classification and extraction models can be changed independently.
    """
    options = dict(debug=debug, run_id=current_trace().run_id, trace_root=trace_root)
    # A local server may start from any directory. Explicit roots avoid changing
    # the process cwd (unsafe while another thread handles HTTP requests).
    root = Path(generated_root).resolve() if generated_root is not None else None
    conversion = convert_document(path, use_hierarchy=use_hierarchy,
        **({'output_root': root/'converted'} if root else {}), **options)
    chunks = build_chunks(conversion,
        **({'output_root': root/'stage_b'} if root else {}), **options)
    # Omitting a model must preserve B2's own default; passing None would
    # override that default and fail its explicit model-to-endpoint routing.
    classification_options = ({} if classification_model is None
                              else {'model': classification_model})
    classified = reflect_topics(chunks, client=client,
        reasoning_effort=classification_reasoning_effort, **classification_options, **options)
    topic_map = build_topic_map(chunks, classified, **options)
    current_trace().event('topic_map_ready')
    return extract_credit_terms(topic_map, chunks, conversion=conversion, client=client,
        model=model, reasoning_effort=reasoning_effort,
        **({'output_root': root/'stage_d'} if root else {}), **options)
