"""Tạo bảng chấm tay mù cho 20% câu có căn cứ, lấy mẫu phân tầng theo loại câu.

    uv run python eval/make_grading_sheet.py eval/results/<lần chạy có --judge>.json

Bảng không có kết luận của giám khảo LLM để người chấm không bị ảnh hưởng. Người chấm điền cột
`nguoi_cham` bằng dung / dung_mot_phan / sai, rồi chạy eval/judge_agreement.py.
"""

import argparse
import csv
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evaluation.testset import load_testset  # noqa: E402

FRACTION = 0.2
SEED = 2026
COLUMNS = ["id", "loai", "khoa", "cau_hoi", "dap_an_chuan", "cau_tra_loi_he_thong",
           "trich_dan", "nguoi_cham", "ghi_chu"]


def stratified_sample(rows: list[dict], fraction: float, seed: int) -> list[dict]:
    """Mỗi loại câu lấy ít nhất 1 câu, tổng khoảng `fraction` số câu, cố định theo seed."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r["loai"]].append(r)
    rng = random.Random(seed)
    picked = []
    for loai in sorted(groups):
        items = sorted(groups[loai], key=lambda r: r["id"])
        k = max(1, math.floor(len(items) * fraction + 0.5))
        picked += rng.sample(items, k)
    return sorted(picked, key=lambda r: r["id"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path, nargs="+", help="một hoặc nhiều lần chạy có --judge")
    parser.add_argument("--out", type=Path, default=ROOT / "eval" / "human" / "cham-tay.csv")
    parser.add_argument("--fraction", type=float, default=FRACTION)
    parser.add_argument("--source", choices=["tu_viet", "thuc_te"],
                        help="chỉ lấy câu của một nguồn")
    parser.add_argument("--answered-only", action="store_true",
                        help="chỉ lấy câu hệ thống đã trả lời: câu bị từ chối do code chấm, "
                             "không qua giám khảo")
    args = parser.parse_args()

    questions = {}
    for name in ("testset.jsonl", "testset_holdout.jsonl"):
        if (ROOT / "eval" / name).exists():
            questions.update({q.id: q for q in load_testset(ROOT / "eval" / name)})
    candidates = []
    for path in args.results:
        run = json.loads(path.read_text(encoding="utf-8"))
        candidates += [
            r for r in run["questions"]
            if not r["nen_tu_choi"]
            and (args.source is None or r.get("nguon") == args.source)
            and (not args.answered_only or r["status"] == "tra_loi")
        ]
    sample = stratified_sample(candidates, args.fraction, SEED)
    answered = candidates

    args.out.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig để Excel hiển thị đúng tiếng Việt.
    with args.out.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for r in sample:
            q = questions[r["id"]]
            writer.writerow({
                "id": r["id"], "loai": r["loai"], "khoa": q.khoa, "cau_hoi": q.question,
                "dap_an_chuan": q.answer, "cau_tra_loi_he_thong": r["answer"],
                "trich_dan": "; ".join(r.get("citations", [])), "nguoi_cham": "", "ghi_chu": "",
            })
    print(f"{len(sample)}/{len(answered)} câu -> {args.out}")


if __name__ == "__main__":
    main()
