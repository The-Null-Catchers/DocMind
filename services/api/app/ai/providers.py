from __future__ import annotations

import hashlib
import math
import re
import subprocess
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import AsyncIterator
import httpx
from PIL import Image
from ..config import get_settings


class LLMProvider(ABC):
    name: str
    model: str

    @abstractmethod
    async def stream(self, *, system: str, messages: list[dict[str, str]]) -> AsyncIterator[str]: ...


class EmbeddingProvider(ABC):
    name: str
    model: str
    dimension: int

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True)
class OCRResult:
    text: str
    confidence: float | None


class OCRProvider(ABC):
    name: str

    @abstractmethod
    def extract_image(self, data: bytes, languages: str) -> OCRResult: ...


class RerankerProvider(ABC):
    name: str

    @abstractmethod
    async def rerank(self, query: str, texts: list[str]) -> list[float]: ...


class HashEmbeddingProvider(EmbeddingProvider):
    """Deterministic multilingual-ish feature hashing for local development and CI.

    It is deliberately not positioned as production semantic quality. It lets retrieval,
    tenancy, citation, and evaluation behavior be tested without external credentials.
    """

    name = "hash"

    def __init__(self, dimension: int = 384, model: str = "hash-384-v1"):
        self.dimension = dimension
        self.model = model

    @staticmethod
    def _tokens(text: str) -> list[str]:
        normalized = re.sub(r"\s+", " ", text.casefold()).strip()
        words = re.findall(r"[\w\u0600-\u06FF]+", normalized, flags=re.UNICODE)
        trigrams = [normalized[i:i+3] for i in range(max(0, len(normalized) - 2)) if " " not in normalized[i:i+3]]
        return words + trigrams

    async def embed(self, texts: list[str]) -> list[list[float]]:
        output: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dimension
            for token in self._tokens(text):
                digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
                idx = int.from_bytes(digest[:4], "big") % self.dimension
                sign = 1.0 if digest[4] & 1 else -1.0
                vector[idx] += sign
            norm = math.sqrt(sum(v * v for v in vector)) or 1.0
            output.append([v / norm for v in vector])
        return output


class OllamaEmbeddingProvider(EmbeddingProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str, dimension: int):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.dimension = dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(f"{self.base_url}/api/embed", json={"model": self.model, "input": texts})
            response.raise_for_status()
            return response.json()["embeddings"]


class MockGroundedLLM(LLMProvider):
    name = "mock"
    model = "mock-grounded-v1"

    async def stream(self, *, system: str, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        context = next((m["content"] for m in reversed(messages) if m["role"] == "system" and "SOURCE" in m["content"]), "")
        question = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        source_match = re.search(r"\[SOURCE C1\].*?\n(.*?)(?=\n\[SOURCE|\Z)", context, flags=re.S)
        if not source_match:
            answer = "I couldn't find support for that in the selected documents."
        else:
            excerpt = re.sub(r"\s+", " ", source_match.group(1)).strip()[:420]
            answer = f"Based on the retrieved source, {excerpt} [C1]"
            if re.search(r"[\u0600-\u06FF]", question):
                answer = f"وفقًا للمصدر المسترجع: {excerpt} [C1]"
        for token in re.findall(r"\S+\s*", answer):
            yield token


class OllamaLLM(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def stream(self, *, system: str, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        payload = {"model": self.model, "stream": True, "messages": [{"role": "system", "content": system}] + messages}
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    import json
                    data = json.loads(line)
                    content = data.get("message", {}).get("content")
                    if content:
                        yield content


class TesseractOCR(OCRProvider):
    name = "tesseract"

    def extract_image(self, data: bytes, languages: str) -> OCRResult:
        try:
            import pytesseract
            image = Image.open(BytesIO(data))
            details = pytesseract.image_to_data(image, lang=languages, output_type=pytesseract.Output.DICT)
            words: list[str] = []
            confidences: list[float] = []
            for text, confidence in zip(details.get("text", []), details.get("conf", []), strict=False):
                value = str(text).strip()
                try:
                    score = float(confidence)
                except (TypeError, ValueError):
                    score = -1
                if value:
                    words.append(value)
                if score >= 0:
                    confidences.append(score / 100.0)
            return OCRResult(text=" ".join(words), confidence=(sum(confidences) / len(confidences)) if confidences else None)
        except Exception as exc:
            raise RuntimeError(f"OCR failed: {exc}") from exc


class NoopReranker(RerankerProvider):
    name = "none"

    async def rerank(self, query: str, texts: list[str]) -> list[float]:
        return [1.0 - (i * 0.001) for i in range(len(texts))]


def get_embedding_provider() -> EmbeddingProvider:
    s = get_settings()
    if s.embedding_provider == "ollama":
        return OllamaEmbeddingProvider(s.ollama_base_url, s.ollama_embed_model, s.embedding_dimension)
    return HashEmbeddingProvider(s.embedding_dimension, s.embedding_model)


def get_llm_provider() -> LLMProvider:
    s = get_settings()
    if s.llm_provider == "ollama":
        return OllamaLLM(s.ollama_base_url, s.ollama_chat_model)
    return MockGroundedLLM()


def get_ocr_provider() -> OCRProvider:
    return TesseractOCR()


def get_reranker_provider() -> RerankerProvider:
    return NoopReranker()
