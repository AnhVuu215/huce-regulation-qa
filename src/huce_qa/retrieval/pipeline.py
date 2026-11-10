"""Pipeline truy xuất có cấu hình: mỗi bước bật/tắt được để đo đóng góp trong bảng ablation."""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from huce_qa.retrieval.bm25 import BM25
from huce_qa.retrieval.corpus import Passage

RRF_K = 60


@dataclass(frozen=True)
class RetrievalConfig:
    name: str
    chunking: str = "structure"  # "window" (baseline) | "structure"
    window_words: int = 200
    window_overlap: int = 50
    hybrid: bool = False  # dense + BM25, gộp bằng Reciprocal Rank Fusion
    synonyms: bool = False  # mở rộng truy vấn bằng từ điển ngôn ngữ sinh viên
    rerank: bool = False
    rerank_candidates: int = 20
    khoa_filter: bool = False  # lọc phiên bản theo khóa trước khi tìm
    decompose: bool = False  # tách câu hỏi ghép thành truy vấn con, gộp bằng RRF
    embedding_model: str = "BAAI/bge-m3"


MIN_SUBQUERY_WORDS = 4


def sub_queries(question: str) -> list[str]:
    """Câu hỏi ghép ("A? B?", "điều kiện A và B") tìm riêng từng vế; luôn giữ cả câu gốc.
    Chỉ tách khi mỗi vế đủ dài, để không cắt cụm như "học lại và cải thiện"."""
    parts = []
    for sentence in re.split(r"\?\s*", question):
        pieces = re.split(r"\s+và\s+", sentence.strip())
        if len(pieces) > 1 and all(len(p.split()) >= MIN_SUBQUERY_WORDS for p in pieces):
            parts += pieces
        elif sentence.strip():
            parts.append(sentence.strip())
    parts = [p for p in parts if len(p.split()) >= MIN_SUBQUERY_WORDS]
    return list(dict.fromkeys([question, *parts])) if len(parts) > 1 else [question]


def load_synonyms(path: Path) -> list[tuple[list[str], str]]:
    return [(e["terms"], e["expand"]) for e in yaml.safe_load(path.read_text(encoding="utf-8"))]


def _contains(text: str, term: str) -> bool:
    # Khớp theo ranh giới từ: "tín" không được khớp vào giữa "tính".
    return re.search(rf"(?<!\w){re.escape(term.strip())}(?!\w)", text) is not None


def expand_query(query: str, synonyms: list[tuple[list[str], str]]) -> str:
    lowered = query.lower()
    extra = [expand for terms, expand in synonyms if any(_contains(lowered, t) for t in terms)]
    return " ".join([query, *extra])


def rrf(rankings: list[list[int]], k: int = RRF_K) -> list[int]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, idx in enumerate(ranking, start=1):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=lambda i: -scores[i])


class Retriever:
    def __init__(
        self,
        config: RetrievalConfig,
        passages: list[Passage],
        embedder,
        reranker=None,
        synonyms=None,
    ):
        self.config = config
        self.passages = passages
        self.embedder = embedder
        self.reranker = reranker
        self.synonyms = synonyms or []
        self.matrix = embedder.encode([p.text for p in passages])
        self.bm25 = BM25([p.text for p in passages]) if config.hybrid else None

    def max_similarity(self, question: str, khoa: int | None = None) -> float:
        """Cosine cao nhất giữa câu hỏi gốc và các đoạn được phép: dùng làm cổng liên quan."""
        allowed = [
            i
            for i, p in enumerate(self.passages)
            if not (self.config.khoa_filter and khoa is not None) or p.ap_dung_cho(khoa)
        ]
        return float((self.matrix[allowed] @ self.embedder.encode_query(question)).max())

    def _rankings(self, query: str, allowed: list[int]) -> list[list[int]]:
        dense = self.matrix[allowed] @ self.embedder.encode_query(query)
        rankings = [[allowed[i] for i in dense.argsort()[::-1]]]
        if self.bm25 is not None:
            lexical = self.bm25.scores(query)
            rankings.append(sorted(allowed, key=lambda i: -lexical[i]))
        return rankings

    def search(self, question: str, khoa: int | None = None, k: int = 10) -> list[Passage]:
        cfg = self.config
        allowed = [
            i
            for i, p in enumerate(self.passages)
            if not (cfg.khoa_filter and khoa is not None) or p.ap_dung_cho(khoa)
        ]
        queries = sub_queries(question) if cfg.decompose else [question]
        expanded = [expand_query(q, self.synonyms) if cfg.synonyms else q for q in queries]
        # Mã hóa mọi câu cần dùng trong một lượt, kể cả câu gốc cho cổng liên quan
        # (max_similarity): trên CPU một lượt rẻ hơn nhiều lượt riêng.
        self.embedder.encode_queries([*expanded, question])
        rankings = []
        for query in expanded:
            rankings += self._rankings(query, allowed)
        ranked = rrf(rankings) if len(rankings) > 1 else rankings[0]

        if cfg.rerank and self.reranker is not None:
            pool = ranked[: cfg.rerank_candidates]
            # Reranker chấm câu hỏi gốc: phần mở rộng chỉ để tìm ứng viên.
            scores = self.reranker.scores(question, [self.passages[i].text for i in pool])
            ranked = [i for _, i in sorted(zip(scores, pool, strict=True), key=lambda x: -x[0])]
        return [self.passages[i] for i in ranked[:k]]
