"""Kiểm định và nạp 12 bảng luật/danh mục D1-D7 từ tệp JSON/YAML lên PostgreSQL."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from app.db.bang_luat_store import (
    HEADER_SCALAR_KEYS,
    RULE_DOCUMENTS,
    RULE_TABLES,
    TABLE_SPECS,
    BangLuatReadError,
    RuleDocSpec,
    clear_all_caches,
    load_document,
    load_rule_data,
    reconstruct_document,
    register_cache_clear,
)
from app.db.sources import SourceError

__all__ = [
    "BangLuatReadError",
    "PreparedDocument",
    "RULE_DOCUMENTS",
    "RULE_TABLES",
    "RuleDocSpec",
    "clear_all_caches",
    "expected_table_counts",
    "inspect_bang_luat",
    "load_bang_luat",
    "load_document",
    "load_rule_data",
    "prepare_document",
    "reconstruct_document",
    "register_cache_clear",
    "validate_document",
]


@dataclass(frozen=True)
class PreparedDocument:
    """Tài liệu đã kiểm định pydantic và tách thành dòng sẵn sàng nạp DB."""

    spec: RuleDocSpec
    raw: dict[str, Any]
    meta_row: dict[str, Any]
    rows_by_table: dict[str, list[dict[str, Any]]]


def _single_hc_id(ids: Iterable[Any] | None) -> str | None:
    """Lấy mã hoạt chất đơn để lập chỉ mục B-tree khi danh sách đúng 1 phần tử."""
    if not ids:
        return None
    items = list(ids)
    if len(items) != 1:
        return None
    val = str(items[0]).strip()
    return val or None


def _insert_table_rows(conn: Any, table: str, rows: list[dict[str, Any]]) -> None:
    """Chèn danh sách hàng vào bảng PostgreSQL dùng placeholder %s và Jsonb."""
    if not rows:
        return
    columns, json_cols, _ = TABLE_SPECS[table]
    col_sql = ", ".join(columns)
    placeholders = ", ".join("%s" for _ in columns)
    sql_text = f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders})"
    payload = [
        tuple(
            Jsonb(row[col]) if col in json_cols and row.get(col) is not None else row.get(col)
            for col in columns
        )
        for row in rows
    ]
    executemany = getattr(conn, "executemany", None)
    if callable(executemany):
        executemany(sql_text, payload)
    else:
        for params in payload:
            conn.execute(sql_text, params)


def _pack_extra(item: Mapping[str, Any], known_keys: Iterable[str]) -> dict[str, Any]:
    """Gói danh sách khoá gốc và phần ngoài cột để dựng lại không mất chi tiết."""
    known = set(known_keys)
    extra = {k: v for k, v in item.items() if k not in known}
    packed: dict[str, Any] = {"_khoa": list(item.keys())}
    if extra:
        packed["_khac"] = extra
    return packed


def _read_source_file(path: Path, fmt: Literal["json", "yaml"]) -> tuple[dict[str, Any], str]:
    """Đọc và kiểm tra tệp nguồn JSON/YAML, trả (dict gốc, sha256)."""
    try:
        raw_bytes = path.read_bytes()
    except OSError as exc:
        raise SourceError(f"Không đọc được {path}: {exc}") from exc
    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    try:
        text = raw_bytes.decode("utf-8")
        if fmt == "json":
            parsed = json.loads(text)
        else:
            parsed = yaml.safe_load(text)
    except (UnicodeError, ValueError, yaml.YAMLError) as exc:
        raise SourceError(f"Tệp {path} sai định dạng {fmt.upper()}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SourceError(f"Tệp {path} phải có gốc là đối tượng/ánh xạ")
    return parsed, sha256


def validate_document(ma: str, raw: dict[str, Any]) -> None:
    """Kiểm định dữ liệu tài liệu bằng đúng mô hình pydantic của bộ nạp tương ứng."""
    from app.kb.names import DrugNameCatalog
    from app.rules.allergy_config import AllergyCrossConfig
    from app.rules.d4_config import DrugDiseaseConfig, HepaticConfig, LabThresholdConfig
    from app.rules.d5_config import MaxDoseConfig, RouteConfig
    from app.rules.d6_config import ToxicityConfig
    from app.rules.d7_config import StewardshipConfig
    from app.rules.duplicate_config import AtcSupplement, TreatmentGroups
    from app.rules.renal_dose import RenalRuleBook

    validators: dict[str, Callable[[Any], Any]] = {
        "quy_tac_lieu_than": RenalRuleBook.model_validate,
        "quy_tac_gan": HepaticConfig.model_validate,
        "nguong_xet_nghiem": LabThresholdConfig.model_validate,
        "thuoc_benh_icd": DrugDiseaseConfig.model_validate,
        "duong_dung_hop_le": RouteConfig.model_validate,
        "lieu_toi_da": MaxDoseConfig.model_validate,
        "doc_tinh": ToxicityConfig.model_validate,
        "khang_sinh_quan_ly": StewardshipConfig.model_validate,
        "di_ung_cheo": AllergyCrossConfig.model_validate,
        "hoat_chat": DrugNameCatalog.model_validate,
        "nhom_dieu_tri_trung": TreatmentGroups.model_validate,
        "atc_bo_sung": AtcSupplement.model_validate,
    }
    fn = validators.get(ma)
    if fn is None:
        raise SourceError(f"Mã bảng luật không hợp lệ: {ma}")
    try:
        fn(raw)
    except ValidationError as exc:
        details = "; ".join(
            f"{'/'.join(map(str, err['loc']))}: {err['msg']}"
            for err in exc.errors(include_input=False, include_context=False)
        )
        raise SourceError(f"Bảng luật {ma} không hợp lệ: {details}") from exc


def _build_meta_row(
    spec: RuleDocSpec,
    raw: Mapping[str, Any],
    sha256_tep: str,
    extra_meta: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Tạo dòng cho tri_thuc.bang_luat_meta giữ các khoá phi-danh-sách để dựng lại nguyên vẹn."""
    excluded = set(spec.danh_sach_khoa) | set(HEADER_SCALAR_KEYS)
    phan_khac: dict[str, Any] = {
        "_thu_tu_khoa": list(raw.keys()),
        "_khoa_header": [k for k in HEADER_SCALAR_KEYS if k in raw],
    }
    for key, value in raw.items():
        if key not in excluded:
            phan_khac[key] = value
    if extra_meta:
        phan_khac.update(extra_meta)
    return {
        "ma": spec.ma,
        "ten": raw.get("ten"),
        "phien_ban": raw.get("phien_ban"),
        "ngay": raw.get("ngay"),
        "trang_thai": raw.get("trang_thai"),
        "ghi_chu": raw.get("ghi_chu"),
        "nguon": raw.get("nguon"),
        "phan_khac": phan_khac,
        "sha256_tep": sha256_tep,
    }


def _decompose_document(
    spec: RuleDocSpec, raw: Mapping[str, Any], sha256_tep: str
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    """Tách một tài liệu JSON/YAML thành các dòng bảng quan hệ theo đúng đặc tả."""
    ma = spec.ma
    phien_ban = str(raw.get("phien_ban") or "")
    extra_meta: dict[str, Any] = {}
    rows: dict[str, list[dict[str, Any]]] = {tbl: [] for tbl in spec.cac_bang}

    if ma == "quy_tac_lieu_than":
        extracted = (
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
        for section in ("quy_tac", "quy_tac_cho_duyet"):
            for idx, item in enumerate(raw.get(section) or []):
                hc_ids = item.get("hoat_chat_ids")
                rows["tri_thuc.quy_tac_lieu_than_v2"].append(
                    {
                        "danh_sach": section,
                        "thu_tu": idx,
                        "ten_quoc_te": item["ten_quoc_te"],
                        "hoat_chat_ids": hc_ids if hc_ids is not None else [],
                        "hoat_chat_id": _single_hc_id(hc_ids),
                        "chi_so": item.get("chi_so"),
                        "trang_thai": item.get("trang_thai"),
                        "nguon": item["nguon"],
                        "nguoi_duyet": item.get("nguoi_duyet"),
                        "muc": item["muc"],
                        "nguon_chi_tiet": item.get("nguon_chi_tiet"),
                        "phoi_hop": item.get("phoi_hop"),
                        "bi_danh": item.get("bi_danh"),
                        "phien_ban": phien_ban,
                        "bo_sung": _pack_extra(item, extracted),
                    }
                )
        kn_keys = ("hoat_chat_id", "loai", "ly_do", "set_id", "url")
        for idx, item in enumerate(raw.get("khong_co_nguong") or []):
            rows["tri_thuc.quy_tac_lieu_than_khong_nguong"].append(
                {
                    "thu_tu": idx,
                    "hoat_chat_id": item["hoat_chat_id"],
                    "loai": item["loai"],
                    "ly_do": item["ly_do"],
                    "set_id": item.get("set_id"),
                    "url": item.get("url"),
                    "phien_ban": phien_ban,
                    "bo_sung": _pack_extra(item, kn_keys),
                }
            )

    elif ma == "quy_tac_gan":
        extracted = (
            "ten_quoc_te",
            "hoat_chat_ids",
            "phan_loai_gan",
            "hanh_dong_nhan",
            "khuyen_cao",
            "trang_thai",
            "nguon_chi_tiet",
        )
        for idx, item in enumerate(raw.get("quy_tac") or []):
            hc_ids = item.get("hoat_chat_ids") or []
            rows["tri_thuc.quy_tac_gan"].append(
                {
                    "thu_tu": idx,
                    "ten_quoc_te": item["ten_quoc_te"],
                    "hoat_chat_ids": hc_ids,
                    "hoat_chat_id": _single_hc_id(hc_ids),
                    "phan_loai_gan": item.get("phan_loai_gan") or [],
                    "hanh_dong_nhan": item["hanh_dong_nhan"],
                    "khuyen_cao": item["khuyen_cao"],
                    "trang_thai": item.get("trang_thai"),
                    "nguon_chi_tiet": item.get("nguon_chi_tiet") or [],
                    "phien_ban": phien_ban or None,
                    "bo_sung": _pack_extra(item, extracted),
                }
            )

    elif ma == "nguong_xet_nghiem":
        extracted = (
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
        for idx, item in enumerate(raw.get("quy_tac") or []):
            hc_ids = item.get("hoat_chat_ids") or []
            rows["tri_thuc.nguong_xet_nghiem"].append(
                {
                    "thu_tu": idx,
                    "ten_quoc_te": item.get("ten_quoc_te"),
                    "hoat_chat_ids": hc_ids,
                    "hoat_chat_id": _single_hc_id(hc_ids),
                    "xet_nghiem": item["xet_nghiem"],
                    "dieu_kien": item.get("dieu_kien") or [],
                    "hanh_dong_nhan": item["hanh_dong_nhan"],
                    "don_vi_nhan": item.get("don_vi_nhan"),
                    "don_vi_trong_ca": item.get("don_vi_trong_ca"),
                    "trang_thai": item.get("trang_thai"),
                    "kieu_dieu_kien": item.get("kieu_dieu_kien"),
                    "muc_do_de_xuat": item.get("muc_do_de_xuat"),
                    "dieu_kien_khac": item.get("dieu_kien_khac"),
                    "ghi_chu": item.get("ghi_chu"),
                    "nguon_chi_tiet": item.get("nguon_chi_tiet") or [],
                    "phien_ban": phien_ban or None,
                    "bo_sung": _pack_extra(item, extracted),
                }
            )

    elif ma == "thuoc_benh_icd":
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
        for idx, item in enumerate(raw.get("cap_thuoc_benh") or []):
            rows["tri_thuc.tuong_tac_benh"].append(
                {
                    "thu_tu": idx,
                    "hoat_chat_id": item["hoat_chat_id"],
                    "ddinter_id": item.get("ddinter_id"),
                    "ten_benh": item["ten_benh"],
                    "ma_icd10": item.get("ma_icd10") or [],
                    "muc_do": item["muc_do"],
                    "noi_dung": item.get("noi_dung", ""),
                    "url": item.get("url"),
                    "trang_thai": item.get("trang_thai"),
                    "phien_ban": phien_ban or None,
                    "bo_sung": _pack_extra(item, tb_keys),
                }
            )
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
        for idx, item in enumerate(raw.get("anh_xa") or []):
            hc_ids = item.get("hoat_chat_ids") or []
            rows["tri_thuc.anh_xa_benh_icd"].append(
                {
                    "thu_tu": idx,
                    "ten_benh": item["ten_benh"],
                    "ma_icd10": item.get("ma_icd10") or [],
                    "ghi_chu": item.get("ghi_chu"),
                    "khong_anh_xa": bool(item["khong_anh_xa"]),
                    "hoat_chat_ids": hc_ids,
                    "hoat_chat_id": _single_hc_id(hc_ids),
                    "so_dong_ddinter": item.get("so_dong_ddinter"),
                    "muc_do_cao_nhat": item.get("muc_do_cao_nhat"),
                    "trang_thai": item.get("trang_thai"),
                    "phien_ban": phien_ban or None,
                    "bo_sung": _pack_extra(item, ax_keys),
                }
            )
        kc_keys = ("ca_id", "hoat_chat_id", "ten_benh", "ma_icd10_ca")
        for idx, item in enumerate(raw.get("cap_khop_chan_doan_ca") or []):
            rows["tri_thuc.tuong_tac_benh_khop_ca"].append(
                {
                    "thu_tu": idx,
                    "ca_id": item["ca_id"],
                    "hoat_chat_id": item["hoat_chat_id"],
                    "ten_benh": item["ten_benh"],
                    "ma_icd10_ca": item.get("ma_icd10_ca"),
                    "phien_ban": phien_ban or None,
                    "bo_sung": _pack_extra(item, kc_keys),
                }
            )

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
        for idx, item in enumerate(raw.get("nhom") or []):
            hc_ids = item.get("hoat_chat_ids") or []
            rows["tri_thuc.duong_dung_hop_le"].append(
                {
                    "ma_dong": item.get("ma_dong", ""),
                    "thu_tu": idx,
                    "hoat_chat_ids": hc_ids,
                    "hoat_chat_id": _single_hc_id(hc_ids),
                    "nhom_dang_bao_che": item["nhom_dang_bao_che"],
                    "ten_nhom_dang": item.get("ten_nhom_dang"),
                    "duong_dung_hop_le": item.get("duong_dung_hop_le") or [],
                    "muc_chac_chan": item.get("muc_chac_chan"),
                    "nguon": item.get("nguon") or [],
                    "ghi_chu": item.get("ghi_chu"),
                    "trang_thai": item.get("trang_thai"),
                    "phien_ban": phien_ban or None,
                    "bo_sung": _pack_extra(item, dd_keys),
                }
            )
        norm = raw.get("bang_chuan_hoa_duong_dung") or {}
        norm_seq = 0
        for item in norm.get("ma_chuan") or []:
            rows["tri_thuc.chuan_hoa_duong_dung"].append(
                {
                    "thu_tu": norm_seq,
                    "loai": "ma_chuan",
                    "khoa": item["ma"],
                    "duong_dung": item["ma"],
                    "gia_tri": item,
                    "phien_ban": phien_ban or None,
                }
            )
            norm_seq += 1
        for k, v in (norm.get("khoa_sang_ma") or {}).items():
            rows["tri_thuc.chuan_hoa_duong_dung"].append(
                {
                    "thu_tu": norm_seq,
                    "loai": "khoa_sang_ma",
                    "khoa": k,
                    "duong_dung": v,
                    "gia_tri": {"duong_dung": v},
                    "phien_ban": phien_ban or None,
                }
            )
            norm_seq += 1
        for k, v in (norm.get("tu_mo_ho") or {}).items():
            rows["tri_thuc.chuan_hoa_duong_dung"].append(
                {
                    "thu_tu": norm_seq,
                    "loai": "tu_mo_ho",
                    "khoa": k,
                    "duong_dung": None,
                    "gia_tri": {"mo_ta": v},
                    "phien_ban": phien_ban or None,
                }
            )
            norm_seq += 1
        for item in norm.get("cach_viet_trong_66_ca") or []:
            rows["tri_thuc.chuan_hoa_duong_dung"].append(
                {
                    "thu_tu": norm_seq,
                    "loai": "cach_viet_trong_66_ca",
                    "khoa": item["viet_trong_ca"],
                    "duong_dung": item.get("ma_chuan"),
                    "gia_tri": item,
                    "phien_ban": phien_ban or None,
                }
            )
            norm_seq += 1
        for k, v in (norm.get("ma_fda_sang_ma_chuan") or {}).items():
            rows["tri_thuc.chuan_hoa_duong_dung"].append(
                {
                    "thu_tu": norm_seq,
                    "loai": "ma_fda_sang_ma_chuan",
                    "khoa": k,
                    "duong_dung": v[0] if len(v) == 1 else None,
                    "gia_tri": v,
                    "phien_ban": phien_ban or None,
                }
            )
            norm_seq += 1
        norm_sections = {
            "ma_chuan",
            "khoa_sang_ma",
            "tu_mo_ho",
            "cach_viet_trong_66_ca",
            "ma_fda_sang_ma_chuan",
        }
        extra_meta["_bang_chuan_hoa_meta"] = {
            "_thu_tu_khoa": list(norm.keys()),
            **{k: v for k, v in norm.items() if k not in norm_sections},
        }

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
        for idx, item in enumerate(raw.get("nhom") or []):
            hc_ids = item.get("hoat_chat_ids") or []
            rows["tri_thuc.lieu_toi_da"].append(
                {
                    "ma_dong": item.get("ma_dong", ""),
                    "thu_tu": idx,
                    "hoat_chat_ids": hc_ids,
                    "hoat_chat_id": _single_hc_id(hc_ids),
                    "duong_dung": item.get("duong_dung") or [],
                    "doi_tuong": item["doi_tuong"],
                    "dieu_kien": item.get("dieu_kien"),
                    "dieu_kien_khac": item.get("dieu_kien_khac"),
                    "loai_gioi_han": item.get("loai_gioi_han", "toi_da_ro"),
                    "lieu_toi_da_lan": item.get("lieu_toi_da_lan"),
                    "lieu_toi_da_ngay": item.get("lieu_toi_da_ngay"),
                    "lieu_toi_da_tuan": item.get("lieu_toi_da_tuan"),
                    "theo_kg": item.get("theo_kg"),
                    "thuoc_dung_cung_hoat_chat_ids": item.get("thuoc_dung_cung_hoat_chat_ids"),
                    "quy_doi_don_vi": item.get("quy_doi_don_vi"),
                    "ghi_chu": item.get("ghi_chu"),
                    "nguon": item.get("nguon"),
                    "trang_thai": item.get("trang_thai"),
                    "phien_ban": phien_ban or None,
                    "bo_sung": _pack_extra(item, md_keys),
                }
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
        for idx, (code, item) in enumerate((raw.get("doi_tuong_dinh_nghia") or {}).items()):
            rows["tri_thuc.doi_tuong_dinh_nghia"].append(
                {
                    "ma": code,
                    "thu_tu": idx,
                    **{k: item.get(k) for k in dt_keys},
                    "phien_ban": phien_ban or None,
                    "bo_sung": _pack_extra(item, dt_keys),
                }
            )
        kg_keys = ("hoat_chat_id", "co_dong_theo_nhom_dac_biet", "ly_do")
        for idx, item in enumerate(raw.get("khong_ghi_toi_da") or []):
            rows["tri_thuc.lieu_toi_da_khong_ghi"].append(
                {
                    "thu_tu": idx,
                    "hoat_chat_id": item["hoat_chat_id"],
                    "co_dong_theo_nhom_dac_biet": item.get("co_dong_theo_nhom_dac_biet"),
                    "ly_do": item["ly_do"],
                    "phien_ban": phien_ban or None,
                    "bo_sung": _pack_extra(item, kg_keys),
                }
            )
        kgc_keys = ("hoat_chat_ids", "duong_dung")
        for idx, item in enumerate(raw.get("khong_ghi_toi_da_theo_duong_trong_ca") or []):
            hc_ids = item.get("hoat_chat_ids") or []
            rows["tri_thuc.lieu_toi_da_khong_ghi_duong_ca"].append(
                {
                    "thu_tu": idx,
                    "hoat_chat_ids": hc_ids,
                    "hoat_chat_id": _single_hc_id(hc_ids),
                    "duong_dung": item["duong_dung"],
                    "phien_ban": phien_ban or None,
                    "bo_sung": _pack_extra(item, kgc_keys),
                }
            )

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
        sections = (
            "doc_than",
            "keo_dai_qt",
            "khoang_dieu_tri_hep",
            "doc_gan_livertox",
            "khong_co_nguon",
        )
        for section in sections:
            for idx, item in enumerate(raw.get(section) or []):
                rows["tri_thuc.canh_bao_doc_tinh"].append(
                    {
                        "thu_tu": idx,
                        "loai": section,
                        "hoat_chat_id": item["hoat_chat_id"],
                        "nhom": item.get("nhom"),
                        "muc_nhan": item.get("muc_nhan"),
                        "ma_xet_nghiem_nong_do": item.get("ma_xet_nghiem_nong_do"),
                        "likelihood_score": item.get("likelihood_score"),
                        "danh_sach": item.get("danh_sach"),
                        "ly_do": item.get("ly_do"),
                        "nguon": item.get("nguon"),
                        "trang_thai": item.get("trang_thai"),
                        "phien_ban": phien_ban or None,
                        "bo_sung": _pack_extra(item, dt_tox_keys),
                    }
                )

    elif ma == "khang_sinh_quan_ly":
        nh_keys = ("ma_nhom", "ten_nhom_van_ban", "yeu_cau", "trang_pdf")
        for idx, item in enumerate(raw.get("nhom") or []):
            rows["tri_thuc.khang_sinh_han_che_nhom"].append(
                {
                    "ma_nhom": item["ma_nhom"],
                    "thu_tu": idx,
                    "ten_nhom_van_ban": item["ten_nhom_van_ban"],
                    "yeu_cau": item["yeu_cau"],
                    "trang_pdf": int(item.get("trang_pdf", 0)),
                    "phien_ban": phien_ban or None,
                    "bo_sung": _pack_extra(item, nh_keys),
                }
            )
        ks_keys = ("ten_trong_van_ban", "hoat_chat_ids", "ma_nhom", "trang_pdf", "trang_thai")
        for idx, item in enumerate(raw.get("khang_sinh") or []):
            hc_ids = item.get("hoat_chat_ids") or []
            rows["tri_thuc.khang_sinh_han_che"].append(
                {
                    "thu_tu": idx,
                    "ten_trong_van_ban": item["ten_trong_van_ban"],
                    "hoat_chat_ids": hc_ids,
                    "hoat_chat_id": _single_hc_id(hc_ids),
                    "ma_nhom": item["ma_nhom"],
                    "trang_pdf": int(item.get("trang_pdf", 0)),
                    "trang_thai": item.get("trang_thai"),
                    "phien_ban": phien_ban or None,
                    "bo_sung": _pack_extra(item, ks_keys),
                }
            )
        kx_keys = ("ten_trong_van_ban", "ma_nhom", "trang_pdf", "ly_do")
        for idx, item in enumerate(raw.get("khong_anh_xa") or []):
            rows["tri_thuc.khang_sinh_khong_anh_xa"].append(
                {
                    "thu_tu": idx,
                    "ten_trong_van_ban": item["ten_trong_van_ban"],
                    "ma_nhom": item.get("ma_nhom", ""),
                    "trang_pdf": int(item.get("trang_pdf", 0)),
                    "ly_do": item["ly_do"],
                    "phien_ban": phien_ban or None,
                    "bo_sung": _pack_extra(item, kx_keys),
                }
            )

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
        for idx, item in enumerate(raw.get("nhom") or []):
            hc_ids = item.get("hoat_chat_ids") or []
            rows["tri_thuc.nhom_di_ung_cheo"].append(
                {
                    "ma_nhom": item["ma_nhom"],
                    "thu_tu": idx,
                    "ten_nhom": item["ten_nhom"],
                    "hoat_chat_ids": hc_ids,
                    "hoat_chat_id": _single_hc_id(hc_ids),
                    "hoat_chat_lien_quan": item.get("hoat_chat_lien_quan") or [],
                    "huong": item["huong"],
                    "co_so": item.get("co_so"),
                    "nguon": item.get("nguon") or [],
                    "ghi_chu": item.get("ghi_chu"),
                    "trang_thai": item.get("trang_thai"),
                    "phien_ban": phien_ban or None,
                    "bo_sung": _pack_extra(item, dc_keys),
                }
            )
        ax_alias_keys = ("hoat_chat_ids", "ma_nhom")
        aliases = raw.get("ten_nhom_di_ung_sang_hoat_chat") or {}
        for idx, (alias_name, item) in enumerate(aliases.items()):
            hc_ids = item.get("hoat_chat_ids") or []
            rows["tri_thuc.nhom_di_ung_anh_xa"].append(
                {
                    "ten_alias": alias_name,
                    "thu_tu": idx,
                    "hoat_chat_ids": hc_ids,
                    "hoat_chat_id": _single_hc_id(hc_ids),
                    "ma_nhom": item["ma_nhom"],
                    "phien_ban": phien_ban or None,
                    "bo_sung": _pack_extra(item, ax_alias_keys),
                }
            )

    elif ma == "hoat_chat":
        hc_keys = ("hoat_chat_id", "ten_inn", "ten_viet", "dong_nghia", "thanh_phan", "nhom")
        for idx, item in enumerate(raw.get("hoat_chat") or []):
            rows["tri_thuc.danh_muc_hoat_chat_demo"].append(
                {
                    "hoat_chat_id": item["hoat_chat_id"],
                    "thu_tu": idx,
                    "ten_inn": item["ten_inn"],
                    "ten_viet": item.get("ten_viet"),
                    "dong_nghia": item.get("dong_nghia") or [],
                    "thanh_phan": item.get("thanh_phan"),
                    "nhom": item.get("nhom"),
                    "phien_ban": phien_ban or None,
                    "bo_sung": _pack_extra(item, hc_keys),
                }
            )
        for idx, (label, ids) in enumerate((raw.get("nhan") or {}).items()):
            rows["tri_thuc.danh_muc_hoat_chat_demo_nhan"].append(
                {
                    "ten_goi": label,
                    "thu_tu": idx,
                    "hoat_chat_ids": ids,
                    "hoat_chat_id": _single_hc_id(ids),
                    "phien_ban": phien_ban or None,
                }
            )

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
        for idx, item in enumerate(raw.get("nhom") or []):
            rows["tri_thuc.nhom_dieu_tri_trung"].append(
                {
                    "ma_nhom": item["ma_nhom"],
                    "thu_tu": idx,
                    "ten": item["ten"],
                    "tien_to_atc": item.get("tien_to_atc") or [],
                    "tien_to_atc_loai_tru": item.get("tien_to_atc_loai_tru"),
                    "muc_do": item["muc_do"],
                    "ly_do": item["ly_do"],
                    "nguon": item["nguon"],
                    "ngoai_le": item.get("ngoai_le") or [],
                    "phien_ban": phien_ban or None,
                    "bo_sung": _pack_extra(item, tr_keys),
                }
            )

    elif ma == "atc_bo_sung":
        for idx, (hc_id, codes) in enumerate((raw.get("ma_atc") or {}).items()):
            rows["tri_thuc.atc_bo_sung"].append(
                {
                    "hoat_chat_id": hc_id,
                    "thu_tu": idx,
                    "ma_atc": codes,
                    "phien_ban": phien_ban or None,
                }
            )

    meta_row = _build_meta_row(spec, raw, sha256_tep, extra_meta)
    return meta_row, rows


def prepare_document(spec: RuleDocSpec, root: Path) -> PreparedDocument:
    """Đọc tệp, kiểm pydantic và tách thành dòng bảng quan hệ kèm kiểm vòng khép kín."""
    path = root / spec.tep
    raw, sha256_tep = _read_source_file(path, spec.dinh_dang)
    validate_document(spec.ma, raw)
    meta_row, rows_by_table = _decompose_document(spec, raw, sha256_tep)
    if reconstruct_document(spec, meta_row, rows_by_table) != raw:
        raise SourceError(f"Tách dòng {spec.ma} không dựng lại được nguyên tài liệu")
    return PreparedDocument(spec=spec, raw=raw, meta_row=meta_row, rows_by_table=rows_by_table)


def inspect_bang_luat(root: Path) -> list[PreparedDocument]:
    """Đọc và kiểm định toàn bộ 12 bảng luật/danh mục trước khi kết nối CSDL."""
    return [prepare_document(spec, root) for spec in RULE_DOCUMENTS]


def expected_table_counts(prepared: Iterable[PreparedDocument]) -> dict[str, int]:
    """Tính số dòng đích dự kiến cho toàn bộ 24 bảng từ danh sách tài liệu đã chuẩn bị."""
    counts = {table: 0 for table in RULE_TABLES}
    for doc in prepared:
        counts["tri_thuc.bang_luat_meta"] += 1
        for table, table_rows in doc.rows_by_table.items():
            counts[table] += len(table_rows)
    return counts


def load_bang_luat(conn: Any, root: Path) -> dict[str, int]:
    """Nạp toàn bộ 12 bảng luật vào DB trong một giao dịch và đối chiếu từng tài liệu."""
    prepared = inspect_bang_luat(root)
    counts = expected_table_counts(prepared)
    with conn.transaction():
        conn.execute(f"TRUNCATE {', '.join(RULE_TABLES)} RESTART IDENTITY")
        _insert_table_rows(conn, "tri_thuc.bang_luat_meta", [doc.meta_row for doc in prepared])
        for doc in prepared:
            for table in doc.spec.cac_bang:
                _insert_table_rows(conn, table, doc.rows_by_table[table])
        for doc in prepared:
            try:
                reconstructed = load_document(conn, doc.spec.ma)
            except BangLuatReadError as exc:
                raise SourceError(str(exc)) from exc
            if reconstructed != doc.raw:
                raise SourceError(
                    f"Dữ liệu dựng lại từ CSDL cho {doc.spec.ma} khác tệp gốc; đã rollback"
                )
    for table in RULE_TABLES:
        print(f"{table}: {counts[table]}")
    return counts
