"""Stage D's single job/output boundary and durable completion contract."""
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from .chunking import ChunkArtifact
from .conversion import ConversionArtifact
from .evidence import retrieve_evidence
from .extraction_specialist import CreditTermSpecialist, PROMPT_VERSION
from .retrieval import document_hash
from .topic_map import TopicMapArtifact
from .topic_taxonomy import VOCABULARY
from .tracing import atomic_json, current_trace, traced

EXTRACTION_TOPICS = tuple(topic for topic in VOCABULARY if topic in (
    'parties_and_roles', 'facility_and_commitment_terms', 'interest_and_fees',
    'interest_and_fees.pik_toggle', 'contract_definitions'))


@traced('D4')
def _persist(result, packet, *, output_root, model, reasoning_effort, api_style):
    """Manifest-last completion in a fresh folder, never replace a saved run."""
    destination = Path(output_root) / result['document_id'] / uuid4().hex
    result_path, manifest_path = destination/'document.extraction.json', destination/'manifest.json'
    atomic_json(result_path, result)
    manifest = dict(schema_version=1, status='completed', source_sha256=result['document_id'],
        run_id=current_trace().run_id, prompt_version=PROMPT_VERSION,
        model=model, reasoning_effort=reasoning_effort, api_style=api_style,
        evidence_sha256=document_hash(packet), inputs=packet['inputs'],
        requested_topics=packet['requested_topics'],
        result_sha256=hashlib.sha256(result_path.read_bytes()).hexdigest(),
        artifacts={'result_json': result_path.name})
    atomic_json(manifest_path, manifest)
    current_trace().event('extraction_artifact', {'result_path': str(result_path),
                                                'manifest_path': str(manifest_path)})
    current_trace().snapshot('D4-manifest', manifest)
    return result


@traced('D1')
def extract_credit_terms(topic_map: TopicMapArtifact, chunks: ChunkArtifact, *,
                         conversion: ConversionArtifact | None = None, client=None,
                         model='deepseek-v4-pro', reasoning_effort='high', api_style=None,
                         output_root: str | Path = 'tmp/stage_d', debug=False,
                         run_id=None, trace_root='tmp/runs') -> dict:
    """Extract the three agreed families from a completed, bound topic map.

    Only this orchestrator accepts Stage D jobs. The specialist's retrieval tool
    can access approved topics on this one source, not external files/reference
    answers. B4/B5 validate readiness and fingerprints before any paid call.
    """
    trace = current_trace()
    options = dict(debug=debug, run_id=trace.run_id, trace_root=trace_root)

    def retrieve():
        artifact = retrieve_evidence(topic_map, chunks, topics=list(EXTRACTION_TOPICS),
                                     conversion=conversion, **options)
        packet = json.loads(artifact.evidence_json_path.read_bytes())
        trace.event('extraction_evidence_ready', {'source_sha256': artifact.source_sha256,
                                                'topics': list(artifact.requested_topics)})
        return packet

    with trace.bind(source_sha256=chunks.source_sha256):
        result, packet, items, used_model, used_style = CreditTermSpecialist().run(retrieve,
            client=client, model=model, reasoning_effort=reasoning_effort,
            api_style=api_style, **options)
        # Resolve readable provenance from supplied source records, never from
        # model-created page numbers or excerpts. Keep only cited items.
        cited = set()

        def collect(value):
            if isinstance(value, dict):
                cited.update(value.get('evidence_item_ids', []))
                for child in value.values(): collect(child)
            elif isinstance(value, list):
                for child in value: collect(child)

        collect(result)
        completed = dict(schema_version=1, status='completed', document_id=chunks.source_sha256,
                         **result, source_evidence={key: items[key] for key in sorted(cited)})
        return _persist(completed, packet, output_root=output_root, model=used_model,
                        reasoning_effort=reasoning_effort, api_style=used_style)
