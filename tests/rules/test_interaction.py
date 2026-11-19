"""Kiểm thử đơn vị cho luật yếu tố 4: rà tương tác thuốc – thuốc."""

from __future__ import annotations

from datetime import UTC, datetime

from app.domain.models import (
    CaBenh,
    ChiTietYLenh,
    DotDieuTri,
    HoatChat,
    NguoiBenh,
    ThanhPhan,
    Thuoc,
    TinhTrangDiUng,
    YLenh,
)
from app.rules.interaction import InteractionBook, InteractionRecord, check

_NOW = datetime(2026, 11, 18, 8, 0, tzinfo=UTC)


def _sample_records() -> InteractionBook:
    return InteractionBook(
        tuong_tac=[
            InteractionRecord(
                tuong_tac_id="TT-aspirin-warfarin",
                hoat_chat_a_id="aspirin",
                hoat_chat_b_id="warfarin",
                ten_hoat_chat_a="Aspirin",
                ten_hoat_chat_b="Warfarin",
                ddinter_id_a="DDInter138",
                ddinter_id_b="DDInter1951",
                ddinter_interaction_id="DDInter216310",
                muc_do_ddinter="Major",
                muc_do="nghiem_trong",
                co_che=["Synergistic effect"],
                mo_ta_lam_sang="Increases bleeding risk.",
                xu_tri="Avoid combination or monitor INR closely.",
                tai_lieu_ddinter=["[1] Holbrook 2005"],
                trich_dan_nhan_fda=["CK-WARF-01"],
            ),
            InteractionRecord(
                tuong_tac_id="TT-atorvastatin-clarithromycin",
                hoat_chat_a_id="atorvastatin",
                hoat_chat_b_id="clarithromycin",
                ten_hoat_chat_a="Atorvastatin",
                ten_hoat_chat_b="Clarithromycin",
                ddinter_id_a="DDInter1",
                ddinter_id_b="DDInter2",
                ddinter_interaction_id="DDInter100",
                muc_do_ddinter="Moderate",
                muc_do="trung_binh",
                co_che=["Metabolism"],
            ),
            InteractionRecord(
                tuong_tac_id="TT-acetaminophen-warfarin",
                hoat_chat_a_id="acetaminophen",
                hoat_chat_b_id="warfarin",
                ten_hoat_chat_a="Acetaminophen",
                ten_hoat_chat_b="Warfarin",
                ddinter_id_a="DDInter3",
                ddinter_id_b="DDInter1951",
                ddinter_interaction_id="DDInter101",
                muc_do_ddinter="Minor",
                muc_do="nhe",
            ),
            InteractionRecord(
                tuong_tac_id="TT-amlodipine-warfarin",
                hoat_chat_a_id="amlodipine",
                hoat_chat_b_id="warfarin",
                ten_hoat_chat_a="Amlodipine",
                ten_hoat_chat_b="Warfarin",
                ddinter_id_a="DDInter79",
                ddinter_id_b="DDInter1951",
                ddinter_interaction_id="DDInter102",
                muc_do_ddinter="Unknown",
                muc_do="chua_ro",
            ),
        ]
    )


def _make_case(
    *,
    pending: list[ChiTietYLenh],
    active: list[ChiTietYLenh],
    thuoc: list[Thuoc],
    hoat_chat: list[HoatChat],
) -> CaBenh:
    return CaBenh(
        ca_id="TEST-DDI",
        mo_ta_ngan="Ca thử nghiệm yếu tố 4",
        nguoi_benh=NguoiBenh(nguoi_benh_id="NB-1", tuoi=65, gioi_tinh="nam"),
        tinh_trang_di_ung=TinhTrangDiUng(trang_thai="khong_di_ung_da_hoi"),
        dot_dieu_tri=DotDieuTri(
            dot_dieu_tri_id="DT-1",
            khoa_dieu_tri="Nội",
            loai_dieu_tri="noi_tru",
            thoi_diem_bat_dau=_NOW,
        ),
        thuoc_dang_dung=active,
        y_lenh_cho_duyet=YLenh(
            y_lenh_id="YL-1",
            khoa_ke_don="Nội",
            luong_duyet="truc_tiep",
            thoi_diem_ke=_NOW,
            chi_tiet=pending,
        ),
        danh_muc_thuoc=thuoc,
        danh_muc_hoat_chat=hoat_chat,
    )


def test_major_moderate_minor_and_hc_prefix_resolution() -> None:
    book = _sample_records()
    assert book.lookup("warfarin", "aspirin") == book.lookup("aspirin", "warfarin")

    ca = _make_case(
        pending=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-1",
                thuoc_id="T-WARF",
                bat_dau=_NOW,
                trang_thai_dong="pending",
            ),
        ],
        active=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-ASP",
                thuoc_id="T-ASP",
                bat_dau=_NOW,
                trang_thai_dong="active",
            ),
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-PARA",
                thuoc_id="T-PARA",
                bat_dau=_NOW,
                trang_thai_dong="active",
            ),
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-AMLO",
                thuoc_id="T-AMLO",
                bat_dau=_NOW,
                trang_thai_dong="active",
            ),
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-STOP",
                thuoc_id="T-ASP",
                bat_dau=_NOW,
                trang_thai_dong="discontinued",
            ),
        ],
        thuoc=[
            Thuoc(
                thuoc_id="T-WARF",
                ten_thuoc="Warfarin 5mg",
                thanh_phan=[ThanhPhan(hoat_chat_id="HC-WARFARIN")],
            ),
            Thuoc(
                thuoc_id="T-ASP",
                ten_thuoc="Aspirin 81mg",
                thanh_phan=[ThanhPhan(hoat_chat_id="HC-ASPIRIN")],
            ),
            Thuoc(
                thuoc_id="T-PARA",
                ten_thuoc="Paracetamol 500mg",
                thanh_phan=[ThanhPhan(hoat_chat_id="HC-ACETAMINOPHEN")],
            ),
            Thuoc(
                thuoc_id="T-AMLO",
                ten_thuoc="Amlodipine 5mg",
                thanh_phan=[ThanhPhan(hoat_chat_id="HC-AMLODIPINE")],
            ),
        ],
        hoat_chat=[
            HoatChat(hoat_chat_id="HC-WARFARIN", ten_hoat_chat="Warfarin", ten_quoc_te="warfarin"),
            HoatChat(hoat_chat_id="HC-ASPIRIN", ten_hoat_chat="Aspirin", ten_quoc_te="aspirin"),
            HoatChat(
                hoat_chat_id="HC-ACETAMINOPHEN",
                ten_hoat_chat="Paracetamol",
                ten_quoc_te="acetaminophen",
            ),
            HoatChat(
                hoat_chat_id="HC-AMLODIPINE",
                ten_hoat_chat="Amlodipine",
                ten_quoc_te="amlodipine",
            ),
        ],
    )

    findings = check(ca, book)
    # Unknown (amlodipine) và discontinued (CT-STOP) đều được bỏ qua
    assert len(findings) == 2

    major = next(f for f in findings if f.ma_luat == "tuong_tac_nghiem_trong")
    assert major.yeu_to == 4
    assert major.ket_luan == "can_xem"
    assert major.muc_do == "nghiem_trong"
    assert major.chi_tiet_y_lenh_id == ["CT-1", "CT-ASP"]
    assert "bleeding risk" in major.mo_ta
    assert any(c.ban_ghi_id == "CK-WARF-01" for c in major.can_cu)
    assert any(c.ban_ghi_id == "DDInter216310" for c in major.can_cu)

    minor = next(f for f in findings if f.ma_luat == "tuong_tac_nhe")
    assert minor.ket_luan == "dat"
    assert minor.muc_do == "thong_tin"
    assert minor.chi_tiet_y_lenh_id == ["CT-1", "CT-PARA"]


def test_pending_pair_deduped_and_moderate_severity() -> None:
    book = _sample_records()
    ca = _make_case(
        pending=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-1",
                thuoc_id="T-ATOR",
                bat_dau=_NOW,
                trang_thai_dong="pending",
            ),
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-2",
                thuoc_id="T-CLAR",
                bat_dau=_NOW,
                trang_thai_dong="pending",
            ),
        ],
        active=[],
        thuoc=[
            Thuoc(
                thuoc_id="T-ATOR",
                ten_thuoc="Atorvastatin",
                thanh_phan=[ThanhPhan(hoat_chat_id="atorvastatin")],
            ),
            Thuoc(
                thuoc_id="T-CLAR",
                ten_thuoc="Clarithromycin",
                thanh_phan=[ThanhPhan(hoat_chat_id="clarithromycin")],
            ),
        ],
        hoat_chat=[
            HoatChat(hoat_chat_id="atorvastatin", ten_hoat_chat="Atorvastatin"),
            HoatChat(hoat_chat_id="clarithromycin", ten_hoat_chat="Clarithromycin"),
        ],
    )

    findings = check(ca, book)
    assert len(findings) == 1
    assert findings[0].ma_luat == "tuong_tac_trung_binh"
    assert findings[0].ket_luan == "can_xem"
    assert findings[0].muc_do == "can_luu_y"
    assert findings[0].chi_tiet_y_lenh_id == ["CT-1", "CT-2"]


def test_combo_same_line_no_self_interaction_and_unknown_freetext() -> None:
    book = _sample_records()
    # Thuốc phối hợp trên CÙNG một dòng không tự coi là tương tác khác dòng -> dat
    combo_ca = _make_case(
        pending=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-COMBO",
                thuoc_id="T-COMBO",
                bat_dau=_NOW,
                trang_thai_dong="pending",
            ),
        ],
        active=[],
        thuoc=[
            Thuoc(
                thuoc_id="T-COMBO",
                ten_thuoc="Aspirin + Warfarin phối hợp",
                thanh_phan=[
                    ThanhPhan(hoat_chat_id="aspirin"),
                    ThanhPhan(hoat_chat_id="warfarin"),
                ],
            ),
        ],
        hoat_chat=[
            HoatChat(hoat_chat_id="aspirin", ten_hoat_chat="Aspirin"),
            HoatChat(hoat_chat_id="warfarin", ten_hoat_chat="Warfarin"),
        ],
    )
    combo_findings = check(combo_ca, book)
    assert len(combo_findings) == 1
    assert combo_findings[0].ma_luat == "tuong_tac_khong_co"
    assert combo_findings[0].ket_luan == "dat"

    # Sản phẩm tên tự do đi kèm thuốc khác -> khong_du_du_lieu
    freetext_ca = _make_case(
        pending=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-FREE",
                ten_tu_do="Viên thảo dược không rõ thành phần",
                bat_dau=_NOW,
                trang_thai_dong="pending",
            ),
        ],
        active=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-WARF",
                thuoc_id="T-WARF",
                bat_dau=_NOW,
                trang_thai_dong="active",
            ),
        ],
        thuoc=[
            Thuoc(
                thuoc_id="T-WARF",
                ten_thuoc="Warfarin",
                thanh_phan=[ThanhPhan(hoat_chat_id="warfarin")],
            ),
        ],
        hoat_chat=[HoatChat(hoat_chat_id="warfarin", ten_hoat_chat="Warfarin")],
    )
    free_findings = check(freetext_ca, book)
    assert len(free_findings) == 1
    assert free_findings[0].ma_luat == "tuong_tac_san_pham_chua_ro"
    assert free_findings[0].ket_luan == "khong_du_du_lieu"
    assert free_findings[0].muc_do is None
    assert free_findings[0].thong_tin_con_thieu == ["thanh_phan_hoat_chat"]
