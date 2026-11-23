"""Kiểm thử công cụ tra_tuong_tac: DDInter thật, Gateway, chính sách, kiểm chứng dòng bảng.

Chạy ở chế độ tệp, không cần DB; mọi truy cập `read_pool` bị chặn để chứng minh chỉ đọc cục bộ.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest

from app import container as container_mod
from app.agent.graph import dung_do_thi_hoi_dap
from app.agent.tools.base import CanCu, ToolContext
from app.agent.tools.gateway import ToolGateway
from app.agent.tools.policy import ChinhSachCongCu
from app.agent.tools.registry import DanhMucCongCu
from app.agent.tools.tra_tuong_tac import ThamSoTraTuongTac, TraTuongTac
from app.api import lookup
from app.config.settings import load_settings
from app.container import Container, build_container
from app.core.progress import TienTrinh, tien_trinh_hien_tai
from app.db.read_pool import read_pool
from app.domain.loader import load_case
from app.orchestration.ask import AskResult
from app.providers.fakes import FakeLLM
from app.rules.registry import RuleContext

ROOT = Path(__file__).resolve().parents[2]
DEMO_02_PATH = ROOT / "data/mock/demo/DEMO-02.json"
DEMO_05_PATH = ROOT / "data/mock/demo/DEMO-05.json"
PROMPT_PATH = ROOT / "config/prompts/tac_tu.v1.md"
POLICY_PATH = ROOT / "config/tool_policy.yaml"
DEMO_02_NAME: str = json.loads(DEMO_02_PATH.read_text(encoding="utf-8"))["hanh_chinh"]["ho_ten"]
_TRA_CUU = "data/kb_curated/tra_cuu/tra_cuu.sqlite"
_DDINTER = "data/kb_curated/tuong_tac/ddinter.sqlite"
needs_index = pytest.mark.can_du_lieu(_TRA_CUU, _DDINTER)

# Cặp có thật trong DDInter của kho (đã kiểm: amiodarone × warfarin, mức Major, cơ chế Metabolism).
PAIR_KEY = "bang:ddinter_cap:ddinter1951-ddinter76"


@pytest.fixture(autouse=True)
def local_only(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Ép chế độ tệp và biến mọi kết nối DB thành lỗi."""
    monkeypatch.setenv("KB_SOURCE", "file")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("CDSS_LUONG_CU_CUNG", raising=False)

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Không được mở kết nối DB trong test công cụ")

    monkeypatch.setattr(read_pool, "connection", forbidden)
    monkeypatch.setattr(psycopg, "connect", forbidden)
    lookup.clear_caches()
    yield
    lookup.clear_caches()


@pytest.fixture(scope="module")
def runtime_context() -> RuleContext:
    return Container(load_settings("test")).rule_context


@pytest.fixture(autouse=True)
def shared_context(runtime_context: RuleContext, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(container_mod, "get_rule_context", lambda: runtime_context)


def _ctx(
    *, che_do: str = "ca", ca_path: Path | None = None, vai_tro: str = "duoc_si_ls"
) -> ToolContext:
    ca = load_case(ca_path or DEMO_02_PATH) if che_do == "ca" else None
    return ToolContext(
        vai_tro=vai_tro,
        che_do=che_do,  # type: ignore[arg-type]
        han_chot=time.monotonic() + 30.0,
        cau_hoi_goc="câu hỏi",
        ca=ca,
    )


def _chay(tham_so: dict[str, Any], **kwargs: Any):  # type: ignore[no-untyped-def]
    return TraTuongTac().chay(ThamSoTraTuongTac.model_validate(tham_so), _ctx(**kwargs))


def _gateway() -> ToolGateway:
    registry = DanhMucCongCu()
    registry.dang_ky(TraTuongTac())
    return ToolGateway(registry, ChinhSachCongCu.tu_tep(POLICY_PATH), so_lan_goi_toi_da=5)


# ---------------------------------------------------------------- thuốc–thuốc


@needs_index
def test_pair_with_interaction_returns_citable_row() -> None:
    res = _chay({"ten_thuoc": ["amiodarone", "warfarin"]})
    assert res.trang_thai == "ok"
    row = next(item for item in res.can_cu if item.ma == PAIR_KEY)
    assert row.loai == "bang"
    assert row.nhan
    assert row.noi_dung is not None
    assert "amiodarone" in row.noi_dung and "warfarin" in row.noi_dung
    assert "mức: nặng" in row.noi_dung
    assert "hậu quả:" in row.noi_dung and "xử trí:" in row.noi_dung
    assert f"[{PAIR_KEY}] {row.noi_dung}" in res.noi_dung
    assert "\n" not in row.ma and len(row.ma) <= 120
    assert res.chi_tiet_tien_trinh == "2 hoạt chất, 1 cặp có tương tác"


@needs_index
def test_unresolved_name_is_reported_as_missing_not_as_no_interaction() -> None:
    res = _chay({"ten_thuoc": ["amiodarone", "zzzxx"]})
    text = res.noi_dung.lower()
    assert "không có dữ liệu ddinter cho zzzxx" in text
    assert "không có tương tác" not in text
    assert res.can_cu == []
    assert res.trang_thai == "khong_co"
    assert res.chi_tiet_tien_trinh is not None and "zzzxx" not in res.chi_tiet_tien_trinh


@needs_index
def test_pair_tool_needs_two_names() -> None:
    res = _chay({"ten_thuoc": ["warfarin"]})
    assert res.trang_thai == "loi"
    assert res.ma_loi == "sai_tham_so"
    assert "2 tên thuốc" in res.noi_dung


@needs_index
def test_duplicate_names_are_a_parameter_error() -> None:
    res = _chay({"ten_thuoc": ["warfarin", "Warfarin"]})
    assert res.trang_thai == "loi"
    assert res.ma_loi == "sai_tham_so"


@needs_index
def test_row_cap_is_twenty_and_reports_remaining() -> None:
    names = [
        "warfarin",
        "amiodarone",
        "ibuprofen",
        "ketorolac",
        "metformin",
        "simvastatin",
        "aspirin",
        "clarithromycin",
        "fluconazole",
        "digoxin",
    ]
    res = _chay({"ten_thuoc": names})
    assert len(res.can_cu) <= 20
    assert len(res.noi_dung) <= 8000
    if "còn" in res.noi_dung:
        assert "dòng nữa chưa hiển thị" in res.noi_dung


# ---------------------------------------------------------------- thuốc–thức ăn


@needs_index
def test_food_interaction_rows() -> None:
    res = _chay({"loai": "thuoc_thuc_an", "ten_thuoc": ["amiodarone"]}, che_do="chung")
    assert res.trang_thai == "ok"
    row = next(item for item in res.can_cu if "grapefruit" in item.ma)
    assert row.ma == "bang:ddinter_thuc_an:ddinter76:grapefruit_juice"
    assert row.noi_dung is not None
    assert "mức: nặng" in row.noi_dung
    assert res.chi_tiet_tien_trinh == "1 hoạt chất, 1 dòng thức ăn"


@needs_index
def test_food_unresolved_name_is_missing() -> None:
    res = _chay({"loai": "thuoc_thuc_an", "ten_thuoc": ["zzzxx"]}, che_do="chung")
    assert res.can_cu == []
    assert "không có dữ liệu ddinter cho zzzxx" in res.noi_dung.lower()
    assert "không có tương tác" not in res.noi_dung.lower()


# ---------------------------------------------------------------- thuốc–bệnh


@needs_index
def test_drug_disease_by_icd_prefix_and_by_name() -> None:
    by_icd = _chay({"loai": "thuoc_benh", "ten_thuoc": ["ketorolac"], "benh": ["K25.9"]})
    assert by_icd.trang_thai == "ok"
    assert [item.ma for item in by_icd.can_cu] == ["bang:thuoc_benh_icd:ketorolac:peptic_ulcer"]
    assert by_icd.can_cu[0].noi_dung is not None
    assert "mức: nặng" in by_icd.can_cu[0].noi_dung
    by_name = _chay({"loai": "thuoc_benh", "ten_thuoc": ["ketorolac"], "benh": ["peptic ulcer"]})
    assert [item.ma for item in by_name.can_cu] == [item.ma for item in by_icd.can_cu]


@needs_index
def test_drug_disease_uses_case_diagnosis_when_benh_omitted() -> None:
    res = _chay({"loai": "thuoc_benh", "ten_thuoc": ["ketorolac"]}, ca_path=DEMO_05_PATH)
    assert res.trang_thai == "ok"  # DEMO-05 có chẩn đoán I10 (tăng huyết áp)
    assert any(item.ma.endswith(":hypertension") for item in res.can_cu)


@needs_index
def test_drug_disease_without_benh_in_general_mode_is_parameter_error() -> None:
    res = _chay({"loai": "thuoc_benh", "ten_thuoc": ["ketorolac"]}, che_do="chung")
    assert res.trang_thai == "loi"
    assert res.ma_loi == "sai_tham_so"


@needs_index
def test_drug_disease_no_match_is_stated_as_unmatched() -> None:
    res = _chay({"loai": "thuoc_benh", "ten_thuoc": ["ketorolac"], "benh": ["S72.0"]})
    assert res.can_cu == []
    assert "không khớp dòng thuốc–bệnh" in res.noi_dung


# ---------------------------------------------------------------- bảo mật qua Gateway


def test_schema_rejects_unknown_fields_via_gateway() -> None:
    gateway = _gateway()
    for extra in ({"ca_id": "DEMO-02"}, {"sql": "select 1"}):
        res = gateway.goi(
            "tra_tuong_tac", {"ten_thuoc": ["warfarin", "amiodarone"], **extra}, _ctx()
        )
        assert res.trang_thai == "tu_choi"
        assert res.ma_loi == "sai_tham_so"


def test_schema_has_no_case_id_and_enforces_bounds() -> None:
    assert "ca_id" not in ThamSoTraTuongTac.model_fields
    gateway = _gateway()
    for bad in (
        {"ten_thuoc": []},
        {"ten_thuoc": ["a"] * 11},
        {"ten_thuoc": ["x" * 121, "warfarin"]},
        {"ten_thuoc": ["warfarin", "digoxin"], "benh": ["b"] * 6},
        {"ten_thuoc": ["warfarin", "digoxin"], "benh": ["b" * 121]},
        {"loai": "tuy_y", "ten_thuoc": ["warfarin", "digoxin"]},
    ):
        res = gateway.goi("tra_tuong_tac", bad, _ctx())
        assert res.ma_loi == "sai_tham_so", bad


def test_unlisted_role_is_denied_and_policy_allows_pharmacist() -> None:
    gateway = _gateway()
    res = gateway.goi("tra_tuong_tac", {"ten_thuoc": ["warfarin", "digoxin"]}, _ctx(vai_tro="la"))
    assert res.trang_thai == "tu_choi"
    assert res.ma_loi == "khong_co_quyen"
    policy = ChinhSachCongCu.tu_tep(POLICY_PATH)
    assert policy.mac_dinh == "tu_choi"
    assert policy.cho_phep("duoc_si_ls", "ca", "tra_tuong_tac") is True
    assert policy.cho_phep("admin", "chung", "tra_tuong_tac") is True
    assert policy.cho_phep("khach", "ca", "tra_tuong_tac") is False


def test_params_with_patient_identity_are_rejected() -> None:
    gateway = _gateway()
    ctx = _ctx()
    from app.llm.case_context import open_deid_session

    assert ctx.ca is not None
    ctx = ToolContext(
        vai_tro=ctx.vai_tro,
        che_do=ctx.che_do,
        han_chot=ctx.han_chot,
        cau_hoi_goc=ctx.cau_hoi_goc,
        ca=ctx.ca,
        deid_session=open_deid_session(ctx.ca, []),
    )
    res = gateway.goi("tra_tuong_tac", {"ten_thuoc": [DEMO_02_NAME, "warfarin"]}, ctx)
    assert res.trang_thai == "tu_choi"
    assert res.ma_loi == "tham_so_co_dinh_danh"


@needs_index
def test_gateway_keeps_row_citations_and_audit_summary() -> None:
    res = _gateway().goi("tra_tuong_tac", {"ten_thuoc": ["amiodarone", "warfarin"]}, _ctx())
    assert res.trang_thai == "ok"
    assert res.noi_dung.startswith("<<<KET_QUA_CONG_CU ten=tra_tuong_tac>>>")
    assert any(item.ma == PAIR_KEY for item in res.can_cu)
    assert res.chi_tiet_tien_trinh is not None and "warfarin" not in res.chi_tiet_tien_trinh


# ---------------------------------------------------------------- kiểm chứng dòng bảng


def _run_graph(llm: FakeLLM, question: str) -> AskResult:
    container = build_container("test")
    registry = DanhMucCongCu()
    registry.dang_ky(TraTuongTac())
    policy = ChinhSachCongCu.tu_tep(POLICY_PATH)
    graph = dung_do_thi_hoi_dap(
        llm=llm,
        danh_muc=registry,
        chinh_sach=policy,
        prompt_path=PROMPT_PATH,
        case_settings=container.settings.case_context,
        renal_rules_getter=lambda: container.renal_rules,
        max_turns=5,
    )
    ctx = ToolContext(
        vai_tro="duoc_si_ls",
        che_do="ca",
        han_chot=time.monotonic() + 30.0,
        cau_hoi_goc=question,
        ca=load_case(DEMO_02_PATH),
    )
    token = tien_trinh_hien_tai.set(TienTrinh())
    try:
        final = graph.invoke(
            {
                "ctx": ctx,
                "cau_hoi_sach": question,
                "gateway": ToolGateway(registry, policy, so_lan_goi_toi_da=15),
                "thoi_gian_bat_dau": time.perf_counter(),
                "so_vong": 0,
                "luot_tac_tu": 0,
                "so_lan_kiem_chung": 0,
                "so_lan_sai_luoc_do": 0,
                "can_cu": [],
                "ket_qua_cong_cu": [],
                "cong_cu_da_goi": [],
                "can_du_phong": False,
            }
        )
    finally:
        tien_trinh_hien_tai.reset(token)
    return final["ket_qua"]


def _plans(answer: str, ma: str) -> list[dict[str, Any]]:
    call = {
        "hanh_dong": "goi_cong_cu",
        "goi": [
            {
                "cong_cu": "tra_tuong_tac",
                "tham_so": {"ten_thuoc": ["amiodarone", "warfarin"]},
            }
        ],
    }
    reply = {
        "hanh_dong": "tra_loi",
        "tra_loi": {
            "pham_vi": "trong",
            "tra_loi": answer,
            "trich_dan": [{"so": 1, "loai": "bang", "ma": ma, "trich_nguyen_van": None}],
        },
    }
    return [call, reply, reply]


@needs_index
def test_verified_answer_citing_table_row_passes() -> None:
    llm = FakeLLM(_plans("Amiodarone và warfarin có tương tác mức nặng [1].", PAIR_KEY))
    result = _run_graph(llm, "Amiodarone và warfarin có tương tác không?")
    assert result.trang_thai == "ok"
    assert result.cong_cu_da_goi == ["tra_tuong_tac"]
    assert len(result.trich_dan) == 1
    citation = result.trich_dan[0]
    assert citation.loai_ma == "tai_lieu"
    assert "DDInter" in citation.nhan
    assert citation.doan_trich_id is None and citation.trich_nguyen_van is None


@needs_index
def test_citing_table_row_not_in_turn_is_blocked() -> None:
    bad = "bang:ddinter_cap:ddinter1-ddinter2"
    llm = FakeLLM(_plans("Amiodarone và warfarin có tương tác mức nặng [1].", bad))
    result = _run_graph(llm, "Amiodarone và warfarin có tương tác không?")
    assert result.trang_thai != "ok"
    assert result.trich_dan == []


@needs_index
def test_number_not_in_cited_row_is_blocked() -> None:
    llm = FakeLLM(_plans("Nên giảm liều warfarin 97% [1].", PAIR_KEY))
    result = _run_graph(llm, "Amiodarone và warfarin có tương tác không?")
    assert result.trang_thai != "ok"
    assert result.trich_dan == []


def test_ask_citation_raw_accepts_bang_and_cancu_noi_dung_optional() -> None:
    from app.orchestration.ask import AskCitationRaw

    assert AskCitationRaw(so=1, loai="bang", ma="bang:x:y").loai == "bang"
    assert CanCu(ma="bang:x", loai="bang", nhan="n").noi_dung is None


# ------------------------------------------------------- gợi ý tên, không đủ loại trừ


@needs_index
def test_unresolved_name_gets_typo_suggestion_from_real_index() -> None:
    res = _chay({"ten_thuoc": ["parecetamo", "warfarin"]})
    text = res.noi_dung.lower()
    assert "không có dữ liệu ddinter cho parecetamo" in text
    assert "có thể là:" in text and "paracetamol" in text
    assert "gợi ý gần đúng, cần xác nhận" in text
    assert "không có tương tác" not in text


@needs_index
def test_suggestion_is_appended_for_all_types_and_failure_is_silent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Item:
        nhan = "Paracetamol"

    class _Res:
        goi_y_sua = "paracetamol"
        ket_qua = [_Item()]

    monkeypatch.setattr(lookup, "suggest_drugs", lambda ten, limit=8: _Res())
    for loai in ("thuoc_thuoc", "thuoc_thuc_an"):
        names = ["parecetamo", "warfarin"] if loai == "thuoc_thuoc" else ["parecetamo"]
        res = _chay({"loai": loai, "ten_thuoc": names}, che_do="chung")
        assert "có thể là: paracetamol, Paracetamol" in res.noi_dung

    def boom(ten: str, limit: int = 8) -> None:
        raise RuntimeError("chỉ mục hỏng")

    monkeypatch.setattr(lookup, "suggest_drugs", boom)
    res = _chay({"loai": "thuoc_thuc_an", "ten_thuoc": ["parecetamo"]}, che_do="chung")
    assert "không có dữ liệu ddinter cho parecetamo" in res.noi_dung.lower()
    assert "có thể là" not in res.noi_dung


@needs_index
def test_drug_disease_notes_say_not_enough_to_exclude() -> None:
    res = _chay({"loai": "thuoc_benh", "ten_thuoc": ["ketorolac"], "benh": ["S72.0"]})
    assert "bảng trong kho chỉ có" in res.noi_dung
    assert "không đủ để loại trừ" in res.noi_dung
    res2 = _chay({"loai": "thuoc_benh", "ten_thuoc": ["warfarin"], "benh": ["S72.0"]})
    if "không có dữ liệu thuốc–bệnh" in res2.noi_dung:
        assert "không đủ để loại trừ" in res2.noi_dung


@needs_index
@pytest.mark.parametrize("ma", [PAIR_KEY.removeprefix("bang:"), f"[{PAIR_KEY}]", f" {PAIR_KEY} "])
def test_table_code_normalisation_is_accepted(ma: str) -> None:
    llm = FakeLLM(_plans("Amiodarone và warfarin có tương tác mức nặng [1].", ma))
    result = _run_graph(llm, "Amiodarone và warfarin có tương tác không?")
    assert result.trang_thai == "ok"
    assert len(result.trich_dan) == 1


@needs_index
def test_table_code_of_another_row_still_blocked_without_prefix() -> None:
    llm = FakeLLM(
        _plans("Amiodarone và warfarin có tương tác mức nặng [1].", "ddinter_cap:ddinter1-ddinter2")
    )
    result = _run_graph(llm, "Amiodarone và warfarin có tương tác không?")
    assert result.trang_thai != "ok"
    assert result.trich_dan == []
