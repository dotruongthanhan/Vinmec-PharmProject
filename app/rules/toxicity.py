"""Luật yếu tố 5 (D6): độc thận, kéo dài QT, khoảng điều trị hẹp, độc gan và thuốc nguy cơ cao."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from app.calc.renal import cockcroft_gault
from app.domain.loader import latest_lab, latest_vital
from app.domain.models import CaBenh, ChiTietYLenh, KetQuaXetNghiem
from app.rules.d6_config import (
    LiverToxEntry,
    ToxicityConfig,
    ToxicitySource,
    try_load_default_toxicity_config,
)
from app.rules.types import (
    CanCu,
    PhatHien,
    effective_lines,
    line_label,
    normalize_text,
    pending_lines,
)

if TYPE_CHECKING:
    from app.kb.resolver import DrugResolver
    from app.kb.resolver.resolver import KetQuaPhanGiai

_YEU_TO = 5
_EXCLUDED_KINDS = {"dich_truyen_dien_giai", "duoc_lieu"}
_LIVERTOX_HIGH_SCORES = {"A", "B"}
_LIVERTOX_SCORE_RANK: dict[str, int] = {
    "A": 0,
    "B": 1,
    "C": 2,
    "D": 3,
    "E": 4,
    "E*": 5,
    "X": 6,
}


@dataclass(frozen=True)
class _ResolvedLine:
    """Thông tin một dòng thuốc sau khi phân giải qua DrugResolver."""

    line: ChiTietYLenh
    label: str
    is_pending: bool
    ingredient_ids: tuple[str, ...]
    ingredient_names: dict[str, str]
    is_unresolved: bool
    unresolved_reason: str | None


def _is_line_excluded(result: KetQuaPhanGiai) -> bool:
    """Kiểm tra dòng thuốc thuộc nhóm dịch truyền, điện giải hoặc dược liệu."""
    if result.trang_thai == "khong_ap_dung":
        return True
    if result.trang_thai == "mot_phan":
        return False
    return bool(result.thanh_phan) and all(tp.loai in _EXCLUDED_KINDS for tp in result.thanh_phan)


def _resolve_effective_lines(ca: CaBenh, resolver: DrugResolver) -> list[_ResolvedLine]:
    """Phân giải toàn bộ các dòng đang hiệu lực, bỏ nhóm không áp dụng."""
    pending_ids = {line.chi_tiet_y_lenh_id for line in pending_lines(ca)}
    thuoc_by_id = {thuoc.thuoc_id: thuoc for thuoc in ca.danh_muc_thuoc}
    resolved_items: list[_ResolvedLine] = []

    for line in effective_lines(ca):
        result = resolver.resolve_line(ca, line)
        if _is_line_excluded(result):
            continue

        label = line_label(line, thuoc_by_id)
        ingredient_ids: list[str] = []
        ingredient_names: dict[str, str] = {}
        if result.trang_thai in {"da_phan_giai", "mot_phan"}:
            for tp in result.thanh_phan:
                if tp.loai in _EXCLUDED_KINDS:
                    continue
                hc_id = normalize_text(tp.hoat_chat_id)
                if not hc_id:
                    continue
                if hc_id not in ingredient_names:
                    ingredient_ids.append(hc_id)
                    ingredient_names[hc_id] = tp.ten_inn or tp.hoat_chat_id

        is_unresolved = result.trang_thai in {"khong_nhan_dien", "mot_phan"} or not ingredient_ids
        resolved_items.append(
            _ResolvedLine(
                line=line,
                label=label,
                is_pending=line.chi_tiet_y_lenh_id in pending_ids,
                ingredient_ids=tuple(ingredient_ids),
                ingredient_names=ingredient_names,
                is_unresolved=is_unresolved,
                unresolved_reason=result.ly_do,
            )
        )

    return resolved_items


def _dedupe_ids(ids: list[str]) -> list[str]:
    """Loại bỏ mã trùng lặp nhưng giữ nguyên thứ tự xuất hiện."""
    return list(dict.fromkeys(ids))


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


def _format_source_evidence(src: ToxicitySource) -> CanCu:
    """Tạo căn cứ tài liệu theo chuẩn trích dẫn nhãn FDA hoặc LiverTox."""
    if src.loai == "livertox" or (src.ma_chuyen_luan and not src.set_id):
        chapter = src.ma_chuyen_luan or src.ten_nhan or "không rõ"
        prefix = f"LiverTox chương {chapter}"
        record_id = src.ma_chuyen_luan
    elif src.loai == "nhan_fda" or src.set_id:
        name = f"Nhãn FDA {src.ten_nhan.strip()}" if src.ten_nhan else "Nhãn FDA"
        prefix = f"{name} (set_id={src.set_id})" if src.set_id else name
        record_id = src.set_id
    else:
        prefix = src.ten_nhan or src.loai
        record_id = src.set_id or src.ma_chuyen_luan
    url_part = f" — {src.url}" if src.url else ""
    return CanCu(
        loai="tai_lieu",
        ban_ghi_id=record_id,
        mo_ta=f'{prefix}: "{src.trich_nguyen_van}"{url_part} (chờ dược sĩ duyệt)',
    )


def _line_origin_text(item: _ResolvedLine) -> str:
    """Mô tả ngắn nguồn gốc dòng thuốc (chờ duyệt hoặc đang dùng)."""
    if item.is_pending:
        return "y lệnh chờ duyệt"
    return f"thuốc đang dùng ({item.line.trang_thai_dong})"


def _crcl_evidences(ca: CaBenh) -> tuple[list[CanCu], str | None]:
    """Tính CrCl Cockcroft-Gault để bổ sung căn cứ; thiếu đầu vào không chặn phát hiện."""
    weight_vital = latest_vital(ca, "can_nang")
    creatinin_lab = latest_lab(ca, "creatinin")
    can_nang_kg = weight_vital.gia_tri if weight_vital is not None else None
    creatinin_val = creatinin_lab.gia_tri_so if creatinin_lab is not None else None
    creatinin_unit = creatinin_lab.don_vi if creatinin_lab is not None else None

    evidences: list[CanCu] = []
    if creatinin_lab is not None:
        val = creatinin_lab.gia_tri_so if creatinin_lab.gia_tri_so is not None else "không rõ"
        unit = creatinin_lab.don_vi or "không rõ đơn vị"
        cr_time = creatinin_lab.thoi_diem_ket_qua.isoformat()
        evidences.append(
            CanCu(
                loai="du_lieu",
                ban_ghi_id=creatinin_lab.xet_nghiem_id,
                mo_ta=f"Creatinin máu: {val} {unit} lúc {cr_time}",
            )
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
            )
        )

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
        evidences.append(
            CanCu(
                loai="tinh_toan",
                ban_ghi_id="cockcroft_gault",
                mo_ta=f"Không tính được CrCl do số liệu bất thường: {exc}",
            )
        )
        return evidences, None

    if calc_res.ket_qua is None:
        missing_text = ", ".join(calc_res.thieu_dau_vao)
        evidences.append(
            CanCu(
                loai="tinh_toan",
                ban_ghi_id="cockcroft_gault",
                mo_ta=f"Thiếu đầu vào tính CrCl: {missing_text}",
            )
        )
        return evidences, None

    assert weight_vital is not None
    crcl_display = f"{calc_res.ket_qua:.1f}"
    evidences.append(
        CanCu(
            loai="tinh_toan",
            ban_ghi_id="cockcroft_gault",
            mo_ta=(
                f"CrCl = {crcl_display} mL/min "
                f"(cân nặng thuc_te: {weight_vital.gia_tri} {weight_vital.don_vi})"
            ),
        )
    )
    return evidences, crcl_display


def _build_missing_ingredient_finding(
    ma_luat: str,
    rule_label: str,
    matched_lines: list[_ResolvedLine],
    unresolved_lines: list[_ResolvedLine],
) -> PhatHien:
    """Tạo phát hiện thiếu dữ liệu hoạt chất khi chưa thể loại trừ tổ hợp độc tính."""
    line_ids = _dedupe_ids(
        [
            *(item.line.chi_tiet_y_lenh_id for item in matched_lines),
            *(item.line.chi_tiet_y_lenh_id for item in unresolved_lines),
        ]
    )
    unresolved_labels = ", ".join(f"'{item.label}'" for item in unresolved_lines)
    evidences = [
        CanCu(
            loai="du_lieu",
            ban_ghi_id=item.line.chi_tiet_y_lenh_id,
            mo_ta=(
                f"Dòng '{item.label}' ({_line_origin_text(item)}) chưa nhận diện đủ hoạt chất"
                + (f" ({item.unresolved_reason})" if item.unresolved_reason else "")
            ),
        )
        for item in unresolved_lines
    ]
    return PhatHien(
        ma_luat=ma_luat,
        yeu_to=_YEU_TO,
        ket_luan="khong_du_du_lieu",
        muc_do=None,
        chi_tiet_y_lenh_id=line_ids,
        mo_ta=f"Chưa đủ dữ liệu hoạt chất cho {unresolved_labels} để loại trừ {rule_label}",
        can_cu=_dedupe_evidences(evidences),
        thong_tin_con_thieu=["hoat_chat"],
    )


def _doc_than_cong_don(
    ca: CaBenh,
    resolved_items: list[_ResolvedLine],
    config: ToxicityConfig,
) -> list[PhatHien]:
    """Đánh giá cộng dồn độc thận từ danh sách dòng đã phân giải."""
    nephro_map = config.nephrotoxic_map()
    matched_hc_order: list[str] = []
    matched_lines: list[_ResolvedLine] = []
    matched_line_ids: set[str] = set()
    line_matched_names: dict[str, list[str]] = {}
    unresolved_lines: list[_ResolvedLine] = []

    for item in resolved_items:
        if item.is_unresolved:
            unresolved_lines.append(item)
        matched_here: list[str] = []
        for hc_id in item.ingredient_ids:
            if hc_id not in nephro_map:
                continue
            if hc_id not in matched_hc_order:
                matched_hc_order.append(hc_id)
            matched_here.append(item.ingredient_names.get(hc_id, hc_id))
        if matched_here:
            line_id = item.line.chi_tiet_y_lenh_id
            line_matched_names[line_id] = matched_here
            if line_id not in matched_line_ids:
                matched_line_ids.add(line_id)
                matched_lines.append(item)

    if len(matched_hc_order) >= 2 and any(item.is_pending for item in matched_lines):
        has_renal_impairment = any(
            cd.loai == "suy_than" and cd.trang_thai == "co" for cd in ca.co_dia
        )
        muc_do: Literal["nghiem_trong", "can_luu_y"] = (
            "nghiem_trong" if has_renal_impairment else "can_luu_y"
        )
        crcl_evidences, crcl_display = _crcl_evidences(ca)

        evidences: list[CanCu] = []
        drug_parts: list[str] = []
        for item in matched_lines:
            line_id = item.line.chi_tiet_y_lenh_id
            names_text = ", ".join(line_matched_names[line_id])
            drug_parts.append(f"{item.label} ({names_text})")
            evidences.append(
                CanCu(
                    loai="du_lieu",
                    ban_ghi_id=line_id,
                    mo_ta=(
                        f"{item.label} ({_line_origin_text(item)}): hoạt chất độc thận {names_text}"
                    ),
                )
            )
        if has_renal_impairment:
            evidences.append(
                CanCu(
                    loai="du_lieu",
                    ban_ghi_id=None,
                    mo_ta="Cơ địa người bệnh: suy_than (trang_thai=co)",
                )
            )
        evidences.extend(crcl_evidences)
        for hc_id in matched_hc_order:
            for entry in nephro_map[hc_id]:
                for src in entry.nguon:
                    evidences.append(_format_source_evidence(src))

        crcl_note = f"; CrCl = {crcl_display} mL/min" if crcl_display is not None else ""
        renal_note = "; người bệnh có cơ địa suy thận" if has_renal_impairment else ""
        return [
            PhatHien(
                ma_luat="doc_than_cong_don",
                yeu_to=_YEU_TO,
                ket_luan="can_xem",
                muc_do=muc_do,
                chi_tiet_y_lenh_id=[item.line.chi_tiet_y_lenh_id for item in matched_lines],
                mo_ta=(
                    f"Cộng dồn nguy cơ độc thận khi phối hợp {len(matched_hc_order)} hoạt chất "
                    f"cùng lúc: {', '.join(drug_parts)}{renal_note}{crcl_note}"
                ),
                can_cu=_dedupe_evidences(evidences),
            )
        ]

    if unresolved_lines and (
        any(item.is_pending for item in unresolved_lines)
        or any(item.is_pending for item in matched_lines)
    ):
        return [
            _build_missing_ingredient_finding(
                "doc_than_cong_don_thieu_du_lieu",
                "cộng dồn độc thận",
                matched_lines,
                unresolved_lines,
            )
        ]

    return []


def doc_than_cong_don(
    ca: CaBenh,
    resolver: DrugResolver,
    config: ToxicityConfig,
) -> list[PhatHien]:
    """Kiểm tra phối hợp đồng thời ≥ 2 hoạt chất độc thận."""
    resolved_items = _resolve_effective_lines(ca, resolver)
    return _doc_than_cong_don(ca, resolved_items, config)


def _keo_dai_qt_cong_don(
    resolved_items: list[_ResolvedLine],
    config: ToxicityConfig,
) -> list[PhatHien]:
    """Đánh giá cộng dồn kéo dài khoảng QT từ danh sách dòng đã phân giải."""
    qt_map = config.qt_map()
    matched_hc_order: list[str] = []
    matched_lines: list[_ResolvedLine] = []
    matched_line_ids: set[str] = set()
    line_matched_desc: dict[str, list[str]] = {}
    unresolved_lines: list[_ResolvedLine] = []

    for item in resolved_items:
        if item.is_unresolved:
            unresolved_lines.append(item)
        here_desc: list[str] = []
        for hc_id in item.ingredient_ids:
            if hc_id not in qt_map:
                continue
            if hc_id not in matched_hc_order:
                matched_hc_order.append(hc_id)
            entries = qt_map[hc_id]
            sections_raw: list[str] = []
            for entry in entries:
                if entry.muc_nhan:
                    sections_raw.append(entry.muc_nhan)
                else:
                    sections_raw.extend(src.truong_nhan for src in entry.nguon if src.truong_nhan)
            sections = _dedupe_ids(sections_raw)
            section_text = ", ".join(sections) if sections else "cảnh báo nhãn"
            hc_name = item.ingredient_names.get(hc_id, hc_id)
            here_desc.append(f"{hc_name} (mục nhãn: {section_text})")
        if here_desc:
            line_id = item.line.chi_tiet_y_lenh_id
            line_matched_desc[line_id] = here_desc
            if line_id not in matched_line_ids:
                matched_line_ids.add(line_id)
                matched_lines.append(item)

    if len(matched_hc_order) >= 2 and any(item.is_pending for item in matched_lines):
        evidences: list[CanCu] = []
        drug_parts: list[str] = []
        for item in matched_lines:
            line_id = item.line.chi_tiet_y_lenh_id
            desc = "; ".join(line_matched_desc[line_id])
            drug_parts.append(f"{item.label} [{desc}]")
            evidences.append(
                CanCu(
                    loai="du_lieu",
                    ban_ghi_id=line_id,
                    mo_ta=f"{item.label} ({_line_origin_text(item)}): {desc}",
                )
            )
        for hc_id in matched_hc_order:
            for entry in qt_map[hc_id]:
                for src in entry.nguon:
                    evidences.append(_format_source_evidence(src))

        return [
            PhatHien(
                ma_luat="keo_dai_qt_cong_don",
                yeu_to=_YEU_TO,
                ket_luan="can_xem",
                muc_do="can_luu_y",
                chi_tiet_y_lenh_id=[item.line.chi_tiet_y_lenh_id for item in matched_lines],
                mo_ta=(
                    f"Cộng dồn nguy cơ kéo dài khoảng QT khi dùng {len(matched_hc_order)} "
                    f"hoạt chất cùng lúc: {', '.join(drug_parts)}"
                ),
                can_cu=_dedupe_evidences(evidences),
            )
        ]

    if unresolved_lines and (
        any(item.is_pending for item in unresolved_lines)
        or any(item.is_pending for item in matched_lines)
    ):
        return [
            _build_missing_ingredient_finding(
                "keo_dai_qt_cong_don_thieu_du_lieu",
                "cộng dồn kéo dài QT",
                matched_lines,
                unresolved_lines,
            )
        ]

    return []


def keo_dai_qt_cong_don(
    ca: CaBenh,
    resolver: DrugResolver,
    config: ToxicityConfig,
) -> list[PhatHien]:
    """Kiểm tra phối hợp đồng thời ≥ 2 hoạt chất kéo dài khoảng QT."""
    resolved_items = _resolve_effective_lines(ca, resolver)
    return _keo_dai_qt_cong_don(resolved_items, config)


def _khoang_dieu_tri_hep(
    ca: CaBenh,
    resolved_items: list[_ResolvedLine],
    config: ToxicityConfig,
) -> list[PhatHien]:
    """Kiểm tra theo dõi nồng độ cho các dòng chờ duyệt thuộc khoảng điều trị hẹp."""
    narrow_map = config.narrow_map()
    findings: list[PhatHien] = []

    for item in resolved_items:
        if not item.is_pending:
            continue
        line_id = item.line.chi_tiet_y_lenh_id
        for hc_id in item.ingredient_ids:
            if hc_id not in narrow_map:
                continue
            entries = narrow_map[hc_id]
            hc_name = item.ingredient_names.get(hc_id, hc_id)
            target_codes = {
                normalize_text(code)
                for entry in entries
                for code in entry.ma_xet_nghiem_nong_do
                if normalize_text(code)
            }
            source_evidences = [
                _format_source_evidence(src) for entry in entries for src in entry.nguon
            ]
            matching_labs = [
                xn for xn in ca.xet_nghiem if normalize_text(xn.ma_xet_nghiem) in target_codes
            ]
            if matching_labs:
                latest = max(matching_labs, key=lambda xn: xn.thoi_diem_ket_qua)
                val_str = (
                    f"{latest.gia_tri_so} {latest.don_vi or ''}".strip()
                    if latest.gia_tri_so is not None
                    else (latest.gia_tri_text or "không rõ")
                )
                time_str = latest.thoi_diem_ket_qua.isoformat()
                findings.append(
                    PhatHien(
                        ma_luat="nong_do_da_theo_doi",
                        yeu_to=_YEU_TO,
                        ket_luan="dat",
                        muc_do="thong_tin",
                        chi_tiet_y_lenh_id=[line_id],
                        mo_ta=(
                            f"{item.label} ({hc_name}): thuốc khoảng điều trị hẹp, đã có kết quả "
                            f"nồng độ {latest.ten_xet_nghiem}: {val_str} lúc {time_str}"
                        ),
                        can_cu=_dedupe_evidences(
                            [
                                CanCu(
                                    loai="du_lieu",
                                    ban_ghi_id=latest.xet_nghiem_id,
                                    mo_ta=(
                                        f"Xét nghiệm {latest.ten_xet_nghiem} "
                                        f"({latest.ma_xet_nghiem}): {val_str} lúc {time_str}"
                                    ),
                                ),
                                *source_evidences,
                            ]
                        ),
                    )
                )
            else:
                findings.append(
                    PhatHien(
                        ma_luat="nong_do_chua_theo_doi",
                        yeu_to=_YEU_TO,
                        ket_luan="can_xem",
                        muc_do="can_luu_y",
                        chi_tiet_y_lenh_id=[line_id],
                        mo_ta=(
                            f"{item.label} ({hc_name}): nhãn khuyến cáo theo dõi nồng độ; "
                            "hồ sơ chưa có kết quả"
                        ),
                        can_cu=_dedupe_evidences(
                            [
                                CanCu(
                                    loai="du_lieu",
                                    ban_ghi_id=line_id,
                                    mo_ta=(
                                        f"Hồ sơ chưa có xét nghiệm nồng độ "
                                        f"({', '.join(sorted(target_codes)) or hc_id})"
                                    ),
                                ),
                                *source_evidences,
                            ]
                        ),
                    )
                )

    return findings


def khoang_dieu_tri_hep(
    ca: CaBenh,
    resolver: DrugResolver,
    config: ToxicityConfig,
) -> list[PhatHien]:
    """Kiểm tra theo dõi nồng độ thuốc có khoảng điều trị hẹp trên y lệnh chờ duyệt."""
    resolved_items = _resolve_effective_lines(ca, resolver)
    return _khoang_dieu_tri_hep(ca, resolved_items, config)


def _latest_lab_ci(ca: CaBenh, code: str) -> KetQuaXetNghiem | None:
    """Tìm kết quả xét nghiệm mới nhất không phân biệt hoa thường ở ma_xet_nghiem."""
    target = normalize_text(code)
    matches = [xn for xn in ca.xet_nghiem if normalize_text(xn.ma_xet_nghiem) == target]
    if not matches:
        return None
    return max(matches, key=lambda xn: xn.thoi_diem_ket_qua)


def _format_lab_summary(lab: KetQuaXetNghiem) -> str:
    """Định dạng ngắn gọn kết quả xét nghiệm kèm ngưỡng trên và thời điểm."""
    val = (
        f"{lab.gia_tri_so} {lab.don_vi or ''}".strip()
        if lab.gia_tri_so is not None
        else (lab.gia_tri_text or "không rõ")
    )
    upper = f" (ngưỡng trên: {lab.nguong_tren})" if lab.nguong_tren is not None else ""
    return f"{lab.ten_xet_nghiem} = {val}{upper} lúc {lab.thoi_diem_ket_qua.isoformat()}"


def _pick_livertox_entry(entries: list[LiverToxEntry]) -> LiverToxEntry:
    """Chọn bản ghi LiverTox có mức khả năng cao nhất khi có nhiều dòng cùng hoạt chất."""
    return min(
        entries,
        key=lambda item: _LIVERTOX_SCORE_RANK.get(item.likelihood_score.strip().upper(), 99),
    )


def _doc_gan_livertox(
    ca: CaBenh,
    resolved_items: list[_ResolvedLine],
    config: ToxicityConfig,
) -> list[PhatHien]:
    """Kiểm tra độc gan LiverTox mức A/B đối chiếu ALT, AST mới nhất với nguong_tren."""
    alt_lab = _latest_lab_ci(ca, "alt")
    ast_lab = _latest_lab_ci(ca, "ast")
    present_labs = [lab for lab in (alt_lab, ast_lab) if lab is not None]
    numeric_labs = [lab for lab in present_labs if lab.gia_tri_so is not None]
    if not numeric_labs:
        return []

    liver_map = config.livertox_map()
    findings: list[PhatHien] = []

    for item in resolved_items:
        if not item.is_pending:
            continue
        line_id = item.line.chi_tiet_y_lenh_id
        for hc_id in item.ingredient_ids:
            if hc_id not in liver_map:
                continue
            entries = liver_map[hc_id]
            primary = _pick_livertox_entry(entries)
            score = primary.likelihood_score.strip().upper()
            if score not in _LIVERTOX_HIGH_SCORES:
                continue

            hc_name = item.ingredient_names.get(hc_id, hc_id)
            source_evidences = [
                _format_source_evidence(src) for entry in entries for src in entry.nguon
            ]
            lab_evidences = [
                CanCu(
                    loai="du_lieu",
                    ban_ghi_id=lab.xet_nghiem_id,
                    mo_ta=_format_lab_summary(lab),
                )
                for lab in present_labs
            ]

            elevated = [
                lab
                for lab in numeric_labs
                if lab.nguong_tren is not None
                and lab.gia_tri_so is not None
                and lab.gia_tri_so > lab.nguong_tren
            ]
            if elevated:
                elevated_text = "; ".join(_format_lab_summary(lab) for lab in elevated)
                findings.append(
                    PhatHien(
                        ma_luat="doc_gan_men_gan_tang",
                        yeu_to=_YEU_TO,
                        ket_luan="can_xem",
                        muc_do="can_luu_y",
                        chi_tiet_y_lenh_id=[line_id],
                        mo_ta=(
                            f"{item.label} ({hc_name}, LiverTox {score}): "
                            f"men gan vượt ngưỡng trên ({elevated_text})"
                        ),
                        can_cu=_dedupe_evidences([*lab_evidences, *source_evidences]),
                    )
                )
                continue

            missing_upper = [lab for lab in numeric_labs if lab.nguong_tren is None]
            if missing_upper:
                findings.append(
                    PhatHien(
                        ma_luat="doc_gan_thieu_xet_nghiem",
                        yeu_to=_YEU_TO,
                        ket_luan="khong_du_du_lieu",
                        muc_do=None,
                        chi_tiet_y_lenh_id=[line_id],
                        mo_ta=(
                            f"{item.label} ({hc_name}, LiverTox {score}): "
                            "kết quả ALT/AST thiếu nguong_tren của phòng xét nghiệm"
                        ),
                        can_cu=_dedupe_evidences([*lab_evidences, *source_evidences]),
                        thong_tin_con_thieu=["nguong_tren_alt_ast"],
                    )
                )
                continue

            normal_text = "; ".join(_format_lab_summary(lab) for lab in numeric_labs)
            findings.append(
                PhatHien(
                    ma_luat="doc_gan_men_gan_binh_thuong",
                    yeu_to=_YEU_TO,
                    ket_luan="dat",
                    muc_do="thong_tin",
                    chi_tiet_y_lenh_id=[line_id],
                    mo_ta=(
                        f"{item.label} ({hc_name}, LiverTox {score}): "
                        f"ALT/AST không vượt ngưỡng trên ({normal_text})"
                    ),
                    can_cu=_dedupe_evidences([*lab_evidences, *source_evidences]),
                )
            )

    return findings


def doc_gan_livertox(
    ca: CaBenh,
    resolver: DrugResolver,
    config: ToxicityConfig,
) -> list[PhatHien]:
    """Kiểm tra độc gan LiverTox mức A/B đối chiếu ALT, AST của ca."""
    resolved_items = _resolve_effective_lines(ca, resolver)
    return _doc_gan_livertox(ca, resolved_items, config)


def thuoc_nguy_co_cao(ca: CaBenh) -> list[PhatHien]:
    """Kiểm tra cờ la_thuoc_nguy_co_cao trong danh mục thuốc của ca cho y lệnh chờ duyệt."""
    thuoc_by_id = {thuoc.thuoc_id: thuoc for thuoc in ca.danh_muc_thuoc}
    findings: list[PhatHien] = []

    for line in pending_lines(ca):
        if line.thuoc_id is None:
            continue
        thuoc = thuoc_by_id.get(line.thuoc_id)
        if thuoc is None or not thuoc.la_thuoc_nguy_co_cao:
            continue
        findings.append(
            PhatHien(
                ma_luat="thuoc_nguy_co_cao",
                yeu_to=_YEU_TO,
                ket_luan="can_xem",
                muc_do="thong_tin",
                chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                mo_ta=(
                    f"{thuoc.ten_thuoc}: thuốc thuộc danh mục nguy cơ cao của viện: "
                    "kiểm tra kép liều, đường dùng"
                ),
                can_cu=[
                    CanCu(
                        loai="du_lieu",
                        ban_ghi_id=thuoc.thuoc_id,
                        mo_ta=(
                            f"Danh mục thuốc của ca: {thuoc.ten_thuoc} (la_thuoc_nguy_co_cao=True)"
                        ),
                    )
                ],
            )
        )

    return findings


def check(
    ca: CaBenh,
    resolver: DrugResolver | None = None,
    config: ToxicityConfig | None = None,
    renal_rules: Any = None,
) -> list[PhatHien]:
    """Rà soát yếu tố 5 (độc tính) cho y lệnh chờ duyệt."""
    del renal_rules
    if resolver is None:
        return []

    active_config = config if config is not None else try_load_default_toxicity_config()
    if active_config is None:
        return thuoc_nguy_co_cao(ca)

    resolved_items = _resolve_effective_lines(ca, resolver)
    return [
        *_doc_than_cong_don(ca, resolved_items, active_config),
        *_keo_dai_qt_cong_don(resolved_items, active_config),
        *_khoang_dieu_tri_hep(ca, resolved_items, active_config),
        *_doc_gan_livertox(ca, resolved_items, active_config),
        *thuoc_nguy_co_cao(ca),
    ]
