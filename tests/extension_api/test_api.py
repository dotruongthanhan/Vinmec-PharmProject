"""Kiểm thử API Extension độc lập: cô lập DB nghiep_vu, IDOR 404, pre-body 401/413, magic bytes."""

from __future__ import annotations

import ast
import json
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.auth.errors import AuthError
from app.auth.principal import Principal
from app.config.settings import AuthSettings
from app.core.types import Chunk
from app.domain.models import CaBenh
from app.extension_api.main import create_extension_app
from app.extension_api.service import ExtensionService
from app.llm.schema import KetQuaLLM, NhanDinhCuoi
from app.orchestration.ai_review import AiRunResult
from app.orchestration.ask import AskCitation, AskResult
from app.pipeline import KetQuaThamDinh

_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = _ROOT / "tests/extension_api/fixtures"
_FORBIDDEN_PATIENT_DB_IMPORTS = {
    "app.db.reader",
    "app.db.administrative",
    "app.db.medical_record",
    "app.storage.review_results",
    "app.storage.feedback_chat",
}
_FORBIDDEN_SYMBOLS = {
    "DbReviewService",
    "DbReviewResultStore",
    "DbFeedbackChatStore",
    "FileFeedbackChatStore",
}


class _FakeAuthenticator:
    """Bộ xác thực giả phát JWT cho hai dược sĩ độc lập A và B."""

    def __init__(self) -> None:
        self._tokens = {
            "tok-user-a": Principal(
                nguoi_dung_id="user-a-001",
                email="duocsia@example.org",
                vai_tro="duoc_si_ls",
                phien_id="sess-a",
                het_han_luc=time.time() + 3600,
            ),
            "tok-user-b": Principal(
                nguoi_dung_id="user-b-002",
                email="duocsib@example.org",
                vai_tro="duoc_si_ls",
                phien_id="sess-b",
                het_han_luc=time.time() + 3600,
            ),
        }

    def verify(self, token: str) -> Principal:
        principal = self._tokens.get(token)
        if principal is None:
            raise AuthError("chua_dang_nhap")
        return principal

    def online_check(self, token: str) -> str:
        return self.verify(token).vai_tro


class _FakeGemini:
    def __init__(self, model: str) -> None:
        self.model = model

    def complete_json(
        self, system_prompt: str, user_text: str, schema: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        del system_prompt, schema
        if "nhom_dich" not in user_text:
            return {
                "phan_loai": [
                    {"ten_nhan": "Tuổi", "nhom": "lam_sang_giu", "ly_do": "Tuổi bệnh nhân"},
                    {"ten_nhan": "Cân nặng", "nhom": "lam_sang_giu", "ly_do": "Tính CrCl"},
                ]
            }
        if "nhom_dich = demographics_dx" in user_text:
            return {
                "nguoi_benh": {"tuoi": 75, "gioi_tinh": "nu"},
                "dot_dieu_tri": {"khoa_dieu_tri": "Hô hấp", "loai_dieu_tri": "noi_tru"},
                "tinh_trang_di_ung": "khong_di_ung_da_hoi",
                "di_ung": [],
                "chan_doan": [{"ma_icd10": "J18.9", "noi_dung": "Viêm phổi", "loai": "chinh"}],
                "co_dia": [],
            }
        if "nhom_dich = labs_vitals" in user_text:
            return {
                "sinh_hieu": [
                    {"loai": "can_nang", "gia_tri": 50.0, "don_vi": "kg"},
                    {"loai": "chieu_cao", "gia_tri": 155.0, "don_vi": "cm"},
                ],
                "xet_nghiem": [
                    {
                        "ma_xet_nghiem": "creatinin",
                        "ten_xet_nghiem": "Creatinin máu",
                        "gia_tri_so": 212.0,
                        "don_vi": "umol/L",
                        "nguong_duoi": 44.0,
                        "nguong_tren": 80.0,
                    }
                ],
                "vi_sinh": [],
            }
        return {"thuoc_dang_dung": [], "y_lenh_tu_emr": [], "dien_bien": []}

    def complete_vision_json(
        self,
        system_prompt: str,
        user_text: str,
        image_bytes: bytes,
        mime_type: str,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del system_prompt, user_text, image_bytes, mime_type, schema
        return {
            "khoa_ke_don": "Hô hấp",
            "luong_duyet": "truc_tiep",
            "y_lenh": [
                {
                    "ten_thuoc": "Meropenem 1 g",
                    "lieu_moi_lan": 1.0,
                    "don_vi_lieu": "g",
                    "duong_dung": "Tĩnh mạch",
                    "tan_suat": "Mỗi 8 giờ",
                    "so_lan_moi_ngay": 3,
                    "khoang_cach_gio": 8.0,
                    "loai_san_pham": "thuoc",
                }
            ],
            "canh_bao_pii_trong_anh": [],
        }


class _FakeAiRunner:
    model_name = "deepseek-flash"

    def run(self, ca: CaBenh, ket_qua: KetQuaThamDinh) -> AiRunResult:
        del ca
        # Bất biến 1: giữ đủ mọi phát hiện của bộ luật trong phản hồi LLM.
        items = [
            NhanDinhCuoi(nguon_goc="luat", phat_hien=item, dien_giai=None)
            for item in ket_qua.phat_hien
        ]
        chunk = Chunk(
            doan_trich_id="CHUNK-EXT-1",
            tai_lieu_id="TL-FDA-1",
            muc_cha_id=None,
            nhom_nguon="openfda",
            nguon="openfda",
            tang_tin_cay=1,
            hoat_chat_ids=["HC-MEROPENEM"],
            muc="lieu_than",
            duong_dan_muc="DOSAGE AND ADMINISTRATION",
            loai_noi_dung="van_ban",
            ngon_ngu="vi",
            phien_ban_nguon="v1",
            url_goc="https://dailymed.nlm.nih.gov/dailymed/",
            noi_dung_goc="Điều chỉnh liều meropenem khi CrCl 10-25 mL/min xuống 500 mg q12h.",
            noi_dung_nhung="Điều chỉnh liều meropenem khi CrCl 10-25 mL/min xuống 500 mg q12h.",
        )
        return AiRunResult(
            llm=KetQuaLLM(
                trang_thai="ok",
                nhan_dinh=items,
                so_lan_goi=1,
                canh_bao=[],
                phien_ban_prompt="tong_hop.v1",
                mo_hinh="deepseek-flash",
            ),
            doan=[chunk],
            canh_bao=[],
            thoi_gian_ms=12.5,
        )


class _FakeAsker:
    def ask(
        self,
        ca: CaBenh,
        cau_hoi: str,
        lich_su: list[tuple[str, str]] | None = None,
        *,
        ket_qua: KetQuaThamDinh | None = None,
        ai_result: AiRunResult | None = None,
        nhan_dinh_id: str | None = None,
    ) -> AskResult:
        del ca, ket_qua, ai_result, nhan_dinh_id
        chunk = Chunk(
            doan_trich_id="CHUNK-ASK-1",
            tai_lieu_id="TL-FDA-2",
            muc_cha_id=None,
            nhom_nguon="openfda",
            nguon="openfda",
            tang_tin_cay=1,
            hoat_chat_ids=["HC-MEROPENEM"],
            muc="lieu_than",
            duong_dan_muc="RENAL IMPAIRMENT",
            loai_noi_dung="van_ban",
            ngon_ngu="vi",
            phien_ban_nguon="v1",
            url_goc="https://dailymed.nlm.nih.gov/dailymed/",
            noi_dung_goc="Giảm liều khi CrCl < 26 mL/min.",
            noi_dung_nhung="Giảm liều khi CrCl < 26 mL/min.",
        )
        turn_count = len(lich_su or [])
        return AskResult(
            trang_thai="ok",
            noi_dung=f"Đáp án cho '{cau_hoi}' (lượt trước: {turn_count}) [1].",
            trich_dan=[
                AskCitation(
                    so=1,
                    loai_ma="tai_lieu",
                    nhan="Nhãn FDA · RENAL IMPAIRMENT",
                    doan_trich_id=chunk.doan_trich_id,
                    trich_nguyen_van=chunk.noi_dung_goc,
                )
            ],
            doan=[chunk],
            cong_cu_da_goi=["tim_doan_nguon"],
            thoi_gian_ms=18,
        )


def _build_test_client(*, auth_mode: str = "required") -> tuple[TestClient, ExtensionService]:
    auth_cfg = AuthSettings(
        auth_mode=auth_mode,  # type: ignore[arg-type]
        supabase_url="https://example.supabase.co" if auth_mode == "required" else None,
        supabase_anon_key="anon-key" if auth_mode == "required" else None,
    )
    svc = ExtensionService(
        auth_settings=auth_cfg,
        schema_client=_FakeGemini("gemini-3.5-flash-lite"),
        vision_client=_FakeGemini("gemini-3.6-flash"),
        emr_client=_FakeGemini("gemini-3.5-flash-lite"),
        ai_runner=_FakeAiRunner(),
        asker=_FakeAsker(),
    )
    app = create_extension_app(
        svc,
        auth_settings=auth_cfg,
        auth=_FakeAuthenticator(),
    )
    return TestClient(app), svc


def test_ast_isolation_no_patient_db_or_env_access() -> None:
    """Bảo đảm extension_api và gemini_llm không nhập bất kỳ module DB bệnh nhân hay os.getenv."""
    targets = list((_ROOT / "app/extension_api").rglob("*.py")) + [
        _ROOT / "app/providers/gemini_llm.py"
    ]
    for path in targets:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name not in _FORBIDDEN_PATIENT_DB_IMPORTS
                    assert alias.name != "os"
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert not any(
                    node.module == mod or node.module.startswith(f"{mod}.")
                    for mod in _FORBIDDEN_PATIENT_DB_IMPORTS
                ), f"{path}: Cấm import DB bệnh nhân {node.module}"
                for alias in node.names:
                    assert alias.name not in _FORBIDDEN_SYMBOLS
                    if node.module == "os":
                        raise AssertionError(f"{path}: Cấm import từ os ({alias.name})")


def test_health_reports_zero_retention_and_expected_models() -> None:
    client, _ = _build_test_client(auth_mode="required")
    resp = client.get("/api/extension/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["zero_retention"] is True
    assert body["mo_hinh_trich_xuat"]["schema_classifier"] == "gemini-3.5-flash-lite"
    assert body["mo_hinh_trich_xuat"]["oh_vision"] == "gemini-3.6-flash"
    assert body["mo_hinh_trich_xuat"]["emr_extract"] == "gemini-3.5-flash-lite"
    assert body["mo_hinh_trich_xuat"]["deep_review"] == "deepseek-flash"


def test_prebody_auth_and_dual_body_caps() -> None:
    client, _ = _build_test_client(auth_mode="required")

    # 1. Thiếu token trên payload 1 MB -> bị chặn 401 ngay trước khi đọc thân.
    resp_unauth = client.post(
        "/api/extension/extract-and-review",
        files={"oh_image": ("oh.png", b"A" * 1024, "image/png")},
        data={"emr_json": "{}", "oh_crop_confirmed": "true"},
    )
    assert resp_unauth.status_code == 401

    # 2. Tuyến JSON vượt quá 512 KB bị chặn 413 dù đã đăng nhập.
    oversized_json = json.dumps(
        {
            "schema_hash": "abc123",
            "fields": [{"ten_nhan": "x" * 100, "kieu_dom": "dt_dd"}] * 100,
        }
    )
    assert len(oversized_json) < 600_000
    huge_raw = b'{"schema_hash":"abcd","fields":[' + (b'{"ten_nhan":"a"},' * 40_000) + b"{}]}"
    resp_413_json = client.post(
        "/api/extension/classify-schema",
        headers={
            "Authorization": "Bearer tok-user-a",
            "Content-Type": "application/json",
        },
        content=huge_raw,
    )
    assert resp_413_json.status_code == 413

    # 3. Tuyến multipart ảnh > 8 MB bị chặn 413.
    resp_413_img = client.post(
        "/api/extension/extract-and-review",
        headers={"Authorization": "Bearer tok-user-a"},
        files={"oh_image": ("huge.png", b"\x89PNG\r\n\x1a\n" + b"0" * 8_400_000, "image/png")},
        data={
            "emr_json": json.dumps(
                {"sections": [{"tieu_de": "Hành chính", "noi_dung": "BN 75 tuổi"}]}
            ),
            "oh_crop_confirmed": "true",
        },
    )
    assert resp_413_img.status_code == 413


def test_image_magic_bytes_and_crop_confirmation_validation() -> None:
    client, _ = _build_test_client(auth_mode="required")
    emr_json = json.dumps({"sections": [{"tieu_de": "Chẩn đoán", "noi_dung": "Viêm phổi"}]})

    # Giả mạo đuôi .png nhưng ruột text -> 422.
    corrupt_bytes = (_FIXTURES / "corrupt_not_image.png").read_bytes()
    resp_bad_magic = client.post(
        "/api/extension/extract-and-review",
        headers={"Authorization": "Bearer tok-user-a"},
        files={"oh_image": ("fake.png", corrupt_bytes, "image/png")},
        data={"emr_json": emr_json, "oh_crop_confirmed": "true"},
    )
    assert resp_bad_magic.status_code == 422

    # Ảnh PNG hợp lệ nhưng chưa tích xác nhận đã cắt thanh bệnh nhân -> 422.
    valid_png = (_FIXTURES / "oh_demo02.png").read_bytes()
    resp_unconfirmed = client.post(
        "/api/extension/extract-and-review",
        headers={"Authorization": "Bearer tok-user-a"},
        files={"oh_image": ("oh.png", valid_png, "image/png")},
        data={"emr_json": emr_json, "oh_crop_confirmed": "false"},
    )
    assert resp_unconfirmed.status_code == 422


def test_schema_classifier_rejects_raw_pii_value_422() -> None:
    client, _ = _build_test_client(auth_mode="required")
    for bad_label in (
        "001051012345",
        "0912345678",
        "nguyenvana@example.org",
        "[NGAY_1]",
        "[TEN_1]",
    ):
        resp = client.post(
            "/api/extension/classify-schema",
            headers={"Authorization": "Bearer tok-user-a"},
            json={
                "schema_hash": "hash-bad-label",
                "fields": [{"ten_nhan": bad_label, "kieu_dom": "dt_dd"}],
            },
        )
        assert resp.status_code == 422


def test_extract_and_review_accepts_browser_scrubbed_tokens_and_relative_dates() -> None:
    client, _ = _build_test_client(auth_mode="required")
    headers_a = {"Authorization": "Bearer tok-user-a"}
    valid_png = (_FIXTURES / "oh_demo02.png").read_bytes()
    emr_json = json.dumps(
        {
            "schema_hash": "hash-prescrubbed-v1",
            "tab_count": 2,
            "source_domains": ["localhost:5173"],
            "sections": [
                {
                    "tieu_de": "Thông tin bệnh nhân",
                    "loai_muc": "demographics_dx",
                    "noi_dung": (
                        "Bệnh nhân [TEN_1], 78 tuổi, thẻ [BHYT_1], mã [ID_1]. "
                        "Nhập viện Ngày +0, khám lại Ngày +30 08:00."
                    ),
                },
                {
                    "tieu_de": "Xét nghiệm",
                    "loai_muc": "labs_vitals",
                    "noi_dung": "Cân nặng 50 kg. Creatinin [NGAY_1]: 212 umol/L (Ngày +30 08:00).",
                },
            ],
        }
    )
    resp = client.post(
        "/api/extension/extract-and-review",
        headers=headers_a,
        files={"oh_image": ("oh.png", valid_png, "image/png")},
        data={"emr_json": emr_json, "oh_crop_confirmed": "true"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["zero_retention"] is True
    assert body["session_id"]


def test_full_ephemeral_flow_and_cross_user_idor_returns_404() -> None:
    client, svc = _build_test_client(auth_mode="required")
    headers_a = {"Authorization": "Bearer tok-user-a"}
    headers_b = {"Authorization": "Bearer tok-user-b"}

    # 1. Phân loại nhãn trường (0b).
    resp_schema = client.post(
        "/api/extension/classify-schema",
        headers=headers_a,
        json={
            "schema_hash": "hash-demo-v1",
            "fields": [
                {"ten_nhan": "Họ và tên", "kieu_dom": "dt_dd", "ngu_canh_muc": "I. Hành chính"},
                {"ten_nhan": "Tuổi", "kieu_dom": "dt_dd", "ngu_canh_muc": "I. Hành chính"},
            ],
        },
    )
    assert resp_schema.status_code == 200
    assert resp_schema.json()["fields"][0]["nhom"] == "pii_xoa"
    assert resp_schema.json()["fields"][1]["nhom"] == "lam_sang_giu"

    # 2. Extract + chạy 14 công thức + 14 luật tất định cho User A.
    valid_png = (_FIXTURES / "oh_demo02.png").read_bytes()
    emr_json = json.dumps(
        {
            "schema_hash": "hash-demo-v1",
            "tab_count": 2,
            "source_domains": ["localhost:5173"],
            "sections": [
                {
                    "tieu_de": "Hành chính & Chẩn đoán",
                    "loai_muc": "demographics_dx",
                    "noi_dung": "BN Nữ 75 tuổi. Chẩn đoán J18.9 Viêm phổi.",
                },
                {
                    "tieu_de": "Sinh hiệu & Xét nghiệm",
                    "loai_muc": "labs_vitals",
                    "noi_dung": "Cân nặng 50 kg. Creatinin 212 umol/L.",
                },
            ],
        }
    )
    resp_extract = client.post(
        "/api/extension/extract-and-review",
        headers=headers_a,
        files={"oh_image": ("oh.png", valid_png, "image/png")},
        data={"emr_json": emr_json, "oh_crop_confirmed": "true"},
    )
    assert resp_extract.status_code == 200
    review = resp_extract.json()
    sid = review["session_id"]
    assert review["zero_retention"] is True
    assert review["chi_tiet"]["dinh_danh"]["crcl_bat_thuong"] is True

    # 3. IDOR: User B cố truy cập mọi endpoint trên session của User A -> tất cả phải trả 404.
    assert (
        client.post(
            f"/api/extension/sessions/{sid}/recalc", headers=headers_b, json={"tuoi": 70}
        ).status_code
        == 404
    )
    assert client.post(f"/api/extension/sessions/{sid}/ai", headers=headers_b).status_code == 404
    assert client.get(f"/api/extension/sessions/{sid}/ai", headers=headers_b).status_code == 404
    assert (
        client.post(
            f"/api/extension/sessions/{sid}/ask",
            headers=headers_b,
            json={"cau_hoi": "Liều meropenem thế nào?"},
        ).status_code
        == 404
    )
    assert (
        client.get(f"/api/extension/sessions/{sid}/ask-progress", headers=headers_b).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/extension/sessions/{sid}/sources/CHUNK-EXT-1", headers=headers_b
        ).status_code
        == 404
    )
    assert client.delete(f"/api/extension/sessions/{sid}", headers=headers_b).status_code == 404

    # 4. User A sửa nhanh cân nặng & Creatinin -> chạy lại luật (<50ms).
    resp_recalc = client.post(
        f"/api/extension/sessions/{sid}/recalc",
        headers=headers_a,
        json={
            "can_nang_kg": 70.0,
            "xet_nghiem": [{"ma_xet_nghiem": "creatinin", "gia_tri_so": 55.0, "don_vi": "umol/L"}],
        },
    )
    assert resp_recalc.status_code == 200
    assert resp_recalc.json()["chi_tiet"]["dinh_danh"]["crcl_bat_thuong"] is False

    # 5. User A chạy DeepSeek AI nền & hỏi đáp theo ca + xem nguồn.
    resp_ai = client.post(f"/api/extension/sessions/{sid}/ai", headers=headers_a)
    assert resp_ai.status_code == 200
    for _ in range(25):
        poll = client.get(f"/api/extension/sessions/{sid}/ai", headers=headers_a)
        if poll.json()["trang_thai"] in {"xong", "loi"}:
            break
        time.sleep(0.02)
    assert poll.json()["trang_thai"] == "xong", poll.json()
    assert (
        client.get(
            f"/api/extension/sessions/{sid}/sources/CHUNK-EXT-1", headers=headers_a
        ).status_code
        == 200
    )

    resp_ask = client.post(
        f"/api/extension/sessions/{sid}/ask",
        headers=headers_a,
        json={"cau_hoi": "Cần chỉnh liều thuốc này không?"},
    )
    assert resp_ask.status_code == 200
    assert "Đáp án" in resp_ask.json()["noi_dung"]
    assert (
        client.get(
            f"/api/extension/sessions/{sid}/sources/CHUNK-ASK-1", headers=headers_a
        ).status_code
        == 200
    )

    # 6. User A xoá phiên -> RAM sạch, truy cập lại trả 404.
    assert client.delete(f"/api/extension/sessions/{sid}", headers=headers_a).status_code == 200
    assert svc.session_count() == 0
    assert client.get(f"/api/extension/sessions/{sid}/ai", headers=headers_a).status_code == 404
