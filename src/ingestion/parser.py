"""Parser cấu trúc Chương/Điều/Khoản/Điểm của văn bản quy phạm tiếng Việt.

Số Điều và số Khoản phải tăng liên tiếp mới được nhận là tiêu đề mới. Nhờ vậy các
dòng bắt đầu bằng tham chiếu chéo (ví dụ "Điều 6 của Quy chế này.") không tách nhầm.
"""

import re
from dataclasses import dataclass, field

CHUONG = re.compile(r"^\s*Chương\s+([IVXLC]+)\s*$")
DIEU = re.compile(r"^\s*Điều\s+(\d+)\.\s*(.*)$")
KHOAN = re.compile(r"^\s*(\d{1,2})\.\s+(.*)$")
DIEM = re.compile(r"^\s*([a-zđ])[).]\s+(.*)$")
# Phân biệt hoa thường: "Hiệu trưởng quy định..." là nội dung, không phải khối chữ ký.
SIGNATURE = re.compile(
    r"^\s*(?:(?:K/?T|TM|Q)\.?\s*)?(?:PHÓ\s+)?(?:HIỆU TRƯỞNG|BỘ TRƯỞNG)\s*$|^\s*Nơi nhận"
)

# Tiêu đề Phụ lục thật ("Phụ lục 1. ...", "PHỤ LỤC 2: ..."), không phải câu tham chiếu
# bị xuống dòng như "Phụ lục 3 và tuân thủ ...".
APPENDIX = re.compile(r"^\s*(?:PHỤ LỤC|Phụ lục\s+[\dIVX]+(?:-[A-Z])?\s*[.:]\s)")

DIEM_ORDER = "abcdđefghiklmnopqrstuvxy"
PARAGRAPH_END = (".", ";", ":")


@dataclass
class Khoan:
    number: int
    lines: list[str] = field(default_factory=list)
    diem: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return _join(self.lines)


@dataclass
class Dieu:
    number: int
    title: str
    chuong: str | None
    preamble_lines: list[str] = field(default_factory=list)
    khoan: list[Khoan] = field(default_factory=list)

    @property
    def preamble(self) -> str:
        return _join(self.preamble_lines)

    @property
    def heading(self) -> str:
        return f"Điều {self.number}. {self.title}"

    @property
    def body(self) -> str:
        parts = [self.preamble] if self.preamble_lines else []
        parts.extend(k.text for k in self.khoan)
        return "\n".join(parts)


def _join(lines: list[str]) -> str:
    """Nối dòng bị ngắt do khổ giấy, giữ xuống dòng ở cuối đoạn và trước mỗi Điểm."""
    text = ""
    for raw in lines:
        line = " ".join(raw.split())
        if not text:
            text = line
        elif text.endswith(PARAGRAPH_END) or DIEM.match(line):
            text += "\n" + line
        else:
            text += " " + line
    return text


def _is_next_diem(letter: str, khoan: Khoan) -> bool:
    if letter not in DIEM_ORDER:
        return False
    if not khoan.diem:
        return letter == "a"
    return DIEM_ORDER.index(letter) > DIEM_ORDER.index(khoan.diem[-1])


def _first_dieu(lines: list[str]) -> int:
    return next((i for i, line in enumerate(lines) if DIEU.match(line)), len(lines))


def body_end(lines: list[str]) -> int:
    """Vị trí khối chữ ký hoặc Phụ lục đầu tiên sau Điều đầu tiên: phần thân kết thúc ở đó."""
    start = _first_dieu(lines)
    for i in range(start + 1, len(lines)):
        if SIGNATURE.match(lines[i]) or APPENDIX.match(lines[i]):
            return i
    return len(lines)


def parse_document(lines: list[str]) -> list[Dieu]:
    dieus: list[Dieu] = []
    chuong: str | None = None
    lines = lines[: body_end(lines)]
    i = 0
    while i < len(lines):
        line = lines[i]

        if match := CHUONG.match(line):
            chuong = f"Chương {match.group(1)}"
            i += 2  # dòng kế tiếp là tên Chương
            continue

        match = DIEU.match(line)
        if match and int(match.group(1)) == len(dieus) + 1:
            title = match.group(2).strip()
            # Tiêu đề dài xuống dòng: phần nối tiếp luôn bắt đầu bằng chữ thường.
            while i + 1 < len(lines) and lines[i + 1].strip()[:1].islower():
                i += 1
                title += " " + lines[i].strip()
            dieus.append(Dieu(int(match.group(1)), " ".join(title.split()), chuong))
            i += 1
            continue

        if dieus:
            _add_body_line(dieus[-1], line)
        i += 1
    return dieus


def _add_body_line(dieu: Dieu, line: str) -> None:
    match = KHOAN.match(line)
    if match and int(match.group(1)) == len(dieu.khoan) + 1:
        dieu.khoan.append(Khoan(int(match.group(1)), [line]))
        return
    if not dieu.khoan:
        dieu.preamble_lines.append(line)
        return
    khoan = dieu.khoan[-1]
    match = DIEM.match(line)
    if match and _is_next_diem(match.group(1), khoan):
        khoan.diem.append(match.group(1))
    khoan.lines.append(line)


def coverage(lines: list[str], dieus: list[Dieu]) -> float:
    """Tỷ lệ từ của phần thân (từ Điều đầu tiên tới điểm dừng) còn giữ lại sau khi parse."""
    source = sum(len(line.split()) for line in lines[_first_dieu(lines) : body_end(lines)])
    kept = sum(len(d.heading.split()) + len(d.body.split()) for d in dieus)
    return kept / source if source else 0.0


def stopped_early(lines: list[str], dieus: list[Dieu]) -> bool:
    """Sau điểm dừng mà vẫn còn Điều kế tiếp thì điểm dừng đã nhận nhầm (ví dụ một câu
    bắt đầu bằng "Hiệu trưởng ..." bị coi là khối chữ ký)."""
    if not dieus:
        return False
    next_heading = re.compile(rf"^\s*Điều\s+{dieus[-1].number + 1}\.\s")
    return any(next_heading.match(line) for line in lines[body_end(lines) :])


def check_structure(dieus: list[Dieu]) -> list[str]:
    """Trả về danh sách vấn đề để người soát, rỗng nghĩa là cấu trúc ổn."""
    problems: list[str] = []
    for expected, dieu in enumerate(dieus, start=1):
        if dieu.number != expected:
            problems.append(f"Số Điều không liên tục tại Điều {dieu.number}")
        if not dieu.title:
            problems.append(f"Điều {dieu.number} thiếu tiêu đề")
        if not dieu.body.strip():
            problems.append(f"Điều {dieu.number} không có nội dung")
    return problems
