"""Public package interface for the credit-agreement extraction scaffold."""

from .api import extract_parties
from .chunking import ChunkArtifact, InvalidChunkInputError, build_chunks
from .conversion import (
    ConversionArtifact,
    InvalidDocumentInputError,
    convert_document,
)
from .hierarchy import InvalidHierarchyInputError

__all__ = [
    "ConversionArtifact",
    "ChunkArtifact",
    "InvalidChunkInputError",
    "InvalidDocumentInputError",
    "InvalidHierarchyInputError",
    "convert_document",
    "build_chunks",
    "extract_parties",
]
