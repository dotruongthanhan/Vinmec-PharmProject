"""Kiểm thử bảng nhãn tiếng Việt bao phủ đầy đủ các Literal của mô hình."""

from typing import Literal, get_args, get_origin

from app.domain.models import ChiTietYLenh, CoDia, DiUng, DotDieuTri, YLenh
from app.feedback import PhanHoi
from app.rules.types import CanCu, PhatHien
from app.ui.labels import (
    NHAN_CO_DIA_LOAI,
    NHAN_CO_DIA_TRANG_THAI,
    NHAN_KET_LUAN,
    NHAN_LOAI_CAN_CU,
    NHAN_LOAI_DIEU_TRI,
    NHAN_LOAI_HO_SO,
    NHAN_LOAI_TAC_NHAN,
    NHAN_LUONG_DUYET,
    NHAN_MUC_DO,
    NHAN_PHAN_HOI,
    NHAN_TRANG_THAI_DONG,
    NHOM_LY_DO,
    TEN_YEU_TO,
    label_of,
)


def _literal_values(annotation: object) -> set[str]:
    """Trích tập chuỗi từ kiểu Literal hoặc Literal | None."""
    if get_origin(annotation) is Literal:
        return {str(v) for v in get_args(annotation)}
    values: set[str] = set()
    for branch in get_args(annotation):
        if branch is type(None):
            continue
        if get_origin(branch) is Literal:
            values.update(str(v) for v in get_args(branch))
    return values


def test_rule_and_domain_literals_have_labels() -> None:
    """Mọi Literal của kết luận, mức độ, căn cứ, luồng duyệt, trạng thái, loại ĐT đều có nhãn."""
    assert set(NHAN_KET_LUAN) >= _literal_values(PhatHien.model_fields["ket_luan"].annotation)
    assert set(NHAN_MUC_DO) >= _literal_values(PhatHien.model_fields["muc_do"].annotation)
    assert set(NHAN_LOAI_CAN_CU) >= _literal_values(CanCu.model_fields["loai"].annotation)
    assert set(NHAN_LUONG_DUYET) >= _literal_values(YLenh.model_fields["luong_duyet"].annotation)
    assert set(NHAN_TRANG_THAI_DONG) >= _literal_values(
        ChiTietYLenh.model_fields["trang_thai_dong"].annotation
    )
    assert set(NHAN_LOAI_DIEU_TRI) >= _literal_values(
        DotDieuTri.model_fields["loai_dieu_tri"].annotation
    )
    assert set(NHAN_PHAN_HOI) >= _literal_values(PhanHoi.model_fields["phan_hoi"].annotation)
    assert set(NHAN_CO_DIA_LOAI) >= _literal_values(CoDia.model_fields["loai"].annotation)
    assert set(NHAN_CO_DIA_TRANG_THAI) >= _literal_values(
        CoDia.model_fields["trang_thai"].annotation
    )
    assert set(NHAN_LOAI_TAC_NHAN) >= _literal_values(
        DiUng.model_fields["loai_tac_nhan"].annotation
    )


def test_seven_factors_and_reason_groups_complete() -> None:
    """Đủ 7 yếu tố kiểm tra và đúng 5 nhóm lý do phản hồi theo thiết kế."""
    assert set(TEN_YEU_TO) == {1, 2, 3, 4, 5, 6, 7}
    assert list(NHOM_LY_DO.values()) == [
        "Không phù hợp lâm sàng",
        "Đã biết, đã xử lý",
        "Sai dữ liệu đầu vào",
        "Sai nguồn hoặc nguồn cũ",
        "Khác",
    ]
    assert len(NHAN_LOAI_HO_SO) >= 1


def test_label_of_preserves_unknown_code() -> None:
    """Mã chưa có trong bảng nhãn được trả nguyên vẹn để dễ phát hiện thiếu sót."""
    assert label_of(NHAN_TRANG_THAI_DONG, "discontinued") == "Đã ngừng"
    assert label_of(NHAN_LOAI_HO_SO, "Phiếu điều trị") == "Phiếu điều trị"
