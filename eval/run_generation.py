"""Đánh giá tầng trả lời: trích dẫn đúng, từ chối đúng/nhầm, độ trễ, token.

    uv run --group ml python eval/run_generation.py                  # gemini-3.5-flash-lite
    uv run --group ml python eval/run_generation.py --model gemini-3.6-flash --no-fallback
    uv run --group ml python eval/run_generation.py --limit 10       # eval rút gọn khi phát triển

Câu trả lời LLM được cache trong .cache/llm: chạy lại không gọi mạng.
Gói miễn phí: gemini-3.6-flash chỉ 20 lượt/ngày nên không dùng làm mặc định.
"""

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "eval")]

from run_eval import CACHE, EXTRA, build_retriever, load_corpus  # noqa: E402

from evaluation.judge import SCORE, Judge  # noqa: E402
from evaluation.metrics import short_answer_correct, unit_matches  # noqa: E402
from evaluation.testset import load_testset  # noqa: E402
from generation.answer import QA, QAConfig  # noqa: E402
from generation.llm import CachedLLM, GeminiClient, load_env  # noqa: E402
from retrieval.dense import Embedder  # noqa: E402
from tools.hoc_vu import HocVu  # noqa: E402

RETRIEVAL = "khong_rerank+loc_khoa"
DEFAULT_MODEL = "gemini-3.5-flash-lite"
FALLBACK = "gemini-3.5-flash-lite"
# Cùng họ mô hình với bên trả lời nên có rủi ro thiên vị; độ lệch được đo bằng chấm tay 20%.
JUDGE_MODEL = "gemini-3.5-flash-lite"


def judge_row(judge: Judge, q, a) -> tuple[str, str]:
    """Câu ngoài phạm vi: đúng khi từ chối. Câu có căn cứ mà bị từ chối hay hỏi lại: sai.
    Còn lại đưa giám khảo LLM chấm theo đáp án chuẩn."""
    if q.nen_tu_choi:
        if a.status == "tu_choi":
            return "dung", "Từ chối đúng."
        return "sai", "Lẽ ra phải từ chối."
    if a.status != "tra_loi":
        return "sai", "Không trả lời câu hỏi có căn cứ."
    verdict = judge.grade(q.question, q.answer, a.text)
    return verdict.ket_luan, verdict.ly_do


def score_citations(answer, gold) -> dict:
    cited = answer.citations
    relevant = [u for u in cited if any(unit_matches(u, g) for g in gold)]
    covered = [g for g in gold if any(unit_matches(u, g) for u in cited)]
    precision = len(relevant) / len(cited) if cited else 0.0
    recall = len(covered) / len(gold) if gold else 0.0
    return {
        "citation_precision": precision,
        "citation_recall": recall,
        # "Trích dẫn đúng": có trích dẫn, mọi trích dẫn đều đúng căn cứ, và chạm ít nhất một căn cứ.
        "citation_correct": float(bool(cited) and precision == 1.0 and recall > 0),
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--no-fallback", action="store_true",
                        help="đo riêng một mô hình, không chuyển sang dự phòng")
    parser.add_argument("--tools", action="store_true",
                        help="cho LLM gọi công cụ tính toán học vụ")
    parser.add_argument("--only", default="", help="chỉ chạy các loại câu, ví dụ tinh_toan")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--judge", action="store_true",
                        help="chấm độ đúng nội dung bằng giám khảo LLM")
    args = parser.parse_args()

    load_env(ROOT / ".env")
    use_fallback = not args.no_fallback and args.model != FALLBACK
    models = [args.model] + ([FALLBACK] if use_fallback else [])
    llm = CachedLLM(GeminiClient(models), CACHE / "llm", namespace=args.model)
    docs, parsed = load_corpus()
    retriever = build_retriever(EXTRA[RETRIEVAL], docs, parsed,
                                Embedder(cache_dir=CACHE / "embeddings"), None)
    tools = HocVu(ROOT / "data" / "rules" / "hoc-vu.yaml", docs) if args.tools else None
    qa = QA(retriever, llm, docs, QAConfig(), tools=tools)
    # Giám khảo không dùng mô hình dự phòng: mọi câu phải được chấm bởi cùng một mô hình.
    judge = (Judge(CachedLLM(GeminiClient([JUDGE_MODEL]), CACHE / "judge", JUDGE_MODEL))
             if args.judge else None)
    questions = load_testset(ROOT / "eval" / "testset.jsonl")
    if args.only:
        questions = [q for q in questions if q.loai in args.only.split(",")]
    if args.limit:
        questions = questions[: args.limit] + [q for q in questions if q.nen_tu_choi][:2]

    rows = []
    for i, q in enumerate(questions, 1):
        a = qa.answer(q.question, q.khoa)
        row = {
            "id": q.id, "loai": q.loai, "nen_tu_choi": q.nen_tu_choi, "status": a.status,
            "refused": a.status == "tu_choi", "uncertain": a.uncertain,
            "relevance": round(a.relevance, 3), "answer": a.text,
            "cited": a.cited_passages, "warnings": a.warnings,
            "citations": [f"{u.doc_id} Điều {u.dieu}" + (f" Khoản {u.khoan}" if u.khoan else "")
                          for u in a.citations],
            "model": a.llm.model if a.llm else None,
            "latency_s": round(a.llm.latency_s, 2) if a.llm else 0.0,
            "cached": a.llm.cached if a.llm else None,
            "llm_errors": a.llm.errors if a.llm else [],
            "tool_calls": [c["name"] for c in a.llm.tool_calls] if a.llm else [],
            "tokens": (a.llm.input_tokens + a.llm.output_tokens + a.llm.thinking_tokens)
            if a.llm else 0,
        }
        if not q.nen_tu_choi:
            row.update(score_citations(a, q.can_cu))
        if q.dap_an_ngan:
            row["short_answer_correct"] = float(short_answer_correct(a.text, q.dap_an_ngan))
        if judge:
            row["judge"], row["judge_reason"] = judge_row(judge, q, a)
            row["judge_score"] = SCORE[row["judge"]]
        rows.append(row)
        print(f"[{i}/{len(questions)}] {q.id} {a.status}"
              f"{' (cache)' if a.llm and a.llm.cached else ''}", flush=True)

    answerable = [r for r in rows if not r["nen_tu_choi"]]
    out_scope = [r for r in rows if r["nen_tu_choi"]]
    by_type = defaultdict(list)
    for r in answerable:
        by_type[r["loai"]].append(r)
    fresh = sorted(r["latency_s"] for r in rows if r["cached"] is False)

    def mean(items, key):
        return round(statistics.mean(r[key] for r in items), 3) if items else None

    summary = {
        "model": args.model, "retrieval": RETRIEVAL, "tools": args.tools, "n": len(rows),
        "tinh_toan_dung": mean([r for r in rows if "short_answer_correct" in r],
                               "short_answer_correct"),
        "cau_goi_cong_cu": sum(bool(r["tool_calls"]) for r in rows),
        "trich_dan_dung": mean(answerable, "citation_correct"),
        "citation_precision": mean(answerable, "citation_precision"),
        "citation_recall": mean(answerable, "citation_recall"),
        "tu_choi_dung": f"{sum(r['refused'] for r in out_scope)}/{len(out_scope)}",
        "tu_choi_nham": f"{sum(r['refused'] for r in answerable)}/{len(answerable)}",
        "khong_chac_chan": f"{sum(r['uncertain'] for r in answerable)}/{len(answerable)}",
        "fallback_used": sum(1 for r in rows if r["model"] not in (None, args.model)),
        "latency_s_p50": fresh[len(fresh) // 2] if fresh else None,
        "latency_s_p95": fresh[int(len(fresh) * 0.95)] if fresh else None,
        "tokens_per_question": mean([r for r in rows if r["tokens"]], "tokens"),
        "by_type": {k: {"n": len(v), "trich_dan_dung": mean(v, "citation_correct"),
                        "tu_choi_nham": sum(r["refused"] for r in v)} for k, v in by_type.items()},
    }
    if judge:
        summary["do_dung_noi_dung"] = mean(answerable, "judge_score")
        summary["phan_bo_cham"] = dict(Counter(r["judge"] for r in answerable))
        for k, v in by_type.items():
            summary["by_type"][k]["do_dung_noi_dung"] = mean(v, "judge_score")
    suffix = "-tools" if args.tools else ""
    stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
    out = ROOT / "eval" / "results" / f"{stamp}-generation-{args.model}{suffix}.json"
    payload = {"summary": summary, "questions": rows, "qa_config": asdict(QAConfig())}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("->", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
