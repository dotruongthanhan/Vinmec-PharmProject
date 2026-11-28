"""Luật yếu tố 3: kiểm tra đường dùng hợp lệ theo dạng bào chế của sản phẩm."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain.models import CaBenh, ChiTietYLenh, Thuoc
from app.rules.d5_config import (
    ROUTE_TO_FORM_GROUP,
    RouteConfig,
    RouteRule,
    RouteSource,
    is_same_route_or_iv,
    try_load_default_route_config,
)
from app.rules.types import CanCu, PhatHien, line_label, pending_lines

if TYPE_CHECKING:
    from app.kb.resolver import DrugResolver
    from app.kb.resolver.resolver import KetQuaPhanGiai

_YEU_TO = 3
_EXCLUDED_KINDS = {"dich_truyen_dien_giai", "duoc_lieu"}
_DAV_URL = "https://dichvucong.dav.gov.vn/congbothuoc"
_SPLIT_ROUTE_RE = re.compile(r"\s*(?:,|;|/|\bvà\b|\bva\b)\s*", re.IGNORECASE)


@dataclass(frozen=True)
class _GroupEval:
    """Kết quả đối chiếu đường dùng của một dòng với một nhóm dạng bào chế."""

    finding: PhatHien
    rank: int


def _extract_resolved_ids(result: KetQuaPhanGiai) -> set[str]:
    """Lấy tập mã hoạt chất trên trục từ kết quả phân giải đã hoặc một phần nhận diện."""
    if result.trang_thai not in {"da_phan_giai", "mot_phan"}:
        return set()
    return {tp.hoat_chat_id for tp in result.thanh_phan if tp.hoat_chat_id}


def _is_line_excluded(result: KetQuaPhanGiai) -> bool:
    """Kiểm tra dòng thuốc thuộc nhóm dịch truyền, điện giải hoặc dược liệu."""
    if result.trang_thai == "khong_ap_dung":
        return True
    return bool(result.thanh_phan) and all(tp.loai in _EXCLUDED_KINDS for tp in result.thanh_phan)


def _format_route_goc(src: RouteSource) -> str:
    """Định dạng danh sách route_goc của nguồn NDC hoặc nhãn FDA."""
    parts: list[str] = []
    for item in src.route_goc:
        if isinstance(item, str):
            parts.append(item)
        elif item.so_san_pham is not None:
            parts.append(f"{item.route} ({item.so_san_pham})")
        else:
            parts.append(item.route)
    return ", ".join(parts) if parts else "không rõ"


def _build_source_evidence(rule: RouteRule, src: RouteSource) -> CanCu:
    """Tạo căn cứ tài liệu từ một mục nguồn trong bảng đường dùng hợp lệ."""
    row_id = rule.ma_dong or None
    if src.loai == "dav_dang_bao_che":
        count = src.so_san_pham_dav if src.so_san_pham_dav is not None else "không rõ"
        sdk = src.vi_du_so_dang_ky or "không rõ"
        url = src.url or _DAV_URL
        desc = f"DAV dạng bào chế: {count} sản phẩm (VD SĐK: {sdk}) — {url} (chờ dược sĩ duyệt)"
    elif src.loai == "ndc_openfda":
        routes = _format_route_goc(src)
        query = src.truy_van or src.url or "https://api.fda.gov/drug/ndc.json"
        desc = f"openFDA NDC route_goc=[{routes}] — {query} (chờ dược sĩ duyệt)"
    else:
        name = src.ten_nhan or src.loai
        routes = _format_route_goc(src)
        url = src.url or src.truy_van or src.url_api or "https://open.fda.gov"
        desc = f"{name} (route_goc=[{routes}]) — {url} (chờ dược sĩ duyệt)"
    return CanCu(loai="tai_lieu", ban_ghi_id=row_id, mo_ta=desc)


def _dedupe_evidences(evidences: list[CanCu]) -> list[CanCu]:
    """Loại bỏ căn cứ trùng lặp nhưng giữ nguyên thứ tự."""
    seen: set[tuple[str, str | None, str]] = set()
    unique: list[CanCu] = []
    for item in evidences:
        key = (item.loai, item.ban_ghi_id, item.mo_ta)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _product_form_groups(thuoc: Thuoc | None, config: RouteConfig) -> list[str]:
    """Suy tập nhóm dạng bào chế của sản phẩm từ Thuoc.duong_dung theo thứ tự xuất hiện."""
    if thuoc is None or not thuoc.duong_dung or not thuoc.duong_dung.strip():
        return []
    groups: list[str] = []
    for part in _SPLIT_ROUTE_RE.split(thuoc.duong_dung):
        piece = part.strip()
        if not piece:
            continue
        code, _ = config.normalize_route(piece)
        if code is None:
            continue
        group = ROUTE_TO_FORM_GROUP.get(code)
        if group is not None and group not in groups:
            groups.append(group)
    return groups


def _find_rules_for_group(
    resolved_ids: set[str],
    form_group: str,
    combo_index: dict[tuple[tuple[str, ...], str], RouteRule],
    single_index: dict[tuple[str, str], RouteRule],
) -> list[RouteRule]:
    """Tra hàng bảng cho tập hoạt chất và nhóm dạng; thử từng hoạt chất nếu phối hợp."""
    sorted_ids = tuple(sorted(resolved_ids))
    combined = combo_index.get((sorted_ids, form_group))
    if combined is not None:
        return [combined] if combined.duong_dung_hop_le else []

    if len(sorted_ids) > 1:
        per_ingredient: list[RouteRule] = []
        for hc_id in sorted_ids:
            row = single_index.get((hc_id, form_group))
            if row is not None and row.duong_dung_hop_le:
                per_ingredient.append(row)
        return per_ingredient
    return []


def _is_route_allowed(ordered_code: str, allowed_routes: tuple[str, ...]) -> bool:
    """Kiểm tra mã đường dùng có nằm trong tập hợp lệ (kể cả tương đương tĩnh mạch)."""
    return any(is_same_route_or_iv(ordered_code, allowed) for allowed in allowed_routes)


def _evaluate_group(
    *,
    line: ChiTietYLenh,
    label: str,
    raw_route: str,
    ordered_code: str,
    product_route_raw: str,
    form_group: str,
    resolved_ids: set[str],
    combo_index: dict[tuple[tuple[str, ...], str], RouteRule],
    single_index: dict[tuple[str, str], RouteRule],
    partial_reason: str | None,
) -> _GroupEval:
    """Đánh giá đường dùng của dòng theo một nhóm dạng bào chế cụ thể."""
    data_ev = CanCu(
        loai="du_lieu",
        ban_ghi_id=line.chi_tiet_y_lenh_id,
        mo_ta=(
            f"{label}: đường kê '{raw_route}' ({ordered_code}), "
            f"đường dùng danh mục '{product_route_raw}' (nhóm {form_group})"
        ),
    )

    rules = _find_rules_for_group(resolved_ids, form_group, combo_index, single_index)
    if not rules:
        return _GroupEval(
            finding=PhatHien(
                ma_luat="duong_dung_thieu_nguon",
                yeu_to=_YEU_TO,
                ket_luan="khong_du_du_lieu",
                muc_do=None,
                chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                mo_ta=(
                    f"{label}: không có dữ liệu đường dùng hợp lệ cho "
                    f"{', '.join(sorted(resolved_ids))} ở nhóm {form_group}"
                ),
                can_cu=[data_ev],
                thong_tin_con_thieu=["nguon_duong_dung"],
            ),
            rank=1,
        )

    all_allowed: list[str] = []
    source_evidences: list[CanCu] = []
    mismatched_rules: list[RouteRule] = []

    for rule in rules:
        for route in rule.duong_dung_hop_le:
            if route not in all_allowed:
                all_allowed.append(route)
        for src in rule.nguon:
            source_evidences.append(_build_source_evidence(rule, src))
        if not _is_route_allowed(ordered_code, rule.duong_dung_hop_le):
            mismatched_rules.append(rule)

    evidences = _dedupe_evidences([data_ev, *source_evidences])
    allowed_text = ", ".join(all_allowed)

    if not mismatched_rules:
        if partial_reason is not None:
            return _GroupEval(
                finding=PhatHien(
                    ma_luat="duong_dung_thieu_hoat_chat",
                    yeu_to=_YEU_TO,
                    ket_luan="khong_du_du_lieu",
                    muc_do=None,
                    chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                    mo_ta=(
                        f"{label}: chỉ phân giải được một phần hoạt chất ({partial_reason}), "
                        "không thể kết luận đạt đường dùng"
                    ),
                    can_cu=evidences,
                    thong_tin_con_thieu=["hoat_chat"],
                ),
                rank=1,
            )
        return _GroupEval(
            finding=PhatHien(
                ma_luat="duong_dung_hop_le",
                yeu_to=_YEU_TO,
                ket_luan="dat",
                muc_do="thong_tin",
                chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                mo_ta=(
                    f"{label}: đường dùng '{raw_route}' ({ordered_code}) phù hợp với "
                    f"nhóm {form_group} (hợp lệ: {allowed_text})"
                ),
                can_cu=evidences,
            ),
            rank=4,
        )

    ordered_group = ROUTE_TO_FORM_GROUP.get(ordered_code)
    if ordered_group is not None and ordered_group != form_group:
        return _GroupEval(
            finding=PhatHien(
                ma_luat="duong_dung_khac_dang_bao_che",
                yeu_to=_YEU_TO,
                ket_luan="can_xem",
                muc_do="nghiem_trong",
                chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                mo_ta=(
                    f"{label}: đường dùng '{raw_route}' ({ordered_code}) thuộc nhóm "
                    f"{ordered_group}, khác nhóm dạng {form_group} của sản phẩm "
                    f"(hợp lệ: {allowed_text})"
                ),
                can_cu=evidences,
            ),
            rank=3,
        )

    return _GroupEval(
        finding=PhatHien(
            ma_luat="duong_dung_ngoai_nguon",
            yeu_to=_YEU_TO,
            ket_luan="can_xem",
            muc_do="can_luu_y",
            chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
            mo_ta=(
                f"{label}: đường dùng '{raw_route}' ({ordered_code}) thuộc nhóm {form_group} "
                f"nhưng không thấy trong nguồn đã lấy, chưa phải kết luận kê sai "
                f"(nguồn ghi: {allowed_text})"
            ),
            can_cu=evidences,
        ),
        rank=2,
    )


def check(
    ca: CaBenh,
    resolver: DrugResolver | None = None,
    config: RouteConfig | None = None,
) -> list[PhatHien]:
    """Kiểm tra đường dùng hợp lệ cho các dòng thuốc chờ duyệt (yếu tố 3)."""
    if resolver is None:
        return []

    active_config = config if config is not None else try_load_default_route_config()
    if active_config is None:
        return []

    combo_index: dict[tuple[tuple[str, ...], str], RouteRule] = {}
    single_index: dict[tuple[str, str], RouteRule] = {}
    for rule in active_config.nhom:
        sorted_ids = tuple(sorted(rule.hoat_chat_ids))
        combo_index[(sorted_ids, rule.nhom_dang_bao_che)] = rule
        if len(sorted_ids) == 1:
            single_index[(sorted_ids[0], rule.nhom_dang_bao_che)] = rule

    thuoc_by_id = {thuoc.thuoc_id: thuoc for thuoc in ca.danh_muc_thuoc}
    findings: list[PhatHien] = []

    for line in pending_lines(ca):
        if line.loai_san_pham != "thuoc":
            continue

        result = resolver.resolve_line(ca, line)
        if _is_line_excluded(result):
            continue

        label = line_label(line, thuoc_by_id)
        resolved_ids = _extract_resolved_ids(result)
        if result.trang_thai == "khong_nhan_dien" or not resolved_ids:
            reason = f" ({result.ly_do})" if result.ly_do else ""
            findings.append(
                PhatHien(
                    ma_luat="duong_dung_thieu_hoat_chat",
                    yeu_to=_YEU_TO,
                    ket_luan="khong_du_du_lieu",
                    muc_do=None,
                    chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                    mo_ta=f"{label}: chưa nhận diện được hoạt chất để kiểm tra đường dùng{reason}",
                    can_cu=[
                        CanCu(
                            loai="du_lieu",
                            ban_ghi_id=line.chi_tiet_y_lenh_id,
                            mo_ta=f"Phân giải '{label}' trạng thái {result.trang_thai}{reason}",
                        ),
                    ],
                    thong_tin_con_thieu=["hoat_chat"],
                )
            )
            continue

        if line.duong_dung is None or not line.duong_dung.strip():
            findings.append(
                PhatHien(
                    ma_luat="duong_dung_thieu",
                    yeu_to=_YEU_TO,
                    ket_luan="khong_du_du_lieu",
                    muc_do=None,
                    chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                    mo_ta=f"{label}: thiếu đường dùng trên dòng y lệnh",
                    can_cu=[
                        CanCu(
                            loai="du_lieu",
                            ban_ghi_id=line.chi_tiet_y_lenh_id,
                            mo_ta=f"Dòng {label} không ghi duong_dung",
                        ),
                    ],
                    thong_tin_con_thieu=["duong_dung"],
                )
            )
            continue

        raw_route = line.duong_dung.strip()
        ordered_code, ambiguous_reason = active_config.normalize_route(raw_route)
        if ordered_code is None:
            detail = f" ({ambiguous_reason})" if ambiguous_reason else ""
            findings.append(
                PhatHien(
                    ma_luat="duong_dung_khong_chuan_hoa_duoc",
                    yeu_to=_YEU_TO,
                    ket_luan="khong_du_du_lieu",
                    muc_do=None,
                    chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                    mo_ta=f"{label}: không chuẩn hoá được đường dùng '{raw_route}'{detail}",
                    can_cu=[
                        CanCu(
                            loai="du_lieu",
                            ban_ghi_id=line.chi_tiet_y_lenh_id,
                            mo_ta=f"Cách viết đường dùng gốc: '{raw_route}'",
                        ),
                    ],
                    thong_tin_con_thieu=["duong_dung_chuan_hoa"],
                )
            )
            continue

        thuoc = thuoc_by_id.get(line.thuoc_id) if line.thuoc_id else None
        form_groups = _product_form_groups(thuoc, active_config)
        if not form_groups:
            product_route = thuoc.duong_dung if thuoc is not None and thuoc.duong_dung else "trống"
            findings.append(
                PhatHien(
                    ma_luat="duong_dung_thieu_dang_bao_che",
                    yeu_to=_YEU_TO,
                    ket_luan="khong_du_du_lieu",
                    muc_do=None,
                    chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                    mo_ta=(
                        f"{label}: danh mục thuốc chưa có dạng bào chế / đường dùng rõ ràng "
                        f"(giá trị: '{product_route}')"
                    ),
                    can_cu=[
                        CanCu(
                            loai="du_lieu",
                            ban_ghi_id=line.chi_tiet_y_lenh_id,
                            mo_ta=f"Thuoc.duong_dung = '{product_route}'",
                        ),
                    ],
                    thong_tin_con_thieu=["dang_bao_che"],
                )
            )
            continue

        partial_reason: str | None = None
        if result.trang_thai == "mot_phan":
            partial_reason = result.ly_do or "một phần thành phần"
        product_route_raw = thuoc.duong_dung if thuoc and thuoc.duong_dung else ""
        evaluations = [
            _evaluate_group(
                line=line,
                label=label,
                raw_route=raw_route,
                ordered_code=ordered_code,
                product_route_raw=product_route_raw,
                form_group=group,
                resolved_ids=resolved_ids,
                combo_index=combo_index,
                single_index=single_index,
                partial_reason=partial_reason,
            )
            for group in form_groups
        ]
        best = max(evaluations, key=lambda item: item.rank)
        findings.append(best.finding)

    return findings
