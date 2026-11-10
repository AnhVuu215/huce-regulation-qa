from pathlib import Path

import pytest

from huce_qa.ingestion.chunker import chunk_document
from huce_qa.ingestion.cli import parse_registered
from huce_qa.ingestion.registry import load_registry
from huce_qa.retrieval.bm25 import BM25, tokenize
from huce_qa.retrieval.pipeline import expand_query, load_synonyms, rrf

ROOT = Path(__file__).resolve().parents[1]


def test_tokenize_adds_syllable_pairs_and_normalizes_math_letters():
    assert "thôi_học" in tokenize("buộc thôi học")
    assert "s" in tokenize("𝑆")


def test_bm25_prefers_exact_phrase():
    bm25 = BM25(["sinh viên bị buộc thôi học", "sinh viên học thôi", "điểm trung bình"])
    scores = bm25.scores("buộc thôi học")
    assert scores[0] > scores[1] > scores[2]


def test_rrf_rewards_agreement():
    assert rrf([[1, 2, 3], [3, 1, 2]])[0] == 1


def test_synonym_expansion_uses_word_boundaries():
    synonyms = load_synonyms(ROOT / "data" / "synonyms.yaml")
    assert "buộc thôi học" in expand_query("Bị đuổi học thì sao?", synonyms)
    assert "tín chỉ" in expand_query("Đăng ký tối đa bao nhiêu tín?", synonyms)
    assert expand_query("Cách tính điểm", synonyms) == "Cách tính điểm"


def test_long_khoan_is_split_on_diem_and_keeps_intro():
    doc = next(
        d
        for d in load_registry(ROOT / "data/registry.yaml").documents
        if d.doc_id == "qc-dhxd-2022"
    )
    chunks = chunk_document(doc, parse_registered(doc, ROOT))
    parts = [c for c in chunks if c.dieu == 3 and c.khoan == 2]
    assert len(parts) > 1
    assert all("2. Đào tạo theo tín chỉ:" in c.text for c in parts)
    assert len({c.chunk_id for c in chunks}) == len(chunks)


class _CountingModel:
    def __init__(self):
        self.calls = 0

    def encode(self, texts, **kwargs):
        import numpy as np  # noqa: PLC0415

        self.calls += 1
        return np.ones((len(texts), 4), dtype=np.float32)


def test_query_embedding_stays_in_memory(tmp_path):
    pytest.importorskip("numpy")  # CI không cài nhóm ml
    from huce_qa.retrieval.dense import Embedder  # noqa: PLC0415

    embedder = Embedder(cache_dir=tmp_path)
    embedder._model = model = _CountingModel()
    embedder.encode_query("học lại môn")
    embedder.encode_query("học lại môn")
    assert model.calls == 1
    # Câu hỏi không được ghi file cache: mỗi câu mới sẽ phải ghi lại cả file.
    assert not list(tmp_path.iterdir())


def test_queries_encoded_in_one_batch_and_warm_up_bypasses_cache(tmp_path):
    pytest.importorskip("numpy")
    from huce_qa.retrieval.dense import Embedder  # noqa: PLC0415

    embedder = Embedder(cache_dir=tmp_path)
    embedder._model = model = _CountingModel()
    embedder.encode_queries(["câu mở rộng", "câu gốc"])
    embedder.encode_query("câu gốc")
    assert model.calls == 1
    embedder._cache[embedder._key("khởi động")] = None  # có sẵn trong cache cũ
    embedder.warm_up()
    assert model.calls == 2


def test_sub_queries_split_compound_questions_only():
    from huce_qa.retrieval.pipeline import sub_queries

    q = "Bị cấm thi kỳ 1 thì kỳ 2 có bị cấm nữa không? Với dưới bao nhiêu điểm là nợ môn ạ?"
    assert sub_queries(q) == [
        q,
        "Bị cấm thi kỳ 1 thì kỳ 2 có bị cấm nữa không",
        "Với dưới bao nhiêu điểm là nợ môn ạ",
    ]
    assert sub_queries("Học lại và cải thiện điểm thì sao?") == [
        "Học lại và cải thiện điểm thì sao?"
    ]
