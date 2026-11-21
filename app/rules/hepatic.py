"""Luật yếu tố 6: kiểm tra chỉnh liều theo tình trạng suy gan và nhãn FDA."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from app.domain.loader import latest_lab
from app.domain.models import CaBenh, CoDia, KetQuaXetNghiem
from app.rules.d4_config import (
    HepaticAction,
    HepaticConfig,
    HepaticRule,
    dedupe_evidences,
    display_name_for_ids,
    extract_resolved_ids,
    format_fda_source_evidence,
    is_line_excluded,
    rule_ingredient_key,
    try_load_default_hepatic_config,
)
from app.rules.types import CanCu, PhatHien, normalize_text, pending_lines

if TYPE_CHECKING:
    from app.kb.resolver import DrugResolver

_YEU_TO = 6
_MIN_DT = datetime.min.replace(tzinfo=UTC)
_CHILD_PUGH_RE = re.compile(r"child[\s-]*pugh\s*(?:class\s*)?([abc])\b", re.IGNORECASE)
_HEPATIC_LAB_CODES = ("alt", "ast", "bilirubin")

_KetLuan = Literal["dat", "can_xem", "ngoai_hdsd"]
_MucDo = Literal["nghiem_trong", "can_luu_y", "thong_tin"]

_ACTION_OUTCOME: dict[HepaticAction, tuple[_KetLuan, _MucDo]] = {
    "chong_chi_dinh": ("can_xem", "nghiem_trong"),
    "tranh_khong_khuyen_cao": ("can_xem", "nghiem_trong"),
    "giam_lieu": ("can_xem", "can_luu_y"),
    "theo_doi": ("can_xem", "can_luu_y"),
    "khong_co_khuyen_cao_cu_the": ("ngoai_hdsd", "can_luu_y"),
    "khong_chinh_lieu": ("dat", "thong_tin"),
}
_SEVERITY_RANK: dict[tuple[_KetLuan, _MucDo], int] = {
    ("can_xem", "nghiem_trong"): 0,
    ("can_xem", "can_luu_y"): 1,
    ("ngoai_hdsd", "can_luu_y"): 2,
    ("dat", "thong_tin"): 3,
}


def _latest_hepatic_condition(ca: CaBenh) -> CoDia | None:
    """Lấy bản ghi cơ địa suy_gan mới nhất; bản ghi thiếu thoi_diem xếp cũ nhất."""
    records = [cd for cd in ca.co_dia if cd.loai == "suy_gan"]
    if not records:
        return None
    _, latest = max(
        enumerate(records),
        key=lambda item: (item[1].thoi_diem is not None, item[1].thoi_diem or _MIN_DT, item[0]),
    )
    return latest


def _classify_hepatic_status(record: CoDia | None) -> str:
    """Phân loại tình trạng gan của người bệnh từ bản ghi suy_gan mới nhất."""
    if record is None or record.trang_thai == "chua_ro":
        return "chua_danh_gia"
    if record.trang_thai == "khong":
        return "khong_suy"
    if record.gia_tri:
        match = _CHILD_PUGH_RE.search(record.gia_tri)
        if match:
            return f"child_pugh_{match.group(1).upper()}"
    return "co_suy_chua_phan_hang"


def _row_applies_to_status(row: HepaticRule, status: str) -> bool:
    """Kiểm tra một dòng bảng gan có áp dụng cho phân hạng suy gan hiện tại không."""
    classes = set(row.phan_loai_gan)
    if status == "child_pugh_A":
        return bool(classes & {"child_pugh_A", "nhe_vua", "khong_phan_loai"})
    if status == "child_pugh_B":
        return bool(classes & {"child_pugh_B", "nhe_vua", "khong_phan_loai"})
    if status == "child_pugh_C":
        return bool(classes & {"child_pugh_C", "nang", "khong_phan_loai"})
    if status == "co_suy_chua_phan_hang":
        return "khong_phan_loai" in classes
    return False


def _hepatic_condition_evidence(record: CoDia | None, status: str) -> CanCu:
    """Tạo căn cứ dữ liệu mô tả bản ghi suy_gan đã dùng để đánh giá."""
    if record is None:
        return CanCu(
            loai="du_lieu",
            ban_ghi_id=None,
            mo_ta="Cơ địa suy gan: chưa có bản ghi đánh giá trong hồ sơ",
        )
    parts = [f"Cơ địa suy_gan: trang_thai={record.trang_thai}"]
    if record.gia_tri:
        parts.append(f"gia_tri={record.gia_tri}")
    if record.thoi_diem is not None:
        parts.append(f"lúc {record.thoi_diem.isoformat()}")
    if record.nguon:
        parts.append(f"(nguồn: {record.nguon})")
    parts.append(f"[{status}]")
    return CanCu(loai="du_lieu", ban_ghi_id=None, mo_ta=", ".join(parts))


def _hepatic_lab_evidence(lab: KetQuaXetNghiem) -> CanCu:
    """Tạo căn cứ dữ liệu cho một xét nghiệm gan (chỉ tham khảo, không phân hạng)."""
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


def _doc_evidences_from_rows(rows: list[HepaticRule]) -> list[CanCu]:
    """Gộp và khử trùng căn cứ tài liệu từ danh sách dòng bảng gan."""
    return dedupe_evidences(
        [format_fda_source_evidence(src) for row in rows for src in row.nguon_chi_tiet]
    )


def _group_hepatic_rules(
    rules: tuple[HepaticRule, ...],
) -> list[tuple[frozenset[str], list[HepaticRule]]]:
    """Gom các dòng bảng gan theo tập hoạt chất để mỗi cặp (dòng, nhóm) ra một phát hiện."""
    grouped: dict[frozenset[str], list[HepaticRule]] = {}
    for row in rules:
        key = rule_ingredient_key(row.hoat_chat_ids, row.ten_quoc_te)
        if not key:
            continue
        grouped.setdefault(key, []).append(row)
    return list(grouped.items())


def _build_applied_finding(
    line_id: str,
    drug_name: str,
    status: str,
    record: CoDia | None,
    applied_rows: list[HepaticRule],
) -> PhatHien:
    """Tạo phát hiện gan_theo_nhan khi có một hoặc nhiều dòng áp dụng."""
    outcomes = [_ACTION_OUTCOME[row.hanh_dong_nhan] for row in applied_rows]
    ket_luan, muc_do = min(outcomes, key=lambda pair: _SEVERITY_RANK[pair])
    advices = "; ".join(dict.fromkeys(row.khuyen_cao for row in applied_rows))
    evidences = dedupe_evidences(
        [_hepatic_condition_evidence(record, status), *_doc_evidences_from_rows(applied_rows)]
    )
    return PhatHien(
        ma_luat="gan_theo_nhan",
        yeu_to=_YEU_TO,
        ket_luan=ket_luan,
        muc_do=muc_do,
        chi_tiet_y_lenh_id=[line_id],
        mo_ta=f"{drug_name} ({status}): {advices}",
        can_cu=evidences,
    )


def check(
    ca: CaBenh,
    resolver: DrugResolver | None = None,
    config: HepaticConfig | None = None,
) -> list[PhatHien]:
    """Kiểm tra chỉnh liều theo suy gan dựa trên cơ địa suy_gan và bảng nhãn FDA."""
    if resolver is None:
        return []
    active_config = config if config is not None else try_load_default_hepatic_config()
    if active_config is None or not active_config.quy_tac:
        return []

    record = _latest_hepatic_condition(ca)
    status = _classify_hepatic_status(record)
    grouped_rules = _group_hepatic_rules(active_config.quy_tac)

    findings: list[PhatHien] = []
    for line in pending_lines(ca):
        resolved = resolver.resolve_line(ca, line)
        if is_line_excluded(resolved):
            continue
        line_ids = {normalize_text(item) for item in extract_resolved_ids(resolved)}
        if not line_ids:
            continue

        for key, rows in grouped_rules:
            if not (key & line_ids):
                continue
            drug_name = display_name_for_ids(resolved, key, rows[0].ten_quoc_te)
            action_rows = [row for row in rows if row.hanh_dong_nhan != "khong_chinh_lieu"]
            line_id = line.chi_tiet_y_lenh_id

            if status == "khong_suy":
                findings.append(
                    PhatHien(
                        ma_luat="gan_khong_suy_gan",
                        yeu_to=_YEU_TO,
                        ket_luan="dat",
                        muc_do="thong_tin",
                        chi_tiet_y_lenh_id=[line_id],
                        mo_ta=f"{drug_name}: người bệnh không suy gan, không cần chỉnh liều gan",
                        can_cu=dedupe_evidences(
                            [
                                _hepatic_condition_evidence(record, status),
                                *_doc_evidences_from_rows(rows),
                            ]
                        ),
                    )
                )
                continue

            if status in {"child_pugh_A", "child_pugh_B", "child_pugh_C"}:
                applied = [row for row in rows if _row_applies_to_status(row, status)]
                if applied:
                    findings.append(
                        _build_applied_finding(line_id, drug_name, status, record, applied)
                    )
                else:
                    findings.append(
                        PhatHien(
                            ma_luat="gan_khong_co_khuyen_cao_cho_hang",
                            yeu_to=_YEU_TO,
                            ket_luan="dat",
                            muc_do="thong_tin",
                            chi_tiet_y_lenh_id=[line_id],
                            mo_ta=(
                                f"{drug_name} ({status}): nhãn không có khuyến cáo chỉnh liều "
                                "riêng cho phân hạng này"
                            ),
                            can_cu=dedupe_evidences(
                                [
                                    _hepatic_condition_evidence(record, status),
                                    *_doc_evidences_from_rows(rows),
                                ]
                            ),
                        )
                    )
                continue

            if status == "co_suy_chua_phan_hang":
                unclassified_action = [
                    row for row in action_rows if "khong_phan_loai" in row.phan_loai_gan
                ]
                if unclassified_action:
                    applied_unclassified = [
                        row for row in rows if "khong_phan_loai" in row.phan_loai_gan
                    ]
                    findings.append(
                        _build_applied_finding(
                            line_id, drug_name, status, record, applied_unclassified
                        )
                    )
                elif action_rows:
                    advices = "; ".join(dict.fromkeys(row.khuyen_cao for row in action_rows))
                    findings.append(
                        PhatHien(
                            ma_luat="gan_thieu_phan_hang",
                            yeu_to=_YEU_TO,
                            ket_luan="khong_du_du_lieu",
                            muc_do=None,
                            chi_tiet_y_lenh_id=[line_id],
                            mo_ta=(
                                f"{drug_name}: có suy gan nhưng chưa phân hạng Child-Pugh; "
                                f"khuyến cáo theo hạng: {advices}"
                            ),
                            can_cu=dedupe_evidences(
                                [
                                    _hepatic_condition_evidence(record, status),
                                    *_doc_evidences_from_rows(action_rows),
                                ]
                            ),
                            thong_tin_con_thieu=["phan_hang_child_pugh"],
                        )
                    )
                else:
                    findings.append(
                        PhatHien(
                            ma_luat="gan_khong_chinh_lieu",
                            yeu_to=_YEU_TO,
                            ket_luan="dat",
                            muc_do="thong_tin",
                            chi_tiet_y_lenh_id=[line_id],
                            mo_ta=f"{drug_name}: suy gan không cần chỉnh liều theo nhãn",
                            can_cu=dedupe_evidences(
                                [
                                    _hepatic_condition_evidence(record, status),
                                    *_doc_evidences_from_rows(rows),
                                ]
                            ),
                        )
                    )
                continue

            # status == "chua_danh_gia"
            if not action_rows:
                continue
            lab_evidences: list[CanCu] = []
            for lab_code in _HEPATIC_LAB_CODES:
                lab = latest_lab(ca, lab_code)
                if lab is not None:
                    lab_evidences.append(_hepatic_lab_evidence(lab))
            findings.append(
                PhatHien(
                    ma_luat="gan_chua_danh_gia",
                    yeu_to=_YEU_TO,
                    ket_luan="khong_du_du_lieu",
                    muc_do=None,
                    chi_tiet_y_lenh_id=[line_id],
                    mo_ta=(
                        f"{drug_name}: thuốc có khuyến cáo liên quan suy gan nhưng hồ sơ "
                        "chưa đánh giá chức năng gan"
                    ),
                    can_cu=dedupe_evidences(
                        [
                            _hepatic_condition_evidence(record, status),
                            *lab_evidences,
                            *_doc_evidences_from_rows(action_rows),
                        ]
                    ),
                    thong_tin_con_thieu=["danh_gia_chuc_nang_gan"],
                )
            )

    return findings
