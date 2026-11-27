"""Kiểm đặc tả minh hoạ trước khi đưa vào kết quả."""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.agent.minh_hoa.models import BoDuLieu, CotDuLieu, KhoiMinhHoa
from app.calc.hien_thi import CONG_THUC_HIEN_THI
from app.orchestration.ask import _has_injection_directive


class DacTaMinhHoa(BaseModel):
    """Các khoá gốc của ngữ pháp mh-1."""

    model_config = ConfigDict(extra="forbid", strict=True)

    phien_ban: Literal["mh-1"]
    tieu_de: str = Field(max_length=120)
    phu_de: list[Any] = Field(default_factory=list, max_length=2048)
    lop: list[Any] = Field(min_length=1, max_length=6)
    truc: dict[str, Any] | None = None
    tham_so: list[Any] = Field(default_factory=list, max_length=6)
    so_hien: list[Any] = Field(default_factory=list, max_length=2048)
    cong_thuc: str | None = None
    nguon: list[str] = Field(min_length=1, max_length=2048)


class LoiDacTa(BaseModel):
    """Lý do từ chối không chứa nội dung đặc tả."""

    ly_do: str


class _Loi(Exception):
    pass


_ID = re.compile(r"[a-z][a-z0-9_]{0,31}\Z")
_DS = re.compile(r"ds-[1-9][0-9]*\Z")
_AN = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]")
_GIAO_THUC = re.compile(r"http|www\.|(?:javascript|vbscript|data)\s*:", re.I)
_ROLE = re.compile(
    r"\[(?:system|assistant|user|developer)\]|<\|[^|\n]+\|>|###\s*(?:system|assistant|user|developer)\b",
    re.I,
)
_FREE_NUMBER = re.compile(r"(?<!\w)\d")
_UNACCENTED_DIRECTIVE = re.compile(
    r"\bbo\s+qua\s+(?:(?:moi|tat\s+ca|cac)\s+)?(?:huong\s+dan|quy\s+tac|chi\s+thi|lenh)\b", re.I
)
_DAU = {"duong", "vung", "cot", "diem", "o", "dai", "doan", "quy_tac", "chu"}
_KIEU = {"dinh_luong", "thu_tu", "danh_muc", "thoi_gian"}
_KENH_VI_TRI = {"x", "y", "x_tu", "x_den", "y_tu", "y_den"}


def _object(value: Any, keys: set[str], path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _Loi(f"sai_cau_truc:{path}")
    if set(value) - keys:
        raise _Loi(f"khoa_la:{path}")
    return value


def _text(value: Any, path: str, *, number: bool = True, empty: bool = False) -> None:
    if not isinstance(value, str):
        raise _Loi(f"chu_khong_hop_le:{path}")
    value = unicodedata.normalize("NFKC", value)
    if len(value.encode("utf-16-le", errors="surrogatepass")) // 2 > 120 or (
        not empty and not value.strip()
    ):
        raise _Loi(f"chu_khong_hop_le:{path}")
    folded = (
        "".join(c for c in unicodedata.normalize("NFD", value) if not unicodedata.combining(c))
        .replace("đ", "d")
        .replace("Đ", "D")
    )
    if (
        _has_injection_directive(value)
        or _has_injection_directive(folded)
        or _UNACCENTED_DIRECTIVE.search(folded)
        or _ROLE.search(value)
    ):
        raise _Loi(f"chen_lenh:{path}")
    if "<" in value or ">" in value or _AN.search(value) or _GIAO_THUC.search(value):
        raise _Loi(f"chu_khong_an_toan:{path}")
    if number and _FREE_NUMBER.search(value):
        raise _Loi(f"so_tu_do:{path}")


def kiem_dac_ta(
    dac_ta: dict[str, Any], bo_du_lieu: Mapping[str, BoDuLieu], ma_can_cu_hop_le: set[str]
) -> KhoiMinhHoa | LoiDacTa:
    """Kiểm cấu trúc, tham chiếu và trần; không tính lại số liệu."""
    try:
        return _kiem(dac_ta, bo_du_lieu, ma_can_cu_hop_le)
    except _Loi as exc:
        return LoiDacTa(ly_do=str(exc))


def _kiem(
    spec: dict[str, Any], datasets: Mapping[str, BoDuLieu], evidence: set[str]
) -> KhoiMinhHoa:
    try:
        encoded = json.dumps(spec, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > 16384:
            raise _Loi("dac_ta_qua_lon")
    except (ValueError, TypeError, UnicodeError) as exc:
        raise _Loi("dac_ta_khong_hop_le") from exc
    try:
        DacTaMinhHoa.model_validate(spec)
    except ValidationError as exc:
        error = exc.errors(include_input=False, include_context=False)[0]
        code = "khoa_la" if error["type"] == "extra_forbidden" else "sai_cau_truc"
        raise _Loi(f"{code}:dac_ta") from exc

    used: dict[str, BoDuLieu] = {}

    def ds_get(code: Any) -> BoDuLieu:
        if not isinstance(code, str) or not _DS.fullmatch(code) or code not in datasets:
            safe = code if isinstance(code, str) and _DS.fullmatch(code) else "khong_hop_le"
            raise _Loi(f"ds_khong_ton_tai:{safe}")
        ds = datasets[code]
        used[code] = ds
        return ds

    def col(ds: BoDuLieu, name: Any, path: str) -> CotDuLieu:
        for item in ds.cot:
            if item.ten == name:
                return item
        raise _Loi(f"cot_khong_ton_tai:{path}")

    def cell(value: Any, path: str) -> CotDuLieu:
        obj = _object(value, {"ds", "cot", "dong", "theo_tham_so", "dinh_dang"}, path)
        ds = ds_get(obj.get("ds"))
        column = col(ds, obj.get("cot"), path)
        row = obj.get("dong")
        selected = obj.get("theo_tham_so", False)
        if type(selected) is not bool or ("dong" in obj) == selected:
            raise _Loi(f"tham_chieu_khong_hop_le:{path}")
        if "dong" in obj and (type(row) is not int or row < 0 or row >= len(ds.dong)):
            raise _Loi(f"dong_khong_hop_le:{path}")
        if "dinh_dang" in obj and obj["dinh_dang"] not in ("0", "0.0", "0.00"):
            raise _Loi(f"dinh_dang_khong_hop_le:{path}")
        return column

    def interval(value: Any, path: str) -> None:
        keys = {"ds", "cot", "tu", "den", "bao_gom_tu", "bao_gom_den", "gia_tri"}
        obj = _object(value, keys, path)
        ds = ds_get(obj.get("ds"))
        col(ds, obj.get("cot"), path)
        for key in ("tu", "den"):
            if col(ds, obj.get(key), path).kieu != "dinh_luong":
                raise _Loi(f"sai_kieu_cot:{path}")
        for key in ("bao_gom_tu", "bao_gom_den"):
            if col(ds, obj.get(key), path).kieu != "logic":
                raise _Loi(f"sai_kieu_cot:{path}")
        if cell(obj.get("gia_tri"), path).kieu != "dinh_luong":
            raise _Loi(f"sai_kieu_cot:{path}")

    def reference(obj: Any, path: str, *, label: bool = False) -> None:
        if isinstance(obj, (int, float)) and not isinstance(obj, bool):
            raise _Loi(f"so_tu_do:{path}")
        keys = {"o", "o_theo_khoang"} | ({"nhan"} if label else {"chu"})
        obj = _object(obj, keys, path)
        variants = set(obj) & {"chu", "o", "o_theo_khoang"}
        if len(variants) != 1 or (label and "chu" in variants):
            raise _Loi(f"sai_cau_truc:{path}")
        if label:
            _text(obj.get("nhan"), path, number=True)
        if "chu" in obj:
            _text(obj["chu"], path, number=True, empty=True)
        elif "o" in obj:
            cell(obj["o"], path)
        else:
            interval(obj["o_theo_khoang"], path)

    _text(spec["tieu_de"], "tieu_de")
    for i, item in enumerate(spec.get("phu_de", [])):
        reference(item, f"phu_de[{i}]")
    for i, item in enumerate(spec.get("so_hien", [])):
        reference(item, f"so_hien[{i}]", label=True)

    def check_text_array(items: list[Any], path: str) -> None:
        cells = [(i, item["o"]) for i, item in enumerate(items) if "o" in item]
        intervals = [
            (i, item["o_theo_khoang"]["gia_tri"])
            for i, item in enumerate(items)
            if "o_theo_khoang" in item
        ]
        selected_columns = {
            ref["cot"] for _, ref in cells + intervals if ref.get("theo_tham_so") is True
        }
        for i, ref in cells:
            if ref["cot"] in selected_columns and ref.get("theo_tham_so") is not True:
                raise _Loi(
                    f"tron_gia_tri_ca_va_gia_dinh:{path}[{i}]; "
                    "Dùng giá trị theo tham số trong cùng mảng, hoặc tách số của ca sang dòng khác"
                )
        for i, ref in intervals:
            if ref.get("theo_tham_so") is True and not any(
                c.get("theo_tham_so") is True and c["ds"] == ref["ds"] and c["cot"] == ref["cot"]
                for _, c in cells
            ):
                raise _Loi(
                    f"thieu_gia_tri_tra:{path}[{i}]; "
                    "Thêm ô theo tham số cùng bộ dữ liệu và cột để hiện giá trị dùng tra"
                )

    check_text_array(spec.get("phu_de", []), "phu_de")
    check_text_array(spec.get("so_hien", []), "so_hien")

    params: set[str] = set()
    for i, raw in enumerate(spec.get("tham_so", [])):
        path = f"tham_so[{i}]"
        p = _object(raw, {"ma", "loai", "nhan", "gia_tri_tu", "mac_dinh", "nhan_gia_dinh"}, path)
        kind = p.get("loai")
        if kind not in ("thanh_keo", "chon_mot", "bat_tat", "loc", "dat_lai"):
            raise _Loi(f"sai_cau_truc:{path}")
        _text(p.get("nhan"), path)
        if "nhan_gia_dinh" in p and type(p["nhan_gia_dinh"]) is not bool:
            raise _Loi(f"sai_cau_truc:{path}")
        if kind == "dat_lai":
            continue
        name = p.get("ma")
        if not isinstance(name, str) or not _ID.fullmatch(name) or name in params:
            raise _Loi(f"tham_so_khong_hop_le:{path}")
        params.add(name)
        source = _object(p.get("gia_tri_tu"), {"ds", "cot"}, path)
        column = col(ds_get(source.get("ds")), source.get("cot"), path)
        if kind == "thanh_keo" and column.kieu not in ("dinh_luong", "thu_tu"):
            raise _Loi(f"sai_kieu_cot:{path}")
        if "mac_dinh" in p:
            default = _object(p["mac_dinh"], {"o"}, path)
            cell(default.get("o"), path)

    total = 0
    for i, raw in enumerate(spec["lop"]):
        path = f"lop[{i}]"
        layer = _object(raw, {"dau", "du_lieu", "loc", "ma_hoa"}, path)
        mark = layer.get("dau")
        if not isinstance(mark, str) or mark not in _DAU:
            raise _Loi(f"dau_khong_hop_le:{path}")
        ds = ds_get(layer.get("du_lieu"))
        total += len(ds.dong)
        filters = layer.get("loc", [])
        if not isinstance(filters, list) or len(filters) > 2048:
            raise _Loi(f"sai_cau_truc:{path}")
        for f in filters:
            f = _object(f, {"cot", "bang_tham_so", "trong_tham_so"}, path)
            col(ds, f.get("cot"), path)
            options = [f[k] for k in ("bang_tham_so", "trong_tham_so") if k in f]
            if len(options) != 1 or not isinstance(options[0], str) or options[0] not in params:
                raise _Loi(f"tham_so_khong_hop_le:{path}")
        enc = _object(
            layer.get("ma_hoa"),
            _KENH_VI_TRI | {"mau", "nhom", "nhan", "kich_thuoc", "can_cu"},
            path,
        )
        columns: dict[str, CotDuLieu] = {}
        for channel, raw_channel in enc.items():
            cp = f"{path}.ma_hoa.{channel}"
            channel_obj = _object(raw_channel, {"cot", "kieu", "o", "chu"}, cp)
            if "o" in channel_obj:
                if channel not in _KENH_VI_TRI or set(channel_obj) != {"o"}:
                    raise _Loi(f"khoa_la:{cp}")
                columns[channel] = cell(channel_obj["o"], cp)
            elif "chu" in channel_obj:
                if channel != "nhan" or set(channel_obj) != {"chu"}:
                    raise _Loi(f"khoa_la:{cp}")
                _text(channel_obj["chu"], cp, number=True)
            else:
                c = col(ds, channel_obj.get("cot"), cp)
                if "kieu" in channel_obj and (
                    not isinstance(channel_obj["kieu"], str)
                    or channel_obj["kieu"] not in _KIEU
                    or channel_obj["kieu"] != c.kieu
                ):
                    raise _Loi(f"sai_kieu_cot:{cp}")
                columns[channel] = c
        if "kich_thuoc" in columns and columns["kich_thuoc"].kieu != "dinh_luong":
            raise _Loi(f"sai_kieu_cot:{path}")
        if mark == "doan":
            if not {"x_tu", "x_den", "y"}.issubset(enc):
                raise _Loi(f"thieu_kenh:{path}")
            if (
                columns["x_tu"].kieu not in ("dinh_luong", "thoi_gian")
                or columns["x_den"].kieu != columns["x_tu"].kieu
                or columns["y"].kieu != "danh_muc"
            ):
                raise _Loi(f"sai_kieu_cot:{path}")
        elif mark == "dai":
            pairs = [("x_tu", "x_den"), ("y_tu", "y_den")]
            if not any(a in enc and b in enc for a, b in pairs):
                raise _Loi(f"thieu_kenh:{path}")
            for a, b in pairs:
                if (
                    a in enc
                    and b in enc
                    and any(columns[k].kieu not in ("dinh_luong", "thoi_gian") for k in (a, b))
                ):
                    raise _Loi(f"sai_kieu_cot:{path}")
        elif mark in ("o", "duong", "vung", "cot"):
            if "x" not in enc or "y" not in enc:
                raise _Loi(f"thieu_kenh:{path}")
            if mark in ("duong", "vung") and columns["y"].kieu != "dinh_luong":
                raise _Loi(f"sai_kieu_cot:{path}")
            if mark == "cot" and all(columns[k].kieu != "dinh_luong" for k in ("x", "y")):
                raise _Loi(f"sai_kieu_cot:{path}")
        elif "x" not in enc and "y" not in enc:
            raise _Loi(f"thieu_kenh:{path}")
    if total > 2000:
        raise _Loi("qua_2000_phan_tu")

    if "truc" in spec:
        axes = _object(spec["truc"], {"x", "y"}, "truc")
        for key, raw in axes.items():
            if raw is None:
                continue
            axis = _object(raw, {"tieu_de", "mien"}, f"truc.{key}")
            _text(axis.get("tieu_de"), f"truc.{key}")
            if "mien" in axis and axis["mien"] not in ("tu_du_lieu", "tu_0"):
                raise _Loi(f"sai_cau_truc:truc.{key}")
    formula = spec.get("cong_thuc")
    if formula is not None and formula not in CONG_THUC_HIEN_THI:
        raise _Loi("cong_thuc_khong_hop_le")
    for source in spec["nguon"]:
        _text(source, "nguon", number=False)
        if source not in evidence:
            raise _Loi("nguon_khong_hop_le")
    for ds in used.values():
        for c in ds.cot:
            for row in ds.dong:
                v = row.get(c.ten)
                if v is not None and (
                    (
                        c.kieu == "dinh_luong"
                        and (
                            isinstance(v, bool)
                            or not isinstance(v, (float, int))
                            or not math.isfinite(v)
                        )
                    )
                    or (c.kieu == "thoi_gian" and not isinstance(v, str))
                ):
                    raise _Loi("sai_kieu_du_lieu")
    block = KhoiMinhHoa(
        ma="mh-1",
        phien_ban="mh-1",
        dac_ta=spec,
        bo_du_lieu=list(used.values()),
        cong_thuc_hien_thi=CONG_THUC_HIEN_THI.get(formula),
        nguon=spec["nguon"],
    )
    if len(json.dumps(block.model_dump(mode="json")).encode("utf-8")) > 100 * 1024:
        raise _Loi("khoi_qua_lon")
    return block
