"""Trích text từ PDF và phát hiện bản scan hoặc lỗi dấu tiếng Việt."""

import re
import unicodedata
from pathlib import Path

import pymupdf

MIN_CHARS_PER_PAGE = 200
MIN_VIETNAMESE_RATIO = 0.05
FORMULA_PLACEHOLDER = "[CÔNG THỨC]"
MIN_FORMULA_RUN = 5

PAGE_NUMBER = re.compile(r"^\s*\d{1,3}\s*$")
VIETNAMESE_LETTERS = set("ăâđêôơưáàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ")


class ScannedPdfError(ValueError):
    """PDF không có lớp text dùng được, cần OCR."""


def vietnamese_ratio(text: str) -> float:
    letters = [ch for ch in text.lower() if ch.isalpha()]
    if not letters:
        return 0.0
    return sum(ch in VIETNAMESE_LETTERS for ch in letters) / len(letters)


def extract_pages(path: Path) -> list[str]:
    with pymupdf.open(path) as pdf:
        pages = [unicodedata.normalize("NFC", page.get_text()) for page in pdf]
    joined = "".join(pages)
    if len(joined) / max(len(pages), 1) < MIN_CHARS_PER_PAGE:
        raise ScannedPdfError(f"{path.name}: quá ít text, có thể là bản scan")
    if vietnamese_ratio(joined) < MIN_VIETNAMESE_RATIO:
        raise ScannedPdfError(f"{path.name}: tỷ lệ chữ có dấu quá thấp, nghi lỗi font")
    return pages


def _is_formula_fragment(line: str) -> bool:
    stripped = line.strip()
    return len(stripped) <= 1


def _collapse_formulas(lines: list[str]) -> list[str]:
    """Công thức trong PDF rã thành các dòng một ký tự; thay cả cụm bằng placeholder."""
    result: list[str] = []
    i = 0
    while i < len(lines):
        j = i
        while j < len(lines) and _is_formula_fragment(lines[j]):
            j += 1
        fragments = [line for line in lines[i:j] if line.strip()]
        if len(fragments) >= MIN_FORMULA_RUN:
            result.append(FORMULA_PLACEHOLDER)
            i = j
        elif j > i:
            result.extend(lines[i:j])
            i = j
        else:
            result.append(lines[i])
            i += 1
    return result


def clean_lines(pages: list[str]) -> list[str]:
    """Bỏ số trang đầu mỗi trang, gộp công thức vỡ, bỏ dòng trống."""
    lines: list[str] = []
    for page in pages:
        page_lines = page.splitlines()
        first_content = next((i for i, line in enumerate(page_lines) if line.strip()), None)
        if first_content is not None and PAGE_NUMBER.match(page_lines[first_content]):
            del page_lines[first_content]
        lines.extend(page_lines)
    return [line.rstrip() for line in _collapse_formulas(lines) if line.strip()]
