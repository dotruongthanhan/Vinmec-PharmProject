"""Kiểm thử luật yếu tố 7: kháng sinh cần phê duyệt hoặc ưu tiên quản lý theo QĐ 5631."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.domain.models import CaBenh, ChiTietYLenh, DienBien, HoatChat, ThanhPhan, Thuoc
from app.kb.resolver.resolver import KetQuaPhanGiai, ThanhPhanPhanGiai
from app.rules.d7_config import (
    DEFAULT_STEWARDSHIP_CONFIG_PATH,
    ManagedAntibiotic,
    StewardshipConfig,
    StewardshipGroup,
    StewardshipSourceDoc,
    load_stewardship_config,
)
from app.rules.stewardship import check
from tests.rules import NOW, make_minimal_case


class _FakeResolver:
    """Bộ phân giải giả lập trả danh sách hoạt chất đã định trước theo thuoc_id hoặc tên."""

    def __init__(self, mapping: dict[str, list[str]]) -> None:
        self._mapping = mapping

    def resolve_line(self, ca: CaBenh, line: ChiTietYLenh) -> KetQuaPhanGiai:
        key = line.thuoc_id or line.ten_tu_do or ""
        ids = self._mapping.get(key, [])
        if not ids:
            return KetQuaPhanGiai(trang_thai="khong_nhan_dien", ly_do="Không có trong bảng giả")
        components = [
            ThanhPhanPhanGiai(
                hoat_chat_id=hid,
                ten_inn=hid.title(),
                ten_viet=hid.title(),
                ma_atc=[],
                ddinter_id=None,
                loai="thuoc",
            )
            for hid in ids
        ]
        return KetQuaPhanGiai(
            trang_thai="da_phan_giai",
            thanh_phan=components,
            nguon_khop="danh_muc_ca",
        )


def _sample_config() -> StewardshipConfig:
    """Dựng cấu hình bảng kháng sinh quản lý giả lập dùng cho kiểm thử đơn vị."""
    return StewardshipConfig(
        phien_ban="D7-v1",
        ngay="2026-11-19",
        trang_thai="cho_duoc_si_duyet",
        nguon_van_ban=StewardshipSourceDoc(
            so_hieu="5631/QĐ-BYT",
            ngay="2020-12-31",
            tep="data/kb_sources/van_ban_byt/qd5631_2020/qd5631_duytan.pdf",
            ban_sao_thu_cap=True,
            url="https://example.org/qd5631.pdf",
        ),
        nhom=(
            StewardshipGroup(
                ma_nhom="phe_duyet_truoc",
                ten_nhom_van_ban="Danh mục kháng sinh cần phê duyệt trước khi sử dụng",
                yeu_cau="Phải hội chẩn và được lãnh đạo phê duyệt trước khi sử dụng.",
                trang_pdf=12,
            ),
            StewardshipGroup(
                ma_nhom="uu_tien_quan_ly",
                ten_nhom_van_ban="Danh mục kháng sinh ưu tiên quản lý",
                yeu_cau="Theo dõi sát chỉ định, thời gian dùng và đánh giá xuống thang.",
                trang_pdf=13,
            ),
        ),
        khang_sinh=(
            ManagedAntibiotic(
                ten_trong_van_ban="Meropenem",
                hoat_chat_ids=("meropenem",),
                ma_nhom="phe_duyet_truoc",
                trang_pdf=12,
                trang_thai="cho_duoc_si_duyet",
            ),
            ManagedAntibiotic(
                ten_trong_van_ban="Levofloxacin",
                hoat_chat_ids=("levofloxacin",),
                ma_nhom="uu_tien_quan_ly",
                trang_pdf=13,
                trang_thai="cho_duoc_si_duyet",
            ),
        ),
    )


def _case_with_drug(
    *,
    thuoc_id: str,
    ten_thuoc: str,
    hoat_chat_id: str,
    dien_bien: list[DienBien] | None = None,
    in_pending: bool = True,
) -> CaBenh:
    """Tạo ca bệnh có thuốc nằm trong y lệnh chờ duyệt hoặc thuốc đang dùng."""
    hc = HoatChat(hoat_chat_id=hoat_chat_id, ten_hoat_chat=ten_thuoc, ten_quoc_te=hoat_chat_id)
    drug = Thuoc(
        thuoc_id=thuoc_id,
        ten_thuoc=ten_thuoc,
        thanh_phan=[ThanhPhan(hoat_chat_id=hoat_chat_id)],
        la_khang_sinh=True,
    )
    line = ChiTietYLenh(
        chi_tiet_y_lenh_id="CT-ABX" if in_pending else "CT-CUR",
        thuoc_id=thuoc_id,
        bat_dau=NOW,
        trang_thai_dong="active",
    )
    if in_pending:
        ca = make_minimal_case(
            chi_tiet=[line],
            danh_muc_thuoc=[drug],
            danh_muc_hoat_chat=[hc],
        )
    else:
        hc_other = HoatChat(hoat_chat_id="paracetamol", ten_hoat_chat="Paracetamol")
        drug_other = Thuoc(
            thuoc_id="T-PARA",
            ten_thuoc="Paracetamol 500 mg",
            thanh_phan=[ThanhPhan(hoat_chat_id="paracetamol")],
        )
        pending_line = ChiTietYLenh(
            chi_tiet_y_lenh_id="CT-PARA",
            thuoc_id="T-PARA",
            bat_dau=NOW,
            trang_thai_dong="active",
        )
        ca = make_minimal_case(
            chi_tiet=[pending_line],
            thuoc_dang_dung=[line],
            danh_muc_thuoc=[drug_other, drug],
            danh_muc_hoat_chat=[hc_other, hc],
        )
    if dien_bien is not None:
        return ca.model_copy(update={"dien_bien": dien_bien})
    return ca


def test_stewardship_returns_empty_when_resolver_is_none() -> None:
    """Thiếu resolver trả về danh sách rỗng."""
    ca = _case_with_drug(thuoc_id="T-MERO", ten_thuoc="Meropenem 1 g", hoat_chat_id="meropenem")
    assert check(ca, resolver=None, config=_sample_config()) == []


def test_stewardship_pre_approval_without_consultation_flags_can_xem() -> None:
    """Kháng sinh nhóm phe_duyet_truoc chưa có diễn biến hội chẩn -> can_xem can_luu_y."""
    ca = _case_with_drug(thuoc_id="T-MERO", ten_thuoc="Meropenem 1 g", hoat_chat_id="meropenem")
    resolver = _FakeResolver({"T-MERO": ["meropenem"]})
    config = _sample_config()

    findings = check(ca, resolver=resolver, config=config)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.ma_luat == "khang_sinh_can_phe_duyet"
    assert finding.yeu_to == 7
    assert finding.ket_luan == "can_xem"
    assert finding.muc_do == "can_luu_y"
    assert finding.chi_tiet_y_lenh_id == ["CT-ABX"]
    assert "Danh mục kháng sinh cần phê duyệt trước khi sử dụng" in finding.mo_ta
    assert "Phải hội chẩn và được lãnh đạo phê duyệt trước khi sử dụng." in finding.mo_ta
    assert "dò theo chữ trong diễn biến" in finding.mo_ta

    doc_evidences = [item for item in finding.can_cu if item.loai == "tai_lieu"]
    assert len(doc_evidences) == 1
    assert doc_evidences[0].mo_ta == (
        "QĐ 5631/QĐ-BYT (bản sao thứ cấp), trang 12: "
        "Danh mục kháng sinh cần phê duyệt trước khi sử dụng — "
        "https://example.org/qd5631.pdf (chờ dược sĩ duyệt)"
    )


def test_stewardship_pre_approval_with_vietnamese_consultation_note_returns_dat() -> None:
    """Có diễn biến 'Hội chẩn khoa ... đồng ý dùng meropenem' -> dat thong_tin và trích <= 200."""
    long_note = (
        "Bệnh nhân sốt cao kéo dài, procalcitonin tăng. "
        "Hội chẩn khoa Hồi sức tích cực và Dược lâm sàng thống nhất đồng ý dùng meropenem "
        "liều 1 g mỗi 8 giờ truyền tĩnh mạch kéo dài trong 3 giờ, "
        "theo dõi chức năng thận và đáp ứng lâm sàng sau 48 đến 72 giờ điều trị."
    )
    dien_bien = [
        DienBien(
            dien_bien_id="DB-HC-1",
            loai_ho_so="Diễn biến điều trị",
            noi_dung=long_note,
            thoi_diem_ghi=NOW - timedelta(hours=1),
        )
    ]
    ca = _case_with_drug(
        thuoc_id="T-MERO",
        ten_thuoc="Meropenem 1 g",
        hoat_chat_id="meropenem",
        dien_bien=dien_bien,
    )
    resolver = _FakeResolver({"T-MERO": ["meropenem"]})

    findings = check(ca, resolver=resolver, config=_sample_config())

    assert len(findings) == 1
    finding = findings[0]
    assert finding.ma_luat == "khang_sinh_da_co_hoi_chan"
    assert finding.yeu_to == 7
    assert finding.ket_luan == "dat"
    assert finding.muc_do == "thong_tin"
    assert "dò theo chữ trong diễn biến" in finding.mo_ta

    data_evidences = [item for item in finding.can_cu if item.loai == "du_lieu"]
    assert len(data_evidences) == 1
    assert data_evidences[0].ban_ghi_id == "DB-HC-1"
    assert len(data_evidences[0].mo_ta) <= 200
    assert "Hội chẩn" in data_evidences[0].mo_ta


def test_stewardship_pre_approval_matches_phe_duyet_in_loai_ho_so() -> None:
    """Phát hiện cụm 'phe duyet' không phân biệt dấu trong loai_ho_so."""
    dien_bien = [
        DienBien(
            dien_bien_id="DB-PD-1",
            loai_ho_so="Phiếu phê duyệt kháng sinh",
            noi_dung="Đồng ý sử dụng meropenem 1 g x 3 lần/ngày.",
            thoi_diem_ghi=NOW,
        )
    ]
    ca = _case_with_drug(
        thuoc_id="T-MERO",
        ten_thuoc="Meropenem 1 g",
        hoat_chat_id="meropenem",
        dien_bien=dien_bien,
    )
    resolver = _FakeResolver({"T-MERO": ["meropenem"]})

    findings = check(ca, resolver=resolver, config=_sample_config())

    assert len(findings) == 1
    assert findings[0].ma_luat == "khang_sinh_da_co_hoi_chan"
    assert findings[0].ket_luan == "dat"
    data_ev = next(item for item in findings[0].can_cu if item.loai == "du_lieu")
    assert data_ev.ban_ghi_id == "DB-PD-1"
    assert len(data_ev.mo_ta) <= 200


def test_stewardship_priority_managed_group_returns_thong_tin() -> None:
    """Kháng sinh nhóm uu_tien_quan_ly trả về can_xem mức thong_tin với yeu_cau nguyên văn."""
    ca = _case_with_drug(
        thuoc_id="T-LEVO",
        ten_thuoc="Levofloxacin 500 mg",
        hoat_chat_id="levofloxacin",
    )
    resolver = _FakeResolver({"T-LEVO": ["levofloxacin"]})

    findings = check(ca, resolver=resolver, config=_sample_config())

    assert len(findings) == 1
    finding = findings[0]
    assert finding.ma_luat == "khang_sinh_uu_tien_quan_ly"
    assert finding.yeu_to == 7
    assert finding.ket_luan == "can_xem"
    assert finding.muc_do == "thong_tin"
    assert "Theo dõi sát chỉ định, thời gian dùng và đánh giá xuống thang." in finding.mo_ta


def test_stewardship_antibiotic_not_in_table_produces_no_finding() -> None:
    """Kháng sinh không nằm trong bảng cấu hình không sinh phát hiện."""
    ca = _case_with_drug(
        thuoc_id="T-CEF",
        ten_thuoc="Ceftriaxon 1 g",
        hoat_chat_id="ceftriaxone",
    )
    resolver = _FakeResolver({"T-CEF": ["ceftriaxone"]})

    assert check(ca, resolver=resolver, config=_sample_config()) == []


def test_stewardship_current_medication_not_pending_produces_no_finding() -> None:
    """Kháng sinh nằm ở thuoc_dang_dung (không phải y lệnh chờ duyệt) không sinh phát hiện."""
    ca = _case_with_drug(
        thuoc_id="T-MERO",
        ten_thuoc="Meropenem 1 g",
        hoat_chat_id="meropenem",
        in_pending=False,
    )
    resolver = _FakeResolver({"T-MERO": ["meropenem"]})

    assert check(ca, resolver=resolver, config=_sample_config()) == []


@pytest.mark.can_du_lieu
def test_stewardship_loads_real_kb_file_when_available() -> None:
    """Kiểm tra nạp tệp thật data/kb/khang_sinh_quan_ly.json; bỏ qua nếu chưa dựng."""
    if not DEFAULT_STEWARDSHIP_CONFIG_PATH.exists():
        pytest.skip("Chưa có tệp data/kb/khang_sinh_quan_ly.json")

    config = load_stewardship_config(DEFAULT_STEWARDSHIP_CONFIG_PATH)
    assert config.nhom
    assert config.khang_sinh
    assert config.nguon_van_ban.so_hieu == "5631/QĐ-BYT"
