"""Kiểm chứng hồ sơ nhiều đợt và nêu rõ xung đột danh mục nguồn T40."""

import copy
import json
import re
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import pytest

from app.db.engine import expected_counts
from app.db.mapping import ACTIVE_DRUG_VIEW, TABLES, normalize_ingredient
from app.db.sources import (
    Batch,
    RejectionLimitError,
    add_drug,
    prepare_cases,
    read_cases,
    read_json,
)

ROOT = Path(__file__).resolve().parents[2]
OUTSIDE_KB = {"penicillin", "gabapentin", "cefoperazone", "sulbactam"}


@pytest.fixture(scope="module")
def batch() -> Batch:
    return prepare_cases(ROOT)


def test_all_66_cases_and_every_encounter_have_valid_references(batch: Batch) -> None:
    cases = read_cases(ROOT)
    assert len(cases) == 66
    assert not batch.orphans()
    assert len(batch.rows["nghiep_vu.nguoi_benh"]) == 66
    assert len(batch.rows["nghiep_vu.dot_dieu_tri"]) == 6 + 87
    orders = batch.rows["nghiep_vu.y_lenh"]
    assert (
        len(orders)
        == 6
        + sum(
            len(encounter["y_lenh"])
            for _, case in cases
            if "ho_so_id" in case
            for encounter in case["dot_dieu_tri"]
        )
        == 228
    )
    focuses = {row["ca_id"]: row for row in orders if row["ca_id"] is not None}
    assert len(focuses) == 66
    assert Counter(row["ca_id"] for row in orders if row["ca_id"]) == Counter(
        case.get("ho_so_id", case.get("ca_id")) for _, case in cases
    )
    for _, case in cases:
        focus = focuses[case.get("ho_so_id", case.get("ca_id"))]
        assert focus["trang_thai"] == "cho_duyet"
        if "ho_so_id" in case:
            assert focus["y_lenh_id"] == case["y_lenh_trong_tam"]
            assert focus["mo_ta_ngan"] == case["dot_dieu_tri"][-1]["tom_tat"][:200]
    for encounter in batch.rows["nghiep_vu.dot_dieu_tri"]:
        assert "ca_id" not in encounter and "mo_ta_ngan" not in encounter
        assert encounter["tuoi_luc_vao"] is None
    for review in batch.rows["nghiep_vu.lan_tham_dinh"]:
        assert review["y_lenh_id"] == focuses[review["ca_id"]]["y_lenh_id"]
    assert len(batch.rows["nghiep_vu.lan_tham_dinh"]) == 66


def test_source_conflicts_are_explicit_and_no_other_rows_are_rejected(
    tmp_path: Path,
) -> None:
    first_drugs = [
        {
            "thuoc_id": "T-TEST-NAME",
            "ten_thuoc": "Thuốc giả lập A",
            "thanh_phan": [{"hoat_chat_id": "test"}],
        },
        {
            "thuoc_id": "T-TEST-UNIT",
            "ten_thuoc": "Thuốc giả lập B",
            "ham_luong": "1 g",
            "thanh_phan": [{"hoat_chat_id": "test"}],
        },
    ]
    later_drugs = copy.deepcopy(first_drugs)
    later_drugs[0]["ten_thuoc"] = "Thuốc giả lập C"
    later_drugs[1]["ham_luong"] = "1000 mg"
    catalog_path = tmp_path / "data/kb/hoat_chat.json"
    catalog_path.parent.mkdir(parents=True)
    catalog_path.write_text(
        json.dumps({"hoat_chat": [{"hoat_chat_id": "test", "ten_hoat_chat": "Giả lập"}]}),
        encoding="utf-8",
    )
    sources = []
    for index, (directory, drugs) in enumerate(
        (("demo", first_drugs), ("hoso_gia_lap", later_drugs)), start=1
    ):
        case_id = f"HS-TEST-{index}"
        order_id = f"YL-TEST-{index}"
        timestamp = "2026-11-12T08:00:00+07:00"
        case = {
            "ho_so_id": case_id,
            "nguoi_benh": {"nguoi_benh_id": f"NB-TEST-{index}"},
            "tinh_trang_di_ung": {"trang_thai": "chua_co_thong_tin"},
            "danh_muc_thuoc": drugs,
            "y_lenh_trong_tam": order_id,
            "dot_dieu_tri": [
                {
                    "dot_dieu_tri_id": f"DT-TEST-{index}",
                    "khoa_dieu_tri": "Khoa giả lập",
                    "loai_dieu_tri": "noi_tru",
                    "thoi_diem_bat_dau": timestamp,
                    "y_lenh": [
                        {
                            "y_lenh_id": order_id,
                            "khoa_ke_don": "Khoa giả lập",
                            "luong_duyet": "truc_tiep",
                            "thoi_diem_ke": timestamp,
                            "trang_thai": "cho_duyet",
                            "chi_tiet": [
                                {
                                    "chi_tiet_y_lenh_id": f"CT-TEST-{index}-{drug_index}",
                                    "thuoc_id": drug["thuoc_id"],
                                    "bat_dau": timestamp,
                                    "trang_thai_dong": "pending",
                                }
                                for drug_index, drug in enumerate(drugs)
                            ],
                        }
                    ],
                }
            ],
        }
        path = tmp_path / "data/mock" / directory / f"{case_id}.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(case, ensure_ascii=False), encoding="utf-8")
        sources.append(path.relative_to(tmp_path).as_posix())
        gold_path = tmp_path / "data/gold" / directory / path.name
        gold_path.parent.mkdir(parents=True)
        gold_path.write_text(json.dumps({"ca_id": case_id}), encoding="utf-8")

    batch = prepare_cases(tmp_path)
    # Bộ nạp so sánh nguyên văn hàm lượng, chưa quy đổi 1 g = 1000 mg.
    assert len(batch.rejected) == 2
    assert {error.bang for error in batch.rejected} == {"nghiep_vu.thuoc"}
    assert [json.loads(error.dong) for error in batch.rejected] == later_drugs
    for error, drug in zip(batch.rejected, later_drugs, strict=True):
        assert error.nguon_tep == sources[1]
        assert "trùng khoá khác ten_thuoc/ham_luong/thành phần" in error.ly_do
        assert drug["thuoc_id"] in error.ly_do
        assert f"giữ bản đầu từ {sources[0]}" in error.ly_do
    assert batch.rows["nghiep_vu.thuoc"] == [
        TABLES["nghiep_vu.thuoc"].convert(drug, sources[0]) for drug in first_drugs
    ]
    assert batch.rows["nghiep_vu.thuoc_hoat_chat"] == [
        TABLES["nghiep_vu.thuoc_hoat_chat"].convert(
            {"thuoc_id": drug["thuoc_id"], **drug["thanh_phan"][0]}, sources[0]
        )
        for drug in first_drugs
    ]
    assert batch.source_counts["nghiep_vu.thuoc"] == 4
    assert not batch.orphans()
    for table in ("nguoi_benh", "dot_dieu_tri", "y_lenh", "lan_tham_dinh"):
        assert len(batch.rows[f"nghiep_vu.{table}"]) == 2
    assert len(batch.rows["nghiep_vu.chi_tiet_y_lenh"]) == 4
    error_path = tmp_path / "nap_loi.jsonl"
    with pytest.raises(RejectionLimitError, match="5%"):
        batch.finish(error_path)
    assert [json.loads(line) for line in error_path.read_text(encoding="utf-8").splitlines()] == [
        error.model_dump() for error in batch.rejected
    ]


def test_repository_cases_load_without_rejections_and_with_expected_counts(batch: Batch) -> None:
    assert not batch.rejected
    counts = expected_counts([batch])
    for table, count in {
        "nguoi_benh": 66,
        "dot_dieu_tri": 93,
        "y_lenh": 228,
        "chi_tiet_y_lenh": 233,
        "thuoc": 67,
        "lan_tham_dinh": 66,
    }.items():
        assert counts[f"nghiep_vu.{table}"] == count


def test_canonical_ingredients_and_external_catalog_preserve_source(batch: Batch) -> None:
    kb = {row["hoat_chat_id"] for row in read_json(ROOT / "data/kb/hoat_chat.json")["hoat_chat"]}
    ingredients = {row["hoat_chat_id"]: row for row in batch.rows["tri_thuc.hoat_chat"]}
    assert set(ingredients) == kb | OUTSIDE_KB
    assert set(batch.outside_kb) == OUTSIDE_KB
    assert not any(code.startswith("HC-") for code in ingredients)
    for table in ("thuoc_hoat_chat", "di_ung", "khang_sinh_do"):
        for row in batch.rows[f"nghiep_vu.{table}"]:
            assert row["hoat_chat_id"] is None or row["hoat_chat_id"] in ingredients
    for _, case in read_cases(ROOT):
        for raw in case["danh_muc_hoat_chat"]:
            code = normalize_ingredient(raw["hoat_chat_id"])
            if code in OUTSIDE_KB:
                assert ingredients[code]["can_duyet"] is True
                for field in ("ten_hoat_chat", "ten_quoc_te", "ma_atc", "nhom_duoc_ly"):
                    assert ingredients[code][field] == raw.get(field)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("AMLODIPIN", "amlodipine"),
        ("CEFTRIAXON", "ceftriaxone"),
        ("ACID-CLAVULANIC", "clavulanic_acid"),
        ("ACID_CLAVULANIC", "clavulanic_acid"),
        ("SULFAMETHOXAZOL", "sulfamethoxazole"),
        ("COLISTIMETHAT", "colistimethate"),
        ("VALPROATE", "valproic_acid"),
        ("ACIDVALPROIC", "valproic_acid"),
        ("INSULIN_GLARGIN", "insulin_glargine"),
        ("ENOXAPARIN", "enoxaparin"),
        ("HEPARIN", "heparin"),
        ("TRIMETHOPRIM", "trimethoprim"),
        ("NEW-INGREDIENT", "new_ingredient"),
    ],
)
def test_explicit_ingredient_aliases(source: str, expected: str) -> None:
    assert normalize_ingredient("HC-" + source) == expected
    assert normalize_ingredient(expected) == expected


def test_encounter_fields_and_new_clinical_metadata_are_preserved(batch: Batch) -> None:
    encounters = {row["dot_dieu_tri_id"]: row for row in batch.rows["nghiep_vu.dot_dieu_tri"]}
    diagnoses = {row["chan_doan_id"]: row for row in batch.rows["nghiep_vu.chan_doan"]}
    for _, case in read_cases(ROOT):
        if "ho_so_id" not in case:
            continue
        for raw in case["dot_dieu_tri"]:
            row = encounters[raw["dot_dieu_tri_id"]]
            for key in TABLES["nghiep_vu.dot_dieu_tri"].columns:
                if key in raw and key not in ("thoi_diem_bat_dau", "thoi_diem_ket_thuc", "co_dia"):
                    assert row[key] == raw[key]
            for diagnosis in raw["chan_doan"]:
                from datetime import datetime

                assert datetime.fromisoformat(
                    diagnoses[diagnosis["chan_doan_id"]]["thoi_diem"]
                ) == (datetime.fromisoformat(raw["thoi_diem_bat_dau"]))
    # Các trường chưa có trong dữ liệu thật vẫn phải chuyển được, không bịa mặc định.
    row = TABLES["nghiep_vu.dien_bien"].convert(
        {
            "dien_bien_id": "DB-TEST",
            "loai_ho_so": "ghi_chu",
            "noi_dung": "Giả lập",
            "thoi_diem_ghi": "2026-11-12T08:00:00+07:00",
            "dot_dieu_tri_id": "DT-TEST",
            "nguoi_ghi_vai_tro": "bac_si_truc",
        },
        "test",
    )
    assert row["nguoi_ghi_vai_tro"] == "bac_si_truc"


def test_demo_background_order_only_exists_when_needed() -> None:
    path, original = read_cases(ROOT)[0]
    case = copy.deepcopy(original)
    active = copy.deepcopy(case["y_lenh_cho_duyet"]["chi_tiet"][0])
    active["chi_tiet_y_lenh_id"] = "CT-DEMO-NEN-01"
    active["bat_dau"] = "2026-11-09T10:00:00+07:00"
    active["lich_dung"] = []
    earlier = {
        **active,
        "chi_tiet_y_lenh_id": "CT-DEMO-NEN-02",
        "bat_dau": "2026-11-09T09:00:00+07:00",
    }
    case["thuoc_dang_dung"] = [active, earlier]
    with patch("app.db.sources.read_cases", return_value=[(path, case)]):
        batch = prepare_cases(ROOT)
    assert not batch.rejected and not batch.orphans()
    orders = batch.rows["nghiep_vu.y_lenh"]
    background = next(row for row in orders if row["ca_id"] is None)
    assert background["y_lenh_id"] == "YL-DEMO-01-NEN"
    assert background["trang_thai"] == "dang_thuc_hien"
    assert background["thoi_diem_ke"] == "2026-11-09T09:00:00+07:00"
    assert all(row["y_lenh_id"] for row in batch.rows["nghiep_vu.chi_tiet_y_lenh"])
    assert expected_counts([batch])[ACTIVE_DRUG_VIEW] == 2
    with patch("app.db.sources.read_cases", return_value=[(path, original)]):
        empty = prepare_cases(ROOT)
    assert len(empty.rows["nghiep_vu.y_lenh"]) == 1
    assert expected_counts([empty])[ACTIVE_DRUG_VIEW] == 0


@pytest.mark.parametrize("changed", ["ten_thuoc", "ham_luong", "thanh_phan"])
def test_conflicting_drug_never_overwrites_or_merges_components(changed: str) -> None:
    drug = copy.deepcopy(read_cases(ROOT)[0][1]["danh_muc_thuoc"][0])
    batch = Batch()
    add_drug(batch, drug, "first.json")
    original_rows = copy.deepcopy(batch.rows)
    later = copy.deepcopy(drug)
    if changed == "thanh_phan":
        later[changed].append({"hoat_chat_id": "HC-GABAPENTIN"})
    else:
        later[changed] = "Khác bản đầu"
    add_drug(batch, later, "later.json")
    assert batch.rows == original_rows
    assert len(batch.rejected) == 1
    assert json.loads(batch.rejected[0].dong) == later


def test_schema_has_new_constraints_and_view_without_legacy_flags() -> None:
    schema = (ROOT / "db/schema.sql").read_text(encoding="utf-8")
    blocks = dict(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+\.\w+) \(\n(.*?)\n\);", schema, re.S))
    assert "ca_id" not in blocks["nghiep_vu.dot_dieu_tri"]
    assert "mo_ta_ngan" not in blocks["nghiep_vu.dot_dieu_tri"]
    assert "UNIQUE (nguoi_benh_id, thu_tu)" in blocks["nghiep_vu.dot_dieu_tri"]
    assert "ca_id text UNIQUE" in blocks["nghiep_vu.y_lenh"]
    assert "DEFERRABLE INITIALLY DEFERRED" in blocks["nghiep_vu.y_lenh"]
    assert "thuoc_dang_dung" not in blocks["nghiep_vu.chi_tiet_y_lenh"]
    assert "y_lenh_id text NOT NULL" in blocks["nghiep_vu.chi_tiet_y_lenh"]
    assert (
        "FOREIGN KEY (y_lenh_id, ca_id) REFERENCES nghiep_vu.y_lenh(y_lenh_id, ca_id)"
        in (blocks["nghiep_vu.lan_tham_dinh"])
    )
    assert "REFERENCES nghiep_vu.y_lenh(ca_id)" in blocks["nghiep_vu.phan_hoi"]
    assert "security_invoker = true" in schema
    assert "REVOKE ALL ON nghiep_vu.v_thuoc_dang_dung FROM PUBLIC;" in schema
    assert "REVOKE ALL ON nghiep_vu.v_thuoc_dang_dung FROM anon" in schema
    assert "REVOKE ALL ON nghiep_vu.v_thuoc_dang_dung FROM authenticated" in schema
    assert "ct.trang_thai_dong = 'active'" in schema
    assert "yl.trang_thai IN ('da_duyet', 'dang_thuc_hien')" in schema


def test_in_memory_composite_fk_rejects_review_of_wrong_order(batch: Batch) -> None:
    invalid = copy.deepcopy(batch)
    reviews = invalid.rows["nghiep_vu.lan_tham_dinh"]
    reviews[0]["y_lenh_id"] = reviews[1]["y_lenh_id"]
    assert any("lan_tham_dinh" in error for error in invalid.orphans())


def test_replacement_chain_orphans_are_removed_until_stable(batch: Batch) -> None:
    invalid = copy.deepcopy(batch)
    orders = invalid.rows["nghiep_vu.y_lenh"]
    orders[0]["thay_the_y_lenh_id"] = "YL-THIEU"
    orders[1]["thay_the_y_lenh_id"] = orders[0]["y_lenh_id"]
    invalid.reject_orphans()
    assert invalid.orphans() == []
    assert not {orders[0]["y_lenh_id"], orders[1]["y_lenh_id"]} & {
        row["y_lenh_id"] for row in invalid.rows["nghiep_vu.y_lenh"]
    }


def test_read_cases_ignores_private_json_and_non_json_files(tmp_path: Path) -> None:
    for directory in ("demo", "hoso_gia_lap"):
        folder = tmp_path / "data/mock" / directory
        folder.mkdir(parents=True)
        (folder / "case.json").write_text("{}", encoding="utf-8")
        (folder / "_kich_ban.json").write_text("không phải JSON", encoding="utf-8")
        (folder / "BANG_TRA.md").write_text("bảng tra", encoding="utf-8")
    assert len(read_cases(tmp_path)) == 2
