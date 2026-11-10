"""Bộ test: mỗi câu có khóa của người hỏi, đáp án chuẩn và căn cứ Điều/Khoản."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from huce_qa.ingestion.parser import Dieu
from huce_qa.ingestion.registry import Document

Loai = Literal["tra_cuu", "dien_dat_sv", "ket_hop", "tinh_toan", "phien_ban", "ngoai_pham_vi"]


class CanCu(BaseModel):
    doc_id: str
    dieu: int
    khoan: int | None = None


class DapAnNgan(BaseModel):
    """Kiểm tra câu trả lời bằng code: mỗi nhóm trong phai_co phải có ít nhất một cụm xuất hiện,
    và không cụm nào trong khong_duoc_co được xuất hiện (không phân biệt hoa thường)."""

    phai_co: list[list[str]]
    khong_duoc_co: list[str] = []


class Question(BaseModel):
    id: str
    loai: Loai
    khoa: int | None
    question: str
    answer: str | None
    can_cu: list[CanCu]
    nen_tu_choi: bool
    nguon: Literal["tu_viet", "thuc_te"]
    dap_an_ngan: DapAnNgan | None = None
    # Giả định khi dựng câu (ví dụ bài gốc không nêu khóa); không chứa thông tin người hỏi.
    ghi_chu: str | None = None


def load_testset(path: Path) -> list[Question]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [Question.model_validate_json(line) for line in lines if line.strip()]


def validate(
    questions: list[Question], docs: dict[str, Document], parsed: dict[str, list[Dieu]]
) -> list[str]:
    """Kiểm tra bộ test với kho văn bản; trả về danh sách lỗi, rỗng là hợp lệ."""
    problems: list[str] = []
    ids = [q.id for q in questions]
    if len(ids) != len(set(ids)):
        problems.append("id bị trùng")
    for q in questions:
        if q.nen_tu_choi != (not q.can_cu):
            problems.append(f"{q.id}: câu nên từ chối thì không có căn cứ và ngược lại")
        if not q.nen_tu_choi and not q.answer:
            problems.append(f"{q.id}: thiếu đáp án chuẩn")
        for cc in q.can_cu:
            doc = docs.get(cc.doc_id)
            if doc is None:
                problems.append(f"{q.id}: văn bản {cc.doc_id} không có trong registry")
                continue
            dieus = {d.number: d for d in parsed[cc.doc_id]}
            dieu = dieus.get(cc.dieu)
            if dieu is None:
                problems.append(f"{q.id}: {cc.doc_id} không có Điều {cc.dieu}")
            elif cc.khoan is not None and cc.khoan not in {k.number for k in dieu.khoan}:
                problems.append(f"{q.id}: Điều {cc.dieu} của {cc.doc_id} không có Khoản {cc.khoan}")
            # Căn cứ phải thuộc phiên bản áp dụng cho khóa của người hỏi.
            if q.khoa is not None and not doc.ap_dung_cho(q.khoa):
                problems.append(f"{q.id}: {cc.doc_id} không áp dụng cho K{q.khoa}")
    return problems


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
