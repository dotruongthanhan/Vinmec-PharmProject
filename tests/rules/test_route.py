"""Kiểm thử luật yếu tố 3 (route.py): đường dùng hợp lệ theo dạng bào chế."""

from __future__ import annotations

from app.domain.models import ChiTietYLenh, HoatChat, ThanhPhan, Thuoc
from app.kb.resolver.resolver import KetQuaPhanGiai, ThanhPhanPhanGiai
from app.rules.d5_config import (
    RouteConfig,
    RouteCount,
    RouteNormalization,
    RouteRule,
    RouteSource,
    load_route_config,
)
from app.rules.route import check
from tests.rules import NOW, make_minimal_case


class _FakeResolver:
    """Bộ phân giải giả trả về KetQuaPhanGiai dựng sẵn theo chi_tiet_y_lenh_id."""

    def __init__(self, mapping: dict[str, KetQuaPhanGiai]) -> None:
        self._mapping = mapping

    def resolve_line(self, ca: object, line: ChiTietYLenh) -> KetQuaPhanGiai:
        del ca
        return self._mapping.get(
            line.chi_tiet_y_lenh_id,
            KetQuaPhanGiai(trang_thai="khong_nhan_dien", ly_do="Không có trong giả lập"),
        )


def _tp(hoat_chat_id: str, ten_inn: str | None = None, loai: str = "thuoc") -> ThanhPhanPhanGiai:
    """Tạo một thành phần phân giải tối thiểu cho test."""
    return ThanhPhanPhanGiai(
        hoat_chat_id=hoat_chat_id,
        ten_inn=ten_inn or hoat_chat_id,
        ten_viet=None,
        ma_atc=[],
        ddinter_id=None,
        loai=loai,
    )


def _base_route_config(*rules: RouteRule) -> RouteConfig:
    """Dựng RouteConfig mẫu với bảng chuẩn hoá cơ bản."""
    return RouteConfig(
        ten="Đường dùng thử nghiệm",
        phien_ban="test-v1",
        bang_chuan_hoa_duong_dung=RouteNormalization(
            khoa_sang_ma={
                "uong": "uong",
                "tiem tinh mach": "tiem_tinh_mach",
                "truyen tinh mach": "truyen_tinh_mach",
                "tiem bap": "tiem_bap",
                "tiem duoi da": "tiem_duoi_da",
                "dat": None,
                "dat truc trang": "dat_truc_trang",
            },
            tu_mo_ho={
                "dat": "Phải hỏi: đặt trực tràng (dat_truc_trang) hay đặt âm đạo (dat_am_dao)",
            },
        ),
        nhom=rules,
    )


def test_levofloxacin_oral_product_ordered_iv() -> None:
    """Sản phẩm đường uống nhưng kê tiêm tĩnh mạch -> can_xem nghiem_trong."""
    hc = HoatChat(hoat_chat_id="levofloxacin", ten_hoat_chat="Levofloxacin")
    thuoc = Thuoc(
        thuoc_id="T-LEVO-500",
        ten_thuoc="Levofloxacin 500 mg",
        duong_dung="uống",
        thanh_phan=[ThanhPhan(hoat_chat_id="levofloxacin", ham_luong_thanh_phan=500, don_vi="mg")],
    )
    ca = make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-LEVO",
                thuoc_id="T-LEVO-500",
                duong_dung="tiêm tĩnh mạch",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
        ],
        danh_muc_thuoc=[thuoc],
        danh_muc_hoat_chat=[hc],
    )
    resolver = _FakeResolver(
        {
            "CT-LEVO": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("levofloxacin", "Levofloxacin")],
                nguon_khop="danh_muc_ca",
            ),
        }
    )
    cfg = _base_route_config(
        RouteRule(
            ma_dong="levofloxacin|dang_uong",
            hoat_chat_ids=("levofloxacin",),
            nhom_dang_bao_che="dang_uong",
            duong_dung_hop_le=("uong",),
            nguon=(
                RouteSource(
                    loai="dav_dang_bao_che",
                    so_san_pham_dav=120,
                    vi_du_so_dang_ky="893110000001",
                ),
                RouteSource(
                    loai="ndc_openfda",
                    route_goc=(RouteCount(route="ORAL", so_san_pham=80),),
                    truy_van="https://api.fda.gov/drug/ndc.json?search=levofloxacin",
                ),
            ),
        )
    )

    findings = check(ca, resolver=resolver, config=cfg)  # type: ignore[arg-type]
    assert len(findings) == 1
    f = findings[0]
    assert f.yeu_to == 3
    assert f.ma_luat == "duong_dung_khac_dang_bao_che"
    assert f.ket_luan == "can_xem"
    assert f.muc_do == "nghiem_trong"
    assert "Levofloxacin 500 mg" in f.mo_ta
    assert "tiêm tĩnh mạch" in f.mo_ta
    assert "tiem_tinh_mach" in f.mo_ta
    assert any(c.loai == "tai_lieu" and "(chờ dược sĩ duyệt)" in c.mo_ta for c in f.can_cu)


def test_levofloxacin_iv_infusion_valid() -> None:
    """Levofloxacin dạng truyền kê truyền tĩnh mạch -> dat."""
    hc = HoatChat(hoat_chat_id="levofloxacin", ten_hoat_chat="Levofloxacin")
    thuoc = Thuoc(
        thuoc_id="T-LEVO-750",
        ten_thuoc="Levofloxacin 750 mg/150 mL",
        duong_dung="truyền tĩnh mạch",
        thanh_phan=[ThanhPhan(hoat_chat_id="levofloxacin", ham_luong_thanh_phan=750, don_vi="mg")],
    )
    ca = make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-LEVO-IV",
                thuoc_id="T-LEVO-750",
                duong_dung="truyền tĩnh mạch",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
        ],
        danh_muc_thuoc=[thuoc],
        danh_muc_hoat_chat=[hc],
    )
    resolver = _FakeResolver(
        {
            "CT-LEVO-IV": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("levofloxacin", "Levofloxacin")],
                nguon_khop="danh_muc_ca",
            ),
        }
    )
    cfg = _base_route_config(
        RouteRule(
            ma_dong="levofloxacin|dang_tiem_truyen",
            hoat_chat_ids=("levofloxacin",),
            nhom_dang_bao_che="dang_tiem_truyen",
            duong_dung_hop_le=("tiem_tinh_mach", "truyen_tinh_mach"),
            nguon=(
                RouteSource(
                    loai="ndc_openfda",
                    route_goc=(RouteCount(route="INTRAVENOUS", so_san_pham=45),),
                    truy_van="https://api.fda.gov/drug/ndc.json?search=levofloxacin+iv",
                ),
            ),
        )
    )

    findings = check(ca, resolver=resolver, config=cfg)  # type: ignore[arg-type]
    assert len(findings) == 1
    assert findings[0].ma_luat == "duong_dung_hop_le"
    assert findings[0].ket_luan == "dat"
    assert findings[0].muc_do == "thong_tin"


def test_iv_push_and_infusion_equivalent() -> None:
    """tiem_tinh_mach và truyen_tinh_mach tương đương nhau khi nguồn chỉ ghi một trong hai."""
    hc = HoatChat(hoat_chat_id="ceftriaxone", ten_hoat_chat="Ceftriaxone")
    thuoc = Thuoc(
        thuoc_id="T-CEF-1G",
        ten_thuoc="Ceftriaxone 1 g",
        duong_dung="truyền tĩnh mạch",
        thanh_phan=[ThanhPhan(hoat_chat_id="ceftriaxone")],
    )
    ca = make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-CEF",
                thuoc_id="T-CEF-1G",
                duong_dung="tiêm tĩnh mạch",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
        ],
        danh_muc_thuoc=[thuoc],
        danh_muc_hoat_chat=[hc],
    )
    resolver = _FakeResolver(
        {
            "CT-CEF": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("ceftriaxone")],
                nguon_khop="danh_muc_ca",
            ),
        }
    )
    cfg = _base_route_config(
        RouteRule(
            ma_dong="ceftriaxone|dang_tiem_truyen",
            hoat_chat_ids=("ceftriaxone",),
            nhom_dang_bao_che="dang_tiem_truyen",
            duong_dung_hop_le=("truyen_tinh_mach",),
            nguon=(RouteSource(loai="dav_dang_bao_che", so_san_pham_dav=50),),
        )
    )

    findings = check(ca, resolver=resolver, config=cfg)  # type: ignore[arg-type]
    assert len(findings) == 1
    assert findings[0].ma_luat == "duong_dung_hop_le"
    assert findings[0].ket_luan == "dat"


def test_ambiguous_route_dat_cannot_normalize() -> None:
    """Đường dùng 'dat' mơ hồ -> khong_du_du_lieu, muc_do=None."""
    hc = HoatChat(hoat_chat_id="acetaminophen", ten_hoat_chat="Paracetamol")
    thuoc = Thuoc(
        thuoc_id="T-PARA-SUPP",
        ten_thuoc="Paracetamol 300 mg đạn",
        duong_dung="đặt trực tràng",
        thanh_phan=[ThanhPhan(hoat_chat_id="acetaminophen")],
    )
    ca = make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-DAT",
                thuoc_id="T-PARA-SUPP",
                duong_dung="dat",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
        ],
        danh_muc_thuoc=[thuoc],
        danh_muc_hoat_chat=[hc],
    )
    resolver = _FakeResolver(
        {
            "CT-DAT": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("acetaminophen")],
                nguon_khop="danh_muc_ca",
            ),
        }
    )
    cfg = _base_route_config()

    findings = check(ca, resolver=resolver, config=cfg)  # type: ignore[arg-type]
    assert len(findings) == 1
    f = findings[0]
    assert f.ma_luat == "duong_dung_khong_chuan_hoa_duoc"
    assert f.ket_luan == "khong_du_du_lieu"
    assert f.muc_do is None
    assert f.thong_tin_con_thieu == ["duong_dung_chuan_hoa"]
    assert "dat" in f.mo_ta


def test_missing_route_rule_returns_missing_source() -> None:
    """Không có hàng trong bảng -> khong_du_du_lieu duong_dung_thieu_nguon."""
    hc = HoatChat(hoat_chat_id="thuoc_moi", ten_hoat_chat="Thuốc mới")
    thuoc = Thuoc(
        thuoc_id="T-MOI",
        ten_thuoc="Thuốc mới 100 mg",
        duong_dung="uống",
        thanh_phan=[ThanhPhan(hoat_chat_id="thuoc_moi")],
    )
    ca = make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-MOI",
                thuoc_id="T-MOI",
                duong_dung="uống",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
        ],
        danh_muc_thuoc=[thuoc],
        danh_muc_hoat_chat=[hc],
    )
    resolver = _FakeResolver(
        {
            "CT-MOI": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("thuoc_moi")],
                nguon_khop="danh_muc_ca",
            ),
        }
    )
    cfg = _base_route_config()

    findings = check(ca, resolver=resolver, config=cfg)  # type: ignore[arg-type]
    assert len(findings) == 1
    f = findings[0]
    assert f.ma_luat == "duong_dung_thieu_nguon"
    assert f.ket_luan == "khong_du_du_lieu"
    assert f.muc_do is None
    assert f.thong_tin_con_thieu == ["nguon_duong_dung"]


def test_same_form_group_outside_source_returns_can_luu_y() -> None:
    """Cùng nhóm dang_tiem_truyen nhưng tiêm dưới da không có trong nguồn -> can_luu_y."""
    hc = HoatChat(hoat_chat_id="gentamicin", ten_hoat_chat="Gentamicin")
    thuoc = Thuoc(
        thuoc_id="T-GENTA",
        ten_thuoc="Gentamicin 80 mg",
        duong_dung="tiêm bắp, truyền tĩnh mạch",
        thanh_phan=[ThanhPhan(hoat_chat_id="gentamicin")],
    )
    ca = make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-GENTA",
                thuoc_id="T-GENTA",
                duong_dung="tiêm dưới da",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
        ],
        danh_muc_thuoc=[thuoc],
        danh_muc_hoat_chat=[hc],
    )
    resolver = _FakeResolver(
        {
            "CT-GENTA": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("gentamicin")],
                nguon_khop="danh_muc_ca",
            ),
        }
    )
    cfg = _base_route_config(
        RouteRule(
            ma_dong="gentamicin|dang_tiem_truyen",
            hoat_chat_ids=("gentamicin",),
            nhom_dang_bao_che="dang_tiem_truyen",
            duong_dung_hop_le=("tiem_tinh_mach", "truyen_tinh_mach", "tiem_bap"),
            nguon=(RouteSource(loai="dav_dang_bao_che", so_san_pham_dav=28),),
        )
    )

    findings = check(ca, resolver=resolver, config=cfg)  # type: ignore[arg-type]
    assert len(findings) == 1
    f = findings[0]
    assert f.ma_luat == "duong_dung_ngoai_nguon"
    assert f.ket_luan == "can_xem"
    assert f.muc_do == "can_luu_y"
    assert "không thấy trong nguồn đã lấy, chưa phải kết luận kê sai" in f.mo_ta


def test_combo_drug_falls_back_to_single_ingredient_rows() -> None:
    """Thuốc phối hợp không có hàng gộp thì đối chiếu theo từng hoạt chất có hàng."""
    hc1 = HoatChat(hoat_chat_id="amoxicillin", ten_hoat_chat="Amoxicillin")
    hc2 = HoatChat(hoat_chat_id="clavulanic_acid", ten_hoat_chat="Acid clavulanic")
    thuoc = Thuoc(
        thuoc_id="T-AMOX-CLAV",
        ten_thuoc="Amoxicillin/Clavulanic 875/125",
        duong_dung="uống",
        thanh_phan=[
            ThanhPhan(hoat_chat_id="amoxicillin"),
            ThanhPhan(hoat_chat_id="clavulanic_acid"),
        ],
    )
    ca = make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-COMBO",
                thuoc_id="T-AMOX-CLAV",
                duong_dung="uống",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
        ],
        danh_muc_thuoc=[thuoc],
        danh_muc_hoat_chat=[hc1, hc2],
    )
    resolver = _FakeResolver(
        {
            "CT-COMBO": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("amoxicillin"), _tp("clavulanic_acid")],
                nguon_khop="danh_muc_ca",
            ),
        }
    )
    cfg = _base_route_config(
        RouteRule(
            ma_dong="amoxicillin|dang_uong",
            hoat_chat_ids=("amoxicillin",),
            nhom_dang_bao_che="dang_uong",
            duong_dung_hop_le=("uong",),
            nguon=(RouteSource(loai="dav_dang_bao_che", so_san_pham_dav=185),),
        )
    )

    findings = check(ca, resolver=resolver, config=cfg)  # type: ignore[arg-type]
    assert len(findings) == 1
    assert findings[0].ket_luan == "dat"


def test_missing_data_invariants_and_exclusions() -> None:
    """Bỏ qua dịch truyền và không phải thuốc; thiếu dữ liệu luôn có muc_do=None."""
    hc = HoatChat(hoat_chat_id="levofloxacin", ten_hoat_chat="Levofloxacin")
    thuoc_no_form = Thuoc(
        thuoc_id="T-NO-FORM",
        ten_thuoc="Levofloxacin không rõ dạng",
        duong_dung=None,
        thanh_phan=[ThanhPhan(hoat_chat_id="levofloxacin")],
    )
    ca = make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-UNRES",
                ten_tu_do="Thuốc lạ",
                duong_dung="uống",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-NO-ROUTE",
                thuoc_id="T-NO-FORM",
                duong_dung=None,
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-NO-FORM",
                thuoc_id="T-NO-FORM",
                duong_dung="uống",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-NACL",
                ten_tu_do="Natri clorid 0,9%",
                duong_dung="truyền tĩnh mạch",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-TPCN",
                ten_tu_do="Men vi sinh",
                loai_san_pham="tpcn",
                duong_dung="uống",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
        ],
        danh_muc_thuoc=[thuoc_no_form],
        danh_muc_hoat_chat=[hc],
    )
    resolver = _FakeResolver(
        {
            "CT-UNRES": KetQuaPhanGiai(trang_thai="khong_nhan_dien", ly_do="Không khớp"),
            "CT-NO-ROUTE": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("levofloxacin")],
            ),
            "CT-NO-FORM": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("levofloxacin")],
            ),
            "CT-NACL": KetQuaPhanGiai(
                trang_thai="khong_ap_dung",
                thanh_phan=[_tp("sodium_chloride", loai="dich_truyen_dien_giai")],
            ),
        }
    )
    cfg = _base_route_config()

    assert check(ca, resolver=None, config=cfg) == []

    findings = check(ca, resolver=resolver, config=cfg)  # type: ignore[arg-type]
    assert len(findings) == 3
    for f in findings:
        assert f.ket_luan == "khong_du_du_lieu"
        assert f.muc_do is None
        assert f.thong_tin_con_thieu

    by_line = {f.chi_tiet_y_lenh_id[0]: f for f in findings}
    assert by_line["CT-UNRES"].thong_tin_con_thieu == ["hoat_chat"]
    assert by_line["CT-NO-ROUTE"].ma_luat == "duong_dung_thieu"
    assert by_line["CT-NO-FORM"].ma_luat == "duong_dung_thieu_dang_bao_che"


def test_load_real_route_config_from_kb() -> None:
    """Nạp tệp thật data/kb/duong_dung_hop_le.json và kiểm tra có hàng."""
    cfg = load_route_config()
    assert len(cfg.nhom) > 0
    assert cfg.bang_chuan_hoa_duong_dung.khoa_sang_ma["uong"] == "uong"
