"""Kiểm thử tool luong_cu_cung (bọc CaseAsker làm chuyển tiếp và đường lui)."""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.agent.tools.base import ToolContext
from app.agent.tools.gateway import ToolGateway
from app.agent.tools.luong_cu_cung import LuongCuCung
from app.agent.tools.policy import ChinhSachCongCu
from app.agent.tools.registry import DanhMucCongCu
from app.container import build_container
from app.core.types import Chunk
from app.domain.loader import load_case
from app.domain.models import CaBenh
from app.kb.names import DrugNameIndex
from app.llm.case_context import open_deid_session
from app.orchestration.ai_review import AiRunResult
from app.orchestration.ask import AskCitation, AskResult, CaseAsker
from app.pipeline import KetQuaThamDinh, run_case
from app.providers.fakes import FakeLLM
from app.retrieval.query_builder import QueryBuilder
from tests.deid_support import temp_id

ROOT = Path(__file__).resolve().parents[2]
DEMO_02_PATH = ROOT / "data/mock/demo/DEMO-02.json"
DEMO_02_NAME: str = json.loads(DEMO_02_PATH.read_text(encoding="utf-8"))["hanh_chinh"]["ho_ten"]
pytestmark = pytest.mark.luong_cu_cung


def _chunk(chunk_id: str, nguon: str = "openfda") -> Chunk:
    return Chunk(
        doan_trich_id=chunk_id,
        tai_lieu_id="TL-1",
        muc_cha_id=None,
        nhom_nguon="nhan_thuoc",
        nguon=nguon,
        tang_tin_cay=3,
        hoat_chat_ids=["meropenem"],
        muc="lieu_than",
        duong_dan_muc="Dosage > Renal",
        loai_noi_dung="van_ban",
        ngon_ngu="en",
        phien_ban_nguon="20261102",
        url_goc=None,
        noi_dung_goc="Administer every 12 hours.",
        noi_dung_nhung="Administer every 12 hours.",
    )


class _SpyAsker:
    def __init__(self, reply: AskResult) -> None:
        self.reply = reply
        self.ask_calls: list[dict[str, Any]] = []
        self.global_calls: list[dict[str, Any]] = []

    def ask(
        self,
        ca: CaBenh,
        cau_hoi: str,
        lich_su: list[tuple[str, str]] | None = None,
        *,
        ket_qua: KetQuaThamDinh | None = None,
        ai_result: AiRunResult | None = None,
        nhan_dinh_id: str | None = None,
    ) -> AskResult:
        self.ask_calls.append(
            {
                "ca": ca,
                "cau_hoi": cau_hoi,
                "lich_su": lich_su,
                "ket_qua": ket_qua,
                "ai_result": ai_result,
                "nhan_dinh_id": nhan_dinh_id,
            }
        )
        return self.reply

    def ask_global(
        self,
        cases: Sequence[CaBenh],
        results: dict[str, KetQuaThamDinh],
        cau_hoi: str,
        lich_su: list[tuple[str, str]] | None = None,
    ) -> AskResult:
        self.global_calls.append(
            {
                "cases": cases,
                "results": results,
                "cau_hoi": cau_hoi,
                "lich_su": lich_su,
            }
        )
        return self.reply


def test_spy_asker_receives_exact_args_in_ca_and_chung_modes() -> None:
    case = load_case(DEMO_02_PATH)
    rule = run_case(case, build_container("test").renal_rules)
    spy = _SpyAsker(AskResult(trang_thai="ok", noi_dung="Trả lời mẫu."))
    tool = LuongCuCung(spy)

    ctx_ca = ToolContext(
        vai_tro="duoc_si_ls",
        che_do="ca",
        han_chot=time.monotonic() + 30.0,
        cau_hoi_goc="Câu hỏi ca",
        lich_su_goc=(("nguoi_dung", "Tin 1"),),
        ca=case,
        ket_qua_luat=rule,
        nhan_dinh_id="ND-1",
    )
    tool.chay(tool.LuocDoThamSo(), ctx_ca)
    assert len(spy.ask_calls) == 1
    assert spy.ask_calls[0] == {
        "ca": case,
        "cau_hoi": "Câu hỏi ca",
        "lich_su": [("nguoi_dung", "Tin 1")],
        "ket_qua": rule,
        "ai_result": None,
        "nhan_dinh_id": "ND-1",
    }

    ctx_chung = ToolContext(
        vai_tro="duoc_si_ls",
        che_do="chung",
        han_chot=time.monotonic() + 30.0,
        cau_hoi_goc="Câu hỏi chung",
        lich_su_goc=(("nguoi_dung", "Tin 2"),),
        cac_ca=(case,),
        cac_ket_qua={case.ca_id: rule},
    )
    tool.chay(tool.LuocDoThamSo(), ctx_chung)
    assert len(spy.global_calls) == 1
    assert spy.global_calls[0] == {
        "cases": [case],
        "results": {case.ca_id: rule},
        "cau_hoi": "Câu hỏi chung",
        "lich_su": [("nguoi_dung", "Tin 2")],
    }


def test_converts_chunks_citations_and_progress_detail() -> None:
    case = load_case(DEMO_02_PATH)
    c1 = _chunk("DT-1", "openfda")
    c2 = _chunk("DT-2", "byt")
    reply = AskResult(
        trang_thai="ok",
        noi_dung="Giảm nửa liều [1].",
        trich_dan=[
            AskCitation(
                so=1,
                loai_ma="tai_lieu",
                nhan="Nhãn FDA",
                doan_trich_id="DT-1",
                trich_nguyen_van="Administer every 12 hours.",
            )
        ],
        doan=[c1, c2],
    )
    tool = LuongCuCung(_SpyAsker(reply))
    ctx = ToolContext(
        vai_tro="duoc_si_ls",
        che_do="ca",
        han_chot=time.monotonic() + 30.0,
        cau_hoi_goc="Hỏi liều",
        ca=case,
    )
    res = tool.chay(tool.LuocDoThamSo(), ctx)
    assert res.trang_thai == "ok"
    assert [cc.ma for cc in res.can_cu] == ["doan:DT-1", "doan:DT-2"]
    assert res.can_cu[0].nhan == "Nhãn FDA"
    assert res.can_cu[1].nhan == "Hướng dẫn Bộ Y tế"
    assert res.chi_tiet_tien_trinh == "2 đoạn nguồn"
    assert "[1] Nhãn FDA: Administer every 12 hours." in res.noi_dung


@pytest.mark.parametrize(
    ("ask_status", "expected_status"),
    [
        ("ok", "ok"),
        ("khong_co_nguon", "khong_co"),
        ("ngoai_pham_vi", "khong_co"),
        ("loi", "loi"),
        ("chua_san_sang", "loi"),
    ],
)
def test_status_mapping(ask_status: str, expected_status: str) -> None:
    case = load_case(DEMO_02_PATH)
    reply = AskResult(trang_thai=ask_status, noi_dung="...")  # type: ignore[arg-type]
    tool = LuongCuCung(_SpyAsker(reply))
    ctx = ToolContext(
        vai_tro="duoc_si_ls",
        che_do="ca",
        han_chot=time.monotonic() + 30.0,
        cau_hoi_goc="Hỏi",
        ca=case,
    )
    res = tool.chay(tool.LuocDoThamSo(), ctx)
    assert res.trang_thai == expected_status


def test_schema_rejects_any_field() -> None:
    with pytest.raises(ValidationError):
        LuongCuCung.LuocDoThamSo.model_validate({"x": 1})


def test_integration_with_real_case_asker_and_gateway_masks_pii() -> None:
    container = build_container("test")
    case = load_case(DEMO_02_PATH)
    names = DrugNameIndex.load(ROOT / "data/kb/hoat_chat.json")
    fake_llm = FakeLLM(
        [
            {
                "pham_vi": "trong",
                "tra_loi": "Người bệnh [TEN_1] có creatinin máu 212 umol/L [1].",
                "trich_dan": [
                    {
                        "so": 1,
                        "loai": "du_lieu_ca",
                        "ma": temp_id("DEMO-02", "XN-DEMO02-01"),
                        "trich_nguyen_van": None,
                    }
                ],
            }
        ]
    )
    asker = CaseAsker(
        llm=fake_llm,
        retriever=None,
        query_builder=QueryBuilder(container.settings.retrieval),
        resolve_name=names.resolve,
        prompt_path=ROOT / "config/prompts/hoi_them.v1.md",
        case_settings=container.settings.case_context,
        evidence_max_chars=container.settings.evidence.max_chars,
        model_name="deepseek-flash",
        renal_rules=container.renal_rules,
    )
    registry = DanhMucCongCu()
    registry.dang_ky(LuongCuCung(asker))
    policy = ChinhSachCongCu.tu_tep(ROOT / "config/tool_policy.yaml")
    gateway = ToolGateway(registry, policy, so_lan_goi_toi_da=2)

    session = open_deid_session(case, [])
    ctx = ToolContext(
        vai_tro="duoc_si_ls",
        che_do="ca",
        han_chot=time.monotonic() + 30.0,
        cau_hoi_goc=f"{DEMO_02_NAME} có creatinin bao nhiêu?",
        ca=case,
        deid_session=session,
    )
    res = gateway.goi("luong_cu_cung", {}, ctx)
    assert res.trang_thai == "ok"
    assert DEMO_02_NAME not in res.noi_dung
    assert "[TEN_" in res.noi_dung
    assert "<<<KET_QUA_CONG_CU ten=luong_cu_cung>>>" in res.noi_dung
