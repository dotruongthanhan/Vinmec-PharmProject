"""Kiểm thử các điểm cuối với ca giả lập và tệp phản hồi riêng."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    from app.api.main import create_app
    from app.api.service import CaseService

    service = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "phan_hoi.jsonl",
    )
    with TestClient(create_app(service), raise_server_exceptions=False) as session:
        yield session


def test_health_and_queue(client: TestClient) -> None:
    health = client.get("/api/health")
    assert health.status_code == 200
    body_health = health.json()
    expected_retrieval = (
        "san_sang" if (ROOT / "data/kb_curated/chunks.jsonl").is_file() else "chua_co"
    )
    assert body_health["ok"] is True
    assert body_health["che_do"]["truy_xuat"] == expected_retrieval
    assert isinstance(body_health["che_do"]["co_llm"], bool)
    assert body_health["che_do"]["hoi_them"] is body_health["che_do"]["co_llm"]
    if body_health["che_do"]["co_llm"]:
        assert (
            "Đang chạy không có bước AI: bảng nhận định do bộ luật sinh ra"
            not in body_health["che_do"]["thong_bao"]
        )
    else:
        assert body_health["che_do"]["thong_bao"] == [
            "Đang chạy không có bước AI: bảng nhận định do bộ luật sinh ra"
        ]
    response = client.get("/api/cases")
    assert response.status_code == 200
    body = response.json()
    assert body["loi_nap"] == []
    ids = [row["ca_id"] for row in body["cases"]]
    assert len(ids) == 6
    assert ids[:2] == ["DEMO-02", "DEMO-06"]
    assert ids.index("DEMO-05") < ids.index("DEMO-03")


def test_queue_order_fields_for_six_demo_cases(client: TestClient) -> None:
    expected = {
        "DEMO-01": ("Nam, 45 tuổi", "Amlodipin 5 mg"),
        "DEMO-02": ("Nữ, 75 tuổi", "Meropenem 1 g"),
        "DEMO-03": ("Nam, 60 tuổi", "Amoxicillin + acid clavulanic 875 mg/125 mg"),
        "DEMO-04": ("Nữ, 68 tuổi", "Ceftriaxon 2 g"),
        "DEMO-05": ("Nam, 55 tuổi", "Metoprolol tartrat 50 mg"),
        "DEMO-06": ("Nữ, 40 tuổi", "Amoxicillin 500 mg"),
    }
    from app.domain.loader import load_case

    rows = client.get("/api/cases").json()["cases"]
    assert {row["ca_id"] for row in rows} == expected.keys()
    for row in rows:
        case = load_case(ROOT / f"data/mock/demo/{row['ca_id']}.json")
        summary, drug = expected[row["ca_id"]]
        assert row["ma_y_lenh"] == f"YL-{row['ca_id']}"
        assert row["thoi_diem_ke"] == case.y_lenh_cho_duyet.thoi_diem_ke.isoformat()
        assert row["nguoi_benh_tom_tat"] == summary
        assert row["thuoc"] == [drug]


def test_demo02_detail(client: TestClient) -> None:
    response = client.get("/api/cases/DEMO-02")
    assert response.status_code == 200
    body = response.json()
    assert body["dinh_danh"]["gioi_tuoi"] == "Nữ 75 tuổi"
    assert body["dinh_danh"]["crcl"] == "16,0 mL/phút"
    assert body["dinh_danh"]["dem"]["nghiem_trong"] == 1
    assert len(body["chi_so"]) == 4
    assert body["chi_so"][0]["cong_thuc"] == "cockcroft_gault"
    assert body["chi_so"][0]["gia_tri_text"] == "16,0"
    assert body["chi_so"][-1]["gia_tri_text"] == "1,47"
    findings = body["nhan_dinh"]["can_chu_y"]
    assert len(findings) == 3
    assert [row["ma_luat"] for row in findings] == [
        "lieu_than_can_chinh",
        "khang_sinh_can_phe_duyet",
        "lieu_toi_da_khong_co_nguon",
    ]
    assert findings[1]["yeu_to"].startswith("7.")
    assert findings[2]["yeu_to"].startswith("3.")
    finding = findings[0]
    assert finding["yeu_to"].startswith("6.")
    assert finding["muc_do_ma"] == "nghiem_trong"
    assert finding["nguon_goc_ma"] == "luat"
    assert finding["nguon_goc_nhan"] == "Luật"
    assert finding["dien_giai_ai"] is None
    assert finding["de_xuat_ai"] is None
    assert finding["trich_dan"] == []
    assert [row["loai_ma"] for row in finding["can_cu"]] == ["du_lieu", "tinh_toan", "tai_lieu"]
    assert finding["can_cu"][1]["cong_thuc"] == "cockcroft_gault"
    assert finding["can_cu"][1]["mo_duoc"] is True
    assert finding["can_cu"][2]["ghi_chu"] == ("Nguyên văn đoạn nguồn sẽ có khi nối kho tri thức.")
    assert body["tom_tat"]["bat_thuong"][0]["huong"] == "▲"
    assert "150" in body["tom_tat"]["bat_thuong"][0]["so_voi_truoc"]
    assert body["tom_tat"]["nam_vien_text"].startswith("3 ngày")
    assert "4. Tương tác thuốc" not in body["nhan_dinh"]["yeu_to_chua_kiem"]
    assert body["nhan_dinh"]["so_luat_da_chay"] == 14
    matrix = body["ma_tran_tuong_tac"]
    assert matrix is not None and len(matrix["thuoc"]) == 1 and matrix["cap"] == []
    interaction = next(row for row in body["nhan_dinh"]["dat"] if row["yeu_to"].startswith("4."))
    assert interaction["ket_luan_ma"] == "dat"
    assert interaction["nhan_xet"] == (
        "Y lệnh chỉ có một thuốc đang hiệu lực, không có cặp để đối chiếu tương tác."
    )


def test_missing_data_and_microbiology(client: TestClient) -> None:
    body = client.get("/api/cases/DEMO-03").json()
    assert body["dinh_danh"]["di_ung_ma"] == "chua_co_thong_tin"
    missing = [
        row for row in body["nhan_dinh"]["can_chu_y"] if row["ket_luan_ma"] == "khong_du_du_lieu"
    ]
    assert missing and all(row["thong_tin_con_thieu"] for row in missing)
    cultures = client.get("/api/cases/DEMO-04").json()["chi_tiet"]["vi_sinh"]
    assert cultures
    assert any(row["dang_ke"] for culture in cultures for row in culture["khang_sinh_do"])


@pytest.mark.parametrize(
    "path",
    [
        "/api/cases/KHONG-CO",
        "/api/cases/DEMO-02/records/LA",
        "/api/cases/DEMO-02/records/XN-DEMO04-01",
        "/api/khong-co",
        "/api",
    ],
)
def test_not_found_envelope(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 404
    assert set(response.json()) == {"loi"}
    assert response.json()["loi"]["ma"] == "khong_tim_thay"


def test_record_is_scoped_to_case(client: TestClient) -> None:
    response = client.get("/api/cases/DEMO-02/records/XN-DEMO02-01")
    assert response.status_code == 200
    assert any("212" in value for _, value in response.json()["dong"])


def test_feedback_persists_latest_without_rerunning(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api import service as service_module

    calls = 0
    original = service_module.run_case

    def counted(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(service_module, "run_case", counted)
    detail = client.get("/api/cases/DEMO-02").json()
    findings = detail["nhan_dinh"]["can_chu_y"]
    finding = findings[0]
    assert finding["nhan_dinh_id"] == (
        finding["ma_luat"] + "|" + ",".join(sorted(finding["chi_tiet_y_lenh_id"]))
    )
    payload = {"nhan_dinh_id": finding["nhan_dinh_id"], "phan_hoi": "dong_y"}
    response = client.post("/api/cases/DEMO-02/feedback", json=payload)
    assert response.status_code == 200
    assert response.json()["phan_hoi_nhan"] == "Đồng ý"
    assert calls == 1
    for extra in findings[1:]:
        extra_payload = {"nhan_dinh_id": extra["nhan_dinh_id"], "phan_hoi": "dong_y"}
        extra_resp = client.post("/api/cases/DEMO-02/feedback", json=extra_payload)
        assert extra_resp.status_code == 200
    assert calls == 1
    reread = client.get("/api/cases/DEMO-02").json()
    assert reread["nhan_dinh"]["can_chu_y"][0]["phan_hoi"]["phan_hoi"] == "dong_y"
    queue = client.get("/api/cases").json()["cases"]
    assert next(row for row in queue if row["ca_id"] == "DEMO-02")["da_phan_hoi_het"] is True
    before = calls
    payload.update(phan_hoi="can_sua", nhom_ly_do=detail["nhom_ly_do"][0], ly_do="Cần kiểm tra lại")
    response = client.post("/api/cases/DEMO-02/feedback", json=payload)
    assert response.status_code == 200
    latest = client.get("/api/cases/DEMO-02").json()["nhan_dinh"]["can_chu_y"][0]["phan_hoi"]
    assert latest == response.json()
    assert latest["phan_hoi"] == "can_sua"
    assert calls == before
    text = (tmp_path / "phan_hoi.jsonl").read_text(encoding="utf-8")
    assert len(text.splitlines()) == len(findings) + 1
    assert "Cần kiểm tra lại" in text


@pytest.mark.parametrize(
    "changes,status",
    [
        ({"phan_hoi": "bac_bo"}, 422),
        ({"phan_hoi": "can_sua", "nhom_ly_do": ""}, 422),
        ({"nhom_ly_do": "lạ"}, 422),
        ({"nhan_dinh_id": "LA"}, 404),
        ({"phan_hoi": "lạ"}, 422),
    ],
)
def test_feedback_validation(
    client: TestClient, tmp_path: Path, changes: dict[str, object], status: int
) -> None:
    detail = client.get("/api/cases/DEMO-02").json()
    payload = {
        "nhan_dinh_id": detail["nhan_dinh"]["can_chu_y"][0]["nhan_dinh_id"],
        "phan_hoi": "dong_y",
        **changes,
    }
    response = client.post("/api/cases/DEMO-02/feedback", json=payload)
    assert response.status_code == status
    assert response.json()["loi"]["ma"] == (
        "khong_tim_thay" if status == 404 else "du_lieu_khong_hop_le"
    )
    assert not (tmp_path / "phan_hoi.jsonl").exists()


def test_ask_and_default_validation(client: TestClient, tmp_path: Path) -> None:
    from app.api.main import create_app
    from app.api.service import CaseService

    disabled = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "phan_hoi_ask.jsonl",
        ai_runner=None,
    )
    with TestClient(create_app(disabled), raise_server_exceptions=False) as disabled_client:
        response = disabled_client.post(
            "/api/cases/DEMO-02/ask", json={"cau_hoi": "Vì sao?", "lich_su": []}
        )
        assert response.status_code == 200
        assert response.json()["trang_thai"] == "chua_san_sang"
        assert response.json()["trich_dan"] == []
        assert response.json()["cong_cu_da_goi"] == []

    response = client.post("/api/cases/DEMO-02/ask", json={})
    assert response.status_code == 422
    assert response.json()["loi"]["ma"] == "du_lieu_khong_hop_le"
    response = client.post("/api/cases/KHONG-CO/ask", json={"cau_hoi": "?", "lich_su": []})
    assert response.status_code == 404


def test_unexpected_error_is_redacted(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail() -> None:
        raise RuntimeError("Traceback: nội dung ca bí mật")

    monkeypatch.setattr(client.app.state.service, "list_cases", fail)
    response = client.get("/api/cases")
    assert response.status_code == 500
    assert response.json()["loi"]["ma"] == "loi_he_thong"
    assert "Traceback" not in response.text
    assert "bí mật" not in response.text


def test_cors_only_allows_local_web(client: TestClient) -> None:
    for origin in ["http://localhost:5173", "http://127.0.0.1:5173"]:
        response = client.options(
            "/api/cases", headers={"Origin": origin, "Access-Control-Request-Method": "GET"}
        )
        assert response.headers["access-control-allow-origin"] == origin
    response = client.get("/api/health", headers={"Origin": "https://example.invalid"})
    assert "access-control-allow-origin" not in response.headers


def test_spa_fallback_preserves_api_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api import main
    from app.api.service import CaseService

    dist = tmp_path / "web/dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<html>Demo web</html>", encoding="utf-8")
    (dist / "asset.js").write_text("demo()", encoding="utf-8")
    monkeypatch.setattr(main, "_ROOT", tmp_path)
    service = CaseService(
        ROOT / "data/mock/demo", ROOT / "data/kb/quy_tac_lieu_than.json", tmp_path / "fb.jsonl"
    )
    with TestClient(main.create_app(service)) as session:
        for path in ["/", "/cases/DEMO-02"]:
            assert session.get(path).text == "<html>Demo web</html>"
        assert session.get("/asset.js").text == "demo()"
        for path in ["/api", "/api/unknown"]:
            response = session.get(path)
            assert response.status_code == 404
            assert response.json()["loi"]["ma"] == "khong_tim_thay"
