import json

import pytest

from evaluation.agreement import agreement, cohen_kappa, confusion
from evaluation.judge import VERDICTS, Judge
from generation.llm import FakeLLM


def test_judge_parses_verdict_and_reason():
    llm = FakeLLM(lambda p: json.dumps({"ly_do": "Đúng ngưỡng 2,0.", "ket_luan": "dung"}))
    v = Judge(llm).grade("GPA bao nhiêu thì tốt nghiệp?", "Từ 2,0 trở lên.", "Cần đạt 2,0.")
    assert (v.ket_luan, v.score) == ("dung", 1.0)
    system, prompt = llm.calls[0]
    assert "Đáp án chuẩn: Từ 2,0 trở lên." in prompt
    assert "không bị trừ điểm" in system


def test_judge_rejects_unknown_verdict():
    llm = FakeLLM(lambda p: json.dumps({"ly_do": "x", "ket_luan": "tam_duoc"}))
    with pytest.raises(ValueError):
        Judge(llm).grade("q", "a", "b")


def test_partial_verdict_scores_half():
    llm = FakeLLM(lambda p: json.dumps({"ly_do": "Thiếu ý.", "ket_luan": "dung_mot_phan"}))
    assert Judge(llm).grade("q", "a", "b").score == 0.5


def test_kappa_perfect_agreement_is_one():
    a = ["dung", "sai", "dung_mot_phan", "dung"]
    assert cohen_kappa(a, a) == 1.0


def test_kappa_discounts_agreement_by_chance():
    # Người chấm B luôn chọn "dung": trùng 75% nhưng không hơn đoán bừa.
    a = ["dung", "dung", "dung", "sai"]
    b = ["dung", "dung", "dung", "dung"]
    assert agreement(a, b) == 0.75
    assert cohen_kappa(a, b) == pytest.approx(0.0)


def test_kappa_known_value():
    a = ["dung", "dung", "sai", "sai"]
    b = ["dung", "sai", "sai", "sai"]
    # observed 0.75, expected (2*1 + 2*3)/16 = 0.5 -> kappa 0.5
    assert cohen_kappa(a, b) == pytest.approx(0.5)


def test_confusion_counts():
    table = confusion(["dung", "sai"], ["dung", "dung"], VERDICTS)
    assert table["dung"]["dung"] == 1 and table["sai"]["dung"] == 1
