"""Ghép phát hiện của bộ luật với các đề xuất đã kiểm chứng từ LLM."""

from app.llm.schema import NhanDinhCuoi, NhanDinhDaKiem, NhanDinhDeXuat
from app.rules.types import PhatHien


def _severity_rank(ket_luan: str, muc_do: str | None) -> float:
    """Thứ tự mức độ cảnh báo: cao hơn nghĩa là nghiêm trọng hơn."""
    if ket_luan == "can_xem":
        if muc_do == "nghiem_trong":
            return 5.0
        if muc_do == "can_luu_y":
            return 4.0
        return 3.5
    if ket_luan == "ngoai_hdsd":
        return 3.0
    if ket_luan == "khong_du_du_lieu":
        return 2.0
    return 1.0


def _lines_overlap(a: list[str], b: list[str]) -> bool:
    """Hai nhận định giao nhau khi trùng dòng y lệnh hoặc một bên áp dụng cả đơn."""
    if not a or not b:
        return True
    return bool(set(a) & set(b))


def _matches_rule_for_explanation(dx: NhanDinhDeXuat, ph: PhatHien) -> bool:
    """Kiểm tra đề xuất diễn giải khớp đúng mã luật, yếu tố, tập dòng, kết luận và mức độ."""
    if dx.bo_sung_cho_ma_luat != ph.ma_luat:
        return False
    if dx.yeu_to != ph.yeu_to:
        return False
    if set(dx.chi_tiet_y_lenh_id) != set(ph.chi_tiet_y_lenh_id):
        return False
    if dx.ket_luan != ph.ket_luan:
        return False
    if dx.ket_luan == "dat":
        return dx.muc_do is None and ph.muc_do in (None, "thong_tin")
    return dx.muc_do == ph.muc_do


def merge(
    phat_hien_luat: list[PhatHien],
    da_kiem: list[NhanDinhDaKiem],
) -> tuple[list[NhanDinhCuoi], list[str]]:
    """Ghép phát hiện của luật (nguyên vẹn, giữ thứ tự) với nhận định LLM đã kiểm chứng."""
    warnings: list[str] = []
    rule_items = [NhanDinhCuoi(nguon_goc="luat", phat_hien=ph) for ph in phat_hien_luat]
    verified_items: list[NhanDinhCuoi] = []
    unverified_items: list[NhanDinhCuoi] = []

    for item in da_kiem:
        dx = item.de_xuat
        if dx.bo_sung_cho_ma_luat is not None:
            matched_idx = next(
                (
                    idx
                    for idx, ph in enumerate(phat_hien_luat)
                    if _matches_rule_for_explanation(dx, ph)
                ),
                None,
            )
            if matched_idx is None:
                warnings.append("dien_giai_khong_khop")
                continue
            if item.dat:
                if rule_items[matched_idx].dien_giai is None:
                    rule_items[matched_idx] = rule_items[matched_idx].model_copy(
                        update={"dien_giai": dx}
                    )
                else:
                    warnings.append("dien_giai_khong_khop")
            elif dx.ket_luan == "dat":
                warnings.append("ai_dat_bi_loai")
            else:
                unverified_items.append(
                    NhanDinhCuoi(
                        nguon_goc="ai_chua_kiem_chung",
                        de_xuat=dx,
                        loi_kiem_chung=list(item.loi),
                    )
                )
            continue

        dx_rank = _severity_rank(dx.ket_luan, dx.muc_do)
        downgrades = any(
            ph.ket_luan != "dat"
            and dx.yeu_to == ph.yeu_to
            and _lines_overlap(dx.chi_tiet_y_lenh_id, ph.chi_tiet_y_lenh_id)
            and (dx.ket_luan == "dat" or dx_rank < _severity_rank(ph.ket_luan, ph.muc_do))
            for ph in phat_hien_luat
        )
        if downgrades:
            warnings.append("ai_ha_muc_bi_loai")
            continue

        duplicates_rule = any(
            dx.yeu_to == ph.yeu_to
            and set(dx.chi_tiet_y_lenh_id) == set(ph.chi_tiet_y_lenh_id)
            and dx.ket_luan == ph.ket_luan
            for ph in phat_hien_luat
        )
        if duplicates_rule:
            warnings.append("trung_voi_luat")
            continue

        if dx.ket_luan == "dat":
            warnings.append("ai_dat_bi_loai")
            continue

        if item.dat:
            verified_items.append(NhanDinhCuoi(nguon_goc="ai_da_kiem_chung", de_xuat=dx))
        else:
            unverified_items.append(
                NhanDinhCuoi(
                    nguon_goc="ai_chua_kiem_chung",
                    de_xuat=dx,
                    loi_kiem_chung=list(item.loi),
                )
            )

    return [*rule_items, *verified_items, *unverified_items], warnings
