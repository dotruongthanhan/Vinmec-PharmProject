"""Luật yếu tố 1: kiểm tra dị ứng hoạt chất, dị ứng chéo cùng nhóm và sản phẩm chưa rõ."""

from app.domain.loader import ingredients_of
from app.domain.models import CaBenh, ChiTietYLenh, DiUng, HoatChat, Thuoc
from app.rules.types import CanCu, PhatHien, line_label, normalize_text, pending_lines

_YEU_TO = 1


def _build_allergy_evidence(du: DiUng) -> CanCu:
    """Tạo căn cứ dữ liệu trỏ tới bản ghi dị ứng."""
    phan_ung = du.phan_ung if du.phan_ung else "chưa ghi nhận phản ứng"
    return CanCu(
        loai="du_lieu",
        ban_ghi_id=du.di_ung_id,
        mo_ta=f"Tác nhân dị ứng: {du.tac_nhan}; phản ứng: {phan_ung}",
    )


def _match_line_allergy(
    line: ChiTietYLenh,
    ingredients: list[HoatChat],
    du: DiUng,
    thuoc_by_id: dict[str, Thuoc],
) -> PhatHien | None:
    """Đối chiếu một cặp (dòng thuốc, bản ghi dị ứng), ưu tiên trùng hoạt chất."""
    if du.loai_tac_nhan != "thuoc":
        return None

    label = line_label(line, thuoc_by_id)
    if du.hoat_chat_id is not None:
        matched_hc = next(
            (hc for hc in ingredients if hc.hoat_chat_id == du.hoat_chat_id),
            None,
        )
        if matched_hc is not None:
            return PhatHien(
                ma_luat="di_ung_trung_hoat_chat",
                yeu_to=_YEU_TO,
                ket_luan="can_xem",
                muc_do="nghiem_trong",
                chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                mo_ta=(
                    f"Thuốc {label} chứa hoạt chất {matched_hc.ten_hoat_chat} "
                    f"trùng tiền sử dị ứng {du.tac_nhan}"
                ),
                can_cu=[_build_allergy_evidence(du)],
            )

    allergy_group = normalize_text(du.nhom_duoc_ly)
    if not allergy_group:
        return None

    same_group_hc = next(
        (hc for hc in ingredients if normalize_text(hc.nhom_duoc_ly) == allergy_group),
        None,
    )
    if same_group_hc is None:
        return None

    return PhatHien(
        ma_luat="di_ung_cung_nhom",
        yeu_to=_YEU_TO,
        ket_luan="can_xem",
        muc_do="nghiem_trong",
        chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
        mo_ta=(
            f"Nguy cơ dị ứng chéo cùng nhóm {du.nhom_duoc_ly} giữa "
            f"{same_group_hc.ten_hoat_chat} ({label}) và tiền sử dị ứng {du.tac_nhan}"
        ),
        can_cu=[_build_allergy_evidence(du)],
    )


def check(ca: CaBenh) -> list[PhatHien]:
    """Kiểm tra dị ứng cho các dòng y lệnh đang chờ duyệt."""
    lines = pending_lines(ca)
    all_line_ids = [line.chi_tiet_y_lenh_id for line in lines]
    status = ca.tinh_trang_di_ung

    if status.trang_thai == "chua_co_thong_tin":
        return [
            PhatHien(
                ma_luat="di_ung_thieu_thong_tin",
                yeu_to=_YEU_TO,
                ket_luan="khong_du_du_lieu",
                muc_do=None,
                chi_tiet_y_lenh_id=all_line_ids,
                mo_ta="Hồ sơ chưa có thông tin dị ứng",
                can_cu=[
                    CanCu(
                        loai="du_lieu",
                        ban_ghi_id=None,
                        mo_ta="Trạng thái dị ứng: chua_co_thong_tin",
                    ),
                ],
                thong_tin_con_thieu=["tinh_trang_di_ung"],
            ),
        ]

    if status.trang_thai == "khong_di_ung_da_hoi":
        source_part = f" từ {status.nguon}" if status.nguon else ""
        time_part = f" lúc {status.thoi_diem.isoformat()}" if status.thoi_diem else ""
        return [
            PhatHien(
                ma_luat="di_ung_khong_co",
                yeu_to=_YEU_TO,
                ket_luan="dat",
                muc_do="thong_tin",
                chi_tiet_y_lenh_id=all_line_ids,
                mo_ta="Người bệnh đã được khai thác: không có tiền sử dị ứng",
                can_cu=[
                    CanCu(
                        loai="du_lieu",
                        ban_ghi_id=None,
                        mo_ta=f"Đã khai thác không dị ứng{source_part}{time_part}",
                    ),
                ],
            ),
        ]

    thuoc_by_id = {thuoc.thuoc_id: thuoc for thuoc in ca.danh_muc_thuoc}
    matched_findings: list[PhatHien] = []
    unknown_findings: list[PhatHien] = []
    known_line_ids: list[str] = []

    for line in lines:
        if line.thuoc_id is None or line.thuoc_id.strip() == "":
            label = line_label(line, thuoc_by_id)
            unknown_desc = f"Sản phẩm gõ tay '{label}' chưa rõ thành phần để đối chiếu dị ứng"
            unknown_findings.append(
                PhatHien(
                    ma_luat="di_ung_san_pham_khong_ro",
                    yeu_to=_YEU_TO,
                    ket_luan="khong_du_du_lieu",
                    muc_do=None,
                    chi_tiet_y_lenh_id=[line.chi_tiet_y_lenh_id],
                    mo_ta=unknown_desc,
                    can_cu=[
                        CanCu(
                            loai="du_lieu",
                            ban_ghi_id=line.chi_tiet_y_lenh_id,
                            mo_ta=f"Dòng '{label}' không có mã thuốc trong danh mục",
                        ),
                    ],
                    thong_tin_con_thieu=["thanh_phan_san_pham"],
                ),
            )
            continue

        known_line_ids.append(line.chi_tiet_y_lenh_id)
        ingredients = ingredients_of(ca, line)
        for du in ca.di_ung:
            finding = _match_line_allergy(line, ingredients, du, thuoc_by_id)
            if finding is not None:
                matched_findings.append(finding)

    if not matched_findings and known_line_ids:
        no_match = PhatHien(
            ma_luat="di_ung_khong_khop",
            yeu_to=_YEU_TO,
            ket_luan="dat",
            muc_do="thong_tin",
            chi_tiet_y_lenh_id=known_line_ids,
            mo_ta="Không phát hiện trùng hoạt chất hoặc nhóm dược lý với tiền sử dị ứng",
            can_cu=[_build_allergy_evidence(du) for du in ca.di_ung],
        )
        return [*unknown_findings, no_match]

    return [*matched_findings, *unknown_findings]
