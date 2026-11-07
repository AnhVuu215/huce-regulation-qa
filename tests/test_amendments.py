"""Văn bản mới sửa quy tắc của văn bản cũ cho mọi khóa (không phải phiên bản theo khóa)."""

from pathlib import Path

import pytest
import yaml

from ingestion.chunker import chunk_document
from ingestion.cli import parse_registered
from ingestion.registry import Document, Registry, SuaDoi, ViTri, amendments_to, load_registry
from retrieval.corpus import Unit, structural_passages

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def docs():
    return load_registry(ROOT / "data" / "registry.yaml").documents


def test_2026_rule_amends_component_weights_of_both_regulations(docs):
    targets = {(sd.doc_id, sd.dieu, sd.khoan) for _, sd in
               amendments_to(docs, "qc-dhxd-2022") + amendments_to(docs, "qc-dhxd-2016")}
    assert targets == {("qc-dhxd-2022", 9, 1), ("qc-dhxd-2016", 19, 1)}


def test_amending_provisions_exist(docs):
    by_id = {d.doc_id: d for d in docs}
    amending = by_id["qd-danh-gia-cdr-2026"]
    dieus = {d.number: d for d in parse_registered(amending, ROOT)}
    for sd in amending.sua_doi:
        for v in sd.can_cu:
            assert v.khoan in {k.number for k in dieus[v.dieu].khoan}


def test_only_amended_chunks_are_marked(docs):
    by_id = {d.doc_id: d for d in docs}
    doc = by_id["qc-dhxd-2022"]
    chunks = chunk_document(doc, parse_registered(doc, ROOT),
                            amendments=amendments_to(docs, doc.doc_id))
    marked = {c.chunk_id for c in chunks if c.sua_doi_boi}
    assert marked == {"qc2022-d9-k1-p1", "qc2022-d9-k1-p2"}


def test_whole_article_chunk_carries_amendment_of_its_clause(docs):
    by_id = {d.doc_id: d for d in docs}
    doc = by_id["qc-dhxd-2016"]
    passages = structural_passages(doc, parse_registered(doc, ROOT),
                                   amendments_to(docs, doc.doc_id))
    d19 = next(p for p in passages if p.passage_id == "qc2016-d19")
    assert d19.amended_by[0].by_doc_id == "qd-danh-gia-cdr-2026"
    assert Unit("qd-danh-gia-cdr-2026", 6, 4) in d19.amended_by[0].units


def test_registry_rejects_amendment_of_unknown_document(tmp_path):
    base = dict(chunk_prefix="x", doc_title="t", so_hieu="s", file="f", sha256="h",
                hieu_luc_tu="2026-01-01")
    bad = Registry(documents=[Document(doc_id="a", **base, sua_doi=[SuaDoi(
        doc_id="khong-co", dieu=1, noi_dung="x", can_cu=[ViTri(dieu=1)])])])
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump(bad.model_dump(mode="json"), allow_unicode=True),
                    encoding="utf-8")
    with pytest.raises(ValueError, match="không hợp lệ"):
        load_registry(path)
