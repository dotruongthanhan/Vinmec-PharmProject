"""Các điểm cuối HTTP cho dịch vụ Chrome Extension độc lập (hợp đồng v1.10)."""

from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    UploadFile,
)
from pydantic import ValidationError

from app.api import lookup
from app.api import schemas as core_s
from app.api.auth_schemas import NguoiDung
from app.auth.dependencies import require_role
from app.auth.principal import Principal
from app.auth.roles import ADMIN, CLINICAL_PHARMACIST
from app.extension_api import schemas as ext_s
from app.extension_api.service import ExtensionService, validate_image_bytes

router = APIRouter(prefix="/api/extension")
_allowed = require_role(CLINICAL_PHARMACIST, ADMIN)
Caller = Annotated[Principal, Depends(_allowed)]
Writer = Annotated[Principal, Depends(require_role(CLINICAL_PHARMACIST, ADMIN, strict=True))]


def _service(request: Request) -> ExtensionService:
    """Lấy thể hiện ExtensionService gắn trên ứng dụng."""
    return request.app.state.extension_service


@router.get("/health", response_model=ext_s.ExtensionHealthResponse)
def health(request: Request) -> ext_s.ExtensionHealthResponse:
    """Trả tình trạng dịch vụ Extension và cấu hình mô hình trích xuất."""
    return _service(request).health()


@router.get("/me", response_model=NguoiDung)
def me(principal: Caller) -> NguoiDung:
    """Trả thông tin tài khoản dược sĩ đang đăng nhập qua Supabase JWT."""
    return NguoiDung(
        id=principal.nguoi_dung_id,
        email=principal.email,
        vai_tro=principal.vai_tro,
        phien_id=principal.phien_id,
    )


@router.post("/classify-schema", response_model=ext_s.ClassifySchemaResponse)
def classify_schema(
    body: ext_s.ClassifySchemaRequest,
    request: Request,
    response: Response,
    principal: Writer,
) -> ext_s.ClassifySchemaResponse:
    """Phân loại tên nhãn DOM (tuyệt đối không gửi giá trị người bệnh)."""
    response.headers["Cache-Control"] = "private, no-store"
    return _service(request).classify_schema(body, principal)


@router.post("/extract-and-review", response_model=ext_s.ExtensionReviewResponse)
async def extract_and_review(
    request: Request,
    response: Response,
    principal: Writer,
    emr_json: Annotated[str, Form(max_length=180_000)],
    oh_crop_confirmed: Annotated[bool, Form()] = False,
    oh_image: Annotated[UploadFile | None, File()] = None,
) -> ext_s.ExtensionReviewResponse:
    """Nhận văn bản EMR đã che PII + ảnh OH (tuỳ chọn), trích xuất song song & thẩm định ngay."""
    response.headers["Cache-Control"] = "private, no-store"
    svc = _service(request)
    try:
        emr_payload = ext_s.ExtractEmrPayload.model_validate_json(emr_json)
    except ValidationError as exc:
        raise HTTPException(
            422,
            f"Dữ liệu emr_json không hợp lệ: {exc.errors(include_input=False)[0]['msg']}",
        ) from None

    image_bytes: bytes | None = None
    image_mime: str | None = None
    if oh_image is not None:
        if not oh_crop_confirmed:
            raise HTTPException(
                422,
                "Cần xác nhận đã cắt bỏ phần thông tin hành chính khỏi ảnh OH trước khi phân tích.",
            )
        max_bytes = svc.settings.limits.max_oh_image_bytes
        raw = await oh_image.read(max_bytes + 1)
        image_mime = validate_image_bytes(raw, max_bytes=max_bytes)
        image_bytes = raw

    return svc.extract_and_review(
        emr_payload=emr_payload,
        oh_image_bytes=image_bytes,
        oh_image_mime=image_mime,
        principal=principal,
    )


@router.post("/sessions/{session_id}/recalc", response_model=ext_s.ExtensionReviewResponse)
def recalc(
    session_id: Annotated[str, Path(min_length=4, max_length=128)],
    body: ext_s.RecalcRequest,
    request: Request,
    response: Response,
    principal: Writer,
) -> ext_s.ExtensionReviewResponse:
    """Sửa nhanh dữ liệu lâm sàng hoặc dòng thuốc trong RAM và chạy lại bộ luật (<50 ms)."""
    response.headers["Cache-Control"] = "private, no-store"
    return _service(request).recalc(session_id, body, principal)


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: Annotated[str, Path(min_length=4, max_length=128)],
    request: Request,
    principal: Writer,
) -> dict[str, bool]:
    """Xoá sạch phiên tạm thời khỏi RAM."""
    _service(request).delete_session(session_id, principal)
    return {"ok": True}


@router.post("/sessions/{session_id}/ai", response_model=core_s.KetQuaAI)
def start_ai(
    session_id: Annotated[str, Path(min_length=4, max_length=128)],
    request: Request,
    response: Response,
    principal: Writer,
    body: Annotated[core_s.ChayAI | None, Body()] = None,
) -> core_s.KetQuaAI:
    """Khởi động hoặc đọc trạng thái tác vụ AI (deepseek-flash + openFDA)."""
    response.headers["Cache-Control"] = "private, no-store"
    return _service(request).start_ai(
        session_id,
        restart=body.chay_lai if body is not None else False,
        principal=principal,
    )


@router.get("/sessions/{session_id}/ai", response_model=core_s.KetQuaAI)
def get_ai(
    session_id: Annotated[str, Path(min_length=4, max_length=128)],
    request: Request,
    response: Response,
    principal: Caller,
) -> core_s.KetQuaAI:
    """Đọc tiến trình và kết quả phân tích AI nền của phiên."""
    response.headers["Cache-Control"] = "private, no-store"
    return _service(request).get_ai(session_id, principal)


@router.post("/sessions/{session_id}/ask", response_model=core_s.TraLoi)
def ask(
    session_id: Annotated[str, Path(min_length=4, max_length=128)],
    body: core_s.GuiCauHoi,
    request: Request,
    response: Response,
    principal: Writer,
) -> core_s.TraLoi:
    """Đặt câu hỏi chuyên sâu dựa trên bối cảnh phiên tạm và kho tri thức công khai."""
    response.headers["Cache-Control"] = "private, no-store"
    return _service(request).ask(session_id, body, principal)


@router.get("/sessions/{session_id}/ask-progress", response_model=core_s.TienTrinhHoiDap)
def get_ask_progress(
    session_id: Annotated[str, Path(min_length=4, max_length=128)],
    request: Request,
    response: Response,
    principal: Caller,
) -> core_s.TienTrinhHoiDap:
    """Đọc tiến trình hỏi đáp thời gian thực cho phiên."""
    response.headers["Cache-Control"] = "private, no-store"
    return _service(request).get_ask_progress(session_id, principal)


@router.get("/sessions/{session_id}/sources/{doan_trich_id}", response_model=core_s.DoanNguon)
def get_source(
    session_id: Annotated[str, Path(min_length=4, max_length=128)],
    doan_trich_id: Annotated[str, Path(min_length=1, max_length=160)],
    request: Request,
    response: Response,
    principal: Caller,
) -> core_s.DoanNguon:
    """Xem nguyên văn đoạn trích nguồn FDA/BYT đã cấp cho phiên."""
    response.headers["Cache-Control"] = "private, no-store"
    return _service(request).get_source(session_id, doan_trich_id, principal)


@router.get("/lookup/drugs", response_model=core_s.DanhSachThuoc)
def search_drugs(
    response: Response,
    principal: Caller,
    q: Annotated[str | None, Query(max_length=100)] = None,
    trang: Annotated[int, Query(ge=1, le=10000)] = 1,
    so_dong: Annotated[int, Query(ge=1, le=100)] = 30,
) -> core_s.DanhSachThuoc:
    """Tra cứu danh mục thuốc công khai (chỉ đọc tri_thuc)."""
    del principal
    response.headers["Cache-Control"] = "private, no-store"
    return lookup.search_drugs(q, trang, so_dong)


@router.get("/lookup/drugs/suggest", response_model=core_s.KetQuaGoiYThuoc)
def suggest_drugs(
    response: Response,
    principal: Caller,
    q: Annotated[str, Query(max_length=100)],
    gioi_han: Annotated[int, Query(ge=1, le=15)] = 8,
) -> core_s.KetQuaGoiYThuoc:
    """Gợi ý tên thuốc khi gõ."""
    del principal
    response.headers["Cache-Control"] = "private, no-store"
    return lookup.suggest_drugs(q, gioi_han)


@router.get("/lookup/drugs/{hoat_chat_id}", response_model=core_s.ChiTietThuoc)
def drug_detail(
    hoat_chat_id: Annotated[str, Path(min_length=1, max_length=128)],
    response: Response,
    principal: Caller,
) -> core_s.ChiTietThuoc:
    """Tra chi tiết một hoạt chất từ kho công khai."""
    del principal
    response.headers["Cache-Control"] = "private, no-store"
    return lookup.drug_detail(hoat_chat_id)


@router.post("/lookup/interactions", response_model=core_s.KetQuaTraTuongTac)
def lookup_interactions(
    body: core_s.TraTuongTacYeuCau,
    response: Response,
    principal: Caller,
) -> core_s.KetQuaTraTuongTac:
    """Tra ma trận tương tác DDInter công khai."""
    del principal
    response.headers["Cache-Control"] = "private, no-store"
    return lookup.lookup_interactions(body.thuoc)
