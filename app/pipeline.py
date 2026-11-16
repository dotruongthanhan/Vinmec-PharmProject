"""Đường chạy (pipeline) thẩm định một ca bệnh: tính chỉ số và chạy bộ luật."""

import time
from collections.abc import Callable

from pydantic import BaseModel

from app.calc import CalcResult, bmi, bsa_mosteller, cockcroft_gault, egfr_ckd_epi_2021
from app.domain.loader import latest_lab, latest_vital
from app.domain.models import CaBenh, KetQuaXetNghiem, SinhHieu
from app.rules import PhatHien, RenalRuleBook, run_rules

_CALC_VERSION = "1.0"


class KetQuaThamDinh(BaseModel):
    """Kết quả tổng hợp sau khi chạy đường chạy thẩm định cho một ca bệnh."""

    ca_id: str
    chi_so: list[CalcResult]
    phat_hien: list[PhatHien]
    thoi_gian_ms: float


def _safe_calc(
    cong_thuc: str,
    don_vi: str,
    tham_khao: str,
    fn: Callable[[], CalcResult],
) -> CalcResult:
    """Chạy hàm tính công thức và bắt ValueError thành CalcResult không có giá trị."""
    try:
        return fn()
    except ValueError as exc:
        return CalcResult(
            cong_thuc=cong_thuc,
            phien_ban=_CALC_VERSION,
            ket_qua=None,
            don_vi=don_vi,
            dau_vao=[],
            thieu_dau_vao=["so_lieu_hop_le"],
            ghi_chu=[str(exc)],
            tham_khao=tham_khao,
        )


def _attach_provenance(
    result: CalcResult,
    weight_vital: SinhHieu | None,
    height_vital: SinhHieu | None,
    creatinin_lab: KetQuaXetNghiem | None,
) -> CalcResult:
    """Bổ sung mã bản ghi và thời điểm nguồn cho từng đầu vào trong CalcResult."""
    if not result.dau_vao:
        return result

    updated_inputs = []
    for item in result.dau_vao:
        if item.ten == "creatinin" and creatinin_lab is not None:
            updated_inputs.append(
                item.model_copy(
                    update={
                        "ban_ghi_id": creatinin_lab.xet_nghiem_id,
                        "thoi_diem": creatinin_lab.thoi_diem_ket_qua,
                    },
                ),
            )
        elif item.ten == "can_nang_kg" and weight_vital is not None:
            updated_inputs.append(
                item.model_copy(
                    update={
                        "ban_ghi_id": weight_vital.sinh_hieu_id,
                        "thoi_diem": weight_vital.thoi_diem_do,
                    },
                ),
            )
        elif item.ten == "chieu_cao_cm" and height_vital is not None:
            updated_inputs.append(
                item.model_copy(
                    update={
                        "ban_ghi_id": height_vital.sinh_hieu_id,
                        "thoi_diem": height_vital.thoi_diem_do,
                    },
                ),
            )
        else:
            updated_inputs.append(item)

    return result.model_copy(update={"dau_vao": updated_inputs})


def run_case(ca: CaBenh, renal_rules: RenalRuleBook) -> KetQuaThamDinh:
    """Chạy tính 4 chỉ số lâm sàng và bộ luật v0 cho một ca bệnh."""
    start = time.perf_counter()

    weight_vital = latest_vital(ca, "can_nang")
    height_vital = latest_vital(ca, "chieu_cao")
    creatinin_lab = latest_lab(ca, "creatinin")

    tuoi = ca.nguoi_benh.tuoi
    gioi_tinh = ca.nguoi_benh.gioi_tinh
    can_nang_kg = weight_vital.gia_tri if weight_vital is not None else None
    chieu_cao_cm = height_vital.gia_tri if height_vital is not None else None
    creatinin = creatinin_lab.gia_tri_so if creatinin_lab is not None else None
    creatinin_don_vi = creatinin_lab.don_vi if creatinin_lab is not None else None

    raw_results = [
        _safe_calc(
            cong_thuc="cockcroft_gault",
            don_vi="mL/min",
            tham_khao="Cockcroft DW, Gault MH. Nephron 1976;16:31-41.",
            fn=lambda: cockcroft_gault(
                tuoi=tuoi,
                gioi_tinh=gioi_tinh,
                can_nang_kg=can_nang_kg,
                creatinin=creatinin,
                creatinin_don_vi=creatinin_don_vi,
                loai_can_nang="thuc_te",
            ),
        ),
        _safe_calc(
            cong_thuc="egfr_ckd_epi_2021",
            don_vi="mL/min/1.73m2",
            tham_khao="Inker LA, et al. N Engl J Med 2021;385:1737-1749.",
            fn=lambda: egfr_ckd_epi_2021(
                tuoi=tuoi,
                gioi_tinh=gioi_tinh,
                creatinin=creatinin,
                creatinin_don_vi=creatinin_don_vi,
            ),
        ),
        _safe_calc(
            cong_thuc="bmi",
            don_vi="kg/m2",
            tham_khao="WHO. Body mass index (BMI).",
            fn=lambda: bmi(can_nang_kg=can_nang_kg, chieu_cao_cm=chieu_cao_cm),
        ),
        _safe_calc(
            cong_thuc="bsa_mosteller",
            don_vi="m2",
            tham_khao="Mosteller RD. N Engl J Med 1987;317:1098.",
            fn=lambda: bsa_mosteller(can_nang_kg=can_nang_kg, chieu_cao_cm=chieu_cao_cm),
        ),
    ]

    chi_so = [
        _attach_provenance(res, weight_vital, height_vital, creatinin_lab) for res in raw_results
    ]
    phat_hien = run_rules(ca, renal_rules)
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    return KetQuaThamDinh(
        ca_id=ca.ca_id,
        chi_so=chi_so,
        phat_hien=phat_hien,
        thoi_gian_ms=elapsed_ms,
    )
