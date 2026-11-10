"""Độ khớp giữa giám khảo LLM và người chấm trên bảng chấm tay đã điền.

uv run python eval/judge_agreement.py eval/results/<lần chạy có --judge>.json
"""

import argparse
import csv
import json
import sys
from pathlib import Path

from huce_qa.evaluation.agreement import agreement, cohen_kappa, confusion
from huce_qa.evaluation.judge import VERDICTS

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path, nargs="+", help="các lần chạy đã tạo bảng chấm")
    parser.add_argument("--sheet", type=Path, default=ROOT / "eval" / "human" / "cham-tay.csv")
    parser.add_argument(
        "--column",
        default="nguoi_cham",
        help="cột điểm người chấm: nguoi_cham (chấm mù) hoặc phan_xu (sau phân xử)",
    )
    args = parser.parse_args()

    judged = {}
    for path in args.results:
        run = json.loads(path.read_text(encoding="utf-8"))
        judged.update({r["id"]: r for r in run["questions"]})
    with args.sheet.open(encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r[args.column].strip()]
    invalid = [r["id"] for r in rows if r[args.column].strip() not in VERDICTS]
    if invalid:
        raise SystemExit(f"Giá trị nguoi_cham không hợp lệ ở {invalid}; dùng {VERDICTS}")
    if not rows:
        raise SystemExit("Bảng chấm chưa có câu nào được chấm.")

    human = [r[args.column].strip() for r in rows]
    llm = [judged[r["id"]]["judge"] for r in rows]
    result = {
        "so_cau": len(rows),
        "ty_le_trung": round(agreement(human, llm), 3),
        "cohen_kappa": round(cohen_kappa(human, llm), 3),
        "ma_tran (hàng: người, cột: giám khảo)": confusion(human, llm, VERDICTS),
        "lech": [
            {
                "id": r["id"],
                "nguoi": h,
                "giam_khao": j,
                "ly_do_giam_khao": judged[r["id"]].get("judge_reason", ""),
            }
            for r, h, j in zip(rows, human, llm, strict=True)
            if h != j
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
