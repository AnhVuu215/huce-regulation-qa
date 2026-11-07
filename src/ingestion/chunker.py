"""Chunk theo cấu trúc: một Điều một chunk, Điều dài tách theo Khoản."""

from datetime import date

from pydantic import BaseModel

from ingestion.parser import DIEM, Dieu, Khoan, _join
from ingestion.registry import Document

# Đếm theo từ để không phụ thuộc tokenizer; 300 từ tiếng Việt nằm dưới giới hạn
# 512 token thường gặp của reranker.
MAX_WORDS = 300


class Chunk(BaseModel):
    chunk_id: str
    doc_id: str
    doc_title: str
    so_hieu: str
    hieu_luc_tu: date
    khoa_tu: int | None
    khoa_den: int | None
    chuong: str | None
    dieu: int
    dieu_title: str
    khoan: int | None
    text: str
    sua_doi_boi: str | None = None


def _chunk(doc: Document, dieu: Dieu, khoan: int | None, text: str) -> Chunk:
    suffix = f"-k{khoan}" if khoan is not None else ""
    return Chunk(
        chunk_id=f"{doc.chunk_prefix}-d{dieu.number}{suffix}",
        doc_id=doc.doc_id,
        doc_title=doc.doc_title,
        so_hieu=doc.so_hieu,
        hieu_luc_tu=doc.hieu_luc_tu,
        khoa_tu=doc.khoa_tu,
        khoa_den=doc.khoa_den,
        chuong=dieu.chuong,
        dieu=dieu.number,
        dieu_title=dieu.title,
        khoan=khoan,
        text=text,
    )


def chunk_dieu(doc: Document, dieu: Dieu, max_words: int = MAX_WORDS) -> list[Chunk]:
    whole = f"{dieu.heading}\n{dieu.body}"
    if len(whole.split()) <= max_words or len(dieu.khoan) < 2:
        return [_chunk(doc, dieu, None, whole)]

    header = dieu.heading
    if dieu.preamble_lines:
        header += "\n" + dieu.preamble
    chunks = []
    for k in dieu.khoan:
        parts = _split_khoan(k, max_words)
        for n, part in enumerate(parts, start=1):
            chunk = _chunk(doc, dieu, k.number, f"{header}\n{part}")
            if len(parts) > 1:
                chunk.chunk_id += f"-p{n}"
            chunks.append(chunk)
    return chunks


def _split_khoan(khoan: Khoan, max_words: int) -> list[str]:
    """Khoản quá dài thì tách theo ranh giới Điểm, lặp lại phần dẫn của Khoản ở mỗi phần.
    Không bao giờ cắt giữa một Điểm; Khoản không có Điểm thì giữ nguyên."""
    if len(khoan.text.split()) <= max_words or len(khoan.diem) < 2:
        return [khoan.text]
    intro: list[str] = []
    groups: list[list[str]] = []
    expected = iter(khoan.diem)
    nxt = next(expected, None)
    for line in khoan.lines:
        match = DIEM.match(line)
        if match and match.group(1) == nxt:
            groups.append([line])
            nxt = next(expected, None)
        elif groups:
            groups[-1].append(line)
        else:
            intro.append(line)
    intro_text = _join(intro)
    parts: list[list[str]] = [[]]
    for group in groups:
        candidate = parts[-1] + group
        if parts[-1] and len(_join(intro + candidate).split()) > max_words:
            parts.append(group)
        else:
            parts[-1] = candidate
    return [intro_text + "\n" + _join(p) if intro_text else _join(p) for p in parts]


def chunk_document(doc: Document, dieus: list[Dieu], max_words: int = MAX_WORDS) -> list[Chunk]:
    return [chunk for dieu in dieus for chunk in chunk_dieu(doc, dieu, max_words)]
