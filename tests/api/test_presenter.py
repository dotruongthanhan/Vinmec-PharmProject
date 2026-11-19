"""Kiểm thử hàm trình bày không làm đổi dữ liệu đầu vào."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.domain.loader import load_case
from app.feedback import PhanHoi
from app.pipeline import run_case
from app.rules import load_renal_rules

ROOT = Path(__file__).resolve().parents[2]


def test_presenter_is_pure_and_uses_latest_feedback() -> None:
    from app.api.presenter import present_case, present_queue, present_record

    case = load_case(ROOT / "data/mock/demo/DEMO-02.json")
    result = run_case(case, load_renal_rules(ROOT / "data/kb/quy_tac_lieu_than.json"))
    finding = result.phat_hien[0]
    feedback = PhanHoi(
        thoi_diem=datetime(2026, 11, 16, tzinfo=UTC),
        ca_id=case.ca_id,
        ma_luat=finding.ma_luat,
        yeu_to=finding.yeu_to,
        chi_tiet_y_lenh_id=finding.chi_tiet_y_lenh_id,
        phan_hoi="bac_bo",
        nhom_ly_do="khac",
        ly_do="Đã xem",
    )
    newer = feedback.model_copy(
        update={"thoi_diem": datetime(2026, 11, 17, tzinfo=UTC), "phan_hoi": "dong_y"}
    )
    before = (case.model_dump_json(), result.model_dump_json())
    body = present_case(case, result, [newer, feedback])
    assert body.nhan_dinh.can_chu_y[0].phan_hoi.phan_hoi == "dong_y"
    assert body.nhan_dinh.can_chu_y[0].phan_hoi.thoi_diem_text == "17/11/2026 07:00"
    assert newer.thoi_diem.tzinfo is UTC
    assert body.nhan_dinh.can_chu_y[0].dien_giai_ai is None
    assert body.nhan_dinh.can_chu_y[0].de_xuat_ai is None
    assert body.nhan_dinh.can_chu_y[0].trich_dan == []
    assert present_queue([case], {case.ca_id: result}, [newer, feedback])[0].da_phan_hoi_het
    assert present_record(case, "XN-DEMO02-01").loai == "Xét nghiệm"
    assert present_record(case, "LA") is None
    assert before == (case.model_dump_json(), result.model_dump_json())


def test_unknown_calculation_evidence_cannot_open() -> None:
    from app.api.presenter import present_case
    from app.rules.types import CanCu

    case = load_case(ROOT / "data/mock/demo/DEMO-02.json")
    result = run_case(case, load_renal_rules(ROOT / "data/kb/quy_tac_lieu_than.json"))
    finding = result.phat_hien[0].model_copy(
        update={"ma_luat": "LA", "can_cu": [CanCu(loai="tinh_toan", mo_ta="Chưa xác định")]}
    )
    result = result.model_copy(update={"phat_hien": [finding]})
    evidence = present_case(case, result, []).nhan_dinh.can_chu_y[0].can_cu[0]
    assert evidence.cong_thuc is None
    assert evidence.mo_duoc is False


def test_finding_ids_preserves_legacy_id_and_disambiguates_stably() -> None:
    from app.api.presenter import finding_id, finding_ids

    case = load_case(ROOT / "data/mock/demo/DEMO-02.json")
    result = run_case(case, load_renal_rules(ROOT / "data/kb/quy_tac_lieu_than.json"))
    template = result.phat_hien[0]
    line_id = template.chi_tiet_y_lenh_id[0]
    first = template.model_copy(
        update={
            "ma_luat": "lieu_toi_da_khong_co_nguon",
            "chi_tiet_y_lenh_id": [line_id],
            "mo_ta": "Không thấy liều tối đa cho sulfamethoxazole.",
        }
    )
    second = template.model_copy(
        update={
            "ma_luat": "lieu_toi_da_khong_co_nguon",
            "chi_tiet_y_lenh_id": [line_id],
            "mo_ta": "Không thấy liều tối đa cho trimethoprim.",
        }
    )
    unique = template.model_copy(update={"ma_luat": "khac", "chi_tiet_y_lenh_id": [line_id]})

    forward = finding_ids([first, second, unique])
    reversed_ids = finding_ids([second, first, unique])
    assert len(set(forward)) == 3
    assert forward[2] == finding_id(unique) == f"khac|{line_id}"
    assert forward[0].startswith(f"lieu_toi_da_khong_co_nguon|{line_id}|")
    assert forward[1].startswith(f"lieu_toi_da_khong_co_nguon|{line_id}|")
    assert forward[0] == reversed_ids[1]
    assert forward[1] == reversed_ids[0]


def test_present_case_preserves_can_cu_and_ai_on_duplicate_findings() -> None:
    from app.api.presenter import present_ai_result, present_case
    from app.llm.schema import KetQuaLLM, NhanDinhCuoi, NhanDinhDeXuat
    from app.rules.types import CanCu

    case = load_case(ROOT / "data/mock/demo/DEMO-02.json")
    result = run_case(case, load_renal_rules(ROOT / "data/kb/quy_tac_lieu_than.json"))
    template = result.phat_hien[0]
    line_id = template.chi_tiet_y_lenh_id[0]
    f1 = template.model_copy(
        update={
            "ma_luat": "lieu_toi_da_khong_co_nguon",
            "chi_tiet_y_lenh_id": [line_id],
            "mo_ta": "Hoạt chất A thiếu ngưỡng liều tối đa.",
            "can_cu": [CanCu(loai="tai_lieu", mo_ta="Căn cứ A")],
        }
    )
    f2 = template.model_copy(
        update={
            "ma_luat": "lieu_toi_da_khong_co_nguon",
            "chi_tiet_y_lenh_id": [line_id],
            "mo_ta": "Hoạt chất B thiếu ngưỡng liều tối đa.",
            "can_cu": [CanCu(loai="tai_lieu", mo_ta="Căn cứ B")],
        }
    )
    dup_result = result.model_copy(update={"phat_hien": [f1, f2]})
    body = present_case(case, dup_result, [])
    case_rows = body.nhan_dinh.can_chu_y
    assert len(case_rows) == 2
    assert case_rows[0].nhan_dinh_id != case_rows[1].nhan_dinh_id
    assert case_rows[0].can_cu[0].mo_ta == "Căn cứ A"
    assert case_rows[1].can_cu[0].mo_ta == "Căn cứ B"

    llm = KetQuaLLM(
        trang_thai="ok",
        so_lan_goi=1,
        phien_ban_prompt="v1",
        nhan_dinh=[
            NhanDinhCuoi(
                nguon_goc="luat",
                phat_hien=f1,
                dien_giai=NhanDinhDeXuat(
                    chi_tiet_y_lenh_id=[line_id],
                    yeu_to=f1.yeu_to,
                    ket_luan=f1.ket_luan,
                    muc_do=f1.muc_do,
                    nhan_xet="Diễn giải AI cho A",
                    ban_ghi_ids=[],
                    trich_dan=[],
                    de_xuat="Đề xuất A",
                ),
            ),
            NhanDinhCuoi(
                nguon_goc="luat",
                phat_hien=f2,
                dien_giai=NhanDinhDeXuat(
                    chi_tiet_y_lenh_id=[line_id],
                    yeu_to=f2.yeu_to,
                    ket_luan=f2.ket_luan,
                    muc_do=f2.muc_do,
                    nhan_xet="Diễn giải AI cho B",
                    ban_ghi_ids=[],
                    trich_dan=[],
                    de_xuat="Đề xuất B",
                ),
            ),
        ],
    )
    ai_body = present_ai_result(case, dup_result, llm, [])
    assert ai_body.trang_thai == "xong"
    assert ai_body.nhan_dinh is not None
    ai_rows = ai_body.nhan_dinh.can_chu_y
    assert len(ai_rows) == 2
    assert ai_rows[0].nhan_dinh_id == case_rows[0].nhan_dinh_id
    assert ai_rows[1].nhan_dinh_id == case_rows[1].nhan_dinh_id
    assert ai_rows[0].dien_giai_ai == "Diễn giải AI cho A"
    assert ai_rows[1].dien_giai_ai == "Diễn giải AI cho B"
    assert ai_rows[0].can_cu[0].mo_ta == "Căn cứ A"
    assert ai_rows[1].can_cu[0].mo_ta == "Căn cứ B"


def test_duplicate_finding_feedback_is_tracked_independently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi.testclient import TestClient

    from app.api.main import create_app
    from app.api.presenter import present_case
    from app.api.service import CaseService
    from app.ui.labels import NHOM_LY_DO

    monkeypatch.setenv("AUTH_MODE", "off")
    monkeypatch.setenv("CASE_SOURCE", "file")
    monkeypatch.setenv("CDSS_AI", "off")

    case = load_case(ROOT / "data/mock/demo/DEMO-02.json")
    (tmp_path / "DEMO-02.json").write_text(case.model_dump_json(), encoding="utf-8")
    service = CaseService(
        tmp_path,
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "phan_hoi.jsonl",
        ai_runner=None,
        asker=None,
    )
    base_result = run_case(case, load_renal_rules(ROOT / "data/kb/quy_tac_lieu_than.json"))
    template = base_result.phat_hien[0]
    line_id = template.chi_tiet_y_lenh_id[0]
    f1 = template.model_copy(
        update={
            "ma_luat": "lieu_toi_da_khong_co_nguon",
            "chi_tiet_y_lenh_id": [line_id],
            "mo_ta": "Hoạt chất A thiếu ngưỡng liều tối đa.",
        }
    )
    f2 = template.model_copy(
        update={
            "ma_luat": "lieu_toi_da_khong_co_nguon",
            "chi_tiet_y_lenh_id": [line_id],
            "mo_ta": "Hoạt chất B thiếu ngưỡng liều tối đa.",
        }
    )
    dup_result = base_result.model_copy(update={"phat_hien": [f1, f2]})
    service._ensure_cases()
    service._results = {case.ca_id: dup_result}

    detail_before = present_case(case, dup_result, [])
    nid1 = detail_before.nhan_dinh.can_chu_y[0].nhan_dinh_id
    nid2 = detail_before.nhan_dinh.can_chu_y[1].nhan_dinh_id
    assert nid1 != nid2

    with TestClient(create_app(service)) as client:
        r1 = client.post(
            "/api/cases/DEMO-02/feedback",
            json={"nhan_dinh_id": nid1, "phan_hoi": "dong_y", "ly_do": "OK 1"},
        )
        assert r1.status_code == 200
        mid = client.get("/api/cases/DEMO-02").json()
        assert mid["nhan_dinh"]["can_chu_y"][0]["phan_hoi"]["phan_hoi"] == "dong_y"
        assert mid["nhan_dinh"]["can_chu_y"][1]["phan_hoi"] is None
        assert client.get("/api/cases").json()["cases"][0]["da_phan_hoi_het"] is False

        r2 = client.post(
            "/api/cases/DEMO-02/feedback",
            json={
                "nhan_dinh_id": nid2,
                "phan_hoi": "bac_bo",
                "nhom_ly_do": NHOM_LY_DO["khac"],
                "ly_do": "OK 2",
            },
        )
        assert r2.status_code == 200
        done = client.get("/api/cases/DEMO-02").json()
        assert done["nhan_dinh"]["can_chu_y"][0]["phan_hoi"]["phan_hoi"] == "dong_y"
        assert done["nhan_dinh"]["can_chu_y"][1]["phan_hoi"]["phan_hoi"] == "bac_bo"
        assert client.get("/api/cases").json()["cases"][0]["da_phan_hoi_het"] is True
