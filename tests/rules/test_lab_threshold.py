"""Kiểm thử luật yếu tố 6: ngưỡng xét nghiệm theo nhãn FDA và quy đổi đơn vị."""

import re
from datetime import timedelta
from pathlib import Path

import pytest

from app.domain.models import CaBenh, ChiTietYLenh, KetQuaXetNghiem
from app.kb.resolver.resolver import KetQuaPhanGiai, ThanhPhanPhanGiai
from app.rules.d4_config import (
    D4SourceDetail,
    LabCondition,
    LabThresholdConfig,
    LabThresholdRule,
    load_lab_threshold_config,
)
from app.rules.lab_threshold import check
from tests.rules import NOW, make_minimal_case

_REAL_PATH = Path(__file__).resolve().parents[2] / "data" / "kb" / "nguong_xet_nghiem.json"


class _FakeResolver:
    """Bộ phân giải giả cho test đơn vị."""

    def __init__(self, mapping: dict[str, KetQuaPhanGiai]) -> None:
        self._mapping = mapping

    def resolve_line(self, ca: CaBenh, line: ChiTietYLenh) -> KetQuaPhanGiai:
        return self._mapping.get(
            line.chi_tiet_y_lenh_id,
            KetQuaPhanGiai(trang_thai="khong_nhan_dien"),
        )


def _tp(hoat_chat_id: str, ten_inn: str) -> ThanhPhanPhanGiai:
    return ThanhPhanPhanGiai(
        hoat_chat_id=hoat_chat_id,
        ten_inn=ten_inn,
        ten_viet=None,
        ma_atc=[],
        ddinter_id=None,
        loai="thuoc",
    )


def _src(drug: str = "FDA Drug", set_id: str = "set-lab-1") -> D4SourceDetail:
    return D4SourceDetail(
        loai="nhan_fda",
        ten_nhan=drug,
        set_id=set_id,
        trich_nguyen_van="lab threshold excerpt",
        url=f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={set_id}",
    )


def test_lab_canh_bao_khi_thoa_positive_and_negative() -> None:
    """Kiểu canh_bao_khi_thoa: INR > 4.0 cảnh báo khi 4.5 và đạt khi 2.5."""
    cfg = LabThresholdConfig(
        quy_tac=(
            LabThresholdRule(
                ten_quoc_te="warfarin",
                hoat_chat_ids=("warfarin",),
                xet_nghiem="inr",
                dieu_kien=(
                    LabCondition(
                        ma_xet_nghiem="inr",
                        toan_tu=">",
                        gia_tri=4.0,
                        don_vi_nhan="",
                        don_vi_ca="",
                        he_so_ca_sang_nhan=1.0,
                    ),
                ),
                hanh_dong_nhan="INR > 4,0 tăng nguy cơ chảy máu",
                kieu_dieu_kien="canh_bao_khi_thoa",
                muc_do_de_xuat="nghiem_trong",
                nguon_chi_tiet=(_src("Warfarin"),),
            ),
        )
    )
    resolver = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("warfarin", "Warfarin")],
            ),
        }
    )

    ca_pos = make_minimal_case(
        xet_nghiem=[
            KetQuaXetNghiem(
                xet_nghiem_id="XN-INR-HIGH",
                ma_xet_nghiem="inr",
                ten_xet_nghiem="INR",
                gia_tri_so=4.5,
                don_vi=None,
                thoi_diem_ket_qua=NOW,
            )
        ]
    )
    f_pos = check(ca_pos, resolver, cfg)
    assert len(f_pos) == 1
    assert f_pos[0].ma_luat == "xet_nghiem_vuot_nguong"
    assert f_pos[0].ket_luan == "can_xem"
    assert f_pos[0].muc_do == "nghiem_trong"

    ca_neg = make_minimal_case(
        xet_nghiem=[
            KetQuaXetNghiem(
                xet_nghiem_id="XN-INR-OK",
                ma_xet_nghiem="inr",
                ten_xet_nghiem="INR",
                gia_tri_so=2.5,
                don_vi="",
                thoi_diem_ket_qua=NOW,
            )
        ]
    )
    f_neg = check(ca_neg, resolver, cfg)
    assert len(f_neg) == 1
    assert f_neg[0].ma_luat == "xet_nghiem_trong_nguong"
    assert f_neg[0].ket_luan == "dat"
    assert f_neg[0].muc_do == "thong_tin"


def test_lab_canh_bao_khi_ngoai_khoang_positive_and_negative() -> None:
    """Kiểu canh_bao_khi_ngoai_khoang: phenytoin 10-20 cảnh báo khi 8.0 và đạt khi 15.0."""
    cfg = LabThresholdConfig(
        quy_tac=(
            LabThresholdRule(
                ten_quoc_te="phenytoin",
                hoat_chat_ids=("phenytoin",),
                xet_nghiem="phenytoin",
                dieu_kien=(
                    LabCondition(
                        ma_xet_nghiem="phenytoin",
                        toan_tu="khoang",
                        gia_tri=10.0,
                        gia_tri_den=20.0,
                        don_vi_nhan="mcg/mL",
                        don_vi_ca="mcg/mL",
                        he_so_ca_sang_nhan=1.0,
                    ),
                ),
                hanh_dong_nhan="Khoảng điều trị thường gặp 10–20 mcg/mL",
                kieu_dieu_kien="canh_bao_khi_ngoai_khoang",
                muc_do_de_xuat="can_luu_y",
                nguon_chi_tiet=(_src("Phenytoin"),),
            ),
        )
    )
    resolver = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("phenytoin", "Phenytoin")],
            )
        }
    )

    ca_out = make_minimal_case(
        xet_nghiem=[
            KetQuaXetNghiem(
                xet_nghiem_id="XN-PHE-LOW",
                ma_xet_nghiem="phenytoin",
                ten_xet_nghiem="Phenytoin máu",
                gia_tri_so=8.0,
                don_vi="mcg/mL",
                thoi_diem_ket_qua=NOW,
            )
        ]
    )
    f_out = check(ca_out, resolver, cfg)
    assert len(f_out) == 1
    assert f_out[0].ma_luat == "xet_nghiem_vuot_nguong"
    assert f_out[0].ket_luan == "can_xem"
    assert f_out[0].muc_do == "can_luu_y"

    ca_in = make_minimal_case(
        xet_nghiem=[
            KetQuaXetNghiem(
                xet_nghiem_id="XN-PHE-OK",
                ma_xet_nghiem="phenytoin",
                ten_xet_nghiem="Phenytoin máu",
                gia_tri_so=15.0,
                don_vi="mcg/mL",
                thoi_diem_ket_qua=NOW,
            )
        ]
    )
    f_in = check(ca_in, resolver, cfg)
    assert len(f_in) == 1
    assert f_in[0].ma_luat == "xet_nghiem_trong_nguong"
    assert f_in[0].ket_luan == "dat"


def test_lab_dieu_kien_khoi_dau_positive_and_negative() -> None:
    """Kiểu dieu_kien_khoi_dau: đạt khi mọi điều kiện đúng, cảnh báo khi có điều kiện sai."""
    cfg = LabThresholdConfig(
        quy_tac=(
            LabThresholdRule(
                ten_quoc_te="spironolactone",
                hoat_chat_ids=("spironolactone",),
                xet_nghiem="kali",
                dieu_kien=(
                    LabCondition(
                        ma_xet_nghiem="kali",
                        toan_tu="<=",
                        gia_tri=5.0,
                        don_vi_nhan="mEq/L",
                        don_vi_ca="mmol/L",
                        he_so_ca_sang_nhan=1.0,
                    ),
                    LabCondition(
                        ma_xet_nghiem="egfr",
                        toan_tu=">",
                        gia_tri=50.0,
                        don_vi_nhan="mL/min/1.73m2",
                        don_vi_ca="mL/phút/1,73m2",
                        he_so_ca_sang_nhan=1.0,
                    ),
                ),
                hanh_dong_nhan="Khởi đầu spironolacton khi K+ <= 5,0 và eGFR > 50",
                kieu_dieu_kien="dieu_kien_khoi_dau",
                muc_do_de_xuat="nghiem_trong",
                nguon_chi_tiet=(_src("Spironolactone"),),
            ),
        )
    )
    resolver = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("spironolactone", "Spironolactone")],
            )
        }
    )

    ca_ok = make_minimal_case(
        xet_nghiem=[
            KetQuaXetNghiem(
                xet_nghiem_id="XN-K-OK",
                ma_xet_nghiem="kali",
                ten_xet_nghiem="Kali máu",
                gia_tri_so=4.2,
                don_vi="mmol/L",
                thoi_diem_ket_qua=NOW,
            ),
            KetQuaXetNghiem(
                xet_nghiem_id="XN-EGFR-OK",
                ma_xet_nghiem="egfr",
                ten_xet_nghiem="eGFR",
                gia_tri_so=65.0,
                don_vi="mL/phút/1,73m2",
                thoi_diem_ket_qua=NOW,
            ),
        ]
    )
    f_ok = check(ca_ok, resolver, cfg)
    assert len(f_ok) == 1
    assert f_ok[0].ket_luan == "dat"

    ca_fail = make_minimal_case(
        xet_nghiem=[
            KetQuaXetNghiem(
                xet_nghiem_id="XN-K-HIGH",
                ma_xet_nghiem="kali",
                ten_xet_nghiem="Kali máu",
                gia_tri_so=5.8,
                don_vi="mmol/L",
                thoi_diem_ket_qua=NOW,
            ),
            KetQuaXetNghiem(
                xet_nghiem_id="XN-EGFR-OK",
                ma_xet_nghiem="egfr",
                ten_xet_nghiem="eGFR",
                gia_tri_so=65.0,
                don_vi="mL/phút/1,73m2",
                thoi_diem_ket_qua=NOW,
            ),
        ]
    )
    f_fail = check(ca_fail, resolver, cfg)
    assert len(f_fail) == 1
    assert f_fail[0].ma_luat == "xet_nghiem_vuot_nguong"
    assert f_fail[0].ket_luan == "can_xem"
    assert f_fail[0].muc_do == "nghiem_trong"


def test_lab_creatinine_unit_conversion_150_umol_to_mg_dl() -> None:
    """Đổi 150 µmol/L x 0.011312 = 1.6968 > 1.6 mg/dL -> cảnh báo đúng giá trị quy đổi."""
    cfg = LabThresholdConfig(
        quy_tac=(
            LabThresholdRule(
                ten_quoc_te="enalapril",
                hoat_chat_ids=("enalapril",),
                xet_nghiem="creatinin",
                dieu_kien=(
                    LabCondition(
                        ma_xet_nghiem="creatinin",
                        toan_tu=">",
                        gia_tri=1.6,
                        don_vi_nhan="mg/dL",
                        don_vi_ca="umol/L",
                        he_so_ca_sang_nhan=0.011312,
                    ),
                ),
                hanh_dong_nhan="Creatinin > 1,6 mg/dL: khởi đầu 2,5 mg/ngày",
                kieu_dieu_kien="canh_bao_khi_thoa",
                muc_do_de_xuat="can_luu_y",
                nguon_chi_tiet=(_src("Enalapril"),),
            ),
        )
    )
    resolver = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("enalapril", "Enalapril")],
            )
        }
    )
    ca = make_minimal_case(
        xet_nghiem=[
            KetQuaXetNghiem(
                xet_nghiem_id="XN-CR-150",
                ma_xet_nghiem="creatinin",
                ten_xet_nghiem="Creatinin máu",
                gia_tri_so=150.0,
                don_vi="µmol/L",
                thoi_diem_ket_qua=NOW,
            )
        ]
    )
    findings = check(ca, resolver, cfg)
    assert len(findings) == 1
    f = findings[0]
    assert f.ma_luat == "xet_nghiem_vuot_nguong"
    assert f.ket_luan == "can_xem"
    assert "150" in f.mo_ta
    assert "1.697" in f.mo_ta
    assert "1.6" in f.mo_ta


def test_lab_unit_mismatch_returns_missing_with_don_vi_suffix() -> None:
    """Đơn vị ca lệch so với don_vi_ca -> khong_du_du_lieu có hậu tố _don_vi và muc_do=None."""
    cfg = LabThresholdConfig(
        quy_tac=(
            LabThresholdRule(
                ten_quoc_te="enoxaparin",
                hoat_chat_ids=("enoxaparin",),
                xet_nghiem="tieu_cau",
                dieu_kien=(
                    LabCondition(
                        ma_xet_nghiem="tieu_cau",
                        toan_tu="<",
                        gia_tri=100000.0,
                        don_vi_nhan="/mm3",
                        don_vi_ca="G/L",
                        he_so_ca_sang_nhan=1000.0,
                    ),
                ),
                hanh_dong_nhan="Ngừng nếu tiểu cầu < 100.000/mm3",
                kieu_dieu_kien="canh_bao_khi_thoa",
                muc_do_de_xuat="nghiem_trong",
                nguon_chi_tiet=(_src("Enoxaparin"),),
            ),
        )
    )
    resolver = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("enoxaparin", "Enoxaparin")],
            )
        }
    )
    ca = make_minimal_case(
        xet_nghiem=[
            KetQuaXetNghiem(
                xet_nghiem_id="XN-PLT",
                ma_xet_nghiem="tieu_cau",
                ten_xet_nghiem="Tiểu cầu",
                gia_tri_so=120.0,
                don_vi="mg/dL",
                thoi_diem_ket_qua=NOW,
            )
        ]
    )
    findings = check(ca, resolver, cfg)
    assert len(findings) == 1
    assert findings[0].ma_luat == "xet_nghiem_thieu"
    assert findings[0].ket_luan == "khong_du_du_lieu"
    assert findings[0].muc_do is None
    assert findings[0].thong_tin_con_thieu == ["tieu_cau_don_vi"]


def test_lab_missing_result_returns_khong_du_du_lieu() -> None:
    """Không có xét nghiệm tương ứng -> khong_du_du_lieu với muc_do=None."""
    cfg = LabThresholdConfig(
        quy_tac=(
            LabThresholdRule(
                ten_quoc_te="metformin",
                hoat_chat_ids=("metformin",),
                xet_nghiem="egfr",
                dieu_kien=(
                    LabCondition(
                        ma_xet_nghiem="egfr",
                        toan_tu="<",
                        gia_tri=30.0,
                        don_vi_nhan="mL/min/1.73m2",
                        don_vi_ca="mL/phút/1,73m2",
                        he_so_ca_sang_nhan=1.0,
                    ),
                ),
                hanh_dong_nhan="Chống chỉ định khi eGFR < 30",
                kieu_dieu_kien="canh_bao_khi_thoa",
                muc_do_de_xuat="nghiem_trong",
                nguon_chi_tiet=(_src("Metformin"),),
            ),
        )
    )
    resolver = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("metformin", "Metformin")],
            )
        }
    )
    ca = make_minimal_case(xet_nghiem=[])
    findings = check(ca, resolver, cfg)
    assert len(findings) == 1
    assert findings[0].ma_luat == "xet_nghiem_thieu"
    assert findings[0].ket_luan == "khong_du_du_lieu"
    assert findings[0].muc_do is None
    assert findings[0].thong_tin_con_thieu == ["egfr"]


def test_lab_dieu_kien_khac_caps_severity_to_can_luu_y() -> None:
    """Dòng có dieu_kien_khac phải hạ mức tối đa về can_luu_y và nêu phần cần đối chiếu."""
    cfg = LabThresholdConfig(
        quy_tac=(
            LabThresholdRule(
                ten_quoc_te="apixaban",
                hoat_chat_ids=("apixaban",),
                xet_nghiem="creatinin",
                dieu_kien=(
                    LabCondition(
                        ma_xet_nghiem="creatinin",
                        toan_tu=">=",
                        gia_tri=1.5,
                        don_vi_nhan="mg/dL",
                        don_vi_ca="umol/L",
                        he_so_ca_sang_nhan=0.011312,
                    ),
                ),
                hanh_dong_nhan="Giảm liều nếu đạt >= 2/3 tiêu chí",
                kieu_dieu_kien="canh_bao_khi_thoa",
                muc_do_de_xuat="nghiem_trong",
                dieu_kien_khac="cần kèm tuổi >= 80 hoặc cân nặng <= 60 kg",
                nguon_chi_tiet=(_src("Apixaban"),),
            ),
        )
    )
    resolver = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("apixaban", "Apixaban")],
            ),
        }
    )
    ca = make_minimal_case(
        xet_nghiem=[
            KetQuaXetNghiem(
                xet_nghiem_id="XN-CR-150",
                ma_xet_nghiem="creatinin",
                ten_xet_nghiem="Creatinin máu",
                gia_tri_so=150.0,
                don_vi="umol/L",
                thoi_diem_ket_qua=NOW,
            )
        ]
    )
    findings = check(ca, resolver, cfg)
    assert len(findings) == 1
    assert findings[0].ket_luan == "can_xem"
    assert findings[0].muc_do == "can_luu_y"
    assert "cần đối chiếu thêm: cần kèm tuổi >= 80 hoặc cân nặng <= 60 kg" in findings[0].mo_ta


def test_lab_skips_rows_missing_kieu_dieu_kien_and_aggregates() -> None:
    """Bỏ qua dòng thiếu kieu_dieu_kien và gộp nhiều dòng cùng hoạt chất thành một phát hiện."""
    cfg = LabThresholdConfig(
        quy_tac=(
            LabThresholdRule(
                ten_quoc_te="metformin",
                hoat_chat_ids=("metformin",),
                xet_nghiem="egfr",
                dieu_kien=(LabCondition(ma_xet_nghiem="egfr", toan_tu="<", gia_tri=30.0),),
                hanh_dong_nhan="Dòng thiếu kieu_dieu_kien phải bị bỏ qua",
                kieu_dieu_kien=None,
            ),
            LabThresholdRule(
                ten_quoc_te="metformin",
                hoat_chat_ids=("metformin",),
                xet_nghiem="egfr",
                dieu_kien=(
                    LabCondition(
                        ma_xet_nghiem="egfr",
                        toan_tu="<",
                        gia_tri=30.0,
                        don_vi_nhan="mL/min/1.73m2",
                        don_vi_ca="mL/phút/1,73m2",
                        he_so_ca_sang_nhan=1.0,
                    ),
                ),
                hanh_dong_nhan="eGFR < 30: chống chỉ định",
                kieu_dieu_kien="canh_bao_khi_thoa",
                muc_do_de_xuat="nghiem_trong",
                nguon_chi_tiet=(_src("Metformin"),),
            ),
            LabThresholdRule(
                ten_quoc_te="metformin",
                hoat_chat_ids=("metformin",),
                xet_nghiem="egfr",
                dieu_kien=(
                    LabCondition(
                        ma_xet_nghiem="egfr",
                        toan_tu="<",
                        gia_tri=45.0,
                        don_vi_nhan="mL/min/1.73m2",
                        don_vi_ca="mL/phút/1,73m2",
                        he_so_ca_sang_nhan=1.0,
                    ),
                ),
                hanh_dong_nhan="eGFR < 45: đánh giá lại",
                kieu_dieu_kien="canh_bao_khi_thoa",
                muc_do_de_xuat="can_luu_y",
                nguon_chi_tiet=(_src("Metformin"),),
            ),
        )
    )
    resolver = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("metformin", "Metformin")],
            )
        }
    )
    ca = make_minimal_case(
        xet_nghiem=[
            KetQuaXetNghiem(
                xet_nghiem_id="XN-EGFR-25",
                ma_xet_nghiem="egfr",
                ten_xet_nghiem="eGFR",
                gia_tri_so=25.0,
                don_vi="mL/phút/1,73m2",
                thoi_diem_ket_qua=NOW,
            )
        ]
    )
    findings = check(ca, resolver, cfg)
    assert len(findings) == 1
    assert findings[0].muc_do == "nghiem_trong"


def test_load_real_lab_threshold_kb() -> None:
    """Nạp tệp data/kb/nguong_xet_nghiem.json thật; skip nếu khoá MỚI chưa có."""
    if not _REAL_PATH.exists():
        pytest.skip("Thiếu tệp data/kb/nguong_xet_nghiem.json")
    cfg = load_lab_threshold_config(_REAL_PATH)
    assert len(cfg.quy_tac) > 0
    if not any(rule.kieu_dieu_kien is not None for rule in cfg.quy_tac):
        pytest.skip("Khoá MỚI kieu_dieu_kien chưa có trong nguong_xet_nghiem.json")


def _inr_cfg() -> LabThresholdConfig:
    """Cấu hình INR không đơn vị: don_vi_ca null kèm hệ số 1."""
    return LabThresholdConfig(
        quy_tac=(
            LabThresholdRule(
                ten_quoc_te="warfarin",
                hoat_chat_ids=("warfarin",),
                xet_nghiem="inr",
                dieu_kien=(
                    LabCondition(
                        ma_xet_nghiem="inr",
                        toan_tu=">",
                        gia_tri=4.0,
                        don_vi_nhan=None,
                        don_vi_ca=None,
                        he_so_ca_sang_nhan=1.0,
                    ),
                ),
                hanh_dong_nhan="INR > 4,0 tăng nguy cơ chảy máu",
                kieu_dieu_kien="canh_bao_khi_thoa",
                muc_do_de_xuat="nghiem_trong",
                nguon_chi_tiet=(_src("Warfarin"),),
            ),
            LabThresholdRule(
                ten_quoc_te="warfarin",
                hoat_chat_ids=("warfarin",),
                xet_nghiem="inr",
                dieu_kien=(
                    LabCondition(
                        ma_xet_nghiem="inr",
                        toan_tu="khoang",
                        gia_tri=2.0,
                        gia_tri_den=3.0,
                        don_vi_nhan=None,
                        don_vi_ca=None,
                        he_so_ca_sang_nhan=1.0,
                    ),
                ),
                hanh_dong_nhan="Mục tiêu INR 2-3",
                kieu_dieu_kien="canh_bao_khi_ngoai_khoang",
                muc_do_de_xuat="can_luu_y",
                nguon_chi_tiet=(_src("Warfarin"),),
            ),
        )
    )


def _inr_resolver() -> _FakeResolver:
    return _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("warfarin", "Warfarin")],
            ),
        }
    )


def _inr_case(value: float, unit: str | None) -> CaBenh:
    return make_minimal_case(
        xet_nghiem=[
            KetQuaXetNghiem(
                xet_nghiem_id="XN-INR-X",
                ma_xet_nghiem="inr",
                ten_xet_nghiem="INR",
                gia_tri_so=value,
                don_vi=unit,
                thoi_diem_ket_qua=NOW,
            )
        ]
    )


def test_lab_inr_unitless_empty_string_exceeds_threshold() -> None:
    """INR 4,5 với don_vi rỗng, điều kiện don_vi_ca null: vượt ngưỡng 4,0."""
    findings = check(_inr_case(4.5, ""), _inr_resolver(), _inr_cfg())
    assert len(findings) == 1
    assert findings[0].ma_luat == "xet_nghiem_vuot_nguong"
    assert findings[0].ket_luan == "can_xem"
    assert "> 4" in findings[0].mo_ta


def test_lab_inr_unitless_none_in_range_no_warning() -> None:
    """INR 2,5 với don_vi None: không cảnh báo, nằm trong khoảng 2-3."""
    findings = check(_inr_case(2.5, None), _inr_resolver(), _inr_cfg())
    assert len(findings) == 1
    assert findings[0].ma_luat == "xet_nghiem_trong_nguong"
    assert findings[0].ket_luan == "dat"


def test_lab_inr_with_wrong_unit_returns_missing_don_vi() -> None:
    """INR kèm đơn vị sai (mmol/L) vẫn là không đổi được đơn vị."""
    findings = check(_inr_case(4.5, "mmol/L"), _inr_resolver(), _inr_cfg())
    assert len(findings) == 1
    assert findings[0].ket_luan == "khong_du_du_lieu"
    assert findings[0].thong_tin_con_thieu == ["inr_don_vi"]


def _metformin_egfr_cfg() -> LabThresholdConfig:
    """Cấu hình metformin theo eGFR < 30 (chống chỉ định)."""
    return LabThresholdConfig(
        quy_tac=(
            LabThresholdRule(
                ten_quoc_te="metformin",
                hoat_chat_ids=("metformin",),
                xet_nghiem="egfr",
                dieu_kien=(
                    LabCondition(
                        ma_xet_nghiem="egfr",
                        toan_tu="<",
                        gia_tri=30.0,
                        don_vi_nhan="mL/min/1.73 m2",
                        don_vi_ca="mL/phút/1,73m2",
                        he_so_ca_sang_nhan=1.0,
                    ),
                ),
                hanh_dong_nhan="eGFR < 30: chống chỉ định",
                kieu_dieu_kien="canh_bao_khi_thoa",
                muc_do_de_xuat="nghiem_trong",
                nguon_chi_tiet=(_src("Metformin Hydrochloride"),),
            ),
        )
    )


def _metformin_resolver() -> _FakeResolver:
    return _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("metformin", "Metformin")],
            ),
        }
    )


def test_lab_egfr_estimated_from_creatinine_triggers_contraindication() -> None:
    """Nam 72 tuổi, creatinin 230 µmol/L, không có eGFR -> ước tính ≈ 25,4 -> can_xem."""
    ca = make_minimal_case(
        tuoi=72,
        gioi_tinh="nam",
        xet_nghiem=[
            KetQuaXetNghiem(
                xet_nghiem_id="XN-CR-OLD",
                ma_xet_nghiem="creatinin",
                ten_xet_nghiem="Creatinin máu",
                gia_tri_so=90.0,
                don_vi="µmol/L",
                thoi_diem_ket_qua=NOW - timedelta(days=5),
            ),
            KetQuaXetNghiem(
                xet_nghiem_id="XN-CR-230",
                ma_xet_nghiem="creatinin",
                ten_xet_nghiem="Creatinin máu",
                gia_tri_so=230.0,
                don_vi="µmol/L",
                thoi_diem_ket_qua=NOW,
            ),
        ],
    )
    findings = check(ca, _metformin_resolver(), _metformin_egfr_cfg())
    assert len(findings) == 1
    f = findings[0]
    assert f.ma_luat == "xet_nghiem_vuot_nguong"
    assert f.ket_luan == "can_xem"
    assert f.muc_do == "nghiem_trong"
    assert "eGFR < 30: chống chỉ định" in f.mo_ta
    assert "CKD-EPI 2021" in f.mo_ta
    assert "230 µmol/L" in f.mo_ta
    match = re.search(r"eGFR ước tính (\d+(?:\.\d+)?)", f.mo_ta)
    assert match is not None
    assert float(match.group(1)) == pytest.approx(25.4, abs=0.5)
    assert any(c.loai == "du_lieu" and c.ban_ghi_id == "XN-CR-230" for c in f.can_cu)
    assert any(c.loai == "tinh_toan" and c.ban_ghi_id == "egfr_ckd_epi_2021" for c in f.can_cu)


def test_lab_egfr_measured_value_takes_priority_over_creatinine() -> None:
    """Ca có cả eGFR đo = 50 và creatinin cao -> dùng 50, không cảnh báo < 30."""
    ca = make_minimal_case(
        tuoi=72,
        gioi_tinh="nam",
        xet_nghiem=[
            KetQuaXetNghiem(
                xet_nghiem_id="XN-CR-230",
                ma_xet_nghiem="creatinin",
                ten_xet_nghiem="Creatinin máu",
                gia_tri_so=230.0,
                don_vi="µmol/L",
                thoi_diem_ket_qua=NOW,
            ),
            KetQuaXetNghiem(
                xet_nghiem_id="XN-EGFR-50",
                ma_xet_nghiem="egfr",
                ten_xet_nghiem="eGFR",
                gia_tri_so=50.0,
                don_vi="mL/phút/1,73m2",
                thoi_diem_ket_qua=NOW,
            ),
        ],
    )
    findings = check(ca, _metformin_resolver(), _metformin_egfr_cfg())
    assert len(findings) == 1
    f = findings[0]
    assert f.ma_luat == "xet_nghiem_trong_nguong"
    assert f.ket_luan == "dat"
    assert f.muc_do == "thong_tin"
    assert "50" in f.mo_ta
    assert "CKD-EPI 2021" not in f.mo_ta
    assert any(c.loai == "du_lieu" and c.ban_ghi_id == "XN-EGFR-50" for c in f.can_cu)


def test_lab_egfr_fallback_missing_sex_returns_khong_du_du_lieu() -> None:
    """Không có eGFR, có creatinin nhưng thiếu giới tính -> khong_du_du_lieu, nêu thiếu giới."""
    ca = make_minimal_case(
        tuoi=72,
        gioi_tinh=None,
        xet_nghiem=[
            KetQuaXetNghiem(
                xet_nghiem_id="XN-CR-230",
                ma_xet_nghiem="creatinin",
                ten_xet_nghiem="Creatinin máu",
                gia_tri_so=230.0,
                don_vi="µmol/L",
                thoi_diem_ket_qua=NOW,
            ),
        ],
    )
    findings = check(ca, _metformin_resolver(), _metformin_egfr_cfg())
    assert len(findings) == 1
    f = findings[0]
    assert f.ma_luat == "xet_nghiem_thieu"
    assert f.ket_luan == "khong_du_du_lieu"
    assert f.muc_do is None
    assert "gioi_tinh" in f.thong_tin_con_thieu
    assert "gioi_tinh" in f.mo_ta
    assert any(c.loai == "du_lieu" and c.ban_ghi_id == "XN-CR-230" for c in f.can_cu)


def test_lab_egfr_fallback_underage_value_error_returns_khong_du_du_lieu() -> None:
    """Tuổi dưới 18 khi tính CKD-EPI 2021 -> không ném lỗi, trả khong_du_du_lieu."""
    ca = make_minimal_case(
        tuoi=12,
        gioi_tinh="nam",
        xet_nghiem=[
            KetQuaXetNghiem(
                xet_nghiem_id="XN-CR-80",
                ma_xet_nghiem="creatinin",
                ten_xet_nghiem="Creatinin máu",
                gia_tri_so=80.0,
                don_vi="µmol/L",
                thoi_diem_ket_qua=NOW,
            ),
        ],
    )
    findings = check(ca, _metformin_resolver(), _metformin_egfr_cfg())
    assert len(findings) == 1
    f = findings[0]
    assert f.ma_luat == "xet_nghiem_thieu"
    assert f.ket_luan == "khong_du_du_lieu"
    assert f.muc_do is None
    assert f.thong_tin_con_thieu == ["so_lieu_hop_le"]
