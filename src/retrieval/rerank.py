"""Reranker cross-encoder: chấm lại từng cặp (câu hỏi, đoạn). Điểm được cache theo nội dung."""

import hashlib
import json
from pathlib import Path

DEFAULT_RERANKER = "BAAI/bge-reranker-v2-m3"


class Reranker:
    def __init__(self, model_name: str = DEFAULT_RERANKER, cache_dir: Path | None = None,
                 max_length: int = 512):
        self.model_name = model_name
        self.max_length = max_length
        self._model = None
        self._cache_path = (
            cache_dir / f"rerank__{model_name.replace('/', '__')}.json" if cache_dir else None
        )
        self._cache: dict[str, float] = {}
        if self._cache_path and self._cache_path.exists():
            self._cache = json.loads(self._cache_path.read_text(encoding="utf-8"))

    @staticmethod
    def _key(query: str, text: str) -> str:
        return hashlib.sha1(f"{query}\x00{text}".encode()).hexdigest()

    def scores(self, query: str, texts: list[str]) -> list[float]:
        missing = [t for t in texts if self._key(query, t) not in self._cache]
        if missing:
            if self._model is None:
                from sentence_transformers import CrossEncoder

                self._model = CrossEncoder(
                    self.model_name, max_length=self.max_length, device="cpu"
                )
            values = self._model.predict([(query, t) for t in missing], batch_size=8)
            for text, value in zip(missing, values, strict=True):
                self._cache[self._key(query, text)] = float(value)
            if self._cache_path:
                self._cache_path.parent.mkdir(parents=True, exist_ok=True)
                self._cache_path.write_text(json.dumps(self._cache), encoding="utf-8")
        return [self._cache[self._key(query, t)] for t in texts]
