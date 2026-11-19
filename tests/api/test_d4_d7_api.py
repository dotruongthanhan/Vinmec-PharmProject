"""Kiểm thử API tích hợp đầy đủ bộ luật D4–D7 trên 66 ca qua TestClient."""

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import container as container_mod
from app.api.main import create_app
from app.api.service import CaseService
from app.config.settings import load_settings
from app.container import Container
from app.db.reader import load_source_cases
from app.rules.registry import RuleContext

ROOT = Path(__file__).resolve().parents[2]
_TRA_CUU_PATH = ROOT / "data/kb_curated/tra_cuu/tra_cuu.sqlite"
_RENAL_PATH = ROOT / "data/kb/quy_tac_lieu_than.json"

CaseBodyMap = dict[str, dict[str, Any]]

pytestmark = pytest.mark.can_du_lieu("data/kb_curated/tra_cuu/tra_cuu.sqlite")


@pytest.fixture(scope="module")
def runtime_context() -> RuleContext:
    """Nạp RuleContext cấu hình test từ kho chỉ mục thật; bỏ qua nếu thiếu tra_cuu.sqlite."""
    if not _TRA_CUU_PATH.is_file():
        pytest.skip("Thiếu data/kb_curated/tra_cuu/tra_cuu.sqlite")
    context = Container(load_settings("test")).rule_context
    assert context.resolver is not None
    return context


@pytest.fixture(scope="module")
def case_details_by_id(
    tmp_path_factory: pytest.TempPathFactory,
    runtime_context: RuleContext,
) -> CaseBodyMap:
    """Chạy GET /api/cases/{ca_id} cho đủ 66 ca từ load_source_cases với CASE_SOURCE=file."""
    source_cases = load_source_cases(ROOT)
    assert len(source_cases) == 66

    case_dir = tmp_path_factory.mktemp("d4_d7_api_cases")
    for case in source_cases:
        (case_dir / f"{case.ca_id}.json").write_text(case.model_dump_json(), encoding="utf-8")

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("AUTH_MODE", "off")
        mp.setenv("CASE_SOURCE", "file")
        mp.setenv("CDSS_AI", "off")
        mp.setattr(container_mod, "get_rule_context", lambda: runtime_context, raising=False)
        service = CaseService(
            case_dir,
            _RENAL_PATH,
            case_dir / "phan_hoi.jsonl",
            ai_runner=None,
            asker=None,
        )
        details: CaseBodyMap = {}
        with TestClient(create_app(service)) as client:
            list_resp = client.get("/api/cases")
            assert list_resp.status_code == 200
            list_body = list_resp.json()
            assert list_body["loi_nap"] == []
            assert len(list_body["cases"]) == 66
            for case in source_cases:
                resp = client.get(f"/api/cases/{case.ca_id}")
                assert resp.status_code == 200
                details[case.ca_id] = resp.json()
        return details


def test_hs019_factor_3_max_dose_exceeded(case_details_by_id: CaseBodyMap) -> None:
    """HS-019 phải có nhận định yếu tố 3 vượt liều tối đa nêu 6000 và 4000."""
    body = case_details_by_id["HS-019"]
    matches = [
        row
        for row in body["nhan_dinh"]["can_chu_y"]
        if row["yeu_to"].startswith("3.") and row["ma_luat"] == "lieu_toi_da_vuot"
    ]
    assert len(matches) >= 1
    assert any("6000" in row["nhan_xet"] and "4000" in row["nhan_xet"] for row in matches)


def test_demo02_factor_6_renal_dose_can_chinh(case_details_by_id: CaseBodyMap) -> None:
    """DEMO-02 phải có nhận định yếu tố 6 mã lieu_than_can_chinh."""
    body = case_details_by_id["DEMO-02"]
    matches = [
        row
        for row in body["nhan_dinh"]["can_chu_y"]
        if row["yeu_to"].startswith("6.") and row["ma_luat"] == "lieu_than_can_chinh"
    ]
    assert len(matches) >= 1


def test_hs028_factor_5_nephrotoxic_accumulation(case_details_by_id: CaseBodyMap) -> None:
    """HS-028 phải có nhận định yếu tố 5 cộng dồn độc thận."""
    body = case_details_by_id["HS-028"]
    matches = [
        row
        for row in body["nhan_dinh"]["can_chu_y"]
        if row["yeu_to"].startswith("5.") and row["ma_luat"] == "doc_than_cong_don"
    ]
    assert len(matches) == 1
    assert matches[0]["ket_luan_ma"] == "can_xem"
    assert matches[0]["muc_do_ma"] == "nghiem_trong"


def test_all_66_cases_no_dat_with_missing_info(case_details_by_id: CaseBodyMap) -> None:
    """Không ca nào trong 66 ca có nhận định ket_luan_ma='dat' mà thong_tin_con_thieu khác rỗng."""
    assert len(case_details_by_id) == 66
    for ca_id, body in case_details_by_id.items():
        all_rows = [*body["nhan_dinh"]["can_chu_y"], *body["nhan_dinh"]["dat"]]
        assert all_rows, f"Ca {ca_id} không có nhận định nào"
        for row in all_rows:
            if row["ket_luan_ma"] == "dat":
                assert row["thong_tin_con_thieu"] == [], f"{ca_id}:{row['ma_luat']}"
