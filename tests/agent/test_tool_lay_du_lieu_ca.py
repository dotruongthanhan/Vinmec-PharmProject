"""Kiểm tra dữ liệu thời gian, phân quyền và đường đi tới minh hoạ."""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agent.tools.base import ToolContext
from app.agent.tools.gateway import ToolGateway
from app.agent.tools.lay_du_lieu_ca import LayDuLieuCa, ThamSoLayDuLieuCa
from app.agent.tools.policy import ChinhSachCongCu
from app.agent.tools.registry import DanhMucCongCu
from app.agent.tools.ve_bieu_do import VeBieuDo
from app.config.settings import TracerSettings
from app.container import build_container
from app.deid.known import GiaTriDinhDanh
from app.deid.session import DeidSession
from app.domain.loader import load_case
from app.domain.models import CaBenh, ChiTietYLenh, DienBien, HoatChat, KhangSinhDo, Thuoc, ViSinh
from app.providers.fakes import FakeLLM
from app.rules.d5_config import load_max_dose_config
from app.tracing import Tracer
from tests.agent.test_graph import DEMO_02_PATH, _policy, _run_graph

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def sample_ca() -> CaBenh:
    """Ca hoàn toàn giả với cân nặng và xét nghiệm để kiểm thử."""
    stamp = "2026-01-01T00:00:00+07:00"
    return CaBenh.model_validate(
        {
            "ca_id": "CASE_FAKE_A",
            "mo_ta_ngan": "Ca giả",
            "nguoi_benh": {"nguoi_benh_id": "PATIENT_FAKE_A", "tuoi": 60, "gioi_tinh": "nam"},
            "tinh_trang_di_ung": {"trang_thai": "chua_co_thong_tin"},
            "dot_dieu_tri": {
                "dot_dieu_tri_id": "STAY_FAKE_A",
                "khoa_dieu_tri": "Khoa giả",
                "loai_dieu_tri": "noi_tru",
                "thoi_diem_bat_dau": stamp,
            },
            "sinh_hieu": [
                {
                    "sinh_hieu_id": "WEIGHT",
                    "loai": "can_nang",
                    "gia_tri": 80,
                    "don_vi": "kg",
                    "thoi_diem_do": stamp,
                }
            ],
            "xet_nghiem": [
                {
                    "xet_nghiem_id": "LAB_FAKE",
                    "ma_xet_nghiem": "creatinin",
                    "ten_xet_nghiem": "Creatinin",
                    "gia_tri_so": 1,
                    "don_vi": "mg/dL",
                    "thoi_diem_ket_qua": stamp,
                }
            ],
            "y_lenh_cho_duyet": {
                "y_lenh_id": "ORDER_FAKE",
                "khoa_ke_don": "Khoa giả",
                "luong_duyet": "truc_tiep",
                "thoi_diem_ke": stamp,
                "chi_tiet": [
                    {
                        "chi_tiet_y_lenh_id": "LINE_FAKE",
                        "ten_tu_do": "thuốc giả",
                        "bat_dau": stamp,
                        "trang_thai_dong": "pending",
                    }
                ],
            },
        }
    )


def context(
    ca: CaBenh | None, *, mode: str = "ca", session: DeidSession | None = None
) -> ToolContext:
    return ToolContext(
        vai_tro="duoc_si_ls",
        che_do=mode,  # type: ignore[arg-type]
        han_chot=time.monotonic() + 90,
        cau_hoi_goc="Diễn tiến của ca?",
        ca=ca,
        deid_session=session,
    )


def gateway(limit: int = 10) -> ToolGateway:
    registry = DanhMucCongCu()
    registry.dang_ky(LayDuLieuCa())
    registry.dang_ky(VeBieuDo())
    return ToolGateway(registry, ChinhSachCongCu.tu_tep(ROOT / "config/tool_policy.yaml"), limit)


def run(ca: CaBenh, *parts: str):
    return LayDuLieuCa().chay(ThamSoLayDuLieuCa.model_validate({"phan": parts}), context(ca))


def paracetamol_case(ca: CaBenh) -> CaBenh:
    ca = ca.model_copy(deep=True)
    ca.danh_muc_hoat_chat = [HoatChat(hoat_chat_id="acetaminophen", ten_hoat_chat="paracetamol")]
    ca.danh_muc_thuoc = []
    ca.y_lenh_cho_duyet.chi_tiet = []
    start = datetime.fromisoformat("2026-01-01T22:00:00+07:00")
    for index in range(3):
        drug_id = f"THUOC-{index}"
        ca.danh_muc_thuoc.append(
            Thuoc.model_validate(
                {
                    "thuoc_id": drug_id,
                    "ten_thuoc": f"Chế phẩm giả {index}",
                    "thanh_phan": [
                        {
                            "hoat_chat_id": "acetaminophen",
                            "ham_luong_thanh_phan": 1,
                            "don_vi": "g",
                        }
                    ],
                }
            )
        )
        ca.y_lenh_cho_duyet.chi_tiet.append(
            ChiTietYLenh.model_validate(
                {
                    "chi_tiet_y_lenh_id": f"DONG-{index}",
                    "thuoc_id": drug_id,
                    "lieu_moi_lan": 1,
                    "don_vi_lieu": "viên",
                    "so_lan_moi_ngay": 2,
                    "duong_dung": "uống",
                    "bat_dau": start,
                    "trang_thai_dong": "active",
                    "lich_dung": [
                        {
                            "thoi_diem_du_kien": start + timedelta(hours=index + 4 * j),
                            "lieu": 1,
                            "don_vi": "viên",
                        }
                        for j in range(2)
                    ],
                }
            )
        )
    return ca


def test_demo_creatinin_matches_case_and_manual_flags() -> None:
    case = load_case(DEMO_02_PATH)
    result = LayDuLieuCa().chay(
        ThamSoLayDuLieuCa(phan=["xet_nghiem"], ma_xet_nghiem=["creatinin"]), context(case)
    )
    rows = result.bo_du_lieu[0].dong
    assert result.trang_thai == "ok"
    assert [row["gia_tri"] for row in rows] == [150.0, 212.0]
    assert [row["ngoai_nguong"] for row in rows] == [True, True]
    assert [row["creatinin_tang_nhanh"] for row in rows] == [None, False]
    assert "150" in result.noi_dung and "212" in result.noi_dung


def test_kdigo_converts_units_and_respects_windows(sample_ca: CaBenh) -> None:
    first = sample_ca.xet_nghiem[0]
    first.gia_tri_so, first.don_vi = 1.0, "mg/dL"
    first.thoi_diem_ket_qua = datetime.fromisoformat("2026-01-01T00:00:00+07:00")
    second = first.model_copy(
        update={
            "xet_nghiem_id": "LAB-2",
            "gia_tri_so": 1.3,
            "thoi_diem_ket_qua": first.thoi_diem_ket_qua + timedelta(hours=48),
        }
    )
    third = first.model_copy(
        update={
            "xet_nghiem_id": "LAB-3",
            "gia_tri_so": 150.0,
            "don_vi": "umol/L",
            "thoi_diem_ket_qua": first.thoi_diem_ket_qua + timedelta(days=7),
        }
    )
    sample_ca.xet_nghiem = [third, first, second]
    rows = run(sample_ca, "xet_nghiem").bo_du_lieu[0].dong
    assert [r["creatinin_tang_nhanh"] for r in rows] == [None, True, True]


def test_incomplete_lab_interval_does_not_claim_normal(sample_ca: CaBenh) -> None:
    lab = sample_ca.xet_nghiem[0]
    lab.nguong_duoi = None
    lab.nguong_tren = 2.0
    assert run(sample_ca, "xet_nghiem").bo_du_lieu[0].dong[0]["ngoai_nguong"] is None
    lab.gia_tri_so = 3.0
    assert run(sample_ca, "xet_nghiem").bo_du_lieu[0].dong[0]["ngoai_nguong"] is True


def test_sliding_24h_counts_three_preparations(sample_ca: CaBenh) -> None:
    case = paracetamol_case(sample_ca)
    result = run(case, "lich_dung")
    doses, totals = result.bo_du_lieu
    assert len(doses.dong) == 6
    assert all(row["lieu"] == 1000 for row in doses.dong)
    row = totals.dong[0]
    limits = load_max_dose_config()
    expected = next(
        r.lieu_toi_da_ngay.gia_tri
        for r in limits.nhom
        if r.ma_dong.startswith("acetaminophen|") and r.lieu_toi_da_ngay is not None
    )
    assert row["tong_24h_lon_nhat"] == 6000
    assert row["lieu_toi_da_ngay"] == expected
    assert row["vuot"] is True and row["so_che_pham"] == 3
    assert row["cua_so_tu"] is not None and row["cua_so_den"] is not None


def test_frequency_only_has_no_fabricated_schedule(sample_ca: CaBenh) -> None:
    case = paracetamol_case(sample_ca)
    case.y_lenh_cho_duyet.chi_tiet = case.y_lenh_cho_duyet.chi_tiet[:1]
    case.y_lenh_cho_duyet.chi_tiet[0].lich_dung = []
    doses, totals = run(case, "lich_dung").bo_du_lieu
    assert doses.dong == []
    assert totals.dong[0]["tong_24h_lon_nhat"] == 2000
    assert totals.dong[0]["nguon_lich"] == "suy_tu_tan_suat"
    assert totals.dong[0]["cua_so_tu"] is None


def test_multiple_frequency_only_regimens_use_daily_totals(sample_ca: CaBenh) -> None:
    case = paracetamol_case(sample_ca)
    case.y_lenh_cho_duyet.thoi_diem_ke += timedelta(days=1, hours=12)
    for line in case.y_lenh_cho_duyet.chi_tiet:
        line.lich_dung = []
    doses, totals = run(case, "lich_dung").bo_du_lieu
    assert doses.dong == []
    assert totals.dong[0]["tong_24h_lon_nhat"] == 6000
    assert totals.dong[0]["nguon_lich"] == "suy_tu_tan_suat"
    assert totals.dong[0]["cua_so_tu"] is None


def test_maximum_uses_existing_vietnamese_ingredient_mapping(sample_ca: CaBenh) -> None:
    case = paracetamol_case(sample_ca)
    case.danh_muc_hoat_chat = [
        HoatChat(hoat_chat_id="HC-PARA", ten_hoat_chat="paracetamol", ten_quoc_te="paracetamol")
    ]
    for drug in case.danh_muc_thuoc:
        drug.thanh_phan[0].hoat_chat_id = "HC-PARA"
    total = run(case, "lich_dung").bo_du_lieu[1].dong[0]
    assert total["lieu_toi_da_ngay"] == 4000
    assert total["vuot"] is True


def test_products_with_distinct_case_codes_share_a_resolved_ingredient(sample_ca: CaBenh) -> None:
    case = paracetamol_case(sample_ca)
    case.danh_muc_hoat_chat = []
    for index, drug in enumerate(case.danh_muc_thuoc):
        code = f"HC-PARA-{index}"
        drug.thanh_phan[0].hoat_chat_id = code
        case.danh_muc_hoat_chat.append(
            HoatChat(hoat_chat_id=code, ten_hoat_chat="paracetamol", ten_quoc_te="paracetamol")
        )
    totals = run(case, "lich_dung").bo_du_lieu[1].dong
    assert len(totals) == 1
    assert totals[0]["tong_24h_lon_nhat"] == 6000
    assert totals[0]["lieu_toi_da_ngay"] == 4000


def test_mixed_missing_schedules_do_not_imply_a_maximum(sample_ca: CaBenh) -> None:
    case = paracetamol_case(sample_ca)
    case.y_lenh_cho_duyet.chi_tiet[0].lich_dung = []
    result = run(case, "lich_dung")
    row = result.bo_du_lieu[1].dong[0]
    assert row["tong_24h_lon_nhat"] is None and row["vuot"] is None
    assert "thiếu" in result.noi_dung


def test_schedules_exactly_24_hours_apart_do_not_double_count(sample_ca: CaBenh) -> None:
    case = paracetamol_case(sample_ca)
    case.y_lenh_cho_duyet.chi_tiet = case.y_lenh_cho_duyet.chi_tiet[:1]
    line = case.y_lenh_cho_duyet.chi_tiet[0]
    line.lich_dung[1].thoi_diem_du_kien = line.lich_dung[0].thoi_diem_du_kien + timedelta(hours=24)
    total = run(case, "lich_dung").bo_du_lieu[1].dong[0]
    assert total["tong_24h_lon_nhat"] == 1000


def test_antibiotics_microbiology_and_reference_time(sample_ca: CaBenh) -> None:
    case = paracetamol_case(sample_ca)
    case.danh_muc_thuoc[0].la_khang_sinh = True
    case.y_lenh_cho_duyet.chi_tiet = case.y_lenh_cho_duyet.chi_tiet[:1]
    case.y_lenh_cho_duyet.chi_tiet[0].bat_dau = datetime.fromisoformat("2025-12-30T10:00:00+07:00")
    case.y_lenh_cho_duyet.thoi_diem_ke = datetime.fromisoformat("2026-01-01T11:00:00+07:00")
    case.vi_sinh = [
        ViSinh(
            vi_sinh_id="VS1",
            benh_pham="mẫu giả",
            vi_khuan="vi khuẩn giả",
            thoi_diem_lay_mau=case.y_lenh_cho_duyet.thoi_diem_ke,
            khang_sinh_do=[KhangSinhDo(hoat_chat_id="acetaminophen", ket_qua="S", mic=1)],
        ),
        ViSinh(
            vi_sinh_id="VS2",
            benh_pham="mẫu khác",
            thoi_diem_lay_mau=case.y_lenh_cho_duyet.thoi_diem_ke,
        ),
    ]
    courses, cultures = run(case, "khang_sinh").bo_du_lieu
    assert courses.dong[0]["ngay_thu"] == 3
    assert courses.dong[0]["dang_dung"] is True
    assert courses.dong[0]["chua_bat_dau"] is False
    assert courses.dong[0]["ket_thuc"] is None
    assert [row["ket_qua"] for row in cultures.dong] == ["S", None]
    assert "ngày thứ 3" in run(case, "khang_sinh").noi_dung


def test_future_antibiotic_is_not_reported_as_already_ongoing(sample_ca: CaBenh) -> None:
    case = paracetamol_case(sample_ca)
    case.danh_muc_thuoc[0].la_khang_sinh = True
    case.y_lenh_cho_duyet.chi_tiet = case.y_lenh_cho_duyet.chi_tiet[:1]
    result = run(case, "khang_sinh")
    course = result.bo_du_lieu[0].dong[0]
    assert course["ngay_thu"] is None and course["dang_dung"] is False
    assert course["chua_bat_dau"] is True
    start = case.y_lenh_cho_duyet.chi_tiet[0].bat_dau
    assert course["bat_dau"] == start.isoformat()
    expected = f"chưa bắt đầu (liều đầu dự kiến [NGAY_1] {start:%H:%M}, sau thời điểm kê)"
    assert expected in result.noi_dung
    assert "thiếu" not in result.noi_dung


def test_stopped_antibiotic_summary(sample_ca: CaBenh) -> None:
    case = paracetamol_case(sample_ca)
    case.danh_muc_thuoc[0].la_khang_sinh = True
    case.y_lenh_cho_duyet.chi_tiet = case.y_lenh_cho_duyet.chi_tiet[:1]
    line = case.y_lenh_cho_duyet.chi_tiet[0]
    line.bat_dau = datetime.fromisoformat("2025-12-29T10:00:00+07:00")
    line.ket_thuc = datetime.fromisoformat("2025-12-31T10:00:00+07:00")
    line.trang_thai_dong = "stopped"
    result = run(case, "khang_sinh")
    course = result.bo_du_lieu[0].dong[0]
    assert course["chua_bat_dau"] is False
    assert course["dang_dung"] is False
    assert course["ket_thuc"] == line.ket_thuc.isoformat()
    assert "đã ngưng ngày [NGAY_1]" in result.noi_dung
    assert "thiếu" not in result.noi_dung


def test_missing_component_strength_is_not_assumed(sample_ca: CaBenh) -> None:
    case = paracetamol_case(sample_ca)
    case.danh_muc_thuoc[0].thanh_phan[0].ham_luong_thanh_phan = None
    result = run(case, "lich_dung")
    assert result.bo_du_lieu[0].dong[0]["lieu"] is None
    assert result.bo_du_lieu[1].dong[0]["tong_24h_lon_nhat"] is None
    assert "thiếu" in result.noi_dung


def test_unknown_free_text_drug_is_reported_missing(sample_ca: CaBenh) -> None:
    result = run(sample_ca, "lich_dung")
    assert "thiếu: thanh_phan" in result.noi_dung
    assert result.bo_du_lieu[1].dong == []


def test_evidence_text_does_not_leak_pii(sample_ca: CaBenh) -> None:
    sample_ca.sinh_hieu[0].loai = "Giả Lập Sao 0900000000"
    session = DeidSession(
        [
            GiaTriDinhDanh(loai="TEN", gia_tri="Giả Lập Sao"),
            GiaTriDinhDanh(loai="SDT", gia_tri="0900000000"),
        ]
    )
    result = gateway().goi(
        "lay_du_lieu_ca", {"phan": ["sinh_hieu"]}, context(sample_ca, session=session)
    )
    payload = json.dumps(result.model_dump(), ensure_ascii=False)
    assert "Giả Lập Sao" not in payload and "0900000000" not in payload


def test_timeline_excludes_free_text_and_gateway_masks_pii(sample_ca: CaBenh) -> None:
    case = paracetamol_case(sample_ca)
    case.y_lenh_cho_duyet.chi_tiet[0].ten_tu_do = "Giả Lập Sao 0900000000"
    case.dien_bien = [
        DienBien(
            dien_bien_id="DB1",
            loai_ho_so="phiếu giả",
            noi_dung="CANARY_DIENBIEN",
            thoi_diem_ghi=case.dot_dieu_tri.thoi_diem_bat_dau,
        )
    ]
    from app.domain.models import ChanDoan

    case.chan_doan = [ChanDoan(chan_doan_id="CD1", noi_dung="CANARY_CHANDOAN", loai="chinh")]
    session = DeidSession(
        [
            GiaTriDinhDanh(loai="TEN", gia_tri="Giả Lập Sao"),
            GiaTriDinhDanh(loai="SDT", gia_tri="0900000000"),
        ]
    )
    gw = gateway()
    result = gw.goi(
        "lay_du_lieu_ca", {"phan": ["moc_ca", "lich_dung"]}, context(case, session=session)
    )
    payload = json.dumps(result.model_dump(), ensure_ascii=False)
    assert result.trang_thai == "ok" and len(result.bo_du_lieu) == 3
    for forbidden in ("CANARY_DIENBIEN", "CANARY_CHANDOAN", "Giả Lập Sao", "0900000000"):
        assert forbidden not in payload
    spec = {
        "phien_ban": "mh-1",
        "tieu_de": "Mốc ca",
        "lop": [
            {
                "dau": "diem",
                "du_lieu": "ds-1",
                "ma_hoa": {"x": {"cot": "thoi_diem"}, "y": {"cot": "loai"}},
            }
        ],
        "nguon": ["ca:moc_ca"],
    }
    assert gw.goi("ve_bieu_do", {"dac_ta": spec}, context(case, session=session)).trang_thai == "ok"
    block = json.dumps(gw.minh_hoa[0].model_dump(), ensure_ascii=False)
    for forbidden in ("CANARY_DIENBIEN", "CANARY_CHANDOAN", "Giả Lập Sao", "0900000000"):
        assert forbidden not in block


@pytest.mark.parametrize(
    "params",
    [
        {"phan": ["xet_nghiem"], "ca_id": "CA-KHAC"},
        {"phan": []},
        {"phan": ["khong_co"]},
        {"phan": ["moc_ca", "moc_ca"]},
        {"phan": ["xet_nghiem"], "ma_xet_nghiem": ["'; drop"]},
        {"phan": ["xet_nghiem"], "ma_xet_nghiem": ["<"]},
        {"phan": ["sinh_hieu"], "loai_sinh_hieu": ["x" * 33]},
        {"phan": ["sinh_hieu"], "loai_sinh_hieu": ["x"] * 11},
    ],
)
def test_invalid_parameters(params: dict) -> None:
    with pytest.raises(ValidationError):
        ThamSoLayDuLieuCa.model_validate(params)


def test_scope_policy_and_budget(sample_ca: CaBenh) -> None:
    tool = LayDuLieuCa()
    assert tool.chay(ThamSoLayDuLieuCa(phan=["xet_nghiem"]), context(None)).ma_loi == "sai_tham_so"
    gw = gateway(limit=1)
    assert (
        gw.goi(tool.ten, {"phan": ["xet_nghiem"]}, context(sample_ca, mode="chung")).trang_thai
        == "tu_choi"
    )
    assert gw.goi(tool.ten, {"phan": ["xet_nghiem"]}, context(sample_ca)).trang_thai == "ok"
    assert gw.goi(tool.ten, {"phan": ["xet_nghiem"]}, context(sample_ca)).ma_loi == "het_ngan_sach"
    asker = build_container("test").agentic_asker
    assert asker._danh_muc.lay(tool.ten) is not None
    assert asker._chinh_sach.cho_phep("admin", "ca", tool.ten)
    assert not asker._chinh_sach.cho_phep("duoc_si_ls", "chung", tool.ten)


def test_tool_reads_only_current_case(sample_ca: CaBenh) -> None:
    other = sample_ca.model_copy(deep=True)
    other.ca_id = "CASE_FAKE_B"
    other.xet_nghiem[0].gia_tri_so = 999
    ctx = ToolContext(
        vai_tro="duoc_si_ls",
        che_do="ca",
        han_chot=time.monotonic() + 30,
        cau_hoi_goc="Xét nghiệm?",
        ca=sample_ca,
        cac_ca=(sample_ca, other),
    )
    result = LayDuLieuCa().chay(ThamSoLayDuLieuCa(phan=["xet_nghiem"]), ctx)
    assert result.bo_du_lieu[0].dong[0]["gia_tri"] == 1
    assert "999" not in result.model_dump_json()


def test_latest_2000_and_trace(sample_ca: CaBenh, tmp_path: Path) -> None:
    base = sample_ca.xet_nghiem[0]
    sample_ca.xet_nghiem = [
        base.model_copy(
            update={
                "xet_nghiem_id": f"XN-{i}",
                "gia_tri_so": float(i),
                "thoi_diem_ket_qua": base.thoi_diem_ket_qua + timedelta(minutes=i),
            }
        )
        for i in reversed(range(2500))
    ]
    tracer = Tracer(TracerSettings(thu_muc=str(tmp_path), muc_noi_dung="sieu_du_lieu"))
    with tracer.bat_dau_vet("hoi_dap", "agentic") as vet:
        assert vet is not None
        result = gateway().goi("lay_du_lieu_ca", {"phan": ["xet_nghiem"]}, context(sample_ca))
        record = vet.chot()
    tracer.close()
    assert result.trang_thai == "ok"
    rows = result.bo_du_lieu[0].dong
    assert len(rows) == 2000 and rows[0]["gia_tri"] == 500 and rows[-1]["gia_tri"] == 2499
    assert any(s.thuoc_tinh.get("so_dong_bi_cat") == 500 for s in record.cac_buoc)


def test_agent_graph_returns_verified_timeline() -> None:
    reg = DanhMucCongCu()
    reg.dang_ky(LayDuLieuCa())
    reg.dang_ky(VeBieuDo())
    milestones = run(load_case(DEMO_02_PATH), "moc_ca").bo_du_lieu[0].dong
    order_row = next(i for i, row in enumerate(milestones) if row["loai"] == "y_lenh")
    spec = {
        "phien_ban": "mh-1",
        "tieu_de": "Diễn tiến creatinin",
        "lop": [
            {
                "dau": "duong",
                "du_lieu": "ds-1",
                "ma_hoa": {
                    "x": {"cot": "thoi_diem", "kieu": "thoi_gian"},
                    "y": {"cot": "gia_tri", "kieu": "dinh_luong"},
                },
            },
            {
                "dau": "quy_tac",
                "du_lieu": "ds-2",
                "ma_hoa": {"x": {"o": {"ds": "ds-2", "cot": "thoi_diem", "dong": order_row}}},
            },
        ],
        "nguon": ["ca:xet_nghiem", "ca:moc_ca"],
    }
    sequence = [
        {
            "hanh_dong": "goi_cong_cu",
            "goi": [
                {
                    "cong_cu": "lay_du_lieu_ca",
                    "tham_so": {
                        "phan": ["xet_nghiem", "moc_ca"],
                        "ma_xet_nghiem": ["creatinin"],
                    },
                }
            ],
        },
        {
            "hanh_dong": "goi_cong_cu",
            "goi": [{"cong_cu": "ve_bieu_do", "tham_so": {"dac_ta": spec}}],
        },
        {
            "hanh_dong": "tra_loi",
            "tra_loi": {
                "pham_vi": "trong",
                "tra_loi": "Creatinin tăng từ 150 lên 212 umol/L [1].",
                "trich_dan": [{"so": 1, "loai": "bang", "ma": "ca:xet_nghiem"}],
            },
        },
    ]
    result, _, _ = _run_graph(
        FakeLLM(sequence),
        "Creatinin diễn tiến thế nào?",
        danh_muc=reg,
        chinh_sach=_policy(["lay_du_lieu_ca", "ve_bieu_do"]),
    )
    assert result.trang_thai == "ok" and len(result.minh_hoa) == 1

    assert [row["gia_tri"] for row in result.minh_hoa[0].bo_du_lieu[0].dong] == [150, 212]
    assert [layer["dau"] for layer in result.minh_hoa[0].dac_ta["lop"]] == ["duong", "quy_tac"]
    original = run(load_case(DEMO_02_PATH), "xet_nghiem").bo_du_lieu[0].dong
    for row, source in zip(result.minh_hoa[0].bo_du_lieu[0].dong, original, strict=False):
        assert datetime.fromisoformat(row["thoi_diem"]) == datetime.fromisoformat(
            source["thoi_diem"]
        )


def test_gateway_timeline_keeps_dates_out_of_llm_and_masks_other_cells(sample_ca: CaBenh) -> None:
    case = paracetamol_case(sample_ca)
    case.y_lenh_cho_duyet.chi_tiet[0].ten_tu_do = "Giả Lập Sao 0900000000"
    session = DeidSession([GiaTriDinhDanh(loai="TEN", gia_tri="Giả Lập Sao")])
    result = gateway().goi(
        "lay_du_lieu_ca", {"phan": ["lich_dung"]}, context(case, session=session)
    )
    original = run(case, "lich_dung").bo_du_lieu
    assert "2026-01-01" not in result.noi_dung
    for actual, expected in zip(result.bo_du_lieu, original, strict=True):
        for col in actual.cot:
            if col.kieu == "thoi_gian":
                for row, source in zip(actual.dong, expected.dong, strict=True):
                    if source.get(col.ten) is not None:
                        assert datetime.fromisoformat(row[col.ten]) == datetime.fromisoformat(
                            source[col.ten]
                        )
    payload = json.dumps([d.model_dump() for d in result.bo_du_lieu], ensure_ascii=False)
    assert "Giả Lập Sao" not in payload and "0900000000" not in payload


def test_agent_graph_verifies_calculated_daily_dose() -> None:
    reg = DanhMucCongCu()
    reg.dang_ky(LayDuLieuCa())
    reg.dang_ky(VeBieuDo())
    spec = {
        "phien_ban": "mh-1",
        "tieu_de": "Tổng liều",
        "lop": [
            {
                "dau": "cot",
                "du_lieu": "ds-2",
                "ma_hoa": {
                    "x": {"cot": "hoat_chat", "kieu": "danh_muc"},
                    "y": {"cot": "tong_24h_lon_nhat", "kieu": "dinh_luong"},
                },
            }
        ],
        "nguon": ["tinh:lich_dung"],
    }
    sequence = [
        {
            "hanh_dong": "goi_cong_cu",
            "goi": [{"cong_cu": "lay_du_lieu_ca", "tham_so": {"phan": ["lich_dung"]}}],
        },
        {
            "hanh_dong": "goi_cong_cu",
            "goi": [{"cong_cu": "ve_bieu_do", "tham_so": {"dac_ta": spec}}],
        },
        {
            "hanh_dong": "tra_loi",
            "tra_loi": {
                "pham_vi": "trong",
                "tra_loi": (
                    "Tổng liều meropenem trong 24 giờ là **3.000 mg** "
                    "(3 liều 1.000 mg lúc 06:00, 14:00, 22:00) [1]."
                ),
                "trich_dan": [{"so": 1, "loai": "tinh_toan", "ma": "tinh:lich_dung"}],
            },
        },
    ]
    result, _, _ = _run_graph(
        FakeLLM(sequence),
        "Tổng liều meropenem trong 24 giờ?",
        danh_muc=reg,
        chinh_sach=_policy(["lay_du_lieu_ca", "ve_bieu_do"]),
    )
    assert result.trang_thai == "ok" and len(result.minh_hoa) == 1
    invalid = json.loads(json.dumps(sequence))
    invalid[-1]["tra_loi"]["tra_loi"] = "Tổng liều 999999 mg [1]."
    invalid.append(invalid[-1])
    rejected, _, _ = _run_graph(
        FakeLLM(invalid),
        "Tổng liều meropenem trong 24 giờ?",
        danh_muc=reg,
        chinh_sach=_policy(["lay_du_lieu_ca", "ve_bieu_do"]),
    )
    assert rejected.trang_thai != "ok" and not rejected.minh_hoa


def test_all_case_columns_have_labels(sample_ca: CaBenh) -> None:
    result = run(sample_ca, "xet_nghiem", "sinh_hieu", "lich_dung", "khang_sinh", "moc_ca")
    assert len(result.bo_du_lieu) == 7
    assert all(column.nhan for dataset in result.bo_du_lieu for column in dataset.cot)
