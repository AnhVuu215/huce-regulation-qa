from collections import Counter
from pathlib import Path

import pytest

from huce_qa.evaluation.metrics import score, short_answer_correct, unit_matches
from huce_qa.evaluation.testset import CanCu, DapAnNgan, load_testset, validate
from huce_qa.ingestion.cli import parse_registered
from huce_qa.ingestion.registry import load_registry
from huce_qa.retrieval.corpus import Passage, Unit, window_passages

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def corpus():
    docs = {d.doc_id: d for d in load_registry(ROOT / "data" / "registry.yaml").documents}
    return docs, {doc_id: parse_registered(doc, ROOT) for doc_id, doc in docs.items()}


def test_testset_is_valid_against_corpus(corpus):
    questions = load_testset(ROOT / "eval" / "testset.jsonl")
    assert validate(questions, *corpus) == []
    assert len(questions) >= 50


def test_testset_covers_all_six_types():
    counts = Counter(q.loai for q in load_testset(ROOT / "eval" / "testset.jsonl"))
    assert len(counts) == 6
    assert counts["ngoai_pham_vi"] >= 0.08 * sum(counts.values())


def test_validator_rejects_citation_from_wrong_version(corpus):
    q = load_testset(ROOT / "eval" / "testset.jsonl")[0].model_copy(
        update={"khoa": 65}  # câu dùng quy chế 2022, nhưng K65 theo quy chế 2016
    )
    assert any("không áp dụng cho K65" in p for p in validate([q], *corpus))


def _passage(pid, units, khoa_tu=None, khoa_den=None):
    return Passage(pid, units[0].doc_id, "", tuple(units), khoa_tu, khoa_den)


def test_unit_matching_levels():
    gold = CanCu(doc_id="d", dieu=9, khoan=4)
    assert unit_matches(Unit("d", 9, None), gold)  # chunk trọn Điều
    assert unit_matches(Unit("d", 9, 4), gold)
    assert not unit_matches(Unit("d", 9, 0), gold)  # chỉ có tên Điều
    assert not unit_matches(Unit("d", 9, 3), gold)
    assert unit_matches(Unit("d", 9, 0), CanCu(doc_id="d", dieu=9))


def test_score_recall_mrr_and_wrong_version():
    gold = [CanCu(doc_id="d", dieu=1, khoan=1), CanCu(doc_id="d", dieu=2)]
    ranked = [
        _passage("a", [Unit("old", 1, None)], khoa_den=66),
        _passage("b", [Unit("d", 2, 3)], khoa_tu=67),
    ]
    s = score(ranked, gold, khoa=68, k=5)
    assert s.recall_at_k == 0.5
    assert s.reciprocal_rank == 0.5
    assert s.hit_at_k == 1.0
    assert s.wrong_version_at_k == 0.5


def test_window_passages_label_every_word(corpus):
    docs, parsed = corpus
    doc = docs["qc-dhxd-2022"]
    windows = window_passages(doc, parsed[doc.doc_id], size=200, overlap=50)
    total_words = sum(len(d.heading.split()) + len(d.body.split()) for d in parsed[doc.doc_id])
    assert sum(len(w.text.split()) for w in windows) >= total_words
    assert any(len({u.dieu for u in w.units}) > 1 for w in windows)  # cửa sổ vắt qua Điều


def test_short_answer_check_handles_negation():
    spec = DapAnNgan(phai_co=[["bị cảnh báo"]], khong_duoc_co=["không bị cảnh báo"])
    assert short_answer_correct("Có, bạn bị cảnh báo học tập.", spec)
    assert not short_answer_correct("Bạn không bị cảnh báo.", spec)


def test_reference_answers_pass_their_own_short_checks():
    for q in load_testset(ROOT / "eval" / "testset.jsonl"):
        if q.dap_an_ngan:
            assert short_answer_correct(q.answer, q.dap_an_ngan), q.id


def test_holdout_set_is_valid_and_disjoint_from_development_set(corpus):
    holdout = load_testset(ROOT / "eval" / "testset_holdout.jsonl")
    dev = load_testset(ROOT / "eval" / "testset.jsonl")
    assert validate(holdout, *corpus) == []
    assert not {q.question for q in holdout} & {q.question for q in dev}
    assert not {q.id for q in holdout} & {q.id for q in dev}
