"""Công thức hiển thị tương ứng với các hàm tính."""

CONG_THUC_HIEN_THI: dict[str, str] = {
    "cockcroft_gault": (
        "(140 - tuổi) × cân nặng / (72 × creatinin mg/dL) × hệ số giới "
        "(nữ: 0.85; nam: 1); creatinin µmol/L / 88.4 = mg/dL"
    ),
    "egfr_ckd_epi_2021": (
        "142 × min(tỷ số, 1) ^ alpha × max(tỷ số, 1) ^ -1.2 × 0.9938 ^ tuổi × hệ số giới; "
        "tỷ số = creatinin mg/dL / kappa; nữ: kappa = 0.7, alpha = -0.241, hệ số = 1.012; "
        "nam: kappa = 0.9, alpha = -0.302, hệ số = 1; creatinin µmol/L / 88.4 = mg/dL"
    ),
    "bmi": "cân nặng kg / (chiều cao cm / 100) ^ 2",
    "bsa_mosteller": "√(chiều cao cm × cân nặng kg / 3600)",
    "bsa_dubois": "0.007184 × cân nặng kg ^ 0.425 × chiều cao cm ^ 0.725",
    "ibw_devine": "(nam: 50; nữ: 45.5) + 2.3 × (chiều cao cm / 2.54 - 60)",
    "adjusted_body_weight": (
        "IBW + 0.4 × (cân nặng kg - IBW); "
        "IBW = (nam: 50; nữ: 45.5) + 2.3 × (chiều cao cm / 2.54 - 60)"
    ),
}
