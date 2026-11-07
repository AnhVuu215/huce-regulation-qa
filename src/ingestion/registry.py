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
    return registry


def verify_file(doc: Document, root: Path) -> Path:
    path = root / doc.file
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != doc.sha256:
        raise ValueError(f"{doc.doc_id}: sha256 không khớp ({digest})")
    return path
