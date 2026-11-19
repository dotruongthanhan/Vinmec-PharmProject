"""Luật yếu tố 4: rà tương tác thuốc – thuốc từ kho tri thức tuong_tac đã chuẩn hoá."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from app.domain.loader import ingredients_of
from app.domain.models import CaBenh, ChiTietYLenh, HoatChat, Thuoc
from app.rules.types import (
    CanCu,
    PhatHien,
    effective_lines,
    line_label,
    normalize_text,
    pending_lines,
)

_YEU_TO = 4

InteractionSeverity = Literal[
    "chong_chi_dinh",
    "nghiem_trong",
    "trung_binh",
    "nhe",
    "chua_ro",
]
DdinterLevel = Literal["Major", "Moderate", "Minor", "Unknown"]


def _ordered_id_pair(a_id: str, b_id: str) -> tuple[str, str]:
    """Trả về cặp mã hoạt chất theo thứ tự tăng dần để tra cứu vô hướng O(1)."""
    return (a_id, b_id) if a_id <= b_id else (b_id, a_id)


class InteractionRecord(BaseModel):
    """Một cặp tương tác hoạt chất đã hợp nhất từ DDInter 2.0 và nhãn openFDA."""

    model_config = ConfigDict(extra="forbid")

    tuong_tac_id: str
    hoat_chat_a_id: str
    hoat_chat_b_id: str
    ten_hoat_chat_a: str
    ten_hoat_chat_b: str
    ddinter_id_a: str
    ddinter_id_b: str
    ddinter_interaction_id: str | None = None
    muc_do_ddinter: DdinterLevel
    muc_do: InteractionSeverity
    co_che: list[str] = Field(default_factory=list)
    mo_ta_lam_sang: str | None = None
    xu_tri: str | None = None
    tai_lieu_ddinter: list[str] = Field(default_factory=list)
    trich_dan_nhan_fda: list[str] = Field(default_factory=list)
    nguon_chinh: str = "DDInter 2.0"
    tang_tin_cay: int = Field(ge=1, le=4, default=4)
    trang_thai: Literal["sang_loc", "da_duyet"] = "sang_loc"
    co_muc_lech_ddinter: bool = False


class InteractionBook(BaseModel):
    """Tập quy tắc tương tác thuốc – thuốc tra cứu nhanh theo cặp hoạt chất."""

    model_config = ConfigDict(extra="forbid")

    tuong_tac: list[InteractionRecord] = Field(default_factory=list)
    _by_pair: dict[tuple[str, str], InteractionRecord] = PrivateAttr(default_factory=dict)
    _by_name_pair: dict[tuple[str, str], InteractionRecord] = PrivateAttr(default_factory=dict)

    def model_post_init(self, __context: object) -> None:
        """Lập chỉ mục cặp hoạt chất theo cả mã KB và tên quốc tế chuẩn hoá."""
        self._by_pair = {
            _ordered_id_pair(rec.hoat_chat_a_id, rec.hoat_chat_b_id): rec for rec in self.tuong_tac
        }
        self._by_name_pair = {
            _ordered_id_pair(
                normalize_text(rec.ten_hoat_chat_a),
                normalize_text(rec.ten_hoat_chat_b),
            ): rec
            for rec in self.tuong_tac
        }

    def lookup(self, hoat_chat_a_id: str, hoat_chat_b_id: str) -> InteractionRecord | None:
        """Tra bản ghi tương tác theo hai mã hoạt chất (hoặc tên chuẩn hoá) bất kể thứ tự."""
        if hoat_chat_a_id == hoat_chat_b_id:
            return None
        direct = self._by_pair.get(_ordered_id_pair(hoat_chat_a_id, hoat_chat_b_id))
        if direct is not None:
            return direct
        return self._by_name_pair.get(
            _ordered_id_pair(normalize_text(hoat_chat_a_id), normalize_text(hoat_chat_b_id))
        )

    def lookup_ingredients(self, hc_a: HoatChat, hc_b: HoatChat) -> InteractionRecord | None:
        """Tra bản ghi tương tác từ hai HoatChat của ca bệnh (hỗ trợ HC-* và ten_quoc_te)."""
        if hc_a.hoat_chat_id == hc_b.hoat_chat_id:
            return None
        keys_a = _hc_lookup_keys(hc_a)
        keys_b = _hc_lookup_keys(hc_b)
        for ka in keys_a:
            for kb in keys_b:
                if ka == kb:
                    continue
                hit = self.lookup(ka, kb)
                if hit is not None:
                    return hit
        return None


def _hc_lookup_keys(hc: HoatChat) -> list[str]:
    """Sinh các khoá tra cứu hợp lệ từ một HoatChat trong ca bệnh."""
    raw = [
        hc.hoat_chat_id,
        hc.hoat_chat_id.removeprefix("HC-").lower().replace("-", "_"),
        normalize_text(hc.ten_quoc_te),
        normalize_text(hc.ten_hoat_chat),
    ]
    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def load_interaction_rules(path: Path) -> InteractionBook:
    """Đọc tệp JSONL tuong_tac; báo lỗi nếu đường dẫn không tồn tại."""
    resolved = Path(path)
    records: list[InteractionRecord] = []
    for raw_line in resolved.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        records.append(InteractionRecord.model_validate_json(line))
    return InteractionBook(tuong_tac=records)


def load_interaction_rules_if_exists(path: Path) -> InteractionBook:
    """Nạp tệp JSONL tuong_tac nếu có sẵn, hoặc trả về InteractionBook rỗng."""
    resolved = Path(path)
    if not resolved.is_file():
        return InteractionBook()
    return load_interaction_rules(resolved)


def _line_origin(line: ChiTietYLenh, pending_ids: set[str]) -> str:
    """Mô tả ngắn vai trò của dòng thuốc trong bối cảnh y lệnh."""
    if line.chi_tiet_y_lenh_id in pending_ids:
        return "y lệnh chờ duyệt"
    return f"thuốc đang dùng ({line.trang_thai_dong})"


def _map_severity(
    muc_do: InteractionSeverity,
) -> tuple[str, Literal["dat", "can_xem"], Literal["nghiem_trong", "can_luu_y", "thong_tin"]]:
    """Ánh xạ mức độ tương tác chuẩn hoá sang mã luật, kết luận và mức độ PhatHien."""
    if muc_do in ("chong_chi_dinh", "nghiem_trong"):
        return "tuong_tac_nghiem_trong", "can_xem", "nghiem_trong"
    if muc_do == "trung_binh":
        return "tuong_tac_trung_binh", "can_xem", "can_luu_y"
    return "tuong_tac_nhe", "dat", "thong_tin"


def _build_interaction_description(
    label_a: str,
    hc_a: HoatChat,
    label_b: str,
    hc_b: HoatChat,
    rec: InteractionRecord,
) -> str:
    """Tạo mô tả tiếng Việt ngắn gọn kèm cơ chế và xử trí DDInter nếu có."""
    mech_text = f"; cơ chế: {', '.join(rec.co_che)}" if rec.co_che else ""
    base = (
        f"Tương tác {rec.muc_do_ddinter} giữa {label_a} ({hc_a.ten_hoat_chat}) "
        f"và {label_b} ({hc_b.ten_hoat_chat}){mech_text}"
    )
    details: list[str] = []
    if rec.mo_ta_lam_sang:
        details.append(f"Ảnh hưởng lâm sàng: {rec.mo_ta_lam_sang}")
    if rec.xu_tri:
        details.append(f"Xử trí: {rec.xu_tri}")
    if details:
        return f"{base}. {' '.join(details)}"
    return base


def _build_interaction_evidences(
    la: ChiTietYLenh,
    hc_a: HoatChat,
    lb: ChiTietYLenh,
    hc_b: HoatChat,
    rec: InteractionRecord,
    pending_ids: set[str],
    thuoc_by_id: dict[str, Thuoc],
) -> list[CanCu]:
    """Tạo danh sách căn cứ dữ liệu người bệnh + tài liệu DDInter và nhãn FDA."""
    label_a = line_label(la, thuoc_by_id)
    label_b = line_label(lb, thuoc_by_id)
    evidences: list[CanCu] = [
        CanCu(
            loai="du_lieu",
            ban_ghi_id=la.chi_tiet_y_lenh_id,
            mo_ta=f"{label_a} ({_line_origin(la, pending_ids)}) chứa {hc_a.ten_hoat_chat}",
        ),
        CanCu(
            loai="du_lieu",
            ban_ghi_id=lb.chi_tiet_y_lenh_id,
            mo_ta=f"{label_b} ({_line_origin(lb, pending_ids)}) chứa {hc_b.ten_hoat_chat}",
        ),
    ]

    ref_note = ""
    if rec.tai_lieu_ddinter:
        ref_note = f"; trích dẫn: {rec.tai_lieu_ddinter[0]}"
        if len(rec.tai_lieu_ddinter) > 1:
            ref_note += f" (+{len(rec.tai_lieu_ddinter) - 1} tài liệu)"
    ddinter_id_note = f" (ID {rec.ddinter_interaction_id})" if rec.ddinter_interaction_id else ""
    evidences.append(
        CanCu(
            loai="tai_lieu",
            ban_ghi_id=rec.ddinter_interaction_id,
            mo_ta=(
                f"DDInter 2.0{ddinter_id_note}: mức {rec.muc_do_ddinter} — "
                f"{rec.ten_hoat_chat_a} + {rec.ten_hoat_chat_b}{ref_note}"
            ),
        ),
    )

    for chunk_id in rec.trich_dan_nhan_fda[:3]:
        evidences.append(
            CanCu(
                loai="tai_lieu",
                ban_ghi_id=chunk_id,
                mo_ta=(
                    f"Nhãn FDA đối chiếu tương tác {rec.ten_hoat_chat_a} – "
                    f"{rec.ten_hoat_chat_b} ({chunk_id})"
                ),
            ),
        )
    return evidences


def check(ca: CaBenh, rules: InteractionBook) -> list[PhatHien]:
    """Kiểm tra tương tác thuốc – thuốc giữa dòng chờ duyệt và các dòng đang hiệu lực khác."""
    pending = pending_lines(ca)
    pending_ids = {line.chi_tiet_y_lenh_id for line in pending}
    effective = effective_lines(ca)
    thuoc_by_id = {thuoc.thuoc_id: thuoc for thuoc in ca.danh_muc_thuoc}

    ingredients_cache: dict[str, list[HoatChat]] = {
        line.chi_tiet_y_lenh_id: ingredients_of(ca, line) for line in effective
    }

    findings: list[PhatHien] = []
    seen_line_hc_pairs: set[tuple[tuple[str, str], tuple[str, str]]] = set()

    for la in pending:
        ings_a = ingredients_cache.get(la.chi_tiet_y_lenh_id, [])
        if not ings_a:
            if len(effective) >= 2:
                label = line_label(la, thuoc_by_id)
                findings.append(
                    PhatHien(
                        ma_luat="tuong_tac_san_pham_chua_ro",
                        yeu_to=_YEU_TO,
                        ket_luan="khong_du_du_lieu",
                        muc_do=None,
                        chi_tiet_y_lenh_id=[la.chi_tiet_y_lenh_id],
                        mo_ta=(
                            f"Sản phẩm {label} chưa gắn thành phần hoạt chất nên chưa thể rà "
                            "tương tác thuốc – thuốc"
                        ),
                        can_cu=[
                            CanCu(
                                loai="du_lieu",
                                ban_ghi_id=la.chi_tiet_y_lenh_id,
                                mo_ta=(
                                    f"Dòng y lệnh {label} chỉ có tên tự do hoặc chưa có thành phần"
                                ),
                            ),
                        ],
                        thong_tin_con_thieu=["thanh_phan_hoat_chat"],
                    ),
                )
            continue

        for lb in effective:
            if lb.chi_tiet_y_lenh_id == la.chi_tiet_y_lenh_id:
                continue
            ings_b = ingredients_cache.get(lb.chi_tiet_y_lenh_id, [])
            if not ings_b:
                continue

            line_pair = _ordered_id_pair(la.chi_tiet_y_lenh_id, lb.chi_tiet_y_lenh_id)
            for hc_a in ings_a:
                for hc_b in ings_b:
                    if hc_a.hoat_chat_id == hc_b.hoat_chat_id:
                        continue
                    hc_pair = _ordered_id_pair(hc_a.hoat_chat_id, hc_b.hoat_chat_id)
                    dedupe_key = (line_pair, hc_pair)
                    if dedupe_key in seen_line_hc_pairs:
                        continue
                    seen_line_hc_pairs.add(dedupe_key)

                    rec = rules.lookup_ingredients(hc_a, hc_b)
                    if rec is None or rec.muc_do == "chua_ro":
                        continue

                    ma_luat, ket_luan, muc_do = _map_severity(rec.muc_do)
                    label_a = line_label(la, thuoc_by_id)
                    label_b = line_label(lb, thuoc_by_id)
                    findings.append(
                        PhatHien(
                            ma_luat=ma_luat,
                            yeu_to=_YEU_TO,
                            ket_luan=ket_luan,
                            muc_do=muc_do,
                            chi_tiet_y_lenh_id=[la.chi_tiet_y_lenh_id, lb.chi_tiet_y_lenh_id],
                            mo_ta=_build_interaction_description(label_a, hc_a, label_b, hc_b, rec),
                            can_cu=_build_interaction_evidences(
                                la,
                                hc_a,
                                lb,
                                hc_b,
                                rec,
                                pending_ids,
                                thuoc_by_id,
                            ),
                        ),
                    )

    if not findings:
        return [
            PhatHien(
                ma_luat="tuong_tac_khong_co",
                yeu_to=_YEU_TO,
                ket_luan="dat",
                muc_do="thong_tin",
                chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id for line in pending],
                mo_ta=(
                    "Không phát hiện tương tác thuốc – thuốc đáng kể trong các dòng thuốc đang "
                    "hiệu lực"
                ),
                can_cu=[
                    CanCu(
                        loai="du_lieu",
                        ban_ghi_id=None,
                        mo_ta=(
                            f"Đã đối chiếu {len(effective)} dòng thuốc đang hiệu lực theo "
                            "DDInter 2.0"
                        ),
                    ),
                ],
            ),
        ]

    return findings
