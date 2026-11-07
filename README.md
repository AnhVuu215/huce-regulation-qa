# Hỏi đáp quy chế đào tạo HUCE (RAG)

Hệ thống hỏi đáp quy chế đào tạo của Trường Đại học Xây dựng Hà Nội, mỗi câu trả lời kèm
trích dẫn Điều/Khoản. Đang phát triển, xem tiến độ tại [docs/ROADMAP.md](docs/ROADMAP.md).

## Chạy thử

Cần Python 3.11 và [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest
uv run python -m ingestion.cli    # PDF trong registry -> data/processed/*.json
docker compose up -d db           # Postgres + pgvector, cổng 5433
```

Trên máy có `make`: `make setup`, `make test`, `make ingest`.

## Thêm văn bản mới

1. Đặt PDF vào `data/raw/`.
2. Khai báo trong `data/registry.yaml` (sha256, hiệu lực, khóa áp dụng).
3. Nếu PDF là bản scan: chạy `scripts/ocr_pdf.py`, soát tay vào `data/text/`, khai báo `text_file`.
4. Chạy lại lệnh nạp. Không cần sửa code.
