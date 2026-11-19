"""Luật yếu tố 1: kiểm tra dị ứng hoạt chất, dị ứng chéo theo bảng và sản phẩm chưa rõ."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from app.domain.loader import ingredients_of
from app.domain.models import CaBenh, ChiTietYLenh, DiUng, HoatChat, Thuoc
from app.rules.allergy_config import (
    AllergyCrossConfig,
    AllergyCrossGroup,
    CrossMatch,
    CrossSource,
    GroupAlias,
    strip_parenthetical,
    try_load_default_allergy_config,
)
from app.rules.types import CanCu, PhatHien, line_label, normalize_text, pending_lines

if TYPE_CHECKING:
    from app.kb.resolver import DrugResolver
    from app.kb.resolver.resolver import KetQuaPhanGiai

_YEU_TO = 1
_MucDo = Literal["nghiem_trong", "can_luu_y", "thong_tin"]
_MUC_DO_ORDER: dict[_MucDo, int] = {
    "nghiem_trong": 3,
    "can_luu_y": 2,
    "thong_tin": 1,
}
_EXCLUDED_KINDS = {"dich_truyen_dien_giai", "duoc_lieu"}
_CROSS_RISK_DISPLAY: dict[str, tuple[_MucDo, str]] = {
    "cao": ("nghiem_trong", "nguy cơ dị ứng chéo cao"),
    "thap": ("can_luu_y", "nguy cơ dị ứng chéo thấp"),
    "rat_thap": ("can_luu_y", "nguy cơ chéo rất thấp theo nguồn"),
}


@dataclass(frozen=True)
class _ResolvedAllergen:
    """Hoạt chất hoặc nhóm dị ứng sau khi phân giải từ bản ghi dị ứng."""

    du: DiUng
    ingredient_ids: frozenset[str]
    group_alias: GroupAlias | None = None


def _build_allergy_evidence(du: DiUng) -> CanCu:
    """Tạo căn cứ dữ liệu trỏ tới bản ghi dị ứng."""
    phan_ung = du.phan_ung if du.phan_ung else "chưa ghi nhận phản ứng"
    return CanCu(
        loai="du_lieu",
        ban_ghi_id=du.di_ung_id,
        mo_ta=f"Tác nhân dị ứng: {du.tac_nhan}; phản ứng: {phan_ung}",
    )


def _match_line_allergy(
    line: ChiTietYLenh,
    ingredients: list[HoatChat],
    du: DiUng,
    thuoc_by_id: dict[str, Thuoc],
) -> PhatHien | None:
    """Đối chiếu một cặp (dòng thuốc, bản ghi dị ứng), ưu tiên trùng hoạt chất."""
    if du.loai_tac_nhan != "thuoc":
        return None

    label = line_label(line, thuoc_by_id)
    if du.hoat_chat_id is not None:
        matched_hc = next(
            (hc for hc in ingredients if hc.hoat_chat_id == du.hoat_chat_id),
            None,
        )
        if matched_hc is not None:
            return PhatHien(
                ma_luat="di_ung_trung_hoat_chat",
                yeu_to=_YEU_TO,
                ket_luan="can_xem",
                muc_do="nghiem_trong",
                chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                mo_ta=(
                    f"Thuốc {label} chứa hoạt chất {matched_hc.ten_hoat_chat} "
                    f"trùng tiền sử dị ứng {du.tac_nhan}"
                ),
                can_cu=[_build_allergy_evidence(du)],
            )

    allergy_group = normalize_text(du.nhom_duoc_ly)
    if not allergy_group:
        return None

    same_group_hc = next(
        (hc for hc in ingredients if normalize_text(hc.nhom_duoc_ly) == allergy_group),
        None,
    )
    if same_group_hc is None:
        return None

    return PhatHien(
        ma_luat="di_ung_cung_nhom",
        yeu_to=_YEU_TO,
        ket_luan="can_xem",
        muc_do="nghiem_trong",
        chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
        mo_ta=(
            f"Nguy cơ dị ứng chéo cùng nhóm {du.nhom_duoc_ly} giữa "
            f"{same_group_hc.ten_hoat_chat} ({label}) và tiền sử dị ứng {du.tac_nhan}"
        ),
        can_cu=[_build_allergy_evidence(du)],
    )


def _check_allergy_status(ca: CaBenh, all_line_ids: list[str]) -> list[PhatHien] | None:
    """Xử lý hai nhánh trạng thái chưa có thông tin và không dị ứng đã hỏi."""
    status = ca.tinh_trang_di_ung

    if status.trang_thai == "chua_co_thong_tin":
        return [
            PhatHien(
                ma_luat="di_ung_thieu_thong_tin",
                yeu_to=_YEU_TO,
                ket_luan="khong_du_du_lieu",
                muc_do=None,
                chi_tiet_y_lenh_id=all_line_ids,
                mo_ta="Hồ sơ chưa có thông tin dị ứng",
                can_cu=[
                    CanCu(
                        loai="du_lieu",
                        ban_ghi_id=None,
                        mo_ta="Trạng thái dị ứng: chua_co_thong_tin",
                    ),
                ],
                thong_tin_con_thieu=["tinh_trang_di_ung"],
            ),
        ]

    if status.trang_thai == "khong_di_ung_da_hoi":
        source_part = f" từ {status.nguon}" if status.nguon else ""
        time_part = f" lúc {status.thoi_diem.isoformat()}" if status.thoi_diem else ""
        return [
            PhatHien(
                ma_luat="di_ung_khong_co",
                yeu_to=_YEU_TO,
                ket_luan="dat",
                muc_do="thong_tin",
                chi_tiet_y_lenh_id=all_line_ids,
                mo_ta="Người bệnh đã được khai thác: không có tiền sử dị ứng",
                can_cu=[
                    CanCu(
                        loai="du_lieu",
                        ban_ghi_id=None,
                        mo_ta=f"Đã khai thác không dị ứng{source_part}{time_part}",
                    ),
                ],
            ),
        ]

    return None


def _legacy_check(ca: CaBenh) -> list[PhatHien]:
    """Kiểm tra dị ứng theo logic cũ khi chưa có bộ phân giải hoặc bảng chéo."""
    lines = pending_lines(ca)
    all_line_ids = [line.chi_tiet_y_lenh_id for line in lines]
    early = _check_allergy_status(ca, all_line_ids)
    if early is not None:
        return early

    thuoc_by_id = {thuoc.thuoc_id: thuoc for thuoc in ca.danh_muc_thuoc}
    matched_findings: list[PhatHien] = []
    unknown_findings: list[PhatHien] = []
    known_line_ids: list[str] = []

    for line in lines:
        if line.thuoc_id is None or line.thuoc_id.strip() == "":
            label = line_label(line, thuoc_by_id)
            unknown_desc = f"Sản phẩm gõ tay '{label}' chưa rõ thành phần để đối chiếu dị ứng"
            unknown_findings.append(
                PhatHien(
                    ma_luat="di_ung_san_pham_khong_ro",
                    yeu_to=_YEU_TO,
                    ket_luan="khong_du_du_lieu",
                    muc_do=None,
                    chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                    mo_ta=unknown_desc,
                    can_cu=[
                        CanCu(
                            loai="du_lieu",
                            ban_ghi_id=line.chi_tiet_y_lenh_id,
                            mo_ta=f"Dòng '{label}' không có mã thuốc trong danh mục",
                        ),
                    ],
                    thong_tin_con_thieu=["thanh_phan_san_pham"],
                ),
            )
            continue

        known_line_ids.append(line.chi_tiet_y_lenh_id)
        ingredients = ingredients_of(ca, line)
        for du in ca.di_ung:
            finding = _match_line_allergy(line, ingredients, du, thuoc_by_id)
            if finding is not None:
                matched_findings.append(finding)

    if not matched_findings and known_line_ids:
        no_match = PhatHien(
            ma_luat="di_ung_khong_khop",
            yeu_to=_YEU_TO,
            ket_luan="dat",
            muc_do="thong_tin",
            chi_tiet_y_lenh_id=known_line_ids,
            mo_ta="Không phát hiện trùng hoạt chất hoặc nhóm dược lý với tiền sử dị ứng",
            can_cu=[_build_allergy_evidence(du) for du in ca.di_ung],
        )
        return [*unknown_findings, no_match]

    return [*matched_findings, *unknown_findings]


def _extract_resolved_ids(result: KetQuaPhanGiai) -> set[str]:
    """Lấy tập mã hoạt chất trên trục từ kết quả phân giải đã hoặc một phần nhận diện."""
    if result.trang_thai not in {"da_phan_giai", "mot_phan"}:
        return set()
    return {tp.hoat_chat_id for tp in result.thanh_phan if tp.hoat_chat_id}


def _is_line_excluded(result: KetQuaPhanGiai) -> bool:
    """Kiểm tra dòng thuốc thuộc nhóm dịch truyền, điện giải hoặc dược liệu."""
    if result.trang_thai == "khong_ap_dung":
        return True
    return bool(result.thanh_phan) and all(
        tp.loai in _EXCLUDED_KINDS for tp in result.thanh_phan
    )


def _resolve_allergen(
    du: DiUng,
    resolver: DrugResolver,
    config: AllergyCrossConfig,
) -> _ResolvedAllergen | None:
    """Phân giải bản ghi dị ứng thuốc theo 4 bước ưu tiên."""
    if du.hoat_chat_id:
        axis = getattr(resolver, "_axis", {})
        case_codes = getattr(resolver, "_case_codes", {})
        if du.hoat_chat_id.startswith("HC-") or du.hoat_chat_id in case_codes:
            mapped = case_codes.get(du.hoat_chat_id)
            if mapped:
                return _ResolvedAllergen(du=du, ingredient_ids=frozenset({mapped}))
        elif not axis or du.hoat_chat_id in axis:
            return _ResolvedAllergen(du=du, ingredient_ids=frozenset({du.hoat_chat_id}))

    direct = resolver.resolve_name(du.tac_nhan)
    direct_ids = _extract_resolved_ids(direct)
    if direct_ids:
        return _ResolvedAllergen(du=du, ingredient_ids=frozenset(direct_ids))

    stripped = strip_parenthetical(du.tac_nhan)
    if stripped and stripped != du.tac_nhan.strip():
        stripped_res = resolver.resolve_name(stripped)
        stripped_ids = _extract_resolved_ids(stripped_res)
        if stripped_ids:
            return _ResolvedAllergen(du=du, ingredient_ids=frozenset(stripped_ids))

    alias = config.resolve_group_alias(du.tac_nhan)
    if alias is not None:
        return _ResolvedAllergen(
            du=du,
            ingredient_ids=frozenset(alias.hoat_chat_ids),
            group_alias=alias,
        )

    return None


def _build_cross_source_evidence(group: AllergyCrossGroup, src: CrossSource) -> CanCu:
    """Tạo căn cứ tài liệu cho một nguồn trích dẫn từ bảng dị ứng chéo."""
    if src.set_id:
        ref = f"Nhãn FDA {src.ten_nhan or ''} (set_id={src.set_id})".strip()
    elif src.doi:
        title = src.tieu_de or "Tổng quan"
        ref = f"{title} (doi={src.doi})"
    elif src.pmid:
        title = src.tieu_de or "Tổng quan"
        ref = f"{title} (pmid={src.pmid})"
    else:
        ref = src.tieu_de or src.ten_nhan or src.loai
    return CanCu(
        loai="tai_lieu",
        ban_ghi_id=group.ma_nhom,
        mo_ta=(
            f'[{group.ma_nhom}] {ref}: "{src.trich_nguyen_van}" — {src.url} '
            "(chờ dược sĩ duyệt)"
        ),
    )


def _dedupe_evidences(evidences: list[CanCu]) -> list[CanCu]:
    """Loại bỏ căn cứ trùng lặp nhưng giữ nguyên thứ tự xuất hiện."""
    seen: set[tuple[str, str | None, str]] = set()
    unique: list[CanCu] = []
    for item in evidences:
        key = (item.loai, item.ban_ghi_id, item.mo_ta)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _build_line_unknown_finding(
    line: ChiTietYLenh,
    label: str,
    result: KetQuaPhanGiai,
) -> PhatHien:
    """Tạo phát hiện thiếu dữ liệu khi dòng y lệnh chưa phân giải trọn vẹn thành phần."""
    reason = f" ({result.ly_do})" if result.ly_do else ""
    prefix = (
        "Phân giải được một phần thành phần"
        if result.trang_thai == "mot_phan"
        else "Chưa nhận diện được thành phần thuốc"
    )
    return PhatHien(
        ma_luat="di_ung_san_pham_khong_ro",
        yeu_to=_YEU_TO,
        ket_luan="khong_du_du_lieu",
        muc_do=None,
        chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
        mo_ta=f"{prefix} của '{label}' để đối chiếu dị ứng{reason}",
        can_cu=[
            CanCu(
                loai="du_lieu",
                ban_ghi_id=line.chi_tiet_y_lenh_id,
                mo_ta=(
                    f"Bộ phân giải trả trạng thái {result.trang_thai} "
                    f"cho '{label}'{reason}"
                ),
            ),
        ],
        thong_tin_con_thieu=["thanh_phan_san_pham"],
    )


def _build_direct_overlap_finding(
    du: DiUng,
    line: ChiTietYLenh,
    label: str,
    line_ids: set[str],
    overlap: list[str],
) -> PhatHien:
    """Tạo phát hiện trùng trực tiếp hoạt chất giữa tiền sử dị ứng và y lệnh."""
    overlap_text = ", ".join(overlap)
    resolved_text = ", ".join(sorted(line_ids))
    return PhatHien(
        ma_luat="di_ung_trung_hoat_chat",
        yeu_to=_YEU_TO,
        ket_luan="can_xem",
        muc_do="nghiem_trong",
        chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
        mo_ta=(
            f"Dị ứng {du.tac_nhan} trùng trực tiếp hoạt chất {overlap_text} "
            f"với y lệnh {label}"
        ),
        can_cu=[
            _build_allergy_evidence(du),
            CanCu(
                loai="du_lieu",
                ban_ghi_id=line.chi_tiet_y_lenh_id,
                mo_ta=f"Y lệnh {label} phân giải thành: {resolved_text}",
            ),
        ],
    )


def _build_cross_finding(
    du: DiUng,
    line: ChiTietYLenh,
    label: str,
    line_ids: set[str],
    matches: list[CrossMatch],
) -> PhatHien:
    """Tạo phát hiện dị ứng chéo hoặc cùng nhóm theo bảng dị ứng chéo."""
    primary = matches[0]
    muc_do, risk_phrase = _CROSS_RISK_DISPLAY[primary.related.muc_cheo]
    resolved_text = ", ".join(sorted(line_ids))
    evidences: list[CanCu] = [
        _build_allergy_evidence(du),
        CanCu(
            loai="du_lieu",
            ban_ghi_id=line.chi_tiet_y_lenh_id,
            mo_ta=f"Y lệnh {label} phân giải thành: {resolved_text}",
        ),
    ]
    seen_sources: set[tuple[str, str, str, str]] = set()
    for match in matches:
        for src in match.group.nguon:
            source_key = (
                src.set_id or "",
                src.doi or "",
                src.url,
                src.trich_nguyen_van,
            )
            if source_key in seen_sources:
                continue
            seen_sources.add(source_key)
            evidences.append(_build_cross_source_evidence(match.group, src))

    return PhatHien(
        ma_luat="di_ung_cheo",
        yeu_to=_YEU_TO,
        ket_luan="can_xem",
        muc_do=muc_do,
        chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
        mo_ta=(
            f"Dị ứng {du.tac_nhan}; y lệnh {label} ({resolved_text}): "
            f"{risk_phrase} ({primary.group.ten_nhom}; {primary.related.ly_do}). "
            "Bảng chéo chờ dược sĩ duyệt."
        ),
        can_cu=evidences,
    )


def _store_finding(
    by_key: dict[tuple[str, tuple[str, ...]], PhatHien],
    finding: PhatHien,
) -> None:
    """Gộp phát hiện trùng cặp (ma_luat, chi_tiet_y_lenh_id) để không ghi đè ở API."""
    key = (finding.ma_luat, tuple(finding.chi_tiet_y_lenh_id))
    existing = by_key.get(key)
    if existing is None:
        by_key[key] = finding
        return

    chosen_muc_do = existing.muc_do
    if finding.muc_do is not None and (
        existing.muc_do is None
        or _MUC_DO_ORDER[finding.muc_do] > _MUC_DO_ORDER[existing.muc_do]
    ):
        chosen_muc_do = finding.muc_do

    mo_ta = (
        existing.mo_ta
        if finding.mo_ta in existing.mo_ta
        else f"{existing.mo_ta}; {finding.mo_ta}"
    )
    by_key[key] = existing.model_copy(
        update={
            "muc_do": chosen_muc_do,
            "mo_ta": mo_ta,
            "can_cu": _dedupe_evidences([*existing.can_cu, *finding.can_cu]),
        }
    )


def check(
    ca: CaBenh,
    resolver: DrugResolver | None = None,
    config: AllergyCrossConfig | None = None,
) -> list[PhatHien]:
    """Kiểm tra dị ứng cho các dòng y lệnh chờ duyệt bằng bộ phân giải và bảng chéo."""
    if resolver is None:
        return _legacy_check(ca)

    active_config = config if config is not None else try_load_default_allergy_config()
    if active_config is None:
        return _legacy_check(ca)

    lines = pending_lines(ca)
    all_line_ids = [line.chi_tiet_y_lenh_id for line in lines]
    early = _check_allergy_status(ca, all_line_ids)
    if early is not None:
        return early

    thuoc_by_id = {thuoc.thuoc_id: thuoc for thuoc in ca.danh_muc_thuoc}
    resolved_allergens: list[_ResolvedAllergen] = []
    unresolved_allergies: list[DiUng] = []
    for du in ca.di_ung:
        if du.loai_tac_nhan != "thuoc":
            continue
        resolved = _resolve_allergen(du, resolver, active_config)
        if resolved is None:
            unresolved_allergies.append(du)
        else:
            resolved_allergens.append(resolved)

    evaluable_line_ids: list[str] = []
    known_line_ids: list[str] = []
    unknown_findings: list[PhatHien] = []
    matched_by_key: dict[tuple[str, tuple[str, ...]], PhatHien] = {}

    for line in lines:
        result = resolver.resolve_line(ca, line)
        if _is_line_excluded(result):
            continue

        evaluable_line_ids.append(line.chi_tiet_y_lenh_id)
        label = line_label(line, thuoc_by_id)
        line_ids = _extract_resolved_ids(result)
        is_line_unresolved = result.trang_thai in {"khong_nhan_dien", "mot_phan"} or not line_ids
        if is_line_unresolved:
            unknown_findings.append(_build_line_unknown_finding(line, label, result))
        else:
            known_line_ids.append(line.chi_tiet_y_lenh_id)

        if not line_ids:
            continue

        for allergen in resolved_allergens:
            if allergen.group_alias is None:
                overlap = sorted(allergen.ingredient_ids & line_ids)
                if overlap:
                    finding = _build_direct_overlap_finding(
                        allergen.du, line, label, line_ids, overlap
                    )
                    _store_finding(matched_by_key, finding)
                    continue

            matches = active_config.find_cross_matches(
                set(allergen.ingredient_ids),
                line_ids,
                alias=allergen.group_alias,
            )
            if matches:
                finding = _build_cross_finding(allergen.du, line, label, line_ids, matches)
                _store_finding(matched_by_key, finding)

    unresolved_allergy_findings: list[PhatHien] = []
    if unresolved_allergies and evaluable_line_ids:
        names = ", ".join(f'"{du.tac_nhan}"' for du in unresolved_allergies)
        unresolved_allergy_findings.append(
            PhatHien(
                ma_luat="di_ung_tac_nhan_khong_ro",
                yeu_to=_YEU_TO,
                ket_luan="khong_du_du_lieu",
                muc_do=None,
                chi_tiet_y_lenh_id=evaluable_line_ids,
                mo_ta=f"Chưa nhận diện được hoạt chất của tác nhân dị ứng {names}",
                can_cu=[_build_allergy_evidence(du) for du in unresolved_allergies],
                thong_tin_con_thieu=["hoat_chat_tac_nhan_di_ung"],
            )
        )

    matched_findings = list(matched_by_key.values())
    if not matched_findings and not unresolved_allergy_findings and known_line_ids:
        no_match = PhatHien(
            ma_luat="di_ung_khong_khop",
            yeu_to=_YEU_TO,
            ket_luan="dat",
            muc_do="thong_tin",
            chi_tiet_y_lenh_id=known_line_ids,
            mo_ta=(
                "Không phát hiện trùng hoạt chất hoặc nguy cơ dị ứng chéo "
                "theo bảng với tiền sử dị ứng"
            ),
            can_cu=[_build_allergy_evidence(du) for du in ca.di_ung],
        )
        return [*unknown_findings, no_match]

    return [*matched_findings, *unresolved_allergy_findings, *unknown_findings]
