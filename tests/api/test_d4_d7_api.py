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


def test_demo02_and_demo06_factor_5_has_dat_finding(case_details_by_id: CaseBodyMap) -> None:
    """DEMO-02 và DEMO-06 phải có nhận định đạt yếu tố 5, không nằm trong yeu_to_chua_kiem."""
    for ca_id in ("DEMO-02", "DEMO-06"):
        body = case_details_by_id[ca_id]
        assert "5. Độc tính" not in body["nhan_dinh"]["yeu_to_chua_kiem"]
        factor5 = [row for row in body["nhan_dinh"]["dat"] if row["yeu_to"].startswith("5.")]
        assert [row["ma_luat"] for row in factor5] == ["doc_tinh_khong_thuoc_danh_sach"]


def test_all_66_cases_have_unique_nhan_dinh_ids(case_details_by_id: CaseBodyMap) -> None:
    """Mọi nhận định trong cùng một ca đều có nhan_dinh_id duy nhất across 66 ca."""
    assert len(case_details_by_id) == 66
    for ca_id, body in case_details_by_id.items():
        all_rows = [*body["nhan_dinh"]["can_chu_y"], *body["nhan_dinh"]["dat"]]
        ids = [row["nhan_dinh_id"] for row in all_rows]
        assert len(ids) == len(set(ids)), f"Ca {ca_id} bị trùng nhan_dinh_id"


def test_hs056_combination_drug_ids_distinct_and_stable(
    tmp_path: Path,
    runtime_context: RuleContext,
    case_details_by_id: CaseBodyMap,
) -> None:
    """HS-056 hai nhận định thuốc phối hợp phải có 2 mã khác nhau, ổn định giữa 2 lần chạy."""
    hs056 = case_details_by_id["HS-056"]
    all_rows = [*hs056["nhan_dinh"]["can_chu_y"], *hs056["nhan_dinh"]["dat"]]
    combo_rows = [
        row
        for row in all_rows
        if row["ma_luat"] == "lieu_toi_da_khong_co_nguon"
        and row["chi_tiet_y_lenh_id"] == ["CT-HS-056-05-01"]
    ]
    assert len(combo_rows) == 2
    first_run_ids = [row["nhan_dinh_id"] for row in combo_rows]
    assert len(set(first_run_ids)) == 2
    prefix = "lieu_toi_da_khong_co_nguon|CT-HS-056-05-01|"
    assert all(nid.startswith(prefix) for nid in first_run_ids)

    source_cases = [case for case in load_source_cases(ROOT) if case.ca_id == "HS-056"]
    assert len(source_cases) == 1
    case_dir = tmp_path / "hs056_only"
    case_dir.mkdir()
    (case_dir / "HS-056.json").write_text(source_cases[0].model_dump_json(), encoding="utf-8")

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("AUTH_MODE", "off")
        mp.setenv("CASE_SOURCE", "file")
        mp.setenv("CDSS_AI", "off")
        mp.setattr(container_mod, "get_rule_context", lambda: runtime_context, raising=False)
        service = CaseService(
            case_dir,
            _RENAL_PATH,
            tmp_path / "phan_hoi_stable.jsonl",
            ai_runner=None,
            asker=None,
        )
        with TestClient(create_app(service)) as client:
            second = client.get("/api/cases/HS-056").json()
            second_rows = [
                row
                for row in (*second["nhan_dinh"]["can_chu_y"], *second["nhan_dinh"]["dat"])
                if row["ma_luat"] == "lieu_toi_da_khong_co_nguon"
                and row["chi_tiet_y_lenh_id"] == ["CT-HS-056-05-01"]
            ]
            assert [row["nhan_dinh_id"] for row in second_rows] == first_run_ids


def test_hs056_feedback_distinguishes_duplicate_findings(
    tmp_path: Path,
    runtime_context: RuleContext,
) -> None:
    """Phản hồi một trong hai nhận định trùng khóa của HS-056 không đè lên nhận định còn lại."""
    hs056_case = next(case for case in load_source_cases(ROOT) if case.ca_id == "HS-056")
    case_dir = tmp_path / "hs056_fb"
    case_dir.mkdir()
    (case_dir / "HS-056.json").write_text(hs056_case.model_dump_json(), encoding="utf-8")

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("AUTH_MODE", "off")
        mp.setenv("CASE_SOURCE", "file")
        mp.setenv("CDSS_AI", "off")
        mp.setattr(container_mod, "get_rule_context", lambda: runtime_context, raising=False)
        service = CaseService(
            case_dir,
            _RENAL_PATH,
            tmp_path / "phan_hoi_fb.jsonl",
            ai_runner=None,
            asker=None,
        )
        with TestClient(create_app(service)) as client:
            detail = client.get("/api/cases/HS-056").json()
            targets = [
                row
                for row in (*detail["nhan_dinh"]["can_chu_y"], *detail["nhan_dinh"]["dat"])
                if row["ma_luat"] == "lieu_toi_da_khong_co_nguon"
                and row["chi_tiet_y_lenh_id"] == ["CT-HS-056-05-01"]
            ]
            assert len(targets) == 2
            id_a, id_b = targets[0]["nhan_dinh_id"], targets[1]["nhan_dinh_id"]
            assert id_a != id_b

            resp1 = client.post(
                "/api/cases/HS-056/feedback",
                json={"nhan_dinh_id": id_a, "phan_hoi": "dong_y", "ly_do": "Đồng ý thành phần 1"},
            )
            assert resp1.status_code == 200

            after1 = client.get("/api/cases/HS-056").json()
            by_id1 = {
                row["nhan_dinh_id"]: row
                for row in (*after1["nhan_dinh"]["can_chu_y"], *after1["nhan_dinh"]["dat"])
            }
            assert by_id1[id_a]["phan_hoi"]["phan_hoi"] == "dong_y"
            assert by_id1[id_b]["phan_hoi"] is None

            all_rows = [*detail["nhan_dinh"]["can_chu_y"], *detail["nhan_dinh"]["dat"]]
            for row in all_rows:
                if row["nhan_dinh_id"] == id_a:
                    continue
                resp_other = client.post(
                    "/api/cases/HS-056/feedback",
                    json={"nhan_dinh_id": row["nhan_dinh_id"], "phan_hoi": "dong_y"},
                )
                assert resp_other.status_code == 200

            queue_done = client.get("/api/cases").json()["cases"]
            assert queue_done[0]["da_phan_hoi_het"] is True
