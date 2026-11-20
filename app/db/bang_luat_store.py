"""Đọc bảng luật và danh mục D1-D7 lúc chạy từ tệp hoặc PostgreSQL (không import app.rules)."""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any, Literal, TypeVar

import psycopg
import yaml
from pydantic import ValidationError

from app.config.settings import get_secret, load_kb_source
from app.core.errors import ConfigError
from app.db.read_pool import read_pool

_T = TypeVar("_T")
_LOGGER = logging.getLogger(__name__)
_CACHE_CLEARS: list[Callable[[], None]] = []
_TABLE_ORDER_MAP: dict[str, str] = {
    "tri_thuc.quy_tac_lieu_than_v2": "danh_sach ASC, thu_tu ASC",
    "tri_thuc.canh_bao_doc_tinh": "loai ASC, thu_tu ASC",
}
_DB_CACHE_LOCK = RLock()
_RAW_DB_LOADED = False
_RAW_DB_KEY: tuple[str, str | None] | None = None
_RAW_DB_DOCS: dict[str, dict[str, Any]] = {}
_RAW_DB_ERROR: tuple[str, str] | None = None
_WARNED_DB_DOCS: set[str] = set()

RULE_TABLES: tuple[str, ...] = (
    "tri_thuc.bang_luat_meta",
    "tri_thuc.quy_tac_lieu_than_v2",
    "tri_thuc.quy_tac_lieu_than_khong_nguong",
    "tri_thuc.quy_tac_gan",
    "tri_thuc.nguong_xet_nghiem",
    "tri_thuc.tuong_tac_benh",
    "tri_thuc.anh_xa_benh_icd",
    "tri_thuc.tuong_tac_benh_khop_ca",
    "tri_thuc.duong_dung_hop_le",
    "tri_thuc.chuan_hoa_duong_dung",
    "tri_thuc.lieu_toi_da",
    "tri_thuc.doi_tuong_dinh_nghia",
    "tri_thuc.lieu_toi_da_khong_ghi",
    "tri_thuc.lieu_toi_da_khong_ghi_duong_ca",
    "tri_thuc.canh_bao_doc_tinh",
    "tri_thuc.khang_sinh_han_che_nhom",
    "tri_thuc.khang_sinh_han_che",
    "tri_thuc.khang_sinh_khong_anh_xa",
    "tri_thuc.nhom_di_ung_cheo",
    "tri_thuc.nhom_di_ung_anh_xa",
    "tri_thuc.danh_muc_hoat_chat_demo",
    "tri_thuc.danh_muc_hoat_chat_demo_nhan",
    "tri_thuc.nhom_dieu_tri_trung",
    "tri_thuc.atc_bo_sung",
)

HEADER_SCALAR_KEYS = ("ten", "phien_ban", "ngay", "trang_thai", "ghi_chu", "nguon")


class BangLuatReadError(OSError):
    """Lỗi đọc bảng luật từ cấu hình, tệp hoặc PostgreSQL (không chứa DSN)."""


@dataclass(frozen=True)
class RuleDocSpec:
    """Đặc tả ánh xạ giữa một tệp nguồn bảng luật và các bảng PostgreSQL."""

    ma: str
    tep: str
    dinh_dang: Literal["json", "yaml"]
    danh_sach_khoa: tuple[str, ...]
    cac_bang: tuple[str, ...]


RULE_DOCUMENTS: tuple[RuleDocSpec, ...] = (
    RuleDocSpec(
        ma="quy_tac_lieu_than",
        tep="data/kb/quy_tac_lieu_than.json",
        dinh_dang="json",
        danh_sach_khoa=("quy_tac", "quy_tac_cho_duyet", "khong_co_nguong"),
        cac_bang=("tri_thuc.quy_tac_lieu_than_v2", "tri_thuc.quy_tac_lieu_than_khong_nguong"),
    ),
    RuleDocSpec(
        ma="quy_tac_gan",
        tep="data/kb/quy_tac_gan.json",
        dinh_dang="json",
        danh_sach_khoa=("quy_tac",),
        cac_bang=("tri_thuc.quy_tac_gan",),
    ),
    RuleDocSpec(
        ma="nguong_xet_nghiem",
        tep="data/kb/nguong_xet_nghiem.json",
        dinh_dang="json",
        danh_sach_khoa=("quy_tac",),
        cac_bang=("tri_thuc.nguong_xet_nghiem",),
    ),
    RuleDocSpec(
        ma="thuoc_benh_icd",
        tep="data/kb/thuoc_benh_icd.json",
        dinh_dang="json",
        danh_sach_khoa=("anh_xa", "cap_khop_chan_doan_ca", "cap_thuoc_benh"),
        cac_bang=(
            "tri_thuc.tuong_tac_benh",
            "tri_thuc.anh_xa_benh_icd",
            "tri_thuc.tuong_tac_benh_khop_ca",
        ),
    ),
    RuleDocSpec(
        ma="duong_dung_hop_le",
        tep="data/kb/duong_dung_hop_le.json",
        dinh_dang="json",
        danh_sach_khoa=("nhom", "bang_chuan_hoa_duong_dung"),
        cac_bang=("tri_thuc.duong_dung_hop_le", "tri_thuc.chuan_hoa_duong_dung"),
    ),
    RuleDocSpec(
        ma="lieu_toi_da",
        tep="data/kb/lieu_toi_da.json",
        dinh_dang="json",
        danh_sach_khoa=(
            "nhom",
            "khong_ghi_toi_da",
            "khong_ghi_toi_da_theo_duong_trong_ca",
            "doi_tuong_dinh_nghia",
        ),
        cac_bang=(
            "tri_thuc.lieu_toi_da",
            "tri_thuc.doi_tuong_dinh_nghia",
            "tri_thuc.lieu_toi_da_khong_ghi",
            "tri_thuc.lieu_toi_da_khong_ghi_duong_ca",
        ),
    ),
    RuleDocSpec(
        ma="doc_tinh",
        tep="data/kb/doc_tinh.json",
        dinh_dang="json",
        danh_sach_khoa=(
            "doc_than",
            "keo_dai_qt",
            "khoang_dieu_tri_hep",
            "doc_gan_livertox",
            "khong_co_nguon",
        ),
        cac_bang=("tri_thuc.canh_bao_doc_tinh",),
    ),
    RuleDocSpec(
        ma="khang_sinh_quan_ly",
        tep="data/kb/khang_sinh_quan_ly.json",
        dinh_dang="json",
        danh_sach_khoa=("nhom", "khang_sinh", "khong_anh_xa"),
        cac_bang=(
            "tri_thuc.khang_sinh_han_che_nhom",
            "tri_thuc.khang_sinh_han_che",
            "tri_thuc.khang_sinh_khong_anh_xa",
        ),
    ),
    RuleDocSpec(
        ma="di_ung_cheo",
        tep="data/kb/di_ung_cheo.json",
        dinh_dang="json",
        danh_sach_khoa=("nhom", "ten_nhom_di_ung_sang_hoat_chat"),
        cac_bang=("tri_thuc.nhom_di_ung_cheo", "tri_thuc.nhom_di_ung_anh_xa"),
    ),
    RuleDocSpec(
        ma="hoat_chat",
        tep="data/kb/hoat_chat.json",
        dinh_dang="json",
        danh_sach_khoa=("hoat_chat", "nhan"),
        cac_bang=(
            "tri_thuc.danh_muc_hoat_chat_demo",
            "tri_thuc.danh_muc_hoat_chat_demo_nhan",
        ),
    ),
    RuleDocSpec(
        ma="nhom_dieu_tri_trung",
        tep="config/kb/nhom_dieu_tri_trung.yaml",
        dinh_dang="yaml",
        danh_sach_khoa=("nhom",),
        cac_bang=("tri_thuc.nhom_dieu_tri_trung",),
    ),
    RuleDocSpec(
        ma="atc_bo_sung",
        tep="config/kb/atc_bo_sung.yaml",
        dinh_dang="yaml",
        danh_sach_khoa=("ma_atc",),
        cac_bang=("tri_thuc.atc_bo_sung",),
    ),
)

_DOCS_BY_MA: dict[str, RuleDocSpec] = {spec.ma: spec for spec in RULE_DOCUMENTS}

TABLE_SPECS: dict[str, tuple[tuple[str, ...], frozenset[str], frozenset[str]]] = {
    "tri_thuc.bang_luat_meta": (
        (
            "ma",
            "ten",
            "phien_ban",
            "ngay",
            "trang_thai",
            "ghi_chu",
            "nguon",
            "phan_khac",
            "sha256_tep",
        ),
        frozenset({"phan_khac"}),
        frozenset(),
    ),
    "tri_thuc.quy_tac_lieu_than_v2": (
        (
            "danh_sach",
            "thu_tu",
            "ten_quoc_te",
            "hoat_chat_ids",
            "hoat_chat_id",
            "chi_so",
            "trang_thai",
            "nguon",
            "nguoi_duyet",
            "muc",
            "nguon_chi_tiet",
            "phoi_hop",
            "bi_danh",
            "phien_ban",
            "bo_sung",
        ),
        frozenset({"hoat_chat_ids", "muc", "nguon_chi_tiet", "bi_danh", "bo_sung"}),
        frozenset(),
    ),
    "tri_thuc.quy_tac_lieu_than_khong_nguong": (
        ("thu_tu", "hoat_chat_id", "loai", "ly_do", "set_id", "url", "phien_ban", "bo_sung"),
        frozenset({"bo_sung"}),
        frozenset(),
    ),
    "tri_thuc.quy_tac_gan": (
        (
            "thu_tu",
            "ten_quoc_te",
            "hoat_chat_ids",
            "hoat_chat_id",
            "phan_loai_gan",
            "hanh_dong_nhan",
            "khuyen_cao",
            "trang_thai",
            "nguon_chi_tiet",
            "phien_ban",
            "bo_sung",
        ),
        frozenset({"hoat_chat_ids", "phan_loai_gan", "nguon_chi_tiet", "bo_sung"}),
        frozenset(),
    ),
    "tri_thuc.nguong_xet_nghiem": (
        (
            "thu_tu",
            "ten_quoc_te",
            "hoat_chat_ids",
            "hoat_chat_id",
            "xet_nghiem",
            "dieu_kien",
            "hanh_dong_nhan",
            "don_vi_nhan",
            "don_vi_trong_ca",
            "trang_thai",
            "kieu_dieu_kien",
            "muc_do_de_xuat",
            "dieu_kien_khac",
            "ghi_chu",
            "nguon_chi_tiet",
            "phien_ban",
            "bo_sung",
        ),
        frozenset({"hoat_chat_ids", "dieu_kien", "nguon_chi_tiet", "bo_sung"}),
        frozenset(),
    ),
    "tri_thuc.tuong_tac_benh": (
        (
            "thu_tu",
            "hoat_chat_id",
            "ddinter_id",
            "ten_benh",
            "ma_icd10",
            "muc_do",
            "noi_dung",
            "url",
            "trang_thai",
            "phien_ban",
            "bo_sung",
        ),
        frozenset({"ma_icd10", "bo_sung"}),
        frozenset(),
    ),
    "tri_thuc.anh_xa_benh_icd": (
        (
            "thu_tu",
            "ten_benh",
            "ma_icd10",
            "ghi_chu",
            "khong_anh_xa",
            "hoat_chat_ids",
            "hoat_chat_id",
            "so_dong_ddinter",
            "muc_do_cao_nhat",
            "trang_thai",
            "phien_ban",
            "bo_sung",
        ),
        frozenset({"ma_icd10", "hoat_chat_ids", "bo_sung"}),
        frozenset({"khong_anh_xa"}),
    ),
    "tri_thuc.tuong_tac_benh_khop_ca": (
        ("thu_tu", "ca_id", "hoat_chat_id", "ten_benh", "ma_icd10_ca", "phien_ban", "bo_sung"),
        frozenset({"bo_sung"}),
        frozenset(),
    ),
    "tri_thuc.duong_dung_hop_le": (
        (
            "ma_dong",
            "thu_tu",
            "hoat_chat_ids",
            "hoat_chat_id",
            "nhom_dang_bao_che",
            "ten_nhom_dang",
            "duong_dung_hop_le",
            "muc_chac_chan",
            "nguon",
            "ghi_chu",
            "trang_thai",
            "phien_ban",
            "bo_sung",
        ),
        frozenset({"hoat_chat_ids", "duong_dung_hop_le", "nguon", "bo_sung"}),
        frozenset(),
    ),
    "tri_thuc.chuan_hoa_duong_dung": (
        ("thu_tu", "loai", "khoa", "duong_dung", "gia_tri", "phien_ban"),
        frozenset({"gia_tri"}),
        frozenset(),
    ),
    "tri_thuc.lieu_toi_da": (
        (
            "ma_dong",
            "thu_tu",
            "hoat_chat_ids",
            "hoat_chat_id",
            "duong_dung",
            "doi_tuong",
            "dieu_kien",
            "dieu_kien_khac",
            "loai_gioi_han",
            "lieu_toi_da_lan",
            "lieu_toi_da_ngay",
            "lieu_toi_da_tuan",
            "theo_kg",
            "thuoc_dung_cung_hoat_chat_ids",
            "quy_doi_don_vi",
            "ghi_chu",
            "nguon",
            "trang_thai",
            "phien_ban",
            "bo_sung",
        ),
        frozenset(
            {
                "hoat_chat_ids",
                "duong_dung",
                "lieu_toi_da_lan",
                "lieu_toi_da_ngay",
                "lieu_toi_da_tuan",
                "theo_kg",
                "thuoc_dung_cung_hoat_chat_ids",
                "quy_doi_don_vi",
                "nguon",
                "bo_sung",
            }
        ),
        frozenset(),
    ),
    "tri_thuc.doi_tuong_dinh_nghia": (
        (
            "ma",
            "thu_tu",
            "tuoi_tu",
            "tuoi_den",
            "tuoi_tren",
            "tuoi_duoi",
            "bao_gom_can_duoi",
            "bao_gom_can_tren",
            "tuoi_thang_tu",
            "tuoi_thang_den",
            "tuoi_ngay_tu",
            "tuoi_ngay_den",
            "can_nang_tu",
            "can_nang_den",
            "can_nang_tren",
            "can_nang_duoi",
            "dieu_kien_khac",
            "phien_ban",
            "bo_sung",
        ),
        frozenset({"bo_sung"}),
        frozenset({"bao_gom_can_duoi", "bao_gom_can_tren"}),
    ),
    "tri_thuc.lieu_toi_da_khong_ghi": (
        ("thu_tu", "hoat_chat_id", "co_dong_theo_nhom_dac_biet", "ly_do", "phien_ban", "bo_sung"),
        frozenset({"co_dong_theo_nhom_dac_biet", "bo_sung"}),
        frozenset(),
    ),
    "tri_thuc.lieu_toi_da_khong_ghi_duong_ca": (
        ("thu_tu", "hoat_chat_ids", "hoat_chat_id", "duong_dung", "phien_ban", "bo_sung"),
        frozenset({"hoat_chat_ids", "bo_sung"}),
        frozenset(),
    ),
    "tri_thuc.canh_bao_doc_tinh": (
        (
            "thu_tu",
            "loai",
            "hoat_chat_id",
            "nhom",
            "muc_nhan",
            "ma_xet_nghiem_nong_do",
            "likelihood_score",
            "danh_sach",
            "ly_do",
            "nguon",
            "trang_thai",
            "phien_ban",
            "bo_sung",
        ),
        frozenset({"ma_xet_nghiem_nong_do", "nguon", "bo_sung"}),
        frozenset(),
    ),
    "tri_thuc.khang_sinh_han_che_nhom": (
        ("ma_nhom", "thu_tu", "ten_nhom_van_ban", "yeu_cau", "trang_pdf", "phien_ban", "bo_sung"),
        frozenset({"bo_sung"}),
        frozenset(),
    ),
    "tri_thuc.khang_sinh_han_che": (
        (
            "thu_tu",
            "ten_trong_van_ban",
            "hoat_chat_ids",
            "hoat_chat_id",
            "ma_nhom",
            "trang_pdf",
            "trang_thai",
            "phien_ban",
            "bo_sung",
        ),
        frozenset({"hoat_chat_ids", "bo_sung"}),
        frozenset(),
    ),
    "tri_thuc.khang_sinh_khong_anh_xa": (
        (
            "thu_tu",
            "ten_trong_van_ban",
            "ma_nhom",
            "trang_pdf",
            "ly_do",
            "phien_ban",
            "bo_sung",
        ),
        frozenset({"bo_sung"}),
        frozenset(),
    ),
    "tri_thuc.nhom_di_ung_cheo": (
        (
            "ma_nhom",
            "thu_tu",
            "ten_nhom",
            "hoat_chat_ids",
            "hoat_chat_id",
            "hoat_chat_lien_quan",
            "huong",
            "co_so",
            "nguon",
            "ghi_chu",
            "trang_thai",
            "phien_ban",
            "bo_sung",
        ),
        frozenset({"hoat_chat_ids", "hoat_chat_lien_quan", "nguon", "bo_sung"}),
        frozenset(),
    ),
    "tri_thuc.nhom_di_ung_anh_xa": (
        ("ten_alias", "thu_tu", "hoat_chat_ids", "hoat_chat_id", "ma_nhom", "phien_ban", "bo_sung"),
        frozenset({"hoat_chat_ids", "bo_sung"}),
        frozenset(),
    ),
    "tri_thuc.danh_muc_hoat_chat_demo": (
        (
            "hoat_chat_id",
            "thu_tu",
            "ten_inn",
            "ten_viet",
            "dong_nghia",
            "thanh_phan",
            "nhom",
            "phien_ban",
            "bo_sung",
        ),
        frozenset({"dong_nghia", "thanh_phan", "bo_sung"}),
        frozenset(),
    ),
    "tri_thuc.danh_muc_hoat_chat_demo_nhan": (
        ("ten_goi", "thu_tu", "hoat_chat_ids", "hoat_chat_id", "phien_ban"),
        frozenset({"hoat_chat_ids"}),
        frozenset(),
    ),
    "tri_thuc.nhom_dieu_tri_trung": (
        (
            "ma_nhom",
            "thu_tu",
            "ten",
            "tien_to_atc",
            "tien_to_atc_loai_tru",
            "muc_do",
            "ly_do",
            "nguon",
            "ngoai_le",
            "phien_ban",
            "bo_sung",
        ),
        frozenset({"tien_to_atc", "tien_to_atc_loai_tru", "ngoai_le", "bo_sung"}),
        frozenset(),
    ),
    "tri_thuc.atc_bo_sung": (
        ("hoat_chat_id", "thu_tu", "ma_atc", "phien_ban"),
        frozenset({"ma_atc"}),
        frozenset(),
    ),
}


def register_cache_clear(clear_fn: Callable[[], None]) -> None:
    """Đăng ký hàm xoá bộ nhớ đệm của một bộ nạp cấu hình để tiện kiểm thử."""
    if clear_fn not in _CACHE_CLEARS:
        _CACHE_CLEARS.append(clear_fn)


def clear_all_caches() -> None:
    """Xoá toàn bộ bộ nhớ đệm đã đăng ký của các bảng luật/danh mục."""
    global _RAW_DB_LOADED, _RAW_DB_KEY, _RAW_DB_ERROR
    with _DB_CACHE_LOCK:
        _RAW_DB_LOADED = False
        _RAW_DB_KEY = None
        _RAW_DB_DOCS.clear()
        _RAW_DB_ERROR = None
        _WARNED_DB_DOCS.clear()
    for fn in _CACHE_CLEARS:
        fn()


def _decode_json(value: Any) -> Any:
    """Giải mã cột jsonb nếu trả về dạng chuỗi (ví dụ SQLite giả lập)."""
    if isinstance(value, str):
        return json.loads(value)
    return value


def _row_to_dict(row: Any, columns: tuple[str, ...]) -> dict[str, Any]:
    """Chuyển hàng tuple, dict_row hoặc sqlite3.Row thành dict theo tên cột."""
    if isinstance(row, Mapping):
        return dict(row)
    if hasattr(row, "keys"):
        return dict(row)
    return dict(zip(columns, row, strict=True))


def _query_table(
    conn: Any,
    table: str,
    *,
    where_clause: str = "",
    params: tuple[Any, ...] = (),
    order_by: str = "thu_tu ASC",
) -> list[dict[str, Any]]:
    """Truy vấn toàn bộ dòng của một bảng thuộc tri_thuc và giải mã cột JSONB/bool."""
    columns, json_cols, bool_cols = TABLE_SPECS[table]
    col_sql = ", ".join(columns)
    where_sql = f" WHERE {where_clause}" if where_clause else ""
    order_sql = f" ORDER BY {order_by}" if order_by else ""
    sql_text = f"SELECT {col_sql} FROM {table}{where_sql}{order_sql}"  # noqa: S608  # bảng/cột hằng
    cur = conn.execute(sql_text, params)
    fetch = getattr(cur, "fetchall", None)
    raw_rows = fetch() if callable(fetch) else list(cur)
    parsed: list[dict[str, Any]] = []
    for row in raw_rows:
        item = _row_to_dict(row, columns)
        for col in json_cols:
            if col in item and item[col] is not None:
                item[col] = _decode_json(item[col])
        for col in bool_cols:
            if col in item and item[col] is not None:
                item[col] = bool(item[col])
        parsed.append(item)
    return parsed


def _unpack_item(
    row: Mapping[str, Any],
    field_keys: Iterable[str],
    *,
    rename: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Dựng lại dict gốc từ các cột SQL và metadata bo_sung, giữ đúng khoá tuỳ chọn."""
    rename_map = rename or {}
    bo_sung = row.get("bo_sung") or {}
    if not isinstance(bo_sung, Mapping):
        bo_sung = {}
    key_order = bo_sung.get("_khoa")
    extra = bo_sung.get("_khac")
    candidates: dict[str, Any] = dict(extra) if isinstance(extra, Mapping) else {}
    for col in field_keys:
        out_key = rename_map.get(col, col)
        candidates[out_key] = row.get(col)
    if not isinstance(key_order, list):
        return {k: v for k, v in candidates.items() if v is not None}

    out: dict[str, Any] = {}
    for key in key_order:
        if key in candidates:
            out[key] = candidates[key]
    for col in field_keys:
        out_key = rename_map.get(col, col)
        val = row.get(col)
        if out_key not in out and val is not None and val != []:
            out[out_key] = val
    return out


def reconstruct_document(
    spec: RuleDocSpec,
    meta_row: Mapping[str, Any],
    rows_by_table: Mapping[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Dựng lại đúng cấu trúc dict gốc từ dòng meta và các dòng bảng quan hệ."""
    ma = spec.ma
    phan_khac = meta_row.get("phan_khac") or {}
    if not isinstance(phan_khac, Mapping):
        phan_khac = {}

    sections: dict[str, Any] = {}

    if ma == "quy_tac_lieu_than":
        rt_keys = (
            "ten_quoc_te",
            "hoat_chat_ids",
            "chi_so",
            "trang_thai",
            "nguon",
            "nguoi_duyet",
            "muc",
            "nguon_chi_tiet",
            "phoi_hop",
            "bi_danh",
        )
        all_rules = rows_by_table["tri_thuc.quy_tac_lieu_than_v2"]
        sections["quy_tac"] = [
            _unpack_item(row, rt_keys) for row in all_rules if row["danh_sach"] == "quy_tac"
        ]
        sections["quy_tac_cho_duyet"] = [
            _unpack_item(row, rt_keys)
            for row in all_rules
            if row["danh_sach"] == "quy_tac_cho_duyet"
        ]
        kn_keys = ("hoat_chat_id", "loai", "ly_do", "set_id", "url")
        sections["khong_co_nguong"] = [
            _unpack_item(row, kn_keys)
            for row in rows_by_table["tri_thuc.quy_tac_lieu_than_khong_nguong"]
        ]

    elif ma == "quy_tac_gan":
        gan_keys = (
            "ten_quoc_te",
            "hoat_chat_ids",
            "phan_loai_gan",
            "hanh_dong_nhan",
            "khuyen_cao",
            "trang_thai",
            "nguon_chi_tiet",
        )
        sections["quy_tac"] = [
            _unpack_item(row, gan_keys) for row in rows_by_table["tri_thuc.quy_tac_gan"]
        ]

    elif ma == "nguong_xet_nghiem":
        xn_keys = (
            "ten_quoc_te",
            "hoat_chat_ids",
            "xet_nghiem",
            "dieu_kien",
            "hanh_dong_nhan",
            "don_vi_nhan",
            "don_vi_trong_ca",
            "trang_thai",
            "kieu_dieu_kien",
            "muc_do_de_xuat",
            "dieu_kien_khac",
            "ghi_chu",
            "nguon_chi_tiet",
        )
        sections["quy_tac"] = [
            _unpack_item(row, xn_keys) for row in rows_by_table["tri_thuc.nguong_xet_nghiem"]
        ]

    elif ma == "thuoc_benh_icd":
        ax_keys = (
            "ten_benh",
            "ma_icd10",
            "ghi_chu",
            "khong_anh_xa",
            "hoat_chat_ids",
            "so_dong_ddinter",
            "muc_do_cao_nhat",
            "trang_thai",
        )
        kc_keys = ("ca_id", "hoat_chat_id", "ten_benh", "ma_icd10_ca")
        tb_keys = (
            "hoat_chat_id",
            "ddinter_id",
            "ten_benh",
            "ma_icd10",
            "muc_do",
            "noi_dung",
            "url",
            "trang_thai",
        )
        sections["anh_xa"] = [
            _unpack_item(row, ax_keys) for row in rows_by_table["tri_thuc.anh_xa_benh_icd"]
        ]
        sections["cap_khop_chan_doan_ca"] = [
            _unpack_item(row, kc_keys) for row in rows_by_table["tri_thuc.tuong_tac_benh_khop_ca"]
        ]
        sections["cap_thuoc_benh"] = [
            _unpack_item(row, tb_keys) for row in rows_by_table["tri_thuc.tuong_tac_benh"]
        ]

    elif ma == "duong_dung_hop_le":
        dd_keys = (
            "ma_dong",
            "hoat_chat_ids",
            "nhom_dang_bao_che",
            "ten_nhom_dang",
            "duong_dung_hop_le",
            "muc_chac_chan",
            "nguon",
            "ghi_chu",
            "trang_thai",
        )
        sections["nhom"] = [
            _unpack_item(row, dd_keys) for row in rows_by_table["tri_thuc.duong_dung_hop_le"]
        ]
        norm_rows = rows_by_table["tri_thuc.chuan_hoa_duong_dung"]
        norm_parts: dict[str, Any] = {
            "ma_chuan": [],
            "khoa_sang_ma": {},
            "tu_mo_ho": {},
            "cach_viet_trong_66_ca": [],
            "ma_fda_sang_ma_chuan": {},
        }
        for row in norm_rows:
            loai = row["loai"]
            if loai == "ma_chuan":
                norm_parts["ma_chuan"].append(row["gia_tri"])
            elif loai == "khoa_sang_ma":
                gia_tri = row["gia_tri"]
                val = (
                    gia_tri["duong_dung"]
                    if isinstance(gia_tri, Mapping) and "duong_dung" in gia_tri
                    else row.get("duong_dung")
                )
                norm_parts["khoa_sang_ma"][row["khoa"]] = val
            elif loai == "tu_mo_ho":
                gia_tri = row["gia_tri"]
                val = gia_tri["mo_ta"] if isinstance(gia_tri, Mapping) else gia_tri
                norm_parts["tu_mo_ho"][row["khoa"]] = val
            elif loai == "cach_viet_trong_66_ca":
                norm_parts["cach_viet_trong_66_ca"].append(row["gia_tri"])
            elif loai == "ma_fda_sang_ma_chuan":
                norm_parts["ma_fda_sang_ma_chuan"][row["khoa"]] = row["gia_tri"]
        norm_meta = phan_khac.get("_bang_chuan_hoa_meta")
        if isinstance(norm_meta, Mapping):
            for key, val in norm_meta.items():
                if key != "_thu_tu_khoa":
                    norm_parts[key] = val
            key_order = norm_meta.get("_thu_tu_khoa")
            if isinstance(key_order, list):
                ordered_norm: dict[str, Any] = {}
                for k in key_order:
                    if k in norm_parts:
                        ordered_norm[k] = norm_parts[k]
                norm_parts = ordered_norm
        sections["bang_chuan_hoa_duong_dung"] = norm_parts

    elif ma == "lieu_toi_da":
        md_keys = (
            "ma_dong",
            "hoat_chat_ids",
            "duong_dung",
            "doi_tuong",
            "dieu_kien",
            "dieu_kien_khac",
            "loai_gioi_han",
            "lieu_toi_da_lan",
            "lieu_toi_da_ngay",
            "lieu_toi_da_tuan",
            "theo_kg",
            "thuoc_dung_cung_hoat_chat_ids",
            "quy_doi_don_vi",
            "ghi_chu",
            "nguon",
            "trang_thai",
        )
        dt_keys = (
            "tuoi_tu",
            "tuoi_den",
            "tuoi_tren",
            "tuoi_duoi",
            "bao_gom_can_duoi",
            "bao_gom_can_tren",
            "tuoi_thang_tu",
            "tuoi_thang_den",
            "tuoi_ngay_tu",
            "tuoi_ngay_den",
            "can_nang_tu",
            "can_nang_den",
            "can_nang_tren",
            "can_nang_duoi",
            "dieu_kien_khac",
        )
        kg_keys = ("hoat_chat_id", "co_dong_theo_nhom_dac_biet", "ly_do")
        kgc_keys = ("hoat_chat_ids", "duong_dung")
        sections["nhom"] = [
            _unpack_item(row, md_keys) for row in rows_by_table["tri_thuc.lieu_toi_da"]
        ]
        sections["khong_ghi_toi_da"] = [
            _unpack_item(row, kg_keys) for row in rows_by_table["tri_thuc.lieu_toi_da_khong_ghi"]
        ]
        sections["khong_ghi_toi_da_theo_duong_trong_ca"] = [
            _unpack_item(row, kgc_keys)
            for row in rows_by_table["tri_thuc.lieu_toi_da_khong_ghi_duong_ca"]
        ]
        sections["doi_tuong_dinh_nghia"] = {
            row["ma"]: _unpack_item(row, dt_keys)
            for row in rows_by_table["tri_thuc.doi_tuong_dinh_nghia"]
        }

    elif ma == "doc_tinh":
        dt_tox_keys = (
            "hoat_chat_id",
            "nhom",
            "muc_nhan",
            "ma_xet_nghiem_nong_do",
            "likelihood_score",
            "danh_sach",
            "ly_do",
            "nguon",
            "trang_thai",
        )
        grouped: dict[str, list[dict[str, Any]]] = {k: [] for k in spec.danh_sach_khoa}
        for row in rows_by_table["tri_thuc.canh_bao_doc_tinh"]:
            grouped[row["loai"]].append(_unpack_item(row, dt_tox_keys))
        sections.update(grouped)

    elif ma == "khang_sinh_quan_ly":
        nh_keys = ("ma_nhom", "ten_nhom_van_ban", "yeu_cau", "trang_pdf")
        ks_keys = ("ten_trong_van_ban", "hoat_chat_ids", "ma_nhom", "trang_pdf", "trang_thai")
        kx_keys = ("ten_trong_van_ban", "ma_nhom", "trang_pdf", "ly_do")
        sections["nhom"] = [
            _unpack_item(row, nh_keys) for row in rows_by_table["tri_thuc.khang_sinh_han_che_nhom"]
        ]
        sections["khang_sinh"] = [
            _unpack_item(row, ks_keys) for row in rows_by_table["tri_thuc.khang_sinh_han_che"]
        ]
        sections["khong_anh_xa"] = [
            _unpack_item(row, kx_keys) for row in rows_by_table["tri_thuc.khang_sinh_khong_anh_xa"]
        ]

    elif ma == "di_ung_cheo":
        dc_keys = (
            "ma_nhom",
            "ten_nhom",
            "hoat_chat_ids",
            "hoat_chat_lien_quan",
            "huong",
            "co_so",
            "nguon",
            "ghi_chu",
            "trang_thai",
        )
        ax_alias_keys = ("hoat_chat_ids", "ma_nhom")
        sections["nhom"] = [
            _unpack_item(row, dc_keys) for row in rows_by_table["tri_thuc.nhom_di_ung_cheo"]
        ]
        sections["ten_nhom_di_ung_sang_hoat_chat"] = {
            row["ten_alias"]: _unpack_item(row, ax_alias_keys)
            for row in rows_by_table["tri_thuc.nhom_di_ung_anh_xa"]
        }

    elif ma == "hoat_chat":
        hc_keys = ("hoat_chat_id", "ten_inn", "ten_viet", "dong_nghia", "thanh_phan", "nhom")
        sections["hoat_chat"] = [
            _unpack_item(row, hc_keys) for row in rows_by_table["tri_thuc.danh_muc_hoat_chat_demo"]
        ]
        sections["nhan"] = {
            row["ten_goi"]: row["hoat_chat_ids"]
            for row in rows_by_table["tri_thuc.danh_muc_hoat_chat_demo_nhan"]
        }

    elif ma == "nhom_dieu_tri_trung":
        tr_keys = (
            "ma_nhom",
            "ten",
            "tien_to_atc",
            "tien_to_atc_loai_tru",
            "muc_do",
            "ly_do",
            "nguon",
            "ngoai_le",
        )
        sections["nhom"] = [
            _unpack_item(row, tr_keys) for row in rows_by_table["tri_thuc.nhom_dieu_tri_trung"]
        ]

    elif ma == "atc_bo_sung":
        sections["ma_atc"] = {
            row["hoat_chat_id"]: row["ma_atc"] for row in rows_by_table["tri_thuc.atc_bo_sung"]
        }

    candidates: dict[str, Any] = {}
    header_keys = phan_khac.get("_khoa_header")
    if isinstance(header_keys, list):
        for key in header_keys:
            candidates[key] = meta_row.get(key)
    else:
        for key in HEADER_SCALAR_KEYS:
            if meta_row.get(key) is not None:
                candidates[key] = meta_row[key]
    for key, val in phan_khac.items():
        if not key.startswith("_"):
            candidates[key] = val
    candidates.update(sections)

    key_order = phan_khac.get("_thu_tu_khoa")
    if isinstance(key_order, list):
        ordered: dict[str, Any] = {}
        for key in key_order:
            if key in candidates:
                ordered[key] = candidates[key]
        for key, val in candidates.items():
            if key not in ordered:
                ordered[key] = val
        return ordered
    return candidates


def load_document(conn: Any, ma: str) -> dict[str, Any]:
    """Đọc các bảng quan hệ từ PostgreSQL và dựng lại nguyên vẹn một tài liệu theo thu_tu."""
    spec = _DOCS_BY_MA.get(ma)
    if spec is None:
        raise BangLuatReadError(f"Không biết mã tài liệu bảng luật: {ma}")
    meta_rows = _query_table(
        conn,
        "tri_thuc.bang_luat_meta",
        where_clause="ma = %s",
        params=(ma,),
        order_by="ma ASC",
    )
    if not meta_rows:
        raise BangLuatReadError(f"Thiếu siêu dữ liệu tri_thuc.bang_luat_meta cho mã {ma}")
    rows_by_table: dict[str, list[dict[str, Any]]] = {}
    for table in spec.cac_bang:
        rows_by_table[table] = _query_table(
            conn,
            table,
            order_by=_TABLE_ORDER_MAP.get(table, "thu_tu ASC"),
        )
    return reconstruct_document(spec, meta_rows[0], rows_by_table)


def load_all_documents(conn: Any) -> dict[str, dict[str, Any]]:
    """Đọc toàn bộ tài liệu bảng luật từ PostgreSQL trên cùng một kết nối."""
    meta_rows = _query_table(
        conn,
        "tri_thuc.bang_luat_meta",
        order_by="ma ASC",
    )
    meta_by_ma = {str(row["ma"]): row for row in meta_rows if row.get("ma")}
    if not meta_by_ma:
        return {}
    docs: dict[str, dict[str, Any]] = {}
    for spec in RULE_DOCUMENTS:
        meta_row = meta_by_ma.get(spec.ma)
        if meta_row is None:
            continue
        rows_by_table = {
            table: _query_table(
                conn,
                table,
                order_by=_TABLE_ORDER_MAP.get(table, "thu_tu ASC"),
            )
            for table in spec.cac_bang
        }
        docs[spec.ma] = reconstruct_document(spec, meta_row, rows_by_table)
    return docs


@contextmanager
def open_read_connection(url: str) -> Iterator[Any]:
    """Điểm mở kết nối đọc PostgreSQL duy nhất cho bộ nạp bảng luật lúc chạy."""
    with read_pool.connection(url) as conn:
        yield conn


def _database_url(url_env: str = "DATABASE_URL") -> str | None:
    """Đọc DSN từ môi trường cấu hình, trả None nếu thiếu hoặc rỗng."""
    try:
        url = get_secret(url_env).strip()
    except ConfigError:
        return None
    return url or None


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    """Đọc tệp YAML và kiểm gốc là dict."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ValueError(f"Không đọc được cấu hình {path.name}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"{path.name}: gốc YAML phải là ánh xạ")
    return raw


def _get_db_document(
    ma: str,
    url_env: str,
    active_logger: logging.Logger,
) -> dict[str, Any] | None:
    """Nạp toàn bộ tài liệu bảng luật từ DB một lần dưới khoá, chia sẻ cho mọi bộ nạp."""
    global _RAW_DB_LOADED, _RAW_DB_KEY, _RAW_DB_DOCS, _RAW_DB_ERROR
    with _DB_CACHE_LOCK:
        url = _database_url(url_env)
        key = (url_env, url)
        if not _RAW_DB_LOADED or _RAW_DB_KEY != key:
            _RAW_DB_KEY = key
            _RAW_DB_DOCS = {}
            _RAW_DB_ERROR = None
            _WARNED_DB_DOCS.clear()
            if url is None:
                _RAW_DB_ERROR = ("missing_env", url_env)
            else:
                try:
                    with open_read_connection(url) as conn:
                        _RAW_DB_DOCS = load_all_documents(conn)
                except (
                    BangLuatReadError,
                    ConfigError,
                    OSError,
                    psycopg.Error,
                    sqlite3.Error,
                    ValueError,
                ) as exc:
                    _RAW_DB_DOCS = {}
                    _RAW_DB_ERROR = ("exc", type(exc).__name__)
            _RAW_DB_LOADED = True

        if _RAW_DB_ERROR is not None:
            if ma not in _WARNED_DB_DOCS:
                _WARNED_DB_DOCS.add(ma)
                kind, detail = _RAW_DB_ERROR
                if kind == "missing_env":
                    active_logger.warning(
                        "Không nạp được bảng luật %s từ DB: thiếu %s",
                        ma,
                        detail,
                    )
                else:
                    active_logger.warning(
                        "Không nạp được bảng luật %s từ DB (%s)",
                        ma,
                        detail,
                    )
            return None

        raw = _RAW_DB_DOCS.get(ma)
        if raw is None:
            if ma not in _WARNED_DB_DOCS:
                _WARNED_DB_DOCS.add(ma)
                active_logger.warning(
                    "Không nạp được bảng luật %s từ DB (%s)",
                    ma,
                    "BangLuatReadError",
                )
            return None
        return raw


def load_rule_data(
    ma: str,
    file_path: Path,
    parser: Callable[[dict[str, Any]], _T],
    *,
    logger: logging.Logger | None = None,
    fmt: Literal["json", "yaml"] = "json",
    url_env: str = "DATABASE_URL",
) -> _T | None:
    """Nạp bảng luật từ tệp hoặc PostgreSQL theo `KB_SOURCE`; lỗi chỉ log cảnh báo 1 lần."""
    active_logger = logger or _LOGGER
    kb_source = load_kb_source()

    def _from_file() -> _T | None:
        try:
            raw = (
                json.loads(file_path.read_text(encoding="utf-8"))
                if fmt == "json"
                else _read_yaml_mapping(file_path)
            )
            if not isinstance(raw, dict):
                raise ValueError("Gốc tài liệu không phải ánh xạ")
            return parser(raw)
        except (OSError, UnicodeError, ValueError, ValidationError) as exc:
            active_logger.warning(
                "Không nạp được bảng luật %s từ tệp (%s)",
                ma,
                type(exc).__name__,
            )
            return None

    def _from_db() -> _T | None:
        raw = _get_db_document(ma, url_env, active_logger)
        if raw is None:
            return None
        try:
            return parser(raw)
        except (ValueError, ValidationError) as exc:
            active_logger.warning(
                "Không nạp được bảng luật %s từ DB (%s)",
                ma,
                type(exc).__name__,
            )
            return None

    if kb_source == "file":
        return _from_file()
    if kb_source == "db":
        return _from_db()
    if file_path.is_file():
        return _from_file()
    return _from_db()
