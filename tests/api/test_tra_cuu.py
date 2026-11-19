"""API tra cứu thuốc, tra tương tác thủ công và máy tính công thức (hợp đồng v1.8).

Chạy ở chế độ tệp, không cần DB; mọi truy cập `read_pool` bị chặn để chứng minh chỉ đọc cục bộ.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient

from app import calc
from app import container as container_mod
from app.api import lookup
from app.api.main import create_app
from app.api.service import CaseService
from app.config.settings import load_settings
from app.container import Container
from app.db.read_pool import read_pool
from app.rules.registry import RuleContext
from tests.auth.support import AuthHarness

ROOT = Path(__file__).resolve().parents[2]
_TRA_CUU = "data/kb_curated/tra_cuu/tra_cuu.sqlite"
_DDINTER = "data/kb_curated/tuong_tac/ddinter.sqlite"
_CHUNKS = "data/kb_curated/chunks.jsonl"
needs_index = pytest.mark.can_du_lieu(_TRA_CUU, _DDINTER)
needs_chunks = pytest.mark.can_du_lieu(_TRA_CUU, _DDINTER, _CHUNKS)


@pytest.fixture(autouse=True)
def local_only(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Ép chế độ tệp và biến mọi kết nối DB thành lỗi."""
    monkeypatch.setenv("KB_SOURCE", "file")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Không được mở kết nối DB trong test tra cứu")

    monkeypatch.setattr(read_pool, "connection", forbidden)
    monkeypatch.setattr(psycopg, "connect", forbidden)
    lookup.clear_caches()
    yield
    lookup.clear_caches()


@pytest.fixture(scope="module")
def runtime_context() -> RuleContext:
    return Container(load_settings("test")).rule_context


@pytest.fixture
def client(
    tmp_path: Path, runtime_context: RuleContext, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    monkeypatch.setattr(container_mod, "get_rule_context", lambda: runtime_context)
    service = CaseService(
        ROOT / "data/mock/demo", ROOT / "data/kb/quy_tac_lieu_than.json", tmp_path / "pf.jsonl"
    )
    with TestClient(create_app(service), raise_server_exceptions=False) as session:
        yield session


def _ids(client: TestClient, query: str) -> list[str]:
    response = client.get("/api/thuoc", params={"q": query})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    return [row["hoat_chat_id"] for row in response.json()["ket_qua"]]


@needs_chunks
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("metformin", "metformin"),
        ("METFORMIN", "metformin"),
        ("paracetamol", "acetaminophen"),
        ("Paracetamol", "acetaminophen"),
    ],
)
def test_search_finds_ingredient_first_ignoring_case(
    client: TestClient, query: str, expected: str
) -> None:
    assert _ids(client, query)[0] == expected


@needs_chunks
def test_search_vietnamese_name_without_accents_and_paging(client: TestClient) -> None:
    body = client.get("/api/thuoc", params={"q": "paracetamol", "so_dong": 2}).json()
    assert body["so_dong"] == 2
    assert len(body["ket_qua"]) <= 2
    assert body["tong"] >= 1
    first = body["ket_qua"][0]
    assert first["hoat_chat_id"] == "acetaminophen"
    assert first["so_che_pham"] > 0
    assert first["co_nhan_fda"] is True
    assert first["so_quy_tac"] > 0
    assert set(first) == {
        "hoat_chat_id",
        "ten_inn",
        "ten_viet",
        "ma_atc",
        "so_che_pham",
        "co_nhan_fda",
        "so_quy_tac",
    }


@needs_chunks
def test_search_without_query_lists_only_ingredients_with_data(client: TestClient) -> None:
    body = client.get("/api/thuoc").json()
    assert body["tong"] > 0
    assert all(row["co_nhan_fda"] or row["so_quy_tac"] > 0 for row in body["ket_qua"])
    assert client.get("/api/thuoc", params={"q": "zzzkhongcothuocnay"}).json()["tong"] == 0


@needs_index
@pytest.mark.parametrize("params", [{"so_dong": 101}, {"so_dong": 0}, {"trang": 0}])
def test_search_rejects_bad_paging(client: TestClient, params: dict[str, int]) -> None:
    response = client.get("/api/thuoc", params=params)
    assert response.status_code == 422
    assert response.json()["loi"]["ma"] == "du_lieu_khong_hop_le"


@needs_chunks
def test_meropenem_detail_has_label_renal_dose_and_rules(client: TestClient) -> None:
    response = client.get("/api/thuoc/meropenem")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    body = response.json()
    assert body["dinh_danh"]["ten_inn"] == "meropenem"
    assert body["dinh_danh"]["ma_atc"] == ["J01DH"]
    assert 0 < len(body["che_pham"]["danh_sach"]) <= 50
    assert body["che_pham"]["tong"] >= len(body["che_pham"]["danh_sach"])
    groups = {group["muc"]: group["doan"] for group in body["nhan_fda"]["nhom"]}
    assert len(groups) == 13
    assert groups["lieu_than"], "nhãn FDA phải có đoạn liều theo thận"
    assert all(item["noi_dung_goc"] and item["doan_trich_id"] for item in groups["lieu_than"])
    kinds = {row["nhom"] for row in body["quy_tac"]}
    assert "lieu_than" in kinds
    renal = next(row for row in body["quy_tac"] if row["nhom"] == "lieu_than")
    assert renal["bang_luat"] == "quy_tac_lieu_than"
    assert renal["du_lieu"]["muc"], "giữ nguyên các mức CrCl của bảng luật"
    summary = body["tuong_tac_tom_tat"]
    assert summary["co_du_lieu"] is True
    assert summary["so_cap"]["major"] >= len(summary["major"]) > 0
    assert len(summary["major"]) <= 20


@needs_index
def test_unknown_ingredient_is_404(client: TestClient) -> None:
    response = client.get("/api/thuoc/khong-co-hoat-chat-nay")
    assert response.status_code == 404
    assert set(response.json()["loi"]) == {"ma", "thong_bao"}


def _cell(body: dict[str, Any], a: str, b: str) -> dict[str, Any]:
    return next(row for row in body["ma_tran"]["cap"] if {row["a"], row["b"]} == {a, b})


@needs_index
def test_manual_interaction_matrix_matches_case_page_semantics(client: TestClient) -> None:
    response = client.post(
        "/api/tuong-tac", json={"thuoc": ["Amiodaron 200 mg", "Digoxin 0,25 mg"]}
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    body = response.json()
    assert [row["trang_thai"] for row in body["phan_giai"]] == ["da_phan_giai"] * 2
    assert body["phan_giai"][0]["hoat_chat"] == ["amiodarone"]
    assert [row["ten"] for row in body["ma_tran"]["thuoc"]] == [
        "Amiodaron 200 mg",
        "Digoxin 0,25 mg",
    ]
    cell = _cell(body, "T1", "T2")
    assert cell["muc"] == "nghiem_trong"
    assert "DDInter: Major" in cell["tom_tat"]
    assert body["ma_tran"]["nguon"].startswith("DDInter 2.0")
    detail = body["chi_tiet"][0]
    assert {detail["a"], detail["b"]} == {"T1", "T2"}
    assert detail["muc"] == "tuong_tac_thuoc"
    assert any("DDInter 2.0" in text and "Major" in text for text in detail["can_cu"])


@needs_index
def test_unknown_name_is_reported_and_cells_lack_data(client: TestClient) -> None:
    response = client.post("/api/tuong-tac", json={"thuoc": ["Warfarin", "Thuốc lạ xyz 5 mg"]})
    assert response.status_code == 200
    body = response.json()
    assert [row["trang_thai"] for row in body["phan_giai"]] == ["da_phan_giai", "khong_nhan_dien"]
    assert body["phan_giai"][1]["ly_do"]
    assert _cell(body, "T1", "T2")["muc"] == "thieu_du_lieu"
    assert body["chi_tiet"][0]["muc"] == "tuong_tac_thieu_du_lieu"


@needs_index
@pytest.mark.parametrize(
    "names",
    [
        ["Warfarin"],
        [],
        ["Warfarin", "   "],
        ["Warfarin", "WARFARIN"],
        ["Warfarin", "Warfarín"],
        [f"Thuốc {index}" for index in range(13)],
        ["Warfarin", "x" * 201],
    ],
)
def test_interaction_lookup_rejects_bad_names(client: TestClient, names: list[str]) -> None:
    response = client.post("/api/tuong-tac", json={"thuoc": names})
    assert response.status_code == 422
    assert response.json()["loi"]["ma"] == "du_lieu_khong_hop_le"


def test_interaction_lookup_rejects_extra_fields(client: TestClient) -> None:
    response = client.post("/api/tuong-tac", json={"thuoc": ["A", "B"], "ca_id": "X"})
    assert response.status_code == 422


@needs_index
def test_interaction_lookup_does_not_touch_cases_or_database(client: TestClient) -> None:
    before = client.get("/api/cases").json()
    assert client.post("/api/tuong-tac", json={"thuoc": ["Warfarin", "Aspirin"]}).status_code == 200
    assert client.get("/api/cases").json()["cases"] == before["cases"]


def test_formula_catalog_lists_fourteen_with_specs(client: TestClient) -> None:
    body = client.get("/api/cong-thuc").json()
    assert len(body["cong_thuc"]) == 14
    by_code = {row["ma"]: row for row in body["cong_thuc"]}
    cg = by_code["cockcroft_gault"]
    assert cg["trang_thai"] == "chua_duoc_si_duyet"
    assert cg["dau_ra"]["don_vi"] == ["mL/min"]
    inputs = {row["ten"]: row for row in cg["dau_vao"]}
    assert inputs["creatinin"]["truong_don_vi"] == "creatinin_don_vi"
    assert inputs["creatinin"]["don_vi"] == ["mg/dL", "umol/L"]
    assert inputs["gioi_tinh"]["kieu"] == "lua_chon"
    assert inputs["gioi_tinh"]["lua_chon"] == ["nam", "nu"]
    assert inputs["gioi_tinh"]["nhan"] == "Giới tính"
    assert inputs["gioi_tinh"]["nhan_lua_chon"] == {"nam": "Nam", "nu": "Nữ"}
    assert inputs["loai_can_nang"]["nhan"] == "Loại cân nặng"
    assert inputs["loai_can_nang"]["nhan_lua_chon"] == {
        "thuc_te": "Thực tế",
        "ly_tuong": "Lý tưởng",
        "hieu_chinh": "Hiệu chỉnh",
    }
    assert inputs["loai_can_nang"]["mac_dinh"] == "thuc_te"
    assert inputs["chieu_cao_cm"]["bat_buoc"] is False
    cp_inputs = {row["ten"]: row for row in by_code["child_pugh"]["dau_vao"]}
    assert cp_inputs["co_truong"]["nhan"] == "Cổ trướng"
    assert cp_inputs["co_truong"]["nhan_lua_chon"] == {
        "khong": "Không",
        "nhe": "Nhẹ",
        "vua": "Vừa",
    }
    assert cp_inputs["nao_gan"]["nhan"] == "Bệnh não gan"
    assert cp_inputs["nao_gan"]["nhan_lua_chon"] == {
        "khong": "Không",
        "do_1_2": "Độ 1–2",
        "do_3_4": "Độ 3–4",
    }
    assert by_code["child_pugh"]["dau_ra"]["phan_hang"] == ["A", "B", "C"]
    for row in body["cong_thuc"]:
        for inp in row["dau_vao"]:
            assert inp["nhan"]
            assert "_" not in inp["nhan"]
            if inp["kieu"] == "lua_chon":
                assert set(inp["nhan_lua_chon"]) == set(inp["lua_chon"])
                assert all(v and "_" not in v for v in inp["nhan_lua_chon"].values())


def test_cockcroft_gault_matches_source_function(client: TestClient) -> None:
    payload = {
        "dau_vao": {
            "tuoi": 75,
            "gioi_tinh": "nu",
            "can_nang_kg": 50,
            "creatinin": 1.2,
            "creatinin_don_vi": "mg/dL",
        }
    }
    response = client.post("/api/cong-thuc/cockcroft_gault", json=payload)
    assert response.status_code == 200
    body = response.json()
    expected = calc.cockcroft_gault(75, "nu", 50, 1.2, "mg/dL")
    assert body["ket_qua"] == expected.ket_qua
    assert body["ket_qua"] == pytest.approx((140 - 75) * 50 / (72 * 1.2) * 0.85)
    assert body["don_vi"] == "mL/min"
    assert body["thieu_dau_vao"] == []
    assert body["tham_khao"] == expected.tham_khao
    assert {row["ten"] for row in body["dau_vao_da_dung"]} == {"tuoi", "can_nang_kg", "creatinin"}


def test_formula_accepts_decimal_comma_and_alternative_unit(client: TestClient) -> None:
    mg = client.post(
        "/api/cong-thuc/egfr_ckd_epi_2021",
        json={
            "dau_vao": {
                "tuoi": 60,
                "gioi_tinh": "nam",
                "creatinin": "1,2",
                "creatinin_don_vi": "mg/dL",
            }
        },
    ).json()
    umol = client.post(
        "/api/cong-thuc/egfr_ckd_epi_2021",
        json={
            "dau_vao": {
                "tuoi": 60,
                "gioi_tinh": "nam",
                "creatinin": 1.2 * 88.4,
                "creatinin_don_vi": "umol/L",
            }
        },
    ).json()
    assert mg["ket_qua"] == pytest.approx(umol["ket_qua"])
    assert mg["ket_qua"] == calc.egfr_ckd_epi_2021(60, "nam", 1.2, "mg/dL").ket_qua


def test_child_pugh_missing_inputs_report_missing(client: TestClient) -> None:
    response = client.post("/api/cong-thuc/child_pugh", json={"dau_vao": {"inr": 1.4}})
    assert response.status_code == 200
    body = response.json()
    assert body["ket_qua"] is None
    assert body["thieu_dau_vao"]
    assert "inr" not in body["thieu_dau_vao"]
    assert "bilirubin" in body["thieu_dau_vao"]


def test_formula_calculate_still_accepts_unaccented_choice_keys(client: TestClient) -> None:
    cp_resp = client.post(
        "/api/cong-thuc/child_pugh",
        json={
            "dau_vao": {
                "bilirubin": 1.5,
                "bilirubin_don_vi": "mg/dL",
                "albumin": 3.8,
                "albumin_don_vi": "g/dL",
                "inr": 1.3,
                "co_truong": "nhe",
                "nao_gan": "do_1_2",
            }
        },
    )
    assert cp_resp.status_code == 200
    assert cp_resp.json()["ket_qua"] is not None

    cg_resp = client.post(
        "/api/cong-thuc/cockcroft_gault",
        json={
            "dau_vao": {
                "tuoi": 65,
                "gioi_tinh": "nam",
                "can_nang_kg": 80,
                "chieu_cao_cm": 170,
                "creatinin": 1.1,
                "creatinin_don_vi": "mg/dL",
                "loai_can_nang": "ly_tuong",
            }
        },
    )
    assert cg_resp.status_code == 200
    assert cg_resp.json()["ket_qua"] is not None


@pytest.mark.parametrize(
    "dau_vao",
    [
        {
            "tuoi": 500,
            "gioi_tinh": "nu",
            "can_nang_kg": 50,
            "creatinin": 1.2,
            "creatinin_don_vi": "mg/dL",
        },
        {
            "tuoi": 75,
            "gioi_tinh": "khac",
            "can_nang_kg": 50,
            "creatinin": 1.2,
            "creatinin_don_vi": "mg/dL",
        },
        {
            "tuoi": 75,
            "gioi_tinh": "nu",
            "can_nang_kg": 50,
            "creatinin": 1.2,
            "creatinin_don_vi": "mmol",
        },
        {"tuoi": "bảy mươi", "gioi_tinh": "nu", "can_nang_kg": 50, "creatinin": 1.2},
        {"tuoi": True, "gioi_tinh": "nu", "can_nang_kg": 50, "creatinin": 1.2},
        {"tuoi": 75, "truong_la": 1},
        {
            "tuoi": 75,
            "gioi_tinh": "nu",
            "can_nang_kg": -5,
            "creatinin": 1.2,
            "creatinin_don_vi": "mg/dL",
        },
    ],
)
def test_formula_invalid_input_is_422_without_traceback(
    client: TestClient, dau_vao: dict[str, Any]
) -> None:
    response = client.post("/api/cong-thuc/cockcroft_gault", json={"dau_vao": dau_vao})
    assert response.status_code == 422
    error = response.json()["loi"]
    assert error["ma"] == "du_lieu_khong_hop_le"
    assert "Traceback" not in error["thong_bao"]
    assert error["thong_bao"]


def test_unknown_formula_is_404(client: TestClient) -> None:
    response = client.post("/api/cong-thuc/khong_co", json={"dau_vao": {}})
    assert response.status_code == 404


def test_formula_catalog_only_maps_allowed_functions() -> None:
    from app.api import formulas

    assert set(formulas._load_entries()) == {
        entry["ma"] for entry in formulas.yaml.safe_load(formulas._CATALOG_PATH.read_text("utf-8"))
    }
    assert all(entry["ham"] in formulas._ALLOWED for entry in formulas._load_entries().values())


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", "/api/thuoc", None),
        ("get", "/api/thuoc/meropenem", None),
        ("post", "/api/tuong-tac", {"thuoc": ["A", "B"]}),
        ("get", "/api/cong-thuc", None),
        ("post", "/api/cong-thuc/bmi", {"dau_vao": {}}),
    ],
)
def test_lookup_endpoints_require_login(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, method: str, path: str, body: Any
) -> None:
    harness = AuthHarness(tmp_path, monkeypatch)
    response = getattr(harness.client, method)(path, **({"json": body} if body else {}))
    assert response.status_code == 401
    ok = getattr(harness.client, method)(
        path, headers=harness.headers(), **({"json": body} if body else {})
    )
    assert ok.status_code != 401
