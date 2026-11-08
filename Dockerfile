FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    HF_HOME=/app/.cache/huggingface \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Lớp thư viện tách riêng: sửa code không phải cài lại PyTorch và sentence-transformers.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --group ml --no-install-project

COPY src ./src
COPY data ./data
RUN uv sync --frozen --no-dev --group ml

RUN useradd --create-home app && mkdir -p .cache .data && chown -R app:app .cache .data
USER app

EXPOSE 8000
# Lần đầu khởi động tải mô hình bge-m3 và tính embedding các đoạn (vài phút); các lần sau dùng cache
# trong volume.
HEALTHCHECK --interval=30s --timeout=5s --start-period=600s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if b'\"ready\":true' in urllib.request.urlopen('http://127.0.0.1:8000/health').read() else 1)"

CMD ["uv", "run", "--no-sync", "uvicorn", "api.app:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
