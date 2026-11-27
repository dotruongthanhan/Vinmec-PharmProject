"""Dựng bộ dữ liệu thời gian từ ca hiện tại cho công cụ minh hoạ."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.agent.minh_hoa.models import BoDuLieu, CotDuLieu
from app.agent.tools.base import CanCu, KetQuaCongCu, Tool, ToolContext
from app.calc.units import creatinine_to_mg_dl
from app.domain.loader import latest_vital
from app.domain.models import CaBenh, ChiTietYLenh, HoatChat, ThanhPhan, Thuoc
from app.kb.dictionary.axis import VIET_TO_INTERNATIONAL
from app.kb.names import normalize_key
from app.kb.resolver.resolver import ThanhPhanPhanGiai
from app.rules.d5_config import (
    is_same_route_or_iv,
    normalize_route_default,
    try_load_default_max_dose_config,
)
from app.rules.max_dose import (
    _convert_line_dose,
    _limit_to_mg,
    _matches_population,
    _special_condition_text,
    _weight_in_kg,
)
from app.tracing import span

Phan = Literal["xet_nghiem", "sinh_hieu", "lich_dung", "khang_sinh", "moc_ca"]
Ma = Annotated[str, StringConstraints(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")]
GiaTri = str | float | bool | None
Dong = dict[str, GiaTri]
_MAX_DONG = 2000


class ThamSoLayDuLieuCa(BaseModel):
    """Chỉ chọn phần và bộ lọc, không cho truyền mã ca."""

    model_config = ConfigDict(extra="forbid")

    phan: list[Phan] = Field(min_length=1, max_length=5)
    ma_xet_nghiem: list[Ma] | None = Field(default=None, max_length=10)
    loai_sinh_hieu: list[Ma] | None = Field(default=None, max_length=10)

    @field_validator("phan")
    @classmethod
    def unique_parts(cls, value: list[Phan]) -> list[Phan]:
        if len(value) != len(set(value)):
            raise ValueError("Phần dữ liệu không được trùng")
        return value


_LABELS = {
    "thoi_diem": "Thời điểm",
    "ma_xet_nghiem": "Mã xét nghiệm",
    "ten_xet_nghiem": "Tên xét nghiệm",
    "gia_tri": "Giá trị",
    "don_vi": "Đơn vị",
    "nguong_duoi": "Ngưỡng dưới",
    "nguong_tren": "Ngưỡng trên",
    "ngoai_nguong": "Ngoài ngưỡng",
    "creatinin_tang_nhanh": "Creatinin tăng nhanh (KDIGO)",
    "loai": "Loại",
    "thuoc": "Thuốc",
    "hoat_chat": "Hoạt chất",
    "lieu": "Liều",
    "nguon_lich": "Nguồn lịch",
    "tong_24h_lon_nhat": "Tổng 24 giờ lớn nhất",
    "cua_so_tu": "Cửa sổ từ",
    "cua_so_den": "Cửa sổ đến",
    "lieu_toi_da_ngay": "Liều tối đa ngày",
    "vuot": "Vượt",
    "so_che_pham": "Số chế phẩm",
    "bat_dau": "Bắt đầu",
    "ket_thuc": "Kết thúc",
    "dang_dung": "Đang dùng",
    "chua_bat_dau": "Chưa bắt đầu",
    "ngay_thu": "Ngày thứ",
    "trang_thai_dong": "Trạng thái",
    "thoi_diem_lay_mau": "Thời điểm lấy mẫu",
    "benh_pham": "Bệnh phẩm",
    "vi_khuan": "Vi khuẩn",
    "ket_qua": "Kết quả",
    "mic": "MIC",
    "nhan": "Nhãn",
}


def _columns(*items: tuple[str, str]) -> list[CotDuLieu]:
    return [CotDuLieu(ten=name, kieu=kind, nhan=_LABELS[name]) for name, kind in items]  # type: ignore[arg-type]


def _text(value: str | None, limit: int = 200) -> str | None:
    return value[:limit] if value is not None else None


def _lab_rows(ca: CaBenh, selected: list[str] | None) -> list[Dong]:
    labs = sorted(ca.xet_nghiem, key=lambda lab: lab.thoi_diem_ket_qua)
    # Hai hàng đợi đơn điệu lưu giá trị thấp nhất trong các cửa sổ trước đó.
    window_48: deque[tuple[datetime, float]] = deque()
    window_7: deque[tuple[datetime, float]] = deque()
    rows: list[Dong] = []
    for lab in labs:
        time = lab.thoi_diem_ket_qua
        for window, duration in ((window_48, timedelta(hours=48)), (window_7, timedelta(days=7))):
            while window and time - window[0][0] > duration:
                window.popleft()
        is_creatinine = normalize_key(lab.ma_xet_nghiem) == "creatinin"
        rapid: bool | None = None
        if is_creatinine and lab.gia_tri_so is not None and lab.don_vi:
            try:
                factor = creatinine_to_mg_dl(1, "umol/L")
                value = creatinine_to_mg_dl(lab.gia_tri_so, lab.don_vi) / factor
            except ValueError:
                value = None
            if value is not None:
                if window_7:
                    rapid = bool(
                        (window_48 and value - window_48[0][1] >= 26.5)
                        or value >= 1.5 * window_7[0][1]
                    )
                for window in (window_48, window_7):
                    while window and window[-1][1] >= value:
                        window.pop()
                    window.append((time, value))
        if selected is not None and lab.ma_xet_nghiem not in selected:
            continue
        outside: bool | None = None
        if lab.gia_tri_so is not None:
            if (lab.nguong_duoi is not None and lab.gia_tri_so < lab.nguong_duoi) or (
                lab.nguong_tren is not None and lab.gia_tri_so > lab.nguong_tren
            ):
                outside = True
            elif lab.nguong_duoi is not None and lab.nguong_tren is not None:
                outside = False
        rows.append(
            {
                "thoi_diem": time.isoformat(),
                "ma_xet_nghiem": _text(lab.ma_xet_nghiem),
                "ten_xet_nghiem": _text(lab.ten_xet_nghiem),
                "gia_tri": lab.gia_tri_so,
                "don_vi": _text(lab.don_vi),
                "nguong_duoi": lab.nguong_duoi,
                "nguong_tren": lab.nguong_tren,
                "ngoai_nguong": outside,
                "creatinin_tang_nhanh": rapid,
            }
        )
    return rows


def _vital_rows(ca: CaBenh, selected: list[str] | None) -> list[Dong]:
    return [
        {
            "thoi_diem": vital.thoi_diem_do.isoformat(),
            "loai": _text(vital.loai),
            "gia_tri": vital.gia_tri,
            "don_vi": _text(vital.don_vi),
        }
        for vital in sorted(ca.sinh_hieu, key=lambda item: item.thoi_diem_do)
        if selected is None or vital.loai in selected
    ]


def _catalog(ca: CaBenh) -> tuple[dict[str, Thuoc], dict[str, str]]:
    return (
        {drug.thuoc_id: drug for drug in ca.danh_muc_thuoc},
        {item.hoat_chat_id: item.ten_hoat_chat for item in ca.danh_muc_hoat_chat},
    )


def _lines(ca: CaBenh) -> list[ChiTietYLenh]:
    return [*ca.thuoc_dang_dung, *ca.y_lenh_cho_duyet.chi_tiet]


def _dose(
    line: ChiTietYLenh, drug: Thuoc, component: ThanhPhan, amount: float, unit: str | None
) -> float | None:
    """Dùng phép quy đổi của D5; chỉ lấy kết quả đã quy về mg."""
    comp = ThanhPhanPhanGiai(
        hoat_chat_id=component.hoat_chat_id,
        ten_inn=component.hoat_chat_id,
        ten_viet=None,
        ma_atc=[],
        ddinter_id=None,
        loai="thuoc",
        ham_luong=component.ham_luong_thanh_phan,
        don_vi=component.don_vi,
    )
    converted = _convert_line_dose(
        line.model_copy(update={"lieu_moi_lan": amount, "don_vi_lieu": unit}),
        comp,
        drug,
        len(drug.thanh_phan),
    )
    return converted.value if converted.mode == "mass_mg" and amount >= 0 else None


def _axis_id(hc: HoatChat, known_ids: set[str]) -> str | None:
    """Dùng bảng tên sẵn có, chỉ chấp nhận một mã D5 duy nhất."""
    keys = {hc.hoat_chat_id}
    for name in (hc.ten_quoc_te, hc.ten_hoat_chat):
        key = normalize_key(name or "")
        keys.add(VIET_TO_INTERNATIONAL.get(key, key).replace(" ", "_"))
    keys.intersection_update(known_ids)
    return next(iter(keys)) if len(keys) == 1 else None


def _max_limit(ca: CaBenh, ingredient: str, lines: list[ChiTietYLenh]) -> float | None:
    config = try_load_default_max_dose_config()
    if config is None:
        return None
    hc = next((item for item in ca.danh_muc_hoat_chat if item.hoat_chat_id == ingredient), None)
    if hc is None:
        return None
    known_ids = {identifier for rule in config.nhom for identifier in rule.hoat_chat_ids}
    axis_id = _axis_id(hc, known_ids)
    if axis_id is None:
        return None
    weight = _weight_in_kg(latest_vital(ca, "can_nang"))
    all_limits: set[float] = set()
    for line in lines:
        route, _ = normalize_route_default(line.duong_dung)
        if route is None:
            return None
        matching: set[float] = set()
        for rule in config.nhom:
            if axis_id not in rule.hoat_chat_ids or rule.lieu_toi_da_ngay is None:
                continue
            if rule.loai_gioi_han == "gioi_han_thiet_bi" or _special_condition_text(rule, config):
                continue
            if rule.thuoc_dung_cung_hoat_chat_ids:
                continue
            if not any(
                is_same_route_or_iv(route, normalize_route_default(r)[0] or r)
                for r in rule.duong_dung
            ):
                continue
            applies, missing = _matches_population(rule, config, ca.nguoi_benh.tuoi, weight)
            if missing:
                return None
            if applies:
                limit, _ = _limit_to_mg(rule.lieu_toi_da_ngay)
                if limit is not None:
                    matching.add(limit)
        if len(matching) != 1:
            return None
        all_limits.update(matching)
    return next(iter(all_limits)) if len(all_limits) == 1 else None


def _schedule_rows(ca: CaBenh) -> tuple[list[Dong], list[Dong], set[str]]:
    drugs, names = _catalog(ca)
    config = try_load_default_max_dose_config()
    known_ids = (
        {identifier for rule in config.nhom for identifier in rule.hoat_chat_ids}
        if config is not None
        else set()
    )
    groups = {
        item.hoat_chat_id: _axis_id(item, known_ids) or item.hoat_chat_id
        for item in ca.danh_muc_hoat_chat
    }
    representatives: dict[str, str] = {}
    doses: list[tuple[datetime, Dong]] = []
    # Giá trị theo hoạt chất: liều có giờ, liều suy từ tần suất và dòng nguồn.
    events: dict[str, list[tuple[datetime, float, str]]] = defaultdict(list)
    inferred: dict[str, list[float]] = defaultdict(list)
    relevant: dict[str, list[ChiTietYLenh]] = defaultdict(list)
    missing: set[str] = set()
    incomplete: set[str] = set()
    for line in _lines(ca):
        drug = drugs.get(line.thuoc_id or "")
        label = _text(line.ten_tu_do or (drug.ten_thuoc if drug else None))
        if drug is None:
            missing.add("thanh_phan")
            if line.lich_dung:
                for event in line.lich_dung:
                    doses.append(
                        (
                            event.thoi_diem_du_kien,
                            {
                                "thoi_diem": event.thoi_diem_du_kien.isoformat(),
                                "thuoc": label,
                                "hoat_chat": None,
                                "lieu": None,
                                "don_vi": None,
                                "nguon_lich": "lich_dung",
                            },
                        )
                    )
            continue
        for component in drug.thanh_phan:
            hc = groups.get(component.hoat_chat_id, component.hoat_chat_id)
            representatives.setdefault(hc, component.hoat_chat_id)
            relevant[hc].append(line)
            if line.lich_dung:
                for event in line.lich_dung:
                    amount = _dose(line, drug, component, event.lieu, event.don_vi)
                    if amount is None:
                        missing.add("lieu_hoac_don_vi_thanh_phan")
                        incomplete.add(hc)
                    doses.append(
                        (
                            event.thoi_diem_du_kien,
                            {
                                "thoi_diem": event.thoi_diem_du_kien.isoformat(),
                                "thuoc": label,
                                "hoat_chat": _text(names.get(component.hoat_chat_id, hc)),
                                "lieu": amount,
                                "don_vi": "mg" if amount is not None else None,
                                "nguon_lich": "lich_dung",
                            },
                        )
                    )
                    if amount is not None:
                        events[hc].append((event.thoi_diem_du_kien, amount, drug.thuoc_id))
            elif (
                line.lieu_moi_lan is not None
                and line.so_lan_moi_ngay is not None
                and line.so_lan_moi_ngay > 0
            ):
                amount = _dose(line, drug, component, line.lieu_moi_lan, line.don_vi_lieu)
                if amount is None:
                    missing.add("lieu_hoac_don_vi_thanh_phan")
                    incomplete.add(hc)
                else:
                    inferred[hc].append(amount * line.so_lan_moi_ngay)
            else:
                missing.add("lich_dung_hoac_lieu_moi_lan_va_so_lan_moi_ngay")
                incomplete.add(hc)
    totals: list[tuple[datetime, Dong]] = []
    for hc, lines in relevant.items():
        ordered = sorted(events[hc], key=lambda event: event[0])
        max_sum: float | None = None
        end: datetime | None = None
        source = "lich_dung" if ordered else "suy_tu_tan_suat"
        if ordered and not inferred[hc] and hc not in incomplete:
            left = 0
            current = 0.0
            for at, amount, _ in ordered:
                current += amount
                while at - ordered[left][0] >= timedelta(hours=24):
                    current -= ordered[left][1]
                    left += 1
                if max_sum is None or current > max_sum:
                    max_sum, end = current, at
        elif not ordered and inferred[hc] and hc not in incomplete:
            reference = ca.y_lenh_cho_duyet.thoi_diem_ke
            overlapping = all(
                line.bat_dau <= reference
                and (line.ket_thuc is None or line.ket_thuc > reference)
                and line.trang_thai_dong in {"active", "pending"}
                for line in lines
            )
            if len(inferred[hc]) == 1 or overlapping:
                max_sum = sum(inferred[hc])
            else:
                missing.add("thoi_gian_dung_chong_lap")
        else:
            missing.add("lich_dung_day_du")
        representative = representatives[hc]
        limit = _max_limit(ca, representative, lines)
        if limit is None:
            missing.add("lieu_toi_da_ngay")
        totals.append(
            (
                end or max(line.bat_dau for line in lines),
                {
                    "hoat_chat": _text(names.get(representative, hc)),
                    "tong_24h_lon_nhat": max_sum,
                    "cua_so_tu": (end - timedelta(hours=24)).isoformat() if end else None,
                    "cua_so_den": end.isoformat() if end else None,
                    "lieu_toi_da_ngay": limit,
                    "vuot": max_sum > limit if max_sum is not None and limit is not None else None,
                    "so_che_pham": float(len({line.thuoc_id for line in lines if line.thuoc_id})),
                    "nguon_lich": source,
                },
            )
        )
    return (
        [row for _, row in sorted(doses, key=lambda item: item[0])],
        [row for _, row in sorted(totals, key=lambda item: item[0])],
        missing,
    )


def _antibiotic_rows(ca: CaBenh) -> tuple[list[Dong], list[Dong]]:
    drugs, names = _catalog(ca)
    reference = ca.y_lenh_cho_duyet.thoi_diem_ke
    courses: list[tuple[datetime, Dong]] = []
    for line in _lines(ca):
        drug = drugs.get(line.thuoc_id or "")
        if drug is None or not drug.la_khang_sinh:
            continue
        ongoing = (
            line.ket_thuc is None and line.trang_thai_dong == "active" and line.bat_dau <= reference
        )
        day = float((reference - line.bat_dau).days + 1) if reference >= line.bat_dau else None
        for component in drug.thanh_phan:
            courses.append(
                (
                    line.bat_dau,
                    {
                        "thuoc": _text(line.ten_tu_do or drug.ten_thuoc),
                        "hoat_chat": _text(
                            names.get(component.hoat_chat_id, component.hoat_chat_id)
                        ),
                        "bat_dau": line.bat_dau.isoformat(),
                        "ket_thuc": line.ket_thuc.isoformat() if line.ket_thuc else None,
                        "dang_dung": ongoing,
                        "chua_bat_dau": line.bat_dau > reference,
                        "ngay_thu": day,
                        "trang_thai_dong": line.trang_thai_dong,
                    },
                )
            )
    cultures: list[Dong] = []
    for sample in sorted(ca.vi_sinh, key=lambda item: item.thoi_diem_lay_mau):
        for susceptibility in sample.khang_sinh_do or [None]:
            cultures.append(
                {
                    "thoi_diem_lay_mau": sample.thoi_diem_lay_mau.isoformat(),
                    "benh_pham": _text(sample.benh_pham),
                    "vi_khuan": _text(sample.vi_khuan),
                    "hoat_chat": _text(
                        names.get(susceptibility.hoat_chat_id, susceptibility.hoat_chat_id)
                    )
                    if susceptibility
                    else None,
                    "ket_qua": susceptibility.ket_qua if susceptibility else None,
                    "mic": susceptibility.mic if susceptibility else None,
                }
            )
    return [row for _, row in sorted(courses, key=lambda item: item[0])], cultures


def _milestone_rows(ca: CaBenh) -> list[Dong]:
    drugs, _ = _catalog(ca)
    events: list[tuple[datetime, Dong]] = []

    def add(at: datetime, kind: str, label: str | None) -> None:
        events.append((at, {"thoi_diem": at.isoformat(), "loai": kind, "nhan": _text(label, 80)}))

    add(ca.dot_dieu_tri.thoi_diem_bat_dau, "vao_vien", "Vào viện")
    for line in _lines(ca):
        drug = drugs.get(line.thuoc_id or "")
        add(
            ca.y_lenh_cho_duyet.thoi_diem_ke
            if line in ca.y_lenh_cho_duyet.chi_tiet
            else line.bat_dau,
            "y_lenh",
            line.ten_tu_do or (drug.ten_thuoc if drug else None),
        )
    for lab in ca.xet_nghiem:
        add(lab.thoi_diem_ket_qua, "xet_nghiem", lab.ma_xet_nghiem)
    for sample in ca.vi_sinh:
        add(sample.thoi_diem_lay_mau, "vi_sinh", "Vi sinh")
    for record in ca.dien_bien:
        add(record.thoi_diem_ghi, "dien_bien", record.loai_ho_so)
    return [row for _, row in sorted(events, key=lambda item: item[0])]


def _summary(part: str, rows: list[Dong]) -> str:
    if not rows:
        return f"{part}: thiếu dữ liệu."
    if part in {"xet_nghiem", "sinh_hieu"}:
        key = "ma_xet_nghiem" if part == "xet_nghiem" else "loai"
        grouped: dict[str, list[Dong]] = defaultdict(list)
        for row in rows:
            grouped[str(row[key])].append(row)
        details: list[str] = []
        for name, values in list(grouped.items())[:10]:
            numeric = [r for r in values if r["gia_tri"] is not None]
            if numeric:
                first, last = numeric[0], numeric[-1]
                details.append(
                    f"{name}: {len(values)} lần, {first['gia_tri']} "
                    f"{first.get('don_vi') or 'thiếu đơn vị'} → {last['gia_tri']} "
                    f"{last.get('don_vi') or ''}"
                )
            else:
                details.append(f"{name}: {len(values)} lần, thiếu gia_tri_so")
        return "; ".join(details)
    if part == "lich_dung":
        details = []
        for row in rows[:10]:
            total = row["tong_24h_lon_nhat"]
            limit = row["lieu_toi_da_ngay"]
            total_text = total if total is not None else "thiếu"
            limit_text = limit if limit is not None else "thiếu"
            details.append(
                f"{row['hoat_chat']}: tổng 24 giờ {total_text} mg, tối đa {limit_text} mg"
            )
        return "; ".join(details)
    return f"{part}: {len(rows)} dòng."


class LayDuLieuCa(Tool):
    """Lấy chuỗi thời gian từ ca đang mở, không nhận mã ca từ LLM."""

    ten: ClassVar[str] = "lay_du_lieu_ca"
    ten_hien_thi: ClassVar[str] = "Lấy dữ liệu ca"
    mo_ta: ClassVar[str] = (
        "Lấy dữ liệu thời gian của ca hiện tại để trả lời và minh hoạ; chỉ chọn phần cần dùng."
    )
    LuocDoThamSo: ClassVar[type[BaseModel]] = ThamSoLayDuLieuCa
    che_do_cho_phep: ClassVar[frozenset[str]] = frozenset({"ca"})
    thoi_gian_toi_da: ClassVar[float] = 20.0

    def chay(self, tham_so: BaseModel, ctx: ToolContext) -> KetQuaCongCu:
        from app.agent.tools.gateway import _scrub_dataset_cell
        from app.deid.session import DeidSession

        assert isinstance(tham_so, ThamSoLayDuLieuCa)
        if ctx.ca is None:
            return KetQuaCongCu(
                trang_thai="loi", ma_loi="sai_tham_so", noi_dung="Chỉ dùng trong chế độ ca."
            )
        ca = ctx.ca
        datasets: list[BoDuLieu] = []
        evidence: list[CanCu] = []
        messages: list[str] = []
        counts: dict[str, int] = {}
        cut = 0
        with span("tool", "lay_du_lieu_ca_du_lieu") as data_span:

            def add(part: str, name: str, columns: list[CotDuLieu], rows: list[Dong]) -> None:
                nonlocal cut
                counts[name] = len(rows)
                cut += max(0, len(rows) - _MAX_DONG)
                datasets.append(
                    BoDuLieu(
                        ma="",
                        cot=columns,
                        dong=rows[-_MAX_DONG:],
                        can_cu=["tinh:lich_dung" if part == "lich_dung" else f"ca:{part}"],
                    )
                )

            for part in tham_so.phan:
                if part == "xet_nghiem":
                    rows = _lab_rows(ca, tham_so.ma_xet_nghiem)
                    add(
                        part,
                        part,
                        _columns(
                            ("thoi_diem", "thoi_gian"),
                            ("ma_xet_nghiem", "danh_muc"),
                            ("ten_xet_nghiem", "danh_muc"),
                            ("gia_tri", "dinh_luong"),
                            ("don_vi", "danh_muc"),
                            ("nguong_duoi", "dinh_luong"),
                            ("nguong_tren", "dinh_luong"),
                            ("ngoai_nguong", "logic"),
                            ("creatinin_tang_nhanh", "logic"),
                        ),
                        rows,
                    )
                    message = _summary(part, rows)
                elif part == "sinh_hieu":
                    rows = _vital_rows(ca, tham_so.loai_sinh_hieu)
                    add(
                        part,
                        part,
                        _columns(
                            ("thoi_diem", "thoi_gian"),
                            ("loai", "danh_muc"),
                            ("gia_tri", "dinh_luong"),
                            ("don_vi", "danh_muc"),
                        ),
                        rows,
                    )
                    message = _summary(part, rows)
                elif part == "lich_dung":
                    doses, totals, missing = _schedule_rows(ca)
                    add(
                        part,
                        "lich_tung_lieu",
                        _columns(
                            ("thoi_diem", "thoi_gian"),
                            ("thuoc", "danh_muc"),
                            ("hoat_chat", "danh_muc"),
                            ("lieu", "dinh_luong"),
                            ("don_vi", "danh_muc"),
                            ("nguon_lich", "danh_muc"),
                        ),
                        doses,
                    )
                    add(
                        part,
                        "tong_24h",
                        _columns(
                            ("hoat_chat", "danh_muc"),
                            ("tong_24h_lon_nhat", "dinh_luong"),
                            ("cua_so_tu", "thoi_gian"),
                            ("cua_so_den", "thoi_gian"),
                            ("lieu_toi_da_ngay", "dinh_luong"),
                            ("vuot", "logic"),
                            ("so_che_pham", "dinh_luong"),
                            ("nguon_lich", "danh_muc"),
                        ),
                        totals,
                    )
                    message = _summary(part, totals)
                    for total in totals[:10]:
                        start, end = total["cua_so_tu"], total["cua_so_den"]
                        if not isinstance(start, str) or not isinstance(end, str):
                            continue
                        start_time, end_time = (
                            datetime.fromisoformat(start),
                            datetime.fromisoformat(end),
                        )
                        matching = [
                            dose
                            for dose in doses
                            if dose["hoat_chat"] == total["hoat_chat"]
                            and isinstance(dose["thoi_diem"], str)
                            and start_time < datetime.fromisoformat(dose["thoi_diem"]) <= end_time
                            and dose["lieu"] is not None
                        ]
                        grouped: dict[float, int] = defaultdict(int)
                        for dose in matching:
                            grouped[float(str(dose["lieu"]))] += 1
                        if grouped:
                            details = ", ".join(
                                f"{count} liều {amount:g} mg" for amount, count in grouped.items()
                            )
                            message += f"; {total['hoat_chat']}: {details}"
                    if missing:
                        message += "; thiếu: " + ", ".join(sorted(missing))
                elif part == "khang_sinh":
                    courses, cultures = _antibiotic_rows(ca)
                    add(
                        part,
                        "dot_khang_sinh",
                        _columns(
                            ("thuoc", "danh_muc"),
                            ("hoat_chat", "danh_muc"),
                            ("bat_dau", "thoi_gian"),
                            ("ket_thuc", "thoi_gian"),
                            ("dang_dung", "logic"),
                            ("chua_bat_dau", "logic"),
                            ("ngay_thu", "dinh_luong"),
                            ("trang_thai_dong", "danh_muc"),
                        ),
                        courses,
                    )
                    add(
                        part,
                        "vi_sinh",
                        _columns(
                            ("thoi_diem_lay_mau", "thoi_gian"),
                            ("benh_pham", "danh_muc"),
                            ("vi_khuan", "danh_muc"),
                            ("hoat_chat", "danh_muc"),
                            ("ket_qua", "danh_muc"),
                            ("mic", "dinh_luong"),
                        ),
                        cultures,
                    )
                    details = []
                    for course in courses[:10]:
                        if course["chua_bat_dau"]:
                            start = datetime.fromisoformat(str(course["bat_dau"]))
                            status = (
                                f"chưa bắt đầu (liều đầu dự kiến {start:%d/%m %H:%M}, "
                                "sau thời điểm kê)"
                            )
                        elif course["dang_dung"]:
                            status = f"ngày thứ {int(float(str(course['ngay_thu'])))}"
                        elif course["ket_thuc"] is not None:
                            end = datetime.fromisoformat(str(course["ket_thuc"]))
                            status = f"đã ngưng ngày {end:%d/%m}"
                        else:
                            status = "thiếu ket_thuc"
                        details.append(f"{course['thuoc']}: {status}")
                    for culture in cultures[:10]:
                        if culture["ket_qua"] is not None:
                            details.append(
                                f"{culture['hoat_chat']}: {culture['ket_qua']}, "
                                f"MIC {culture['mic'] if culture['mic'] is not None else 'thiếu'}"
                            )
                    message = (
                        f"Kháng sinh: {len(courses)} dòng; vi sinh: {len(cultures)} dòng. "
                        + "; ".join(details)
                    )
                else:
                    rows = _milestone_rows(ca)
                    add(
                        part,
                        part,
                        _columns(
                            ("thoi_diem", "thoi_gian"), ("loai", "danh_muc"), ("nhan", "danh_muc")
                        ),
                        rows,
                    )
                    message = _summary(part, rows)
                # Gateway giữ nguyên căn cứ cho bộ kiểm chứng nên che cả bản sao này.
                message = _scrub_dataset_cell(message, ctx.deid_session or DeidSession(), [])
                code = "tinh:lich_dung" if part == "lich_dung" else f"ca:{part}"
                messages.append(f"[{code}] {message}")
                evidence.append(
                    CanCu(
                        ma=code,
                        loai="tinh" if part == "lich_dung" else "bang",
                        nhan=f"Dữ liệu ca: {part}",
                        noi_dung=message,
                    )
                )
            data_span.dat_thuoc_tinh(
                phan=tham_so.phan,
                so_dong_bo=counts,
                so_dong_bi_cat=cut,
                bi_cat=cut > 0,
                ly_do_cat_du_lieu="giu_2000_dong_moi_nhat" if cut else None,
            )
        return KetQuaCongCu(
            trang_thai="ok",
            noi_dung="\n".join(messages),
            can_cu=evidence,
            bo_du_lieu=datasets,
            chi_tiet_tien_trinh="Dữ liệu thời gian của ca",
        )
