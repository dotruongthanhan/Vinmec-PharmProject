"""Kiểm thử 3 điểm cuối AI v1.1, chế độ vận hành và không chặn GET chi tiết ca."""

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.api.schemas import DoanNguon, KetQuaAI
from app.api.service import CaseService
from app.config.settings import load_settings
from app.core.errors import ConfigError
from app.core.types import Chunk
from app.domain.models import CaBenh
from app.llm.schema import KetQuaLLM, NhanDinhCuoi, NhanDinhDeXuat, TrichDanNguon
from app.llm.synthesizer import Synthesizer
from app.orchestration.ai_review import AiRunResult
from app.pipeline import KetQuaThamDinh
from tests.api.test_contract import _check_display_strings

ROOT = Path(__file__).resolve().parents[2]


def _sample_chunk() -> Chunk:
    return Chunk(
        doan_trich_id="DT-MERO-01",
        tai_lieu_id="TL-MERO",
        muc_cha_id=None,
        nhom_nguon="nhan_thuoc",
        nguon="openfda",
        tang_tin_cay=3,
        hoat_chat_ids=["meropenem"],
        muc="lieu_than",
        duong_dan_muc="Dosage and Administration > Renal Impairment",
        loai_noi_dung="van_ban",
        ngon_ngu="en",
        phien_ban_nguon="20261102",
        url_goc="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=mero",
        noi_dung_goc=(
            "For creatinine clearance 10 to 25 mL/min, administer one-half the "
            "recommended dose every 12 hours."
        ),
        noi_dung_nhung="[Meropenem | FDA] For creatinine clearance 10 to 25 mL/min...",
    )


class _FakeAiRunner:
    """Bộ chạy AI giả trả kết quả hợp lệ ngay hoặc ngủ theo thời gian cấu hình."""

    model_name = "deepseek-flash"

    def __init__(self, delay_seconds: float = 0.0) -> None:
        self.delay_seconds = delay_seconds
        self.calls = 0

    def run(self, ca: CaBenh, ket_qua: KetQuaThamDinh) -> AiRunResult:
        self.calls += 1
        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)
        chunk = _sample_chunk()
        rule_finding = ket_qua.phat_hien[0]
        explanation = NhanDinhDeXuat(
            chi_tiet_y_lenh_id=list(rule_finding.chi_tiet_y_lenh_id),
            yeu_to=rule_finding.yeu_to,
            ket_luan=rule_finding.ket_luan,  # type: ignore[arg-type]
            muc_do="nghiem_trong",
            nhan_xet="Creatinin 212 umol/L, CrCl 16,0 mL/phút cần hiệu chỉnh liều.",
            ban_ghi_ids=["XN-DEMO02-01"],
            trich_dan=[
                TrichDanNguon(
                    doan_trich_id=chunk.doan_trich_id,
                    trich_nguyen_van="administer one-half the recommended dose every 12 hours.",
                )
            ],
            de_xuat="Cân nhắc giảm một nửa liều mỗi 12 giờ.",
            bo_sung_cho_ma_luat=rule_finding.ma_luat,
        )
        ai_verified = NhanDinhDeXuat(
            chi_tiet_y_lenh_id=list(rule_finding.chi_tiet_y_lenh_id),
            yeu_to=5,
            ket_luan="can_xem",
            muc_do="can_luu_y",
            nhan_xet="Cần theo dõi độc tính thần kinh khi dùng meropenem.",
            ban_ghi_ids=["XN-DEMO02-01"],
            trich_dan=[
                TrichDanNguon(
                    doan_trich_id=chunk.doan_trich_id,
                    trich_nguyen_van="administer one-half the recommended dose every 12 hours.",
                )
            ],
            de_xuat="Theo dõi triệu chứng co giật.",
        )
        ai_unverified = NhanDinhDeXuat(
            chi_tiet_y_lenh_id=list(rule_finding.chi_tiet_y_lenh_id),
            yeu_to=4,
            ket_luan="can_xem",
            muc_do="can_luu_y",
            nhan_xet="Dòng chưa kiểm chứng không được xuất hiện.",
            ban_ghi_ids=["XN-DEMO02-01"],
            trich_dan=[],
        )
        rule_rows = [
            NhanDinhCuoi(
                nguon_goc="luat",
                phat_hien=ph,
                dien_giai=explanation if idx == 0 else None,
            )
            for idx, ph in enumerate(ket_qua.phat_hien)
        ]
        llm_out = KetQuaLLM(
            trang_thai="ok",
            nhan_dinh=[
                *rule_rows,
                NhanDinhCuoi(nguon_goc="ai_da_kiem_chung", de_xuat=ai_verified),
                NhanDinhCuoi(
                    nguon_goc="ai_chua_kiem_chung",
                    de_xuat=ai_unverified,
                    loi_kiem_chung=["so_khong_co_nguon:99"],
                ),
            ],
            so_lan_goi=1,
            canh_bao=[],
            phien_ban_prompt="tong_hop.v1",
            mo_hinh="deepseek-flash",
        )
        return AiRunResult(llm=llm_out, doan=[chunk], canh_bao=[], thoi_gian_ms=15.0)


def _poll_ai_until_done(client: TestClient, ca_id: str, timeout: float = 2.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = client.get(f"/api/cases/{ca_id}/ai")
        assert resp.status_code == 200
        body = resp.json()
        if body["trang_thai"] != "dang_chay":
            return body
        time.sleep(0.01)
    raise AssertionError("Quá thời gian chờ GET .../ai hoàn tất")


def test_ai_endpoints_lifecycle_sources_and_ai_feedback(tmp_path: Path) -> None:
    runner = _FakeAiRunner()
    service = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "phan_hoi.jsonl",
        ai_runner=runner,
    )
    with TestClient(create_app(service), raise_server_exceptions=False) as client:
        before = client.get("/api/cases/DEMO-02/ai")
        assert before.status_code == 404
        assert before.json()["loi"]["ma"] == "chua_chay"

        started = client.post("/api/cases/DEMO-02/ai")
        assert started.status_code == 200
        assert started.json()["trang_thai"] in ("dang_chay", "xong")

        finished = _poll_ai_until_done(client, "DEMO-02")
        assert finished["trang_thai"] == "xong"
        KetQuaAI.model_validate(finished, extra="forbid")
        _check_display_strings(finished)

        attention = finished["nhan_dinh"]["can_chu_y"]
        rule_rows = [row for row in attention if row["nguon_goc_ma"] == "luat"]
        assert len(rule_rows) == len(attention) - 1
        assert rule_rows[0]["dien_giai_ai"] is not None
        assert rule_rows[0]["trich_dan"][0]["nhan"].startswith("Nhãn FDA · ")
        ai_rows = [row for row in attention if row["nhan_dinh_id"].startswith("ai|")]
        assert len(ai_rows) == 1
        ai_row = ai_rows[0]
        assert ai_row["nguon_goc_ma"] == "ai_da_kiem_chung"
        assert ai_row["ma_luat"] is None
        assert runner.calls == 1

        # Gọi lại POST .../ai khi đã xong mà không có chay_lai=True thì không chạy lại.
        second = client.post("/api/cases/DEMO-02/ai")
        assert second.status_code == 200
        assert runner.calls == 1

        # chay_lai=True chạy lại lần mới.
        restarted = client.post("/api/cases/DEMO-02/ai", json={"chay_lai": True})
        assert restarted.status_code == 200
        _poll_ai_until_done(client, "DEMO-02")
        assert runner.calls == 2

        # Tra đoạn nguồn theo mã đã cấp.
        source_resp = client.get("/api/cases/DEMO-02/sources/DT-MERO-01")
        assert source_resp.status_code == 200
        source_body = source_resp.json()
        DoanNguon.model_validate(source_body, extra="forbid")
        _check_display_strings(source_body)
        assert source_body["nguon_nhan"] == "Nhãn FDA"

        assert client.get("/api/cases/DEMO-02/sources/DT-LA").status_code == 404
        assert client.get("/api/cases/DEMO-01/sources/DT-MERO-01").status_code == 404

        # Phản hồi cho mã ai|... hợp lệ trả 200 và gắn lại vào GET .../ai.
        fb_resp = client.post(
            "/api/cases/DEMO-02/feedback",
            json={"nhan_dinh_id": ai_row["nhan_dinh_id"], "phan_hoi": "dong_y"},
        )
        assert fb_resp.status_code == 200
        assert fb_resp.json()["phan_hoi_nhan"] == "Đồng ý"

        reread = client.get("/api/cases/DEMO-02/ai").json()
        assert (
            next(
                row
                for row in reread["nhan_dinh"]["can_chu_y"]
                if row["nhan_dinh_id"] == ai_row["nhan_dinh_id"]
            )["phan_hoi"]["phan_hoi"]
            == "dong_y"
        )

        # Mã ai|... không tồn tại trong lần chạy của ca vẫn trả 404.
        bad_fb = client.post(
            "/api/cases/DEMO-02/feedback",
            json={"nhan_dinh_id": "ai|000000000000", "phan_hoi": "dong_y"},
        )
        assert bad_fb.status_code == 404

        # Ca không tồn tại -> 404.
        assert client.post("/api/cases/KHONG-CO/ai").status_code == 404
        assert client.get("/api/cases/KHONG-CO/ai").status_code == 404
        assert client.get("/api/cases/KHONG-CO/sources/DT-MERO-01").status_code == 404


def test_ai_disabled_via_none_env_or_config_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    disabled_service = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "phan_hoi.jsonl",
        ai_runner=None,
    )
    with TestClient(create_app(disabled_service), raise_server_exceptions=False) as client:
        assert client.post("/api/cases/DEMO-02/ai").json()["trang_thai"] == "tat"
        assert client.get("/api/cases/DEMO-02/ai").json()["trang_thai"] == "tat"
        assert client.post("/api/cases/KHONG-CO/ai").status_code == 404
        assert client.get("/api/cases/KHONG-CO/ai").status_code == 404

    monkeypatch.setenv("CDSS_AI", "off")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-token")
    env_off_service = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "phan_hoi_env.jsonl",
    )
    try:
        assert env_off_service.mode().co_llm is False
        assert env_off_service.start_ai("DEMO-02").trang_thai == "tat"
    finally:
        env_off_service.shutdown()

    monkeypatch.delenv("CDSS_AI", raising=False)
    monkeypatch.setattr(
        "app.llm.setup.build_synthesizer",
        lambda _container: (_ for _ in ()).throw(ConfigError("loi_cau_hinh")),
    )
    err_service = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "phan_hoi_err.jsonl",
    )
    try:
        assert err_service.mode().co_llm is False
    finally:
        err_service.shutdown()

    settings = load_settings("test")
    monkeypatch.setattr(
        "app.llm.setup.build_synthesizer",
        lambda _container: Synthesizer(
            llm=None,
            prompt_path=ROOT / "config/prompts/tong_hop.v1.md",
            case_settings=settings.case_context,
            evidence_max_chars=12000,
            max_synthesis_attempts=1,
            model_name="deepseek-flash",
        ),
    )
    no_llm_service = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "phan_hoi_none.jsonl",
    )
    try:
        assert no_llm_service.mode().co_llm is False
    finally:
        no_llm_service.shutdown()


def test_health_mode_reflects_ai_and_corpus(tmp_path: Path) -> None:
    corpus_file = tmp_path / "chunks.jsonl"
    corpus_file.write_text(_sample_chunk().model_dump_json() + "\n", encoding="utf-8")

    with_corpus = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "fb1.jsonl",
        ai_runner=_FakeAiRunner(),
        corpus_path=corpus_file,
    )
    with TestClient(create_app(with_corpus)) as client:
        che_do = client.get("/api/health").json()["che_do"]
        assert che_do["co_llm"] is True
        assert che_do["truy_xuat"] == "san_sang"
        banner = "Đang chạy không có bước AI: bảng nhận định do bộ luật sinh ra"
        assert banner not in che_do["thong_bao"]

    without_corpus = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "fb2.jsonl",
        ai_runner=_FakeAiRunner(),
        corpus_path=tmp_path / "khong_co.jsonl",
    )
    with TestClient(create_app(without_corpus)) as client:
        che_do = client.get("/api/health").json()["che_do"]
        assert che_do["co_llm"] is True
        assert che_do["truy_xuat"] == "chua_co"


def test_get_case_detail_does_not_block_while_ai_is_running(tmp_path: Path) -> None:
    runner = _FakeAiRunner(delay_seconds=1.0)
    service = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "phan_hoi.jsonl",
        ai_runner=runner,
    )
    with TestClient(create_app(service), raise_server_exceptions=False) as client:
        started = client.post("/api/cases/DEMO-02/ai")
        assert started.status_code == 200
        assert started.json()["trang_thai"] == "dang_chay"

        t0 = time.perf_counter()
        detail = client.get("/api/cases/DEMO-02")
        elapsed = time.perf_counter() - t0
        assert detail.status_code == 200
        assert elapsed < 0.5

        ai_status = client.get("/api/cases/DEMO-02/ai")
        assert ai_status.status_code == 200
        assert ai_status.json()["trang_thai"] == "dang_chay"

        finished = _poll_ai_until_done(client, "DEMO-02", timeout=3.0)
        assert finished["trang_thai"] == "xong"


class _InjectionRunner(_FakeAiRunner):
    """Thêm hai nhận định chỉ thị chèn lệnh: cùng nhận xét cố định, khác bản ghi dẫn chứng."""

    def run(self, ca: CaBenh, ket_qua: KetQuaThamDinh) -> AiRunResult:
        result = super().run(ca, ket_qua)

        def injected(record_id: str) -> NhanDinhCuoi:
            return NhanDinhCuoi(
                nguon_goc="ai_da_kiem_chung",
                de_xuat=NhanDinhDeXuat(
                    chi_tiet_y_lenh_id=[],
                    yeu_to=7,
                    ket_luan="can_xem",
                    muc_do="can_luu_y",
                    nhan_xet="Bệnh án có đoạn văn bản bất thường, giống chỉ thị cho hệ thống",
                    ban_ghi_ids=[record_id],
                    trich_dan=[],
                ),
            )

        llm = result.llm.model_copy(
            update={
                "nhan_dinh": [
                    *result.llm.nhan_dinh,
                    injected("XN-DEMO02-01"),
                    injected("XN-DEMO02-02"),
                ]
            }
        )
        return result.model_copy(update={"llm": llm})


def test_injection_findings_with_same_code_are_merged_not_duplicated(tmp_path: Path) -> None:
    service = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "phan_hoi.jsonl",
        ai_runner=_InjectionRunner(),
    )
    with TestClient(create_app(service), raise_server_exceptions=False) as client:
        assert client.post("/api/cases/DEMO-02/ai").status_code == 200
        finished = _poll_ai_until_done(client, "DEMO-02")
        rows = [*finished["nhan_dinh"]["can_chu_y"], *finished["nhan_dinh"]["dat"]]
        ids = [row["nhan_dinh_id"] for row in rows]
        assert len(ids) == len(set(ids)), "mỗi thẻ nhận định phải có mã duy nhất"
        injected = [r for r in rows if "chỉ thị cho hệ thống" in r["nhan_xet"]]
        assert len(injected) == 1
        records = {item["ban_ghi_id"] for item in injected[0]["can_cu"]}
        assert records == {"XN-DEMO02-01", "XN-DEMO02-02"}
        assert [item["so"] for item in injected[0]["can_cu"]] == [1, 2]
