"""Kiểm thử luật yếu tố 6: chỉnh liều theo suy gan và nhãn FDA."""

from datetime import timedelta
from pathlib import Path

import pytest

from app.domain.models import CaBenh, ChiTietYLenh, CoDia, KetQuaXetNghiem
from app.kb.resolver.resolver import KetQuaPhanGiai, ThanhPhanPhanGiai
from app.rules.d4_config import D4SourceDetail, HepaticConfig, HepaticRule, load_hepatic_config
from app.rules.hepatic import check
from tests.rules import NOW, make_minimal_case

_REAL_PATH = Path(__file__).resolve().parents[2] / "data" / "kb" / "quy_tac_gan.json"


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


def _src(drug: str = "ELIQUIS", set_id: str = "set-1") -> D4SourceDetail:
    return D4SourceDetail(
        loai="nhan_fda",
        ten_nhan=drug,
        set_id=set_id,
        trich_nguyen_van="hepatic impairment recommendation",
        url=f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={set_id}",
    )


def _case_hepatic(
    co_dia: list[CoDia] | None = None,
    xet_nghiem: list[KetQuaXetNghiem] | None = None,
) -> CaBenh:
    base = make_minimal_case(xet_nghiem=xet_nghiem or [])
    return base.model_copy(update={"co_dia": co_dia or []})


def _apixaban_config() -> HepaticConfig:
    return HepaticConfig(
        phien_ban="D4-v1",
        quy_tac=(
            HepaticRule(
                ten_quoc_te="apixaban",
                hoat_chat_ids=("apixaban",),
                phan_loai_gan=("child_pugh_A",),
                hanh_dong_nhan="khong_chinh_lieu",
                khuyen_cao="Nhẹ (Child-Pugh A): không cần chỉnh liều",
                nguon_chi_tiet=(_src(),),
            ),
            HepaticRule(
                ten_quoc_te="apixaban",
                hoat_chat_ids=("apixaban",),
                phan_loai_gan=("child_pugh_B",),
                hanh_dong_nhan="khong_co_khuyen_cao_cu_the",
                khuyen_cao="Vừa (Child-Pugh B): không đưa được khuyến cáo liều",
                nguon_chi_tiet=(_src(),),
            ),
            HepaticRule(
                ten_quoc_te="apixaban",
                hoat_chat_ids=("apixaban",),
                phan_loai_gan=("child_pugh_C",),
                hanh_dong_nhan="tranh_khong_khuyen_cao",
                khuyen_cao="Nặng (Child-Pugh C): không khuyến cáo",
                nguon_chi_tiet=(_src(),),
            ),
        ),
    )


def test_hepatic_no_impairment_returns_dat() -> None:
    """Tình trạng khong_suy trả dat thong_tin với ma_luat=gan_khong_suy_gan."""
    ca = _case_hepatic(co_dia=[CoDia(loai="suy_gan", trang_thai="khong", thoi_diem=NOW)])
    resolver = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("apixaban", "Apixaban")],
            ),
        }
    )
    findings = check(ca, resolver, _apixaban_config())
    assert len(findings) == 1
    assert findings[0].ma_luat == "gan_khong_suy_gan"
    assert findings[0].ket_luan == "dat"
    assert findings[0].muc_do == "thong_tin"


@pytest.mark.parametrize(
    ("gia_tri", "expected_ket_luan", "expected_muc_do", "expected_ma_luat"),
    [
        ("Child-Pugh B", "ngoai_hdsd", "can_luu_y", "gan_theo_nhan"),
        ("child pugh class c", "can_xem", "nghiem_trong", "gan_theo_nhan"),
        ("Child-Pugh A", "dat", "thong_tin", "gan_theo_nhan"),
    ],
)
def test_hepatic_child_pugh_regex_and_matching(
    gia_tri: str,
    expected_ket_luan: str,
    expected_muc_do: str,
    expected_ma_luat: str,
) -> None:
    """Regex nhận Child-Pugh B và child pugh class c, ánh xạ đúng kết luận và mức."""
    ca = _case_hepatic(
        co_dia=[CoDia(loai="suy_gan", trang_thai="co", gia_tri=gia_tri, thoi_diem=NOW)]
    )
    resolver = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("apixaban", "Apixaban")],
            ),
        }
    )
    findings = check(ca, resolver, _apixaban_config())
    assert len(findings) == 1
    assert findings[0].ma_luat == expected_ma_luat
    assert findings[0].ket_luan == expected_ket_luan
    assert findings[0].muc_do == expected_muc_do


def test_hepatic_child_pugh_without_matching_tier_returns_dat() -> None:
    """Có hạng Child-Pugh A nhưng chỉ có dòng Child-Pugh C -> gan_khong_co_khuyen_cao_cho_hang."""
    ca = _case_hepatic(
        co_dia=[CoDia(loai="suy_gan", trang_thai="co", gia_tri="Child-Pugh A", thoi_diem=NOW)]
    )
    config = HepaticConfig(
        quy_tac=(
            HepaticRule(
                ten_quoc_te="esomeprazole",
                hoat_chat_ids=("esomeprazole",),
                phan_loai_gan=("child_pugh_C",),
                hanh_dong_nhan="giam_lieu",
                khuyen_cao="Child-Pugh C: 20 mg 1 lần/ngày",
                nguon_chi_tiet=(_src("Esomeprazole", "set-eso"),),
            ),
        )
    )
    resolver = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("esomeprazole", "Esomeprazole")],
            )
        }
    )
    findings = check(ca, resolver, config)
    assert len(findings) == 1
    assert findings[0].ma_luat == "gan_khong_co_khuyen_cao_cho_hang"
    assert findings[0].ket_luan == "dat"
    assert findings[0].muc_do == "thong_tin"


def test_hepatic_ungraded_impairment_three_branches() -> None:
    """Kiểm đủ 3 nhánh của co_suy_chua_phan_hang: không phân loại, theo hạng, không hành động."""
    ca = _case_hepatic(
        co_dia=[CoDia(loai="suy_gan", trang_thai="co", gia_tri="Xơ gan", thoi_diem=NOW)]
    )

    # 1) Dòng theo hạng -> gan_thieu_phan_hang
    resolver_apix = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("apixaban", "Apixaban")],
            ),
        }
    )
    f_graded = check(ca, resolver_apix, _apixaban_config())
    assert len(f_graded) == 1
    assert f_graded[0].ma_luat == "gan_thieu_phan_hang"
    assert f_graded[0].ket_luan == "khong_du_du_lieu"
    assert f_graded[0].muc_do is None
    assert f_graded[0].thong_tin_con_thieu == ["phan_hang_child_pugh"]
    assert "Nặng (Child-Pugh C)" in f_graded[0].mo_ta

    # 2) Dòng khong_phan_loai cần hành động -> gan_theo_nhan
    cfg_unclassified = HepaticConfig(
        quy_tac=(
            HepaticRule(
                ten_quoc_te="metformin",
                hoat_chat_ids=("metformin",),
                phan_loai_gan=("khong_phan_loai",),
                hanh_dong_nhan="tranh_khong_khuyen_cao",
                khuyen_cao="Suy gan: không khuyến cáo",
                nguon_chi_tiet=(_src("Metformin", "set-met"),),
            ),
        )
    )
    resolver_met = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("metformin", "Metformin")],
            )
        }
    )
    f_unclass = check(ca, resolver_met, cfg_unclassified)
    assert len(f_unclass) == 1
    assert f_unclass[0].ma_luat == "gan_theo_nhan"
    assert f_unclass[0].ket_luan == "can_xem"
    assert f_unclass[0].muc_do == "nghiem_trong"

    # 3) Không có dòng cần hành động -> dat
    cfg_no_action = HepaticConfig(
        quy_tac=(
            HepaticRule(
                ten_quoc_te="piperacillin",
                hoat_chat_ids=("piperacillin", "tazobactam"),
                phan_loai_gan=("khong_phan_loai",),
                hanh_dong_nhan="khong_chinh_lieu",
                khuyen_cao="Xơ gan: không cần chỉnh liều",
                nguon_chi_tiet=(_src("Pip-Tazo", "set-pip"),),
            ),
        )
    )
    resolver_pip = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("piperacillin", "Piperacillin"), _tp("tazobactam", "Tazobactam")],
            )
        }
    )
    f_none = check(ca, resolver_pip, cfg_no_action)
    assert len(f_none) == 1
    assert f_none[0].ket_luan == "dat"
    assert f_none[0].muc_do == "thong_tin"


def test_hepatic_unassessed_with_and_without_action_rows() -> None:
    """chua_danh_gia: có hành động -> gan_chua_danh_gia kèm xét nghiệm gan; không -> rỗng."""
    ca = _case_hepatic(
        co_dia=[],
        xet_nghiem=[
            KetQuaXetNghiem(
                xet_nghiem_id="XN-ALT",
                ma_xet_nghiem="alt",
                ten_xet_nghiem="ALT",
                gia_tri_so=120.0,
                don_vi="U/L",
                thoi_diem_ket_qua=NOW,
            ),
            KetQuaXetNghiem(
                xet_nghiem_id="XN-BILI",
                ma_xet_nghiem="bilirubin",
                ten_xet_nghiem="Bilirubin TP",
                gia_tri_so=35.0,
                don_vi="umol/L",
                thoi_diem_ket_qua=NOW,
            ),
        ],
    )
    resolver_apix = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("apixaban", "Apixaban")],
            ),
        }
    )
    f_action = check(ca, resolver_apix, _apixaban_config())
    assert len(f_action) == 1
    assert f_action[0].ma_luat == "gan_chua_danh_gia"
    assert f_action[0].ket_luan == "khong_du_du_lieu"
    assert f_action[0].muc_do is None
    assert f_action[0].thong_tin_con_thieu == ["danh_gia_chuc_nang_gan"]
    lab_ids = {c.ban_ghi_id for c in f_action[0].can_cu if c.loai == "du_lieu"}
    assert {"XN-ALT", "XN-BILI"}.issubset(lab_ids)

    cfg_no_action = HepaticConfig(
        quy_tac=(
            HepaticRule(
                ten_quoc_te="levofloxacin",
                hoat_chat_ids=("levofloxacin",),
                phan_loai_gan=("khong_phan_loai",),
                hanh_dong_nhan="khong_chinh_lieu",
                khuyen_cao="Không cần chỉnh liều",
                nguon_chi_tiet=(_src("Levofloxacin", "set-levo"),),
            ),
        )
    )
    resolver_levo = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("levofloxacin", "Levofloxacin")],
            )
        }
    )
    assert check(ca, resolver_levo, cfg_no_action) == []


def test_hepatic_latest_record_prefers_newest_timestamp() -> None:
    """Bản ghi suy_gan thiếu thoi_diem xếp cũ nhất; bản ghi mới nhất quyết định kết quả."""
    ca = _case_hepatic(
        co_dia=[
            CoDia(loai="suy_gan", trang_thai="co", gia_tri="Child-Pugh C", thoi_diem=None),
            CoDia(
                loai="suy_gan",
                trang_thai="co",
                gia_tri="Child-Pugh A",
                thoi_diem=NOW - timedelta(days=1),
            ),
            CoDia(loai="suy_gan", trang_thai="khong", thoi_diem=NOW),
        ]
    )
    resolver = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("apixaban", "Apixaban")],
            ),
        }
    )
    findings = check(ca, resolver, _apixaban_config())
    assert len(findings) == 1
    assert findings[0].ma_luat == "gan_khong_suy_gan"


def test_load_real_hepatic_kb() -> None:
    """Nạp tệp data/kb/quy_tac_gan.json thật và kiểm số dòng > 0."""
    if not _REAL_PATH.exists():
        pytest.skip("Thiếu tệp data/kb/quy_tac_gan.json")
    cfg = load_hepatic_config(_REAL_PATH)
    assert len(cfg.quy_tac) > 0
