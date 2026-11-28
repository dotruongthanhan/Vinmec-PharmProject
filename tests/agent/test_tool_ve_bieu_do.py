"""Kiểm thử công cụ minh hoạ qua Gateway."""

import json
import time
from dataclasses import replace
from pathlib import Path
from typing import ClassVar

import pytest
from pydantic import BaseModel, ConfigDict

from app.agent.minh_hoa.models import BoDuLieu, CotDuLieu
from app.agent.tools.base import CanCu, KetQuaCongCu, Tool, ToolContext
from app.agent.tools.gateway import ToolGateway
from app.agent.tools.policy import ChinhSachCongCu
from app.agent.tools.registry import DanhMucCongCu
from app.agent.tools.ve_bieu_do import VeBieuDo
from app.config.settings import TracerSettings
from app.deid.known import GiaTriDinhDanh
from app.deid.session import DeidSession
from app.tracing import Tracer


class Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DataTool(Tool):
    ten: ClassVar[str] = "data_test"
    ten_hien_thi: ClassVar[str] = "Dữ liệu thử"
    mo_ta: ClassVar[str] = "Dữ liệu thử"
    LuocDoThamSo: ClassVar[type[BaseModel]] = Params

    def chay(self, tham_so: BaseModel, ctx: ToolContext) -> KetQuaCongCu:
        return KetQuaCongCu(
            trang_thai="ok",
            noi_dung="Dữ liệu",
            can_cu=[CanCu(ma="tinh:x", loai="tinh", nhan="nguồn")],
            bo_du_lieu=[
                BoDuLieu(
                    ma="",
                    cot=[
                        CotDuLieu(ten="x", kieu="dinh_luong"),
                        CotDuLieu(ten="chu", kieu="danh_muc"),
                    ],
                    dong=[{"x": 1.0, "chu": "Bệnh nhân Giả Lập Sao, 0912345678"}],
                    can_cu=["tinh:x"],
                )
            ],
        )


def setup_gateway(limit: int = 8) -> tuple[ToolGateway, ToolContext]:
    registry = DanhMucCongCu()
    registry.dang_ky(DataTool())
    registry.dang_ky(VeBieuDo())
    policy = ChinhSachCongCu.model_validate(
        {"vai_tro": {"duoc_si_ls": {"cho_phep": ["data_test", "ve_bieu_do"]}}}
    )
    session = DeidSession([GiaTriDinhDanh(loai="TEN", gia_tri="Giả Lập Sao")])
    ctx = ToolContext(
        vai_tro="duoc_si_ls",
        che_do="ca",
        han_chot=time.monotonic() + 30,
        cau_hoi_goc="",
        deid_session=session,
    )
    gateway = ToolGateway(registry, policy, limit)
    assert gateway.goi("data_test", {}, ctx).trang_thai == "ok"
    return gateway, ctx


def spec() -> dict:
    return {
        "phien_ban": "mh-1",
        "tieu_de": "Biểu đồ",
        "lop": [{"dau": "diem", "du_lieu": "ds-1", "ma_hoa": {"x": {"cot": "x"}}}],
        "nguon": ["tinh:x"],
    }


def test_gateway_saves_three_blocks_and_masks_pii() -> None:
    gateway, ctx = setup_gateway()
    for i in range(3):
        description = spec()
        description["lop"][0]["dau"] = ["diem", "chu", "quy_tac"][i]
        result = gateway.goi("ve_bieu_do", {"dac_ta": description}, ctx)
        assert result.trang_thai == "ok"
        assert result.noi_dung.startswith(f"mh-{i + 1}:")
    fourth = spec()
    fourth["lop"][0]["dau"] = "vung"
    result = gateway.goi("ve_bieu_do", {"dac_ta": fourth}, ctx)
    assert result.trang_thai == "tu_choi" and result.noi_dung == "qua_3_khoi"
    block_text = json.dumps([item.model_dump() for item in gateway.minh_hoa], ensure_ascii=False)
    assert "Giả Lập Sao" not in block_text and "0912345678" not in block_text
    assert len(gateway.minh_hoa) == 3


def test_rejection_has_help_and_trace_has_no_spec(tmp_path: Path) -> None:
    gateway, ctx = setup_gateway(limit=2)
    tracer = Tracer(TracerSettings(thu_muc=str(tmp_path), muc_noi_dung="day_du"))
    bad = spec()
    bad["tieu_de"] = "Dấu canary an toàn"
    bad["nguon"] = ["tinh:khac"]
    with tracer.bat_dau_vet("hoi_dap", "agentic") as vet:
        assert vet is not None
        result = gateway.goi("ve_bieu_do", {"dac_ta": bad}, ctx)
        assert result.trang_thai == "tu_choi"
        assert "tinh:x" in result.noi_dung
        assert gateway.goi("ve_bieu_do", {"dac_ta": spec()}, ctx).trang_thai == "ok"
        record = vet.chot()
    tracer.close()
    trace = json.dumps(record.model_dump(mode="json"), ensure_ascii=False)
    assert "Dấu canary an toàn" not in trace
    assert any(s.thuoc_tinh.get("ly_do_tu_choi") == "nguon_khong_hop_le" for s in record.cac_buoc)
    assert "tinh:x" not in trace


def test_two_rejections_block_next_draw() -> None:
    gateway, ctx = setup_gateway()
    bad = spec()
    bad["nguon"] = ["tinh:khac"]
    for _ in range(2):
        assert gateway.goi("ve_bieu_do", {"dac_ta": bad}, ctx).trang_thai == "tu_choi"
    result = gateway.goi("ve_bieu_do", {"dac_ta": spec()}, ctx)
    assert result.ma_loi == "het_luot_ve"
    assert result.noi_dung == "het_luot_ve: không vẽ thêm, hãy trả lời bằng chữ"


def test_rejection_lists_at_most_ten_evidence_codes() -> None:
    gateway, ctx = setup_gateway()
    gateway._ma_can_cu.update(f"tinh:ma_{index:02}" for index in range(15))
    bad = spec()
    bad["nguon"] = ["tinh:khong_co"]
    result = gateway.goi("ve_bieu_do", {"dac_ta": bad}, ctx)
    codes = result.noi_dung.split("mã căn cứ hợp lệ: ", 1)[1].split(", ")
    assert len(codes) == 10
    assert set(codes) <= gateway._ma_can_cu


def test_dataset_summary_includes_its_evidence_code() -> None:
    registry = DanhMucCongCu()
    registry.dang_ky(DataTool())
    policy = ChinhSachCongCu.model_validate(
        {"vai_tro": {"duoc_si_ls": {"cho_phep": ["data_test"]}}}
    )
    ctx = ToolContext(
        vai_tro="duoc_si_ls", che_do="ca", han_chot=time.monotonic() + 30, cau_hoi_goc=""
    )
    result = ToolGateway(registry, policy, 1).goi("data_test", {}, ctx)
    assert "ds-1:" in result.noi_dung
    assert "căn cứ cho nguon: tinh:x" in result.noi_dung


@pytest.mark.parametrize("kind", ["ds", "cot", "so"])
def test_rejection_shows_safe_guidance(kind: str) -> None:
    gateway, ctx = setup_gateway()
    bad = spec()
    if kind == "ds":
        bad["lop"][0]["du_lieu"] = "ds-9"
    elif kind == "cot":
        bad["lop"][0]["ma_hoa"]["x"]["cot"] = "khac"
    else:
        bad["phu_de"] = [{"chu": "CrCl 16"}]
    result = gateway.goi("ve_bieu_do", {"dac_ta": bad}, ctx)
    if kind == "so":
        assert "dùng tham chiếu `o` hoặc `o_theo_khoang`" in result.noi_dung
    else:
        assert "ds-1" in result.noi_dung and "x" in result.noi_dung


def test_success_trace_contains_only_metrics(tmp_path: Path) -> None:
    gateway, ctx = setup_gateway()
    tracer = Tracer(TracerSettings(thu_muc=str(tmp_path), muc_noi_dung="day_du"))
    description = spec()
    description["tieu_de"] = "Canary tiêu đề riêng"
    with tracer.bat_dau_vet("hoi_dap", "agentic") as vet:
        assert vet is not None
        assert gateway.goi("ve_bieu_do", {"dac_ta": description}, ctx).trang_thai == "ok"
        record = vet.chot()
    tracer.close()
    assert "Canary tiêu đề riêng" not in json.dumps(
        record.model_dump(mode="json"), ensure_ascii=False
    )
    tool_span = next(s for s in record.cac_buoc if s.ten == "ve_bieu_do")
    assert tool_span.thuoc_tinh["kieu_dau"] == ["diem"]
    assert tool_span.thuoc_tinh["so_lop"] == 1
    assert tool_span.thuoc_tinh["so_phan_tu"] == 1
    assert tool_span.thuoc_tinh["kich_thuoc_byte"] > 0


def test_timeout_does_not_store_late_result(monkeypatch: pytest.MonkeyPatch) -> None:
    gateway, ctx = setup_gateway()
    original = VeBieuDo.tao

    def slow(*args: object, **kwargs: object) -> object:
        time.sleep(0.15)
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(VeBieuDo, "tao", slow)
    result = gateway.goi(
        "ve_bieu_do", {"dac_ta": spec()}, replace(ctx, han_chot=time.monotonic() + 0.03)
    )
    assert result.ma_loi == "het_gio"
    time.sleep(0.2)
    assert gateway.minh_hoa == []


def test_duplicate_key_order_does_not_spend_rejections() -> None:
    gateway, ctx = setup_gateway()
    original = spec()
    result = gateway.goi("ve_bieu_do", {"dac_ta": original}, ctx)
    assert "Đã có hình mh-1. Không cần vẽ lại; hãy trả lời bằng chữ." in result.noi_dung
    duplicate = dict(reversed(list(spec().items())))
    for _ in range(3):
        result = gateway.goi("ve_bieu_do", {"dac_ta": duplicate}, ctx)
        assert result.trang_thai == "ok"
        assert result.noi_dung == "Đã vẽ ở mh-1, không vẽ lại."
    other = spec()
    other["lop"][0]["dau"] = "chu"
    assert gateway.goi("ve_bieu_do", {"dac_ta": other}, ctx).trang_thai == "ok"
    assert len(gateway.minh_hoa) == 2


def test_different_title_is_a_different_specification() -> None:
    gateway, ctx = setup_gateway()
    assert gateway.goi("ve_bieu_do", {"dac_ta": spec()}, ctx).trang_thai == "ok"
    other = spec()
    other["tieu_de"] = "Tên khác"
    assert gateway.goi("ve_bieu_do", {"dac_ta": other}, ctx).trang_thai == "ok"
    assert len(gateway.minh_hoa) == 2


def test_duplicate_datasets_with_different_ids_are_same_figure() -> None:
    gateway, ctx = setup_gateway()
    first = spec()
    assert gateway.goi("ve_bieu_do", {"dac_ta": first}, ctx).trang_thai == "ok"
    with gateway._lock:
        gateway._bo_du_lieu["ds-2"] = gateway._bo_du_lieu["ds-1"].model_copy(update={"ma": "ds-2"})
    second = spec()
    second["lop"][0]["du_lieu"] = "ds-2"
    result = gateway.goi("ve_bieu_do", {"dac_ta": second}, ctx)
    assert result.trang_thai == "ok"
    assert "mh-1" in result.noi_dung
    assert len(gateway.minh_hoa) == 1
