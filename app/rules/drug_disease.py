"""Luật yếu tố 6: sàng lọc tương tác thuốc – bệnh DDInter 2.0 theo mã ICD-10."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Literal

from app.domain.models import CaBenh, ChanDoan
from app.rules.d4_config import (
    DDInterSeverity,
    DrugDiseaseConfig,
    DrugDiseasePair,
    dedupe_evidences,
    extract_resolved_ids,
    is_line_excluded,
    try_load_default_drug_disease_config,
)
from app.rules.types import CanCu, PhatHien, line_label, normalize_text, pending_lines

if TYPE_CHECKING:
    from app.kb.resolver import DrugResolver

_YEU_TO = 6
_WS_RE = re.compile(r"\s+")
_DDINTER_LICENSE = "DDInter 2.0, CC BY-NC-SA 4.0, chỉ dùng sàng lọc, chờ dược sĩ duyệt"
_LEVEL_MAP: dict[DDInterSeverity, Literal["nghiem_trong", "can_luu_y", "thong_tin"]] = {
    "Major": "nghiem_trong",
    "Moderate": "can_luu_y",
    "Minor": "thong_tin",
}


def _norm_icd(code: str | None) -> str:
    """Chuẩn hoá mã ICD-10: bỏ mọi khoảng trắng và chuyển chữ hoa."""
    if code is None:
        return ""
    return _WS_RE.sub("", code).upper()


def icd_matches(case_code_raw: str | None, pattern_raw: str) -> bool:
    """So khớp mã ICD-10 của ca với một mục mã đơn, thập phân hoặc khoảng."""
    case_code = _norm_icd(case_code_raw)
    target = _norm_icd(pattern_raw)
    if not case_code or not target:
        return False

    if "-" in target:
        start, end = target.split("-", 1)
        if len(start) >= 3 and len(end) >= 3 and len(case_code) >= 3:
            return start[:3] <= case_code[:3] <= end[:3]
        return False

    if "." in target:
        return case_code.startswith(target)

    if len(target) == 3:
        return len(case_code) >= 3 and case_code[:3] == target

    return case_code.startswith(target)


def _pair_matches_diagnosis(pair: DrugDiseasePair, cd: ChanDoan) -> bool:
    """Kiểm tra một cặp thuốc – bệnh có khớp với một chẩn đoán có mã ICD-10 không."""
    if not cd.ma_icd10 or not _norm_icd(cd.ma_icd10):
        return False
    return any(icd_matches(cd.ma_icd10, pattern) for pattern in pair.ma_icd10)


def _build_tai_lieu_evidence(pair: DrugDiseasePair) -> CanCu:
    """Tạo căn cứ tài liệu cho một cặp thuốc – bệnh từ DDInter 2.0."""
    parts = [_DDINTER_LICENSE]
    if pair.noi_dung:
        parts.append(pair.noi_dung)
    if pair.url:
        parts.append(pair.url)
    return CanCu(
        loai="tai_lieu",
        ban_ghi_id=pair.ddinter_id,
        mo_ta=" — ".join(parts),
    )


def _diagnosis_evidence(cd: ChanDoan) -> CanCu:
    """Tạo căn cứ dữ liệu trỏ tới một chẩn đoán của ca bệnh."""
    code_text = cd.ma_icd10 if cd.ma_icd10 and _norm_icd(cd.ma_icd10) else "thiếu mã ICD-10"
    return CanCu(
        loai="du_lieu",
        ban_ghi_id=cd.chan_doan_id,
        mo_ta=f"Chẩn đoán ({code_text}): {cd.noi_dung}",
    )


def check(
    ca: CaBenh,
    resolver: DrugResolver | None = None,
    config: DrugDiseaseConfig | None = None,
) -> list[PhatHien]:
    """Kiểm tra tương tác thuốc – bệnh DDInter 2.0 dựa trên mã ICD-10 chẩn đoán."""
    if resolver is None:
        return []
    active_config = config if config is not None else try_load_default_drug_disease_config()
    if active_config is None or not active_config.cap_thuoc_benh:
        return []

    pairs_by_hc: dict[str, list[DrugDiseasePair]] = {}
    for pair in active_config.cap_thuoc_benh:
        hc_key = normalize_text(pair.hoat_chat_id)
        if hc_key:
            pairs_by_hc.setdefault(hc_key, []).append(pair)
    if not pairs_by_hc:
        return []

    thuoc_by_id = {thuoc.thuoc_id: thuoc for thuoc in ca.danh_muc_thuoc}
    findings: list[PhatHien] = []

    for line in pending_lines(ca):
        resolved = resolver.resolve_line(ca, line)
        if is_line_excluded(resolved):
            continue
        raw_ids = extract_resolved_ids(resolved)
        if not raw_ids:
            continue

        ordered_hc_ids: list[str] = []
        name_by_hc: dict[str, str] = {}
        for tp in resolved.thanh_phan:
            hc_key = normalize_text(tp.hoat_chat_id)
            if hc_key and hc_key in {normalize_text(item) for item in raw_ids}:
                if hc_key not in name_by_hc:
                    ordered_hc_ids.append(hc_key)
                    name_by_hc[hc_key] = tp.ten_inn or tp.hoat_chat_id

        label = line_label(line, thuoc_by_id)
        line_id = line.chi_tiet_y_lenh_id

        for hc_key in ordered_hc_ids:
            all_pairs = pairs_by_hc.get(hc_key, [])
            comparable_pairs = [
                pair for pair in all_pairs if any(_norm_icd(code) for code in pair.ma_icd10)
            ]
            if not comparable_pairs:
                continue

            drug_label = label if len(ordered_hc_ids) == 1 else f"{label} ({name_by_hc[hc_key]})"
            matched_for_hc: list[PhatHien] = []
            for pair in comparable_pairs:
                matched_cds = [cd for cd in ca.chan_doan if _pair_matches_diagnosis(pair, cd)]
                if not matched_cds:
                    continue
                diag_text = "; ".join(f"{cd.ma_icd10} {cd.noi_dung}" for cd in matched_cds)
                evidences = dedupe_evidences(
                    [
                        *[_diagnosis_evidence(cd) for cd in matched_cds],
                        _build_tai_lieu_evidence(pair),
                    ]
                )
                matched_for_hc.append(
                    PhatHien(
                        ma_luat="thuoc_benh_ddinter",
                        yeu_to=_YEU_TO,
                        ket_luan="can_xem",
                        muc_do=_LEVEL_MAP[pair.muc_do],
                        chi_tiet_y_lenh_id=[line_id],
                        mo_ta=(
                            f"{drug_label} – {pair.ten_benh} (chẩn đoán {diag_text}): "
                            f"DDInter mức {pair.muc_do}, chỉ dùng sàng lọc"
                        ),
                        can_cu=evidences,
                    )
                )

            if matched_for_hc:
                findings.extend(matched_for_hc)
                continue

            missing_cds = [
                cd for cd in ca.chan_doan if cd.ma_icd10 is None or not _norm_icd(cd.ma_icd10)
            ]
            if not ca.chan_doan or missing_cds:
                data_evidences = (
                    [_diagnosis_evidence(cd) for cd in missing_cds]
                    if missing_cds
                    else [
                        CanCu(
                            loai="du_lieu",
                            ban_ghi_id=None,
                            mo_ta="Ca bệnh chưa có bản ghi chẩn đoán",
                        )
                    ]
                )
                findings.append(
                    PhatHien(
                        ma_luat="thuoc_benh_thieu_icd",
                        yeu_to=_YEU_TO,
                        ket_luan="khong_du_du_lieu",
                        muc_do=None,
                        chi_tiet_y_lenh_id=[line_id],
                        mo_ta=(
                            f"{drug_label}: chưa đủ mã ICD-10 chẩn đoán để loại trừ "
                            "tương tác thuốc – bệnh"
                        ),
                        can_cu=dedupe_evidences(
                            [
                                *data_evidences,
                                CanCu(
                                    loai="tai_lieu",
                                    ban_ghi_id=None,
                                    mo_ta=(
                                        f"{_DDINTER_LICENSE} — đã kiểm "
                                        f"{len(comparable_pairs)} cặp bệnh của {hc_key}"
                                    ),
                                ),
                            ]
                        ),
                        thong_tin_con_thieu=["ma_icd10_chan_doan"],
                    )
                )
            else:
                findings.append(
                    PhatHien(
                        ma_luat="thuoc_benh_khong_khop",
                        yeu_to=_YEU_TO,
                        ket_luan="dat",
                        muc_do="thong_tin",
                        chi_tiet_y_lenh_id=[line_id],
                        mo_ta=(
                            f"{drug_label}: không khớp tương tác thuốc – bệnh DDInter "
                            "với các chẩn đoán hiện có"
                        ),
                        can_cu=dedupe_evidences(
                            [
                                *[_diagnosis_evidence(cd) for cd in ca.chan_doan],
                                CanCu(
                                    loai="tai_lieu",
                                    ban_ghi_id=None,
                                    mo_ta=(
                                        f"{_DDINTER_LICENSE} — đã đối chiếu "
                                        f"{len(comparable_pairs)} cặp bệnh của {hc_key}"
                                    ),
                                ),
                            ]
                        ),
                    )
                )

    return findings
