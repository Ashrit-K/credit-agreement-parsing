"""Golden-set evaluation helpers."""

from src.evaluation.golden_set_eval import (
    EvaluationRow,
    ManifestEntry,
    evaluate_manifest,
    evaluate_manifest_entries,
    format_compact_table,
    load_expected_labels,
    load_manifest,
    write_evaluation_csv,
)
from src.evaluation.golden_set_labels import (
    DEFAULT_EXPECTED_OUTPUTS_PATH,
    DEFAULT_GOLDEN_SET_DIR,
    DEFAULT_LABELS_DIR,
    DEFAULT_PDF_DIR,
    export_expected_outputs,
    get_label_path,
    list_golden_pdfs,
    load_label,
    load_or_create_label,
    prefill_label_payload,
    save_label,
)

__all__ = [
    "EvaluationRow",
    "ManifestEntry",
    "load_manifest",
    "load_expected_labels",
    "evaluate_manifest_entries",
    "evaluate_manifest",
    "format_compact_table",
    "write_evaluation_csv",
    "DEFAULT_GOLDEN_SET_DIR",
    "DEFAULT_PDF_DIR",
    "DEFAULT_LABELS_DIR",
    "DEFAULT_EXPECTED_OUTPUTS_PATH",
    "list_golden_pdfs",
    "prefill_label_payload",
    "get_label_path",
    "load_label",
    "save_label",
    "load_or_create_label",
    "export_expected_outputs",
]
