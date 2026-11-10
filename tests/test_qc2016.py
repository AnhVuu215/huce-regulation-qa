"""Kiểm tra trên PDF thật: bắt các lỗi mà dữ liệu giả lập không lộ ra."""

from pathlib import Path

import pytest

from huce_qa.ingestion import cli
from huce_qa.ingestion.chunker import chunk_document
from huce_qa.ingestion.cli import parse_registered
from huce_qa.ingestion.registry import load_registry

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def doc():
    registry = load_registry(ROOT / "data" / "registry.yaml")
    return next(d for d in registry.documents if d.doc_id == "qc-dhxd-2016")


@pytest.fixture(scope="module")
def dieus(doc):
    return {d.number: d for d in parse_registered(doc, ROOT)}


def test_all_dieu_and_chuong_are_found(dieus):
    assert sorted(dieus) == list(range(1, 35))
    assert len({d.chuong for d in dieus.values()}) == 6


def test_wrapped_titles(dieus):
    assert dieus[26].title.endswith("ngành đào tạo đặc thù")
    assert dieus[28].title.endswith("chuyển loại hình đào tạo")


def test_cross_reference_stays_inside_khoan(dieus):
    assert "khoản 3 Điều 6 của Quy chế này." in dieus[15].khoan[0].text
    assert [k.number for k in dieus[15].khoan] == [1, 2]


def test_exception_clause_is_kept_with_its_khoan(dieus):
    assert "trừ học kỳ cuối khóa học" in dieus[10].khoan[2].text
    assert dieus[10].khoan[2].diem == ["a", "b", "c"]


def test_page_break_does_not_split_diem(dieus):
    assert dieus[28].khoan[0].diem == ["a", "b", "c", "d"]


def test_signature_is_not_in_last_dieu(dieus):
    assert "Phạm Xuân Anh" not in dieus[34].body
    assert dieus[34].body.endswith("do Hiệu trưởng quyết định.")


def test_formula_and_symbol_patches_are_applied(dieus):
    assert "A = Σ(ai × ni) / Σ(ni)" in dieus[23].body
    assert "(0,3 ÷ 0,5)" in dieus[19].body


def test_page_numbers_do_not_leak(dieus):
    assert all(line.strip() != "9" for line in dieus[20].body.splitlines())
    assert "thời gian dành cho ôn thi" in dieus[20].body


def test_chunks_have_unique_ids_and_repeat_dieu_heading(doc, dieus):
    chunks = chunk_document(doc, list(dieus.values()))
    assert len({c.chunk_id for c in chunks}) == len(chunks)
    assert {c.dieu for c in chunks} == set(range(1, 35))
    assert all(c.text.startswith(f"Điều {c.dieu}. ") for c in chunks)


def test_truncated_parse_is_rejected(doc, monkeypatch):
    real_parse = cli.parse_document
    monkeypatch.setattr(cli, "parse_document", lambda lines: real_parse(lines)[:3])
    with pytest.raises(ValueError, match="cắt cụt"):
        parse_registered(doc, ROOT)
