"""Danh mục văn bản: thêm phiên bản mới chỉ cần sửa registry.yaml, không sửa code."""

import hashlib
from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator


class Patch(BaseModel):
    """Sửa tay một đoạn text mà PDF không trích đúng được."""

    find: str
    replace: str


class ViTri(BaseModel):
    dieu: int
    khoan: int | None = None


class SuaDoi(BaseModel):
    """Văn bản này sửa đổi một Điều/Khoản của văn bản khác. Khai báo ở văn bản sửa đổi;
    `can_cu` là các Điều/Khoản của chính văn bản này thay thế nội dung bị sửa."""

    doc_id: str
    dieu: int
    khoan: int | None = None
    noi_dung: str
    can_cu: list[ViTri]
    ghi_chu: str | None = None


class Document(BaseModel):
    doc_id: str
    chunk_prefix: str
    doc_title: str
    so_hieu: str
    file: str
    sha256: str
    source_url: str | None = None
    hieu_luc_tu: date
    hieu_luc_ghi_chu: str | None = None
    # Khoảng khóa áp dụng, hai đầu đều tính; None là không giới hạn phía đó.
    # khoa_chua_ro: văn bản không nói rõ khóa, câu trả lời phải cảnh báo.
    khoa_tu: int | None = None
    khoa_den: int | None = None
    khoa_chua_ro: bool = False
    khoa_nguon: str | None = None
    # Bản text đã soát tay, dùng khi PDF là bản scan. PDF gốc vẫn được kiểm sha256.
    text_file: str | None = None
    # Dòng mở đầu phần nội dung chính, để bỏ qua Quyết định ban hành (có Điều 1-3 riêng).
    body_start: str | None = None
    patches: list[Patch] = Field(default_factory=list)
    # Văn bản mới sửa quy tắc của văn bản cũ cho mọi khóa (khác với phiên bản theo khóa).
    sua_doi: list[SuaDoi] = Field(default_factory=list)

    def ap_dung_cho(self, khoa: int) -> bool:
        return (self.khoa_tu is None or khoa >= self.khoa_tu) and (
            self.khoa_den is None or khoa <= self.khoa_den
        )

    @model_validator(mode="after")
    def _check_khoa(self) -> "Document":
        if self.khoa_tu is not None and self.khoa_den is not None and self.khoa_tu > self.khoa_den:
            raise ValueError(f"{self.doc_id}: khoa_tu lớn hơn khoa_den")
        return self


class Registry(BaseModel):
    documents: list[Document]


def load_registry(path: Path) -> Registry:
    registry = Registry.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    ids = [doc.doc_id for doc in registry.documents]
    if len(ids) != len(set(ids)):
        raise ValueError("doc_id bị trùng trong registry")
    for doc in registry.documents:
        for sd in doc.sua_doi:
            if sd.doc_id not in ids or sd.doc_id == doc.doc_id:
                raise ValueError(f"{doc.doc_id}: sửa đổi trỏ tới văn bản không hợp lệ {sd.doc_id}")
    return registry


def amendments_to(docs: list[Document], target_doc_id: str) -> list[tuple[str, SuaDoi]]:
    """Các sửa đổi nhắm vào văn bản `target_doc_id`, kèm doc_id của văn bản sửa đổi."""
    return [(d.doc_id, sd) for d in docs for sd in d.sua_doi if sd.doc_id == target_doc_id]


def verify_file(doc: Document, root: Path) -> Path:
    path = root / doc.file
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != doc.sha256:
        raise ValueError(f"{doc.doc_id}: sha256 không khớp ({digest})")
    return path
