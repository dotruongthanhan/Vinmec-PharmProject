"""Phân giải dòng thuốc bằng chỉ mục SQLite nạp vào bộ nhớ."""

import json
import re
import sqlite3
from collections import defaultdict
from collections.abc import Iterable, Mapping
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import CaBenh, ChiTietYLenh, HoatChat, Thuoc
from app.kb.names import normalize_key
from app.kb.resolver.matching import (
    CaseMatch,
    IngredientNames,
    combination_parts,
    product_key,
    salt_key,
)

NguonKhop = Literal["danh_muc_ca", "ten_thuoc_dav", "dong_nghia", "tach_phoi_hop"]
_EXCLUDED_KINDS = {"dich_truyen_dien_giai", "duoc_lieu"}
_MULTI_STRENGTH_RE = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:mg|mcg|g|ui|iu)?\s*/\s*"
    r"\d+(?:[.,]\d+)?\s*(?:$|mg\b|mcg\b|g\b|ui\b|iu\b)",
    re.IGNORECASE,
)


class ThanhPhanPhanGiai(BaseModel):
    """Hoạt chất trên trục và hàm lượng đã xác định."""

    model_config = ConfigDict(extra="forbid")

    hoat_chat_id: str
    ma_ca: str | None = None
    ten_inn: str
    ten_viet: str | None
    ma_atc: list[str]
    ddinter_id: str | None
    loai: str
    ham_luong: float | None = None
    don_vi: str | None = None


class KetQuaPhanGiai(BaseModel):
    """Kết quả tra một dòng hoặc một tên thuốc."""

    model_config = ConfigDict(extra="forbid")

    trang_thai: Literal["da_phan_giai", "mot_phan", "khong_nhan_dien", "khong_ap_dung"]
    thanh_phan: list[ThanhPhanPhanGiai] = Field(default_factory=list)
    nguon_khop: NguonKhop | None = None
    ly_do: str | None = None
    canh_bao: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class AxisIngredient:
    ten_inn: str
    ten_viet: str | None
    ma_atc: tuple[str, ...]
    loai: str
    ddinter_id: str | None


_AXIS_COLUMNS = ("hoat_chat_id", "ten_inn", "ten_viet", "ma_atc_json", "loai", "ddinter_id")
_SYNONYM_COLUMNS = ("khoa_chuan_hoa", "hoat_chat_id", "loai")
_CASE_CODE_COLUMNS = ("ma_ca", "hoat_chat_id")
_PRODUCT_COLUMNS = ("khoa_ten_thuoc", "thuoc_id")
_FORMULA_COLUMNS = ("thuoc_id", "hoat_chat_id", "ham_luong", "don_vi")


def _row_to_tuple(row: Any, columns: tuple[str, ...]) -> tuple[Any, ...]:
    """Chuyển hàng tuple hoặc dict (dict_row) thành tuple đúng thứ tự cột."""
    if isinstance(row, Mapping):
        return tuple(row[col] for col in columns)
    if isinstance(row, sqlite3.Row):
        return tuple(row[col] for col in columns)
    return tuple(row)


def _fetch_rows(cursor: Any) -> Iterable[Any]:
    """Lấy toàn bộ hàng từ con trỏ psycopg hoặc đối tượng giả tương đương."""
    if hasattr(cursor, "fetchall") and callable(cursor.fetchall):
        return cursor.fetchall()
    return cursor


class DrugResolver:
    """Tra cứu thuần trong bộ nhớ sau khi mở chỉ mục một lần."""

    @classmethod
    def _build(
        cls,
        axis_rows: Iterable[Any],
        synonym_rows: Iterable[Any],
        case_code_rows: Iterable[Any],
        product_rows: Iterable[Any],
        formula_rows: Iterable[Any],
    ) -> "DrugResolver":
        """Dựng cấu trúc phân giải trong bộ nhớ từ các luồng hàng nguồn."""
        resolver = cls()
        resolver._axis: dict[str, AxisIngredient] = {}
        for row in axis_rows:
            identifier, inn, viet, atc, kind, ddinter = _row_to_tuple(row, _AXIS_COLUMNS)
            parsed_atc = json.loads(atc) if isinstance(atc, str) else atc
            entry = AxisIngredient(inn, viet, tuple(parsed_atc), kind, ddinter)
            resolver._axis[identifier] = entry

        resolver._names = IngredientNames(
            {identifier: row.ten_inn for identifier, row in resolver._axis.items()},
            (_row_to_tuple(row, _SYNONYM_COLUMNS) for row in synonym_rows),
        )
        resolver._case_codes: dict[str, str] = {
            ma_ca: hoat_chat_id
            for ma_ca, hoat_chat_id in (
                _row_to_tuple(row, _CASE_CODE_COLUMNS) for row in case_code_rows
            )
        }
        resolver._products: dict[str, list[str]] = defaultdict(list)
        for row in product_rows:
            key, identifier = _row_to_tuple(row, _PRODUCT_COLUMNS)
            resolver._products[key].append(identifier)

        resolver._formulas: dict[str, dict[str, tuple[float | None, str | None]]] = defaultdict(
            dict
        )
        for row in formula_rows:
            product, ingredient, amount, unit = _row_to_tuple(row, _FORMULA_COLUMNS)
            resolver._formulas[product][ingredient] = (amount, unit)
        return resolver

    @classmethod
    def from_index(cls, path: Path) -> "DrugResolver":
        """Đọc chỉ mục ở chế độ chỉ đọc và đóng kết nối trước khi trả về."""
        with closing(sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)) as db:
            return cls._build(
                db.execute(
                    "SELECT hoat_chat_id, ten_inn, ten_viet, ma_atc_json, loai, ddinter_id "
                    "FROM hoat_chat"
                ),
                db.execute("SELECT khoa_chuan_hoa, hoat_chat_id, loai FROM dong_nghia"),
                db.execute("SELECT ma_ca, hoat_chat_id FROM chuyen_ma_ca"),
                db.execute(
                    "SELECT khoa_ten_thuoc, thuoc_id FROM thuoc ORDER BY khoa_ten_thuoc, thuoc_id"
                ),
                db.execute(
                    "SELECT thuoc_id, hoat_chat_id, ham_luong, don_vi FROM thuoc_thanh_phan"
                ),
            )

    @classmethod
    def from_db(cls, conn: Any) -> "DrugResolver":
        """Đọc chỉ mục tra cứu từ các bảng tri_thuc.tra_cuu_* trên PostgreSQL."""
        return cls._build(
            _fetch_rows(
                conn.execute(
                    "SELECT hoat_chat_id, ten_inn, ten_viet, ma_atc_json, loai, ddinter_id "
                    "FROM tri_thuc.tra_cuu_hoat_chat"
                )
            ),
            _fetch_rows(
                conn.execute(
                    "SELECT khoa_chuan_hoa, hoat_chat_id, loai FROM tri_thuc.tra_cuu_dong_nghia"
                )
            ),
            _fetch_rows(
                conn.execute("SELECT ma_ca, hoat_chat_id FROM tri_thuc.tra_cuu_chuyen_ma_ca")
            ),
            _fetch_rows(
                conn.execute(
                    "SELECT khoa_ten_thuoc, thuoc_id FROM tri_thuc.tra_cuu_thuoc "
                    "ORDER BY khoa_ten_thuoc, thuoc_id"
                )
            ),
            _fetch_rows(
                conn.execute(
                    "SELECT thuoc_id, hoat_chat_id, ham_luong, don_vi "
                    "FROM tri_thuc.tra_cuu_thuoc_thanh_phan"
                )
            ),
        )

    def _component(
        self,
        identifier: str,
        *,
        ma_ca: str | None = None,
        ham_luong: float | None = None,
        don_vi: str | None = None,
    ) -> ThanhPhanPhanGiai:
        row = self._axis[identifier]
        return ThanhPhanPhanGiai(
            hoat_chat_id=identifier,
            ma_ca=ma_ca,
            ten_inn=row.ten_inn,
            ten_viet=row.ten_viet,
            ma_atc=list(row.ma_atc),
            ddinter_id=row.ddinter_id,
            loai=row.loai,
            ham_luong=ham_luong,
            don_vi=don_vi,
        )

    @staticmethod
    def _result(
        components: list[ThanhPhanPhanGiai],
        source: NguonKhop,
        reasons: list[str],
        warnings: list[str],
    ) -> KetQuaPhanGiai:
        status = "da_phan_giai"
        excluded = [row.hoat_chat_id for row in components if row.loai in _EXCLUDED_KINDS]
        if reasons:
            status = "mot_phan"
        elif components and len(excluded) == len(components):
            status = "khong_ap_dung"
            reasons = ["Thành phần thuộc nhóm dịch truyền, điện giải hoặc dược liệu"]
        elif excluded:
            warnings.append(f"Không áp dụng tra tương tác cho: {', '.join(excluded)}")
        for component in components:
            if not component.ma_atc:
                warnings.append(f"Thiếu ma_atc trên trục cho {component.hoat_chat_id}")
            if component.ddinter_id is None and component.loai not in _EXCLUDED_KINDS:
                warnings.append(f"Thiếu ddinter_id đã xác nhận cho {component.hoat_chat_id}")
        return KetQuaPhanGiai(
            trang_thai=status,
            thanh_phan=components,
            nguon_khop=source,
            ly_do="; ".join(reasons) or None,
            canh_bao=list(dict.fromkeys(warnings)),
        )

    def _match_case_ingredient(self, identifier: str, catalog: dict[str, HoatChat]) -> CaseMatch:
        ingredient = catalog.get(identifier)
        indexed = self._case_codes.get(identifier)
        if ingredient is not None:
            local = self._names.match_case(ingredient)
            if indexed is not None and indexed == local.hoat_chat_id:
                return CaseMatch(indexed, local.cach_khop)
            return local
        if indexed is not None:
            return CaseMatch(indexed)
        if identifier in self._axis and not identifier.startswith("HC-"):
            return CaseMatch(identifier, "ma_truc")
        return CaseMatch(None, ly_do="Thiếu mục tương ứng trong danh_muc_hoat_chat")

    def _resolve_catalog(self, ca: CaBenh, product: Thuoc) -> KetQuaPhanGiai:
        catalog = {row.hoat_chat_id: row for row in ca.danh_muc_hoat_chat}
        components = []
        reasons = []
        warnings = []
        key = product_key(product.ten_thuoc)
        for component in product.thanh_phan:
            case_id = component.hoat_chat_id
            match = self._match_case_ingredient(case_id, catalog)
            identifier = match.hoat_chat_id
            if identifier is None:
                reasons.append(f"{case_id}: {match.ly_do}")
                continue
            if match.cach_khop == "dang_muoi" or (
                len(product.thanh_phan) == 1 and self._names.is_salt(key, identifier)
            ):
                warnings.append(f"dang_muoi: {case_id} → {identifier}")
            components.append(
                self._component(
                    identifier,
                    ma_ca=case_id if case_id.startswith("HC-") else None,
                    ham_luong=component.ham_luong_thanh_phan,
                    don_vi=component.don_vi,
                )
            )
        return self._result(components, "danh_muc_ca", reasons, warnings)

    def resolve_line(self, ca: CaBenh, line: ChiTietYLenh) -> KetQuaPhanGiai:
        """Tra danh mục ca trước, sau đó mới tra tên tự do."""
        if line.thuoc_id:
            for product in ca.danh_muc_thuoc:
                if product.thuoc_id == line.thuoc_id:
                    return self._resolve_catalog(ca, product)
        if not line.ten_tu_do or not line.ten_tu_do.strip():
            return KetQuaPhanGiai(
                trang_thai="khong_nhan_dien",
                ly_do="Thiếu ten_tu_do và không tìm thấy thuoc_id trong danh_muc_thuoc",
            )
        result = self.resolve_name(line.ten_tu_do)
        if not result.thanh_phan:
            if result.nguon_khop is None and line.loai_san_pham in {"dinh_duong", "tpcn"}:
                return KetQuaPhanGiai(
                    trang_thai="khong_ap_dung",
                    ly_do=f"Dòng có loai_san_pham={line.loai_san_pham}",
                )
            if line.loai_san_pham == "khac" and product_key(line.ten_tu_do).startswith(
                ("xet nghiem ", "do duong huyet ")
            ):
                return KetQuaPhanGiai(
                    trang_thai="khong_ap_dung",
                    ly_do="Dòng chỉ định xét nghiệm hoặc theo dõi đường huyết",
                )
        return result

    def _by_product(self, key: str) -> KetQuaPhanGiai | None:
        products = self._products.get(key, [])
        formulas = [
            self._formulas[identifier] for identifier in products if identifier in self._formulas
        ]
        if not formulas:
            return None
        if len({frozenset(formula) for formula in formulas}) > 1:
            return KetQuaPhanGiai(
                trang_thai="khong_nhan_dien",
                nguon_khop="ten_thuoc_dav",
                ly_do="tên ứng với nhiều công thức",
            )
        components = []
        warnings = []
        if len(formulas) < len(products):
            warnings.append("Một số chế phẩm DAV cùng khoá tên thiếu danh sách thành phần")
        for identifier in sorted(formulas[0]):
            values = {formula[identifier] for formula in formulas}
            amount, unit = next(iter(values)) if len(values) == 1 else (None, None)
            if amount is None:
                unit = None
                warnings.append(f"Thiếu hàm lượng thống nhất cho {identifier}")
            if self._names.is_salt(key, identifier):
                warnings.append(f"dang_muoi: {identifier}")
            components.append(self._component(identifier, ham_luong=amount, don_vi=unit))
        return self._result(components, "ten_thuoc_dav", [], warnings)

    def _by_synonym(self, key: str, *, expand: bool = True) -> KetQuaPhanGiai | None:
        candidates = self._names.name_ids(key)
        if not candidates and key != salt_key(key):
            candidates = self._names.name_ids(salt_key(key))
        if not candidates:
            return None
        if len(candidates) > 1:
            return KetQuaPhanGiai(
                trang_thai="khong_nhan_dien",
                nguon_khop="dong_nghia",
                ly_do=f"Tên khớp nhiều hoạt chất: {', '.join(sorted(candidates))}",
            )
        identifier = next(iter(candidates))
        warnings = [f"dang_muoi: {identifier}"] if self._names.is_salt(key, identifier) else []
        parts = combination_parts(self._axis[identifier].ten_inn)
        if len(parts) > 1:
            return self._resolve_parts(parts) if expand else None
        return self._result([self._component(identifier)], "dong_nghia", [], warnings)

    def _canonical_inn_fallback(self, name: str, key: str) -> KetQuaPhanGiai | None:
        """Phân giải theo INN chuẩn khi tên chung khớp nhiều công thức DAV do thiếu phần sau."""
        if _MULTI_STRENGTH_RE.search(name):
            return None
        candidates = [
            identifier
            for identifier, item in self._axis.items()
            if len(combination_parts(item.ten_inn)) == 1
            and key in {normalize_key(item.ten_inn), normalize_key(identifier)}
        ]
        if len(candidates) != 1:
            return None
        return self._result([self._component(candidates[0])], "dong_nghia", [], [])

    def _resolve_single(
        self, raw_text: str, key: str, *, expand: bool = True
    ) -> KetQuaPhanGiai | None:
        """Phân giải một tên đơn theo DAV, INN chuẩn khi đa công thức và đồng nghĩa."""
        product = self._by_product(key)
        if product is not None:
            if product.trang_thai == "khong_nhan_dien":
                fallback = self._canonical_inn_fallback(raw_text, key)
                if fallback is not None:
                    return fallback
            return product
        return self._by_synonym(key, expand=expand)

    def _resolve_exact(self, name: str) -> KetQuaPhanGiai | None:
        key = product_key(name)
        if not key:
            return None
        return self._resolve_single(name, key)

    def _resolve_parts(self, parts: list[str]) -> KetQuaPhanGiai:
        components: dict[str, ThanhPhanPhanGiai] = {}
        reasons = []
        warnings = []
        for part in parts:
            key = product_key(part)
            match = self._resolve_single(part, key, expand=False) if key else None
            if match is None or not match.thanh_phan:
                reason = match.ly_do if match else "không khớp từ điển"
                reasons.append(f"{part.strip() or '(trống)'}: {reason}")
                continue
            warnings.extend(match.canh_bao)
            for component in match.thanh_phan:
                previous = components.get(component.hoat_chat_id)
                if previous is not None:
                    warnings.append(f"Hoạt chất lặp trong tên phối hợp: {component.hoat_chat_id}")
                    component = component.model_copy(update={"ham_luong": None, "don_vi": None})
                components[component.hoat_chat_id] = component
        if not components:
            return KetQuaPhanGiai(
                trang_thai="khong_nhan_dien", nguon_khop="tach_phoi_hop", ly_do="; ".join(reasons)
            )
        return self._result(list(components.values()), "tach_phoi_hop", reasons, warnings)

    def resolve_name(self, ten: str) -> KetQuaPhanGiai:
        """Tra tên DAV, đồng nghĩa và tên phối hợp theo thứ tự."""
        result = self._resolve_exact(ten)
        if result is not None:
            return result
        parts = combination_parts(ten)
        if len(parts) > 1:
            return self._resolve_parts(parts)
        key = product_key(ten)
        if key in self._products:
            return KetQuaPhanGiai(
                trang_thai="khong_nhan_dien",
                nguon_khop="ten_thuoc_dav",
                ly_do="Chế phẩm DAV chưa có danh sách thành phần trên trục",
            )
        return KetQuaPhanGiai(
            trang_thai="khong_nhan_dien",
            ly_do="Không khớp tên chế phẩm DAV hoặc đồng nghĩa" if key else "Thiếu tên thuốc",
        )
