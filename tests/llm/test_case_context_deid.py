"""Kiểm thử T48: che theo trường, gửi tối thiểu, mã bản ghi tạm và khôi phục ở bước tổng hợp."""

import re
import unicodedata
from pathlib import Path

import pytest

from app.container import build_container
from app.db.reader import load_source_cases
from app.db.sources import read_cases
from app.deid.known import IdentifierLookupError
from app.domain.models import CaBenh, DienBien
from app.llm.case_context import build_case_bundle, build_case_context
from app.llm.synthesizer import Synthesizer
from app.pipeline import run_case
from app.providers.fakes import FakeLLM
from tests.deid_support import temp_id

ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = ROOT / "config/prompts/tong_hop.v1.md"


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.category(ch).startswith("M"))
    return stripped.replace("đ", "d").replace("Đ", "D").casefold()


def _forbidden_values(raw: dict) -> list[str]:
    """Mọi giá trị hành chính của tệp nguồn, đọc độc lập với mã nguồn che."""
    admin = raw["hanh_chinh"]
    contact = admin.get("nguoi_bao_tin") or {}
    values = [admin["ho_ten"], contact.get("ho_ten"), (admin.get("bhyt") or {}).get("so_the")]
    phone = contact.get("dien_thoai") or ""
    values += [phone, phone.replace(" ", "")]
    year, month, day = admin["ngay_sinh"].split("-")
    values += [admin["ngay_sinh"], f"{day}/{month}/{year}", f"{int(day)}/{int(month)}/{year}"]
    address = admin.get("dia_chi") or {}
    values += [address.get(key) for key in ("thon_pho", "xa_phuong", "huyen")]
    values += [", ".join(address[key] for key in address if address[key])]
    for parent in (admin.get("bo_me") or {}).values():
        values.append((parent or {}).get("ho_ten"))
    patient = raw["nguoi_benh"]["nguoi_benh_id"]
    values += [patient, raw.get("ca_id") or raw["ho_so_id"]]
    stays = raw["dot_dieu_tri"]
    for stay in stays if isinstance(stays, list) else [stays]:
        management = stay.get("quan_ly") or {}
        values += [management.get("so_luu_tru"), management.get("ma_yt")]
        values.append(stay.get("dot_dieu_tri_id"))
    return [value for value in values if value]


def _raw_by_case() -> dict[str, dict]:
    return {raw.get("ca_id") or raw["ho_so_id"]: raw for _path, raw in read_cases(ROOT)}


def _all_cases() -> list[CaBenh]:
    return load_source_cases(ROOT)


def test_no_administrative_value_reaches_the_prompt_for_every_mock_case() -> None:
    container = build_container("test")
    raws = _raw_by_case()
    cases = _all_cases()
    assert len(cases) >= 66

    for case in cases:
        bundle = build_case_bundle(
            case, run_case(case, container.renal_rules), container.settings.case_context
        )
        text = bundle.goi.van_ban_ca
        folded_text = _fold(text)
        assert bundle.warnings == [], case.ca_id
        for value in _forbidden_values(raws[case.ca_id]):
            assert value not in text, (case.ca_id, "chuỗi gốc")
            assert _fold(value) not in folded_text, (case.ca_id, "biến thể không dấu")
        assert all(re.fullmatch(r"R\d+", item) for item in bundle.goi.ban_ghi_ids), case.ca_id
        assert all(re.fullmatch(r"R\d+", item) for item in bundle.goi.dong_y_lenh_ids), case.ca_id


def test_prompt_contains_only_age_and_sex_as_demographics() -> None:
    container = build_container("test")
    case = container.case_repo.get("DEMO-02")
    goi, _ = build_case_context(
        case, run_case(case, container.renal_rules), container.settings.case_context
    )

    assert "- Tuổi: 75 | Giới: Nữ |" in goi.van_ban_ca
    for field in ("ho_ten", "ngay_sinh", "dia_chi", "dien_thoai", "so_the", "bhyt", "cccd"):
        assert field not in goi.van_ban_ca.casefold()
    for code in (case.nguoi_benh.nguoi_benh_id, case.ca_id, case.dot_dieu_tri.dot_dieu_tri_id):
        assert code not in goi.van_ban_ca
    assert not re.search(r"[A-Z]{2,}-[A-Z0-9]+-\d+", goi.van_ban_ca.replace("DU_LIEU_BENH_AN", ""))


def _with_free_text(case: CaBenh, text: str) -> CaBenh:
    note = DienBien(
        dien_bien_id="DB-T48-01",
        loai_ho_so="Phiếu điều trị",
        noi_dung=text,
        thoi_diem_ghi=case.dien_bien[0].thoi_diem_ghi if case.dien_bien else None,
    )
    line = case.y_lenh_cho_duyet.chi_tiet[0].model_copy(update={"cach_dung": text})
    order = case.y_lenh_cho_duyet.model_copy(update={"chi_tiet": [line]})
    return case.model_copy(update={"dien_bien": [note], "y_lenh_cho_duyet": order})


@pytest.mark.parametrize("case_id", ["DEMO-02", "HS-001", "HS-030"])
def test_layer1_masks_injected_patient_values_in_free_text(case_id: str) -> None:
    container = build_container("test")
    case = next(item for item in _all_cases() if item.ca_id == case_id)
    raw = _raw_by_case()[case_id]
    admin = raw["hanh_chinh"]
    name = admin["ho_ten"]
    year, month, day = admin["ngay_sinh"].split("-")
    street = admin["dia_chi"]["thon_pho"]
    text = (
        f"{name} vào viện. NGUYEN {name.split()[1].upper()} nói đau. "
        f"Sinh {day}/{month}/{year} (còn ghi {admin['ngay_sinh']}). "
        f"Ở {admin['dia_chi']['so_nha']} {street}. "
        f"Gọi {admin['nguoi_bao_tin']['dien_thoai'].replace(' ', '')} "
        f"thẻ {admin['bhyt']['so_the']} mã {case_id}."
    )
    injected = _with_free_text(case, text)

    bundle = build_case_bundle(
        injected, run_case(injected, container.renal_rules), container.settings.case_context
    )

    prompt = bundle.goi.van_ban_ca
    folded = _fold(prompt)
    for secret in (
        name,
        f"{day}/{month}/{year}",
        admin["ngay_sinh"],
        street,
        admin["nguoi_bao_tin"]["dien_thoai"].replace(" ", ""),
        admin["bhyt"]["so_the"],
        case_id,
    ):
        assert secret not in prompt
        assert _fold(secret) not in folded
    assert bundle.deid.anh_xa["[TEN_1]"] == name
    assert bundle.khoi_phuc_van_ban("Người bệnh [TEN_1]") == f"Người bệnh {name}"


def test_lookup_failure_fails_closed_with_warning_and_still_masks_patterns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = build_container("test")
    case = container.case_repo.get("DEMO-02")

    def fail(_case: CaBenh) -> list:
        raise IdentifierLookupError("không đọc được")

    monkeypatch.setattr("app.llm.case_context.known_identifiers", fail)
    injected = _with_free_text(
        case, "người nhà Lê Văn Hùng, sđt 0912 345 678, mã DEMO-02, 2026-11-06."
    )

    bundle = build_case_bundle(
        injected, run_case(injected, container.renal_rules), container.settings.case_context
    )

    assert any("Không lấy được định danh" in item for item in bundle.warnings)
    prompt = bundle.goi.van_ban_ca
    for leaked in ("Lê Văn Hùng", "0912 345 678", "DEMO-02", "2026-11-06"):
        assert leaked not in prompt


def test_record_id_map_round_trip_and_unknown_codes_are_kept() -> None:
    container = build_container("test")
    case = container.case_repo.get("DEMO-02")
    bundle = build_case_bundle(
        case, run_case(case, container.renal_rules), container.settings.case_context
    )
    lab = temp_id("DEMO-02", "XN-DEMO02-01")

    assert bundle.ma_ban_ghi.that(lab) == "XN-DEMO02-01"
    assert bundle.ma_ban_ghi.that("R999") == "R999"
    assert bundle.khoi_phuc_van_ban(f"Xem [{lab}] và R999") == "Xem [XN-DEMO02-01] và R999"
    assert bundle.ma_ban_ghi.doi_van_ban_sang_tam("Xem XN-DEMO02-01.") == f"Xem {lab}."


def _synthesizer(llm: FakeLLM) -> Synthesizer:
    container = build_container("test")
    return Synthesizer(
        llm=llm,
        prompt_path=PROMPT_PATH,
        case_settings=container.settings.case_context,
        evidence_max_chars=12000,
        max_synthesis_attempts=2,
        model_name="model-test",
    )


def test_synthesizer_verifies_on_temp_ids_then_restores_real_ids_and_identity() -> None:
    container = build_container("test")
    case = container.case_repo.get("DEMO-02")
    admin_name = _raw_by_case()["DEMO-02"]["hanh_chinh"]["ho_ten"]
    injected = _with_free_text(case, f"{admin_name} sốt nhẹ, creatinin tăng.")
    ket_qua = run_case(injected, container.renal_rules)
    proposal = {
        "chi_tiet_y_lenh_id": [temp_id("DEMO-02", "CT-DEMO02-01")],
        "yeu_to": 5,
        "ket_luan": "can_xem",
        "muc_do": "can_luu_y",
        "nhan_xet": "[TEN_1] có creatinin 212 umol/L, xem [R2] và [R999].",
        "ban_ghi_ids": [temp_id("DEMO-02", "XN-DEMO02-01")],
        "trich_dan": [],
        "thong_tin_con_thieu": [],
        "de_xuat": None,
        "bo_sung_cho_ma_luat": None,
    }
    llm = FakeLLM([{"nhan_dinh": [proposal]}])

    result = _synthesizer(llm).run(injected, ket_qua, [])

    sent = "\n".join(message.content for call in llm.calls for message in call["messages"])
    assert admin_name not in sent
    assert "XN-DEMO02-01" not in sent and "CT-DEMO02-01" not in sent
    assert result.trang_thai == "ok"
    verified = [item for item in result.nhan_dinh if item.nguon_goc == "ai_da_kiem_chung"]
    assert len(verified) == 1
    proposal_out = verified[0].de_xuat
    assert proposal_out is not None
    assert proposal_out.ban_ghi_ids == ["XN-DEMO02-01"]
    assert proposal_out.chi_tiet_y_lenh_id == ["CT-DEMO02-01"]
    assert proposal_out.nhan_xet.startswith(f"{admin_name} có creatinin 212 umol/L")
    assert "[R999]" in proposal_out.nhan_xet
    assert not any(admin_name in warning for warning in result.canh_bao)


def test_synthesizer_rejects_real_record_ids_because_llm_only_sees_temp_ids() -> None:
    container = build_container("test")
    case = container.case_repo.get("DEMO-02")
    ket_qua = run_case(case, container.renal_rules)
    proposal = {
        "chi_tiet_y_lenh_id": ["CT-DEMO02-01"],
        "yeu_to": 5,
        "ket_luan": "can_xem",
        "muc_do": "can_luu_y",
        "nhan_xet": "Creatinin 212 umol/L.",
        "ban_ghi_ids": ["XN-DEMO02-01"],
        "trich_dan": [],
        "thong_tin_con_thieu": [],
        "de_xuat": None,
        "bo_sung_cho_ma_luat": None,
    }
    llm = FakeLLM([{"nhan_dinh": [proposal]}, {"nhan_dinh": [proposal]}])

    result = _synthesizer(llm).run(case, ket_qua, [])

    unverified = [item for item in result.nhan_dinh if item.nguon_goc == "ai_chua_kiem_chung"]
    assert len(unverified) == 1
    assert "ma_ban_ghi_la" in unverified[0].loi_kiem_chung
