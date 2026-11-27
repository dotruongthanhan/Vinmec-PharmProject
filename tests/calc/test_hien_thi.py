import math
import re

import pytest

from app import calc


def test_cong_thuc_va_hang_so() -> None:
    results = [
        (
            calc.cockcroft_gault(60, "nu", 70, 1, "mg/dL"),
            (140 - 60) * 70 / (72 * 1) * 0.85,
            ["140", "72", "0.85"],
        ),
        (
            calc.egfr_ckd_epi_2021(60, "nu", 1, "mg/dL"),
            142 * min(1 / 0.7, 1) ** -0.241 * max(1 / 0.7, 1) ** -1.2 * 0.9938**60 * 1.012,
            ["142", "0.7", "-0.241", "-1.2", "0.9938", "1.012"],
        ),
        (calc.bmi(70, 170), 70 / (170 / 100) ** 2, ["100", "2"]),
        (calc.bsa_mosteller(70, 170), math.sqrt(170 * 70 / 3600), ["3600"]),
        (
            calc.bsa_dubois(70, 170),
            0.007184 * 70**0.425 * 170**0.725,
            ["0.007184", "0.425", "0.725"],
        ),
        (calc.ibw_devine("nu", 170), 45.5 + 2.3 * (170 / 2.54 - 60), ["45.5", "2.3", "2.54", "60"]),
        (
            calc.adjusted_body_weight("nu", 170, 70),
            (45.5 + 2.3 * (170 / 2.54 - 60)) + 0.4 * (70 - (45.5 + 2.3 * (170 / 2.54 - 60))),
            ["0.4", "45.5", "2.3", "2.54", "60"],
        ),
    ]
    assert set(calc.CONG_THUC_HIEN_THI) == {result.cong_thuc for result, _, _ in results}
    for result, expected, constants in results:
        assert result.ket_qua == pytest.approx(expected, abs=0.01)
        numbers = [
            float(n)
            for n in re.findall(r"-?\d+(?:\.\d+)?", calc.CONG_THUC_HIEN_THI[result.cong_thuc])
        ]
        assert all(float(n) in numbers for n in constants)

    def nums(name: str) -> list[float]:
        return [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", calc.CONG_THUC_HIEN_THI[name])]

    c = nums("cockcroft_gault")
    e = nums("egfr_ckd_epi_2021")
    b = nums("bmi")
    m = nums("bsa_mosteller")
    d = nums("bsa_dubois")
    i = nums("ibw_devine")
    a = nums("adjusted_body_weight")
    ibw = i[1] + i[2] * (170 / i[3] - i[4])
    adj_ibw = a[2] + a[3] * (170 / a[4] - a[5])
    from_strings = [
        (c[0] - 60) * 70 / (c[1] * 1) * c[2],
        e[0] * min(1 / e[5], e[1]) ** e[6] * max(1 / e[5], e[2]) ** e[3] * e[4] ** 60 * e[7],
        70 / (170 / b[0]) ** b[1],
        math.sqrt(170 * 70 / m[0]),
        d[0] * 70 ** d[1] * 170 ** d[2],
        ibw,
        adj_ibw + a[0] * (70 - adj_ibw),
    ]
    for (result, _, _), value in zip(results, from_strings, strict=True):
        assert result.ket_qua == pytest.approx(value, abs=0.01)


def test_mosteller_formula_checked_in_demo_bundle() -> None:
    import time

    from app.calc import bsa_mosteller
    from app.container import build_container
    from app.domain.loader import latest_vital
    from app.llm.case_context import build_case_bundle
    from app.orchestration.ask import AskLLMOutput, AskVerificationError, kiem_chung_tra_loi
    from app.pipeline import KetQuaThamDinh

    container = build_container("test")
    ca = container.case_repo.get("DEMO-02")
    weight = latest_vital(ca, "can_nang")
    height = latest_vital(ca, "chieu_cao")
    assert weight is not None and height is not None
    result = bsa_mosteller(weight.gia_tri, height.gia_tri)
    ket_qua = KetQuaThamDinh(ca_id=ca.ca_id, chi_so=[result], phat_hien=[], thoi_gian_ms=0)
    bundle = build_case_bundle(ca, ket_qua, container.settings.case_context)
    assert "công thức:" in bundle.goi.van_ban_ca
    assert 3600 in bundle.goi.so_cho_phep
    assert 3700 not in bundle.goi.so_cho_phep

    def verify(number: int):
        return kiem_chung_tra_loi(
            ca=ca,
            ket_qua=ket_qua,
            cleaned_question="BSA Mosteller bao nhiêu?",
            output=AskLLMOutput.model_validate(
                {
                    "pham_vi": "trong",
                    "tra_loi": f"BSA là {result.ket_qua:.2f} theo công thức chia {number} [1].",
                    "trich_dan": [{"so": 1, "loai": "tinh_toan", "ma": "bsa_mosteller"}],
                }
            ),
            allowed_record_ids=set(),
            allowed_calc_ids={"bsa_mosteller"},
            allowed_numbers=bundle.goi.so_cho_phep,
            chunk_by_id={},
            anh_xa={},
            ids=bundle.ma_ban_ghi,
            tools_called=[],
            perf_start=time.perf_counter(),
        )

    assert verify(3600).trang_thai == "ok"
    with pytest.raises(AskVerificationError, match="so_khong_co_nguon:3700"):
        verify(3700)

    missing = ket_qua.model_copy(update={"chi_so": [bsa_mosteller(None, None)]})
    missing_bundle = build_case_bundle(ca, missing, container.settings.case_context)
    assert 3600 not in missing_bundle.goi.so_cho_phep
    assert "công thức:" not in missing_bundle.goi.van_ban_ca
