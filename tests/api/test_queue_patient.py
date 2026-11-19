"""Kiểm logic hàng đợi theo người bệnh: gom ca, 2 mốc thời gian và thứ tự trạng thái NB."""

from app.api import schemas as s
from app.api.service import _highest_patient_status, _map_order_status, _merge_patient_queue


def _row(**overrides: object) -> s.DongHangDoi:
    base: dict[str, object] = {
        "ca_id": "CA-1",
        "khoa": "Nội tổng hợp",
        "mo_ta": "Ca giả lập",
        "uu_tien": 1,
        "huy_hieu": "1 cần lưu ý",
        "so_nghiem_trong": 0,
        "so_can_luu_y": 1,
        "so_thieu_du_lieu": 0,
        "da_phan_hoi_het": False,
        "nguoi_benh_id": "NB-01",
        "thoi_diem_ke": "2026-11-10T08:00:00+07:00",
        "thoi_diem_ke_xa_nhat": "2026-11-10T08:00:00+07:00",
        "thoi_diem_ke_gan_nhat": "2026-11-10T08:00:00+07:00",
        "so_don_cho": 1,
        "chan_doan": [s.Diagnosis(loai_nhan="Chính", noi_dung="Viêm phổi", ma_icd10="J18.9")],
        "trang_thai_nb": "chua_duyet",
    }
    base.update(overrides)
    return s.DongHangDoi.model_validate(base)


def test_patient_status_precedence_chua_duyet_gt_dang_cho_gt_da_huy_gt_da_xong() -> None:
    assert _highest_patient_status(["da_xong", "da_huy"]) == "da_huy"
    assert _highest_patient_status(["da_xong", "da_huy", "dang_cho"]) == "dang_cho"
    assert _highest_patient_status(["da_xong", "da_huy", "dang_cho", "chua_duyet"]) == "chua_duyet"
    assert _highest_patient_status(["da_xong"]) == "da_xong"
    assert _map_order_status("ngung", is_focal=False, focal_done=False, focal_missing=0) == "da_huy"
    assert (
        _map_order_status("hoan_tat", is_focal=False, focal_done=False, focal_missing=0)
        == "da_xong"
    )


def test_merge_patient_queue_keeps_highest_priority_dual_times_and_all_diagnoses() -> None:
    rows = [
        _row(
            ca_id="CA-LOW",
            uu_tien=3,
            so_can_luu_y=0,
            so_thieu_du_lieu=1,
            thoi_diem_ke_xa_nhat="2026-11-10T09:30:00+07:00",
            thoi_diem_ke_gan_nhat="2026-11-10T09:30:00+07:00",
            so_don_cho=1,
            trang_thai_nb="dang_cho",
            chan_doan=[s.Diagnosis(loai_nhan="Kèm", noi_dung="Tăng huyết áp", ma_icd10="I10")],
        ),
        _row(
            ca_id="CA-HIGH",
            uu_tien=0,
            so_nghiem_trong=1,
            so_can_luu_y=0,
            thoi_diem_ke_xa_nhat="2026-11-10T06:00:00+07:00",
            thoi_diem_ke_gan_nhat="2026-11-10T06:00:00+07:00",
            so_don_cho=1,
            trang_thai_nb="chua_duyet",
            chan_doan=[s.Diagnosis(loai_nhan="Chính", noi_dung="Viêm phổi", ma_icd10="J18.9")],
        ),
        _row(
            ca_id="CA-OTHER",
            nguoi_benh_id="NB-02",
            uu_tien=1,
            thoi_diem_ke_xa_nhat="2026-11-10T05:00:00+07:00",
            thoi_diem_ke_gan_nhat="2026-11-10T05:00:00+07:00",
            so_don_cho=1,
            trang_thai_nb="chua_duyet",
        ),
    ]
    merged = _merge_patient_queue(rows)
    assert len(merged) == 2
    assert merged[0].nguoi_benh_id == "NB-01"
    assert merged[0].ca_id == "CA-HIGH"
    assert merged[0].uu_tien == 0
    assert merged[0].so_don_cho == 2
    assert merged[0].thoi_diem_ke_xa_nhat == "2026-11-10T06:00:00+07:00"
    assert merged[0].thoi_diem_ke_gan_nhat == "2026-11-10T09:30:00+07:00"
    assert merged[0].trang_thai_nb == "chua_duyet"
    assert {(d.noi_dung, d.ma_icd10) for d in merged[0].chan_doan} == {
        ("Tăng huyết áp", "I10"),
        ("Viêm phổi", "J18.9"),
    }
    assert merged[1].nguoi_benh_id == "NB-02"
