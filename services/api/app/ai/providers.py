from __future__ import annotations

import hashlib
import json
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


class OpenAICompatibleLLM(LLMProvider):
    def __init__(self, *, name: str, base_url: str, api_key: str, model: str):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def stream(self, *, system: str, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        payload = {
            "model": self.model,
            "stream": True,
            "messages": [{"role": "system", "content": system}] + messages,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if not raw or raw == "[DONE]":
                        continue
                    data = json.loads(raw)
                    choices = data.get("choices") or []
                    if not choices:
                        continue
                    content = choices[0].get("delta", {}).get("content")
                    if content:
                        yield content


class AnthropicLLM(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def stream(self, *, system: str, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        payload = {
            "model": self.model,
            "system": system,
            "messages": [
                message for message in messages if message.get("role") in {"user", "assistant"}
            ],
            "max_tokens": 4096,
            "stream": True,
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                "https://api.anthropic.com/v1/messages",
                json=payload,
                headers=headers,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if not raw:
                        continue
                    data = json.loads(raw)
                    if data.get("type") != "content_block_delta":
                        continue
                    delta = data.get("delta", {})
                    if delta.get("type") == "text_delta" and delta.get("text"):
                        yield delta["text"]


class GeminiLLM(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    @staticmethod
    def _contents(messages: list[dict[str, str]]) -> list[dict]:
        contents: list[dict] = []
        for message in messages:
            role = message.get("role")
            if role == "system":
                role = "user"
            if role not in {"user", "assistant", "model"}:
                continue
            contents.append(
                {
                    "role": "model" if role in {"assistant", "model"} else "user",
                    "parts": [{"text": message.get("content", "")}],
                }
            )
        return contents

    async def stream(self, *, system: str, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": self._contents(messages),
        }
        headers = {"x-goog-api-key": self.api_key}
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:streamGenerateContent?alt=sse"
        )
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if not raw:
                        continue
                    data = json.loads(raw)
                    candidates = data.get("candidates") or []
                    if not candidates:
                        continue
                    parts = candidates[0].get("content", {}).get("parts", [])
                    for part in parts:
                        text = part.get("text")
                        if text:
                            yield text


class OpenAIEmbeddingProvider(EmbeddingProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str, dimension: int):
        self.api_key = api_key
        self.model = model
        self.dimension = dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        payload: dict = {"model": self.model, "input": texts}
        if self.dimension:
            payload["dimensions"] = self.dimension
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
            rows = sorted(response.json()["data"], key=lambda row: row["index"])
            return [row["embedding"] for row in rows]


class GeminiEmbeddingProvider(EmbeddingProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str, dimension: int):
        self.api_key = api_key
        self.model = model
        self.dimension = dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        model_name = self.model.removeprefix("models/")
        requests = [
            {
                "model": f"models/{model_name}",
                "content": {"parts": [{"text": text}]},
                "embedContentConfig": {
                    "taskType": "SEMANTIC_SIMILARITY",
                    "outputDimensionality": self.dimension,
                },
            }
            for text in texts
        ]
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model_name}:batchEmbedContents"
        )
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                url,
                json={"requests": requests},
                headers={"x-goog-api-key": self.api_key},
            )
            response.raise_for_status()
            return [embedding["values"] for embedding in response.json()["embeddings"]]


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
    provider = s.embedding_provider.lower()
    if provider == "ollama":
        return OllamaEmbeddingProvider(
            s.ollama_base_url,
            s.ollama_embed_model,
            s.embedding_dimension,
        )
    if provider == "openai":
        if not s.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI embeddings")
        return OpenAIEmbeddingProvider(
            s.openai_api_key,
            s.embedding_model,
            s.embedding_dimension,
        )
    if provider == "gemini":
        if not s.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required for Gemini embeddings")
        return GeminiEmbeddingProvider(
            s.gemini_api_key,
            s.embedding_model,
            s.embedding_dimension,
        )
    return HashEmbeddingProvider(s.embedding_dimension, s.embedding_model)


def get_llm_provider() -> LLMProvider:
    s = get_settings()
    provider = s.llm_provider.lower()
    if provider == "ollama":
        return OllamaLLM(s.ollama_base_url, s.ollama_chat_model)
    if provider == "openai":
        if not s.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI")
        return OpenAICompatibleLLM(
            name="openai",
            base_url="https://api.openai.com/v1",
            api_key=s.openai_api_key,
            model=s.llm_model,
        )
    if provider == "groq":
        if not s.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is required for Groq")
        return OpenAICompatibleLLM(
            name="groq",
            base_url="https://api.groq.com/openai/v1",
            api_key=s.groq_api_key,
            model=s.llm_model,
        )
    if provider == "anthropic":
        if not s.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for Anthropic")
        return AnthropicLLM(s.anthropic_api_key, s.llm_model)
    if provider == "gemini":
        if not s.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required for Gemini")
        return GeminiLLM(s.gemini_api_key, s.llm_model)
    return MockGroundedLLM()


def get_ocr_provider() -> OCRProvider:
    return TesseractOCR()


def get_reranker_provider() -> RerankerProvider:
    return NoopReranker()
