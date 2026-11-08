"""Hợp đồng dữ liệu của API."""

from datetime import date

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    khoa: int | None = Field(default=None, ge=40, le=99,
                             description="Khóa của sinh viên, ví dụ 68 cho K68")


class Citation(BaseModel):
    doc_id: str
    doc_title: str
    so_hieu: str
    dieu: int
    khoan: int | None
    label: str


class AskResponse(BaseModel):
    request_id: str
    status: str = Field(description="tra_loi | tu_choi | hoi_lai_khoa")
    answer: str
    citations: list[Citation]
    warnings: list[str]
    uncertain: bool
    latency_ms: int


class FeedbackRequest(BaseModel):
    request_id: str
    helpful: bool
    comment: str | None = Field(default=None, max_length=1000)


class DocumentInfo(BaseModel):
    doc_id: str
    doc_title: str
    so_hieu: str
    hieu_luc_tu: date
    khoa_tu: int | None
    khoa_den: int | None
    sua_doi: list[str] = Field(default_factory=list,
                               description="Các văn bản khác mà văn bản này sửa đổi")
