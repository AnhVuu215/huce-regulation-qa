from pathlib import Path

import pytest

from ingestion.cli import parse_registered
from ingestion.registry import load_registry
from tools.hoc_vu import FUNCTION_DECLARATIONS, TOOL_NAMES, HocVu, ToolError, lam_tron

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def docs():
    return {d.doc_id: d for d in load_registry(ROOT / "data" / "registry.yaml").documents}


@pytest.fixture(scope="module")
def hv(docs):
    return HocVu(ROOT / "data" / "rules" / "hoc-vu.yaml", docs)


def test_every_rule_citation_exists_in_corpus(hv, docs):
    parsed = {}
    for doc_id, version in hv.versions.items():
        for name, rule in version.items():
            for cite in _citations(rule):
                target = cite.get("doc_id", doc_id)
                if target not in parsed:
                    parsed[target] = {d.number: d for d in parse_registered(docs[target], ROOT)}
                dieu = parsed[target].get(cite["dieu"])
                assert dieu is not None, (doc_id, name, cite)
                if cite.get("khoan"):
                    assert cite["khoan"] in {k.number for k in dieu.khoan}, (doc_id, name, cite)


def _citations(node):
    if isinstance(node, dict):
        if "dieu" in node:
            yield node
        for value in node.values():
            yield from _citations(value)
    elif isinstance(node, list):
        for value in node:
            yield from _citations(value)


def test_rounding_is_half_up_not_bankers():
    assert lam_tron(2.25, 1) == 2.3
    assert lam_tron(8.45, 1) == 8.5
    assert lam_tron(2.125, 2) == 2.13


def test_version_is_chosen_by_cohort(hv):
    assert hv.phien_ban(66) == "qc-dhxd-2016"
    assert hv.phien_ban(67) == "qc-dhxd-2022"
    with pytest.raises(ToolError):
        hv.phien_ban(None)


@pytest.mark.parametrize(("diem", "chu"), [(8.45, "A"), (8.44, "B+"), (3.95, "D"), (3.94, "F")])
def test_letter_grade_boundaries_after_rounding(hv, diem, chu):
    assert hv.quy_doi_diem(68, diem)["diem_chu"] == chu


@pytest.mark.parametrize(
    ("gpa", "loai"),
    [(3.2, "Giỏi"), (3.19, "Khá"), (3.15, "Khá"), (2.0, "Trung bình"), (0.99, "Kém")],
)
def test_academic_standing_2022(hv, gpa, loai):
    assert hv.xep_loai_hoc_luc(68, gpa)["xep_loai"] == loai


def test_academic_standing_2016_has_two_levels(hv):
    assert hv.xep_loai_hoc_luc(65, 1.99)["xep_loai"] == "Yếu"
    assert hv.xep_loai_hoc_luc(65, 3.9)["xep_loai"] == "Bình thường"


def test_semester_gpa_matches_test_set_q035(hv):
    # q035: 8,2 (3 tín), 6,7 (2 tín), 5,2 (3 tín) -> B+, C+, D+ -> 2,50
    r = hv.tinh_diem_trung_binh(
        68,
        [
            {"diem_10": 8.2, "tin_chi": 3},
            {"diem_10": 6.7, "tin_chi": 2},
            {"diem_10": 5.2, "tin_chi": 3},
        ],
    )
    assert r["diem_trung_binh"] == 2.5
    assert [d["diem_chu"] for d in r["chi_tiet"]] == ["B+", "C+", "D+"]


def test_pass_only_letters_are_excluded_from_gpa(hv):
    hoc_phan = [{"diem_chu": "A", "tin_chi": 2}, {"diem_chu": "P", "tin_chi": 3}]
    r = hv.tinh_diem_trung_binh(68, hoc_phan)
    assert r["diem_trung_binh"] == 4.0 and r["khong_tinh"] == ["P"]


def test_graduation_downgrade_matches_q034(hv):
    r = hv.xep_hang_tot_nghiep(68, 3.65, tin_chi_hoc_lai=12, tong_tin_chi_chuong_trinh=150)
    assert (r["hang_theo_diem"], r["hang"], r["bi_ha_hang"]) == ("Xuất sắc", "Giỏi", True)


def test_exactly_five_percent_retake_is_not_downgraded(hv):
    r = hv.xep_hang_tot_nghiep(68, 3.65, tin_chi_hoc_lai=5, tong_tin_chi_chuong_trinh=100)
    assert r["hang"] == "Xuất sắc"


def test_graduation_versions_differ(hv):
    assert hv.xep_hang_tot_nghiep(65, 3.15)["hang"] == "Khá"
    assert hv.xep_hang_tot_nghiep(65, 3.2)["hang"] == "Giỏi"
    assert hv.xep_hang_tot_nghiep(68, 1.9)["du_dieu_kien_diem"] is False


def test_year_level_2022_needs_m_and_matches_q036(hv):
    with pytest.raises(ToolError):
        hv.xep_trinh_do_nam(68, 65)
    assert hv.xep_trinh_do_nam(68, 65, tin_chi_trung_binh_mot_nam=30)["nam_thu"] == 3
    assert hv.xep_trinh_do_nam(68, 60, tin_chi_trung_binh_mot_nam=30)["nam_thu"] == 3


def test_year_level_2016_uses_fixed_thresholds(hv):
    assert hv.xep_trinh_do_nam(65, 33)["nam_thu"] == 1
    assert hv.xep_trinh_do_nam(65, 34)["nam_thu"] == 2


def test_warning_matches_q037_and_q039(hv):
    assert hv.kiem_tra_canh_bao(68, tin_chi_dang_ky=18, tin_chi_khong_dat=10)["bi_canh_bao"]
    assert not hv.kiem_tra_canh_bao(68, tin_chi_dang_ky=18, tin_chi_khong_dat=9)["bi_canh_bao"]
    assert hv.kiem_tra_canh_bao(65, diem_trung_binh_hoc_ky=0.75, la_hoc_ky_dau=True)["bi_canh_bao"]


def test_module_score_with_current_weights_matches_q038(hv):
    # 0,25×6,0 + 0,25×5,0 + 0,5×2,0 = 3,75 -> làm tròn nửa lên 3,8 -> F
    r = hv.tinh_diem_hoc_phan(68, diem_thuong_xuyen=6.0, diem_giua_ky=5.0, diem_cuoi_ky=2.0)
    assert (r["diem_hoc_phan"], r["diem_chu"], r["dat"]) == (3.8, "F", False)
    assert "canh_bao" not in r
    assert {"doc_id": "qd-danh-gia-cdr-2026", "dieu": 6, "khoan": 4} in r["can_cu"]


def test_current_weights_apply_to_every_cohort(hv):
    old = hv.tinh_diem_hoc_phan(65, diem_thuong_xuyen=6.0, diem_giua_ky=5.0, diem_cuoi_ky=2.0)
    assert old["diem_hoc_phan"] == 3.8


def test_custom_weights_are_computed_but_flagged(hv):
    r = hv.tinh_diem_hoc_phan(
        68, diem_thanh_phan=[{"diem": 6.0, "trong_so": 0.4}, {"diem": 2.0, "trong_so": 0.6}]
    )
    assert (r["diem_hoc_phan"], r["diem_chu"]) == (3.6, "F")
    assert "25%" in r["canh_bao"] and "50%" in r["canh_bao"]


def test_custom_weights_equal_to_current_are_not_flagged(hv):
    r = hv.tinh_diem_hoc_phan(
        68,
        diem_thanh_phan=[
            {"diem": 7, "trong_so": 0.25},
            {"diem": 7, "trong_so": 0.25},
            {"diem": 7, "trong_so": 0.5},
        ],
    )
    assert "canh_bao" not in r


def test_partial_component_scores_are_rejected(hv):
    with pytest.raises(ToolError):
        hv.tinh_diem_hoc_phan(68, diem_thuong_xuyen=6.0, diem_cuoi_ky=2.0)


def test_call_returns_errors_to_llm_instead_of_raising(hv):
    assert "loi" in hv.call("xep_trinh_do_nam", {"khoa": 68, "tin_chi_tich_luy": 65})
    assert "loi" in hv.call("khong_ton_tai", {})
    assert "loi" in hv.call("quy_doi_diem", {"khoa": 68})


def test_declarations_match_methods(hv):
    assert all(callable(getattr(hv, name)) for name in TOOL_NAMES)
    assert len(TOOL_NAMES) == len(FUNCTION_DECLARATIONS)


def _cited(result):
    return {(c["dieu"], c["khoan"]) for c in result["can_cu"]}


def test_graduation_rank_cites_the_thresholds_it_used(hv):
    # 2022: hạng theo ngưỡng Điều 10 khoản 4; 2016: ngưỡng riêng ở Điều 28 khoản 1.
    assert _cited(hv.xep_hang_tot_nghiep(68, 3.65)) == {(13, 3), (10, 4)}
    assert _cited(hv.xep_hang_tot_nghiep(65, 3.15)) == {(28, 1)}
    assert _cited(hv.xep_hang_tot_nghiep(68, 1.9)) == {(13, 1)}


def test_module_score_cites_weights_and_letter_scale_only(hv):
    r = hv.tinh_diem_hoc_phan(68, diem_thuong_xuyen=6.0, diem_giua_ky=5.0, diem_cuoi_ky=2.0)
    assert {(c["doc_id"], c["dieu"], c["khoan"]) for c in r["can_cu"]} == {
        ("qd-danh-gia-cdr-2026", 5, 2),
        ("qd-danh-gia-cdr-2026", 6, 3),
        ("qd-danh-gia-cdr-2026", 6, 4),
        ("qc-dhxd-2022", 9, 4),
    }
