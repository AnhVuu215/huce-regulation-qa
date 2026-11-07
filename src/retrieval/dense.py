"""Tìm kiếm vector. Embedding được cache theo nội dung để chạy eval lại không phải tính lại."""

import hashlib
from pathlib import Path

import numpy as np

from retrieval.corpus import Passage

DEFAULT_MODEL = "BAAI/bge-m3"


class Embedder:
    def __init__(self, model_name: str = DEFAULT_MODEL, cache_dir: Path | None = None,
                 max_seq_length: int = 1024):
        self.model_name = model_name
        self.max_seq_length = max_seq_length
        self._model = None
        self._cache_path = (
            cache_dir / f"{model_name.replace('/', '__')}.npz" if cache_dir else None
        )
        self._cache: dict[str, np.ndarray] = {}
        if self._cache_path and self._cache_path.exists():
            with np.load(self._cache_path) as data:
                self._cache = {key: data[key] for key in data.files}

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name, device="cpu")
            self._model.max_seq_length = self.max_seq_length
        return self._model

    @staticmethod
    def _key(text: str) -> str:
        return hashlib.sha1(text.encode("utf-8")).hexdigest()

    def encode(self, texts: list[str]) -> np.ndarray:
        missing = list(dict.fromkeys(t for t in texts if self._key(t) not in self._cache))
        if missing:
            vectors = self._load().encode(
                missing,
                batch_size=8,
                normalize_embeddings=True,
                show_progress_bar=len(missing) > 50,
            )
            for text, vec in zip(missing, vectors, strict=True):
                self._cache[self._key(text)] = vec.astype(np.float32)
            self._save()
        return np.stack([self._cache[self._key(t)] for t in texts])

    def _save(self) -> None:
        if self._cache_path:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            np.savez(self._cache_path, **self._cache)


class DenseIndex:
    def __init__(self, passages: list[Passage], embedder: Embedder):
        self.passages = passages
        self.embedder = embedder
        self.matrix = embedder.encode([p.text for p in passages])

    def search(self, query: str, k: int = 10) -> list[tuple[Passage, float]]:
        scores = self.matrix @ self.embedder.encode([query])[0]
        order = np.argsort(-scores)[:k]
        return [(self.passages[i], float(scores[i])) for i in order]
