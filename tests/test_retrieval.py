from pathlib import Path

from ingestion.chunker import chunk_document
from ingestion.cli import parse_registered
from ingestion.registry import load_registry
from retrieval.bm25 import BM25, tokenize
from retrieval.pipeline import expand_query, load_synonyms, rrf

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
    doc = next(d for d in load_registry(ROOT / "data/registry.yaml").documents
               if d.doc_id == "qc-dhxd-2022")
    chunks = chunk_document(doc, parse_registered(doc, ROOT))
    parts = [c for c in chunks if c.dieu == 3 and c.khoan == 2]
    assert len(parts) > 1
    assert all("2. Đào tạo theo tín chỉ:" in c.text for c in parts)
    assert len({c.chunk_id for c in chunks}) == len(chunks)
