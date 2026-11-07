"""Nạp toàn bộ văn bản trong registry thành data/processed/<doc_id>.json."""

import json
import sys
from pathlib import Path

from ingestion.chunker import Chunk, chunk_document
from ingestion.parser import Dieu, check_structure, coverage, parse_document, stopped_early
from ingestion.pdf_text import clean_lines, extract_pages
from ingestion.registry import Document, load_registry, verify_file

ROOT = Path(__file__).resolve().parents[2]
# Phần bị loại hợp lệ chỉ là tên Chương và khối chữ ký, nên tụt dưới ngưỡng là bị cắt cụt.
MIN_COVERAGE = 0.97


def parse_registered(doc: Document, root: Path = ROOT) -> list[Dieu]:
    pdf_path = verify_file(doc, root)
    if doc.text_file:
        text = (root / doc.text_file).read_text(encoding="utf-8").strip()
    else:
        text = "\n".join(clean_lines(extract_pages(pdf_path)))
    for patch in doc.patches:
        if patch.find not in text:
            raise ValueError(f"{doc.doc_id}: patch không khớp: {patch.find!r}")
        text = text.replace(patch.find, patch.replace)
    lines = text.split("\n")
    if doc.body_start:
        starts = [i for i, line in enumerate(lines) if line.strip() == doc.body_start]
        if not starts:
            raise ValueError(f"{doc.doc_id}: không thấy dòng body_start {doc.body_start!r}")
        lines = lines[starts[0] :]
    dieus = parse_document(lines)
    if stopped_early(lines, dieus):
        raise ValueError(f"{doc.doc_id}: dừng ở Điều {dieus[-1].number} nhưng phía sau còn Điều")
    if (ratio := coverage(lines, dieus)) < MIN_COVERAGE:
        raise ValueError(f"{doc.doc_id}: parser chỉ giữ {ratio:.1%} nội dung, nghi bị cắt cụt")
    return dieus


def ingest(doc: Document, root: Path = ROOT) -> list[Chunk]:
    dieus = parse_registered(doc, root)
    if problems := check_structure(dieus):
        raise ValueError(f"{doc.doc_id}: {problems}")
    return chunk_document(doc, dieus)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    out_dir = ROOT / "data" / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    for doc in load_registry(ROOT / "data" / "registry.yaml").documents:
        chunks = ingest(doc)
        payload = [chunk.model_dump(mode="json") for chunk in chunks]
        out_path = out_dir / f"{doc.doc_id}.json"
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{doc.doc_id}: {len(chunks)} chunk -> {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
