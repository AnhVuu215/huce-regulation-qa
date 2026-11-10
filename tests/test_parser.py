from huce_qa.ingestion.parser import check_structure, coverage, parse_document, stopped_early
from huce_qa.ingestion.pdf_text import FORMULA_PLACEHOLDER, clean_lines


def test_cross_reference_at_line_start_is_not_a_heading():
    dieus = parse_document(
        [
            "Điều 1. Nghỉ học",
            "1. Thời gian nghỉ được tính theo khoản 3",
            "Điều 6 của Quy chế này.",
            "2. Khoản tiếp theo.",
        ]
    )
    assert len(dieus) == 1
    assert [k.number for k in dieus[0].khoan] == [1, 2]
    assert "Điều 6 của Quy chế này." in dieus[0].khoan[0].text


def test_out_of_sequence_dieu_stays_in_body():
    dieus = parse_document(["Điều 1. A", "1. Xem", "Điều 9. Tên điều khác", "2. Hết."])
    assert len(dieus) == 1
    assert "Điều 9." in dieus[0].khoan[0].text


def test_wrapped_title_is_joined():
    dieus = parse_document(["Điều 1. Thực tập cuối khoá của ngành", "đặc thù", "Nội dung."])
    assert dieus[0].title == "Thực tập cuối khoá của ngành đặc thù"
    assert dieus[0].preamble == "Nội dung."


def test_preamble_is_separate_from_khoan():
    dieus = parse_document(["Điều 1. A", "Được đánh giá qua:", "1. Tiêu chí một."])
    assert dieus[0].preamble == "Được đánh giá qua:"
    assert dieus[0].khoan[0].text == "1. Tiêu chí một."


def test_diem_supports_both_markers_and_skipped_letters():
    dieus = parse_document(
        ["Điều 1. A", "1. Gồm:", "a. Một;", "b) Hai;", "d) Ba;", "đ) Bốn;", "e) Năm."]
    )
    assert dieus[0].khoan[0].diem == ["a", "b", "d", "đ", "e"]


def test_chuong_is_carried_to_following_dieu():
    dieus = parse_document(
        ["Chương I", "TÊN MỘT", "Điều 1. A", "Nội dung.", "Chương II", "TÊN", "Điều 2. B", "X."]
    )
    assert [d.chuong for d in dieus] == ["Chương I", "Chương II"]
    assert "TÊN MỘT" not in dieus[0].body


def test_signature_block_is_excluded():
    dieus = parse_document(["Điều 1. A", "Nội dung.", "K/T. HIỆU TRƯỞNG", "PHÓ HIỆU TRƯỞNG"])
    assert dieus[0].body == "Nội dung."


def test_sentence_starting_with_hieu_truong_is_not_a_signature():
    dieus = parse_document(["Điều 1. A", "Hiệu trưởng quy định cụ thể.", "Điều 2. B", "Nội dung."])
    assert [d.number for d in dieus] == [1, 2]


def test_coverage_detects_truncation():
    lines = ["Điều 1. A", "Một hai ba bốn năm sáu bảy tám chín mười."]
    assert coverage(lines, parse_document(lines)) == 1.0
    assert coverage(lines, parse_document(lines[:1])) < 0.5


def test_clean_lines_drops_page_number_and_keeps_numbers_in_text():
    assert clean_lines([" \n12\nDòng một\n68 tín chỉ;\n"]) == ["Dòng một", "68 tín chỉ;"]


def test_clean_lines_collapses_broken_formula():
    pages = ["1\nCông thức:\n" + "\n".join("niAn1") + "\nTrong đó:\n"]
    assert clean_lines(pages) == ["Công thức:", FORMULA_PLACEHOLDER, "Trong đó:"]


def test_check_structure_reports_empty_dieu():
    assert check_structure(parse_document(["Điều 1. A"])) == ["Điều 1 không có nội dung"]


def test_appendix_heading_stops_body_but_reference_does_not():
    lines = ["Điều 1. A", "1. Theo", "Phụ lục 3 và tuân thủ quy định.", "Phụ lục 1. BIỂU MẪU", "x"]
    dieus = parse_document(lines)
    assert "Phụ lục 3 và tuân thủ" in dieus[0].body
    assert "BIỂU MẪU" not in dieus[0].body


def test_false_stop_is_detected():
    lines = ["Điều 1. A", "Nội dung.", "HIỆU TRƯỞNG", "Điều 2. B", "Nội dung."]
    dieus = parse_document(lines)
    assert [d.number for d in dieus] == [1]
    assert stopped_early(lines, dieus)
    assert not stopped_early(lines[:3], parse_document(lines[:3]))
