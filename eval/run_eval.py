"""Chạy bộ test qua các cấu hình truy xuất, in bảng theo loại câu và lưu kết quả.

    uv run --group ml python eval/run_eval.py --config baseline
    uv run --group ml python eval/run_eval.py --ablation     # mọi cấu hình, cộng dồn
"""

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evaluation.metrics import score  # noqa: E402
from evaluation.testset import load_testset, validate  # noqa: E402
from retrieval import build, presets  # noqa: E402
from retrieval.dense import Embedder  # noqa: E402
from retrieval.pipeline import RetrievalConfig, Retriever  # noqa: E402
from retrieval.rerank import Reranker  # noqa: E402

K = 5
CACHE = ROOT / ".cache"

CONFIGS = {c.name: c for c in presets.ABLATION}
EXTRA = {c.name: c for c in presets.EXTRA}


def load_corpus():
    return build.load_corpus(ROOT)


def build_retriever(config: RetrievalConfig, docs, parsed, embedder, reranker) -> Retriever:
    return build.build_retriever(config, docs, parsed, embedder, reranker, ROOT)


def summarize(rows: list[dict]) -> dict[str, dict[str, float]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r["loai"]].append(r)
        groups["TẤT CẢ"].append(r)
    return {
        loai: {
            "n": len(items),
            f"recall@{K}": statistics.mean(r["recall_at_k"] for r in items),
            f"hit@{K}": statistics.mean(r["hit_at_k"] for r in items),
            "mrr": statistics.mean(r["reciprocal_rank"] for r in items),
            f"sai_phien_ban@{K}": statistics.mean(r["wrong_version_at_k"] for r in items),
        }
        for loai, items in groups.items()
    }


def table(header: str, rows: dict[str, dict[str, float]]) -> str:
    cols = ["n", f"recall@{K}", f"hit@{K}", "mrr", f"sai_phien_ban@{K}"]
    lines = [f"| {header} | " + " | ".join(cols) + " |", "|---" * (len(cols) + 1) + "|"]
    for name, m in rows.items():
        cells = [str(m["n"])] + [f"{m[c]:.3f}" for c in cols[1:]]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def run(config: RetrievalConfig, questions, docs, parsed, embedder, reranker) -> dict:
    retriever = build_retriever(config, docs, parsed, embedder, reranker)
    rows, latencies = [], []
    for q in questions:
        if q.nen_tu_choi:
            continue  # câu ngoài phạm vi được chấm ở tầng từ chối (Phase 5)
        t = time.perf_counter()
        ranked = retriever.search(q.question, q.khoa, k=10)
        latencies.append(time.perf_counter() - t)
        s = score(ranked, q.can_cu, q.khoa, k=K)
        rows.append({"id": q.id, "loai": q.loai, "khoa": q.khoa, **asdict(s),
                     "top": [p.passage_id for p in ranked[:K]]})
    latencies.sort()
    return {
        "config": asdict(config),
        "n_passages": len(retriever.passages),
        # Độ trễ có dùng cache embedding/rerank nên chỉ để so tương đối giữa các cấu hình.
        "search_latency_ms": {
            "p50": round(1000 * latencies[len(latencies) // 2], 1),
            "p95": round(1000 * latencies[int(len(latencies) * 0.95)], 1),
        },
        "summary": summarize(rows),
        "questions": rows,
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="baseline", choices=sorted(CONFIGS | EXTRA))
    parser.add_argument("--ablation", action="store_true")
    args = parser.parse_args()

    docs, parsed = load_corpus()
    questions = load_testset(ROOT / "eval" / "testset.jsonl")
    if problems := validate(questions, docs, parsed):
        raise SystemExit("Bộ test không hợp lệ:\n" + "\n".join(problems))
    embedder = Embedder(cache_dir=CACHE / "embeddings")
    reranker = Reranker(cache_dir=CACHE / "rerank")

    configs = list(CONFIGS.values()) if args.ablation else [(CONFIGS | EXTRA)[args.config]]
    stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
    out_dir = ROOT / "eval" / "results"
    out_dir.mkdir(exist_ok=True)
    overall = {}
    for config in configs:
        result = run(config, questions, docs, parsed, embedder, reranker)
        result["time"] = datetime.now().isoformat(timespec="seconds")
        (out_dir / f"{stamp}-{config.name}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        overall[config.name] = result["summary"]["TẤT CẢ"]
        print(f"\n## {config.name} ({result['n_passages']} đoạn, "
              f"p50 {result['search_latency_ms']['p50']} ms)")
        print(table("loại", result["summary"]))

    if args.ablation:
        md = table("cấu hình (cộng dồn)", overall)
        (out_dir / f"{stamp}-ablation.md").write_text(md + "\n", encoding="utf-8")
        print("\n## Ablation\n" + md)


if __name__ == "__main__":
    main()
