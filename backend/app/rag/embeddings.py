"""Configurable embedding providers.

* ``local`` - hashed bag-of-words (unigrams + bigrams, sublinear TF, signed
  feature hashing into 1024 dimensions, L2-normalised). Runs offline with no
  model download. It is a *lexical* embedding: it matches shared words, not
  meaning. Use it for development, tests and air-gapped installs.
* ``openai_compatible`` - any server implementing ``POST /embeddings``
  (OpenAI, Azure OpenAI, Ollama, vLLM, LM Studio...). Gives semantic retrieval.

Vectors from different models are never compared: each chunk stores the
model id it was embedded with and retrieval filters on it.
"""
import hashlib
import math
import re
import time
from functools import lru_cache
from typing import Protocol

import httpx

from app.core.config import settings

STOPWORDS = set("""a an and are as at be by can do does for from has have how i if in into is it its me my of on or our
so that the their them then there these they this to us was we what when where which who why will with you your
please""".split())


class Embedder(Protocol):
    model_id: str
    default_min_score: float

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _stem(word: str) -> str:
    for suffix in ("ations", "ation", "ings", "ing", "ies", "ed", "es", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return word


def tokens(text: str) -> list[str]:
    return [_stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS and len(w) > 1]


class LexicalHashEmbedder:
    dim = 1024
    model_id = "local:lexical-hash-1024-v1"
    default_min_score = 0.13  # measured: unrelated queries score <= 0.12, weakest relevant top hit 0.14

    def _vector(self, text: str) -> list[float]:
        words = tokens(text)
        features = words + [f"{a}_{b}" for a, b in zip(words, words[1:], strict=False)]
        counts: dict[str, int] = {}
        for feature in features:
            counts[feature] = counts.get(feature, 0) + 1
        vector = [0.0] * self.dim
        for feature, count in counts.items():
            digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "little") % self.dim
            sign = 1.0 if digest[4] & 1 else -1.0
            weight = (1 + math.log(count)) * (0.6 if "_" in feature else 1.0)
            vector[index] += sign * weight
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]


class OpenAICompatibleEmbedder:
    def __init__(self, base_url: str, api_key: str, model: str):
        if not model:
            raise ValueError("EMBEDDING_MODEL is required for the openai_compatible embedding provider")
        self.base_url, self.api_key, self.model = base_url.rstrip("/"), api_key, model
        self.model_id = f"openai_compatible:{model}"
        self.default_min_score = 0.30

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        for start in range(0, len(texts), 64):
            batch = texts[start:start + 64]
            for attempt in range(settings.LLM_MAX_RETRIES + 1):
                try:
                    response = httpx.post(f"{self.base_url}/embeddings", headers=headers,
                                          json={"model": self.model, "input": batch},
                                          timeout=settings.LLM_TIMEOUT_SECONDS)
                    if response.status_code in (429, 500, 502, 503, 504) and attempt < settings.LLM_MAX_RETRIES:
                        time.sleep(0.5 * 3 ** attempt)
                        continue
                    response.raise_for_status()
                    data = sorted(response.json()["data"], key=lambda item: item["index"])
                    out.extend(item["embedding"] for item in data)
                    break
                except httpx.TransportError:
                    if attempt >= settings.LLM_MAX_RETRIES:
                        raise
                    time.sleep(0.5 * 3 ** attempt)
        return out


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    if settings.EMBEDDING_PROVIDER == "openai_compatible":
        return OpenAICompatibleEmbedder(settings.EMBEDDING_BASE_URL, settings.EMBEDDING_API_KEY,
                                        settings.EMBEDDING_MODEL)
    if settings.EMBEDDING_PROVIDER != "local":
        raise ValueError(f"Unknown EMBEDDING_PROVIDER {settings.EMBEDDING_PROVIDER!r}")
    return LexicalHashEmbedder()
