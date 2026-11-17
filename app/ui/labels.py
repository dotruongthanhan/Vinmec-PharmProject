"""Bảng nhãn tiếng Việt tập trung cho toàn bộ mã nội bộ hiển thị trên giao diện."""

from collections.abc import Mapping

TEN_YEU_TO: dict[int, str] = {
    1: "Dị ứng, quá mẫn",
    2: "Trùng lặp thuốc",
    3: "Chỉ định, liều, đường dùng",
    4: "Tương tác thuốc",
    5: "Độc tính",
    6: "Cơ địa và xét nghiệm",
    7: "Yếu tố khác (lịch dùng…)",
}

NHAN_KET_LUAN: dict[str, str] = {
    "dat": "Đạt",
    "can_xem": "Cần xem",
    "khong_du_du_lieu": "Không đủ dữ liệu",
    "ngoai_hdsd": "Ngoài HDSD / phác đồ",
}

NHAN_MUC_DO: dict[str, str] = {
    "nghiem_trong": "Nghiêm trọng",
    "can_luu_y": "Cần lưu ý",
    "thong_tin": "Thông tin",
}

NHAN_DAU_VAO: dict[str, str] = {
    "can_nang_kg": "cân nặng",
    "chieu_cao_cm": "chiều cao",
    "creatinin": "creatinin máu",
    "tuoi": "tuổi",
    "gioi_tinh": "giới tính",
    "creatinin_don_vi": "đơn vị creatinin",
    "so_lieu_hop_le": "số liệu hợp lệ",
}

NHAN_SINH_HIEU: dict[str, str] = {
    "can_nang": "Cân nặng",
    "chieu_cao": "Chiều cao",
    "nhiet_do": "Nhiệt độ",
    "huyet_ap": "Huyết áp",
    "mach": "Mạch",
    "nhip_tho": "Nhịp thở",
    "spo2": "SpO2",
}

NHAN_LOAI_CAN_CU: dict[str, str] = {
    "du_lieu": "Dữ liệu ca",
    "tinh_toan": "Tính toán",
    "tai_lieu": "Tài liệu",
}

NHAN_LUONG_DUYET: dict[str, str] = {
    "truc_tiep": "Trực tiếp",
    "hau_kiem": "Hậu kiểm",
}

NHAN_TRANG_THAI_DONG: dict[str, str] = {
    "active": "Đang dùng",
    "pending": "Chờ duyệt",
    "discontinued": "Đã ngừng",
    "completed": "Đã hoàn thành",
}

NHAN_LOAI_DIEU_TRI: dict[str, str] = {
    "noi_tru": "Nội trú",
    "ngoai_tru": "Ngoại trú",
}

NHAN_LOAI_HO_SO: dict[str, str] = {
    "phieu_dieu_tri": "Phiếu điều trị",
    "phieu_kham": "Phiếu khám",
    "hoi_chan": "Hội chẩn",
    "ghi_chu_dieu_duong": "Ghi chú điều dưỡng",
    "tom_tat_benh_an": "Tóm tắt bệnh án",
    "khac": "Khác",
}

NHOM_LY_DO: dict[str, str] = {
    "khong_phu_hop_lam_sang": "Không phù hợp lâm sàng",
    "da_biet_da_xu_ly": "Đã biết, đã xử lý",
    "sai_du_lieu_dau_vao": "Sai dữ liệu đầu vào",
    "sai_nguon_hoac_nguon_cu": "Sai nguồn hoặc nguồn cũ",
    "khac": "Khác",
}

NHAN_PHAN_HOI: dict[str, str] = {
    "dong_y": "Đồng ý",
    "bac_bo": "Bác bỏ",
    "can_sua": "Cần sửa",
}

NHAN_CONG_THUC: dict[str, str] = {
    "cockcroft_gault": "CrCl (Cockcroft-Gault)",
    "egfr_ckd_epi_2021": "eGFR (CKD-EPI 2021)",
    "bmi": "BMI",
    "bsa_mosteller": "BSA (Mosteller)",
}

NHAN_CO_DIA_LOAI: dict[str, str] = {
    "mang_thai": "Mang thai",
    "cho_con_bu": "Cho con bú",
    "suy_than": "Suy thận",
    "suy_gan": "Suy gan",
    "hau_phau": "Hậu phẫu",
    "khac": "Khác",
}

NHAN_CO_DIA_TRANG_THAI: dict[str, str] = {
    "co": "Có",
    "khong": "Không",
    "chua_ro": "Chưa rõ",
}

NHAN_LOAI_TAC_NHAN: dict[str, str] = {
    "thuoc": "Thuốc",
    "thuc_an": "Thức ăn",
    "khac": "Khác",
}

NHAN_BO_LOC_HANG_DOI: dict[str, str] = {
    "tat_ca": "Tất cả",
    "can_xem": "Cần xem",
    "da_phan_hoi_het": "Đã phản hồi hết",
}


def label_of(table: Mapping[str, str], code: str) -> str:
    """Tra nhãn hiển thị, giữ nguyên mã chưa có trong bảng."""
    return table.get(code, code)
