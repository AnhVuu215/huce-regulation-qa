"""Tìm kiếm vector. Embedding được cache theo nội dung để chạy eval lại không phải tính lại."""

import hashlib
import threading
from collections import OrderedDict
from pathlib import Path

import numpy as np

from huce_qa.retrieval.corpus import Passage

DEFAULT_MODEL = "BAAI/bge-m3"
QUERY_CACHE_SIZE = 512


class Embedder:
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        cache_dir: Path | None = None,
        max_seq_length: int = 1024,
        seed_dir: Path | None = None,
    ):
        """`seed_dir`: embedding dựng sẵn, chỉ đọc (data/embeddings trong repo), để máy mới không
        phải tính lại các đoạn văn bản; `cache_dir` là cache ghi được cho phần còn lại."""
        self.model_name = model_name
        self.max_seq_length = max_seq_length
        self._model = None
        # Số văn bản đã phải tính bằng mô hình (không có trong hạt giống hay cache).
        self.computed = 0
        filename = f"{model_name.replace('/', '__')}.npz"
        self._cache_path = cache_dir / filename if cache_dir else None
        self._cache: dict[str, np.ndarray] = {}
        # Câu hỏi chỉ giữ trong bộ nhớ: ghi vào file cache thì mỗi câu hỏi mới phải ghi lại cả
        # file (hàng MB), và file phình theo số câu người dùng hỏi.
        self._queries: OrderedDict[str, np.ndarray] = OrderedDict()
        # API trả lời nhiều request song song; mô hình chạy trên CPU nên mã hóa lần lượt.
        self._lock = threading.Lock()
        for path in [seed_dir / filename if seed_dir else None, self._cache_path]:
            if path and path.exists():
                with np.load(path) as data:
                    self._cache.update({key: data[key] for key in data.files})

    def export(self, texts: list[str], path: Path) -> None:
        """Ghi embedding của đúng các đoạn này ra file hạt giống."""
        vectors = self.encode(texts)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, **{self._key(t): v for t, v in zip(texts, vectors, strict=True)})

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
            self.computed += len(missing)
            self._save()
        return np.stack([self._cache[self._key(t)] for t in texts])

    def encode_query(self, text: str) -> np.ndarray:
        """Vector của một câu hỏi; không ghi cache ra đĩa."""
        return self.encode_queries([text])[0]

    def encode_queries(self, texts: list[str]) -> np.ndarray:
        """Vector của các câu hỏi, mã hóa chung một lượt (rẻ hơn nhiều lượt riêng trên CPU).
        Chỉ giữ trong bộ nhớ: ghi ra file cache thì mỗi câu mới phải ghi lại cả file."""
        with self._lock:
            missing = list(dict.fromkeys(t for t in texts if self._lookup(t) is None))
            if missing:
                vectors = self._load().encode(missing, normalize_embeddings=True)
                for text, vec in zip(missing, vectors, strict=True):
                    self._queries[self._key(text)] = vec.astype(np.float32)
                while len(self._queries) > QUERY_CACHE_SIZE:
                    self._queries.popitem(last=False)
            return np.stack([self._require(t) for t in texts])

    def _lookup(self, text: str) -> np.ndarray | None:
        key = self._key(text)
        if key in self._queries:
            self._queries.move_to_end(key)
            return self._queries[key]
        return self._cache.get(key)

    def _require(self, text: str) -> np.ndarray:
        vec = self._lookup(text)
        if vec is None:
            raise KeyError(f"Chưa có embedding cho: {text[:50]}")
        return vec

    def warm_up(self) -> None:
        """Nạp mô hình và chạy thử một lượt, bỏ qua cache: người hỏi đầu tiên không phải chờ."""
        self._load().encode(["khởi động"], normalize_embeddings=True)

    def _save(self) -> None:
        if self._cache_path:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            # Stub của numpy khai báo **kwds trùng tên với allow_pickle: bool, nên mypy báo nhầm.
            np.savez(self._cache_path, **self._cache)  # type: ignore[arg-type]


class DenseIndex:
    def __init__(self, passages: list[Passage], embedder: Embedder):
        self.passages = passages
        self.embedder = embedder
        self.matrix = embedder.encode([p.text for p in passages])

    def search(self, query: str, k: int = 10) -> list[tuple[Passage, float]]:
        scores = self.matrix @ self.embedder.encode_query(query)
        order = np.argsort(-scores)[:k]
        return [(self.passages[i], float(scores[i])) for i in order]
