"""Luật yếu tố 6: kiểm tra ngưỡng xét nghiệm theo nhãn FDA có quy đổi đơn vị."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from app.calc.renal import egfr_ckd_epi_2021
from app.domain.loader import latest_lab
from app.domain.models import CaBenh, KetQuaXetNghiem
from app.rules.d4_config import (
    LabCondition,
    LabThresholdConfig,
    LabThresholdRule,
    dedupe_evidences,
    display_name_for_ids,
    extract_resolved_ids,
    format_fda_source_evidence,
    is_line_excluded,
    rule_ingredient_key,
    try_load_default_lab_threshold_config,
)
from app.rules.types import CanCu, PhatHien, normalize_text, pending_lines

if TYPE_CHECKING:
    from app.kb.resolver import DrugResolver

_YEU_TO = 6
_WS_RE = re.compile(r"\s+")
_EGFR_INPUT_MISSING_KEYS = frozenset({"tuoi", "gioi_tinh", "creatinin_don_vi", "so_lieu_hop_le"})
_SEVERITY_ORDER: dict[Literal["nghiem_trong", "can_luu_y"], int] = {
    "nghiem_trong": 2,
    "can_luu_y": 1,
}


@dataclass(frozen=True)
class _ConditionEval:
    """Kết quả đánh giá một điều kiện xét nghiệm đơn lẻ."""

    cond: LabCondition
    lab: KetQuaXetNghiem | None
    converted_value: float | None
    satisfied: bool | None
    missing_keys: tuple[str, ...] = ()
    source_lab: KetQuaXetNghiem | None = None
    estimated_egfr: float | None = None
    calc_error: str | None = None


@dataclass(frozen=True)
class _RuleEval:
    """Kết quả đánh giá một dòng trong bảng ngưỡng xét nghiệm."""

    rule: LabThresholdRule
    status: Literal["canh_bao", "dat", "thieu"]
    cond_evals: tuple[_ConditionEval, ...]


def _normalize_unit(unit: str | None) -> str:
    """Chuẩn hoá đơn vị: bỏ mọi khoảng trắng, chữ thường, đồng nhất ký hiệu micro."""
    if unit is None:
        return ""
    cleaned = _WS_RE.sub("", unit).lower()
    return cleaned.replace("µ", "u").replace("μ", "u")


def _format_number(value: float) -> str:
    """Định dạng số cho văn bản hiển thị, không làm tròn trong bước so sánh."""
    if value == 0.0 or abs(value) >= 0.01:
        text = f"{value:.3f}".rstrip("0").rstrip(".")
        return "0" if text == "-0" else text
    return f"{value:g}"


def _compare_threshold(value: float, cond: LabCondition) -> bool:
    """So sánh giá trị đã quy đổi với ngưỡng theo toán tử của điều kiện."""
    if cond.toan_tu == "<":
        return value < cond.gia_tri
    if cond.toan_tu == "<=":
        return value <= cond.gia_tri
    if cond.toan_tu == ">":
        return value > cond.gia_tri
    if cond.toan_tu == ">=":
        return value >= cond.gia_tri
    if cond.gia_tri_den is None:
        raise ValueError(f"Toán tử khoang thiếu gia_tri_den cho {cond.ma_xet_nghiem}")
    return cond.gia_tri <= value <= cond.gia_tri_den


def _format_threshold(cond: LabCondition) -> str:
    """Biểu diễn ngưỡng điều kiện thành chuỗi dễ đọc cho dược sĩ."""
    if cond.toan_tu == "khoang":
        hi = _format_number(cond.gia_tri_den) if cond.gia_tri_den is not None else "?"
        return f"{_format_number(cond.gia_tri)}–{hi}"
    return f"{cond.toan_tu} {_format_number(cond.gia_tri)}"


def _evaluate_estimated_egfr(
    ca: CaBenh,
    cond: LabCondition,
    existing_lab: KetQuaXetNghiem | None,
) -> _ConditionEval:
    """Ước tính eGFR theo CKD-EPI 2021 từ creatinin mới nhất khi ca không có eGFR."""
    creat_lab = latest_lab(ca, "creatinin")
    if creat_lab is None or creat_lab.gia_tri_so is None:
        return _ConditionEval(
            cond=cond,
            lab=existing_lab,
            converted_value=None,
            satisfied=None,
            missing_keys=(cond.ma_xet_nghiem,),
        )

    try:
        calc_res = egfr_ckd_epi_2021(
            tuoi=ca.nguoi_benh.tuoi,
            gioi_tinh=ca.nguoi_benh.gioi_tinh,
            creatinin=creat_lab.gia_tri_so,
            creatinin_don_vi=creat_lab.don_vi,
        )
    except ValueError as exc:
        return _ConditionEval(
            cond=cond,
            lab=existing_lab,
            converted_value=None,
            satisfied=None,
            missing_keys=("so_lieu_hop_le",),
            source_lab=creat_lab,
            calc_error=str(exc),
        )

    if calc_res.ket_qua is None:
        return _ConditionEval(
            cond=cond,
            lab=existing_lab,
            converted_value=None,
            satisfied=None,
            missing_keys=tuple(calc_res.thieu_dau_vao),
            source_lab=creat_lab,
        )

    factor = float(cond.he_so_ca_sang_nhan) if cond.he_so_ca_sang_nhan is not None else 1.0
    converted = float(calc_res.ket_qua) * factor
    satisfied = _compare_threshold(converted, cond)
    return _ConditionEval(
        cond=cond,
        lab=existing_lab,
        converted_value=converted,
        satisfied=satisfied,
        source_lab=creat_lab,
        estimated_egfr=float(calc_res.ket_qua),
    )


def _evaluate_condition(ca: CaBenh, cond: LabCondition) -> _ConditionEval:
    """Đọc xét nghiệm mới nhất của ca, quy đổi đơn vị và so sánh với ngưỡng."""
    lab = latest_lab(ca, cond.ma_xet_nghiem)
    if lab is None or lab.gia_tri_so is None:
        if cond.ma_xet_nghiem == "egfr":
            return _evaluate_estimated_egfr(ca, cond, lab)
        return _ConditionEval(
            cond=cond,
            lab=lab,
            converted_value=None,
            satisfied=None,
            missing_keys=(cond.ma_xet_nghiem,),
        )

    if cond.he_so_ca_sang_nhan is None:
        return _ConditionEval(
            cond=cond,
            lab=lab,
            converted_value=None,
            satisfied=None,
            missing_keys=(f"{cond.ma_xet_nghiem}_don_vi",),
        )

    # don_vi_ca rỗng kèm hệ số có số nghĩa là xét nghiệm không đơn vị (ví dụ INR).
    if _normalize_unit(lab.don_vi) != _normalize_unit(cond.don_vi_ca):
        return _ConditionEval(
            cond=cond,
            lab=lab,
            converted_value=None,
            satisfied=None,
            missing_keys=(f"{cond.ma_xet_nghiem}_don_vi",),
        )

    converted = float(lab.gia_tri_so) * float(cond.he_so_ca_sang_nhan)
    satisfied = _compare_threshold(converted, cond)
    return _ConditionEval(
        cond=cond,
        lab=lab,
        converted_value=converted,
        satisfied=satisfied,
    )


def _evaluate_rule_row(ca: CaBenh, rule: LabThresholdRule) -> _RuleEval:
    """Đánh giá một dòng quy tắc theo kieu_dieu_kien."""
    evals = tuple(_evaluate_condition(ca, cond) for cond in rule.dieu_kien)
    if not evals or any(ev.satisfied is None for ev in evals):
        return _RuleEval(rule=rule, status="thieu", cond_evals=evals)

    all_ok = all(bool(ev.satisfied) for ev in evals)
    if rule.kieu_dieu_kien == "canh_bao_khi_thoa":
        status: Literal["canh_bao", "dat"] = "canh_bao" if all_ok else "dat"
    elif rule.kieu_dieu_kien == "canh_bao_khi_ngoai_khoang":
        status = "dat" if all_ok else "canh_bao"
    else:
        # dieu_kien_khoi_dau
        status = "dat" if all_ok else "canh_bao"
    return _RuleEval(rule=rule, status=status, cond_evals=evals)


def _lab_data_evidence(lab: KetQuaXetNghiem) -> CanCu:
    """Tạo căn cứ dữ liệu từ một bản ghi xét nghiệm của ca."""
    val = lab.gia_tri_so if lab.gia_tri_so is not None else (lab.gia_tri_text or "không rõ")
    unit = f" {lab.don_vi}" if lab.don_vi else ""
    return CanCu(
        loai="du_lieu",
        ban_ghi_id=lab.xet_nghiem_id,
        mo_ta=(
            f"{lab.ten_xet_nghiem} ({lab.ma_xet_nghiem}): {val}{unit} "
            f"lúc {lab.thoi_diem_ket_qua.isoformat()}"
        ),
    )


def _format_estimated_egfr_source(ev: _ConditionEval, ca: CaBenh) -> str:
    """Tạo đoạn mô tả nguồn số liệu cho eGFR ước tính theo CKD-EPI 2021."""
    assert ev.estimated_egfr is not None
    assert ev.source_lab is not None
    assert ev.source_lab.gia_tri_so is not None
    creat_unit = f" {ev.source_lab.don_vi}" if ev.source_lab.don_vi else ""
    creat_str = f"{_format_number(ev.source_lab.gia_tri_so)}{creat_unit}"
    sex_label = "nam" if ca.nguoi_benh.gioi_tinh == "nam" else "nữ"
    return (
        f"eGFR ước tính {ev.estimated_egfr:.1f} mL/phút/1,73 m² "
        f"(CKD-EPI 2021 từ creatinin {creat_str}, {sex_label} {ca.nguoi_benh.tuoi} tuổi)"
    )


def _estimated_egfr_evidence(ev: _ConditionEval, ca: CaBenh) -> CanCu:
    """Tạo căn cứ tính toán cho eGFR ước tính từ creatinin."""
    return CanCu(
        loai="tinh_toan",
        ban_ghi_id="egfr_ckd_epi_2021",
        mo_ta=_format_estimated_egfr_source(ev, ca),
    )


def _format_condition_summary(ev: _ConditionEval, rule: LabThresholdRule, ca: CaBenh) -> str:
    """Tạo đoạn mô tả giá trị ca, giá trị đã quy đổi và ngưỡng điều kiện."""
    assert ev.converted_value is not None
    label_unit_raw = ev.cond.don_vi_nhan if ev.cond.don_vi_nhan is not None else rule.don_vi_nhan
    label_unit = f" {label_unit_raw}" if label_unit_raw else ""
    threshold_str = f"{_format_threshold(ev.cond)}{label_unit}"

    if ev.estimated_egfr is not None and ev.source_lab is not None:
        source_text = _format_estimated_egfr_source(ev, ca)
        if ev.cond.he_so_ca_sang_nhan is not None and float(ev.cond.he_so_ca_sang_nhan) != 1.0:
            conv_str = f"{_format_number(ev.converted_value)}{label_unit}"
            return f"{source_text} -> quy đổi {conv_str} (ngưỡng {threshold_str})"
        return f"{source_text} (ngưỡng {threshold_str})"

    assert ev.lab is not None
    assert ev.lab.gia_tri_so is not None
    case_unit = f" {ev.lab.don_vi}" if ev.lab.don_vi else ""
    case_str = f"{_format_number(ev.lab.gia_tri_so)}{case_unit}"
    conv_str = f"{_format_number(ev.converted_value)}{label_unit}"
    return f"{ev.cond.ma_xet_nghiem}: {case_str} -> quy đổi {conv_str} (ngưỡng {threshold_str})"


def _success_evidences_from_evals(evals: list[_RuleEval], ca: CaBenh) -> list[CanCu]:
    """Thu thập căn cứ dữ liệu và tính toán từ các dòng quy tắc đã đánh giá xong."""
    evidences: list[CanCu] = []
    for item in evals:
        for ev in item.cond_evals:
            if ev.lab is not None:
                evidences.append(_lab_data_evidence(ev.lab))
            if ev.source_lab is not None:
                evidences.append(_lab_data_evidence(ev.source_lab))
            if ev.estimated_egfr is not None:
                evidences.append(_estimated_egfr_evidence(ev, ca))
    return evidences


def _doc_evidences_from_evals(evals: list[_RuleEval]) -> list[CanCu]:
    """Gộp căn cứ tài liệu từ danh sách dòng quy tắc đã đánh giá."""
    return dedupe_evidences(
        [format_fda_source_evidence(src) for item in evals for src in item.rule.nguon_chi_tiet]
    )


def _group_lab_rules(
    rules: tuple[LabThresholdRule, ...],
) -> list[tuple[frozenset[str], list[LabThresholdRule]]]:
    """Lọc bỏ dòng thiếu kieu_dieu_kien và gom nhóm theo tập hoạt chất."""
    grouped: dict[frozenset[str], list[LabThresholdRule]] = {}
    for rule in rules:
        if rule.kieu_dieu_kien is None:
            continue
        key = rule_ingredient_key(rule.hoat_chat_ids, rule.ten_quoc_te)
        if not key:
            continue
        grouped.setdefault(key, []).append(rule)
    return list(grouped.items())


def check(
    ca: CaBenh,
    resolver: DrugResolver | None = None,
    config: LabThresholdConfig | None = None,
) -> list[PhatHien]:
    """Kiểm tra ngưỡng xét nghiệm theo nhãn cho từng (dòng y lệnh, hoạt chất)."""
    if resolver is None:
        return []
    active_config = config if config is not None else try_load_default_lab_threshold_config()
    if active_config is None or not active_config.quy_tac:
        return []

    grouped_rules = _group_lab_rules(active_config.quy_tac)
    if not grouped_rules:
        return []

    findings: list[PhatHien] = []
    for line in pending_lines(ca):
        resolved = resolver.resolve_line(ca, line)
        if is_line_excluded(resolved):
            continue
        line_ids = {normalize_text(item) for item in extract_resolved_ids(resolved)}
        if not line_ids:
            continue

        line_id = line.chi_tiet_y_lenh_id
        for key, group_rules in grouped_rules:
            if not (key & line_ids):
                continue

            drug_name = display_name_for_ids(resolved, key, group_rules[0].ten_quoc_te)
            row_evals = [_evaluate_rule_row(ca, rule) for rule in group_rules]
            warning_evals = [item for item in row_evals if item.status == "canh_bao"]
            missing_evals = [item for item in row_evals if item.status == "thieu"]

            if warning_evals:
                chosen_sev: Literal["nghiem_trong", "can_luu_y"] = "can_luu_y"
                details: list[str] = []
                for item in warning_evals:
                    row_sev: Literal["nghiem_trong", "can_luu_y"] = (
                        item.rule.muc_do_de_xuat or "can_luu_y"
                    )
                    if item.rule.dieu_kien_khac:
                        row_sev = "can_luu_y"
                    if _SEVERITY_ORDER[row_sev] > _SEVERITY_ORDER[chosen_sev]:
                        chosen_sev = row_sev

                    cond_texts = ", ".join(
                        _format_condition_summary(ev, item.rule, ca) for ev in item.cond_evals
                    )
                    extra = (
                        f"; cần đối chiếu thêm: {item.rule.dieu_kien_khac}"
                        if item.rule.dieu_kien_khac
                        else ""
                    )
                    details.append(f"{cond_texts} -> {item.rule.hanh_dong_nhan}{extra}")

                data_evidences = _success_evidences_from_evals(warning_evals, ca)
                findings.append(
                    PhatHien(
                        ma_luat="xet_nghiem_vuot_nguong",
                        yeu_to=_YEU_TO,
                        ket_luan="can_xem",
                        muc_do=chosen_sev,
                        chi_tiet_y_lenh_id=[line_id],
                        mo_ta=f"{drug_name}: {'; '.join(details)}",
                        can_cu=dedupe_evidences(
                            [*data_evidences, *_doc_evidences_from_evals(warning_evals)]
                        ),
                    )
                )
                continue

            if missing_evals:
                missing_keys: list[str] = []
                data_evidences = []
                for item in missing_evals:
                    for ev in item.cond_evals:
                        if ev.lab is not None:
                            data_evidences.append(_lab_data_evidence(ev.lab))
                        if ev.source_lab is not None:
                            data_evidences.append(_lab_data_evidence(ev.source_lab))
                        if ev.lab is None and ev.source_lab is None:
                            data_evidences.append(
                                CanCu(
                                    loai="du_lieu",
                                    ban_ghi_id=None,
                                    mo_ta=f"Thiếu kết quả xét nghiệm {ev.cond.ma_xet_nghiem}",
                                )
                            )
                        if ev.calc_error is not None:
                            data_evidences.append(
                                CanCu(
                                    loai="tinh_toan",
                                    ban_ghi_id="egfr_ckd_epi_2021",
                                    mo_ta=ev.calc_error,
                                )
                            )
                        elif ev.source_lab is not None and ev.missing_keys:
                            data_evidences.append(
                                CanCu(
                                    loai="tinh_toan",
                                    ban_ghi_id="egfr_ckd_epi_2021",
                                    mo_ta=(
                                        "Không tính được eGFR CKD-EPI 2021 do thiếu: "
                                        f"{', '.join(ev.missing_keys)}"
                                    ),
                                )
                            )
                        for key_name in ev.missing_keys:
                            if key_name not in missing_keys:
                                missing_keys.append(key_name)

                has_egfr_calc_gap = any(
                    key_name in _EGFR_INPUT_MISSING_KEYS for key_name in missing_keys
                )
                missing_msg = (
                    f"{drug_name}: thiếu dữ liệu để tính eGFR hoặc xét nghiệm "
                    f"({', '.join(missing_keys)})"
                    if has_egfr_calc_gap
                    else (
                        f"{drug_name}: thiếu hoặc chưa quy đổi được đơn vị xét nghiệm "
                        f"({', '.join(missing_keys)})"
                    )
                )
                findings.append(
                    PhatHien(
                        ma_luat="xet_nghiem_thieu",
                        yeu_to=_YEU_TO,
                        ket_luan="khong_du_du_lieu",
                        muc_do=None,
                        chi_tiet_y_lenh_id=[line_id],
                        mo_ta=missing_msg,
                        can_cu=dedupe_evidences(
                            [*data_evidences, *_doc_evidences_from_evals(missing_evals)]
                        ),
                        thong_tin_con_thieu=missing_keys,
                    )
                )
                continue

            data_evidences = _success_evidences_from_evals(row_evals, ca)
            summary = "; ".join(
                ", ".join(_format_condition_summary(ev, item.rule, ca) for ev in item.cond_evals)
                for item in row_evals
            )
            findings.append(
                PhatHien(
                    ma_luat="xet_nghiem_trong_nguong",
                    yeu_to=_YEU_TO,
                    ket_luan="dat",
                    muc_do="thong_tin",
                    chi_tiet_y_lenh_id=[line_id],
                    mo_ta=f"{drug_name}: xét nghiệm trong ngưỡng cho phép ({summary})",
                    can_cu=dedupe_evidences(
                        [*data_evidences, *_doc_evidences_from_evals(row_evals)]
                    ),
                )
            )

    return findings
