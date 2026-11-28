"""Công cụ tính chỉ số từ dữ liệu của ca hiện tại."""

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict

from app.agent.minh_hoa.models import BoDuLieu, CotDuLieu
from app.agent.tools.base import CanCu, KetQuaCongCu, Tool, ToolContext
from app.agent.tools.lay_du_lieu_ca import _format_number
from app.calc import (
    CONG_THUC_HIEN_THI,
    adjusted_body_weight,
    bmi,
    bsa_dubois,
    bsa_mosteller,
    cockcroft_gault,
    egfr_ckd_epi_2021,
    ibw_devine,
)
from app.calc.types import WeightType
from app.calc.units import creatinine_to_mg_dl
from app.domain.loader import latest_lab, latest_vital


class ThamSoTinhChiSo(BaseModel):
    """Chỉ cho phép chọn công thức và giả định cân nặng."""

    model_config = ConfigDict(extra="forbid")

    cong_thuc: Literal[
        "cockcroft_gault",
        "egfr_ckd_epi_2021",
        "bmi",
        "bsa_mosteller",
        "bsa_dubois",
        "ibw_devine",
        "adjusted_body_weight",
    ]
    can_nang: Literal["thuc_te", "ly_tuong", "hieu_chinh"] = "thuc_te"


_TEN = {
    "cockcroft_gault": "Cockcroft–Gault",
    "egfr_ckd_epi_2021": "eGFR CKD-EPI 2021",
    "bmi": "BMI",
    "bsa_mosteller": "BSA Mosteller",
    "bsa_dubois": "BSA Du Bois",
    "ibw_devine": "IBW Devine",
    "adjusted_body_weight": "Cân nặng hiệu chỉnh",
}
_CAN_NANG = {"thuc_te": "thực tế", "ly_tuong": "lý tưởng", "hieu_chinh": "hiệu chỉnh"}


class TinhChiSo(Tool):
    """Tính chỉ số bằng công thức sẵn có, không nhận số từ LLM."""

    ten: ClassVar[str] = "tinh_chi_so"
    ten_hien_thi: ClassVar[str] = "Tính chỉ số"
    mo_ta: ClassVar[str] = (
        "Tính chỉ số từ ca hiện tại; chỉ chọn công thức và giả định cân nặng, không truyền số."
    )
    LuocDoThamSo: ClassVar[type[BaseModel]] = ThamSoTinhChiSo
    che_do_cho_phep: ClassVar[frozenset[str]] = frozenset({"ca"})
    goi_ra_ngoai: ClassVar[bool] = False
    thoi_gian_toi_da: ClassVar[float] = 5.0

    def chay(self, tham_so: BaseModel, ctx: ToolContext) -> KetQuaCongCu:
        assert isinstance(tham_so, ThamSoTinhChiSo)
        if ctx.ca is None:
            return KetQuaCongCu(
                trang_thai="loi", ma_loi="sai_tham_so", noi_dung="Chỉ dùng trong chế độ ca."
            )
        if tham_so.cong_thuc != "cockcroft_gault" and tham_so.can_nang != "thuc_te":
            return KetQuaCongCu(
                trang_thai="loi",
                ma_loi="sai_tham_so",
                noi_dung="Giả định cân nặng chỉ áp dụng cho Cockcroft–Gault.",
            )

        ca = ctx.ca
        weight = latest_vital(ca, "can_nang")
        height = latest_vital(ca, "chieu_cao")
        lab = latest_lab(ca, "creatinin")
        can_nang = weight.gia_tri if weight is not None else None
        chieu_cao = height.gia_tri if height is not None else None
        creatinin = lab.gia_tri_so if lab is not None else None
        don_vi = lab.don_vi if lab is not None else None
        tuoi, gioi_tinh = ca.nguoi_benh.tuoi, ca.nguoi_benh.gioi_tinh
        try:
            match tham_so.cong_thuc:
                case "cockcroft_gault":
                    result = cockcroft_gault(
                        tuoi,
                        gioi_tinh,
                        can_nang,
                        creatinin,
                        don_vi,
                        loai_can_nang=tham_so.can_nang,
                        chieu_cao_cm=chieu_cao if tham_so.can_nang != "thuc_te" else None,
                    )
                case "egfr_ckd_epi_2021":
                    result = egfr_ckd_epi_2021(tuoi, gioi_tinh, creatinin, don_vi)
                case "bmi":
                    result = bmi(can_nang, chieu_cao)
                case "bsa_mosteller":
                    result = bsa_mosteller(can_nang, chieu_cao)
                case "bsa_dubois":
                    result = bsa_dubois(can_nang, chieu_cao)
                case "ibw_devine":
                    result = ibw_devine(gioi_tinh, chieu_cao)
                case "adjusted_body_weight":
                    result = adjusted_body_weight(gioi_tinh, chieu_cao, can_nang)
        except ValueError as exc:
            message = str(exc)
            fields = ("tuoi", "gioi_tinh", "can_nang_kg", "chieu_cao_cm", "creatinin")
            field = next((name for name in fields if f"Tham số {name} " in message), None)
            field = field or ("creatinin_don_vi" if "Đơn vị creatinin" in message else "đầu vào")
            return KetQuaCongCu(
                trang_thai="khong_co",
                noi_dung=f"Giá trị {field} ngoài khoảng hợp lệ.",
                chi_tiet_tien_trinh="Đầu vào không hợp lệ",
            )

        if result.thieu_dau_vao:
            return KetQuaCongCu(
                trang_thai="khong_co",
                noi_dung=(
                    f"Chưa tính được {tham_so.cong_thuc}: thiếu đầu vào "
                    f"{', '.join(result.thieu_dau_vao)}. Có thể xem dữ liệu ca để bổ sung."
                ),
                chi_tiet_tien_trinh="Thiếu đầu vào",
            )

        assert result.ket_qua is not None
        inputs = []
        if tham_so.cong_thuc in (
            "cockcroft_gault",
            "egfr_ckd_epi_2021",
            "ibw_devine",
            "adjusted_body_weight",
        ):
            inputs.append(f"gioi_tinh: {gioi_tinh} (giới tính)")
        for item in result.dau_vao:
            unit = item.don_vi.strip().lower() if item.ten == "creatinin" else item.don_vi
            inputs.append(f"{item.ten}: {_format_number(item.gia_tri)} {unit}")
        notes = list(result.ghi_chu)
        if tham_so.cong_thuc == "cockcroft_gault" and notes:
            # Hàm tính trả cân nặng chưa làm tròn trong ghi chú; chỉ định dạng khi hiển thị.
            prefix, _, weight_text = notes[0].partition(": ")
            value, _, _ = weight_text.partition(" kg")
            notes[0] = f"{prefix}: {_format_number(round(float(value), 2))} kg"
        ma = f"tinh:{tham_so.cong_thuc}:{tham_so.can_nang}"
        nhan = _TEN[tham_so.cong_thuc]
        if tham_so.cong_thuc == "cockcroft_gault":
            nhan += f" · cân nặng {_CAN_NANG[tham_so.can_nang]}"
        noi_dung = (
            f"[{ma}] {nhan}; kết quả: {_format_number(round(result.ket_qua, 2))} {result.don_vi} "
            f"(làm tròn 2 chữ số thập phân); đầu vào: {'; '.join(inputs)}; "
            f"công thức: {CONG_THUC_HIEN_THI[result.cong_thuc]}; "
            f"ghi chú: {'; '.join(notes) if notes else 'không có'}; "
            f"tham khảo: {result.tham_khao}; kết quả do code tính, không phải kết luận cho ca."
        )
        row: dict[str, str | float | bool | None] = {"gia_tri": result.ket_qua}
        columns = [CotDuLieu(ten="gia_tri", kieu="dinh_luong", don_vi=result.don_vi)]
        for item in result.dau_vao:
            row[item.ten] = item.gia_tri
            columns.append(CotDuLieu(ten=item.ten, kieu="dinh_luong", don_vi=item.don_vi))
        if tham_so.cong_thuc in (
            "cockcroft_gault",
            "egfr_ckd_epi_2021",
            "ibw_devine",
            "adjusted_body_weight",
        ):
            row["gioi_tinh"] = gioi_tinh
            columns.append(CotDuLieu(ten="gioi_tinh", kieu="danh_muc"))
        datasets = [BoDuLieu(ma="", cot=columns, dong=[row], can_cu=[ma])]
        if tham_so.cong_thuc == "cockcroft_gault":
            assert creatinin is not None and don_vi is not None
            factor = creatinine_to_mg_dl(1.0, "umol/L")
            case_umol = creatinine_to_mg_dl(creatinin, don_vi) / factor
            low, high = max(30.0, case_umol / 2), min(800.0, case_umol * 2)
            values = {low + 5 * i for i in range(max(0, int((high - low) / 5) + 1))}
            values.add(case_umol)
            weights: tuple[WeightType, ...] = ("thuc_te", "ly_tuong", "hieu_chinh")
            grid: list[dict[str, str | float | bool | None]] = []
            for value in sorted(values):
                converted = value * factor if don_vi.strip().lower() == "mg/dl" else value
                if value == case_umol:
                    converted = creatinin
                for weight_type in weights:
                    try:
                        computed = cockcroft_gault(
                            tuoi,
                            gioi_tinh,
                            can_nang,
                            converted,
                            don_vi,
                            loai_can_nang=weight_type,
                            chieu_cao_cm=chieu_cao,
                        )
                    except ValueError:
                        continue
                    if computed.ket_qua is not None:
                        grid.append(
                            {
                                "creatinin": converted,
                                "loai_can_nang": weight_type,
                                "crcl": computed.ket_qua,
                            }
                        )
            grid_columns = [
                CotDuLieu(ten="creatinin", kieu="dinh_luong", don_vi=don_vi),
                CotDuLieu(ten="loai_can_nang", kieu="danh_muc"),
                CotDuLieu(ten="crcl", kieu="dinh_luong", don_vi=result.don_vi),
            ]
            datasets.append(BoDuLieu(ma="", cot=grid_columns, dong=grid, can_cu=[ma]))
            datasets.append(
                BoDuLieu(
                    ma="",
                    cot=grid_columns,
                    dong=[
                        {
                            "creatinin": creatinin,
                            "loai_can_nang": tham_so.can_nang,
                            "crcl": result.ket_qua,
                        }
                    ],
                    can_cu=[ma],
                )
            )
        return KetQuaCongCu(
            trang_thai="ok",
            noi_dung=noi_dung,
            can_cu=[CanCu(loai="tinh", ma=ma, nhan=nhan, noi_dung=noi_dung)],
            bo_du_lieu=datasets,
            chi_tiet_tien_trinh="Một chỉ số",
        )
