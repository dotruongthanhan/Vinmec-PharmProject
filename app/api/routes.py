"""Các điểm cuối HTTP theo hợp đồng API v1, bổ sung v1.1 và hỏi đáp v1.2."""

from typing import Annotated

from fastapi import APIRouter, Body, Request

from app.api import schemas as s
from app.api.service import CaseService

router = APIRouter(prefix="/api")


def _service(request: Request) -> CaseService:
    """Lấy dịch vụ được gắn trên ứng dụng, thuận tiện tiêm khi kiểm thử."""
    return request.app.state.service


@router.get("/health")
def health(request: Request) -> dict[str, object]:
    """Báo tình trạng và chế độ thực tế."""
    return {"ok": True, "che_do": _service(request).mode()}


@router.get("/cases", response_model=s.DanhSachCa)
def list_cases(request: Request) -> s.DanhSachCa:
    """Trả hàng đợi thẩm định."""
    return _service(request).list_cases()


@router.get("/cases/{ca_id}", response_model=s.ChiTietCa)
def get_case(ca_id: str, request: Request) -> s.ChiTietCa:
    """Trả chi tiết ca bệnh đã nạp."""
    return _service(request).get_case(ca_id)


@router.get("/cases/{ca_id}/records/{ban_ghi_id}", response_model=s.BanGhi)
def get_record(ca_id: str, ban_ghi_id: str, request: Request) -> s.BanGhi:
    """Trả bản ghi thuộc ca đang mở."""
    return _service(request).get_record(ca_id, ban_ghi_id)


@router.post("/cases/{ca_id}/feedback", response_model=s.PhanHoiDaGhi)
def feedback(ca_id: str, body: s.GuiPhanHoi, request: Request) -> s.PhanHoiDaGhi:
    """Ghi phản hồi của dược sĩ, là điểm ghi duy nhất."""
    return _service(request).feedback(ca_id, body)


@router.post("/cases/{ca_id}/ask", response_model=s.TraLoi)
def ask(ca_id: str, body: s.GuiCauHoi, request: Request) -> s.TraLoi:
    """Trả lời câu hỏi theo ca bệnh đang mở dựa trên hồ sơ và tài liệu."""
    return _service(request).ask(ca_id, body)


@router.post("/cases/{ca_id}/ai", response_model=s.KetQuaAI)
def start_ai(
    ca_id: str,
    request: Request,
    body: Annotated[s.ChayAI | None, Body()] = None,
) -> s.KetQuaAI:
    """Khởi động phân tích AI nền cho một ca hoặc trả trạng thái hiện có."""
    return _service(request).start_ai(ca_id, restart=body.chay_lai if body is not None else False)


@router.get("/cases/{ca_id}/ai", response_model=s.KetQuaAI)
def get_ai(ca_id: str, request: Request) -> s.KetQuaAI:
    """Chỉ đọc trạng thái phân tích AI hiện tại của ca bệnh."""
    return _service(request).get_ai(ca_id)


@router.get("/cases/{ca_id}/sources/{doan_trich_id}", response_model=s.DoanNguon)
def get_source(ca_id: str, doan_trich_id: str, request: Request) -> s.DoanNguon:
    """Trả nguyên văn đoạn nguồn đã cấp cho ca bệnh trong lần phân tích gần nhất."""
    return _service(request).get_source(ca_id, doan_trich_id)
