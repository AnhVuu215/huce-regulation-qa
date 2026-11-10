"""Dựng kho văn bản và retriever từ registry: dùng chung cho API và eval."""

from pathlib import Path

from ingestion.cli import parse_registered
from ingestion.parser import Dieu
from ingestion.registry import Document, amendments_to, load_registry
from retrieval.corpus import structural_passages, window_passages
from retrieval.pipeline import RetrievalConfig, Retriever, load_synonyms


def load_corpus(root: Path) -> tuple[dict[str, Document], dict[str, list[Dieu]]]:
    docs = {d.doc_id: d for d in load_registry(root / "data" / "registry.yaml").documents}
    parsed = {doc_id: parse_registered(doc, root) for doc_id, doc in docs.items()}
    return docs, parsed


def build_retriever(
    config: RetrievalConfig,
    docs: dict[str, Document],
    parsed: dict[str, list[Dieu]],
    embedder,
    reranker,
    root: Path,
) -> Retriever:
    passages = []
    for doc in docs.values():
        if config.chunking == "window":
            passages += window_passages(
                doc, parsed[doc.doc_id], config.window_words, config.window_overlap
            )
        else:
            passages += structural_passages(
                doc, parsed[doc.doc_id], amendments_to(list(docs.values()), doc.doc_id)
            )
    return Retriever(
        config, passages, embedder, reranker, load_synonyms(root / "data" / "synonyms.yaml")
    )
