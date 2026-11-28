"""Đọc nguồn cục bộ, kiểm từng dòng và gộp trùng trước mọi kết nối."""

import csv
import json
from collections import Counter
from contextlib import closing
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.db.mapping import ADMINISTRATIVE_COLUMNS, DDINTER_LEVELS, TABLES, normalize_ingredient


class SourceError(ValueError):
    """Nguồn không đủ hoặc không đọc được."""


class RejectionLimitError(SourceError):
    """Một bảng có hơn 5% dòng bị loại."""


class Rejection(BaseModel):
    bang: str
    nguon_tep: str
    dong: str
    ly_do: str


class Batch:
    """Các dòng đã kiểm, kèm mẫu số nguồn và lý do loại."""

    def __init__(self, tables: tuple[str, ...] = ()) -> None:
        self.rows: dict[str, list[dict[str, Any]]] = {name: [] for name in TABLES}
        self.source_counts: Counter[str] = Counter()
        self.rejected: list[Rejection] = []
        self.tables = set(tables)
        self.outside_kb: dict[str, set[str]] = {}
        self.drug_signatures: dict[str, tuple[Any, ...]] = {}
        self._keys: dict[str, dict[tuple[Any, ...], dict[str, Any]]] = {name: {} for name in TABLES}

    def reject(self, table: str, source: str, line: str, reason: str) -> None:
        self.rejected.append(Rejection(bang=table, nguon_tep=source, dong=line, ly_do=reason))

    def add(self, table: str, raw: dict[str, Any], source: str, line: str = "") -> bool:
        """Loại đúng dòng lỗi, khử dòng trùng theo khoá chính."""
        self.tables.add(table)
        self.source_counts[table] += 1
        mapping = TABLES[table]
        try:
            row = mapping.convert(raw, source)
        except ValidationError as exc:
            reason = "; ".join(
                f"{'/'.join(map(str, e['loc']))}: "
                + ("thiếu" if e["type"] == "missing" else e["msg"])
                for e in exc.errors(include_input=False, include_context=False)
            )
            self.reject(table, source, line, reason)
            return False
        except (ValueError, TypeError) as exc:
            self.reject(table, source, line, str(exc))
            return False
        key = tuple(row[column] for column in mapping.primary_key)
        previous = self._keys[table].get(key)
        if previous is not None:
            if any(previous[col] != row[col] for col in mapping.columns):
                self.reject(table, source, line, f"trùng khoá khác nội dung: {key}")
                return False
            return True
        self._keys[table][key] = row
        self.rows[table].append(row)
        return True

    def orphans(self) -> list[str]:
        """Kiểm tra khoá ngoại ngay trên lượt nạp, không cần PostgreSQL."""
        result = []
        for name in self.tables:
            for reference in TABLES[name].foreign_keys:
                keys = {
                    tuple(row[c] for c in reference.target) for row in self.rows[reference.table]
                }
                for row in self.rows[name]:
                    key = tuple(row[c] for c in reference.columns)
                    if all(v is not None for v in key) and key not in keys:
                        result.append(f"{name}: thiếu {reference.table} {key}")
        return result

    def reject_orphans(self) -> None:
        """Loại dây chuyền dòng con có cha không hợp lệ theo thứ tự khoá ngoại."""
        changed = True
        while changed:
            changed = False
            for name, mapping in TABLES.items():
                for reference in mapping.foreign_keys:
                    keys = {
                        tuple(row[c] for c in reference.target)
                        for row in self.rows[reference.table]
                    }
                    kept = []
                    for row in self.rows[name]:
                        key = tuple(row[c] for c in reference.columns)
                        if all(v is not None for v in key) and key not in keys:
                            self.reject(
                                name,
                                row["nguon_tep"],
                                str(tuple(row[c] for c in mapping.primary_key)),
                                f"thiếu {reference.table}: {key}",
                            )
                            changed = True
                        else:
                            kept.append(row)
                    self.rows[name] = kept
                self._keys[name] = {
                    tuple(row[c] for c in mapping.primary_key): row for row in self.rows[name]
                }

    def finish(self, error_path: Path) -> None:
        """Ghi nhật ký loại và chặn trước giao dịch khi vượt ngưỡng."""
        if self.rejected:
            error_path.parent.mkdir(parents=True, exist_ok=True)
            with error_path.open("a", encoding="utf-8") as stream:
                for error in self.rejected:
                    stream.write(error.model_dump_json() + "\n")
        counts = Counter(error.bang for error in self.rejected)
        exceeded = [
            name for name, count in counts.items() if count / self.source_counts[name] > 0.05
        ]
        if exceeded:
            raise RejectionLimitError("Tỉ lệ loại vượt 5%: " + ", ".join(exceeded))


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise SourceError(f"Không đọc được nguồn {path.name}: {type(exc).__name__}") from None


def source_name(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def read_cases(root: Path) -> list[tuple[Path, dict[str, Any]]]:
    paths = []
    for directory in ("demo", "hoso_gia_lap"):
        found = sorted(
            path
            for path in (root / "data/mock" / directory).glob("*.json")
            if not path.name.startswith("_")
        )
        if not found:
            raise SourceError(f"thiếu data/mock/{directory}/*.json")
        paths.extend(found)
    return [(path, read_json(path)) for path in paths]


def add_catalog(batch: Batch, root: Path) -> list[dict[str, Any]]:
    path = root / "data/kb/hoat_chat.json"
    catalog = read_json(path)["hoat_chat"]
    valid_catalog = []
    known = set()
    for row in catalog:
        if batch.add("tri_thuc.hoat_chat", row, source_name(path, root)):
            valid_catalog.append(row)
            known.add(row["hoat_chat_id"])
    for path, case in read_cases(root):
        for row in case.get("danh_muc_hoat_chat", []):
            code = normalize_ingredient(row["hoat_chat_id"])
            if code in known:
                continue
            batch.outside_kb.setdefault(code, set()).add(row["hoat_chat_id"])
            # Giữ nguyên tên và thuộc tính nguồn; không suy đoán tri thức.
            if (code,) not in batch._keys["tri_thuc.hoat_chat"]:
                batch.add(
                    "tri_thuc.hoat_chat",
                    {**row, "hoat_chat_id": code, "can_duyet": True},
                    source_name(path, root),
                )
    return valid_catalog


def add_drug(batch: Batch, drug: dict[str, Any], source: str) -> None:
    """Gộp thuốc theo danh tính; loại cả bản sau nếu khác thành phần."""
    table = "nghiep_vu.thuoc"
    components = [
        {**row, "hoat_chat_id": normalize_ingredient(row["hoat_chat_id"])}
        for row in drug.get("thanh_phan", [])
    ]
    signature = (
        drug.get("ten_thuoc"),
        drug.get("ham_luong"),
        json.dumps(sorted(components, key=lambda row: row["hoat_chat_id"]), sort_keys=True),
    )
    key = drug.get("thuoc_id")
    if key in batch.drug_signatures:
        batch.source_counts[table] += 1
        if batch.drug_signatures[key] != signature:
            batch.reject(
                table,
                source,
                json.dumps(drug, ensure_ascii=False),
                f"trùng khoá khác ten_thuoc/ham_luong/thành phần: {key}; "
                f"giữ bản đầu từ {batch._keys[table][(key,)]['nguon_tep']}",
            )
        return
    if not batch.add(table, drug, source):
        return
    batch.drug_signatures[key] = signature
    for component in components:
        batch.add("nghiep_vu.thuoc_hoat_chat", {**component, "thuoc_id": key}, source)


def add_order(batch: Batch, order: dict[str, Any], encounter_id: str, source: str) -> None:
    batch.add("nghiep_vu.y_lenh", {**order, "dot_dieu_tri_id": encounter_id}, source)
    for row in order.get("chi_tiet", []):
        batch.add(
            "nghiep_vu.chi_tiet_y_lenh",
            {**row, "dot_dieu_tri_id": encounter_id, "y_lenh_id": order.get("y_lenh_id")},
            source,
        )
        for index, schedule in enumerate(row.get("lich_dung", [])):
            batch.add(
                "nghiep_vu.lich_dung",
                {**schedule, "chi_tiet_y_lenh_id": row.get("chi_tiet_y_lenh_id"), "thu_tu": index},
                source,
            )


def add_encounter(
    batch: Batch,
    encounter: dict[str, Any],
    patient_id: str,
    source: str,
    *,
    new_format: bool,
) -> None:
    encounter_id = encounter.get("dot_dieu_tri_id")
    batch.add(
        "nghiep_vu.dot_dieu_tri",
        {**encounter, **encounter.get("quan_ly", {}), "nguoi_benh_id": patient_id},
        source,
    )
    for key, table in (
        ("chan_doan", "chan_doan"),
        ("sinh_hieu", "sinh_hieu"),
        ("xet_nghiem", "ket_qua_xet_nghiem"),
        ("vi_sinh", "vi_sinh"),
        ("dien_bien", "dien_bien"),
    ):
        for row in encounter.get(key, []):
            raw = {**row, "dot_dieu_tri_id": encounter_id}
            if key == "chan_doan" and new_format and raw.get("thoi_diem") is None:
                raw["thoi_diem"] = encounter.get("thoi_diem_bat_dau")
            batch.add(f"nghiep_vu.{table}", raw, source)
            if key == "vi_sinh":
                for sensitivity in row.get("khang_sinh_do", []):
                    batch.add(
                        "nghiep_vu.khang_sinh_do",
                        {**sensitivity, "vi_sinh_id": row.get("vi_sinh_id")},
                        source,
                    )
    for order in encounter.get("y_lenh", []):
        add_order(batch, order, encounter_id, source)
    for sheet in encounter.get("phieu_dieu_tri", []):
        batch.add("nghiep_vu.phieu_dieu_tri", {**sheet, "dot_dieu_tri_id": encounter_id}, source)
        for order_id in sheet.get("y_lenh_trong_ngay", []):
            batch.add(
                "nghiep_vu.phieu_y_lenh",
                {
                    "phieu_dieu_tri_id": sheet.get("phieu_dieu_tri_id"),
                    "y_lenh_id": order_id,
                    "dot_dieu_tri_id": encounter_id,
                },
                source,
            )


def add_gold(batch: Batch, path: Path, root: Path, order_id: str) -> None:
    gold = root / "data/gold" / path.parent.name / path.name
    if not gold.is_file():
        raise SourceError(f"thiếu {source_name(gold, root)}")
    answer = read_json(gold)
    review_id = f"dap_an:{answer.get('ca_id')}"
    source = source_name(gold, root)
    batch.add(
        "nghiep_vu.lan_tham_dinh",
        {**answer, "tham_dinh_id": review_id, "y_lenh_id": order_id},
        source,
    )
    for index, finding in enumerate(answer.get("phat_hien_ky_vong", [])):
        finding_id = f"{review_id}:{index}"
        batch.add(
            "nghiep_vu.nhan_dinh",
            {**finding, "nhan_dinh_id": finding_id, "tham_dinh_id": review_id},
            source,
        )
        for line_id in finding.get("chi_tiet_y_lenh_id", []):
            batch.add(
                "nghiep_vu.nhan_dinh_thuoc",
                {"nhan_dinh_id": finding_id, "chi_tiet_y_lenh_id": line_id},
                source,
            )


def prepare_cases(root: Path) -> Batch:
    batch = Batch(tuple(name for name in TABLES if name.startswith("nghiep_vu.")))
    add_catalog(batch, root)
    for path, case in read_cases(root):
        source = source_name(path, root)
        patient = case.get("nguoi_benh", {})
        patient_id = patient.get("nguoi_benh_id")
        batch.add(
            "nghiep_vu.nguoi_benh",
            {
                **patient,
                **case.get("hanh_chinh", {}),
                "tinh_trang_di_ung": case.get("tinh_trang_di_ung"),
            },
            source,
        )
        for row in case.get("di_ung", []):
            batch.add("nghiep_vu.di_ung", {**row, "nguoi_benh_id": patient_id}, source)
        for drug in case.get("danh_muc_thuoc", []):
            add_drug(batch, drug, source)
        new_format = "ho_so_id" in case
        if new_format:
            encounters = case.get("dot_dieu_tri", [])
            order_id = case.get("y_lenh_trong_tam")
            summary = (encounters[-1].get("tom_tat") or "")[:200] if encounters else None
            encounters = [
                {
                    **encounter,
                    "y_lenh": [
                        {
                            **order,
                            "ca_id": case["ho_so_id"]
                            if order.get("y_lenh_id") == order_id
                            else None,
                            "mo_ta_ngan": summary if order.get("y_lenh_id") == order_id else None,
                        }
                        for order in encounter.get("y_lenh", [])
                    ],
                }
                for encounter in encounters
            ]
        else:
            order = {
                **case.get("y_lenh_cho_duyet", {}),
                "ca_id": case.get("ca_id"),
                "mo_ta_ngan": case.get("mo_ta_ngan"),
                "trang_thai": "cho_duyet",
                "loai": "thuong_quy",
                "vai_tro_nguoi_ke": "bac_si_dieu_tri",
            }
            order_id = order.get("y_lenh_id")
            orders = [order]
            active = case.get("thuoc_dang_dung", [])
            if active:
                from datetime import datetime

                orders.append(
                    {
                        "y_lenh_id": f"YL-{case['ca_id']}-NEN",
                        "khoa_ke_don": case.get("dot_dieu_tri", {}).get("khoa_dieu_tri"),
                        "luong_duyet": order.get("luong_duyet"),
                        "thoi_diem_ke": min(
                            (row["bat_dau"] for row in active), key=datetime.fromisoformat
                        ),
                        "trang_thai": "dang_thuc_hien",
                        "chi_tiet": active,
                    }
                )
            encounters = [{**case, **case.get("dot_dieu_tri", {}), "y_lenh": orders}]
        for encounter in encounters:
            add_encounter(batch, encounter, patient_id, source, new_format=new_format)
        add_gold(batch, path, root, order_id)
    batch.reject_orphans()
    return batch


def prepare_treatment_sheets(root: Path) -> Batch:
    """Kiểm cả khoá cha từ nguồn, chỉ cho phép nạp hai bảng phiếu."""
    batch = prepare_cases(root)
    batch.tables = {"nghiep_vu.phieu_dieu_tri", "nghiep_vu.phieu_y_lenh"}
    return batch


def prepare_administrative(root: Path) -> Batch:
    """Chỉ chuẩn bị hai bảng hành chính; không đọc tri thức/đáp án."""
    batch = Batch(tuple(ADMINISTRATIVE_COLUMNS))
    for path, case in read_cases(root):
        source = source_name(path, root)
        patient = case.get("nguoi_benh", {})
        admin = case.get("hanh_chinh", {})
        table = "nghiep_vu.nguoi_benh"
        if not isinstance(admin, dict) or set(ADMINISTRATIVE_COLUMNS[table]) - admin.keys():
            batch.tables.add(table)
            batch.source_counts[table] += 1
            batch.reject(table, source, "", "thiếu trường hanh_chinh")
        else:
            batch.add(
                table,
                {**patient, **admin, "tinh_trang_di_ung": case.get("tinh_trang_di_ung")},
                source,
            )
        encounters = case.get("dot_dieu_tri", [])
        if not isinstance(encounters, list):
            encounters = [{**case, **encounters}]
        for encounter in encounters:
            management = encounter.get("quan_ly", {})
            table = "nghiep_vu.dot_dieu_tri"
            if (
                not isinstance(management, dict)
                or set(ADMINISTRATIVE_COLUMNS[table]) - management.keys()
            ):
                batch.tables.add(table)
                batch.source_counts[table] += 1
                batch.reject(table, source, "", "thiếu trường quan_ly")
            else:
                batch.add(
                    table,
                    {**encounter, **management, "nguoi_benh_id": patient.get("nguoi_benh_id")},
                    source,
                )
    batch.reject_orphans()
    return batch


def prepare_kb(root: Path) -> Batch:
    batch = Batch(
        tuple(
            name
            for name in TABLES
            if name.startswith("tri_thuc.") and not name.endswith("tuong_tac_sang_loc")
        )
    )
    catalog = add_catalog(batch, root)
    for item in catalog:
        for name in (
            item["hoat_chat_id"],
            item.get("ten_inn"),
            item.get("ten_viet"),
            *item.get("dong_nghia", []),
        ):
            if name:
                batch.add(
                    "tri_thuc.ten_thuoc",
                    {"ten_thuoc": name, "hoat_chat_id": item["hoat_chat_id"]},
                    "data/kb/hoat_chat.json",
                )
    manifest = read_json(root / "data/kb_sources/manifest.json")
    for item in manifest["tep"]:
        if item.get("set_id"):
            batch.add(
                "tri_thuc.tai_lieu",
                {**item, "tai_lieu_id": f"openfda:{item['set_id']}"},
                "data/kb_sources/" + item["duong_dan"],
            )
    path = root / "data/kb_curated/chunks.jsonl"
    with path.open(encoding="utf-8") as stream:
        for index, line in enumerate(stream, 1):
            if line.strip():
                try:
                    raw = json.loads(line)
                except ValueError:
                    batch.source_counts["tri_thuc.doan_trich"] += 1
                    batch.reject(
                        "tri_thuc.doan_trich", source_name(path, root), str(index), "sai JSON"
                    )
                else:
                    batch.add("tri_thuc.doan_trich", raw, source_name(path, root), str(index))
    path = root / "data/kb/quy_tac_lieu_than.json"
    rules = read_json(path)
    for rule_index, rule in enumerate(rules["quy_tac"]):
        for index, tier in enumerate(rule["muc"]):
            batch.add(
                "tri_thuc.quy_tac_lieu_than",
                {
                    **rule,
                    **tier,
                    "quy_tac_id": f"{rules['phien_ban']}:{rule_index}:{index}",
                    "phien_ban": rules["phien_ban"],
                    "ghi_chu": rules.get("ghi_chu"),
                },
                source_name(path, root),
            )
    batch.reject_orphans()
    return batch


def prepare_ddinter(root: Path) -> Batch:
    table = "tri_thuc.tuong_tac_sang_loc"
    batch = Batch((table,))
    paths = sorted((root / "data/kb_sources/ddinter").glob("*.csv"))
    if len(paths) != 14:
        raise SourceError(f"thiếu bộ 14 tệp DDInter: có {len(paths)}")
    metadata = {
        row["duong_dan"]: row for row in read_json(root / "data/kb_sources/manifest.json")["tep"]
    }
    pairs: dict[tuple[str, str], dict[str, Any]] = {}
    total = 0
    for path in paths:
        source = source_name(path, root)
        info = metadata[f"ddinter/{path.name}"]
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for index, row in enumerate(csv.DictReader(stream), 2):
                total += 1
                required = ("DDInterID_A", "DDInterID_B", "Drug_A", "Drug_B", "Level")
                missing = [key for key in required if not row.get(key)]
                if missing or row.get("Level") not in DDINTER_LEVELS:
                    batch.reject(
                        table,
                        source,
                        str(index),
                        "thiếu " + ", ".join(missing) if missing else "sai Level",
                    )
                    continue
                a, b = row["DDInterID_A"], row["DDInterID_B"]
                if a == b:
                    batch.reject(table, source, str(index), "cặp tự tương tác")
                    continue
                if a > b:
                    row["DDInterID_A"], row["DDInterID_B"] = b, a
                    row["Drug_A"], row["Drug_B"] = row["Drug_B"], row["Drug_A"]
                key = (row["DDInterID_A"], row["DDInterID_B"])
                previous = pairs.get(key)
                if previous is None:
                    pairs[key] = {
                        **row,
                        "muc_do_nguon": {row["Level"]},
                        "cac_tep_nguon": {source},
                        "nguon": info["nguon"],
                        "tang_tin_cay": info["tang_tin_cay"],
                        "giay_phep": info["giay_phep"],
                        "trang_thai": "sang_loc",
                    }
                else:
                    previous["muc_do_nguon"].add(row["Level"])
                    previous["cac_tep_nguon"].add(source)
                    if DDINTER_LEVELS[row["Level"]] > DDINTER_LEVELS[previous["Level"]]:
                        previous["Level"] = row["Level"]
    for row in pairs.values():
        row["muc_do_nguon"] = sorted(row["muc_do_nguon"])
        row["cac_tep_nguon"] = sorted(row["cac_tep_nguon"])
        row["co_muc_lech"] = len(row["muc_do_nguon"]) > 1
        batch.add(table, row, row["cac_tep_nguon"][0])
    batch.source_counts[table] = total
    return batch


def prepare(group: str, root: Path) -> Batch:
    readers = {"cases": prepare_cases, "kb": prepare_kb, "ddinter": prepare_ddinter}
    return readers[group](root)


class Embeddings(BaseModel):
    vectors: dict[str, str] = Field(default_factory=dict)
    missing: int = 0
    rejected: list[Rejection] = Field(default_factory=list)

    def finish(self, error_path: Path) -> None:
        batch = Batch(("tri_thuc.doan_trich",))
        batch.source_counts["tri_thuc.doan_trich"] = len(self.vectors) + self.missing
        batch.rejected = self.rejected
        batch.finish(error_path)


def read_embeddings(chunks: list[dict[str, Any]], path: Path, model: str) -> Embeddings:
    """Đọc SQLite chỉ đọc; không khởi tạo nhà cung cấp hay gọi mạng."""
    import hashlib
    import sqlite3

    import numpy as np

    result = Embeddings()
    if not path.is_file():
        result.missing = len(chunks)
        return result
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        for chunk in chunks:
            key = hashlib.sha256(f"{model}\ndoc\n{chunk['noi_dung_nhung']}".encode()).hexdigest()
            row = connection.execute(
                "SELECT dims, vec FROM embeddings WHERE key = ?", (key,)
            ).fetchone()
            if row is None:
                result.missing += 1
                continue
            try:
                vector = np.frombuffer(row[1], dtype=np.float32)
                valid = (
                    row[0] == 2048
                    and len(vector) == 2048
                    and np.isfinite(vector).all()
                    and np.any(vector)
                    and np.max(np.abs(vector)) <= np.finfo(np.float16).max
                )
            except (ValueError, TypeError):
                valid = False
            if not valid:
                result.missing += 1
                result.rejected.append(
                    Rejection(
                        bang="tri_thuc.doan_trich",
                        nguon_tep=path.as_posix(),
                        dong=chunk["doan_trich_id"],
                        ly_do="embedding bộ đệm sai kiểu/số chiều/giá trị halfvec",
                    )
                )
                continue
            result.vectors[chunk["doan_trich_id"]] = "[" + ",".join(map(str, vector.tolist())) + "]"
    return result
