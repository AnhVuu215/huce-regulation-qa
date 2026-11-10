"""Độ khớp giữa giám khảo LLM và người chấm: tỷ lệ trùng và Cohen's kappa."""

from collections import Counter


def agreement(a: list[str], b: list[str]) -> float:
    if len(a) != len(b) or not a:
        raise ValueError("Hai danh sách phải cùng độ dài và không rỗng")
    return sum(x == y for x, y in zip(a, b, strict=True)) / len(a)


def cohen_kappa(a: list[str], b: list[str]) -> float:
    """Trùng khớp sau khi trừ phần trùng do ngẫu nhiên. 1 là khớp hoàn toàn, 0 là như đoán bừa."""
    observed = agreement(a, b)
    n = len(a)
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    if expected == 1:
        return 1.0
    return (observed - expected) / (1 - expected)


def confusion(a: list[str], b: list[str], labels: tuple[str, ...]) -> dict[str, dict[str, int]]:
    table = {x: dict.fromkeys(labels, 0) for x in labels}
    for x, y in zip(a, b, strict=True):
        table[x][y] += 1
    return table
