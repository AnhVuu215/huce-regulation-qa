"""Xuất embedding các đoạn của cấu hình chạy thật vào data/embeddings, để máy mới khởi động nhanh.

    uv run --group ml python scripts/export_embeddings.py

Chạy lại sau khi văn bản, cách chia đoạn hoặc mô hình embedding thay đổi.
"""

import sys
from pathlib import Path

from huce_qa.retrieval import build, presets
from huce_qa.retrieval.dense import Embedder

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    docs, parsed = build.load_corpus(ROOT)
    embedder = Embedder(cache_dir=ROOT / ".cache" / "embeddings")
    retriever = build.build_retriever(presets.PRODUCTION, docs, parsed, embedder, None, ROOT)
    texts = [p.text for p in retriever.passages]
    out = ROOT / "data" / "embeddings" / f"{embedder.model_name.replace('/', '__')}.npz"
    embedder.export(texts, out)
    print(f"{len(texts)} đoạn -> {out.relative_to(ROOT)} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
