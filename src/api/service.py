"""Dựng pipeline trả lời cho API, đúng cấu hình mà báo cáo đánh giá đo."""

import os
from pathlib import Path

from generation.answer import QA, QAConfig
from generation.llm import CachedLLM, GeminiClient, load_env
from retrieval import build, presets
from retrieval.dense import Embedder
from tools.hoc_vu import HocVu

MODEL = os.environ.get("LLM_MODEL", "gemini-3.5-flash-lite")


def build_qa(root: Path) -> QA:
    load_env(root / ".env")
    cache = root / ".cache"
    docs, parsed = build.load_corpus(root)
    retriever = build.build_retriever(presets.PRODUCTION, docs, parsed,
                                      Embedder(cache_dir=cache / "embeddings"), None, root)
    llm = CachedLLM(GeminiClient([MODEL]), cache / "llm", namespace=MODEL)
    tools = HocVu(root / "data" / "rules" / "hoc-vu.yaml", docs)
    return QA(retriever, llm, docs, QAConfig(), tools=tools)
