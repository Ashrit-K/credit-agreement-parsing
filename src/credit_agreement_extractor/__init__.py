"""Public package interface for the credit-agreement extraction scaffold."""

from .api import extract_parties
from .chunking import ChunkArtifact, InvalidChunkInputError, build_chunks
from .conversion import (
    ConversionArtifact,
    InvalidDocumentInputError,
    convert_document,
)
from .hierarchy import InvalidHierarchyInputError
from .chunk_validation import InvalidTopicInputError
from .topic_reflection import TopicClassificationArtifact, reflect_topics
from .topic_map import TopicMapArtifact, build_topic_map
from .llm import OpenCodeClient, LlmResponse, LlmError
from .tracing import summarize_run

__all__ = [
    "TopicClassificationArtifact", "reflect_topics", "TopicMapArtifact", "build_topic_map",
    "OpenCodeClient", "LlmResponse", "LlmError",
    "summarize_run",
    "ConversionArtifact",
    "ChunkArtifact",
    "InvalidChunkInputError",
    "InvalidDocumentInputError",
    "InvalidHierarchyInputError",
    "convert_document",
    "build_chunks",
    "extract_parties",
    "InvalidTopicInputError",
]
