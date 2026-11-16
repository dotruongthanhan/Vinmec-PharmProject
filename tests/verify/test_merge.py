"""Kiểm thử ghép phát hiện luật và đề xuất LLM ở app/verify/merge.py."""

from app.llm.schema import NhanDinhDaKiem, NhanDinhDeXuat
from app.rules.types import CanCu, PhatHien
from app.verify.merge import merge


def _rule_finding(
    *,
    ma_luat: str = "lieu_than_can_chinh",
    yeu_to: int = 6,
    ket_luan: str = "can_xem",
    muc_do: str | None = "nghiem_trong",
    lines: list[str] | None = None,
) -> PhatHien:
    return PhatHien(
        ma_luat=ma_luat,
        yeu_to=yeu_to,
        ket_luan=ket_luan,  # type: ignore[arg-type]
        muc_do=muc_do,  # type: ignore[arg-type]
        chi_tiet_y_lenh_id=lines if lines is not None else ["CT-01"],
        mo_ta="Mô tả phát hiện luật",
        can_cu=[CanCu(loai="du_lieu", ban_ghi_id="XN-01", mo_ta="Creatinin 212")],
    )


def _proposal(
    *,
    yeu_to: int = 6,
    ket_luan: str = "can_xem",
    muc_do: str | None = "nghiem_trong",
    lines: list[str] | None = None,
    bo_sung: str | None = None,
    nhan_xet: str = "Nhận xét LLM",
) -> NhanDinhDeXuat:
    return NhanDinhDeXuat(
        chi_tiet_y_lenh_id=lines if lines is not None else ["CT-01"],
        yeu_to=yeu_to,
        ket_luan=ket_luan,  # type: ignore[arg-type]
        muc_do=muc_do,  # type: ignore[arg-type]
        nhan_xet=nhan_xet,
        ban_ghi_ids=["XN-01"],
        trich_dan=[],
        bo_sung_cho_ma_luat=bo_sung,
    )


def test_merge_keeps_rules_intact_and_blocks_downgrades() -> None:
    r1 = _rule_finding(yeu_to=6, ket_luan="can_xem", muc_do="nghiem_trong", lines=["CT-01"])
    r2 = _rule_finding(
        ma_luat="lich_dung_thieu_lieu",
        yeu_to=7,
        ket_luan="can_xem",
        muc_do="can_luu_y",
        lines=["CT-02"],
    )
    downgrade_dat = NhanDinhDaKiem(
        de_xuat=_proposal(yeu_to=6, ket_luan="dat", muc_do=None, lines=["CT-01"]),
        dat=True,
        loi=[],
    )
    downgrade_lower = NhanDinhDaKiem(
        de_xuat=_proposal(yeu_to=6, ket_luan="can_xem", muc_do="can_luu_y", lines=["CT-01"]),
        dat=True,
        loi=[],
    )

    merged, warnings = merge([r1, r2], [downgrade_dat, downgrade_lower])

    assert [item.nguon_goc for item in merged] == ["luat", "luat"]
    assert [item.phat_hien for item in merged] == [r1, r2]
    assert warnings == ["ai_ha_muc_bi_loai", "ai_ha_muc_bi_loai"]


def test_merge_attaches_matching_explanation_and_rejects_mismatched() -> None:
    r1 = _rule_finding()
    good_exp = NhanDinhDaKiem(
        de_xuat=_proposal(bo_sung="lieu_than_can_chinh", nhan_xet="Diễn giải hợp lệ"),
        dat=True,
        loi=[],
    )
    wrong_severity = NhanDinhDaKiem(
        de_xuat=_proposal(muc_do="can_luu_y", bo_sung="lieu_than_can_chinh"),
        dat=True,
        loi=[],
    )

    merged, warnings = merge([r1], [good_exp, wrong_severity])

    assert len(merged) == 1
    assert merged[0].phat_hien == r1
    assert merged[0].dien_giai == good_exp.de_xuat
    assert warnings == ["dien_giai_khong_khop"]


def test_merge_orders_rule_verified_and_unverified_and_drops_duplicates_or_dat() -> None:
    r1 = _rule_finding()
    dup = NhanDinhDaKiem(de_xuat=_proposal(), dat=True, loi=[])
    ai_dat = NhanDinhDaKiem(
        de_xuat=_proposal(yeu_to=4, ket_luan="dat", muc_do=None),
        dat=True,
        loi=[],
    )
    ai_unverified = NhanDinhDaKiem(
        de_xuat=_proposal(yeu_to=5, ket_luan="can_xem", muc_do="can_luu_y"),
        dat=False,
        loi=["so_khong_co_nguon:28"],
    )
    ai_verified = NhanDinhDaKiem(
        de_xuat=_proposal(yeu_to=3, ket_luan="can_xem", muc_do="can_luu_y"),
        dat=True,
        loi=[],
    )

    merged, warnings = merge([r1], [dup, ai_dat, ai_unverified, ai_verified])

    assert [item.nguon_goc for item in merged] == [
        "luat",
        "ai_da_kiem_chung",
        "ai_chua_kiem_chung",
    ]
    assert merged[0].phat_hien == r1
    assert merged[1].de_xuat == ai_verified.de_xuat
    assert merged[2].de_xuat == ai_unverified.de_xuat
    assert merged[2].loi_kiem_chung == ["so_khong_co_nguon:28"]
    assert warnings == ["trung_voi_luat", "ai_dat_bi_loai"]
