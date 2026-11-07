"""Quy chế 1053/QĐ-ĐHXDHN (K67 trở đi): PDF scan, dùng bản text đã soát tay."""

import re
import unicodedata
from collections import Counter
from pathlib import Path

import pytest

from ingestion.cli import parse_registered
from ingestion.registry import load_registry

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def registry():
    return load_registry(ROOT / "data" / "registry.yaml")


@pytest.fixture(scope="module")
def dieus(registry):
    doc = next(d for d in registry.documents if d.doc_id == "qc-dhxd-2022")
    return {d.number: d for d in parse_registered(doc, ROOT)}


def _words(text: str) -> list[str]:
    """So sánh bỏ dấu: lỗi OCR chủ yếu nằm ở dấu, còn chữ cái thì giữ được."""
    stripped = "".join(
        c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn"
    )
    return re.findall(r"[a-zđ]{2,}", stripped.replace("đ", "d"))


def test_structure(dieus):
    assert sorted(dieus) == list(range(1, 22))
    assert len({d.chuong for d in dieus.values()}) == 5
    assert dieus[15].title.startswith("Chuyển ngành, chuyển nơi học")


def test_transcription_only_fixes_ocr_errors():
    """Gần như mọi từ trong bản soát phải có mặt trong OCR thô: bản soát không thêm nội dung."""
    reviewed = Counter(_words((ROOT / "data/text/qc-dhxd-2022.txt").read_text(encoding="utf-8")))
    raw = Counter(_words((ROOT / "data/ocr/qc-dhxd-2022.raw.txt").read_text(encoding="utf-8")))
    missing = sum((reviewed - raw).values())
    assert missing / sum(reviewed.values()) < 0.01


@pytest.mark.parametrize(
    ("dieu", "khoan", "phrase"),
    [
        (9, 4, "B+: từ 8,0 đến 8,4;"),
        (9, 4, "P: từ 5,0 trở lên."),
        (9, 9, "không vượt quá mức điểm C+."),
        (10, 5, "b) Trình độ năm thứ hai: M ≤ N < 2M;"),
        (11, 1, "dưới 1,8 đối với sinh viên các năm tiếp theo."),
        (11, 1, "vượt quá 24;"),
        (11, 2, "vượt quá 3 lần liên tiếp; hoặc quá 4 lần không liên tiếp;"),
        (11, 2, "khoản 5 Điều 2"),
        (13, 1, "đạt từ (2.0) trở lên;"),
    ],
)
def test_values_checked_against_scan(dieus, dieu, khoan, phrase):
    assert phrase in dieus[dieu].khoan[khoan - 1].text


def test_versions_cover_disjoint_cohorts(registry):
    docs = {d.doc_id: d for d in registry.documents}
    assert docs["qc-dhxd-2016"].ap_dung_cho(66) and not docs["qc-dhxd-2016"].ap_dung_cho(67)
    assert docs["qc-dhxd-2022"].ap_dung_cho(67) and not docs["qc-dhxd-2022"].ap_dung_cho(66)
