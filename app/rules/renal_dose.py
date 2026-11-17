"""Luật yếu tố 6: kiểm tra chỉnh liều theo chức năng thận (CrCl Cockcroft-Gault)."""

from pathlib import Path

from pydantic import BaseModel

from app.calc.renal import cockcroft_gault
from app.domain.loader import ingredients_of, latest_lab, latest_vital
from app.domain.models import CaBenh, KetQuaXetNghiem, SinhHieu
from app.rules.types import CanCu, PhatHien, normalize_text, pending_lines

_YEU_TO = 6


class RenalDoseTier(BaseModel):
    """Một mức CrCl và khuyến cáo chỉnh liều trong bảng luật thận."""

    crcl_tu: float | None = None
    crcl_den: float | None = None
    bao_gom_can_duoi: bool
    can_chinh: bool
    khuyen_cao: str


class RenalDrugRule(BaseModel):
    """Quy tắc chỉnh liều thận của một hoạt chất theo tên quốc tế."""

    ten_quoc_te: str
    nguon: str
    nguoi_duyet: str | None = None
    muc: list[RenalDoseTier]


class RenalRuleBook(BaseModel):
    """Tập quy tắc chỉnh liều theo chức năng thận nạp từ JSON."""

    phien_ban: str
    ghi_chu: str | None = None
    quy_tac: list[RenalDrugRule]


def load_renal_rules(path: Path) -> RenalRuleBook:
    """Đọc tệp JSON bảng quy tắc chỉnh liều theo chức năng thận."""
    raw = Path(path).read_text(encoding="utf-8")
    return RenalRuleBook.model_validate_json(raw)


def select_renal_tier(crcl: float, rule: RenalDrugRule) -> RenalDoseTier:
    """Chọn mức chỉnh liều theo CrCl (mL/min), không có khe hở giữa các mức."""
    if len(rule.muc) == 4 and rule.muc[0].crcl_tu == 50 and rule.muc[2].crcl_den == 25:
        if crcl > 50.0:
            return rule.muc[0]
        if crcl > 25.0:
            return rule.muc[1]
        if crcl >= 10.0:
            return rule.muc[2]
        return rule.muc[3]

    for tier in rule.muc:
        lower_ok = True
        if tier.crcl_tu is not None:
            lower_ok = crcl >= tier.crcl_tu if tier.bao_gom_can_duoi else crcl > tier.crcl_tu
        upper_ok = True
        if tier.crcl_den is not None:
            if tier.crcl_tu is None and not tier.bao_gom_can_duoi:
                upper_ok = crcl < tier.crcl_den
            else:
                upper_ok = crcl <= tier.crcl_den
        if lower_ok and upper_ok:
            return tier

    raise ValueError(f"Không tìm thấy mức CrCl phù hợp cho {rule.ten_quoc_te} (CrCl={crcl})")


def _available_data_evidence(
    creatinin_lab: KetQuaXetNghiem | None,
    weight_vital: SinhHieu | None,
) -> list[CanCu]:
    """Thu thập căn cứ dữ liệu đang có khi thiếu đầu vào hoặc số liệu bất thường."""
    evidences: list[CanCu] = []
    if creatinin_lab is not None:
        val = creatinin_lab.gia_tri_so if creatinin_lab.gia_tri_so is not None else "không rõ"
        unit = creatinin_lab.don_vi or "không rõ đơn vị"
        evidences.append(
            CanCu(
                loai="du_lieu",
                ban_ghi_id=creatinin_lab.xet_nghiem_id,
                mo_ta=(
                    f"Creatinin máu: {val} {unit} lúc {creatinin_lab.thoi_diem_ket_qua.isoformat()}"
                ),
            ),
        )
    if weight_vital is not None:
        evidences.append(
            CanCu(
                loai="du_lieu",
                ban_ghi_id=weight_vital.sinh_hieu_id,
                mo_ta=(
                    f"Cân nặng: {weight_vital.gia_tri} {weight_vital.don_vi} "
                    f"lúc {weight_vital.thoi_diem_do.isoformat()}"
                ),
            ),
        )
    return evidences


def check(ca: CaBenh, rules: RenalRuleBook) -> list[PhatHien]:
    """Kiểm tra nhu cầu chỉnh liều theo CrCl cho các hoạt chất nằm trong bảng luật."""
    rule_by_inn = {normalize_text(rule.ten_quoc_te): rule for rule in rules.quy_tac}
    weight_vital = latest_vital(ca, "can_nang")
    creatinin_lab = latest_lab(ca, "creatinin")

    can_nang_kg = weight_vital.gia_tri if weight_vital is not None else None
    creatinin_val = creatinin_lab.gia_tri_so if creatinin_lab is not None else None
    creatinin_unit = creatinin_lab.don_vi if creatinin_lab is not None else None

    findings: list[PhatHien] = []
    for line in pending_lines(ca):
        for hc in ingredients_of(ca, line):
            inn = normalize_text(hc.ten_quoc_te)
            if not inn or inn not in rule_by_inn:
                continue
            rule = rule_by_inn[inn]

            try:
                calc_res = cockcroft_gault(
                    tuoi=ca.nguoi_benh.tuoi,
                    gioi_tinh=ca.nguoi_benh.gioi_tinh,
                    can_nang_kg=can_nang_kg,
                    creatinin=creatinin_val,
                    creatinin_don_vi=creatinin_unit,
                    loai_can_nang="thuc_te",
                )
            except ValueError as exc:
                evidences = _available_data_evidence(creatinin_lab, weight_vital)
                evidences.append(
                    CanCu(loai="tinh_toan", ban_ghi_id="cockcroft_gault", mo_ta=str(exc)),
                )
                err_desc = f"Số liệu bất thường khi tính CrCl cho {hc.ten_hoat_chat}: {exc}"
                findings.append(
                    PhatHien(
                        ma_luat="lieu_than_so_lieu_bat_thuong",
                        yeu_to=_YEU_TO,
                        ket_luan="khong_du_du_lieu",
                        muc_do=None,
                        chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                        mo_ta=err_desc,
                        can_cu=evidences,
                        thong_tin_con_thieu=["so_lieu_hop_le"],
                    ),
                )
                continue

            if calc_res.ket_qua is None:
                evidences = _available_data_evidence(creatinin_lab, weight_vital)
                missing_text = ", ".join(calc_res.thieu_dau_vao)
                evidences.append(
                    CanCu(
                        loai="tinh_toan",
                        ban_ghi_id="cockcroft_gault",
                        mo_ta=f"Thiếu đầu vào: {missing_text}",
                    ),
                )
                missing_desc = f"Thiếu dữ liệu tính CrCl cho {hc.ten_hoat_chat}: {missing_text}"
                findings.append(
                    PhatHien(
                        ma_luat="lieu_than_thieu_du_lieu",
                        yeu_to=_YEU_TO,
                        ket_luan="khong_du_du_lieu",
                        muc_do=None,
                        chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                        mo_ta=missing_desc,
                        can_cu=evidences,
                        thong_tin_con_thieu=list(calc_res.thieu_dau_vao),
                    ),
                )
                continue

            assert creatinin_lab is not None
            assert weight_vital is not None
            crcl = calc_res.ket_qua
            tier = select_renal_tier(crcl, rule)
            crcl_display = f"{crcl:.1f}"

            can_cu = [
                CanCu(
                    loai="du_lieu",
                    ban_ghi_id=creatinin_lab.xet_nghiem_id,
                    mo_ta=(
                        f"Creatinin máu: {creatinin_lab.gia_tri_so} {creatinin_lab.don_vi} "
                        f"lúc {creatinin_lab.thoi_diem_ket_qua.isoformat()}"
                    ),
                ),
                CanCu(
                    loai="tinh_toan",
                    ban_ghi_id="cockcroft_gault",
                    mo_ta=(
                        f"CrCl = {crcl_display} mL/min "
                        f"(cân nặng thuc_te: {weight_vital.gia_tri} {weight_vital.don_vi})"
                    ),
                ),
                CanCu(loai="tai_lieu", ban_ghi_id=None, mo_ta=rule.nguon),
            ]

            if tier.can_chinh:
                findings.append(
                    PhatHien(
                        ma_luat="lieu_than_can_chinh",
                        yeu_to=_YEU_TO,
                        ket_luan="can_xem",
                        muc_do="nghiem_trong",
                        chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                        mo_ta=(
                            f"{hc.ten_hoat_chat}: CrCl = {crcl_display} mL/min, "
                            f"cần xem xét chỉnh liều thận ({tier.khuyen_cao})"
                        ),
                        can_cu=can_cu,
                    ),
                )
            else:
                findings.append(
                    PhatHien(
                        ma_luat="lieu_than_khong_can_chinh",
                        yeu_to=_YEU_TO,
                        ket_luan="dat",
                        muc_do="thong_tin",
                        chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                        mo_ta=(
                            f"{hc.ten_hoat_chat}: CrCl = {crcl_display} mL/min, "
                            f"không cần chỉnh liều thận ({tier.khuyen_cao})"
                        ),
                        can_cu=can_cu,
                    ),
                )

    return findings
