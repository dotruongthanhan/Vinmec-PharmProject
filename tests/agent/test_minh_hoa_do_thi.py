"""Kiểm tra minh hoạ từ công cụ đến câu trả lời đã kiểm chứng."""

import json
import re
from pathlib import Path

import pytest

from app.agent.minh_hoa.kiem import kiem_dac_ta
from app.agent.minh_hoa.models import BoDuLieu, CotDuLieu, KhoiMinhHoa
from app.agent.tools.policy import ChinhSachCongCu
from app.agent.tools.registry import DanhMucCongCu
from app.agent.tools.tinh_chi_so import TinhChiSo
from app.agent.tools.tra_thuoc import TraThuoc
from app.agent.tools.ve_bieu_do import VeBieuDo
from app.container import build_container
from app.domain.loader import latest_vital, load_case
from app.providers.fakes import FakeLLM
from tests.agent.test_graph import DEMO_02_PATH, _policy, _run_graph
from tests.deid_support import temp_id

ROOT = Path(__file__).resolve().parents[2]


def examples() -> list[dict]:
    content = (ROOT / "config/prompts/ky_nang_minh_hoa.v1.md").read_text(encoding="utf-8")
    return [json.loads(s) for s in re.findall(r"```json\s*(.*?)\s*```", content, re.S)]


def dataset(ma: str, columns: dict[str, str]) -> BoDuLieu:
    return BoDuLieu(
        ma=ma,
        cot=[CotDuLieu(ten=k, kieu=v) for k, v in columns.items()],
        dong=[
            {
                k: 1.0 if v == "dinh_luong" else True if v == "logic" else "mẫu"
                for k, v in columns.items()
            }
        ],
    )


def test_prompt_examples_pass_checker() -> None:
    specs = examples()
    assert len(specs) == 5
    grid = {"creatinin": "dinh_luong", "loai_can_nang": "danh_muc", "crcl": "dinh_luong"}
    renal = {
        "bien_ve_tu": "dinh_luong",
        "bien_ve_den": "dinh_luong",
        "bao_gom_tu": "logic",
        "bao_gom_den": "logic",
        "khuyen_cao": "danh_muc",
    }
    datasets = [
        {
            "ds-2": dataset("ds-2", grid),
            "ds-3": dataset("ds-3", grid),
            "ds-4": dataset("ds-4", renal),
        },
        {
            "ds-1": dataset(
                "ds-1", {"thuoc_a": "danh_muc", "thuoc_b": "danh_muc", "muc_do": "danh_muc"}
            )
        },
        {"ds-1": dataset("ds-1", {"thoi_gian": "thoi_gian", "gia_tri": "dinh_luong"})},
        {
            "ds-1": dataset(
                "ds-1",
                {
                    "thoi_diem": "thoi_gian",
                    "gia_tri": "dinh_luong",
                    "creatinin_tang_nhanh": "logic",
                },
            ),
            "ds-2": dataset("ds-2", {"thoi_diem": "thoi_gian"}),
        },
        {
            "ds-1": dataset(
                "ds-1",
                {
                    "bat_dau": "thoi_gian",
                    "ket_thuc": "thoi_gian",
                    "hoat_chat": "danh_muc",
                    "trang_thai_dong": "danh_muc",
                },
            ),
            "ds-2": dataset("ds-2", {"thoi_diem_lay_mau": "thoi_gian", "hoat_chat": "danh_muc"}),
        },
    ]
    for spec, ds in zip(specs, datasets, strict=True):
        result = kiem_dac_ta(spec, ds, set(spec["nguon"]))
        assert isinstance(result, KhoiMinhHoa), result


def test_container_registers_tool() -> None:
    asker = build_container("test").agentic_asker
    assert asker._danh_muc.lay("ve_bieu_do") is not None
    assert "ve_bieu_do" in asker._chinh_sach.cac_cong_cu_duoc_phep(
        "duoc_si_ls", "ca", asker._danh_muc
    )


def calls(answer: str = "Creatinin máu là 212 umol/L [1].") -> list[dict]:
    spec = examples()[0]
    spec["nguon"] = ["tinh:cockcroft_gault:thuc_te"]
    return [
        {
            "hanh_dong": "goi_cong_cu",
            "goi": [{"cong_cu": "tinh_chi_so", "tham_so": {"cong_thuc": "cockcroft_gault"}}],
        },
        {
            "hanh_dong": "goi_cong_cu",
            "goi": [
                {
                    "cong_cu": "tra_thuoc",
                    "tham_so": {
                        "ten": "meropenem",
                        "phan": ["quy_tac"],
                        "nhom_quy_tac": ["lieu_than"],
                    },
                }
            ],
        },
        {
            "hanh_dong": "goi_cong_cu",
            "goi": [{"cong_cu": "ve_bieu_do", "tham_so": {"dac_ta": spec}}],
        },
        {
            "hanh_dong": "tra_loi",
            "tra_loi": {
                "pham_vi": "trong",
                "tra_loi": answer,
                "trich_dan": [
                    {
                        "so": 1,
                        "loai": "du_lieu_ca",
                        "ma": temp_id("DEMO-02", "XN-DEMO02-01"),
                        "trich_nguyen_van": None,
                    }
                ],
            },
        },
    ]


@pytest.fixture(autouse=True)
def stub_drug_dataset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bộ khoảng giả lập, không phụ thuộc chỉ mục tra thuốc ngoài Git."""
    from app.agent.tools.base import CanCu, KetQuaCongCu

    def fake_lookup(self, tham_so, ctx):
        del self, tham_so, ctx
        data = dataset(
            "",
            {
                "bien_ve_tu": "dinh_luong",
                "bien_ve_den": "dinh_luong",
                "bao_gom_tu": "logic",
                "bao_gom_den": "logic",
                "khuyen_cao": "danh_muc",
            },
        )
        data.dong[0].update({"bien_ve_tu": 0.0, "bien_ve_den": 100.0})
        data.can_cu = ["bang:mau"]
        return KetQuaCongCu(
            trang_thai="ok",
            noi_dung="Dữ liệu giả lập",
            can_cu=[CanCu(ma="bang:mau", loai="bang", nhan="Mẫu")],
            bo_du_lieu=[data],
        )

    monkeypatch.setattr(TraThuoc, "chay", fake_lookup)


def registry() -> DanhMucCongCu:
    result = DanhMucCongCu()
    for tool in (TinhChiSo(), TraThuoc(), VeBieuDo()):
        result.dang_ky(tool)
    return result


def run(responses: list[dict]):
    return _run_graph(
        FakeLLM(responses),
        "Creatinin của ca này bao nhiêu?",
        danh_muc=registry(),
        chinh_sach=_policy(["tinh_chi_so", "tra_thuoc", "ve_bieu_do"]),
    )[0]


def test_drawing_rounds_preserve_successful_block() -> None:
    sequence = calls()
    bad = json.loads(json.dumps(sequence[2]))
    bad["goi"][0]["tham_so"]["dac_ta"]["nguon"] = ["tinh:khong_co"]
    result = run(sequence[:2] + [bad, sequence[2], bad, sequence[-1]])
    assert result.trang_thai == "ok"
    assert len(result.minh_hoa) == 1


def test_drawing_rejection_list_is_not_recorded_in_llm_trace(tmp_path: Path) -> None:
    from app.config.settings import TracerSettings
    from app.tracing import Tracer

    sequence = calls()
    bad = json.loads(json.dumps(sequence[2]))
    bad["goi"][0]["tham_so"]["dac_ta"]["nguon"] = ["tinh:khong_co"]
    tracer = Tracer(TracerSettings(thu_muc=str(tmp_path), muc_noi_dung="day_du"))
    with tracer.bat_dau_vet("hoi_dap", "agentic") as vet:
        assert vet is not None
        result = run(sequence[:2] + [bad, sequence[-1]])
        record = vet.chot()
    tracer.close()
    assert result.trang_thai == "ok"
    trace = json.dumps(record.model_dump(mode="json"), ensure_ascii=False)
    assert "nguon_khong_hop_le" in trace
    assert "mã căn cứ hợp lệ:" not in trace


def test_four_normal_rounds_and_three_rejected_drawing_rounds() -> None:
    sequence = calls()
    bad = json.loads(json.dumps(sequence[2]))
    bad["goi"][0]["tham_so"]["dac_ta"]["nguon"] = ["tinh:khong_co"]
    llm = FakeLLM(sequence[:2] * 2 + [bad] * 3 + [sequence[-1]])
    result, _, _ = _run_graph(
        llm,
        "Creatinin của ca này bao nhiêu?",
        danh_muc=registry(),
        chinh_sach=_policy(["tinh_chi_so", "tra_thuoc", "ve_bieu_do"]),
    )
    assert result.trang_thai == "ok"
    assert result.minh_hoa == []
    assert "het_luot_ve" in llm.calls[-1]["messages"][1].content


def test_fourth_drawing_round_prompts_for_answer() -> None:
    sequence = calls()
    llm = FakeLLM(sequence[:2] + [sequence[2]] * 4 + [sequence[-1]])
    result, _, _ = _run_graph(
        llm,
        "Creatinin của ca này bao nhiêu?",
        danh_muc=registry(),
        chinh_sach=_policy(["tinh_chi_so", "tra_thuoc", "ve_bieu_do"]),
    )
    assert result.trang_thai == "ok"
    assert len(result.minh_hoa) == 1
    assert "het_luot_ve" in llm.calls[-1]["messages"][1].content


def test_duplicate_drawing_then_different_layer() -> None:
    sequence = calls()
    other = json.loads(json.dumps(sequence[2]))
    other["goi"][0]["tham_so"]["dac_ta"]["lop"].pop()
    llm = FakeLLM(sequence[:2] + [sequence[2], sequence[2], other, sequence[-1]])
    result, _, _ = _run_graph(
        llm,
        "Creatinin của ca này bao nhiêu?",
        danh_muc=registry(),
        chinh_sach=_policy(["tinh_chi_so", "tra_thuoc", "ve_bieu_do"]),
    )
    assert result.trang_thai == "ok"
    assert [block.ma for block in result.minh_hoa] == ["mh-1", "mh-2"]
    assert "Đã vẽ ở mh-1, không vẽ lại" in llm.calls[4]["messages"][1].content


def test_five_normal_rounds_keep_existing_limit() -> None:
    sequence = calls()
    llm = FakeLLM([sequence[0]] * 6)
    result, steps, _ = _run_graph(
        llm,
        "Creatinin của ca này bao nhiêu?",
        danh_muc=registry(),
        chinh_sach=_policy(["tinh_chi_so", "tra_thuoc", "ve_bieu_do"]),
    )
    assert result.trang_thai == "khong_co_nguon"
    assert "agent_du_phong" in steps
    assert len(llm.calls) == 6


def test_graph_returns_verified_block_and_grid() -> None:
    result = run(calls())
    assert result.trang_thai == "ok"
    assert len(result.minh_hoa) == 1
    block = result.minh_hoa[0]
    grid = next(d for d in block.bo_du_lieu if d.ma == "ds-2")
    case = load_case(DEMO_02_PATH)
    weight = latest_vital(case, "can_nang").gia_tri
    age = case.nguoi_benh.tuoi
    female = case.nguoi_benh.gioi_tinh == "nu"
    rows = [r for r in grid.dong if r["loai_can_nang"] == "thuc_te"]
    assert len(rows) >= 5
    for row in rows[:5]:
        expected = (140 - age) * weight / (72 * (row["creatinin"] / 88.4)) * (0.85 if female else 1)
        assert row["crcl"] == pytest.approx(expected, abs=0.01)


def test_graph_rejects_unverified_answer() -> None:
    bad = calls("Liều đề xuất 999999 mg [1].")
    bad.append(bad[-1])
    assert run(bad).minh_hoa == []


def test_retry_preserves_previous_block() -> None:
    bad = calls("Liều đề xuất 999999 mg [1].")
    bad.append(calls()[-1])
    result = run(bad)
    assert result.trang_thai == "ok"
    assert len(result.minh_hoa) == 1


def test_retry_keeps_only_new_block() -> None:
    sequence = calls("Liều đề xuất 999999 mg [1].")
    sequence.append(calls()[2])
    sequence.append(calls()[-1])
    result = run(sequence)
    assert result.trang_thai == "ok"
    assert len(result.minh_hoa) == 1


def test_final_pii_scan_discards_full_block(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agent.tools.gateway import ToolGateway

    original = ToolGateway.minh_hoa.fget
    assert original is not None

    def contaminated(gateway: ToolGateway) -> list[KhoiMinhHoa]:
        blocks = original(gateway)
        for block in blocks:
            block.dac_ta["tieu_de"] = "Giả Lập Sao 0912345678"
        return blocks

    monkeypatch.setattr(ToolGateway, "minh_hoa", property(contaminated))
    result = run(calls())
    assert result.trang_thai == "ok"
    assert result.minh_hoa == []


def test_graph_masks_canary_from_dataset(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agent import nodes
    from app.deid.known import GiaTriDinhDanh, base_identifiers
    from app.deid.session import DeidSession
    from app.domain.models import CaBenh
    from tests.agent.test_tool_ve_bieu_do import DataTool, spec

    def fake_session(case: CaBenh, warnings: list[str]) -> DeidSession:
        del warnings
        return DeidSession(
            [
                *base_identifiers(case),
                GiaTriDinhDanh(loai="TEN", gia_tri="Giả Lập Sao"),
                GiaTriDinhDanh(loai="SDT", gia_tri="0912345678"),
            ]
        )

    monkeypatch.setattr(nodes, "open_deid_session", fake_session)
    reg = DanhMucCongCu()
    reg.dang_ky(DataTool())
    reg.dang_ky(VeBieuDo())
    sequence = [
        {"hanh_dong": "goi_cong_cu", "goi": [{"cong_cu": "data_test", "tham_so": {}}]},
        {
            "hanh_dong": "goi_cong_cu",
            "goi": [{"cong_cu": "ve_bieu_do", "tham_so": {"dac_ta": spec()}}],
        },
        calls()[-1],
    ]
    result, _, _ = _run_graph(
        FakeLLM(sequence),
        "Creatinin của ca này bao nhiêu?",
        danh_muc=reg,
        chinh_sach=_policy(["data_test", "ve_bieu_do"]),
    )
    assert len(result.minh_hoa) == 1
    serialized = json.dumps(result.minh_hoa[0].model_dump(), ensure_ascii=False)
    assert "Giả Lập Sao" not in serialized
    assert "0912345678" not in serialized


def test_prompt_is_loaded_only_for_allowed_tool() -> None:
    llm = FakeLLM([calls()[-1]])
    _run_graph(
        llm,
        "Creatinin của ca này bao nhiêu?",
        danh_muc=registry(),
        chinh_sach=_policy(["tinh_chi_so"]),
    )
    assert "Kỹ năng minh hoạ" not in llm.calls[0]["messages"][0].content
    llm = FakeLLM([calls()[-1]])
    _run_graph(
        llm,
        "Creatinin của ca này bao nhiêu?",
        danh_muc=registry(),
        chinh_sach=_policy(["ve_bieu_do"]),
    )
    assert "Kỹ năng minh hoạ" in llm.calls[0]["messages"][0].content


def test_requested_figure_gets_one_reminder() -> None:
    from tests.agent.test_tool_ve_bieu_do import DataTool, spec

    reg = DanhMucCongCu()
    reg.dang_ky(DataTool())
    reg.dang_ky(VeBieuDo())
    answer = calls()[-1]
    data = {"hanh_dong": "goi_cong_cu", "goi": [{"cong_cu": "data_test", "tham_so": {}}]}
    draw = {
        "hanh_dong": "goi_cong_cu",
        "goi": [{"cong_cu": "ve_bieu_do", "tham_so": {"dac_ta": spec()}}],
    }
    llm = FakeLLM([data, answer, draw, answer])
    result, _, _ = _run_graph(
        llm, "Vẽ biểu đồ", danh_muc=reg, chinh_sach=_policy(["data_test", "ve_bieu_do"])
    )
    assert len(result.minh_hoa) == 1
    assert len(llm.calls) == 4

    llm = FakeLLM([data, answer, answer])
    result, _, _ = _run_graph(
        llm, "Vẽ biểu đồ", danh_muc=reg, chinh_sach=_policy(["data_test", "ve_bieu_do"])
    )
    assert not result.minh_hoa
    assert "Chưa dựng được hình cho câu hỏi này." in result.noi_dung
    assert len(llm.calls) == 3

    llm = FakeLLM([data, answer])
    _run_graph(
        llm,
        "Creatinin của ca này bao nhiêu?",
        danh_muc=reg,
        chinh_sach=_policy(["data_test", "ve_bieu_do"]),
    )
    assert len(llm.calls) == 2


def test_api_case_returns_block_without_saving_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi.testclient import TestClient

    from app.agent.asker import AgenticAsker
    from app.api.main import create_app
    from app.api.service import CaseService

    monkeypatch.setenv("AUTH_MODE", "off")
    container = build_container("test")
    asker = AgenticAsker(
        llm=FakeLLM(calls()),
        danh_muc=registry(),
        chinh_sach=ChinhSachCongCu.tu_tep(ROOT / "config/tool_policy.yaml"),
        global_asker=None,
        prompt_path=ROOT / "config/prompts/tac_tu.v1.md",
        case_settings=container.settings.case_context,
        renal_rules=container.renal_rules,
        max_turns=5,
    )
    service = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "phan_hoi.jsonl",
        ai_runner=object(),
        asker=asker,
    )
    saved = []
    original = service._store.save_chat

    def save(*args, **kwargs):
        saved.append(args[2])
        return original(*args, **kwargs)

    monkeypatch.setattr(service._store, "save_chat", save)
    with TestClient(create_app(service), raise_server_exceptions=False) as client:
        response = client.post(
            "/api/cases/DEMO-02/ask",
            json={"cau_hoi": "Creatinin của ca này bao nhiêu?", "lich_su": []},
        )
        assert response.status_code == 200, response.text
        assert len(response.json()["minh_hoa"]) == 1
        assert "minh_hoa" not in saved[0]


def test_duplicate_drawing_and_forced_answer_are_traced(tmp_path: Path) -> None:
    from app.config.settings import TracerSettings
    from app.tracing import Tracer

    sequence = calls()
    llm = FakeLLM(sequence[:2] + [sequence[2]] * 5 + [sequence[-1]])
    tracer = Tracer(TracerSettings(thu_muc=str(tmp_path), muc_noi_dung="sieu_du_lieu"))
    with tracer.bat_dau_vet("hoi_dap", "agentic") as vet:
        assert vet is not None
        result, _, _ = _run_graph(
            llm,
            "Creatinin của ca này bao nhiêu?",
            danh_muc=registry(),
            chinh_sach=_policy(["tinh_chi_so", "tra_thuoc", "ve_bieu_do"]),
        )
        record = vet.chot()
    tracer.close()
    assert result.trang_thai == "ok"
    assert len(result.minh_hoa) == 1
    assert "Đã vẽ ở mh-1, không vẽ lại" in llm.calls[4]["messages"][1].content
    assert "<<<DANH_SACH_CONG_CU\n[]\nDANH_SACH_CONG_CU>>>" in llm.calls[-1]["messages"][1].content
    assert llm.calls[-1]["schema"]["properties"]["hanh_dong"]["enum"] == ["tra_loi", "hoi_lai"]
    assert any(s.thuoc_tinh.get("so_lan_trung_hinh") == 2 for s in record.cac_buoc)
    assert any(s.thuoc_tinh.get("buoc_tra_loi_chu") is True for s in record.cac_buoc)


def test_forced_answer_still_requests_tool_falls_back() -> None:
    sequence = calls()
    bad = json.loads(json.dumps(sequence[2]))
    bad["goi"][0]["tham_so"]["dac_ta"]["nguon"] = ["tinh:khong_co"]
    llm = FakeLLM(sequence[:2] + [bad] * 6)
    result, _, _ = _run_graph(
        llm,
        "Creatinin của ca này bao nhiêu?",
        danh_muc=registry(),
        chinh_sach=_policy(["tinh_chi_so", "tra_thuoc", "ve_bieu_do"]),
    )
    assert result.trang_thai == "khong_co_nguon"
    assert result.minh_hoa == []
    assert "<<<DANH_SACH_CONG_CU\n[]\nDANH_SACH_CONG_CU>>>" in llm.calls[-1]["messages"][1].content


def test_forced_answer_after_rejection_budget() -> None:
    sequence = calls()
    bad = json.loads(json.dumps(sequence[2]))
    bad["goi"][0]["tham_so"]["dac_ta"]["nguon"] = ["tinh:khong_co"]
    llm = FakeLLM(sequence[:2] + [bad] * 5 + [sequence[-1]])
    result, _, _ = _run_graph(
        llm,
        "Creatinin của ca này bao nhiêu?",
        danh_muc=registry(),
        chinh_sach=_policy(["tinh_chi_so", "tra_thuoc", "ve_bieu_do"]),
    )
    assert result.trang_thai == "ok"
    assert result.minh_hoa == []
    assert "het_luot_ve" in llm.calls[5]["messages"][1].content
    assert "<<<DANH_SACH_CONG_CU\n[]\nDANH_SACH_CONG_CU>>>" in llm.calls[-1]["messages"][1].content


def test_skill_states_images_are_not_in_history() -> None:
    content = (ROOT / "config/prompts/ky_nang_minh_hoa.v1.md").read_text(encoding="utf-8")
    assert "lịch sử không có hình" in content
    assert "trong cùng một lượt" in content


def test_previous_assistant_image_id_is_removed_from_prompt() -> None:
    from app.agent.asker import AgenticAsker

    container = build_container("test")
    llm = FakeLLM([calls()[-1]])
    asker = AgenticAsker(
        llm=llm,
        danh_muc=registry(),
        chinh_sach=_policy(["tinh_chi_so"]),
        global_asker=None,
        prompt_path=ROOT / "config/prompts/tac_tu.v1.md",
        case_settings=container.settings.case_context,
        renal_rules=container.renal_rules,
        max_turns=5,
    )
    history = [
        ("he_thong", "Hình mh-1 đã thể hiện kết quả."),
        ("nguoi_dung", "Mã mh-2 là gì?"),
    ]
    asker.ask(load_case(DEMO_02_PATH), "Creatinin của ca này bao nhiêu?", history)
    prompt = llm.calls[0]["messages"][1].content
    assert "mh-1" not in prompt
    assert "hình (không còn hiển thị)" in prompt
    assert "mh-2" in prompt
    assert history[0][1] == "Hình mh-1 đã thể hiện kết quả."


def test_filter_missing_figure() -> None:
    from app.agent.nodes import _filter_missing_figure

    assert (
        _filter_missing_figure("Có kết quả. Mời dược sĩ xem hình bên dưới.", "Vẽ biểu đồ")
        == "Có kết quả.\nChưa dựng được hình cho câu hỏi này."
    )
    assert _filter_missing_figure("Có kết quả. Xem hình.", "Kết quả?") == "Có kết quả."


def test_missing_figure_filter_in_verified_answer() -> None:
    sequence = calls("Creatinin máu là 212 umol/L [1]. Mời xem hình bên dưới.")
    without_figure = run(sequence[:2] + sequence[-1:])
    assert without_figure.trang_thai == "ok"
    assert "xem hình" not in without_figure.noi_dung.lower()
    with_figure = run(sequence)
    assert with_figure.minh_hoa
    assert "xem hình" in with_figure.noi_dung.lower()


def test_schema_failure_recovers_verified_answer_with_figure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.progress import TienTrinh
    from tests.agent import test_graph

    tracker = TienTrinh()
    monkeypatch.setattr(test_graph, "TienTrinh", lambda: tracker)
    sequence = calls()
    honest = sequence[-1]["tra_loi"]
    result, steps, _ = _run_graph(
        FakeLLM(sequence[:3] + [{"sai": True}, {"sai": True}, honest]),
        "Creatinin của ca này bao nhiêu?",
        danh_muc=registry(),
        chinh_sach=_policy(["tinh_chi_so", "tra_thuoc", "ve_bieu_do"]),
    )
    assert result.trang_thai == "ok"
    assert "212" in result.noi_dung
    assert len(result.minh_hoa) == 1
    assert "agent_du_phong" in steps
    assert any(
        step.trang_thai == "xong"
        and step.chi_tiet == "Đầu ra sai định dạng, chuyển sang trả lời thận trọng"
        for step in tracker.chup()
    )


def test_schema_failure_and_invalid_honest_answer_returns_error() -> None:
    from app.orchestration.ask import ERROR_MESSAGE

    sequence = calls()
    result = run(sequence[:3] + [{"sai": True}, {"sai": True}, {"sai": True}])
    assert result.trang_thai == "loi"
    assert result.noi_dung == ERROR_MESSAGE
    assert not result.minh_hoa
