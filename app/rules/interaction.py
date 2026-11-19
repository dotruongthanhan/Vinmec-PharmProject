"""Luật yếu tố 4 và ma trận thuần dùng dữ liệu DDInter để sàng lọc."""

import logging
from dataclasses import dataclass, field
from itertools import combinations, product

from app.domain.models import CaBenh
from app.kb.interactions import InteractionStore
from app.kb.interactions.models import (
    SEVERITIES,
    CapMaTran,
    MaTranTuongTac,
    PairRecord,
    Severity,
    ThuocMaTran,
    TuongTacThucAn,
)
from app.kb.resolver import DrugResolver
from app.kb.resolver.resolver import KetQuaPhanGiai
from app.rules.engine import _priority_key
from app.rules.types import CanCu, PhatHien, effective_lines, line_label, pending_lines

_LOGGER = logging.getLogger(__name__)
_EXCLUDED = {"dich_truyen_dien_giai", "duoc_lieu"}
_SOURCE = "DDInter 2.0 (sàng lọc, CC BY-NC-SA 4.0)"
_NOTE = (
    "Sàng lọc, cần đối chiếu nhãn. Không phát hiện chỉ khi cả hai hoạt chất có danh sách "
    "DDInter đã cào đủ; dữ liệu thiếu không loại trừ tương tác."
)
_PAIR_LEVELS = {"Major": "nghiem_trong", "Moderate": "can_luu_y", "Minor": "can_luu_y"}
_FOOD_LEVELS = {
    "Major": "nghiem_trong",
    "Moderate": "can_luu_y",
    "Minor": "thong_tin",
    "Unknown": "chua_ro",
}
_SOURCE_SENTENCE = "Nguồn sàng lọc, cần đối chiếu nhãn."
_SEVERITY_LABELS = {
    "Major": "mức nặng",
    "Moderate": "mức trung bình",
    "Minor": "mức nhẹ",
    "Unknown": "chưa rõ",
}


def _severity_text(severity: Severity) -> str:
    """Giữ mức nguồn trong ngoặc sau nhãn tiếng Việt."""
    return f"{_SEVERITY_LABELS[severity]} (DDInter: {severity})"


def _interaction_text(record: PairRecord) -> str:
    """Diễn đạt mức và cơ chế, không lặp tên cặp thuốc."""
    if record.muc_do == "Unknown":
        return f"chưa đủ dữ liệu tương tác: mức {_severity_text(record.muc_do)}"
    mechanism = ", ".join(record.co_che) or "chưa có dữ liệu"
    return (
        f"tương tác {_SEVERITY_LABELS[record.muc_do]} "
        f"(DDInter: {record.muc_do}, cơ chế {mechanism})"
    )


@dataclass
class PairAssessment:
    """Căn cứ nội bộ, không gắn vào PhatHien hoặc trả ra API."""

    pair: CapMaTran
    records: list[tuple[str, PairRecord]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


def _assess_pair(
    a: ThuocMaTran,
    b: ThuocMaTran,
    ra: KetQuaPhanGiai,
    rb: KetQuaPhanGiai,
    store: InteractionStore,
) -> PairAssessment:
    result = PairAssessment(
        CapMaTran(
            a=a.chi_tiet_y_lenh_id,
            b=b.chi_tiet_y_lenh_id,
            muc="khong_ap_dung",
            tom_tat=None,
            ly_do=None,
        )
    )
    if "khong_ap_dung" in {ra.trang_thai, rb.trang_thai}:
        result.pair.ly_do = "; ".join(
            f"{drug.ten}: {resolved.ly_do or 'Dịch truyền, điện giải hoặc dược liệu'}"
            for drug, resolved in ((a, ra), (b, rb))
            if resolved.trang_thai == "khong_ap_dung"
        )
        return result
    ca = [row for row in ra.thanh_phan if row.loai not in _EXCLUDED]
    cb = [row for row in rb.thanh_phan if row.loai not in _EXCLUDED]
    if (
        ra.trang_thai == rb.trang_thai == "da_phan_giai"
        and ca
        and cb
        and {row.hoat_chat_id for row in ca} == {row.hoat_chat_id for row in cb}
    ):
        result.pair.ly_do = "trùng hoạt chất – xem yếu tố 2"
        return result
    for drug, resolved, components in ((a, ra, ca), (b, rb, cb)):
        if resolved.trang_thai in {"mot_phan", "khong_nhan_dien"} or not components:
            result.missing.append(
                f"chưa phân giải đủ hoạt chất: {resolved.ly_do or 'thiếu hoạt chất đã phân giải'}"
            )
        for component in components:
            if component.ddinter_id is None:
                ingredient = f" cho {component.ten_inn}" if component.ten_inn != drug.ten else ""
                result.missing.append(f"chưa có dữ liệu DDInter{ingredient} (thiếu ddinter_id)")
    checked = 0
    for ia, ib in product(ca, cb):
        if ia.hoat_chat_id == ib.hoat_chat_id:
            continue
        checked += 1
        if ia.ddinter_id is None or ib.ddinter_id is None:
            continue
        label = f"{ia.ten_inn} × {ib.ten_inn}"
        record = store.pair(ia.ddinter_id, ib.ddinter_id)
        if record is not None:
            result.records.append((label, record))
            if record.muc_do == "Unknown":
                result.missing.append("DDInter ghi mức chưa rõ (Unknown)")
        elif not (store.drug_complete(ia.ddinter_id) and store.drug_complete(ib.ddinter_id)):
            result.missing.append("danh sách DDInter chưa cào đủ hoặc chưa có dữ liệu thuốc")
    result.missing = list(dict.fromkeys(result.missing))
    result.records.sort(key=lambda item: (SEVERITIES.index(item[1].muc_do), item[0]))
    positive = [row for row in result.records if row[1].muc_do != "Unknown"]
    if positive:
        result.pair.muc = _PAIR_LEVELS[positive[0][1].muc_do]
    elif result.missing:
        result.pair.muc = "thieu_du_lieu"
    elif checked:
        result.pair.muc = "khong_phat_hien"
    else:
        result.pair.ly_do = "trùng hoạt chất – xem yếu tố 2"
    if result.records:
        result.pair.tom_tat = "; ".join(
            f"{label}: {_interaction_text(row)}" for label, row in result.records
        )
    if result.missing:
        result.pair.ly_do = "; ".join(result.missing)
    return result


def _evaluate(
    ca: CaBenh,
    resolver: DrugResolver,
    store: InteractionStore,
) -> tuple[MaTranTuongTac, list[PairAssessment]]:
    lines = effective_lines(ca)
    pending = {row.chi_tiet_y_lenh_id for row in pending_lines(ca)}
    catalog = {row.thuoc_id: row for row in ca.danh_muc_thuoc}
    resolved = [resolver.resolve_line(ca, line) for line in lines]
    drugs = [
        ThuocMaTran(
            chi_tiet_y_lenh_id=line.chi_tiet_y_lenh_id,
            ten=line_label(line, catalog),
            nhom="cho_duyet" if line.chi_tiet_y_lenh_id in pending else "dang_dung",
            phan_giai=result.trang_thai,
            hoat_chat=[row.ten_inn for row in result.thanh_phan],
            ly_do=result.ly_do,
        )
        for line, result in zip(lines, resolved, strict=True)
    ]
    assessments = [
        _assess_pair(drugs[i], drugs[j], resolved[i], resolved[j], store)
        for i, j in combinations(range(len(drugs)), 2)
    ]
    foods = []
    for drug, result in zip(drugs, resolved, strict=True):
        for component in result.thanh_phan:
            if component.ddinter_id is None or component.loai in _EXCLUDED:
                continue
            for food in store.foods(component.ddinter_id):
                foods.append(
                    TuongTacThucAn(
                        chi_tiet_y_lenh_id=drug.chi_tiet_y_lenh_id,
                        hoat_chat=component.ten_inn,
                        thuc_an=food.thuc_an,
                        muc=_FOOD_LEVELS[food.muc_do],
                        mo_ta=food.mo_ta,
                        xu_tri=food.xu_tri,
                    )
                )
    return MaTranTuongTac(
        nguon=_SOURCE,
        ghi_chu=_NOTE,
        thuoc=drugs,
        cap=[result.pair for result in assessments],
        thuc_an=foods,
    ), assessments


def build_interaction_matrix(
    ca: CaBenh,
    resolver: DrugResolver,
    store: InteractionStore,
) -> MaTranTuongTac:
    """Tính mọi cặp dòng; presenter nối mã nhận định từ kết quả luật thực tế."""
    return _evaluate(ca, resolver, store)[0]


def _evidence(label: str, record: PairRecord) -> CanCu:
    parts = [
        f"{_SOURCE}; tầng 4; {label}; {_severity_text(record.muc_do)}",
        f"Cơ chế: {', '.join(record.co_che) or 'thiếu'}",
        f"Hậu quả: {record.hau_qua or 'thiếu'}",
        f"Xử trí: {record.xu_tri or 'thiếu'}",
        f"Tài liệu: {'; '.join(record.tai_lieu) or 'thiếu'}",
        f"URL: {record.url_goc or 'thiếu'}",
    ]
    if record.co_lech_muc:
        source_levels = ", ".join(_severity_text(level) for level in record.cac_muc_nguon)
        parts.append(f"Lệch mức nguồn: {source_levels}; lấy mức cao nhất")
        parts.append(
            "Mức trên là mức cao nhất của cặp; cơ chế gộp từ các quan sát. "
            "Hậu quả và xử trí lấy từ trang đã cào, ưu tiên cùng mức; "
            "có thể thuộc trang mức khác. Cần đối chiếu URL nguồn."
        )
    return CanCu(loai="tai_lieu", mo_ta="\n".join(parts))


def check_with_matrix(
    ca: CaBenh,
    resolver: DrugResolver | None = None,
    store: InteractionStore | None = None,
) -> tuple[list[PhatHien], MaTranTuongTac | None]:
    """Tính một lần, trả phát hiện và ma trận cho cùng phiên bản ca."""
    if resolver is None or store is None:
        _LOGGER.warning("Không chạy yếu tố 4: thiếu chỉ mục tra cứu hoặc bảng tương tác DDInter")
        return [], None
    matrix, assessments = _evaluate(ca, resolver, store)
    pending = {row.chi_tiet_y_lenh_id for row in pending_lines(ca)}
    names = {row.chi_tiet_y_lenh_id: row.ten for row in matrix.thuoc}
    findings = []
    for result in assessments:
        pair = result.pair
        if not pending.intersection((pair.a, pair.b)):
            continue
        if pair.muc not in {"nghiem_trong", "can_luu_y", "thieu_du_lieu"}:
            continue
        missing = pair.muc == "thieu_du_lieu"
        severity = result.records[0][1].muc_do if result.records else None
        description = f"{names[pair.a]} × {names[pair.b]}: "
        description += (
            f"chưa đủ dữ liệu tương tác: {pair.ly_do}"
            if missing
            else _interaction_text(result.records[0][1])
        )
        evidences = [_evidence(label, record) for label, record in result.records]
        if not evidences:
            evidences = [CanCu(loai="tai_lieu", mo_ta=f"{_SOURCE}; tầng 4. {pair.ly_do}")]
        findings.append(
            PhatHien(
                ma_luat="tuong_tac_thieu_du_lieu" if missing else "tuong_tac_thuoc",
                yeu_to=4,
                ket_luan="khong_du_du_lieu" if missing else "can_xem",
                muc_do=None if missing else "thong_tin" if severity == "Minor" else pair.muc,
                chi_tiet_y_lenh_id=[pair.a, pair.b],
                mo_ta=f"{description}. {_SOURCE_SENTENCE}",
                can_cu=evidences,
                thong_tin_con_thieu=result.missing,
            )
        )
    if not findings:
        checked_pairs = [
            pair
            for pair in matrix.cap
            if pending.intersection((pair.a, pair.b)) and pair.muc != "khong_ap_dung"
        ]
        if len(matrix.thuoc) == 1:
            description = (
                "Y lệnh chỉ có một thuốc đang hiệu lực, không có cặp để đối chiếu tương tác."
            )
        elif not matrix.thuoc:
            description = (
                "Y lệnh không có thuốc đang hiệu lực, không có cặp để đối chiếu tương tác."
            )
        elif not checked_pairs:
            description = "Không có cặp thuốc áp dụng đối chiếu tương tác ở dòng chờ duyệt."
        else:
            description = (
                f"Đã đối chiếu {len(checked_pairs)} cặp thuốc, "
                "không phát hiện tương tác trong dữ liệu DDInter. "
                f"{_SOURCE_SENTENCE}"
            )
        findings.append(
            PhatHien(
                ma_luat="tuong_tac_thuoc_khong_co",
                yeu_to=4,
                ket_luan="dat",
                muc_do="thong_tin",
                chi_tiet_y_lenh_id=[row.chi_tiet_y_lenh_id for row in pending_lines(ca)],
                mo_ta=description,
                can_cu=[
                    CanCu(
                        loai="tai_lieu",
                        mo_ta=f"{_SOURCE}; đã đối chiếu {len(checked_pairs)} cặp có dòng chờ duyệt",
                    )
                ],
            )
        )
    return sorted(findings, key=_priority_key), matrix


def check(
    ca: CaBenh,
    resolver: DrugResolver | None = None,
    store: InteractionStore | None = None,
) -> list[PhatHien]:
    """Giữ giao diện luật chỉ trả danh sách phát hiện cho registry."""
    return check_with_matrix(ca, resolver, store)[0]
