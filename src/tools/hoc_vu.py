"""Công cụ tính toán học vụ theo đúng phiên bản quy chế của khóa người hỏi.

Mọi ngưỡng lấy từ data/rules/hoc-vu.yaml; mọi kết quả kèm căn cứ Điều/Khoản để câu trả lời
dùng công cụ vẫn được hậu kiểm trích dẫn. Thiếu dữ liệu thì báo thiếu, không đoán.
"""

from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import yaml

from ingestion.registry import Document


class ToolError(ValueError):
    """Đầu vào không đủ hoặc không hợp lệ; thông điệp được trả lại cho LLM."""


def lam_tron(value: float, digits: int) -> float:
    # round() của Python làm tròn kiểu ngân hàng (2,25 -> 2,2); quy chế dùng làm tròn thông thường.
    return float(Decimal(str(value)).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP))


class HocVu:
    def __init__(self, rules_path: Path, docs: dict[str, Document]):
        data = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
        self.versions: dict[str, dict] = data["versions"]
        self.docs = docs

    # ---- phiên bản và căn cứ -------------------------------------------------------------
    def phien_ban(self, khoa: int | None) -> str:
        if khoa is None:
            raise ToolError("Cần biết khóa của sinh viên để chọn đúng phiên bản quy chế.")
        matches = [d for d in self.versions if self.docs[d].ap_dung_cho(khoa)]
        if not matches:
            raise ToolError(f"Không có quy chế nào trong hệ thống áp dụng cho K{khoa}.")
        return matches[0]

    @staticmethod
    def _cite(doc_id: str, can_cu: dict) -> dict:
        return {"doc_id": doc_id, "dieu": can_cu["dieu"], "khoan": can_cu.get("khoan")}

    def _rule(self, khoa: int | None, name: str) -> tuple[str, dict]:
        doc_id = self.phien_ban(khoa)
        if name not in self.versions[doc_id]:
            raise ToolError(f"Quy chế áp dụng cho K{khoa} không có quy định về {name}.")
        return doc_id, self.versions[doc_id][name]

    # ---- công cụ --------------------------------------------------------------------------
    def tinh_diem_hoc_phan(self, khoa: int, diem_thanh_phan: list[dict]) -> dict:
        """Điểm học phần = tổng điểm thành phần nhân trọng số, rồi quy đổi điểm chữ."""
        doc_id, rule = self._rule(khoa, "diem_hoc_phan")
        if not diem_thanh_phan:
            raise ToolError("Cần ít nhất một điểm thành phần kèm trọng số.")
        total_weight = sum(float(c["trong_so"]) for c in diem_thanh_phan)
        if abs(total_weight - 1) > 1e-6:
            raise ToolError(f"Tổng trọng số phải bằng 1, đang là {total_weight:g}.")
        raw = sum(float(c["diem"]) * float(c["trong_so"]) for c in diem_thanh_phan)
        result = self.quy_doi_diem(khoa, raw)
        result["cong_thuc"] = " + ".join(
            f"{float(c['trong_so']):g}×{float(c['diem']):g}" for c in diem_thanh_phan
        )
        result["can_cu"].insert(0, self._cite(doc_id, rule["can_cu"]))
        return result

    def quy_doi_diem(self, khoa: int, diem_10: float) -> dict:
        doc_id, scale = self._rule(khoa, "thang_diem_chu")
        _, points = self._rule(khoa, "diem_so")
        if not 0 <= float(diem_10) <= 10:
            raise ToolError("Điểm học phần phải nằm trong thang 0 đến 10.")
        rounded = lam_tron(float(diem_10), scale["lam_tron_diem_hoc_phan"])
        letter = next(m["chu"] for m in scale["muc"] if rounded >= m["tu"])
        return {
            "diem_hoc_phan": rounded,
            "diem_chu": letter,
            "diem_so": points["quy_doi"][letter],
            "dat": letter != "F",
            "can_cu": [self._cite(doc_id, scale["can_cu"]), self._cite(doc_id, points["can_cu"])],
        }

    def tinh_diem_trung_binh(self, khoa: int, hoc_phan: list[dict]) -> dict:
        """Trung bình có trọng số tín chỉ của điểm số hệ 4. Mỗi học phần cho điểm hệ 10
        (diem_10) hoặc điểm chữ (diem_chu). Điểm chữ ngoài thang (P, I, X, R) không tính."""
        doc_id, points = self._rule(khoa, "diem_so")
        detail, skipped, weighted, credits = [], [], 0.0, 0
        for hp in hoc_phan:
            tin_chi = int(hp["tin_chi"])
            if hp.get("diem_10") is not None:
                letter = self.quy_doi_diem(khoa, hp["diem_10"])["diem_chu"]
            else:
                letter = str(hp.get("diem_chu", "")).strip().upper()
            if letter not in points["quy_doi"]:
                skipped.append(letter or "?")
                continue
            value = points["quy_doi"][letter]
            detail.append({"diem_chu": letter, "diem_so": value, "tin_chi": tin_chi})
            weighted += value * tin_chi
            credits += tin_chi
        if credits == 0:
            raise ToolError("Không có học phần nào được tính vào điểm trung bình.")
        return {
            "diem_trung_binh": lam_tron(weighted / credits, points["lam_tron_diem_trung_binh"]),
            "tong_tin_chi": credits,
            "chi_tiet": detail,
            "khong_tinh": skipped,
            "can_cu": [self._cite(doc_id, points["can_cu"])],
        }

    def xep_loai_hoc_luc(self, khoa: int, diem_trung_binh: float) -> dict:
        doc_id, rule = self._rule(khoa, "xep_loai_hoc_luc")
        loai = next(m["loai"] for m in rule["muc"] if float(diem_trung_binh) >= m["tu"])
        return {"xep_loai": loai, "can_cu": [self._cite(doc_id, rule["can_cu"])]}

    def xep_hang_tot_nghiep(
        self,
        khoa: int,
        diem_trung_binh_tich_luy: float,
        tin_chi_hoc_lai: int = 0,
        tong_tin_chi_chuong_trinh: int | None = None,
        bi_ky_luat_tu_canh_cao: bool = False,
    ) -> dict:
        doc_id, rule = self._rule(khoa, "tot_nghiep")
        gpa = float(diem_trung_binh_tich_luy)
        cite = [self._cite(doc_id, rule["dieu_kien_gpa"]["can_cu"])]
        if gpa < rule["dieu_kien_gpa"]["tu"]:
            return {"du_dieu_kien_diem": False, "hang": None,
                    "ghi_chu": f"Điểm trung bình tích lũy dưới {rule['dieu_kien_gpa']['tu']}.",
                    "can_cu": cite}
        hang_rule = rule["hang"]
        levels = (self.versions[doc_id]["xep_loai_hoc_luc"]["muc"]
                  if hang_rule.get("theo") == "xep_loai_hoc_luc" else hang_rule["muc"])
        names = [m["loai"] for m in levels]
        hang = next(m["loai"] for m in levels if gpa >= m["tu"])
        cite.append(self._cite(doc_id, hang_rule["can_cu"]))

        reasons = []
        ha = rule["ha_hang"]
        if hang in ha["ap_dung_cho"]:
            if tin_chi_hoc_lai:
                if not tong_tin_chi_chuong_trinh:
                    raise ToolError("Cần tổng số tín chỉ của chương trình để xét tỷ lệ học lại.")
                ratio = tin_chi_hoc_lai / tong_tin_chi_chuong_trinh
                if ratio > ha["ty_le_hoc_lai_vuot"]:
                    reasons.append(f"học lại {tin_chi_hoc_lai}/{tong_tin_chi_chuong_trinh} tín chỉ "
                                   f"= {ratio:.1%}, vượt {ha['ty_le_hoc_lai_vuot']:.0%}")
            if bi_ky_luat_tu_canh_cao:
                reasons.append("bị kỷ luật từ mức cảnh cáo trở lên")
        final = names[names.index(hang) + 1] if reasons else hang
        if reasons:
            cite.append(self._cite(doc_id, ha["can_cu"]))
        return {"du_dieu_kien_diem": True, "hang_theo_diem": hang, "hang": final,
                "bi_ha_hang": bool(reasons), "ly_do_ha_hang": reasons, "can_cu": cite}

    def xep_trinh_do_nam(
        self, khoa: int, tin_chi_tich_luy: int, tin_chi_trung_binh_mot_nam: float | None = None
    ) -> dict:
        doc_id, rule = self._rule(khoa, "trinh_do_nam")
        n = float(tin_chi_tich_luy)
        if "boi_so_M" in rule:
            if not tin_chi_trung_binh_mot_nam:
                raise ToolError("Quy chế này xếp năm theo số tín chỉ trung bình một năm (M) của "
                                "chương trình; cần biết M hoặc tổng tín chỉ và số năm thiết kế.")
            m = float(tin_chi_trung_binh_mot_nam)
            nam = sum(n >= k * m for k in rule["boi_so_M"]) + 1
            nguong = f"M = {m:g}: năm thứ {nam} khi {(nam - 1) * m:g} ≤ N < {nam * m:g}"
        else:
            nam = sum(n >= t for t in rule["nguong_tin_chi"]) + 1
            nguong = f"ngưỡng tích lũy {rule['nguong_tin_chi']} tín chỉ (chương trình 180 tín chỉ)"
        cite = [self._cite(doc_id, rule["can_cu"])]
        return {"nam_thu": nam, "giai_thich": nguong, "can_cu": cite}

    def kiem_tra_canh_bao(
        self,
        khoa: int,
        diem_trung_binh_hoc_ky: float | None = None,
        la_hoc_ky_dau: bool = False,
        tin_chi_dang_ky: int | None = None,
        tin_chi_khong_dat: int | None = None,
        tin_chi_no_dong: int | None = None,
        diem_trung_binh_tich_luy: float | None = None,
        trinh_do_nam: int | None = None,
    ) -> dict:
        doc_id, rule = self._rule(khoa, "canh_bao")
        reasons, checked = [], []
        if diem_trung_binh_hoc_ky is not None:
            limit = rule["gpa_hoc_ky_duoi"]["hoc_ky_dau" if la_hoc_ky_dau else "hoc_ky_khac"]
            checked.append("điểm trung bình học kỳ")
            if float(diem_trung_binh_hoc_ky) < limit:
                reasons.append(f"điểm trung bình học kỳ {diem_trung_binh_hoc_ky} dưới {limit}")
        if "ty_le_khong_dat_vuot" in rule and tin_chi_khong_dat is not None and tin_chi_dang_ky:
            checked.append("tỷ lệ tín chỉ không đạt")
            ratio = tin_chi_khong_dat / tin_chi_dang_ky
            if ratio > rule["ty_le_khong_dat_vuot"]:
                reasons.append(f"không đạt {tin_chi_khong_dat}/{tin_chi_dang_ky} tín chỉ = "
                               f"{ratio:.1%}, vượt {rule['ty_le_khong_dat_vuot']:.0%}")
        if "no_dong_vuot" in rule and tin_chi_no_dong is not None:
            checked.append("tín chỉ nợ đọng")
            if tin_chi_no_dong > rule["no_dong_vuot"]:
                reasons.append(f"nợ đọng {tin_chi_no_dong} tín chỉ, vượt {rule['no_dong_vuot']}")
        if "gpa_tich_luy_duoi" in rule and diem_trung_binh_tich_luy is not None:
            if trinh_do_nam is None:
                raise ToolError("Cần trình độ năm học để xét ngưỡng điểm trung bình tích lũy.")
            limits = rule["gpa_tich_luy_duoi"]
            limit = limits.get(int(trinh_do_nam), limits["cac_nam_sau"])
            checked.append("điểm trung bình tích lũy")
            if float(diem_trung_binh_tich_luy) < limit:
                reasons.append(f"điểm trung bình tích lũy {diem_trung_binh_tich_luy} dưới {limit}")
        if not checked:
            raise ToolError("Chưa có dữ liệu nào để xét cảnh báo học tập.")
        return {"bi_canh_bao": bool(reasons), "ly_do": reasons, "da_xet": checked,
                "can_cu": [self._cite(doc_id, rule["can_cu"])]}

    # ---- giao diện cho LLM --------------------------------------------------------------
    def call(self, name: str, args: dict) -> dict:
        if name not in TOOL_NAMES:
            return {"loi": f"Không có công cụ {name}."}
        try:
            return getattr(self, name)(**args)
        except ToolError as e:
            return {"loi": str(e)}
        except (TypeError, KeyError, ValueError) as e:
            return {"loi": f"Tham số không hợp lệ: {e}"}


def _obj(props: dict, required: list[str]) -> dict:
    return {"type": "OBJECT", "properties": props, "required": required}


_KHOA = {"type": "INTEGER", "description": "Khóa của sinh viên, ví dụ 68 cho K68"}
_NUM = {"type": "NUMBER"}
_INT = {"type": "INTEGER"}

FUNCTION_DECLARATIONS = [
    {"name": "tinh_diem_hoc_phan",
     "description": "Tính điểm học phần từ các điểm thành phần và trọng số, quy đổi điểm chữ.",
     "parameters": _obj({"khoa": _KHOA, "diem_thanh_phan": {"type": "ARRAY", "items": _obj(
         {"diem": _NUM, "trong_so": {"type": "NUMBER", "description": "0 đến 1"}},
         ["diem", "trong_so"])}}, ["khoa", "diem_thanh_phan"])},
    {"name": "quy_doi_diem",
     "description": "Quy đổi điểm học phần thang 10 sang điểm chữ và điểm số thang 4.",
     "parameters": _obj({"khoa": _KHOA, "diem_10": _NUM}, ["khoa", "diem_10"])},
    {"name": "tinh_diem_trung_binh",
     "description": "Tính điểm trung bình (học kỳ hoặc tích lũy) thang 4 có trọng số tín chỉ.",
     "parameters": _obj({"khoa": _KHOA, "hoc_phan": {"type": "ARRAY", "items": _obj(
         {"diem_10": _NUM, "diem_chu": {"type": "STRING"}, "tin_chi": _INT}, ["tin_chi"])}},
         ["khoa", "hoc_phan"])},
    {"name": "xep_loai_hoc_luc",
     "description": "Xếp loại học lực theo điểm trung bình thang 4.",
     "parameters": _obj({"khoa": _KHOA, "diem_trung_binh": _NUM}, ["khoa", "diem_trung_binh"])},
    {"name": "xep_hang_tot_nghiep",
     "description": "Xét điều kiện điểm và hạng tốt nghiệp, kể cả hạ hạng do học lại, kỷ luật.",
     "parameters": _obj({"khoa": _KHOA, "diem_trung_binh_tich_luy": _NUM,
                         "tin_chi_hoc_lai": _INT, "tong_tin_chi_chuong_trinh": _INT,
                         "bi_ky_luat_tu_canh_cao": {"type": "BOOLEAN"}},
                        ["khoa", "diem_trung_binh_tich_luy"])},
    {"name": "xep_trinh_do_nam",
     "description": "Xác định sinh viên năm thứ mấy theo số tín chỉ tích lũy.",
     "parameters": _obj({"khoa": _KHOA, "tin_chi_tich_luy": _INT,
                         "tin_chi_trung_binh_mot_nam": _NUM}, ["khoa", "tin_chi_tich_luy"])},
    {"name": "kiem_tra_canh_bao",
     "description": "Kiểm tra sinh viên có bị cảnh báo học tập không với dữ liệu đã biết.",
     "parameters": _obj({"khoa": _KHOA, "diem_trung_binh_hoc_ky": _NUM,
                         "la_hoc_ky_dau": {"type": "BOOLEAN"}, "tin_chi_dang_ky": _INT,
                         "tin_chi_khong_dat": _INT, "tin_chi_no_dong": _INT,
                         "diem_trung_binh_tich_luy": _NUM, "trinh_do_nam": _INT}, ["khoa"])},
]
TOOL_NAMES = {d["name"] for d in FUNCTION_DECLARATIONS}
