"""Luật yếu tố 2: trùng hoạt chất trên trục và trùng nhóm theo cấu hình ATC."""

from itertools import combinations, product

from app.domain.loader import ingredients_of
from app.domain.models import CaBenh, ChiTietYLenh
from app.kb.resolver import DrugResolver
from app.kb.resolver.resolver import ThanhPhanPhanGiai
from app.rules.duplicate_config import DuplicateConfig, load_duplicate_config
from app.rules.types import CanCu, PhatHien, effective_lines, line_label, pending_lines

_YEU_TO = 2
_EXCLUDED = {"dich_truyen_dien_giai", "duoc_lieu"}


def _ingredient_findings(ca: CaBenh, ingredients: dict[str, dict[str, str]]) -> list[PhatHien]:
    """So khóa hoạt chất, mỗi dòng chỉ được đếm một lần cho mỗi khóa."""
    pending = pending_lines(ca)
    pending_ids = {line.chi_tiet_y_lenh_id for line in pending}
    effective = effective_lines(ca)
    thuoc_by_id = {thuoc.thuoc_id: thuoc for thuoc in ca.danh_muc_thuoc}

    lines_by_hc: dict[str, list[ChiTietYLenh]] = {}
    names: dict[str, str] = {}
    for line in effective:
        for identifier, name in ingredients.get(line.chi_tiet_y_lenh_id, {}).items():
            names[identifier] = name
            lines_by_hc.setdefault(identifier, []).append(line)

    findings: list[PhatHien] = []
    for hoat_chat_id, lines_for_hc in lines_by_hc.items():
        if len(lines_for_hc) < 2:
            continue
        if not any(line.chi_tiet_y_lenh_id in pending_ids for line in lines_for_hc):
            continue

        name = names[hoat_chat_id]
        evidences: list[CanCu] = []
        for line in lines_for_hc:
            label = line_label(line, thuoc_by_id)
            origin = (
                "y lệnh chờ duyệt"
                if line.chi_tiet_y_lenh_id in pending_ids
                else f"thuốc đang dùng ({line.trang_thai_dong})"
            )
            evidences.append(
                CanCu(
                    loai="du_lieu",
                    ban_ghi_id=line.chi_tiet_y_lenh_id,
                    mo_ta=f"{label} ({origin}) chứa {name}",
                ),
            )

        dup_desc = f"Trùng hoạt chất {name} ở {len(lines_for_hc)} dòng đang hiệu lực"
        findings.append(
            PhatHien(
                ma_luat="trung_hoat_chat",
                yeu_to=_YEU_TO,
                ket_luan="can_xem",
                muc_do="can_luu_y",
                chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id for line in lines_for_hc],
                mo_ta=dup_desc,
                can_cu=evidences,
            ),
        )

    return findings


def _group_findings(
    ca: CaBenh,
    components: dict[str, list[ThanhPhanPhanGiai]],
    config: DuplicateConfig,
    notes: list[CanCu],
) -> list[PhatHien]:
    """Xét hai dòng khác nhau, loại cặp cùng hoạt chất và cặp ngoại lệ."""
    pending = {line.chi_tiet_y_lenh_id for line in pending_lines(ca)}
    catalog = {drug.thuoc_id: drug for drug in ca.danh_muc_thuoc}
    findings: list[PhatHien] = []
    for a, b in combinations(effective_lines(ca), 2):
        ids = [a.chi_tiet_y_lenh_id, b.chi_tiet_y_lenh_id]
        if not pending.intersection(ids):
            continue
        for group in config.nhom_dieu_tri.nhom:
            exceptions = {frozenset(pair) for pair in group.ngoai_le}
            for ia, ib in product(components.get(ids[0], []), components.get(ids[1], [])):
                if ia.hoat_chat_id == ib.hoat_chat_id:
                    continue
                codes_a = group.matching_codes(ia.ma_atc)
                codes_b = group.matching_codes(ib.ma_atc)
                if not codes_a or not codes_b:
                    continue
                label_a = f"{line_label(a, catalog)} ({ia.ten_inn}, {', '.join(codes_a)})"
                label_b = f"{line_label(b, catalog)} ({ib.ten_inn}, {', '.join(codes_b)})"
                source = CanCu(
                    loai="tai_lieu",
                    ban_ghi_id=group.ma_nhom,
                    mo_ta=(
                        f"Nhóm {group.ten}: {group.ly_do} Nguồn: {group.nguon}; "
                        "chờ dược sĩ duyệt bảng nhóm."
                    ),
                )
                if frozenset((ia.hoat_chat_id, ib.hoat_chat_id)) in exceptions:
                    notes.extend(
                        [
                            CanCu(
                                loai="du_lieu",
                                mo_ta=f"Ngoại lệ nhóm {group.ten}: {label_a} và {label_b}.",
                            ),
                            source,
                        ]
                    )
                    continue
                findings.append(
                    PhatHien(
                        ma_luat="trung_nhom_dieu_tri",
                        yeu_to=_YEU_TO,
                        ket_luan="can_xem",
                        muc_do=group.muc_do,
                        chi_tiet_y_lenh_id=ids,
                        mo_ta=(
                            f"Trùng nhóm {group.ten}: {label_a} và {label_b}. "
                            "Nếu đang chuyển thuốc, kiểm lịch ngừng thuốc cũ."
                        ),
                        can_cu=[
                            CanCu(loai="du_lieu", ban_ghi_id=ids[0], mo_ta=label_a),
                            CanCu(loai="du_lieu", ban_ghi_id=ids[1], mo_ta=label_b),
                            source,
                        ],
                    )
                )
    return findings


def _check_resolved(ca: CaBenh, resolver: DrugResolver, config: DuplicateConfig) -> list[PhatHien]:
    """Đánh giá thuần trong bộ nhớ, giữ rõ dòng và trường còn thiếu."""
    effective = effective_lines(ca)
    catalog = {drug.thuoc_id: drug for drug in ca.danh_muc_thuoc}
    components: dict[str, list[ThanhPhanPhanGiai]] = {}
    missing: dict[str, str] = {}
    fields: list[str] = []
    notes: list[CanCu] = []
    for line in effective:
        identifier = line.chi_tiet_y_lenh_id
        label = line_label(line, catalog)
        result = resolver.resolve_line(ca, line)
        if result.trang_thai == "khong_ap_dung":
            notes.append(
                CanCu(
                    loai="du_lieu",
                    ban_ghi_id=identifier,
                    mo_ta=f"{label}: không áp dụng ({result.ly_do or 'phân loại bộ phân giải'}).",
                )
            )
            continue
        if result.trang_thai in {"khong_nhan_dien", "mot_phan"} or not result.thanh_phan:
            reason = (
                "chưa nhận diện được hoạt chất"
                if result.trang_thai == "khong_nhan_dien" or not result.thanh_phan
                else "mới phân giải một phần hoạt chất"
            )
            missing[identifier] = f"{label} {reason} ({result.ly_do or 'thiếu hoạt chất'})"
            fields.append(f"{identifier}.hoat_chat_id")
        rows: list[ThanhPhanPhanGiai] = []
        for row in result.thanh_phan:
            if row.loai in _EXCLUDED:
                notes.append(
                    CanCu(
                        loai="du_lieu",
                        ban_ghi_id=identifier,
                        mo_ta=f"{label}: {row.ten_inn} không áp dụng ({row.loai}).",
                    )
                )
                continue
            extra = config.atc_bo_sung.ma_atc.get(row.hoat_chat_id, [])
            codes = list(dict.fromkeys([*row.ma_atc, *extra]))
            rows.append(row.model_copy(update={"ma_atc": codes}))
            if extra:
                notes.append(
                    CanCu(
                        loai="tai_lieu",
                        ban_ghi_id=identifier,
                        mo_ta=(
                            f"{row.ten_inn}: ATC bổ sung {', '.join(extra)}; "
                            f"nguồn {config.atc_bo_sung.nguon}; chờ Claude kiểm."
                        ),
                    )
                )
        components[identifier] = rows
        without_atc = [row for row in rows if not row.ma_atc]
        if without_atc:
            names = ", ".join(row.ten_inn for row in without_atc)
            reason = f"{label}: {names} thiếu ma_atc"
            notes.append(CanCu(loai="du_lieu", ban_ghi_id=identifier, mo_ta=reason))
            if not any(row.ma_atc for row in rows):
                missing[identifier] = "; ".join(filter(None, [missing.get(identifier), reason]))
                fields.extend(f"{identifier}.{row.hoat_chat_id}.ma_atc" for row in without_atc)

    ingredients = {
        identifier: {row.hoat_chat_id: row.ten_inn for row in rows}
        for identifier, rows in components.items()
    }
    findings = _ingredient_findings(ca, ingredients)
    findings.extend(_group_findings(ca, components, config, notes))
    if findings:
        for finding in findings:
            finding.can_cu.extend(notes)
            finding.can_cu.extend(
                CanCu(loai="du_lieu", ban_ghi_id=identifier, mo_ta=reason)
                for identifier, reason in missing.items()
            )
        return findings
    if missing:
        return [
            PhatHien(
                ma_luat="trung_nhom_dieu_tri_thieu_du_lieu",
                yeu_to=_YEU_TO,
                ket_luan="khong_du_du_lieu",
                muc_do=None,
                chi_tiet_y_lenh_id=list(missing),
                mo_ta="Chưa đủ dữ liệu để loại trừ trùng nhóm: "
                + "; ".join(missing.values())
                + ".",
                can_cu=[
                    *notes,
                    *[
                        CanCu(loai="du_lieu", ban_ghi_id=identifier, mo_ta=reason)
                        for identifier, reason in missing.items()
                    ],
                ],
                thong_tin_con_thieu=fields,
            )
        ]
    count = len({key for rows in ingredients.values() for key in rows})
    notes.append(
        CanCu(
            loai="tai_lieu",
            mo_ta=(
                "Đối chiếu theo tiền tố ATC của các nhóm: "
                + ", ".join(group.ten for group in config.nhom_dieu_tri.nhom)
                + "; chờ dược sĩ duyệt bảng nhóm."
            ),
        )
    )
    return [
        PhatHien(
            ma_luat="trung_hoat_chat_khong_co",
            yeu_to=_YEU_TO,
            ket_luan="dat",
            muc_do="thong_tin",
            chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id for line in pending_lines(ca)],
            mo_ta=(
                f"Đã đối chiếu {len(effective)} dòng thuốc đang hiệu lực ({count} hoạt chất) "
                f"theo {len(config.nhom_dieu_tri.nhom)} nhóm điều trị: "
                "không có trùng hoạt chất hay trùng nhóm."
            ),
            can_cu=notes,
        )
    ]


def check(
    ca: CaBenh, resolver: DrugResolver | None = None, config: DuplicateConfig | None = None
) -> list[PhatHien]:
    """Nạp cấu hình ngoài phần đánh giá; thiếu resolver thì giữ luật cũ."""
    if resolver is not None:
        return _check_resolved(
            ca, resolver, config if config is not None else load_duplicate_config()
        )
    ingredients = {
        line.chi_tiet_y_lenh_id: {
            row.hoat_chat_id: row.ten_hoat_chat for row in ingredients_of(ca, line)
        }
        for line in effective_lines(ca)
    }
    findings = _ingredient_findings(ca, ingredients)
    if findings:
        return findings
    return [
        PhatHien(
            ma_luat="trung_hoat_chat_khong_co",
            yeu_to=_YEU_TO,
            ket_luan="dat",
            muc_do="thong_tin",
            chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id for line in pending_lines(ca)],
            mo_ta="Không có hoạt chất trùng lặp trong các dòng thuốc đang hiệu lực",
            can_cu=[
                CanCu(
                    loai="du_lieu",
                    mo_ta=f"Đã đối chiếu {len(effective_lines(ca))} dòng thuốc đang hiệu lực",
                )
            ],
        )
    ]
