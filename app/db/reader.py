"""Đọc ca từ PostgreSQL chỉ đọc, dựng mô hình và đối chiếu nguồn cục bộ."""

import argparse
import json
import sys
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any

import psycopg
from psycopg import IsolationLevel, sql
from psycopg.rows import dict_row
from pydantic import BaseModel, ValidationError

from app.config.settings import get_secret
from app.core.errors import ConfigError
from app.db.timezone import to_vn_time
from app.domain import models as m
from app.pipeline import KetQuaThamDinh, run_case
from app.rules import RenalRuleBook, load_renal_rules

Row = dict[str, Any]
Rows = Mapping[str, Sequence[Row]]
Index = dict[str, dict[str, list[Row]]]
_ROOT = Path(__file__).resolve().parents[2]
_GROUP_KEYS = {
    "nguoi_benh": "nguoi_benh_id",
    "dot_dieu_tri": "dot_dieu_tri_id",
    "di_ung": "nguoi_benh_id",
    "chan_doan": "dot_dieu_tri_id",
    "sinh_hieu": "dot_dieu_tri_id",
    "ket_qua_xet_nghiem": "dot_dieu_tri_id",
    "vi_sinh": "dot_dieu_tri_id",
    "khang_sinh_do": "vi_sinh_id",
    "dien_bien": "dot_dieu_tri_id",
    "chi_tiet_y_lenh": "dot_dieu_tri_id",
    "lich_dung": "chi_tiet_y_lenh_id",
    "thuoc": "thuoc_id",
    "thuoc_hoat_chat": "thuoc_id",
    "hoat_chat": "hoat_chat_id",
}


class DatabaseReadError(RuntimeError):
    """Lỗi nguồn DB đã bỏ mọi thông tin kết nối và dữ liệu đầu vào."""


def _fields(model: type[BaseModel], row: Row) -> Row:
    return {key: row[key] for key in model.model_fields if key in row}


def _index_rows(rows: Rows) -> Index:
    result: Index = {}
    for table, key in _GROUP_KEYS.items():
        schema = "tri_thuc" if table == "hoat_chat" else "nghiep_vu"
        groups: dict[str, list[Row]] = defaultdict(list)
        for row in rows.get(f"{schema}.{table}", []):
            if key in row:
                groups[row[key]].append(row)
        result[table] = groups
    return result


def with_height_vital(
    vitals: list[Row], patient_id: str, height_cm: Any, measured_at: Any
) -> list[Row]:
    """Chiều cao ở hồ sơ hành chính là số đo lâm sàng; thêm một dòng sinh hiệu nếu chưa có."""
    if height_cm is None or any(row.get("loai") == "chieu_cao" for row in vitals):
        return vitals
    return [
        *vitals,
        {
            "sinh_hieu_id": f"SH-{patient_id}-CC",
            "loai": "chieu_cao",
            "gia_tri": float(height_cm),
            "don_vi": "cm",
            "thoi_diem_do": measured_at,
        },
    ]


def build_case(order: Row, index: Index) -> m.CaBenh:
    """Dựng đúng đợt chứa y lệnh trọng tâm, không đọc file hay mạng."""

    def required_row(table: str, key: str) -> Row:
        found = index[table].get(key, [])
        if not found:
            raise KeyError(f"{table}.{_GROUP_KEYS[table]}")
        return found[0]

    encounter_id = order["dot_dieu_tri_id"]
    encounter = required_row("dot_dieu_tri", encounter_id)
    patient_id = encounter["nguoi_benh_id"]
    patient = required_row("nguoi_benh", patient_id)

    def children(table: str, key: str = encounter_id) -> list[Row]:
        return index[table].get(key, [])

    def line_view(row: Row) -> Row:
        schedules = sorted(
            children("lich_dung", row["chi_tiet_y_lenh_id"]), key=lambda item: item["thu_tu"]
        )
        return {
            **_fields(m.ChiTietYLenh, row),
            "lich_dung": [_fields(m.LichDung, item) for item in schedules],
        }

    lines = children("chi_tiet_y_lenh")
    pending = [line_view(row) for row in lines if row["y_lenh_id"] == order["y_lenh_id"]]
    active = [
        line_view(row)
        for row in lines
        if row["y_lenh_id"] != order["y_lenh_id"] and row["trang_thai_dong"] == "active"
    ]
    allergies = [_fields(m.DiUng, row) for row in children("di_ung", patient_id)]
    cultures = [
        {
            **_fields(m.ViSinh, row),
            "khang_sinh_do": [
                _fields(m.KhangSinhDo, item)
                for item in children("khang_sinh_do", row["vi_sinh_id"])
            ],
        }
        for row in children("vi_sinh")
    ]
    drug_ids = {row["thuoc_id"] for row in [*pending, *active] if row.get("thuoc_id")}
    drugs = [
        {
            **_fields(m.Thuoc, required_row("thuoc", code)),
            "thanh_phan": [_fields(m.ThanhPhan, row) for row in children("thuoc_hoat_chat", code)],
        }
        for code in sorted(drug_ids)
    ]
    ingredient_ids = {
        component["hoat_chat_id"] for drug in drugs for component in drug["thanh_phan"]
    }
    ingredient_ids.update(row["hoat_chat_id"] for row in allergies if row.get("hoat_chat_id"))
    ingredient_ids.update(
        row["hoat_chat_id"] for culture in cultures for row in culture["khang_sinh_do"]
    )
    view = {
        "ca_id": order["ca_id"],
        "mo_ta_ngan": (
            (encounter["tom_tat"] or "hồ sơ giả lập")
            if encounter.get("tom_tat") is not None
            else order["mo_ta_ngan"]
        ),
        "nguoi_benh": _fields(m.NguoiBenh, patient),
        "tinh_trang_di_ung": patient["tinh_trang_di_ung"],
        "di_ung": allergies,
        "dot_dieu_tri": _fields(m.DotDieuTri, encounter),
        "co_dia": encounter["co_dia"],
        "vi_sinh": cultures,
        "thuoc_dang_dung": active,
        "y_lenh_cho_duyet": {**_fields(m.YLenh, order), "chi_tiet": pending},
        "danh_muc_thuoc": drugs,
        "danh_muc_hoat_chat": [
            _fields(m.HoatChat, required_row("hoat_chat", code)) for code in sorted(ingredient_ids)
        ],
    }
    for field, table, model in (
        ("chan_doan", "chan_doan", m.ChanDoan),
        ("sinh_hieu", "sinh_hieu", m.SinhHieu),
        ("xet_nghiem", "ket_qua_xet_nghiem", m.KetQuaXetNghiem),
        ("dien_bien", "dien_bien", m.DienBien),
    ):
        view[field] = [_fields(model, row) for row in children(table)]
    view["sinh_hieu"] = with_height_vital(
        view["sinh_hieu"],
        patient_id,
        patient.get("chieu_cao_cm"),
        encounter["thoi_diem_bat_dau"],
    )
    return m.CaBenh.model_validate(view)


def build_cases(rows: Rows) -> tuple[list[m.CaBenh], list[tuple[str, str]]]:
    """Gom hàng một lần, cô lập lỗi từng ca và không phản chiếu giá trị lỗi."""
    index = _index_rows(rows)
    cases: list[m.CaBenh] = []
    errors: list[tuple[str, str]] = []
    orders = [row for row in rows.get("nghiep_vu.y_lenh", []) if row.get("ca_id")]
    for order in sorted(orders, key=lambda row: row["ca_id"]):
        try:
            cases.append(build_case(order, index))
        except ValidationError as exc:
            fields = sorted({".".join(map(str, item["loc"])) for item in exc.errors()})
            errors.append((order["ca_id"], "Dữ liệu thiếu hoặc không hợp lệ: " + ", ".join(fields)))
        except KeyError as exc:
            errors.append((order["ca_id"], "Thiếu trường hoặc bản ghi: " + str(exc.args[0])))
        except (IndexError, TypeError, ValueError):
            errors.append((order["ca_id"], "Thiếu hoặc không hợp lệ: bản ghi liên quan của ca."))
    return cases, errors


def read_case_rows() -> dict[str, list[Row]]:
    """Mỗi bảng một SELECT theo tập khoá; toàn bộ lượt đọc cùng một ảnh chụp."""
    try:
        url = get_secret("DATABASE_URL").strip()
        if not url:
            raise ConfigError("DATABASE_URL")
    except ConfigError:
        raise DatabaseReadError(
            "Chưa cấu hình DATABASE_URL để đọc ca bệnh từ cơ sở dữ liệu."
        ) from None
    try:
        with psycopg.connect(
            url,
            options="-c default_transaction_read_only=on",
            row_factory=dict_row,
            connect_timeout=10,
        ) as connection:
            connection.isolation_level = IsolationLevel.REPEATABLE_READ
            connection.read_only = True
            rows: dict[str, list[Row]] = {
                "nghiep_vu.y_lenh": to_vn_time(
                    connection.execute(
                        "SELECT * FROM nghiep_vu.y_lenh WHERE dot_dieu_tri_id IN "
                        "(SELECT dot_dieu_tri_id FROM nghiep_vu.y_lenh "
                        "WHERE ca_id IS NOT NULL AND ca_id <> '')"
                    ).fetchall()
                )
            }

            def select(table: str, column: str, keys: Sequence[str]) -> list[Row]:
                query = sql.SQL("SELECT * FROM {} WHERE {} = ANY(%s)").format(
                    sql.Identifier(*table.split(".")), sql.Identifier(column)
                )
                result = to_vn_time(connection.execute(query, (sorted(set(keys)),)).fetchall())
                rows[table] = result
                return result

            encounter_ids = [row["dot_dieu_tri_id"] for row in rows["nghiep_vu.y_lenh"]]
            encounters = select("nghiep_vu.dot_dieu_tri", "dot_dieu_tri_id", encounter_ids)
            patient_ids = [row["nguoi_benh_id"] for row in encounters]
            select("nghiep_vu.nguoi_benh", "nguoi_benh_id", patient_ids)
            allergies = select("nghiep_vu.di_ung", "nguoi_benh_id", patient_ids)
            for table in (
                "chan_doan",
                "sinh_hieu",
                "ket_qua_xet_nghiem",
                "vi_sinh",
                "dien_bien",
                "chi_tiet_y_lenh",
            ):
                select(f"nghiep_vu.{table}", "dot_dieu_tri_id", encounter_ids)
            sensitivities = select(
                "nghiep_vu.khang_sinh_do",
                "vi_sinh_id",
                [row["vi_sinh_id"] for row in rows["nghiep_vu.vi_sinh"]],
            )
            lines = rows["nghiep_vu.chi_tiet_y_lenh"]
            select(
                "nghiep_vu.lich_dung",
                "chi_tiet_y_lenh_id",
                [row["chi_tiet_y_lenh_id"] for row in lines],
            )
            drug_ids = [row["thuoc_id"] for row in lines if row["thuoc_id"]]
            select("nghiep_vu.thuoc", "thuoc_id", drug_ids)
            components = select("nghiep_vu.thuoc_hoat_chat", "thuoc_id", drug_ids)
            select(
                "tri_thuc.hoat_chat",
                "hoat_chat_id",
                [
                    row["hoat_chat_id"]
                    for row in [*components, *allergies, *sensitivities]
                    if row["hoat_chat_id"]
                ],
            )
            return rows
    except (psycopg.Error, ValueError, OSError):
        raise DatabaseReadError(
            "Không thể đọc ca bệnh từ cơ sở dữ liệu. Vui lòng kiểm tra cấu hình và kết nối."
        ) from None


class DbReviewService:
    """Nạp lười, giữ bộ đệm có thể làm mới và dùng pipeline thẩm định hiện có."""

    def __init__(self, renal_rules_path: Path) -> None:
        self._renal_rules_path = Path(renal_rules_path)
        self._renal_rules: RenalRuleBook | None = None
        self._cache: tuple[list[m.CaBenh], list[tuple[str, str]]] | None = None
        self._lock = RLock()

    def refresh(self) -> None:
        """Xoá bộ đệm; lần đọc kế tiếp sẽ truy vấn lại."""
        with self._lock:
            self._cache = None

    def list_cases(self) -> tuple[list[m.CaBenh], list[tuple[str, str]]]:
        with self._lock:
            if self._cache is None:
                self._cache = build_cases(read_case_rows())
            return self._cache

    def review(self, ca: m.CaBenh) -> KetQuaThamDinh:
        if self._renal_rules is None:
            self._renal_rules = load_renal_rules(self._renal_rules_path)
        return run_case(ca, self._renal_rules)


def load_source_cases(root: Path) -> list[m.CaBenh]:
    """Dựng khung nhìn tệp độc lập với bộ dựng DB, như công cụ kiểm hồ sơ."""
    from app.db.sources import read_cases

    cases = []
    for _, raw in read_cases(root):
        if "ho_so_id" not in raw:
            view = {key: value for key, value in raw.items() if key != "hanh_chinh"}
            view["dot_dieu_tri"] = {
                key: value for key, value in raw["dot_dieu_tri"].items() if key != "quan_ly"
            }
            view["sinh_hieu"] = with_height_vital(
                list(view["sinh_hieu"]),
                raw["nguoi_benh"]["nguoi_benh_id"],
                (raw.get("hanh_chinh") or {}).get("chieu_cao_cm"),
                raw["dot_dieu_tri"]["thoi_diem_bat_dau"],
            )
            cases.append(m.CaBenh.model_validate(view))
            continue
        encounter = next(
            item
            for item in raw["dot_dieu_tri"]
            if any(order["y_lenh_id"] == raw["y_lenh_trong_tam"] for order in item["y_lenh"])
        )
        focus = next(
            order for order in encounter["y_lenh"] if order["y_lenh_id"] == raw["y_lenh_trong_tam"]
        )
        view = {
            key: raw[key]
            for key in (
                "nguoi_benh",
                "tinh_trang_di_ung",
                "di_ung",
                "danh_muc_thuoc",
                "danh_muc_hoat_chat",
            )
        }
        view.update(
            {
                key: encounter[key]
                for key in (
                    "chan_doan",
                    "co_dia",
                    "sinh_hieu",
                    "xet_nghiem",
                    "vi_sinh",
                )
            }
        )
        view.update(
            {
                "ca_id": raw["ho_so_id"],
                "mo_ta_ngan": encounter["tom_tat"] or "hồ sơ giả lập",
                "dot_dieu_tri": _fields(m.DotDieuTri, encounter),
                "dien_bien": [_fields(m.DienBien, row) for row in encounter["dien_bien"]],
                "thuoc_dang_dung": [
                    row
                    for order in encounter["y_lenh"]
                    if order is not focus
                    for row in order["chi_tiet"]
                    if row["trang_thai_dong"] == "active"
                ],
                "y_lenh_cho_duyet": _fields(m.YLenh, focus),
            }
        )
        view["sinh_hieu"] = with_height_vital(
            list(view["sinh_hieu"]),
            raw["nguoi_benh"]["nguoi_benh_id"],
            (raw.get("hanh_chinh") or {}).get("chieu_cao_cm"),
            encounter["thoi_diem_bat_dau"],
        )
        cases.append(m.CaBenh.model_validate(view))
    return sorted(cases, key=lambda case: case.ca_id)


def comparison_dump(case: m.CaBenh) -> Row:
    """Chỉ bỏ khác biệt thứ tự, mã hoạt chất và biểu diễn múi giờ."""
    from app.db.mapping import normalize_ingredient

    def normalize(value: Any, key: str = "") -> Any:
        if isinstance(value, dict):
            return {name: normalize(item, name) for name, item in value.items()}
        if isinstance(value, list):
            return sorted(
                (normalize(item) for item in value),
                key=lambda item: json.dumps(item, sort_keys=True, ensure_ascii=False),
            )
        if isinstance(value, str):
            if key == "hoat_chat_id":
                return normalize_ingredient(value)
            if key.startswith("thoi_diem") or key in ("bat_dau", "ket_thuc"):
                return datetime.fromisoformat(value).astimezone(UTC).isoformat()
        return value

    return normalize(case.model_dump(mode="json"))


def verify_read(root: Path = _ROOT) -> int:
    """So ca DB với tệp, chỉ in mã ca và tên trường lệch, không in dữ liệu."""
    try:
        cases, errors = build_cases(read_case_rows())
        expected = expected_source_dumps(root)
    except DatabaseReadError as exc:
        print(str(exc))
        return 1
    actual = {case.ca_id: comparison_dump(case) for case in cases}
    matched = 0
    for case_id in sorted(expected.keys() | actual.keys()):
        if expected.get(case_id) == actual.get(case_id):
            matched += 1
        else:
            left, right = expected.get(case_id, {}), actual.get(case_id, {})
            fields = sorted(
                key for key in left.keys() | right.keys() if left.get(key) != right.get(key)
            )
            print(f"Lệch {case_id}: {', '.join(fields) or 'thiếu ca'}")
    print(
        f"Khớp {matched}/{len(expected)} ca; "
        f"lệch {len(expected.keys() | actual.keys()) - matched}; lỗi dựng {len(errors)}."
    )
    return 0 if matched == len(expected) == len(actual) and not errors else 1


def expected_source_dumps(root: Path) -> dict[str, Row]:
    """Áp dụng đúng danh mục KB của bộ nạp, giữ mọi số liệu lâm sàng nguồn."""
    from app.db.sources import Batch, add_catalog

    batch = Batch()
    add_catalog(batch, root)
    catalog = {
        row["hoat_chat_id"]: _fields(m.HoatChat, row) for row in batch.rows["tri_thuc.hoat_chat"]
    }
    result = {}
    for case in load_source_cases(root):
        view = comparison_dump(case)
        drug_ids = {
            row["thuoc_id"]
            for row in [*view["thuoc_dang_dung"], *view["y_lenh_cho_duyet"]["chi_tiet"]]
            if row["thuoc_id"]
        }
        view["danh_muc_thuoc"] = [
            row for row in view["danh_muc_thuoc"] if row["thuoc_id"] in drug_ids
        ]
        ingredient_ids = {
            row["hoat_chat_id"] for drug in view["danh_muc_thuoc"] for row in drug["thanh_phan"]
        }
        ingredient_ids.update(row["hoat_chat_id"] for row in view["di_ung"] if row["hoat_chat_id"])
        ingredient_ids.update(
            row["hoat_chat_id"] for culture in view["vi_sinh"] for row in culture["khang_sinh_do"]
        )
        view["danh_muc_hoat_chat"] = sorted(
            (catalog[code] for code in ingredient_ids),
            key=lambda row: json.dumps(row, sort_keys=True, ensure_ascii=False),
        )
        result[case.ca_id] = view
    return result


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify-read", "verify-ho-so"))
    args = parser.parse_args()
    if args.command == "verify-ho-so":
        from app.db.medical_record import verify_ho_so

        return verify_ho_so()
    return verify_read()


if __name__ == "__main__":
    raise SystemExit(main())
