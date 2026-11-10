"""Đơn vị truy xuất (passage) và hai cách chia: theo cấu trúc, theo cửa sổ từ (baseline)."""

from collections.abc import Sequence
from dataclasses import dataclass

from huce_qa.ingestion.chunker import amendment_matches, chunk_document
from huce_qa.ingestion.parser import Dieu
from huce_qa.ingestion.registry import Document, SuaDoi


@dataclass(frozen=True)
class Unit:
    doc_id: str
    dieu: int
    # None: trọn Điều; 0: tên Điều và phần dẫn; số dương: một Khoản.
    khoan: int | None


@dataclass(frozen=True)
class Amendment:
    """Đoạn này bị văn bản `by_doc_id` sửa đổi; `units` là các Điều/Khoản thay thế."""

    by_doc_id: str
    noi_dung: str
    units: tuple[Unit, ...]


@dataclass(frozen=True)
class Passage:
    passage_id: str
    doc_id: str
    text: str
    units: tuple[Unit, ...]
    khoa_tu: int | None
    khoa_den: int | None
    amended_by: tuple[Amendment, ...] = ()

    def ap_dung_cho(self, khoa: int) -> bool:
        return (self.khoa_tu is None or khoa >= self.khoa_tu) and (
            self.khoa_den is None or khoa <= self.khoa_den
        )


def structural_passages(
    doc: Document, dieus: list[Dieu], amendments: Sequence[tuple[str, SuaDoi]] = ()
) -> list[Passage]:
    """`amendments`: các sửa đổi nhắm vào văn bản này (registry.amendments_to)."""
    passages = []
    for c in chunk_document(doc, dieus, amendments=amendments):
        amended_by = tuple(
            Amendment(by, sd.noi_dung, tuple(Unit(by, v.dieu, v.khoan) for v in sd.can_cu))
            for by, sd in amendments
            if amendment_matches(sd, c.dieu, c.khoan)
        )
        passages.append(
            Passage(
                passage_id=c.chunk_id,
                doc_id=doc.doc_id,
                text=c.text,
                units=(Unit(doc.doc_id, c.dieu, c.khoan),),
                khoa_tu=doc.khoa_tu,
                khoa_den=doc.khoa_den,
                amended_by=amended_by,
            )
        )
    return passages


def _labelled_words(doc: Document, dieus: list[Dieu]) -> list[tuple[str, Unit]]:
    words: list[tuple[str, Unit]] = []
    for d in dieus:
        head = d.heading + ("\n" + d.preamble if d.preamble_lines else "")
        words += [(w, Unit(doc.doc_id, d.number, 0)) for w in head.split()]
        for k in d.khoan:
            words += [(w, Unit(doc.doc_id, d.number, k.number)) for w in k.text.split()]
    return words


def window_passages(
    doc: Document, dieus: list[Dieu], size: int = 200, overlap: int = 50
) -> list[Passage]:
    """Baseline: cửa sổ từ cố định trượt trên toàn văn bản, không biết Điều/Khoản."""
    words = _labelled_words(doc, dieus)
    passages = []
    for n, start in enumerate(range(0, max(len(words) - overlap, 1), size - overlap)):
        window = words[start : start + size]
        units = tuple(dict.fromkeys(u for _, u in window))
        passages.append(
            Passage(
                passage_id=f"{doc.chunk_prefix}-w{n}",
                doc_id=doc.doc_id,
                text=" ".join(w for w, _ in window),
                units=units,
                khoa_tu=doc.khoa_tu,
                khoa_den=doc.khoa_den,
            )
        )
    return passages
