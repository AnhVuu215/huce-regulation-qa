"""Dựng pipeline trả lời cho API, đúng cấu hình mà báo cáo đánh giá đo."""

import logging
import os
from pathlib import Path

from generation.answer import QA, QAConfig
from generation.llm import CachedLLM, GeminiClient, load_env
from retrieval import build, presets
from retrieval.dense import Embedder
from tools.hoc_vu import HocVu

MODEL = os.environ.get("LLM_MODEL", "gemini-3.5-flash-lite")
log = logging.getLogger("huce_qa")


def build_qa(root: Path) -> QA:
    load_env(root / ".env")
    cache = root / ".cache"
    docs, parsed = build.load_corpus(root)
    # Embedding các đoạn có sẵn trong data/embeddings (repo); chỉ đoạn mới phải tính bằng mô hình.
    embedder = Embedder(cache_dir=cache / "embeddings", seed_dir=root / "data" / "embeddings")
    retriever = build.build_retriever(presets.PRODUCTION, docs, parsed, embedder, None, root)
    if embedder.computed:
        log.warning("Đã tính mới %d đoạn không có trong data/embeddings; chạy "
                    "scripts/export_embeddings.py để cập nhật.", embedder.computed)
    # Mô hình vẫn cần để mã hóa câu hỏi; nạp sẵn lúc khởi động (khoảng 20 giây) để người hỏi đầu
    # tiên không phải chờ.
    embedder.encode(["khởi động"])
    llm = CachedLLM(GeminiClient([MODEL]), cache / "llm", namespace=MODEL)
    tools = HocVu(root / "data" / "rules" / "hoc-vu.yaml", docs)
    return QA(retriever, llm, docs, QAConfig(), tools=tools)
