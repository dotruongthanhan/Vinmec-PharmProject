"""Kiểm thử mô hình tiến trình, ContextVar không rò và điểm ghi sự kiện."""

import threading
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.container import build_container
from app.core.errors import ProviderError
from app.core.progress import (
    ASK_PROGRESS_RETENTION_SECONDS,
    MAX_ASK_PROGRESS_ENTRIES,
    MAX_PROGRESS_STEPS,
    MAX_PROGRESS_TEXT_LEN,
    AskProgressRegistry,
    BuocTienTrinh,
    NguonTomTat,
    TienTrinh,
    ghi_buoc,
    tien_trinh_hien_tai,
)
from app.core.types import Chunk, RetrievalQuery, ScoredChunk
from app.domain.loader import load_case
from app.kb.names import DrugNameIndex
from app.llm.synthesizer import Synthesizer
from app.orchestration.ai_review import AiReviewer
from app.orchestration.ask import CaseAsker
from app.orchestration.evidence import EvidenceCollector
from app.orchestration.jobs import AiJobManager
from app.pipeline import run_case
from app.providers.fakes import FakeLLM
from app.retrieval.query_builder import QueryBuilder
from tests.core.test_types import make_chunk
from tests.deid_support import temp_id

ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = ROOT / "config/prompts/tong_hop.v1.md"
NAMES = DrugNameIndex.load(ROOT / "data/kb/hoat_chat.json")


class _StaticRetriever:
    """Bộ truy xuất giả trả sẵn danh sách đoạn nguồn."""

    def __init__(self, chunks: list[Chunk]) -> None:
        self._chunks = chunks

    def retrieve(self, query: RetrievalQuery) -> list[ScoredChunk]:
        del query
        return [
            ScoredChunk(chunk=chunk, diem=0.9 - idx * 0.01, nguon_diem="xep_hang_lai")
            for idx, chunk in enumerate(self._chunks)
        ]


def _wait_until_done(manager: AiJobManager, ca_id: str, timeout: float = 2.0) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = manager.get(ca_id)
        if state is not None and state.trang_thai != "dang_chay":
            return state.trang_thai
        time.sleep(0.01)
    raise AssertionError("Quá thời gian chờ tác vụ nền")


def test_tien_trinh_lifecycle_limits_clipping_and_snapshot_isolation() -> None:
    tp = TienTrinh(bat_dau=100.0)
    tp.dang_ky("b1", "Bước một")
    tp.dang_ky("b2", "Bước hai")
    tp.dang_ky("b3", "Bước ba")

    tp.bat_dau("b1", chi_tiet="Đang chạy")
    mid = tp.chup(now=100.0 + 0.25)
    assert [step.ma for step in mid] == ["b1", "b2", "b3"]
    assert mid[0].trang_thai == "dang_chay"
    assert mid[0].thoi_gian_ms is not None
    assert mid[0].thoi_gian_ms >= 0.0
    assert mid[1].trang_thai == "cho"
    assert mid[1].thoi_gian_ms is None

    # Sửa bản chụp trả về không ảnh hưởng dữ liệu nội bộ.
    mid[0].nguon.append(NguonTomTat(nhan="Biến đổi ngoài", so_doan=99))
    assert tp.chup()[0].nguon == []

    tp.xong("b1", chi_tiet="X" * 250, nguon=[NguonTomTat(nhan="Y" * 200, so_doan=3)])
    tp.bat_dau("b2")
    tp.chot(False)

    final = tp.chup()
    assert final[0].trang_thai == "xong"
    assert len(final[0].chi_tiet or "") == MAX_PROGRESS_TEXT_LEN
    assert len(final[0].nguon[0].nhan) == MAX_PROGRESS_TEXT_LEN
    assert final[1].trang_thai == "loi"
    assert final[2].trang_thai == "bo_qua"
    assert tp.tong_ms(now=102.5) >= 0.0

    # Vượt 40 bước bị bỏ qua im lặng.
    capped = TienTrinh()
    for i in range(MAX_PROGRESS_STEPS + 10):
        capped.them(f"buoc_{i}", f"Tên bước {i}")
    capped.bat_dau("buoc_45")
    assert len(capped.chup()) == MAX_PROGRESS_STEPS

    # Mô hình pydantic từ chối trường thừa.
    with pytest.raises(ValidationError):
        BuocTienTrinh(ma="b", ten="Bước", trang_thai="cho", truong_la=1)  # type: ignore[call-arg]


def test_ghi_buoc_without_tracker_is_noop() -> None:
    assert tien_trinh_hien_tai.get() is None
    ghi_buoc("dang_ky", "x", ten="X")
    ghi_buoc("them", "y", ten="Y")
    ghi_buoc("bat_dau", "x", chi_tiet="Đang chạy")
    ghi_buoc("xong", "x", chi_tiet="Xong")
    ghi_buoc("loi", "x", ly_do="Lỗi", goi_y="Thử lại")


def test_parallel_jobs_do_not_leak_contextvar_steps() -> None:
    manager = AiJobManager(max_workers=2)
    try:
        barrier = threading.Barrier(2)

        def job_a() -> str:
            barrier.wait(timeout=2.0)
            ghi_buoc("bat_dau", "thu_thap_nguon")
            ghi_buoc("them", "buoc_rieng_a", ten="Riêng A")
            ghi_buoc("bat_dau", "buoc_rieng_a")
            ghi_buoc("xong", "buoc_rieng_a", chi_tiet="Chỉ của A")
            ghi_buoc("xong", "thu_thap_nguon", chi_tiet="1 đoạn từ 1 nguồn")
            return "A"

        def job_b() -> str:
            barrier.wait(timeout=2.0)
            ghi_buoc("bat_dau", "thu_thap_nguon")
            ghi_buoc("them", "buoc_rieng_b", ten="Riêng B")
            ghi_buoc("bat_dau", "buoc_rieng_b")
            ghi_buoc("xong", "buoc_rieng_b", chi_tiet="Chỉ của B")
            ghi_buoc("xong", "thu_thap_nguon", chi_tiet="2 đoạn từ 1 nguồn")
            return "B"

        manager.start("CA-A", job_a)
        manager.start("CA-B", job_b)

        assert _wait_until_done(manager, "CA-A") == "xong"
        assert _wait_until_done(manager, "CA-B") == "xong"
        assert tien_trinh_hien_tai.get() is None

        steps_a = [step.ma for step in manager.get("CA-A").tien_trinh.chup()]  # type: ignore[union-attr]
        steps_b = [step.ma for step in manager.get("CA-B").tien_trinh.chup()]  # type: ignore[union-attr]
        assert "buoc_rieng_a" in steps_a
        assert "buoc_rieng_b" not in steps_a
        assert "buoc_rieng_b" in steps_b
        assert "buoc_rieng_a" not in steps_b

        # Tác vụ kế tiếp trên worker cũ không bị rò ContextVar từ tác vụ trước.
        seen_before: list[object] = []

        def probe_job() -> str:
            seen_before.append(tien_trinh_hien_tai.get())
            return "ok"

        manager.start("CA-C", probe_job)
        assert _wait_until_done(manager, "CA-C") == "xong"
        assert seen_before[0] is manager.get("CA-C").tien_trinh  # type: ignore[union-attr]
    finally:
        manager.shutdown()


def test_job_manager_median_thuong_le_ms_needs_three_successes() -> None:
    manager = AiJobManager(max_workers=2)
    try:
        assert manager.thuong_le_ms() is None

        def fast_ok() -> dict[str, object]:
            return {"ok": True}

        def failing() -> None:
            raise RuntimeError("Lỗi giả lập")

        manager.start("C1", fast_ok)
        assert _wait_until_done(manager, "C1") == "xong"
        assert manager.thuong_le_ms() is None

        manager.start("C2", fast_ok)
        assert _wait_until_done(manager, "C2") == "xong"
        assert manager.thuong_le_ms() is None

        # Lượt lỗi không được tính vào trung vị.
        manager.start("C-ERR", failing)
        assert _wait_until_done(manager, "C-ERR") == "loi"
        assert manager.thuong_le_ms() is None

        manager.start("C3", fast_ok)
        assert _wait_until_done(manager, "C3") == "xong"
        median_ms = manager.thuong_le_ms()
        assert median_ms is not None
        assert median_ms >= 0.0
    finally:
        manager.shutdown()


def test_nodes_and_synthesizer_record_steps_and_errors_in_job_manager() -> None:
    container = build_container("test")
    case = load_case(ROOT / "data/mock/demo/DEMO-02.json")
    rule = run_case(case, container.renal_rules)

    # 1. Thu thập nhiều nguồn (giới hạn tối đa 8 nhóm, sắp giảm dần) + thử lại lượt 2.
    chunks = (
        [make_chunk(f"C-FDA-{i}", "dose adjustment", nguon="openfda") for i in range(4)]
        + [make_chunk(f"C-BYT-{i}", "hướng dẫn", nguon="byt") for i in range(2)]
        + [make_chunk(f"C-EXTRA-{i}", "khác", nguon=f"nguon_{i}") for i in range(8)]
    )
    collector = EvidenceCollector(
        _StaticRetriever(chunks[:8]),
        QueryBuilder(container.settings.retrieval),
        NAMES.resolve,
    )
    valid_payload = {
        "nhan_dinh": [
            {
                "chi_tiet_y_lenh_id": [temp_id("DEMO-02", "CT-DEMO02-01")],
                "yeu_to": 5,
                "ket_luan": "can_xem",
                "muc_do": "can_luu_y",
                "nhan_xet": "Creatinin tăng lên 212 umol/L, cần theo dõi.",
                "ban_ghi_ids": [temp_id("DEMO-02", "XN-DEMO02-01")],
                "trich_dan": [],
                "thong_tin_con_thieu": [],
                "de_xuat": None,
                "bo_sung_cho_ma_luat": None,
            }
        ]
    }
    synth_retry = Synthesizer(
        llm=FakeLLM([{"sai_luoc_do": True}, valid_payload]),
        prompt_path=PROMPT_PATH,
        case_settings=container.settings.case_context,
        evidence_max_chars=12000,
        max_synthesis_attempts=2,
        model_name="deepseek-flash",
    )
    reviewer_retry = AiReviewer(collector, synth_retry, engine="langgraph")

    manager = AiJobManager(max_workers=2)
    try:
        manager.start("DEMO-02", lambda: reviewer_retry.run(case, rule))
        assert _wait_until_done(manager, "DEMO-02") == "xong"
        steps = manager.get("DEMO-02").tien_trinh.chup()  # type: ignore[union-attr]
        by_ma = {step.ma: step for step in steps}

        assert by_ma["thu_thap_nguon"].trang_thai == "xong"
        assert by_ma["thu_thap_nguon"].chi_tiet == "8 đoạn từ 4 nguồn"
        assert [n.nhan for n in by_ma["thu_thap_nguon"].nguon] == [
            "Nhãn FDA",
            "Hướng dẫn Bộ Y tế",
            "nguon 0",
            "nguon 1",
        ]
        assert [n.so_doan for n in by_ma["thu_thap_nguon"].nguon] == [4, 2, 1, 1]

        assert by_ma["tong_hop_1"].trang_thai == "xong"
        assert by_ma["tong_hop_1"].chi_tiet == "Đầu ra sai định dạng, thử lại"
        assert by_ma["kiem_chung_1"].trang_thai == "bo_qua"
        assert by_ma["tong_hop_2"].ten == "Tổng hợp lại, lần 2"
        assert by_ma["tong_hop_2"].trang_thai == "xong"
        assert by_ma["kiem_chung_2"].ten == "Kiểm chứng lại, lần 2"
        assert by_ma["kiem_chung_2"].trang_thai == "xong"
        assert by_ma["kiem_chung_2"].chi_tiet == "1/1 dòng đạt"

        # 2. Lỗi vượt hạn mức token.
        class _TokenLimitLLM:
            def complete_json(self, messages: list, schema: dict) -> dict:
                del messages, schema
                raise ProviderError("het_han_muc_token")

        synth_token = Synthesizer(
            llm=_TokenLimitLLM(),  # type: ignore[arg-type]
            prompt_path=PROMPT_PATH,
            case_settings=container.settings.case_context,
            evidence_max_chars=12000,
            max_synthesis_attempts=1,
            model_name="deepseek-flash",
        )
        empty_collector = EvidenceCollector(
            _StaticRetriever([]),
            QueryBuilder(container.settings.retrieval),
            NAMES.resolve,
        )
        reviewer_token = AiReviewer(empty_collector, synth_token, engine="langgraph")
        manager.start("DEMO-02-TOK", lambda: reviewer_token.run(case, rule))
        assert _wait_until_done(manager, "DEMO-02-TOK") == "xong"
        tok_tracker = manager.get("DEMO-02-TOK").tien_trinh  # type: ignore[union-attr]
        tok_steps = {s.ma: s for s in tok_tracker.chup()}
        assert tok_steps["thu_thap_nguon"].trang_thai == "xong"
        assert tok_steps["thu_thap_nguon"].chi_tiet == "Không tìm thấy đoạn nguồn phù hợp"
        assert tok_steps["tong_hop_1"].trang_thai == "loi"
        assert tok_steps["tong_hop_1"].ly_do == "Vượt hạn mức độ dài"
        assert tok_steps["tong_hop_1"].goi_y == "Bảng luật vẫn đúng; bấm Thử lại sau ít phút"
        assert tok_steps["kiem_chung_1"].trang_thai == "bo_qua"

        # 3. Lỗi ở nút ThuThapNguon không lộ nội dung ngoại lệ.
        class _BrokenCollector(EvidenceCollector):
            def collect(  # type: ignore[override]
                self, ca: object, ket_qua: object
            ) -> tuple[list[Chunk], list[str]]:
                del ca, ket_qua
                raise RuntimeError("SENSITIVE_PATIENT_INFO_123")

        broken_collector = _BrokenCollector(
            _StaticRetriever([]),
            QueryBuilder(container.settings.retrieval),
            NAMES.resolve,
        )
        reviewer_broken = AiReviewer(broken_collector, synth_token, engine="langgraph")
        manager.start("DEMO-02-ERR", lambda: reviewer_broken.run(case, rule))
        assert _wait_until_done(manager, "DEMO-02-ERR") == "xong"
        err_tracker = manager.get("DEMO-02-ERR").tien_trinh  # type: ignore[union-attr]
        err_steps = {s.ma: s for s in err_tracker.chup()}
        assert err_steps["thu_thap_nguon"].trang_thai == "loi"
        assert err_steps["thu_thap_nguon"].ly_do == "Không lấy được nguồn"
        assert err_steps["thu_thap_nguon"].goi_y == "Thử lại; bảng luật vẫn dùng được"
        assert err_steps["tong_hop_1"].trang_thai == "bo_qua"
        assert err_steps["kiem_chung_1"].trang_thai == "bo_qua"
    finally:
        manager.shutdown()


def test_thu_thap_nguon_caps_source_groups_at_eight() -> None:
    from app.orchestration.graph.nodes import ThuThapNguon

    container = build_container("test")
    case = load_case(ROOT / "data/mock/demo/DEMO-02.json")
    rule = run_case(case, container.renal_rules)
    many_chunks = [
        make_chunk("C-A1", "nội dung", nguon="openfda"),
        make_chunk("C-A2", "nội dung", nguon="openfda"),
        *[make_chunk(f"C-{i}", "nội dung", nguon=f"nguon_{i}") for i in range(9)],
    ]

    class _ManySourceCollector(EvidenceCollector):
        def collect(  # type: ignore[override]
            self, ca: object, ket_qua: object
        ) -> tuple[list[Chunk], list[str]]:
            del ca, ket_qua
            return many_chunks, []

    collector = _ManySourceCollector(
        _StaticRetriever([]),
        QueryBuilder(container.settings.retrieval),
        NAMES.resolve,
    )
    node = ThuThapNguon(collector)
    tp = TienTrinh()
    tp.dang_ky("thu_thap_nguon", "Lấy nguồn")
    token = tien_trinh_hien_tai.set(tp)
    try:
        node({"ca": case, "ket_qua_luat": rule})
    finally:
        tien_trinh_hien_tai.reset(token)

    step = tp.chup()[0]
    assert step.trang_thai == "xong"
    assert step.chi_tiet == "11 đoạn từ 10 nguồn"
    assert len(step.nguon) == 8
    assert step.nguon[0] == NguonTomTat(nhan="Nhãn FDA", so_doan=2)


def test_ask_progress_registry_lifecycle_retention_token_and_cap() -> None:
    now = [100.0]
    registry = AskProgressRegistry(clock=lambda: now[0])
    steps_spec = [("chuan_bi", "Chuẩn bị ngữ cảnh ca"), ("goi_mo_hinh", "Soạn câu trả lời")]

    key_a = ("DEMO-02", "user-a")
    key_b = ("DEMO-02", "user-b")
    token_a, tp_a = registry.bat_dau(key_a, steps_spec)
    tp_a.bat_dau("chuan_bi")

    snap_running = registry.doc(key_a)
    assert snap_running is not None
    assert snap_running[0] is True
    assert [s.ma for s in snap_running[1]] == ["chuan_bi", "goi_mo_hinh"]
    assert snap_running[1][0].trang_thai == "dang_chay"
    assert snap_running[2] >= 0.0
    assert registry.doc(key_b) is None

    registry.ket_thuc(key_a, token_a, True)
    snap_done = registry.doc(key_a)
    assert snap_done is not None
    assert snap_done[0] is False
    assert snap_done[1][0].trang_thai == "xong"
    assert snap_done[1][1].trang_thai == "bo_qua"

    now[0] = 100.0 + ASK_PROGRESS_RETENTION_SECONDS - 0.1
    assert registry.doc(key_a) is not None

    now[0] = 100.0 + ASK_PROGRESS_RETENTION_SECONDS
    assert registry.doc(key_a) is None

    # Mục cũ kết thúc muộn không được xoá hoặc chốt mục mới cùng khoá.
    t_old, _ = registry.bat_dau(key_a, [("chuan_bi", "Lượt cũ")])
    t_new, tp_new = registry.bat_dau(key_a, [("chuan_bi", "Lượt mới")])
    tp_new.bat_dau("chuan_bi")
    registry.ket_thuc(key_a, t_old, False)
    still_new = registry.doc(key_a)
    assert still_new is not None
    assert still_new[0] is True
    assert still_new[1][0].ten == "Lượt mới"
    assert still_new[1][0].trang_thai == "dang_chay"
    registry.ket_thuc(key_a, t_new, True)

    # Trần 200 mục: đẩy mục tạo sớm nhất ra.
    for i in range(MAX_ASK_PROGRESS_ENTRIES + 5):
        registry.bat_dau((f"CA-{i}", "u"), [("chuan_bi", "Chuẩn bị")])
    for i in range(5):
        assert registry.doc((f"CA-{i}", "u")) is None
    for i in range(5, MAX_ASK_PROGRESS_ENTRIES + 5):
        assert registry.doc((f"CA-{i}", "u")) is not None


@pytest.mark.luong_cu_cung
def test_case_asker_records_steps_for_success_retry_and_errors() -> None:
    container = build_container("test")
    case = load_case(ROOT / "data/mock/demo/DEMO-02.json")
    rule = run_case(case, container.renal_rules)
    ask_prompt = ROOT / "config/prompts/hoi_them.v1.md"

    def _run_with_tracker(
        asker: CaseAsker,
        question: str,
        *,
        is_global: bool = False,
    ) -> tuple[object, list[BuocTienTrinh]]:
        tp = TienTrinh()
        if is_global:
            tp.dang_ky("chuan_bi", "Tổng hợp danh sách y lệnh")
            tp.dang_ky("goi_mo_hinh", "Soạn câu trả lời")
            tp.dang_ky("kiem_chung", "Kiểm chứng trích dẫn và số liệu")
        else:
            tp.dang_ky("chuan_bi", "Chuẩn bị ngữ cảnh ca")
            tp.dang_ky("truy_xuat", "Tra cứu nguồn")
            tp.dang_ky("goi_mo_hinh", "Soạn câu trả lời")
            tp.dang_ky("kiem_chung", "Kiểm chứng trích dẫn và số liệu")
        token = tien_trinh_hien_tai.set(tp)
        try:
            if is_global:
                res = asker.ask_global([case], {case.ca_id: rule}, question)
            else:
                res = asker.ask(case, question, ket_qua=rule)
        finally:
            tien_trinh_hien_tai.reset(token)
        tp.chot(getattr(res, "trang_thai", None) == "ok")
        return res, tp.chup()

    chunks = [
        make_chunk(
            "DT-MERO-01",
            "For creatinine clearance 10 to 25 mL/min, administer one-half the "
            "recommended dose every 12 hours.",
            nguon="openfda",
        ),
        make_chunk("DT-MERO-02", "Hướng dẫn dùng meropenem.", nguon="openfda"),
        make_chunk("DT-BYT-01", "Hướng dẫn Bộ Y tế về kháng sinh.", nguon="byt"),
    ]
    good_payload = {
        "pham_vi": "trong",
        "tra_loi": "Creatinin 212 umol/L [1], nhãn FDA khuyến cáo giảm nửa liều mỗi 12 giờ [2].",
        "trich_dan": [
            {"so": 1, "loai": "du_lieu_ca", "ma": temp_id("DEMO-02", "XN-DEMO02-01")},
            {
                "so": 2,
                "loai": "tai_lieu",
                "ma": "DT-MERO-01",
                "trich_nguyen_van": "administer one-half the recommended dose every 12 hours.",
            },
        ],
    }

    # 1. Thành công với truy xuất nhiều nguồn.
    asker_ok = CaseAsker(
        llm=FakeLLM([good_payload]),
        retriever=_StaticRetriever(chunks),
        query_builder=QueryBuilder(container.settings.retrieval),
        resolve_name=NAMES.resolve,
        prompt_path=ask_prompt,
        case_settings=container.settings.case_context,
        evidence_max_chars=container.settings.evidence.max_chars,
        model_name="deepseek-flash",
        renal_rules=container.renal_rules,
    )
    res_ok, steps_ok = _run_with_tracker(asker_ok, "Vì sao cần giảm liều meropenem?")
    assert res_ok.trang_thai == "ok"  # type: ignore[attr-defined]
    by_ma = {s.ma: s for s in steps_ok}
    assert by_ma["chuan_bi"].trang_thai == "xong"
    assert by_ma["truy_xuat"].trang_thai == "xong"
    assert by_ma["truy_xuat"].chi_tiet == "3 đoạn từ 2 nguồn"
    assert by_ma["truy_xuat"].nguon == [
        NguonTomTat(nhan="Nhãn FDA", so_doan=2),
        NguonTomTat(nhan="Hướng dẫn Bộ Y tế", so_doan=1),
    ]
    assert by_ma["goi_mo_hinh"].trang_thai == "xong"
    assert by_ma["kiem_chung"].trang_thai == "xong"
    assert by_ma["kiem_chung"].chi_tiet == "Đạt"

    # 2. Không dùng tra cứu nguồn (retriever=None).
    no_ret_payload = {
        "pham_vi": "trong",
        "tra_loi": "Creatinin 212 umol/L [1].",
        "trich_dan": [{"so": 1, "loai": "du_lieu_ca", "ma": temp_id("DEMO-02", "XN-DEMO02-01")}],
    }
    asker_no_ret = CaseAsker(
        llm=FakeLLM([no_ret_payload]),
        retriever=None,
        query_builder=QueryBuilder(container.settings.retrieval),
        resolve_name=NAMES.resolve,
        prompt_path=ask_prompt,
        case_settings=container.settings.case_context,
        evidence_max_chars=container.settings.evidence.max_chars,
        model_name="deepseek-flash",
        renal_rules=container.renal_rules,
    )
    res_no_ret, steps_no_ret = _run_with_tracker(asker_no_ret, "Creatinin ca này bao nhiêu?")
    assert res_no_ret.trang_thai == "ok"  # type: ignore[attr-defined]
    assert {s.ma: s for s in steps_no_ret}["truy_xuat"].chi_tiet == "Không dùng tra cứu nguồn"

    # 3. Thử lại lần 2 do kiểm chứng không đạt.
    bad_number_payload = {
        "pham_vi": "trong",
        "tra_loi": "Creatinin 212 umol/L [1], truyền 750 mg [2].",
        "trich_dan": good_payload["trich_dan"],
    }
    asker_retry = CaseAsker(
        llm=FakeLLM([bad_number_payload, good_payload]),
        retriever=_StaticRetriever(chunks),
        query_builder=QueryBuilder(container.settings.retrieval),
        resolve_name=NAMES.resolve,
        prompt_path=ask_prompt,
        case_settings=container.settings.case_context,
        evidence_max_chars=container.settings.evidence.max_chars,
        model_name="deepseek-flash",
        renal_rules=container.renal_rules,
    )
    res_retry, steps_retry = _run_with_tracker(asker_retry, "Liều meropenem thế nào?")
    assert res_retry.trang_thai == "ok"  # type: ignore[attr-defined]
    by_ma_retry = {s.ma: s for s in steps_retry}
    assert by_ma_retry["kiem_chung"].trang_thai == "xong"
    assert by_ma_retry["kiem_chung"].chi_tiet == "Không đạt, thử lại"
    assert by_ma_retry["goi_mo_hinh_2"].ten == "Soạn lại, lần 2"
    assert by_ma_retry["goi_mo_hinh_2"].trang_thai == "xong"
    assert by_ma_retry["kiem_chung_2"].ten == "Kiểm chứng lại, lần 2"
    assert by_ma_retry["kiem_chung_2"].trang_thai == "xong"
    assert by_ma_retry["kiem_chung_2"].chi_tiet == "Đạt"

    # 4. Các loại lỗi provider và ngoại lệ chung không rò message gốc.
    class _RaisingLLM:
        def __init__(self, err: Exception) -> None:
            self._err = err

        def complete_json(self, messages: list, schema: dict) -> dict:
            del messages, schema
            raise self._err

    for exc_obj, expected_reason in (
        (ProviderError("het_han_muc_token"), "Vượt hạn mức độ dài"),
        (ProviderError("Lỗi kết nối nhà cung cấp"), "Không kết nối được nhà cung cấp mô hình"),
        (RuntimeError("SENSITIVE_ERR_999"), "Không soạn được câu trả lời"),
    ):
        asker_err = CaseAsker(
            llm=_RaisingLLM(exc_obj),  # type: ignore[arg-type]
            retriever=None,
            query_builder=QueryBuilder(container.settings.retrieval),
            resolve_name=NAMES.resolve,
            prompt_path=ask_prompt,
            case_settings=container.settings.case_context,
            evidence_max_chars=container.settings.evidence.max_chars,
            model_name="deepseek-flash",
            renal_rules=container.renal_rules,
        )
        res_err, steps_err = _run_with_tracker(asker_err, "Câu hỏi kiểm tra lỗi?")
        assert res_err.trang_thai == "loi"  # type: ignore[attr-defined]
        by_ma_err = {s.ma: s for s in steps_err}
        assert by_ma_err["goi_mo_hinh"].trang_thai == "loi"
        assert by_ma_err["goi_mo_hinh"].ly_do == expected_reason
        assert by_ma_err["goi_mo_hinh"].goi_y == "Bấm Thử lại sau ít phút"
        assert by_ma_err["kiem_chung"].trang_thai == "bo_qua"
        assert "SENSITIVE_ERR_999" not in str(steps_err)

    # 5. Nhánh hỏi đáp chung ask_global.
    global_payload = {
        "pham_vi": "trong",
        "tra_loi": "Có 1 ca đang dùng meropenem.",
        "trich_dan": [],
    }
    asker_global = CaseAsker(
        llm=FakeLLM([global_payload]),
        retriever=None,
        query_builder=QueryBuilder(container.settings.retrieval),
        resolve_name=NAMES.resolve,
        prompt_path=ask_prompt,
        case_settings=container.settings.case_context,
        evidence_max_chars=container.settings.evidence.max_chars,
        model_name="deepseek-flash",
        renal_rules=container.renal_rules,
    )
    res_g, steps_g = _run_with_tracker(asker_global, "Ca nào cần chú ý?", is_global=True)
    assert res_g.trang_thai == "ok"  # type: ignore[attr-defined]
    by_ma_g = {s.ma: s for s in steps_g}
    assert list(by_ma_g) == ["chuan_bi", "goi_mo_hinh", "kiem_chung"]
    assert by_ma_g["chuan_bi"].ten == "Tổng hợp danh sách y lệnh"
    assert by_ma_g["chuan_bi"].trang_thai == "xong"
    assert by_ma_g["goi_mo_hinh"].trang_thai == "xong"
    assert by_ma_g["kiem_chung"].trang_thai == "xong"
    assert by_ma_g["kiem_chung"].chi_tiet == "Đạt"
