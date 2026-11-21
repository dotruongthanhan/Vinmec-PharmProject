"""Luật yếu tố 7: kiểm tra kháng sinh cần phê duyệt hoặc ưu tiên quản lý theo QĐ 5631."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.domain.models import CaBenh, DienBien
from app.kb.names import normalize_key
from app.rules.d7_config import (
    ManagedAntibiotic,
    StewardshipConfig,
    StewardshipGroup,
    try_load_default_stewardship_config,
)
from app.rules.types import CanCu, PhatHien, line_label, pending_lines

if TYPE_CHECKING:
    from app.kb.resolver import DrugResolver

_YEU_TO = 7
_MAX_SNIPPET_LEN = 200
_APPROVAL_PHRASES = ("hoi chan", "phe duyet")
_WORD_SPAN_RE = re.compile(r"\S+")


def _contains_phrase(normalized_text: str, phrase: str) -> bool:
    """Kiểm tra cụm từ khoá xuất hiện theo ranh giới token sau chuẩn hoá."""
    return bool(normalized_text) and f" {phrase} " in f" {normalized_text} "


def _truncate_text(text: str, max_len: int = _MAX_SNIPPET_LEN) -> str:
    """Rút gọn chuỗi bảo đảm độ dài tối đa không vượt quá max_len."""
    if len(text) <= max_len:
        return text
    return f"{text[: max_len - 3].rstrip()}..."


def _extract_snippet_around_match(raw_text: str, phrase: str) -> str:
    """Trích đoạn chữ quanh cụm khớp trong văn bản gốc với độ dài tối đa 200 ký tự."""
    compact = " ".join(raw_text.split())
    if len(compact) <= _MAX_SNIPPET_LEN:
        return compact

    # Dò vị trí token tương ứng cụm chuẩn hoá để đoạn trích luôn giữ lại cụm khớp.
    token_entries: list[tuple[str, int, int]] = []
    for match in _WORD_SPAN_RE.finditer(compact):
        norm_token = normalize_key(match.group(0))
        if not norm_token:
            continue
        for sub_token in norm_token.split():
            token_entries.append((sub_token, match.start(), match.end()))

    phrase_tokens = phrase.split()
    span_start = 0
    span_end = min(len(compact), _MAX_SNIPPET_LEN)
    limit = len(token_entries) - len(phrase_tokens) + 1
    for idx in range(max(0, limit)):
        window = [token_entries[idx + offset][0] for offset in range(len(phrase_tokens))]
        if window == phrase_tokens:
            span_start = token_entries[idx][1]
            span_end = token_entries[idx + len(phrase_tokens) - 1][2]
            break

    budget = _MAX_SNIPPET_LEN - 6
    half_window = max(0, (budget - (span_end - span_start)) // 2)
    start = max(0, span_start - half_window)
    end = min(len(compact), start + budget)
    if end - start < budget:
        start = max(0, end - budget)

    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(compact) else ""
    core = compact[start:end].strip()
    return f"{prefix}{core}{suffix}"


def _find_consultation_record(dien_bien: list[DienBien]) -> tuple[DienBien, str] | None:
    """Tìm bản ghi diễn biến mới nhất có cụm 'hoi chan' hoặc 'phe duyet'."""
    ordered = sorted(dien_bien, key=lambda item: item.thoi_diem_ghi, reverse=True)
    for record in ordered:
        norm_content = normalize_key(record.noi_dung)
        for phrase in _APPROVAL_PHRASES:
            if _contains_phrase(norm_content, phrase):
                return record, _extract_snippet_around_match(record.noi_dung, phrase)

        norm_type = normalize_key(record.loai_ho_so)
        for phrase in _APPROVAL_PHRASES:
            if _contains_phrase(norm_type, phrase):
                combined = " ".join(f"{record.loai_ho_so}: {record.noi_dung}".split())
                return record, _truncate_text(combined)
    return None


def _build_document_evidences(
    config: StewardshipConfig,
    group: StewardshipGroup,
    entries: list[ManagedAntibiotic],
) -> list[CanCu]:
    """Tạo căn cứ tài liệu QĐ 5631/QĐ-BYT theo từng trang PDF duy nhất."""
    pages = list(dict.fromkeys(entry.trang_pdf or group.trang_pdf for entry in entries))
    url = config.nguon_van_ban.url
    return [
        CanCu(
            loai="tai_lieu",
            ban_ghi_id=group.ma_nhom,
            mo_ta=(
                f"QĐ 5631/QĐ-BYT (bản sao thứ cấp), trang {page}: "
                f"{group.ten_nhom_van_ban} — {url} (chờ dược sĩ duyệt)"
            ),
        )
        for page in pages
    ]


def check(
    ca: CaBenh,
    resolver: DrugResolver | None = None,
    config: StewardshipConfig | None = None,
) -> list[PhatHien]:
    """Kiểm tra dòng y lệnh chờ duyệt thuộc danh mục kháng sinh quản lý."""
    if resolver is None:
        return []

    active_config = config if config is not None else try_load_default_stewardship_config()
    if active_config is None:
        return []

    groups_by_code = active_config.group_by_code()
    thuoc_by_id = {thuoc.thuoc_id: thuoc for thuoc in ca.danh_muc_thuoc}
    consultation_match = _find_consultation_record(ca.dien_bien)
    findings: list[PhatHien] = []

    for line in pending_lines(ca):
        resolved = resolver.resolve_line(ca, line)
        if resolved.trang_thai not in {"da_phan_giai", "mot_phan"} or not resolved.thanh_phan:
            continue

        line_hc_ids = {tp.hoat_chat_id for tp in resolved.thanh_phan if tp.hoat_chat_id}
        if not line_hc_ids:
            continue

        entries_by_group: dict[str, list[ManagedAntibiotic]] = {}
        for entry in active_config.khang_sinh:
            if line_hc_ids.intersection(entry.hoat_chat_ids):
                entries_by_group.setdefault(entry.ma_nhom, []).append(entry)

        if not entries_by_group:
            continue

        label = line_label(line, thuoc_by_id)
        for group_code, matched_entries in entries_by_group.items():
            group = groups_by_code.get(group_code)
            if group is None:
                continue

            matched_names = ", ".join(
                dict.fromkeys(entry.ten_trong_van_ban for entry in matched_entries)
            )
            doc_evidences = _build_document_evidences(active_config, group, matched_entries)

            if group.ma_nhom == "phe_duyet_truoc":
                if consultation_match is None:
                    findings.append(
                        PhatHien(
                            ma_luat="khang_sinh_can_phe_duyet",
                            yeu_to=_YEU_TO,
                            ket_luan="can_xem",
                            muc_do="can_luu_y",
                            chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                            mo_ta=(
                                f"{label} ({matched_names}) thuộc nhóm {group.ten_nhom_van_ban}; "
                                "chưa thấy ghi nhận hội chẩn hoặc phê duyệt "
                                "(dò theo chữ trong diễn biến). "
                                f"Yêu cầu: {group.yeu_cau}"
                            ),
                            can_cu=[
                                CanCu(
                                    loai="du_lieu",
                                    ban_ghi_id=line.chi_tiet_y_lenh_id,
                                    mo_ta=(
                                        f"Y lệnh {label} thuộc nhóm {group.ma_nhom}; "
                                        "chưa thấy cụm hội chẩn/phê duyệt khi dò theo chữ "
                                        "trong diễn biến"
                                    ),
                                ),
                                *doc_evidences,
                            ],
                        )
                    )
                else:
                    matched_record, snippet = consultation_match
                    findings.append(
                        PhatHien(
                            ma_luat="khang_sinh_da_co_hoi_chan",
                            yeu_to=_YEU_TO,
                            ket_luan="dat",
                            muc_do="thong_tin",
                            chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                            mo_ta=(
                                f"{label} ({matched_names}) thuộc nhóm {group.ten_nhom_van_ban}; "
                                "đã thấy ghi nhận hội chẩn hoặc phê duyệt "
                                "(dò theo chữ trong diễn biến)."
                            ),
                            can_cu=[
                                CanCu(
                                    loai="du_lieu",
                                    ban_ghi_id=matched_record.dien_bien_id,
                                    mo_ta=snippet,
                                ),
                                *doc_evidences,
                            ],
                        )
                    )
                continue

            findings.append(
                PhatHien(
                    ma_luat="khang_sinh_uu_tien_quan_ly",
                    yeu_to=_YEU_TO,
                    ket_luan="can_xem",
                    muc_do="thong_tin",
                    chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                    mo_ta=(
                        f"{label} ({matched_names}) thuộc nhóm {group.ten_nhom_van_ban}. "
                        f"Yêu cầu: {group.yeu_cau}"
                    ),
                    can_cu=[
                        CanCu(
                            loai="du_lieu",
                            ban_ghi_id=line.chi_tiet_y_lenh_id,
                            mo_ta=f"Y lệnh {label} thuộc nhóm {group.ma_nhom}",
                        ),
                        *doc_evidences,
                    ],
                )
            )

    return findings
