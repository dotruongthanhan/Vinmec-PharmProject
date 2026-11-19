"""Kiểm thử AiReviewer và chuyển đổi present_ai_result cùng bất biến hợp đồng."""

from pathlib import Path

from app.api.presenter import present_ai_result, present_case
from app.container import build_container
from app.core.types import Chunk, RetrievalQuery, ScoredChunk
from app.domain.loader import load_case
from app.kb.names import DrugNameIndex
from app.llm.schema import KetQuaLLM, NhanDinhCuoi, NhanDinhDeXuat, TrichDanNguon
from app.llm.synthesizer import Synthesizer
from app.orchestration.ai_review import AiReviewer, AiRunResult
from app.orchestration.evidence import EvidenceCollector
from app.pipeline import run_case
from app.providers.fakes import FakeLLM
from app.retrieval.query_builder import QueryBuilder
from app.rules import load_renal_rules
from tests.deid_support import temp_id

ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = ROOT / "config/prompts/tong_hop.v1.md"


def _sample_chunk() -> Chunk:
    return Chunk(
        doan_trich_id="DT-MERO-01",
        tai_lieu_id="TL-MERO",
        muc_cha_id=None,
        nhom_nguon="nhan_thuoc",
        nguon="openfda",
        tang_tin_cay=3,
        hoat_chat_ids=["meropenem"],
        muc="lieu_than",
        duong_dan_muc="Dosage and Administration > Renal Impairment",
        loai_noi_dung="van_ban",
        ngon_ngu="en",
        phien_ban_nguon="20261102",
        url_goc="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=mero",
        noi_dung_goc=(
            "For creatinine clearance 10 to 25 mL/min, administer one-half the "
            "recommended dose every 12 hours."
        ),
        noi_dung_nhung="[Meropenem | FDA] For creatinine clearance 10 to 25 mL/min...",
    )


class _StaticRetriever:
    def __init__(self, chunks: list[Chunk]) -> None:
        self._chunks = chunks

    def retrieve(self, query: RetrievalQuery) -> list[ScoredChunk]:
        del query
        return [
            ScoredChunk(chunk=chunk, diem=0.9, nguon_diem="xep_hang_lai") for chunk in self._chunks
        ]


def test_ai_reviewer_runs_collect_and_synthesizer_and_merges_warnings() -> None:
    container = build_container("test")
    case = load_case(ROOT / "data/mock/demo/DEMO-02.json")
    rule_result = run_case(case, container.renal_rules)
    chunk = _sample_chunk()
    names = DrugNameIndex.load(ROOT / "data/kb/hoat_chat.json")
    collector = EvidenceCollector(
        _StaticRetriever([chunk]),
        QueryBuilder(container.settings.retrieval),
        names.resolve,
    )
    fake_llm = FakeLLM(
        [
            {
                "nhan_dinh": [
                    {
                        "chi_tiet_y_lenh_id": [temp_id("DEMO-02", "CT-DEMO02-01")],
                        "yeu_to": 6,
                        "ket_luan": "can_xem",
                        "muc_do": "nghiem_trong",
                        "nhan_xet": "CrCl 16,0 mL/phút, cần xem xét giảm liều theo nhãn FDA.",
                        "ban_ghi_ids": [temp_id("DEMO-02", "XN-DEMO02-01")],
                        "trich_dan": [
                            {
                                "doan_trich_id": "DT-MERO-01",
                                "trich_nguyen_van": (
                                    "administer one-half the recommended dose every 12 hours."
                                ),
                            }
                        ],
                        "thong_tin_con_thieu": [],
                        "de_xuat": "Cân nhắc giảm một nửa liều mỗi 12 giờ.",
                        "bo_sung_cho_ma_luat": "lieu_than_can_chinh",
                    }
                ]
            }
        ]
    )
    synth = Synthesizer(
        llm=fake_llm,
        prompt_path=PROMPT_PATH,
        case_settings=container.settings.case_context,
        evidence_max_chars=12000,
        max_synthesis_attempts=2,
        model_name="deepseek-flash",
    )

    run = AiReviewer(collector, synth).run(case, rule_result)

    assert isinstance(run, AiRunResult)
    assert run.llm.trang_thai == "ok"
    assert run.doan == [chunk]
    assert run.thoi_gian_ms >= 0.0
    assert any(item.dien_giai is not None for item in run.llm.nhan_dinh)


def test_ai_reviewer_wraps_unexpected_error_without_leaking_case_content() -> None:
    container = build_container("test")
    case = load_case(ROOT / "data/mock/demo/DEMO-02.json")
    rule_result = run_case(case, container.renal_rules)
    synth = Synthesizer(
        llm=None,
        prompt_path=PROMPT_PATH,
        case_settings=container.settings.case_context,
        evidence_max_chars=12000,
        max_synthesis_attempts=1,
        model_name="deepseek-flash",
    )

    class _BrokenCollector(EvidenceCollector):
        def collect(  # type: ignore[override]
            self, ca: object, ket_qua: object
        ) -> tuple[list[Chunk], list[str]]:
            del ca, ket_qua
            raise RuntimeError("Dữ liệu nhạy cảm bệnh nhân X")

    names = DrugNameIndex.load(ROOT / "data/kb/hoat_chat.json")
    collector = _BrokenCollector(
        _StaticRetriever([]),
        QueryBuilder(container.settings.retrieval),
        names.resolve,
    )

    run = AiReviewer(collector, synth).run(case, rule_result)

    assert run.llm.trang_thai == "loi_llm"
    assert run.canh_bao == ["Bước AI gặp lỗi không mong muốn (RuntimeError)"]
    assert "nhạy cảm" not in " ".join(run.canh_bao)


def test_present_ai_result_demo02_keeps_rules_adds_verified_drops_unverified() -> None:
    case = load_case(ROOT / "data/mock/demo/DEMO-02.json")
    rule_result = run_case(case, load_renal_rules(ROOT / "data/kb/quy_tac_lieu_than.json"))
    base_detail = present_case(case, rule_result, [])
    rule_finding = rule_result.phat_hien[0]
    chunk = _sample_chunk()

    explanation = NhanDinhDeXuat(
        chi_tiet_y_lenh_id=["CT-DEMO02-01"],
        yeu_to=6,
        ket_luan="can_xem",
        muc_do="nghiem_trong",
        nhan_xet="Creatinin 212 umol/L, CrCl 16,0 mL/phút cần hiệu chỉnh liều.",
        ban_ghi_ids=["XN-DEMO02-01"],
        trich_dan=[
            TrichDanNguon(
                doan_trich_id="DT-MERO-01",
                trich_nguyen_van="administer one-half the recommended dose every 12 hours.",
            )
        ],
        de_xuat="Cân nhắc giảm liều theo mức CrCl 10-25 mL/phút.",
        bo_sung_cho_ma_luat=rule_finding.ma_luat,
    )
    verified_ai = NhanDinhDeXuat(
        chi_tiet_y_lenh_id=["CT-DEMO02-01"],
        yeu_to=5,
        ket_luan="can_xem",
        muc_do="can_luu_y",
        nhan_xet="Cần theo dõi độc tính thần kinh khi dùng meropenem ở người suy thận.",
        ban_ghi_ids=["XN-DEMO02-01", "BAN-GHI-KHONG-CO"],
        trich_dan=[
            TrichDanNguon(
                doan_trich_id="DT-MERO-01",
                trich_nguyen_van="administer one-half the recommended dose every 12 hours.",
            )
        ],
        de_xuat="Theo dõi dấu hiệu co giật.",
    )
    unverified_ai = NhanDinhDeXuat(
        chi_tiet_y_lenh_id=["CT-DEMO02-01"],
        yeu_to=4,
        ket_luan="can_xem",
        muc_do="can_luu_y",
        nhan_xet="Dòng chưa kiểm chứng phải bị loại.",
        ban_ghi_ids=["XN-DEMO02-01"],
        trich_dan=[],
    )

    rule_rows = [
        NhanDinhCuoi(
            nguon_goc="luat",
            phat_hien=ph,
            dien_giai=explanation if idx == 0 else None,
        )
        for idx, ph in enumerate(rule_result.phat_hien)
    ]
    llm_out = KetQuaLLM(
        trang_thai="ok",
        nhan_dinh=[
            *rule_rows,
            NhanDinhCuoi(nguon_goc="ai_da_kiem_chung", de_xuat=verified_ai),
            NhanDinhCuoi(
                nguon_goc="ai_chua_kiem_chung",
                de_xuat=unverified_ai,
                loi_kiem_chung=["so_khong_co_nguon:99"],
            ),
        ],
        so_lan_goi=1,
        canh_bao=[],
        phien_ban_prompt="tong_hop.v1",
        mo_hinh="deepseek-flash",
    )
    ai_run = AiRunResult(llm=llm_out, doan=[chunk], canh_bao=[], thoi_gian_ms=123.4)

    presented = present_ai_result(case, rule_result, ai_run, [])

    assert presented.trang_thai == "xong"
    assert presented.nhan_dinh is not None
    attention = presented.nhan_dinh.can_chu_y
    assert len(attention) == 2

    expected_rule = base_detail.nhan_dinh.can_chu_y[0]
    rule_row = attention[0]
    assert rule_row.nhan_dinh_id == expected_rule.nhan_dinh_id
    assert rule_row.ket_luan_ma == expected_rule.ket_luan_ma
    assert rule_row.muc_do_ma == expected_rule.muc_do_ma
    assert rule_row.nguon_goc_ma == "luat"
    assert rule_row.dien_giai_ai == explanation.nhan_xet
    assert rule_row.de_xuat_ai == explanation.de_xuat
    assert rule_row.trich_dan[0].so == 1
    assert rule_row.trich_dan[0].nhan == "Nhãn FDA · Dosage and Administration > Renal Impairment"

    ai_row = attention[1]
    assert ai_row.nhan_dinh_id.startswith("ai|")
    assert ai_row.nguon_goc_ma == "ai_da_kiem_chung"
    assert ai_row.nguon_goc_nhan == "AI · đã kiểm chứng"
    assert ai_row.ma_luat is None
    assert ai_row.dien_giai_ai is None
    assert ai_row.de_xuat_ai == verified_ai.de_xuat
    assert ai_row.can_cu[0].mo_duoc is True
    assert ai_row.can_cu[1].mo_duoc is False
    assert all(row.nguon_goc_ma != "ai_chua_kiem_chung" for row in attention)


def test_present_ai_result_enforces_invariant_1_and_error_states() -> None:
    case = load_case(ROOT / "data/mock/demo/DEMO-02.json")
    rule_result = run_case(case, load_renal_rules(ROOT / "data/kb/quy_tac_lieu_than.json"))
    rule_finding = rule_result.phat_hien[0]

    missing_rule = KetQuaLLM(
        trang_thai="ok",
        nhan_dinh=[],
        so_lan_goi=1,
        canh_bao=[],
        phien_ban_prompt="tong_hop.v1",
        mo_hinh="deepseek-flash",
    )
    res_missing = present_ai_result(
        case,
        rule_result,
        AiRunResult(llm=missing_rule, doan=[], canh_bao=[], thoi_gian_ms=10.0),
    )
    assert res_missing.trang_thai == "loi"
    assert res_missing.nhan_dinh is None
    assert "Kết quả AI không giữ đủ phát hiện của bộ luật, đã bị loại" in res_missing.canh_bao

    altered_finding = rule_finding.model_copy(update={"ket_luan": "dat", "muc_do": "thong_tin"})
    altered_llm = KetQuaLLM(
        trang_thai="ok",
        nhan_dinh=[
            NhanDinhCuoi(nguon_goc="luat", phat_hien=altered_finding),
            *[NhanDinhCuoi(nguon_goc="luat", phat_hien=ph) for ph in rule_result.phat_hien[1:]],
        ],
        so_lan_goi=1,
        canh_bao=[],
        phien_ban_prompt="tong_hop.v1",
        mo_hinh="deepseek-flash",
    )
    res_altered = present_ai_result(
        case,
        rule_result,
        AiRunResult(llm=altered_llm, doan=[], canh_bao=[], thoi_gian_ms=10.0),
    )
    assert res_altered.trang_thai == "loi"
    assert res_altered.nhan_dinh is None

    failed_llm = KetQuaLLM(
        trang_thai="loi_llm",
        nhan_dinh=[NhanDinhCuoi(nguon_goc="luat", phat_hien=rule_finding)],
        so_lan_goi=1,
        canh_bao=["Lỗi kết nối LLM"],
        phien_ban_prompt="tong_hop.v1",
        mo_hinh="deepseek-flash",
    )
    res_failed = present_ai_result(
        case,
        rule_result,
        AiRunResult(llm=failed_llm, doan=[], canh_bao=["Lỗi kết nối LLM"], thoi_gian_ms=10.0),
    )
    assert res_failed.trang_thai == "loi"
    assert res_failed.nhan_dinh is None
    assert res_failed.canh_bao == ["Lỗi kết nối LLM"]
