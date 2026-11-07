"""Chỉ số truy xuất, đo bằng code so với căn cứ chuẩn."""

from dataclasses import dataclass

from evaluation.testset import CanCu
from retrieval.corpus import Passage, Unit


def unit_matches(unit: Unit, gold: CanCu) -> bool:
    """Đơn vị văn bản chứa căn cứ chuẩn.

    unit.khoan None: chunk là trọn Điều nên chứa mọi Khoản.
    unit.khoan 0: tên Điều hoặc phần dẫn trước Khoản 1, chỉ khớp căn cứ cấp Điều.
    """
    if unit.doc_id != gold.doc_id or unit.dieu != gold.dieu:
        return False
    return unit.khoan is None or gold.khoan is None or unit.khoan == gold.khoan


def is_relevant(passage: Passage, gold: list[CanCu]) -> bool:
    return any(unit_matches(u, g) for u in passage.units for g in gold)


@dataclass
class QuestionScore:
    recall_at_k: float
    hit_at_k: float
    reciprocal_rank: float
    wrong_version_at_k: float


def score(ranked: list[Passage], gold: list[CanCu], khoa: int | None, k: int = 5) -> QuestionScore:
    top = ranked[:k]
    covered = sum(any(unit_matches(u, g) for p in top for u in p.units) for g in gold)
    first = next((i for i, p in enumerate(ranked, 1) if is_relevant(p, gold)), None)
    wrong = sum(khoa is not None and not p.ap_dung_cho(khoa) for p in top)
    return QuestionScore(
        recall_at_k=covered / len(gold),
        hit_at_k=float(first is not None and first <= k),
        reciprocal_rank=1 / first if first else 0.0,
        wrong_version_at_k=wrong / len(top) if top else 0.0,
    )
