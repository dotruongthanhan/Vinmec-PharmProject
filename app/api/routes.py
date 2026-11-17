"""Các điểm cuối HTTP theo hợp đồng API v1, bổ sung v1.1 và hỏi đáp v1.2."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request

from app.api import schemas as s
from app.api.auth_schemas import NguoiDung
from app.api.service import CaseService
from app.auth.dependencies import require_online_check, require_role
from app.auth.principal import Principal
from app.auth.roles import ADMIN, CLINICAL_PHARMACIST

router = APIRouter(prefix="/api")
_allowed = require_role(CLINICAL_PHARMACIST, ADMIN)
Caller = Annotated[Principal, Depends(_allowed)]


def _service(request: Request) -> CaseService:
    """Lấy dịch vụ được gắn trên ứng dụng, thuận tiện tiêm khi kiểm thử."""
    return request.app.state.service


@router.get("/health")
def health(request: Request) -> dict[str, object]:
    """Báo tình trạng và chế độ thực tế."""
    return {
        "ok": True,
        "che_do": _service(request).mode(),
        "xac_thuc": request.app.state.auth_settings.auth_mode,
    }


@router.get("/me", response_model=NguoiDung)
def me(principal: Caller) -> NguoiDung:
    """Trả danh tính và vai trò đã được máy chủ kiểm tra."""
    return NguoiDung(
        id=principal.nguoi_dung_id,
        email=principal.email,
        vai_tro=principal.vai_tro,
        phien_id=principal.phien_id,
    )


@router.get("/cases", response_model=s.DanhSachCa)
def list_cases(request: Request, principal: Caller) -> s.DanhSachCa:
    """Trả hàng đợi thẩm định."""
    return _service(request).list_cases()


@router.get("/cases/{ca_id}", response_model=s.ChiTietCa)
def get_case(ca_id: str, request: Request, principal: Caller) -> s.ChiTietCa:
    """Trả chi tiết ca bệnh đã nạp."""
    return _service(request).get_case(ca_id)


@router.get("/cases/{ca_id}/records/{ban_ghi_id}", response_model=s.BanGhi)
def get_record(ca_id: str, ban_ghi_id: str, request: Request, principal: Caller) -> s.BanGhi:
    """Trả bản ghi thuộc ca đang mở."""
    return _service(request).get_record(ca_id, ban_ghi_id)


@router.post(
    "/cases/{ca_id}/feedback",
    response_model=s.PhanHoiDaGhi,
    dependencies=[Depends(require_online_check)],
)
def feedback(ca_id: str, body: s.GuiPhanHoi, request: Request, principal: Caller) -> s.PhanHoiDaGhi:
    """Ghi phản hồi của dược sĩ, là điểm ghi duy nhất."""
    return _service(request).feedback(ca_id, body, principal)


@router.get("/conversations")
def list_conversations(request: Request, principal: Caller) -> dict[str, list[dict[str, object]]]:
    """Đọc lịch sử hội thoại đã lưu theo từng phạm vi (chung và từng ca)."""
    return _service(request).list_conversations(principal)


@router.post("/conversations/{ca_id}/clear")
def clear_conversation(ca_id: str, request: Request, principal: Caller) -> dict[str, bool]:
    """Xoá lịch sử hội thoại của một phạm vi."""
    _service(request).clear_conversation(ca_id, principal)
    return {"ok": True}


@router.post("/ask", response_model=s.TraLoi)
def ask_global(body: s.GuiCauHoi, request: Request, principal: Caller) -> s.TraLoi:
    """Trả lời câu hỏi chung trên toàn bộ danh sách y lệnh và kho tài liệu."""
    return _service(request).ask("__global__", body, principal)


@router.post("/cases/{ca_id}/ask", response_model=s.TraLoi)
def ask(ca_id: str, body: s.GuiCauHoi, request: Request, principal: Caller) -> s.TraLoi:
    """Trả lời câu hỏi theo ca bệnh đang mở dựa trên hồ sơ và tài liệu."""
    return _service(request).ask(ca_id, body, principal)


@router.post("/cases/{ca_id}/ai", response_model=s.KetQuaAI)
def start_ai(
    ca_id: str,
    request: Request,
    principal: Caller,
    body: Annotated[s.ChayAI | None, Body()] = None,
) -> s.KetQuaAI:
    """Khởi động phân tích AI nền cho một ca hoặc trả trạng thái hiện có."""
    return _service(request).start_ai(ca_id, restart=body.chay_lai if body is not None else False)


@router.get("/cases/{ca_id}/ai", response_model=s.KetQuaAI)
def get_ai(ca_id: str, request: Request, principal: Caller) -> s.KetQuaAI:
    """Chỉ đọc trạng thái phân tích AI hiện tại của ca bệnh."""
    return _service(request).get_ai(ca_id)


@router.get("/cases/{ca_id}/sources/{doan_trich_id}", response_model=s.DoanNguon)
def get_source(ca_id: str, doan_trich_id: str, request: Request, principal: Caller) -> s.DoanNguon:
    """Trả nguyên văn đoạn nguồn đã cấp cho ca bệnh trong lần phân tích gần nhất."""
    return _service(request).get_source(ca_id, doan_trich_id)
