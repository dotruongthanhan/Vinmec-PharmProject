"""Kiểm thử nguồn định danh đã biết của T48: chế độ tệp, chế độ DB (giả lập) và đóng an toàn."""

import json
from pathlib import Path

import pytest

from app.deid.known import (
    IdentifierLookupError,
    base_identifiers,
    identifiers_from_administrative,
    known_identifiers,
)
from app.domain.loader import load_case

ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = ROOT / "data/mock/demo"


def _pairs(items: list) -> set[tuple[str, str]]:
    return {(item.loai, item.gia_tri) for item in items}


def test_base_identifiers_always_include_patient_case_and_encounter_codes() -> None:
    case = load_case(DEMO_DIR / "DEMO-02.json")

    assert _pairs(base_identifiers(case)) == {
        ("MA", "NB-DEMO-02"),
        ("MA", "DEMO-02"),
        ("MA", "DT-DEMO-02"),
    }


def test_file_mode_reads_administrative_block_of_the_same_case() -> None:
    case = load_case(DEMO_DIR / "DEMO-02.json")
    raw = json.loads((DEMO_DIR / "DEMO-02.json").read_text(encoding="utf-8"))
    admin = raw["hanh_chinh"]

    found = _pairs(known_identifiers(case, source="file", case_dirs=[DEMO_DIR]))

    assert ("TEN", admin["ho_ten"]) in found
    assert ("NGAY", admin["ngay_sinh"]) in found
    assert ("SDT", admin["nguoi_bao_tin"]["dien_thoai"]) in found
    assert ("BHYT", admin["bhyt"]["so_the"]) in found
    assert ("MA", "NB-DEMO-02") in found
    assert ("MA", raw["dot_dieu_tri"]["quan_ly"]["so_luu_tru"]) in found
    assert any(loai == "DIACHI" and admin["dia_chi"]["thon_pho"] in value for loai, value in found)
    # Số nhà thuần chữ số không được che riêng vì sẽ nuốt số liệu lâm sàng.
    assert ("DIACHI", admin["dia_chi"]["so_nha"]) not in found


def test_file_mode_finds_synthetic_record_files_of_other_folder() -> None:
    from app.db.reader import load_source_cases

    case = next(item for item in load_source_cases(ROOT) if item.ca_id == "HS-001")

    found = _pairs(known_identifiers(case, source="file"))

    assert ("TEN", "Nguyễn Văn 1") in found
    assert ("MA", "HS-001") in found


def test_file_mode_fails_closed_when_record_missing_or_mismatched(tmp_path: Path) -> None:
    case = load_case(DEMO_DIR / "DEMO-02.json")

    with pytest.raises(IdentifierLookupError):
        known_identifiers(case, source="file", case_dirs=[tmp_path])

    raw = json.loads((DEMO_DIR / "DEMO-02.json").read_text(encoding="utf-8"))
    raw["nguoi_benh"]["nguoi_benh_id"] = "NB-KHAC"
    (tmp_path / "DEMO-02.json").write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(IdentifierLookupError):
        known_identifiers(case, source="file", case_dirs=[tmp_path])


def test_file_mode_does_not_build_paths_from_unsafe_case_ids(tmp_path: Path) -> None:
    case = load_case(DEMO_DIR / "DEMO-02.json").model_copy(update={"ca_id": "../DEMO-02"})

    with pytest.raises(IdentifierLookupError):
        known_identifiers(case, source="file", case_dirs=[DEMO_DIR])


def test_database_mode_uses_injected_reader_without_caching() -> None:
    from app.api import schemas as s

    case = load_case(DEMO_DIR / "DEMO-02.json")
    calls: list[list[str]] = []

    def reader(patient_ids: list[str]) -> dict:
        calls.append(list(patient_ids))
        return {
            patient_ids[0]: s.AdministrativeRecord(
                dinh_danh_day_du=s.FullIdentity(
                    ho_ten="Trần Thị Ngọc Hà",
                    dia_chi=s.Address(so_nha="12A", thon_pho="Ngõ 5 Láng Hạ", tinh_thanh="Hà Nội"),
                ),
                lich_su_vao_vien=[
                    s.EncounterHistory(dot_dieu_tri_id="DT-X", so_luu_tru="LT-9", ma_yt="YT-9")
                ],
            )
        }

    first = _pairs(known_identifiers(case, source="db", administrative_reader=reader))
    known_identifiers(case, source="db", administrative_reader=reader)

    assert calls == [["NB-DEMO-02"], ["NB-DEMO-02"]]
    assert ("TEN", "Trần Thị Ngọc Hà") in first
    assert ("MA", "LT-9") in first and ("MA", "YT-9") in first
    assert ("DIACHI", "12A Ngõ 5 Láng Hạ") in first
    assert ("MA", "NB-DEMO-02") in first


def test_database_mode_fails_closed_without_leaking_exception_text() -> None:
    case = load_case(DEMO_DIR / "DEMO-02.json")

    def broken(_ids: list[str]) -> dict:
        raise RuntimeError("Nguyễn Văn Bí Mật 0912345678")

    with pytest.raises(IdentifierLookupError) as caught:
        known_identifiers(case, source="db", administrative_reader=broken)
    assert "Bí Mật" not in str(caught.value)
    assert "0912345678" not in str(caught.value)

    with pytest.raises(IdentifierLookupError):
        known_identifiers(case, source="db", administrative_reader=lambda _ids: {})


def test_identifiers_from_administrative_handles_missing_blocks() -> None:
    assert identifiers_from_administrative(None) == []
    assert identifiers_from_administrative({"ho_ten": "  "}) == []
