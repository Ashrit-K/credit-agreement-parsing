"""Abstract LLM provider interface — scaffold for v2."""

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Base class for LLM providers."""

    @abstractmethod
    def extract_structured(self, text: str, prompt: str) -> dict:
        """Send text + prompt to LLM, return structured extraction."""
        ...

    @abstractmethod
    def classify(self, text: str, categories: list[str]) -> str:
        """Classify text into one of the given categories."""
        ...


class MockLLMProvider(LLMProvider):
    """No-op provider for v1 — returns empty results."""

    def extract_structured(self, text: str, prompt: str) -> dict:
        return {}

    def classify(self, text: str, categories: list[str]) -> str:
        return categories[0] if categories else ""
