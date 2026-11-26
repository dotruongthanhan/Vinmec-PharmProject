"""Kiểm thử phân loại nhãn PII (0b) và điều phối 4 luồng trích xuất song song (Giai đoạn 1)."""

from __future__ import annotations

import re
import time
from typing import Any

import pytest

from app import container as container_mod
from app.config.settings import CaseContextSettings
from app.deid.scrubber import TOKEN_PATTERN
from app.domain.loader import ingredients_of
from app.domain.models import CaBenh, ChiTietYLenh
from app.extension_api.extractor import (
    CaseRecalcPatch,
    EditableLabPatch,
    EditableLinePatch,
    EmrSectionPayload,
    SchemaFieldDescriptor,
    apply_case_patch,
    classify_schema_fields,
    extract_to_case,
)
from app.kb.resolver.resolver import KetQuaPhanGiai, ThanhPhanPhanGiai
from app.llm.case_context import build_case_bundle
from app.pipeline import run_case
from app.rules.renal_dose import load_renal_rules


class _FakeSchemaGemini:
    model = "gemini-3.5-flash-lite"

    def __init__(self, *, override_map: dict[str, str] | None = None, fail: bool = False) -> None:
        self.override_map = override_map or {}
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    def complete_json(
        self, system_prompt: str, user_text: str, schema: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        del system_prompt, schema
        self.calls.append({"user_text": user_text})
        if self.fail:
            raise RuntimeError("Mất kết nối Gemini")
        rows = []
        for label, group in self.override_map.items():
            rows.append({"ten_nhan": label, "nhom": group, "ly_do": "Kiểm thử"})
        return {"phan_loai": rows}

    def complete_vision_json(
        self,
        system_prompt: str,
        user_text: str,
        image_bytes: bytes,
        mime_type: str,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise AssertionError("Không gọi Vision ở bước phân loại schema")


class _FakeParallelGemini:
    def __init__(self, model: str, *, delay_s: float = 0.0, with_pii_banner: bool = False) -> None:
        self.model = model
        self.delay_s = delay_s
        self.with_pii_banner = with_pii_banner
        self.seen_texts: list[str] = []

    def complete_json(
        self, system_prompt: str, user_text: str, schema: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        del system_prompt, schema
        self.seen_texts.append(user_text)
        if self.delay_s:
            time.sleep(self.delay_s)
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
                    {"loai": "Cân nặng", "gia_tri": 50.0, "don_vi": "kg"},
                    {"loai": "Chiều cao", "gia_tri": 155.0, "don_vi": "cm"},
                ],
                "xet_nghiem": [
                    {
                        "ma_xet_nghiem": "Serum Creatinine",
                        "ten_xet_nghiem": "Creatinin máu",
                        "gia_tri_so": 212.0,
                        "don_vi": "umol/L",
                        "nguong_duoi": 44.0,
                        "nguong_tren": 80.0,
                    }
                ],
                "vi_sinh": [],
            }
        return {
            "thuoc_dang_dung": [],
            "y_lenh_tu_emr": [],
            "dien_bien": [
                {
                    "loai_ho_so": "dien_bien",
                    "noi_dung": "Creatinin máu tăng sau 3 ngày.",
                }
            ],
        }

    def complete_vision_json(
        self,
        system_prompt: str,
        user_text: str,
        image_bytes: bytes,
        mime_type: str,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del system_prompt, user_text, image_bytes, schema
        assert mime_type == "image/png"
        if self.delay_s:
            time.sleep(self.delay_s)
        return {
            "khoa_ke_don": "Hô hấp",
            "luong_duyet": "truc_tiep",
            "y_lenh": [
                {
                    "ten_thuoc": "Meropenem",
                    "ham_luong": "1 g",
                    "lieu_moi_lan": 1.0,
                    "don_vi_lieu": "g",
                    "duong_dung": "Tĩnh mạch",
                    "tan_suat": "Mỗi 8 giờ",
                    "so_lan_moi_ngay": 3,
                    "khoang_cach_gio": 8.0,
                    "loai_san_pham": "thuoc",
                }
            ],
            "canh_bao_pii_trong_anh": ["ho_ten"] if self.with_pii_banner else [],
        }


def test_schema_pii_floor_overrides_llm_and_defaults_safely() -> None:
    fields = [
        SchemaFieldDescriptor(ten_nhan="Họ và tên", kieu_dom="dt_dd", ngu_canh_muc="I. Hành chính"),
        SchemaFieldDescriptor(ten_nhan="Số CCCD", kieu_dom="dt_dd", ngu_canh_muc="I. Hành chính"),
        SchemaFieldDescriptor(ten_nhan="Tuổi", kieu_dom="dt_dd", ngu_canh_muc="I. Hành chính"),
        SchemaFieldDescriptor(ten_nhan="Cân nặng", kieu_dom="dt_dd", ngu_canh_muc="I. Hành chính"),
        SchemaFieldDescriptor(ten_nhan="Nhãn lạ chưa rõ", kieu_dom="dt_dd", ngu_canh_muc="Khác"),
    ]
    # Cố tình trả sai "lam_sang_giu" cho Họ tên / CCCD để kiểm tra sàn PII bắt buộc.
    fake = _FakeSchemaGemini(
        override_map={
            "Họ và tên": "lam_sang_giu",
            "Số CCCD": "lam_sang_giu",
            "Tuổi": "lam_sang_giu",
            "Cân nặng": "lam_sang_giu",
        }
    )
    out = classify_schema_fields(fields, fake, "config/prompts/ext_schema.v1.md")
    by_name = {item.ten_nhan: item for item in out}

    assert by_name["Họ và tên"].nhom == "pii_xoa"
    assert by_name["Họ và tên"].nguon == "san_pii"
    assert by_name["Số CCCD"].nhom == "pii_xoa"
    assert by_name["Tuổi"].nhom == "lam_sang_giu"
    assert by_name["Cân nặng"].nhom == "lam_sang_giu"
    # Nhãn mô hình bỏ sót tự rơi về nghi_ngo_pii (nguyên tắc an toàn cắt bỏ).
    assert by_name["Nhãn lạ chưa rõ"].nhom == "nghi_ngo_pii"
    assert by_name["Nhãn lạ chưa rõ"].nguon == "mac_dinh_an_toan"


def test_schema_classifier_fallback_on_gemini_failure() -> None:
    fields = [
        SchemaFieldDescriptor(ten_nhan="Chẩn đoán chính", ngu_canh_muc="II. Chẩn đoán"),
        SchemaFieldDescriptor(ten_nhan="Điện thoại", ngu_canh_muc="I. Hành chính"),
    ]
    out = classify_schema_fields(
        fields,
        _FakeSchemaGemini(fail=True),
        "config/prompts/ext_schema.v1.md",
    )
    assert out[0].nhom == "nghi_ngo_pii"
    assert out[1].nhom == "pii_xoa"


def test_parallel_extraction_runs_four_workers_scrubs_pii_and_passes_deterministic_rules() -> None:
    vision = _FakeParallelGemini("gemini-3.6-flash", delay_s=0.05, with_pii_banner=True)
    emr = _FakeParallelGemini("gemini-3.5-flash-lite", delay_s=0.05)

    sections = [
        EmrSectionPayload(
            tieu_de="Hành chính & Chẩn đoán",
            loai_muc="demographics_dx",
            noi_dung=(
                "BN Nữ 75 tuổi. CCCD 001051012345. SĐT 0912345678. Chẩn đoán: J18.9 Viêm phổi."
            ),
        ),
        EmrSectionPayload(
            tieu_de="Sinh hiệu & Xét nghiệm",
            loai_muc="labs_vitals",
            noi_dung="Cân nặng 50 kg, cao 155 cm, Creatinin máu 212 umol/L.",
        ),
        EmrSectionPayload(
            tieu_de="Phiếu điều trị",
            loai_muc="meds_notes",
            noi_dung="BS Nguyễn Văn An khám ngày 10/11/2026: Creatinin tăng.",
        ),
    ]

    t0 = time.perf_counter()
    extracted = extract_to_case(
        ca_id="EXT-DEMO02",
        sections=sections,
        oh_image_bytes=b"\x89PNG\r\n\x1a\nfake",
        oh_image_mime="image/png",
        vision_client=vision,
        emr_client=emr,
        vision_prompt_path="config/prompts/ext_oh_vision.v1.md",
        emr_prompt_path="config/prompts/ext_emr_extract.v1.md",
        max_workers=4,
    )
    elapsed = time.perf_counter() - t0

    # Song song 4 worker: tổng thời gian < 0.16s (nếu nối tiếp 4x0.05 = >=0.20s).
    assert elapsed < 0.19
    assert isinstance(extracted.ca_benh, CaBenh)
    assert extracted.canh_bao_pii_anh == ["ho_ten"]
    # Kiểm tra tầng lọc PII thứ cấp tại server đã che CCCD/SDT/BS trước khi gửi sang Gemini.
    joined_emr_inputs = "\n".join(emr.seen_texts)
    assert "001051012345" not in joined_emr_inputs
    assert "0912345678" not in joined_emr_inputs
    assert "Nguyễn Văn An" not in joined_emr_inputs

    # Kiểm tra kết quả CaBenh chạy đúng qua engine tất định giống DEMO-02.
    result = run_case(extracted.ca_benh, load_renal_rules())
    crcl = next(c for c in result.chi_so if c.cong_thuc == "cockcroft_gault")
    assert crcl.ket_qua is not None
    assert round(crcl.ket_qua, 1) < 30.0
    assert result.phat_hien


def test_extract_requires_at_least_one_pending_drug_line() -> None:
    emr = _FakeParallelGemini("gemini-3.5-flash-lite")
    sections = [
        EmrSectionPayload(
            tieu_de="Hành chính",
            loai_muc="demographics_dx",
            noi_dung="BN Nữ 60 tuổi",
        )
    ]
    with pytest.raises(ValueError, match="y lệnh chờ duyệt"):
        extract_to_case(
            ca_id="EXT-EMPTY",
            sections=sections,
            oh_image_bytes=None,
            oh_image_mime=None,
            vision_client=None,
            emr_client=emr,
            vision_prompt_path="config/prompts/ext_oh_vision.v1.md",
            emr_prompt_path="config/prompts/ext_emr_extract.v1.md",
        )


def test_apply_case_patch_updates_weight_labs_and_order_line() -> None:
    vision = _FakeParallelGemini("gemini-3.6-flash")
    emr = _FakeParallelGemini("gemini-3.5-flash-lite")
    base = extract_to_case(
        ca_id="EXT-PATCH",
        sections=[
            EmrSectionPayload(
                tieu_de="Chẩn đoán",
                loai_muc="demographics_dx",
                noi_dung="BN Nữ 75 tuổi",
            )
        ],
        oh_image_bytes=b"\x89PNG\r\n\x1a\nfake",
        oh_image_mime="image/png",
        vision_client=vision,
        emr_client=emr,
        vision_prompt_path="config/prompts/ext_oh_vision.v1.md",
        emr_prompt_path="config/prompts/ext_emr_extract.v1.md",
    ).ca_benh

    patched = apply_case_patch(
        base,
        CaseRecalcPatch(
            tuoi=70,
            can_nang_kg=62.0,
            tinh_trang_di_ung="co_di_ung",
            xet_nghiem=[
                EditableLabPatch(ma_xet_nghiem="creatinin", gia_tri_so=90.0, don_vi="umol/L")
            ],
            y_lenh=[
                EditableLinePatch(
                    chi_tiet_y_lenh_id="YL-1", lieu_moi_lan=0.5, tan_suat="Mỗi 12 giờ"
                )
            ],
        ),
    )
    assert patched.nguoi_benh.tuoi == 70
    assert patched.tinh_trang_di_ung.trang_thai == "co_di_ung"
    assert len(patched.di_ung) == 1
    assert patched.xet_nghiem[0].gia_tri_so == 90.0
    assert patched.y_lenh_cho_duyet.chi_tiet[0].lieu_moi_lan == 0.5


def test_deterministic_equivalence_demo02_hs019_hs024() -> None:
    """Kiểm chứng extract_to_case -> run_case kích hoạt đúng phát hiện DEMO-02, HS-019, HS-024."""

    class _CaseStubGemini:
        model = "gemini-stub"

        def __init__(
            self,
            demo_payload: dict[str, Any],
            labs_payload: dict[str, Any],
            meds_payload: dict[str, Any],
            oh_payload: dict[str, Any],
        ) -> None:
            self._demo = demo_payload
            self._labs = labs_payload
            self._meds = meds_payload
            self._oh = oh_payload

        def complete_json(
            self, system_prompt: str, user_text: str, schema: dict[str, Any] | None = None
        ) -> dict[str, Any]:
            del system_prompt, schema
            if "nhom_dich = demographics_dx" in user_text:
                return self._demo
            if "nhom_dich = labs_vitals" in user_text:
                return self._labs
            return self._meds

        def complete_vision_json(
            self,
            system_prompt: str,
            user_text: str,
            image_bytes: bytes,
            mime_type: str,
            schema: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            del system_prompt, user_text, image_bytes, mime_type, schema
            return self._oh

    ctx = container_mod.get_rule_context()
    renal_rules = load_renal_rules()
    dummy_sections = [
        EmrSectionPayload(
            tieu_de="Hành chính", loai_muc="demographics_dx", noi_dung="Thông tin chung"
        ),
        EmrSectionPayload(
            tieu_de="Xét nghiệm", loai_muc="labs_vitals", noi_dung="Sinh hiệu và xét nghiệm"
        ),
        EmrSectionPayload(tieu_de="Thuốc", loai_muc="meds_notes", noi_dung="Thuốc đang dùng"),
    ]

    # 1. DEMO-02: Nữ 75 tuổi, 50 kg, Cr 212 umol/L, Meropenem 1g x 3 -> CrCl ~16.0, yếu tố 6.
    demo02 = extract_to_case(
        ca_id="EQ-DEMO02",
        sections=dummy_sections,
        oh_image_bytes=b"\x89PNG\r\n\x1a\nfake",
        oh_image_mime="image/png",
        vision_client=_CaseStubGemini(
            {
                "nguoi_benh": {"tuoi": 75, "gioi_tinh": "nu"},
                "tinh_trang_di_ung": "khong_di_ung_da_hoi",
                "chan_doan": [{"noi_dung": "Viêm phổi", "loai": "chinh"}],
            },
            {
                "sinh_hieu": [
                    {"loai": "can_nang", "gia_tri": 50.0, "don_vi": "kg"},
                    {"loai": "chieu_cao", "gia_tri": 155.0, "don_vi": "cm"},
                ],
                "xet_nghiem": [
                    {
                        "ma_xet_nghiem": "creatinin",
                        "ten_xet_nghiem": "Creatinin",
                        "gia_tri_so": 212.0,
                        "don_vi": "umol/L",
                    }
                ],
            },
            {"thuoc_dang_dung": []},
            {
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
                ]
            },
        ),
        emr_client=_CaseStubGemini(
            {
                "nguoi_benh": {"tuoi": 75, "gioi_tinh": "nu"},
                "tinh_trang_di_ung": "khong_di_ung_da_hoi",
                "chan_doan": [{"noi_dung": "Viêm phổi", "loai": "chinh"}],
            },
            {
                "sinh_hieu": [
                    {"loai": "can_nang", "gia_tri": 50.0, "don_vi": "kg"},
                    {"loai": "chieu_cao", "gia_tri": 155.0, "don_vi": "cm"},
                ],
                "xet_nghiem": [
                    {
                        "ma_xet_nghiem": "creatinin",
                        "ten_xet_nghiem": "Creatinin",
                        "gia_tri_so": 212.0,
                        "don_vi": "umol/L",
                    }
                ],
            },
            {"thuoc_dang_dung": []},
            {},
        ),
        vision_prompt_path="config/prompts/ext_oh_vision.v1.md",
        emr_prompt_path="config/prompts/ext_emr_extract.v1.md",
    ).ca_benh
    res_demo02 = run_case(demo02, renal_rules, resolver=ctx.resolver, interactions=ctx.interactions)
    crcl = next(c for c in res_demo02.chi_so if c.cong_thuc == "cockcroft_gault")
    assert crcl.ket_qua is not None
    assert 15.0 <= crcl.ket_qua <= 17.5
    assert any(f.yeu_to == 6 and f.ket_luan == "can_xem" for f in res_demo02.phat_hien)

    # 2. HS-019: Paracetamol 6 g/ngày (1000 mg x 6 lần/ngày) -> vượt liều tối đa (yếu tố 3).
    hs019_stub = _CaseStubGemini(
        {
            "nguoi_benh": {"tuoi": 45, "gioi_tinh": "nam"},
            "tinh_trang_di_ung": "khong_di_ung_da_hoi",
            "chan_doan": [{"noi_dung": "Sốt", "loai": "chinh"}],
        },
        {"sinh_hieu": [{"loai": "can_nang", "gia_tri": 60.0, "don_vi": "kg"}], "xet_nghiem": []},
        {"thuoc_dang_dung": []},
        {
            "y_lenh": [
                {
                    "ten_thuoc": "Paracetamol 500 mg",
                    "lieu_moi_lan": 1000.0,
                    "don_vi_lieu": "mg",
                    "duong_dung": "Uống",
                    "tan_suat": "Mỗi 4 giờ",
                    "so_lan_moi_ngay": 6,
                    "khoang_cach_gio": 4.0,
                    "loai_san_pham": "thuoc",
                }
            ]
        },
    )
    hs019 = extract_to_case(
        ca_id="EQ-HS019",
        sections=dummy_sections,
        oh_image_bytes=b"\x89PNG\r\n\x1a\nfake",
        oh_image_mime="image/png",
        vision_client=hs019_stub,
        emr_client=hs019_stub,
        vision_prompt_path="config/prompts/ext_oh_vision.v1.md",
        emr_prompt_path="config/prompts/ext_emr_extract.v1.md",
    ).ca_benh

    # Dùng DrugResolver từ ctx hoặc fallback danh_muc_hoat_chat khi chạy offline.
    class _FallbackCatalogResolver:
        def resolve_line(self, ca: CaBenh, line: ChiTietYLenh) -> KetQuaPhanGiai:
            items = [
                ThanhPhanPhanGiai(
                    hoat_chat_id=hc.hoat_chat_id,
                    ten_inn=hc.ten_quoc_te or hc.ten_hoat_chat,
                    ten_viet=hc.ten_hoat_chat,
                    ma_atc=[hc.ma_atc] if hc.ma_atc else [],
                    ddinter_id=None,
                    loai="tan_duoc",
                    ham_luong=line.lieu_moi_lan,
                    don_vi=line.don_vi_lieu,
                )
                for hc in ingredients_of(ca, line)
            ]
            return KetQuaPhanGiai(
                trang_thai="da_phan_giai" if items else "khong_nhan_dien",
                thanh_phan=items,
                nguon_khop="danh_muc_ca" if items else None,
            )

    active_resolver = ctx.resolver or _FallbackCatalogResolver()
    res_hs019 = run_case(
        hs019, renal_rules, resolver=active_resolver, interactions=ctx.interactions
    )
    assert any(f.yeu_to == 3 and f.ket_luan == "can_xem" for f in res_hs019.phat_hien)

    # 3. HS-024: Amiodarone + Digoxin -> tương tác thuốc yếu tố 4 (nếu có CSDL DDInter).
    hs024_stub = _CaseStubGemini(
        {
            "nguoi_benh": {"tuoi": 68, "gioi_tinh": "nam"},
            "tinh_trang_di_ung": "khong_di_ung_da_hoi",
            "chan_doan": [{"noi_dung": "Rung nhĩ", "loai": "chinh"}],
        },
        {"sinh_hieu": [{"loai": "can_nang", "gia_tri": 65.0, "don_vi": "kg"}], "xet_nghiem": []},
        {
            "thuoc_dang_dung": [
                {
                    "ten_thuoc": "Digoxin 0.25 mg",
                    "lieu_moi_lan": 0.25,
                    "don_vi_lieu": "mg",
                    "duong_dung": "Uống",
                    "tan_suat": "1 lần/ngày",
                    "so_lan_moi_ngay": 1,
                    "loai_san_pham": "thuoc",
                }
            ]
        },
        {
            "y_lenh": [
                {
                    "ten_thuoc": "Amiodarone 200 mg",
                    "lieu_moi_lan": 200.0,
                    "don_vi_lieu": "mg",
                    "duong_dung": "Uống",
                    "tan_suat": "2 lần/ngày",
                    "so_lan_moi_ngay": 2,
                    "loai_san_pham": "thuoc",
                }
            ]
        },
    )
    hs024 = extract_to_case(
        ca_id="EQ-HS024",
        sections=dummy_sections,
        oh_image_bytes=b"\x89PNG\r\n\x1a\nfake",
        oh_image_mime="image/png",
        vision_client=hs024_stub,
        emr_client=hs024_stub,
        vision_prompt_path="config/prompts/ext_oh_vision.v1.md",
        emr_prompt_path="config/prompts/ext_emr_extract.v1.md",
    ).ca_benh
    res_hs024 = run_case(hs024, renal_rules, resolver=ctx.resolver, interactions=ctx.interactions)
    resolved_inns = {hc.ten_quoc_te for hc in hs024.danh_muc_hoat_chat}
    assert {"amiodarone", "digoxin"}.issubset(resolved_inns)
    if ctx.interactions is not None and ctx.resolver is not None:
        assert any(f.yeu_to == 4 and f.ket_luan == "can_xem" for f in res_hs024.phat_hien)


def test_extract_handles_client_pre_scrubbed_tokens_and_stage3_context() -> None:
    """Kiểm thử hồi quy: đầu vào có [NGAY_1]/[TEN_1]/[BHYT_1] + Ngày +0/+30 không gây DeidError."""

    class _RelativeDateGemini:
        model = "gemini-3.5-flash-lite"

        def __init__(self) -> None:
            self.seen_texts: list[str] = []

        def complete_json(
            self, system_prompt: str, user_text: str, schema: dict[str, Any] | None = None
        ) -> dict[str, Any]:
            del system_prompt, schema
            self.seen_texts.append(user_text)
            if "nhom_dich = demographics_dx" in user_text:
                return {
                    "nguoi_benh": {"tuoi": 78, "gioi_tinh": "nu"},
                    "dot_dieu_tri": {
                        "khoa_dieu_tri": "Tim mạch",
                        "loai_dieu_tri": "noi_tru",
                        "ngay_tuong_doi": 30,
                        "gio_phut": "09:00",
                    },
                    "tinh_trang_di_ung": "khong_di_ung_da_hoi",
                    "di_ung": [],
                    "chan_doan": [
                        {"ma_icd10": "I48", "noi_dung": "Rung nhĩ [TEN_1]", "loai": "chinh"}
                    ],
                    "co_dia": [],
                }
            if "nhom_dich = labs_vitals" in user_text:
                return {
                    "sinh_hieu": [
                        {
                            "loai": "can_nang",
                            "gia_tri": 56.0,
                            "don_vi": "kg",
                            "ngay_tuong_doi": 30,
                        }
                    ],
                    "xet_nghiem": [
                        {
                            "ma_xet_nghiem": "INR",
                            "ten_xet_nghiem": "INR nền",
                            "gia_tri_so": 1.1,
                            "don_vi": "",
                            "ngay_tuong_doi": 0,
                            "gio_phut": "08:30",
                        },
                        {
                            "ma_xet_nghiem": "INR",
                            "ten_xet_nghiem": "INR tái khám",
                            "gia_tri_so": 2.4,
                            "don_vi": "",
                            "thoi_diem_iso": "Ngày +30 08:00",
                        },
                    ],
                    "vi_sinh": [],
                }
            return {
                "thuoc_dang_dung": [],
                "y_lenh_tu_emr": [
                    {
                        "ten_thuoc": "Warfarin 5 mg",
                        "lieu_moi_lan": 5.0,
                        "don_vi_lieu": "mg",
                        "duong_dung": "Uống",
                        "tan_suat": "1 lần/ngày",
                        "so_lan_moi_ngay": 1,
                        "loai_san_pham": "thuoc",
                    }
                ],
                "dien_bien": [
                    {
                        "loai_ho_so": "dien_bien",
                        "noi_dung": (
                            "Khám lại Ngày +30 cùng BS [TEN_1] từ mốc [NGAY_1], INR ổn định 2.4."
                        ),
                        "ngay_tuong_doi": 30,
                        "gio_phut": "09:00",
                    }
                ],
            }

        def complete_vision_json(
            self,
            system_prompt: str,
            user_text: str,
            image_bytes: bytes,
            mime_type: str,
            schema: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            raise AssertionError("Không cần gọi Vision trong kiểm thử này")

    emr = _RelativeDateGemini()
    sections = [
        EmrSectionPayload(
            tieu_de="Hành chính & Chẩn đoán",
            loai_muc="demographics_dx",
            noi_dung=(
                "BN [TEN_1], thẻ [BHYT_1], mã [ID_1]. Rò rỉ SĐT 0912345678, CCCD 001051012345. "
                "Vào viện Ngày +0, khám lại Ngày +30 09:00."
            ),
        ),
        EmrSectionPayload(
            tieu_de="Xét nghiệm",
            loai_muc="labs_vitals",
            noi_dung="INR Ngày +0 08:30: 1.1; INR Ngày +30 08:00: 2.4 (mốc [NGAY_1]).",
        ),
        EmrSectionPayload(
            tieu_de="Diễn biến",
            loai_muc="meds_notes",
            noi_dung="BS [TEN_1] đánh giá Ngày +30: tiếp tục Warfarin 5 mg uống buổi tối.",
        ),
    ]

    extracted = extract_to_case(
        ca_id="EXT-HS042-DEID",
        sections=sections,
        oh_image_bytes=None,
        oh_image_mime=None,
        vision_client=None,
        emr_client=emr,
        vision_prompt_path="config/prompts/ext_oh_vision.v1.md",
        emr_prompt_path="config/prompts/ext_emr_extract.v1.md",
    )

    # 1. Đầu vào gửi Gemini không còn PII rò rỉ và không còn mã tạm dạng [TEN_1]/[NGAY_1]
    joined_inputs = "\n".join(emr.seen_texts)
    assert "0912345678" not in joined_inputs
    assert "001051012345" not in joined_inputs
    assert not re.search(TOKEN_PATTERN, joined_inputs)
    assert "Ngày +0" in joined_inputs
    assert "Ngày +30" in joined_inputs

    # 2. Chênh lệch mốc ngày tái dựng trong CaBenh đúng chính xác 30 ngày
    ca = extracted.ca_benh
    assert len(ca.xet_nghiem) == 2
    lab_day0, lab_day30 = ca.xet_nghiem[0], ca.xet_nghiem[1]
    assert (lab_day30.thoi_diem_ket_qua.date() - lab_day0.thoi_diem_ket_qua.date()).days == 30
    assert lab_day30.thoi_diem_ket_qua > lab_day0.thoi_diem_ket_qua

    # 3. Chuỗi tự do trong CaBenh sạch TOKEN_PATTERN để Tầng 3 không lỗi che định danh
    assert not re.search(TOKEN_PATTERN, ca.chan_doan[0].noi_dung)
    assert not re.search(TOKEN_PATTERN, ca.dien_bien[0].noi_dung)

    rule_result = run_case(ca, load_renal_rules())
    bundle = build_case_bundle(
        ca, rule_result, CaseContextSettings(max_chars=12000, notes_latest_n=5)
    )
    assert not any("Lỗi che định danh" in w for w in bundle.warnings)
    assert "[không đưa được vào vì lỗi che định danh]" not in bundle.goi.van_ban_ca
    assert "INR ổn định 2.4" in bundle.goi.van_ban_ca
