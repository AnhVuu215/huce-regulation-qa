"""Logic trả lời với LLM giả lập: không cần mạng, không cần mô hình embedding."""

import json

import pytest

from generation.answer import QA, QAConfig
from generation.llm import CachedLLM, FakeLLM
from ingestion.registry import Document
from retrieval.corpus import Passage, Unit

DOCS = {
    "new": Document(doc_id="new", chunk_prefix="n", doc_title="Quy chế mới", so_hieu="1",
                    file="x", sha256="x", hieu_luc_tu="2022-09-23", khoa_tu=67),
    "old": Document(doc_id="old", chunk_prefix="o", doc_title="Quy chế cũ", so_hieu="2",
                    file="x", sha256="x", hieu_luc_tu="2016-01-07", khoa_den=66),
}
P_NEW = Passage("n-d11-k2", "new", "Điều 11. Buộc thôi học ...", (Unit("new", 11, 2),), 67, None)
P_OLD = Passage("o-d16-k2", "old", "Điều 16. Buộc thôi học ...", (Unit("old", 16, 2),), None, 66)


class StubRetriever:
    def __init__(self, passages, similarity=0.7):
        self.passages, self.similarity = passages, similarity

    def search(self, question, khoa=None, k=10):
        return [p for p in self.passages if khoa is None or p.ap_dung_cho(khoa)][:k]

    def max_similarity(self, question, khoa=None):
        return self.similarity


def reply(tra_loi, trich_dan, tu_choi=False):
    return lambda prompt: json.dumps(
        {"tu_choi": tu_choi, "tra_loi": tra_loi, "trich_dan": trich_dan}, ensure_ascii=False
    )


def make_qa(llm, passages=(P_NEW, P_OLD), similarity=0.7):
    return QA(StubRetriever(list(passages), similarity), llm, DOCS, QAConfig())


def test_valid_citation_is_kept_and_mapped_to_unit():
    a = make_qa(FakeLLM(reply("Theo Điều 11, quá 3 lần liên tiếp.", [1]))).answer("?", 68)
    assert a.status == "tra_loi"
    assert a.citations == [Unit("new", 11, 2)]
    assert not a.uncertain


def test_out_of_range_citation_is_dropped():
    a = make_qa(FakeLLM(reply("Theo Điều 11.", [1, 7]))).answer("?", 68)
    assert a.dropped_citations == [7]
    assert a.cited_passages == ["n-d11-k2"]


def test_mention_of_article_not_retrieved_is_flagged():
    a = make_qa(FakeLLM(reply("Theo Điều 25, bị buộc thôi học.", [1]))).answer("?", 68)
    assert a.unverified_mentions == [25]
    assert a.uncertain


def test_answer_without_citation_is_uncertain():
    a = make_qa(FakeLLM(reply("Có.", []))).answer("?", 68)
    assert a.uncertain


def test_prompt_only_contains_passages_for_student_cohort():
    llm = FakeLLM(reply("x", [1]))
    make_qa(llm).answer("?", 68)
    prompt = llm.calls[0][1]
    assert "Quy chế mới" in prompt and "Quy chế cũ" not in prompt
    assert "K68" in prompt


def test_asks_for_cohort_when_versions_differ():
    llm = FakeLLM(reply("x", [1]))
    a = make_qa(llm).answer("Bị cảnh báo mấy lần thì bị buộc thôi học?", None)
    assert a.status == "hoi_lai_khoa"
    assert llm.calls == []


def test_low_relevance_refuses_without_calling_llm():
    llm = FakeLLM(reply("x", [1]))
    a = make_qa(llm, similarity=0.2).answer("Ký túc xá còn chỗ không?", 68)
    assert a.status == "tu_choi"
    assert llm.calls == []


def test_llm_refusal_is_respected():
    a = make_qa(FakeLLM(reply("Quy chế không quy định.", [], tu_choi=True))).answer("?", 68)
    assert a.status == "tu_choi"
    assert not a.uncertain


def test_malformed_output_is_flagged():
    a = make_qa(FakeLLM(lambda p: "không phải JSON")).answer("?", 68)
    assert a.uncertain and a.warnings


def test_cache_avoids_second_call(tmp_path):
    inner = FakeLLM(lambda p: "ok")
    llm = CachedLLM(inner, tmp_path, "fake")
    first, second = llm.generate("s", "p"), llm.generate("s", "p")
    assert len(inner.calls) == 1
    assert second.cached and not first.cached


FENCED = '```json\n{"tu_choi": false, "tra_loi": "a", "trich_dan": [1]}\n```'


@pytest.mark.parametrize("fenced", [FENCED])
def test_code_fenced_json_is_parsed(fenced):
    a = make_qa(FakeLLM(lambda p: fenced)).answer("?", 68)
    assert a.cited_passages == ["n-d11-k2"]


def test_cache_skips_answers_from_fallback_model(tmp_path):
    llm = CachedLLM(FakeLLM(lambda p: "ok"), tmp_path, "gemini-main")
    llm.generate("s", "p")
    assert list((tmp_path / "gemini-main").iterdir()) == []
