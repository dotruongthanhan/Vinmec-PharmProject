"""Các điểm cuối HTTP theo hợp đồng API v1, bổ sung v1.1 và hỏi đáp v1.2."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Request, Response

from app.api import formulas, lookup
from app.api import schemas as s
from app.api.auth_schemas import NguoiDung
from app.api.service import CaseService
from app.auth.dependencies import require_role, revoke_current_session
from app.auth.principal import Principal
from app.auth.roles import ADMIN, CLINICAL_PHARMACIST

router = APIRouter(prefix="/api")
_allowed = require_role(CLINICAL_PHARMACIST, ADMIN)
Caller = Annotated[Principal, Depends(_allowed)]
Writer = Annotated[Principal, Depends(require_role(CLINICAL_PHARMACIST, ADMIN, strict=True))]
LogoutCaller = Annotated[Principal, Depends(require_role(CLINICAL_PHARMACIST, ADMIN, online=False))]


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


@router.post("/dang-xuat")
def sign_out(request: Request, principal: LogoutCaller) -> dict[str, bool]:
    """Thu hồi phiên hiện tại trước khi phía web đăng xuất Supabase."""
    revoke_current_session(request, principal)
    return {"ok": True}


@router.get("/cases", response_model=s.DanhSachCa)
def list_cases(request: Request, response: Response, principal: Caller) -> s.DanhSachCa:
    """Trả hàng đợi thẩm định."""
    response.headers["Cache-Control"] = "private, no-store"
    return _service(request).list_cases()


@router.get("/cases/{ca_id}", response_model=s.ChiTietCa)
def get_case(ca_id: str, request: Request, response: Response, principal: Caller) -> s.ChiTietCa:
    """Trả chi tiết ca bệnh đã nạp."""
    response.headers["Cache-Control"] = "private, no-store"
    return _service(request).get_case(ca_id)


@router.get("/cases/{ca_id}/lich-su-tham-dinh", response_model=s.LichSuThamDinh)
def get_review_history(
    ca_id: str, request: Request, response: Response, principal: Caller
) -> s.LichSuThamDinh:
    """Trả danh sách các lần hệ thống đã thẩm định và lưu cho ca bệnh."""
    response.headers["Cache-Control"] = "private, no-store"
    return _service(request).list_review_history(ca_id)


@router.get("/cases/{ca_id}/records/{ban_ghi_id}", response_model=s.BanGhi)
def get_record(ca_id: str, ban_ghi_id: str, request: Request, principal: Caller) -> s.BanGhi:
    """Trả bản ghi thuộc ca đang mở."""
    return _service(request).get_record(ca_id, ban_ghi_id)


@router.post(
    "/cases/{ca_id}/feedback",
    response_model=s.PhanHoiDaGhi,
)
def feedback(ca_id: str, body: s.GuiPhanHoi, request: Request, principal: Writer) -> s.PhanHoiDaGhi:
    """Ghi phản hồi của dược sĩ, là điểm ghi duy nhất."""
    return _service(request).feedback(ca_id, body, principal)


@router.get("/conversations")
def list_conversations(request: Request, principal: Caller) -> dict[str, list[dict[str, object]]]:
    """Đọc lịch sử hội thoại đã lưu theo từng phạm vi (chung và từng ca)."""
    return _service(request).list_conversations(principal)


@router.post("/conversations/{ca_id}/clear")
def clear_conversation(ca_id: str, request: Request, principal: Writer) -> dict[str, bool]:
    """Xoá lịch sử hội thoại của một phạm vi."""
    _service(request).clear_conversation(ca_id, principal)
    return {"ok": True}


@router.get("/ask/tien-trinh", response_model=s.TienTrinhHoiDap)
def get_global_ask_progress(
    request: Request, response: Response, principal: Caller
) -> s.TienTrinhHoiDap:
    """Đọc tiến trình câu hỏi chung đang xử lý hoặc vừa xong của chính người gọi."""
    response.headers["Cache-Control"] = "private, no-store"
    return _service(request).get_ask_progress("__global__", principal)


@router.post("/ask", response_model=s.TraLoi)
def ask_global(body: s.GuiCauHoi, request: Request, principal: Writer) -> s.TraLoi:
    """Trả lời câu hỏi chung trên toàn bộ danh sách y lệnh và kho tài liệu."""
    return _service(request).ask("__global__", body, principal)


@router.get("/cases/{ca_id}/ask/tien-trinh", response_model=s.TienTrinhHoiDap)
def get_case_ask_progress(
    ca_id: Annotated[str, Path(min_length=1, max_length=128)],
    request: Request,
    response: Response,
    principal: Caller,
) -> s.TienTrinhHoiDap:
    """Đọc tiến trình hỏi đáp theo ca đang xử lý hoặc vừa xong của chính người gọi."""
    response.headers["Cache-Control"] = "private, no-store"
    return _service(request).get_ask_progress(ca_id, principal)


@router.post("/cases/{ca_id}/ask", response_model=s.TraLoi)
def ask(ca_id: str, body: s.GuiCauHoi, request: Request, principal: Writer) -> s.TraLoi:
    """Trả lời câu hỏi theo ca bệnh đang mở dựa trên hồ sơ và tài liệu."""
    return _service(request).ask(ca_id, body, principal)


@router.post("/cases/{ca_id}/ai", response_model=s.KetQuaAI)
def start_ai(
    ca_id: str,
    request: Request,
    principal: Writer,
    body: Annotated[s.ChayAI | None, Body()] = None,
) -> s.KetQuaAI:
    """Khởi động phân tích AI nền cho một ca hoặc trả trạng thái hiện có."""
    return _service(request).start_ai(
        ca_id,
        restart=body.chay_lai if body is not None else False,
        principal=principal,
    )


@router.get("/cases/{ca_id}/ai", response_model=s.KetQuaAI)
def get_ai(ca_id: str, request: Request, principal: Caller) -> s.KetQuaAI:
    """Chỉ đọc trạng thái phân tích AI hiện tại của ca bệnh."""
    return _service(request).get_ai(ca_id)


@router.get("/cases/{ca_id}/sources/{doan_trich_id}", response_model=s.DoanNguon)
def get_source(ca_id: str, doan_trich_id: str, request: Request, principal: Caller) -> s.DoanNguon:
    """Trả nguyên văn đoạn nguồn đã cấp cho ca bệnh trong lần phân tích gần nhất."""
    return _service(request).get_source(ca_id, doan_trich_id, principal)


@router.get("/thuoc", response_model=s.DanhSachThuoc)
def search_drugs(
    response: Response,
    principal: Caller,
    q: Annotated[str | None, Query(max_length=100)] = None,
    trang: Annotated[int, Query(ge=1, le=10000)] = 1,
    so_dong: Annotated[int, Query(ge=1, le=100)] = 30,
) -> s.DanhSachThuoc:
    """Tìm hoạt chất theo tên thuốc, hoạt chất hoặc đồng nghĩa (không dấu)."""
    response.headers["Cache-Control"] = "private, no-store"
    return lookup.search_drugs(q, trang, so_dong)


@router.get("/thuoc/goi-y", response_model=s.KetQuaGoiYThuoc)
def suggest_drugs(
    response: Response,
    principal: Caller,
    q: Annotated[str, Query(max_length=100)],
    gioi_han: Annotated[int, Query(ge=1, le=15)] = 8,
) -> s.KetQuaGoiYThuoc:
    """Gợi ý tên thuốc khi gõ (hoạt chất, đồng nghĩa, biệt dược); không ghi q vào nhật ký."""
    response.headers["Cache-Control"] = "private, no-store"
    return lookup.suggest_drugs(q, gioi_han)


@router.get("/thuoc/{hoat_chat_id}", response_model=s.ChiTietThuoc)
def drug_detail(hoat_chat_id: str, response: Response, principal: Caller) -> s.ChiTietThuoc:
    """Toàn bộ thông tin tra cứu của một hoạt chất, mỗi phần ghi nguồn."""
    response.headers["Cache-Control"] = "private, no-store"
    return lookup.drug_detail(hoat_chat_id)


@router.post("/tuong-tac", response_model=s.KetQuaTraTuongTac)
def lookup_interactions(
    body: s.TraTuongTacYeuCau, response: Response, principal: Caller
) -> s.KetQuaTraTuongTac:
    """Tra tương tác thủ công giữa các tên thuốc tự do; chỉ đọc, không lưu."""
    response.headers["Cache-Control"] = "private, no-store"
    return lookup.lookup_interactions(body.thuoc)


@router.get("/cong-thuc", response_model=s.DanhMucCongThuc)
def list_formulas(response: Response, principal: Caller) -> s.DanhMucCongThuc:
    """Danh mục công thức lâm sàng đã cài."""
    response.headers["Cache-Control"] = "private, no-store"
    return formulas.list_formulas()


@router.post("/cong-thuc/{ma}", response_model=s.KetQuaCongThuc)
def calculate_formula(
    ma: str, body: s.TinhCongThucYeuCau, response: Response, principal: Caller
) -> s.KetQuaCongThuc:
    """Tính một công thức bằng hàm đã cài và kiểm; không dùng LLM."""
    response.headers["Cache-Control"] = "private, no-store"
    return formulas.calculate(ma, body.dau_vao)
