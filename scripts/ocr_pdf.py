"""OCR một PDF scan bằng Tesseract (tiếng Việt) chạy trong Docker.

    docker build -t huce-ocr -f docker/ocr.Dockerfile docker
    uv run python scripts/ocr_pdf.py data/raw/qc-dhxd-2022.pdf data/ocr/qc-dhxd-2022.raw.txt

Kết quả là OCR thô. Bản dùng cho hệ thống nằm ở data/text/ và đã được soát tay với ảnh gốc;
test so sánh hai bản để bảo đảm việc soát chỉ sửa lỗi nhận dạng.
"""

import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

import pymupdf

DPI = 300


def ocr(pdf_path: Path) -> str:
    pages = []
    with tempfile.TemporaryDirectory() as tmp, pymupdf.open(pdf_path) as pdf:
        for i, page in enumerate(pdf, start=1):
            name = f"p{i:03}"
            page.get_pixmap(dpi=DPI, colorspace=pymupdf.csGRAY).save(Path(tmp) / f"{name}.png")
            subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    f"{tmp}:/w",
                    "huce-ocr",
                    f"/w/{name}.png",
                    f"/w/{name}",
                    "-l",
                    "vie",
                    "--psm",
                    "4",
                    "--oem",
                    "1",
                ],
                check=True,
                capture_output=True,
            )
            text = (Path(tmp) / f"{name}.txt").read_text(encoding="utf-8")
            pages.append(f"#### PAGE {i}\n{text.strip()}")
    return unicodedata.normalize("NFC", "\n".join(pages)) + "\n"


if __name__ == "__main__":
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    dst.write_text(ocr(src), encoding="utf-8")
    print(f"{src} -> {dst}")
