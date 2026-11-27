"""Tra cứu thuốc chỉ đọc và tra tương tác thủ công (hợp đồng API v1.8).

Đọc từ PostgreSQL (`KB_SOURCE=db`) qua `read_pool` hoặc từ tệp SQLite/JSON cục bộ
(`KB_SOURCE=file`). Không ghi DB, không ghi kết quả thẩm định.
"""

import json
import logging
import re
import sqlite3
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

import psycopg
from starlette.exceptions import HTTPException

from app import container as container_mod
from app.api import schemas as s
from app.config.settings import get_secret, load_kb_source, load_settings
from app.core.errors import ConfigError
from app.db.bang_luat_store import RULE_DOCUMENTS, load_rule_data, register_cache_clear
from app.db.read_pool import read_pool
from app.db.reader import DatabaseReadError
from app.db.timezone import VN_TZ
from app.domain.models import CaBenh, ChiTietYLenh, DotDieuTri, NguoiBenh, TinhTrangDiUng, YLenh
from app.kb.names import normalize_key
from app.kb.resolver.matching import product_key, without_strength
from app.kb.suggest import DrugSuggestIndex, SuggestTuple
from app.retrieval.corpus import load_corpus
from app.rules.interaction import check_with_matrix

_LOGGER = logging.getLogger(__name__)
_ROOT = Path(__file__).resolve().parents[2]
_TTL_SECONDS = 600.0
_MAX_PAGE_SIZE = 100
_MAX_SUGGEST = 15
_MAX_PRODUCTS = 50
_MAX_MAJOR = 20
_EMPTY_BRACKETS_RE = re.compile(r"\(\s*[+/;,.-]*\s*\)|\[\s*[+/;,.-]*\s*\]")
_DANGLING_SEP_RE = re.compile(r"(?:\s*[+/;,.-]+\s*$|\s*[+/;,.-]+\s+(?=[+/;,.-]))")
_SPACE_RE = re.compile(r"\s+")
_MIN_NAMES, _MAX_NAMES, _MAX_NAME_LENGTH = 2, 12, 200
_CHUNKS_PATH = _ROOT / "data/kb_curated/chunks.jsonl"
_FDA_SECTIONS = (
    "chi_dinh",
    "chong_chi_dinh",
    "lieu",
    "lieu_than",
    "lieu_gan",
    "canh_bao",
    "tuong_tac",
    "thai_ky_cho_bu",
    "nhi_cao_tuoi",
    "tac_dung_phu",
    "qua_lieu",
    "duoc_ly",
    "khac",
)
# Bảng luật -> (nhóm hiển thị, các danh sách có hàng theo hoạt chất).
_RULE_SECTIONS: dict[str, tuple[str, tuple[str, ...]]] = {
    "quy_tac_lieu_than": ("lieu_than", ("quy_tac", "quy_tac_cho_duyet", "khong_co_nguong")),
    "quy_tac_gan": ("lieu_gan", ("quy_tac",)),
    "nguong_xet_nghiem": ("nguong_xet_nghiem", ("quy_tac",)),
    "thuoc_benh_icd": ("thuoc_benh", ("cap_thuoc_benh",)),
    "duong_dung_hop_le": ("duong_dung", ("nhom",)),
    "lieu_toi_da": ("lieu_toi_da", ("nhom", "khong_ghi_toi_da")),
    "doc_tinh": (
        "doc_tinh",
        ("doc_than", "keo_dai_qt", "khoang_dieu_tri_hep", "doc_gan_livertox", "khong_co_nguon"),
    ),
    "khang_sinh_quan_ly": ("khang_sinh_quan_ly", ("khang_sinh",)),
    "di_ung_cheo": ("di_ung_cheo", ("nhom",)),
}
_DB_TABLES = {
    "hc": "tri_thuc.tra_cuu_hoat_chat",
    "dn": "tri_thuc.tra_cuu_dong_nghia",
    "th": "tri_thuc.tra_cuu_thuoc",
    "tp": "tri_thuc.tra_cuu_thuoc_thanh_phan",
    "cap": "tri_thuc.ddinter_cap",
    "ddt": "tri_thuc.ddinter_thuoc",
    "dt": "tri_thuc.doan_trich",
    "tl": "tri_thuc.tai_lieu",
}
_FILE_TABLES = {
    "hc": "hoat_chat",
    "dn": "dong_nghia",
    "th": "thuoc",
    "tp": "thuoc_thanh_phan",
    "cap": "cap",
    "ddt": "thuoc",
}
_SOURCE_TRA_CUU = "tri_thuc.tra_cuu_hoat_chat"
_SOURCE_PRODUCTS = "tri_thuc.tra_cuu_thuoc + tra_cuu_thuoc_thanh_phan (Cục Quản lý Dược)"
_SOURCE_FDA = "tri_thuc.doan_trich (nhãn FDA/DailyMed, nguyên văn)"
_SOURCE_DDINTER = "DDInter 2.0 (sàng lọc, CC BY-NC-SA 4.0)"
_DDINTER_NOTE = (
    "Sàng lọc, cần đối chiếu nhãn. Số cặp là số cặp có trong DDInter, không phải đã duyệt."
)


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status, detail={"ma": code, "thong_bao": message})


class _TtlCache:
    """Bộ đệm theo khoá, hết hạn sau `_TTL_SECONDS`, an toàn luồng."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._items: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        with self._lock:
            hit = self._items.get(key)
            if hit is not None and time.monotonic() - hit[0] < _TTL_SECONDS:
                return hit[1]
            return None

    def put(self, key: str, value: Any) -> Any:
        with self._lock:
            self._items[key] = (time.monotonic(), value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


_CACHE = _TtlCache()
_POOL = ThreadPoolExecutor(max_workers=3, thread_name_prefix="tra-cuu")
register_cache_clear(_CACHE.clear)


def clear_caches() -> None:
    """Xoá bộ đệm tra cứu, kể cả chỉ mục gợi ý (dùng khi kiểm thử hoặc đổi nguồn)."""
    _CACHE.clear()
    _clear_suggest_index()


def _db_url() -> str:
    try:
        return get_secret("DATABASE_URL").strip()
    except ConfigError:
        raise _error(503, "loi_he_thong", "Chưa cấu hình kết nối cơ sở dữ liệu.") from None


def _paths() -> tuple[Path, Path]:
    app = load_settings().app
    return _ROOT / app.tra_cuu, _ROOT / app.tuong_tac


def _use_db(path: Path) -> bool:
    """Cùng quy tắc chọn nguồn với container: db, file hoặc tự chọn theo tệp."""
    source = load_kb_source()
    if source == "db":
        return True
    if source == "file":
        return False
    return not path.is_file()


def _sqlite_rows(path: Path, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    try:
        with closing(sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)) as db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute(sql, params)]
    except sqlite3.Error:
        raise DatabaseReadError("Không đọc được chỉ mục tra cứu cục bộ.") from None


def _pg_rows(sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    try:
        with read_pool.connection(_db_url()) as conn:
            return list(conn.execute(sql, params).fetchall())
    except psycopg.Error:
        raise DatabaseReadError("Không đọc được dữ liệu tra cứu từ cơ sở dữ liệu.") from None


def _query(kind: str, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    """Chạy truy vấn đọc trên nguồn đang dùng; `sql` dùng `{hc}`, `{cap}`... và `%s`."""
    tra_cuu, tuong_tac = _paths()
    path = tuong_tac if kind == "ddinter" else tra_cuu
    if _use_db(path):
        return _pg_rows(sql.format(**_DB_TABLES), params)
    return _sqlite_rows(path, sql.format(**_FILE_TABLES).replace("%s", "?"), params)


def _atc(raw: Any) -> list[str]:
    value = json.loads(raw) if isinstance(raw, str) else raw
    return [str(item) for item in value or []]


# ---------------------------------------------------------------- danh mục hoạt chất


def _catalog() -> dict[str, dict[str, Any]]:
    """Mọi hoạt chất kèm số chế phẩm (một truy vấn, giữ trong bộ đệm)."""
    cached = _CACHE.get("catalog")
    if cached is not None:
        return cached
    rows = _query(
        "tra_cuu",
        "SELECT h.hoat_chat_id, h.ten_inn, h.ten_viet, h.rxcui, h.ma_atc_json, h.loai, "
        "h.ddinter_id, COUNT(p.thuoc_id) AS so_che_pham "
        "FROM {hc} h LEFT JOIN {tp} p ON p.hoat_chat_id = h.hoat_chat_id "
        "GROUP BY h.hoat_chat_id, h.ten_inn, h.ten_viet, h.rxcui, h.ma_atc_json, h.loai, "
        "h.ddinter_id",
    )
    return _CACHE.put("catalog", {row["hoat_chat_id"]: row for row in rows})


def _fda_ids() -> set[str]:
    """Tập hoạt chất có ít nhất một đoạn nhãn FDA."""
    cached = _CACHE.get("fda_ids")
    if cached is not None:
        return cached
    tra_cuu, _ = _paths()
    if _use_db(tra_cuu):
        rows = _pg_rows(
            "SELECT DISTINCT jsonb_array_elements_text(hoat_chat_ids) AS hoat_chat_id "
            "FROM tri_thuc.doan_trich",
            (),
        )
        found = {row["hoat_chat_id"] for row in rows}
    else:
        found = {item for chunk in _corpus() for item in chunk.hoat_chat_ids}
    return _CACHE.put("fda_ids", found)


def _corpus() -> list[Any]:
    """Kho đoạn từ tệp JSONL (chế độ tệp)."""
    cached = _CACHE.get("corpus")
    if cached is not None:
        return cached
    try:
        chunks = load_corpus(_CHUNKS_PATH)
    except Exception:
        _LOGGER.warning("Không đọc được kho đoạn cục bộ cho tra cứu thuốc")
        chunks = []
    return _CACHE.put("corpus", chunks)


# ---------------------------------------------------------------- quy tắc theo hoạt chất


def _row_ids(row: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    one = row.get("hoat_chat_id")
    if isinstance(one, str):
        ids.append(one)
    many = row.get("hoat_chat_ids")
    if isinstance(many, list):
        ids.extend(str(item) for item in many)
    if not ids and isinstance(row.get("ten_quoc_te"), str):
        ids.append(row["ten_quoc_te"].strip().lower())
    return ids


def _raw_document(ma: str) -> dict[str, Any] | None:
    """Tài liệu bảng luật nguyên dạng (cùng đường nạp với các luật; DB đã được nạp sẵn)."""
    spec = next((item for item in RULE_DOCUMENTS if item.ma == ma), None)
    if spec is None:
        return None
    return load_rule_data(ma, _ROOT / spec.tep, lambda raw: raw, logger=_LOGGER, fmt=spec.dinh_dang)


def _rule_index() -> tuple[dict[str, list[s.QuyTacDong]], list[dict[str, Any]], dict[str, Any]]:
    """Hàng bảng luật gom theo hoạt chất, cộng nhóm trùng điều trị và ATC bổ sung."""
    cached = _CACHE.get("rules")
    if cached is not None:
        return cached
    by_id: dict[str, list[s.QuyTacDong]] = {}
    for ma, (nhom, keys) in _RULE_SECTIONS.items():
        doc = _raw_document(ma)
        if doc is None:
            continue
        for key in keys:
            for row in doc.get(key) or []:
                if not isinstance(row, dict):
                    continue
                trang_thai = row.get("trang_thai", doc.get("trang_thai"))
                item = s.QuyTacDong(
                    nhom=nhom,
                    bang_luat=ma,
                    phan=key,
                    phien_ban=_text(doc.get("phien_ban")),
                    trang_thai=_text(trang_thai),
                    du_lieu=row,
                )
                for identifier in dict.fromkeys(_row_ids(row)):
                    by_id.setdefault(identifier, []).append(item)
    groups_doc = _raw_document("nhom_dieu_tri_trung") or {}
    atc_doc = _raw_document("atc_bo_sung") or {}
    value = (by_id, list(groups_doc.get("nhom") or []), dict(atc_doc.get("ma_atc") or {}))
    value[2]["__trang_thai_nhom__"] = groups_doc.get("trang_thai")
    return _CACHE.put("rules", value)


def _text(value: Any) -> str | None:
    return None if value is None else str(value)


def _group_rules(identifier: str, atc_codes: list[str]) -> list[s.QuyTacDong]:
    """Nhóm trùng điều trị khớp theo tiền tố ATC (kể cả ATC bổ sung)."""
    _, groups, supplement = _rule_index()
    codes = [*atc_codes, *_as_str_list(supplement.get(identifier))]
    found = []
    for group in groups:
        include = tuple(_as_str_list(group.get("tien_to_atc")))
        exclude = tuple(_as_str_list(group.get("tien_to_atc_loai_tru")))
        if any(
            code.startswith(include) and not (exclude and code.startswith(exclude))
            for code in codes
        ):
            found.append(
                s.QuyTacDong(
                    nhom="nhom_trung_dieu_tri",
                    bang_luat="nhom_dieu_tri_trung",
                    phan="nhom",
                    phien_ban=None,
                    trang_thai=_text(supplement.get("__trang_thai_nhom__")),
                    du_lieu=group,
                )
            )
    return found


def _as_str_list(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _rules_for(identifier: str, atc_codes: list[str]) -> list[s.QuyTacDong]:
    by_id, _, _ = _rule_index()
    return [*by_id.get(identifier, []), *_group_rules(identifier, atc_codes)]


# ---------------------------------------------------------------- tìm và chi tiết thuốc


def _summary(row: dict[str, Any], fda: set[str]) -> s.KetQuaThuoc:
    codes = _atc(row["ma_atc_json"])
    return s.KetQuaThuoc(
        hoat_chat_id=row["hoat_chat_id"],
        ten_inn=row["ten_inn"],
        ten_viet=row["ten_viet"],
        ma_atc=codes,
        so_che_pham=int(row["so_che_pham"]),
        co_nhan_fda=row["hoat_chat_id"] in fda,
        so_quy_tac=len(_rules_for(row["hoat_chat_id"], codes)),
    )


_SEARCH_SQL = (
    "SELECT hoat_chat_id, MIN(hang) AS hang FROM ("
    "SELECT hoat_chat_id, CASE WHEN lower(ten_inn) = %s OR hoat_chat_id = %s THEN 0 "
    "WHEN lower(ten_inn) LIKE %s THEN 1 ELSE 2 END AS hang FROM {hc} "
    "WHERE lower(ten_inn) LIKE %s OR hoat_chat_id LIKE %s "
    "UNION ALL SELECT hoat_chat_id, CASE WHEN khoa_chuan_hoa = %s THEN 1 "
    "WHEN khoa_chuan_hoa LIKE %s THEN 2 ELSE 3 END FROM {dn} WHERE khoa_chuan_hoa LIKE %s "
    "UNION ALL SELECT p.hoat_chat_id, 4 FROM {th} t JOIN {tp} p ON p.thuoc_id = t.thuoc_id "
    "WHERE t.khoa_ten_thuoc LIKE %s"
    ") m GROUP BY hoat_chat_id ORDER BY MIN(hang), hoat_chat_id"
)


def _strip_product_strength(name: str) -> str:
    """Bỏ hàm lượng khỏi tên biệt dược để làm nhãn hiển thị sạch."""
    cleaned = without_strength(name)
    while True:
        next_val = _EMPTY_BRACKETS_RE.sub(" ", cleaned)
        if next_val == cleaned:
            break
        cleaned = next_val
    cleaned = _SPACE_RE.sub(" ", cleaned).strip()
    cleaned = _DANGLING_SEP_RE.sub("", cleaned).strip(" +/;,.-")
    cleaned = _SPACE_RE.sub(" ", cleaned).strip()
    return cleaned or name.strip()


_SUGGEST_LOCK = Lock()
_SUGGEST_INDEX: DrugSuggestIndex | None = None


def _clear_suggest_index() -> None:
    global _SUGGEST_INDEX
    with _SUGGEST_LOCK:
        _SUGGEST_INDEX = None


register_cache_clear(_clear_suggest_index)


def _suggest_index() -> DrugSuggestIndex:
    """Chỉ mục gợi ý tên thuốc, giữ suốt vòng đời tiến trình.

    Dựng mất vài giây trên DB nên không đặt hết hạn theo `_TTL_SECONDS` (tránh để một người
    dùng chờ mỗi 10 phút); được làm nóng lúc khởi động và xoá khi gọi `clear_caches()`.
    """
    global _SUGGEST_INDEX
    if _SUGGEST_INDEX is not None:
        return _SUGGEST_INDEX
    with _SUGGEST_LOCK:
        if _SUGGEST_INDEX is None:
            _SUGGEST_INDEX = _build_suggest_index()
        return _SUGGEST_INDEX


def _build_suggest_index() -> DrugSuggestIndex:
    """Dựng chỉ mục gợi ý tên thuốc từ bảng tra cứu (DB hoặc tệp)."""
    catalog = _catalog()
    inn_by_id = {hid: str(row["ten_inn"]) for hid, row in catalog.items()}
    viet_by_id = {
        (hid, normalize_key(str(row["ten_viet"]))): str(row["ten_viet"]).strip()
        for hid, row in catalog.items()
        if row.get("ten_viet")
    }
    entries: list[SuggestTuple] = []
    non_brand_keys: dict[frozenset[str], set[str]] = defaultdict(set)

    for hid, row in catalog.items():
        ten_inn = str(row["ten_inn"])
        key = normalize_key(ten_inn)
        if key:
            entries.append((key, ten_inn, "hoat_chat", [hid], ten_inn))
            non_brand_keys[frozenset({hid})].add(key)

    synonym_rows = _query("tra_cuu", "SELECT DISTINCT khoa_chuan_hoa, hoat_chat_id FROM {dn}")
    syn_to_ids: dict[str, set[str]] = defaultdict(set)
    for row in synonym_rows:
        khoa = str(row["khoa_chuan_hoa"] or "").strip()
        hid = str(row["hoat_chat_id"])
        if khoa and hid in catalog:
            syn_to_ids[khoa].add(hid)
    for khoa, ids_set in syn_to_ids.items():
        if len(ids_set) != 1:
            continue
        hid = next(iter(ids_set))
        display = viet_by_id.get((hid, khoa), khoa)
        gia_tri_gui = display if product_key(display) == khoa else khoa
        entries.append((khoa, display, "dong_nghia", [hid], gia_tri_gui))
        non_brand_keys[frozenset({hid})].add(khoa)

    product_rows = _query(
        "tra_cuu",
        "SELECT t.thuoc_id, t.khoa_ten_thuoc, t.ten_thuoc, p.hoat_chat_id "
        "FROM {th} t JOIN {tp} p ON p.thuoc_id = t.thuoc_id",
    )
    product_meta: dict[str, tuple[str, str]] = {}
    product_ings: dict[str, set[str]] = defaultdict(set)
    for row in product_rows:
        tid = str(row["thuoc_id"])
        khoa = str(row["khoa_ten_thuoc"] or "").strip()
        ten = str(row["ten_thuoc"] or "").strip()
        hid = str(row["hoat_chat_id"])
        if not khoa or not ten or hid not in catalog:
            continue
        product_meta.setdefault(tid, (khoa, ten))
        product_ings[tid].add(hid)

    by_key_names: dict[str, Counter[str]] = defaultdict(Counter)
    by_key_formulas: dict[str, set[frozenset[str]]] = defaultdict(set)
    for tid, (khoa, ten) in product_meta.items():
        ings = frozenset(product_ings[tid])
        if not ings:
            continue
        by_key_names[khoa][ten] += 1
        by_key_formulas[khoa].add(ings)

    for khoa, formulas in by_key_formulas.items():
        if len(formulas) != 1:
            continue
        ings = next(iter(formulas))
        if khoa in non_brand_keys.get(ings, ()):
            continue
        counts = by_key_names[khoa]
        top_ten = min(counts.items(), key=lambda item: (-item[1], len(item[0]), item[0]))[0]
        nhan = _strip_product_strength(top_ten)
        gia_tri_gui = nhan if product_key(nhan) == khoa else top_ten
        entries.append((khoa, nhan, "biet_duoc", sorted(ings), gia_tri_gui))

    return DrugSuggestIndex(entries, inn_by_id=inn_by_id)


def warm_suggest_index() -> None:
    """Dựng sẵn chỉ mục gợi ý (gọi từ luồng làm nóng lúc khởi động API)."""
    _suggest_index()


def suggest_drugs(q: str, limit: int = 8) -> s.KetQuaGoiYThuoc:
    """Gợi ý tên thuốc khi gõ; không ghi chuỗi tìm kiếm vào nhật ký."""
    bounded = max(1, min(_MAX_SUGGEST, limit))
    result = _suggest_index().goi_y(q, bounded)
    return s.KetQuaGoiYThuoc(
        ket_qua=[
            s.GoiYThuoc(
                nhan=item.nhan,
                loai=item.loai,
                hoat_chat_ids=list(item.hoat_chat_ids),
                ten_hoat_chat=list(item.ten_hoat_chat),
                gia_tri_gui=item.gia_tri_gui,
                khop=item.khop,
            )
            for item in result.ket_qua
        ],
        goi_y_sua=result.goi_y_sua,
    )


def search_drugs(q: str | None, page: int, page_size: int) -> s.DanhSachThuoc:
    """Tìm hoạt chất theo tên thuốc, hoạt chất hoặc đồng nghĩa; không dấu, không phân biệt hoa."""
    page = max(1, page)
    page_size = max(1, min(_MAX_PAGE_SIZE, page_size))
    catalog = _catalog()
    fda = _fda_ids()
    key = normalize_key(q or "")
    goi_y_sua: str | None = None
    if not key:
        ordered = sorted(
            catalog.values(),
            key=lambda row: (
                row["hoat_chat_id"] not in fda,
                -len(_rules_for(row["hoat_chat_id"], _atc(row["ma_atc_json"]))),
                row["ten_inn"].lower(),
            ),
        )
        # Chỉ liệt kê hoạt chất có dữ liệu khi không tìm; hoạt chất trống tìm được bằng `q`.
        ordered = [
            row
            for row in ordered
            if row["hoat_chat_id"] in fda
            or _rules_for(row["hoat_chat_id"], _atc(row["ma_atc_json"]))
        ]
        ids = [row["hoat_chat_id"] for row in ordered]
    else:
        like = f"%{key}%"
        rows = _query(
            "tra_cuu",
            _SEARCH_SQL,
            (key, key, f"{key}%", like, like, key, f"{key}%", like, like),
        )
        ids = [row["hoat_chat_id"] for row in rows if row["hoat_chat_id"] in catalog]
        if not ids:
            suggested = _suggest_index().goi_y(q or "", 30)
            ids = list(
                dict.fromkeys(
                    hid
                    for item in suggested.ket_qua
                    for hid in item.hoat_chat_ids
                    if hid in catalog
                )
            )
            goi_y_sua = suggested.goi_y_sua
    start = (page - 1) * page_size
    return s.DanhSachThuoc(
        tong=len(ids),
        trang=page,
        so_dong=page_size,
        ket_qua=[_summary(catalog[item], fda) for item in ids[start : start + page_size]],
        goi_y_sua=goi_y_sua,
    )


def _products(identifier: str, total: int, *, limit: int = _MAX_PRODUCTS) -> s.DanhSachChePham:
    bounded = max(1, min(_MAX_PRODUCTS, limit))
    rows = _query(
        "tra_cuu",
        "SELECT t.ten_thuoc, t.so_dang_ky, t.dang_bao_che, p.ham_luong, p.don_vi "
        "FROM {tp} p JOIN {th} t ON t.thuoc_id = p.thuoc_id WHERE p.hoat_chat_id = %s "
        "ORDER BY t.ten_thuoc, t.thuoc_id LIMIT %s",
        (identifier, bounded),
    )
    return s.DanhSachChePham(
        nguon=_SOURCE_PRODUCTS,
        trang_thai=None,
        tong=total,
        danh_sach=[
            s.ChePham(
                ten_thuoc=row["ten_thuoc"],
                so_dang_ky=row["so_dang_ky"],
                dang_bao_che=row["dang_bao_che"],
                ham_luong=row["ham_luong"],
                don_vi=row["don_vi"],
            )
            for row in rows
        ],
    )


def _label_rows(identifier: str) -> list[dict[str, Any]]:
    tra_cuu, _ = _paths()
    if _use_db(tra_cuu):
        return _pg_rows(
            "SELECT d.doan_trich_id, d.muc, d.duong_dan_muc, d.noi_dung_goc, d.url_goc, "
            "d.tai_lieu_id, l.set_id, d.nguon, d.phien_ban_nguon, d.tang_tin_cay "
            "FROM tri_thuc.doan_trich d LEFT JOIN tri_thuc.tai_lieu l "
            "ON l.tai_lieu_id = d.tai_lieu_id WHERE d.hoat_chat_ids ? %s "
            "ORDER BY d.doan_trich_id",
            (identifier,),
        )
    return [
        {**chunk.model_dump(), "set_id": None}
        for chunk in sorted(_corpus(), key=lambda item: item.doan_trich_id)
        if identifier in chunk.hoat_chat_ids
    ]


def _label(identifier: str) -> s.NhanFda:
    """Đoạn nhãn nguyên văn nhóm theo mục; đủ các mục, mục trống để rỗng."""
    rows = _label_rows(identifier)
    groups: dict[str, list[s.DoanNhanFda]] = {name: [] for name in _FDA_SECTIONS}
    for row in rows:
        groups.setdefault(row["muc"], []).append(
            s.DoanNhanFda(
                doan_trich_id=row["doan_trich_id"],
                duong_dan_muc=row["duong_dan_muc"],
                noi_dung_goc=row["noi_dung_goc"],
                url_goc=row["url_goc"] or None,
                tai_lieu_id=row["tai_lieu_id"],
                set_id=row["set_id"],
                nguon=row["nguon"],
                phien_ban_nguon=row["phien_ban_nguon"],
                tang_tin_cay=int(row["tang_tin_cay"]),
            )
        )
    return s.NhanFda(
        nguon=_SOURCE_FDA,
        trang_thai=None,
        tong_doan=len(rows),
        nhom=[s.NhomNhanFda(muc=name, doan=items) for name, items in groups.items()],
    )


def _interaction_summary(row: dict[str, Any]) -> s.TuongTacTomTat:
    """Số cặp theo mức và tối đa 20 cặp Major, truy vấn có LIMIT, không nạp cả bảng."""
    ddinter_id = row["ddinter_id"]
    if not ddinter_id:
        return s.TuongTacTomTat(
            nguon=_SOURCE_DDINTER,
            trang_thai=None,
            ddinter_id=None,
            co_du_lieu=False,
            so_cap=s.SoCapTuongTac(major=0, moderate=0, minor=0, unknown=0),
            major=[],
            ghi_chu="Hoạt chất chưa có mã DDInter; không có dữ liệu tương tác để tóm tắt.",
        )
    counts = {
        item["muc_do"]: int(item["n"])
        for item in _query(
            "ddinter",
            "SELECT muc_do, COUNT(*) AS n FROM {cap} "
            "WHERE ddinter_id_a = %s OR ddinter_id_b = %s GROUP BY muc_do",
            (ddinter_id, ddinter_id),
        )
    }
    major = _query(
        "ddinter",
        "SELECT c.ddinter_id_a, c.ddinter_id_b, c.co_che_json, d.ten FROM {cap} c "
        "JOIN {ddt} d ON d.ddinter_id = CASE WHEN c.ddinter_id_a = %s "
        "THEN c.ddinter_id_b ELSE c.ddinter_id_a END "
        "WHERE (c.ddinter_id_a = %s OR c.ddinter_id_b = %s) AND c.muc_do = 'Major' "
        "ORDER BY d.ten LIMIT %s",
        (ddinter_id, ddinter_id, ddinter_id, _MAX_MAJOR),
    )
    return s.TuongTacTomTat(
        nguon=_SOURCE_DDINTER,
        trang_thai=None,
        ddinter_id=ddinter_id,
        co_du_lieu=bool(counts),
        so_cap=s.SoCapTuongTac(
            major=counts.get("Major", 0),
            moderate=counts.get("Moderate", 0),
            minor=counts.get("Minor", 0),
            unknown=counts.get("Unknown", 0),
        ),
        major=[
            s.CapMajor(
                ddinter_id=(
                    item["ddinter_id_b"]
                    if item["ddinter_id_a"] == ddinter_id
                    else item["ddinter_id_a"]
                ),
                ten_thuoc_khac=item["ten"],
                co_che=_atc(item["co_che_json"]),
            )
            for item in major
        ],
        ghi_chu=_DDINTER_NOTE,
    )


def _build_identity(row: dict[str, Any], codes: list[str]) -> s.DinhDanhThuoc:
    return s.DinhDanhThuoc(
        hoat_chat_id=row["hoat_chat_id"],
        ten_inn=row["ten_inn"],
        ten_viet=row["ten_viet"],
        rxcui=row["rxcui"],
        ma_atc=codes,
        ddinter_id=row["ddinter_id"],
        loai=row["loai"],
        nguon=_SOURCE_TRA_CUU,
        trang_thai=None,
    )


def drug_identity(identifier: str) -> s.DinhDanhThuoc | None:
    """Định danh một hoạt chất từ danh mục tra cứu; trả None nếu không có."""
    row = _catalog().get(identifier)
    if row is None:
        return None
    return _build_identity(row, _atc(row["ma_atc_json"]))


def drug_rules(identifier: str, atc_codes: list[str] | None = None) -> list[s.QuyTacDong]:
    """Mọi dòng bảng luật của một hoạt chất (không truy vấn nhãn FDA hay chế phẩm)."""
    if atc_codes is None:
        row = _catalog().get(identifier)
        if row is None:
            return []
        codes = _atc(row["ma_atc_json"])
    else:
        codes = atc_codes
    return _rules_for(identifier, codes)


def drug_products(identifier: str, limit: int = _MAX_PRODUCTS) -> s.DanhSachChePham | None:
    """Danh sách chế phẩm Cục QLD giới hạn theo limit kèm tổng số; None nếu không có."""
    row = _catalog().get(identifier)
    if row is None:
        return None
    return _products(identifier, int(row["so_che_pham"]), limit=limit)


def drug_detail(identifier: str) -> s.ChiTietThuoc:
    """Toàn bộ thông tin một hoạt chất; mỗi phần ghi nguồn, không suy diễn."""
    row = _catalog().get(identifier)
    if row is None:
        raise HTTPException(404, "Không tìm thấy hoạt chất.")
    codes = _atc(row["ma_atc_json"])
    # Ba nhóm truy vấn độc lập chạy song song trên tối đa ba kết nối của read_pool.
    products = _POOL.submit(_products, identifier, int(row["so_che_pham"]))
    label = _POOL.submit(_label, identifier)
    summary = _POOL.submit(_interaction_summary, row)
    return s.ChiTietThuoc(
        dinh_danh=_build_identity(row, codes),
        che_pham=products.result(),
        nhan_fda=label.result(),
        quy_tac=_rules_for(identifier, codes),
        tuong_tac_tom_tat=summary.result(),
    )


# ---------------------------------------------------------------- tra tương tác thủ công


def _temporary_case(ids: list[str], names: list[str]) -> CaBenh:
    """CaBenh chỉ nằm trong bộ nhớ: mỗi tên là một dòng y lệnh chờ duyệt."""
    now = datetime.now(VN_TZ)
    return CaBenh(
        ca_id="TRA-TUONG-TAC",
        mo_ta_ngan="Tra tương tác thủ công (tạm, không lưu)",
        nguoi_benh=NguoiBenh(nguoi_benh_id="TRA-TUONG-TAC"),
        tinh_trang_di_ung=TinhTrangDiUng(trang_thai="chua_co_thong_tin"),
        dot_dieu_tri=DotDieuTri(
            dot_dieu_tri_id="TRA-TUONG-TAC",
            khoa_dieu_tri="Tra cứu",
            loai_dieu_tri="ngoai_tru",
            thoi_diem_bat_dau=now,
        ),
        y_lenh_cho_duyet=YLenh(
            y_lenh_id="TRA-TUONG-TAC",
            khoa_ke_don="Tra cứu",
            luong_duyet="truc_tiep",
            thoi_diem_ke=now,
            chi_tiet=[
                ChiTietYLenh(
                    chi_tiet_y_lenh_id=line_id,
                    ten_tu_do=name,
                    bat_dau=now,
                    trang_thai_dong="pending",
                )
                for line_id, name in zip(ids, names, strict=True)
            ],
        ),
    )


def lookup_interactions(names: list[str]) -> s.KetQuaTraTuongTac:
    """Dựng CaBenh tạm rồi chạy đúng luật yếu tố 4 như trang ca; không ghi gì."""
    cleaned = [item.strip() for item in names]
    if not _MIN_NAMES <= len(cleaned) <= _MAX_NAMES:
        message = f"Cần nhập từ {_MIN_NAMES} đến {_MAX_NAMES} thuốc."
        raise _error(422, "du_lieu_khong_hop_le", message)
    if any(not item or len(item) > _MAX_NAME_LENGTH for item in cleaned):
        raise _error(422, "du_lieu_khong_hop_le", "Tên thuốc không được để trống hoặc quá dài.")
    keys = [normalize_key(item) for item in cleaned]
    if any(not key for key in keys):
        raise _error(422, "du_lieu_khong_hop_le", "Tên thuốc phải có chữ hoặc số.")
    if len(set(keys)) != len(keys):
        raise _error(422, "du_lieu_khong_hop_le", "Danh sách có tên thuốc bị nhập trùng.")
    context = container_mod.get_rule_context()
    if context.resolver is None or context.interactions is None:
        raise _error(503, "loi_he_thong", "Chưa nạp được chỉ mục tra cứu hoặc dữ liệu DDInter.")
    ids = [f"T{index}" for index in range(1, len(cleaned) + 1)]
    findings, matrix = check_with_matrix(
        _temporary_case(ids, cleaned), context.resolver, context.interactions
    )
    if matrix is None:
        raise _error(503, "loi_he_thong", "Không chạy được luật tương tác thuốc.")
    by_id = {row.chi_tiet_y_lenh_id: row for row in matrix.thuoc}
    detail = [
        s.CapChiTiet(
            a=min(item.chi_tiet_y_lenh_id),
            b=max(item.chi_tiet_y_lenh_id),
            muc=item.ma_luat,
            mo_ta=item.mo_ta,
            can_cu=[evidence.mo_ta for evidence in item.can_cu],
            thong_tin_con_thieu=list(item.thong_tin_con_thieu),
        )
        for item in findings
        if item.ma_luat in {"tuong_tac_thuoc", "tuong_tac_thieu_du_lieu"}
        and len(item.chi_tiet_y_lenh_id) == 2
    ]
    return s.KetQuaTraTuongTac(
        ma_tran=matrix,
        phan_giai=[
            s.PhanGiaiTen(
                ten_nhap=name,
                chi_tiet_y_lenh_id=line_id,
                trang_thai=by_id[line_id].phan_giai,
                hoat_chat=list(by_id[line_id].hoat_chat),
                ly_do=by_id[line_id].ly_do,
            )
            for line_id, name in zip(ids, cleaned, strict=True)
        ],
        chi_tiet=detail,
    )
