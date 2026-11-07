"""Quy định đồ án, thực tập, đánh giá theo chuẩn đầu ra (2026): bỏ Quyết định ban hành
và Phụ lục biểu mẫu, chỉ giữ phần Quy định."""

from pathlib import Path

import pytest

from ingestion.cli import parse_registered
from ingestion.registry import load_registry

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "qd-do-an-tn-2026": (30, "Tổ chức thực hiện và hiệu lực thi hành"),
    "qd-thuc-tap-tn-2026": (27, "Hiệu lực thi hành"),
    "qd-danh-gia-cdr-2026": (55, "Điều khoản thi hành"),
}


@pytest.fixture(scope="module")
def parsed():
    docs = {d.doc_id: d for d in load_registry(ROOT / "data" / "registry.yaml").documents}
    return {doc_id: parse_registered(docs[doc_id], ROOT) for doc_id in EXPECTED}


@pytest.mark.parametrize("doc_id", EXPECTED)
def test_body_starts_after_decision_and_stops_before_appendix(parsed, doc_id):
    count, last_title = EXPECTED[doc_id]
    dieus = parsed[doc_id]
    assert [d.number for d in dieus] == list(range(1, count + 1))
    assert dieus[0].title.startswith("Phạm vi điều chỉnh")
    assert dieus[-1].title == last_title
    body = "\n".join(d.body for d in dieus)
    assert "Ban hành kèm theo Quyết định này" not in body
    assert "Mẫu ĐATN-01" not in body and "Mẫu TTTN-01" not in body
