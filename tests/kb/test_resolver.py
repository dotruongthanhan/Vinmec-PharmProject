"""Kiểm tra phân giải và dựng lại chỉ mục từ bộ dữ liệu thu nhỏ."""

import csv
import hashlib
import json
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from app.domain.models import CaBenh, HoatChat, ThanhPhan
from app.kb.resolver import DrugResolver
from app.kb.resolver.build import (
    CASE_CSV,
    DDINTER_CSV,
    DDINTER_PATH,
    DICTIONARY_DIR,
    INDEX_PATH,
    REPORT_DIR,
    build_index,
)
from app.kb.resolver.report import report

FIXTURE = Path(__file__).parent / "fixtures/resolver"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / DICTIONARY_DIR).mkdir(parents=True)
    for name in ("hoat_chat", "dong_nghia", "thuoc", "thuoc_thanh_phan"):
        file = f"{name}.jsonl"
        shutil.copyfile(FIXTURE / file, tmp_path / DICTIONARY_DIR / file)
    (tmp_path / DDINTER_PATH.parent).mkdir(parents=True)
    shutil.copyfile(FIXTURE / "ddinter.jsonl", tmp_path / DDINTER_PATH)
    for folder in ("demo", "hoso_gia_lap"):
        dest = tmp_path / "data/mock" / folder
        dest.mkdir(parents=True)
        data = json.loads((FIXTURE / "ca.json").read_text(encoding="utf-8"))
        data["ca_id"] += f"-{folder}"
        (dest / "ca.json").write_text(json.dumps(data), encoding="utf-8")
    build_index(tmp_path)
    return tmp_path


@pytest.fixture
def resolver(root: Path) -> DrugResolver:
    return DrugResolver.from_index(root / INDEX_PATH)


@pytest.fixture
def case() -> CaBenh:
    return CaBenh.model_validate_json((FIXTURE / "ca.json").read_bytes())


def test_catalog_precedes_free_text(resolver: DrugResolver, case: CaBenh) -> None:
    result = resolver.resolve_line(case, case.y_lenh_cho_duyet.chi_tiet[0])
    assert result.trang_thai == "da_phan_giai"
    assert result.nguon_khop == "danh_muc_ca"
    (component,) = result.thanh_phan
    assert (component.ma_ca, component.hoat_chat_id) == ("HC-MAU", "acetaminophen")
    assert (component.ham_luong, component.don_vi) == (500.0, "mg")
    assert component.ddinter_id == "D1"
    assert component.ma_atc == ["N02BE"]


def test_live_case_mapping_has_same_rules(resolver: DrugResolver, case: CaBenh) -> None:
    case.danh_muc_hoat_chat = [
        HoatChat(
            hoat_chat_id="HC-DB", ten_hoat_chat="Tên thương mại", ten_quoc_te="Metoprolol tartrat"
        ),
        HoatChat(hoat_chat_id="HC-VIET-DB", ten_hoat_chat="Amoxicilin"),
        HoatChat(hoat_chat_id="trimethoprim", ten_hoat_chat="Trimethoprim"),
    ]
    case.danh_muc_thuoc[0].thanh_phan = [
        ThanhPhan(hoat_chat_id=row.hoat_chat_id) for row in case.danh_muc_hoat_chat
    ]
    result = resolver.resolve_line(case, case.y_lenh_cho_duyet.chi_tiet[0])
    assert result.trang_thai == "da_phan_giai"
    assert [(c.hoat_chat_id, c.ma_ca) for c in result.thanh_phan] == [
        ("metoprolol", "HC-DB"),
        ("amoxicillin", "HC-VIET-DB"),
        ("trimethoprim", None),
    ]
    assert result.thanh_phan[0].loai == "loai_moi_t52"
    assert "dang_muoi: HC-DB → metoprolol" in result.canh_bao
    assert "Thiếu ddinter_id đã xác nhận cho metoprolol" in result.canh_bao


def test_partial_case_does_not_guess_from_global_code(resolver: DrugResolver, case: CaBenh) -> None:
    case.danh_muc_hoat_chat[0].ten_quoc_te = "Acetaminophenn"
    case.danh_muc_thuoc[0].thanh_phan.append(ThanhPhan(hoat_chat_id="HC-VIET"))
    result = resolver.resolve_line(case, case.y_lenh_cho_duyet.chi_tiet[0])
    assert result.trang_thai == "mot_phan"
    assert [row.hoat_chat_id for row in result.thanh_phan] == ["amoxicillin"]
    assert result.ly_do and "HC-MAU" in result.ly_do and "ten_quoc_te" in result.ly_do


@pytest.mark.parametrize(
    ("name", "expected", "source"),
    [
        ("Augmentin", ["amoxicillin", "clavulanic_acid"], "ten_thuoc_dav"),
        (
            "Amoxicilin + acid clavulanic 875 mg/125 mg",
            ["amoxicillin", "clavulanic_acid"],
            "tach_phoi_hop",
        ),
        (
            "Amoxicilin 875 mg/acid clavulanic và trimethoprim",
            ["amoxicillin", "clavulanic_acid", "trimethoprim"],
            "tach_phoi_hop",
        ),
        ("Cotrimoxazol 800/160 mg", ["sulfamethoxazole", "trimethoprim"], "tach_phoi_hop"),
    ],
)
def test_combinations(resolver: DrugResolver, name: str, expected: list[str], source: str) -> None:
    result = resolver.resolve_name(name)
    assert result.trang_thai == "da_phan_giai"
    assert result.nguon_khop == source
    assert [row.hoat_chat_id for row in result.thanh_phan] == expected
    if source == "ten_thuoc_dav":
        first, second = result.thanh_phan
        assert (first.ham_luong, first.don_vi) == (None, None)
        assert (second.ham_luong, second.don_vi) == (125, "mg")
        assert any("DAV" in warning for warning in result.canh_bao)


def test_conflicting_product_does_not_fall_back_to_synonym(resolver: DrugResolver) -> None:
    result = resolver.resolve_name("Tên trùng công thức 10 mg")
    assert result.trang_thai == "khong_nhan_dien"
    assert result.nguon_khop == "ten_thuoc_dav"
    assert result.ly_do == "tên ứng với nhiều công thức"
    assert not result.thanh_phan


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Natri clorid 0,9% 500 mL", "sodium_chloride"),
        ("Tên mẫu", "sodium_chloride"),
        ("Cao mẫu", "cao_mau"),
    ],
)
def test_non_applicable_keeps_ingredient(resolver: DrugResolver, name: str, expected: str) -> None:
    result = resolver.resolve_name(name)
    assert result.trang_thai == "khong_ap_dung"
    (component,) = result.thanh_phan
    assert component.hoat_chat_id == expected
    assert component.ham_luong is None


def test_unknown_and_partial_combination(resolver: DrugResolver) -> None:
    result = resolver.resolve_name("Amoxicilinn 10 mg")
    assert result.trang_thai == "khong_nhan_dien"
    assert result.ly_do
    assert not result.thanh_phan
    partial = resolver.resolve_name("Amoxicilin; thành phần XYZ")
    assert partial.trang_thai == "mot_phan"
    assert partial.ly_do and "XYZ" in partial.ly_do
    assert [row.hoat_chat_id for row in partial.thanh_phan] == ["amoxicillin"]


def test_line_type_does_not_hide_identified_drug(resolver: DrugResolver, case: CaBenh) -> None:
    line = case.y_lenh_cho_duyet.chi_tiet[0]
    line.thuoc_id = None
    line.loai_san_pham = "khac"
    line.ten_tu_do = "Đo đường huyết trước bữa và trước ngủ"
    assert resolver.resolve_line(case, line).trang_thai == "khong_ap_dung"
    line.ten_tu_do = "Amoxicilin 500 mg"
    assert resolver.resolve_line(case, line).trang_thai == "da_phan_giai"


def test_ddinter_blocks_both_conflict_directions_and_atc_only(root: Path) -> None:
    with closing(sqlite3.connect(root / INDEX_PATH)) as db:
        links = dict(db.execute("SELECT hoat_chat_id, ddinter_id FROM hoat_chat"))
    assert {key: value for key, value in links.items() if value is not None} == {
        "acetaminophen": "D1",
        "calcium_gluconate": "D4",
        "sodium_chloride": "D10",
        "sulfamethoxazole": "D9",
    }
    with (root / REPORT_DIR / DDINTER_CSV).open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    by_dd = {row["ddinter_id"]: row for row in rows if row["phia"] == "ddinter"}
    by_axis = {row["hoat_chat_id"]: row for row in rows if row["phia"] == "truc"}
    assert by_dd["D7"]["ung_vien_xung_dot"] == "metoprolol | valproic_acid"
    assert by_axis["penicillin_g"]["ung_vien_xung_dot"] == "D2 | D3"
    assert by_dd["D6"]["goi_y_atc"] == "amoxicillin"
    assert not by_dd["D5"]["hoat_chat_id"]


def test_build_reproducible_and_lookup_works_without_sources(root: Path) -> None:
    paths = [root / INDEX_PATH, root / REPORT_DIR / CASE_CSV, root / REPORT_DIR / DDINTER_CSV]
    before = [path.read_bytes() for path in paths]
    build_index(root)
    assert [path.read_bytes() for path in paths] == before
    with closing(sqlite3.connect(root / INDEX_PATH)) as db:
        codes = dict(db.execute("SELECT ma_ca, cach_khop FROM chuyen_ma_ca"))
        (sha256_json,) = db.execute("SELECT sha256_json FROM meta").fetchone()
    assert codes == {"HC-MAU": "ten_quoc_te", "HC-MUOI": "dang_muoi", "HC-VIET": "ten_viet"}
    checksums = json.loads(sha256_json)
    assert (
        checksums[DDINTER_PATH.as_posix()]
        == hashlib.sha256((root / DDINTER_PATH).read_bytes()).hexdigest()
    )
    shutil.rmtree(root / DICTIONARY_DIR)
    resolver = DrugResolver.from_index(root / INDEX_PATH)
    assert resolver.resolve_name("Amoxicilin").trang_thai == "da_phan_giai"
    assert report(root)["so_dong_du_ddinter_id"] == 2


def test_failed_rebuild_keeps_previous_index(root: Path) -> None:
    before = (root / INDEX_PATH).read_bytes()
    (root / DICTIONARY_DIR / "thuoc.jsonl").write_text("{}", encoding="utf-8")
    with pytest.raises(KeyError, match="ten_thuoc"):
        build_index(root)
    assert (root / INDEX_PATH).read_bytes() == before
    assert list((root / INDEX_PATH).parent.iterdir()) == [root / INDEX_PATH]
