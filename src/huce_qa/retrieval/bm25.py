"""BM25 tự viết, có thêm cặp âm tiết vì từ tiếng Việt thường gồm nhiều âm tiết
("thôi học", "tín chỉ"): khớp cả cặp thì điểm cao hơn khớp rời từng âm tiết."""

import math
import re
import unicodedata
from collections import Counter


def tokenize(text: str) -> list[str]:
    # NFKC đưa chữ toán học (𝑆𝑖,𝑘 trong văn bản 2026) về chữ thường.
    syllables = re.findall(r"\w+", unicodedata.normalize("NFKC", text).lower())
    return syllables + [f"{a}_{b}" for a, b in zip(syllables, syllables[1:], strict=False)]


class BM25:
    def __init__(self, documents: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = [Counter(tokenize(d)) for d in documents]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg_len = sum(self.lengths) / len(self.lengths)
        df = Counter(term for d in self.docs for term in d)
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: str) -> list[float]:
        terms = [t for t in set(tokenize(query)) if t in self.idf]
        result = []
        for doc, length in zip(self.docs, self.lengths, strict=True):
            norm = self.k1 * (1 - self.b + self.b * length / self.avg_len)
            result.append(
                sum(
                    self.idf[t] * doc[t] * (self.k1 + 1) / (doc[t] + norm)
                    for t in terms
                    if t in doc
                )
            )
        return result
