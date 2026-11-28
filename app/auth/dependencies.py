"""Phụ thuộc xác thực và phân quyền FastAPI."""

import logging
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request

from app.auth.errors import AuthError
from app.auth.principal import Principal
from app.auth.revocation import session_key
from app.auth.roles import ADMIN, VALID_ROLES

_logger = logging.getLogger(__name__)


def _bearer(request: Request) -> str:
    """Từ chối tiêu đề thiếu, lặp hoặc sai dạng."""
    values = request.headers.getlist("authorization")
    parts = values[0].split() if len(values) == 1 else []
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthError()
    return parts[1]


def _authenticate(request: Request, *, strict: bool = False, online: bool = True) -> Principal:
    """Lấy danh tính hoặc danh tính phát triển khi đã tắt xác thực rõ ràng."""
    if request.app.state.auth_settings.auth_mode == "off":
        principal = Principal(nguoi_dung_id="dev-local", vai_tro=ADMIN)
        request.state.principal = principal
        return principal
    if not request.app.state.auth_settings.supabase_url:
        raise AuthError("xac_thuc_khong_san_sang")
    try:
        token = _bearer(request)
        principal = request.app.state.auth.verify(token)
        if request.app.state.revocations.contains(session_key(principal, token)):
            raise AuthError()
        request.state.principal = principal
    except AuthError:
        raise
    except Exception:
        raise AuthError() from None
    if online:
        try:
            role = request.app.state.auth.online_check(token)
        except Exception as exc:
            unavailable = not isinstance(exc, AuthError) or exc.status_code == 503
            if not unavailable:
                raise
            if strict:
                raise AuthError("xac_thuc_khong_san_sang") from None
            _logger.warning("Kiểm xác thực trực tuyến không sẵn sàng; tạm dùng vai trò trong JWT.")
        else:
            if not isinstance(role, str) or role not in VALID_ROLES:
                raise AuthError("khong_co_quyen")
            principal = principal.model_copy(update={"vai_tro": role})
            request.state.principal = principal
    return principal


def current_principal(request: Request) -> Principal:
    """Kiểm trực tuyến cho điểm cuối đọc, cho phép tạm dùng JWT khi lỗi dịch vụ."""
    return _authenticate(request)


def _strict_principal(request: Request) -> Principal:
    """Thao tác ghi từ chối khi không kiểm được trực tuyến."""
    return _authenticate(request, strict=True)


def _logout_principal(request: Request) -> Principal:
    """Đăng xuất vẫn hoạt động khi Supabase không sẵn sàng."""
    return _authenticate(request, online=False)


def require_role(
    *roles: str, strict: bool = False, online: bool = True
) -> Callable[..., Principal]:
    """Tạo phụ thuộc giới hạn vai trò cho từng điểm cuối."""

    dependency = (
        _logout_principal if not online else _strict_principal if strict else current_principal
    )

    def check(principal: Annotated[Principal, Depends(dependency)]) -> Principal:
        if principal.vai_tro not in roles:
            raise AuthError("khong_co_quyen")
        return principal

    return check


def revoke_current_session(request: Request, principal: Principal) -> None:
    """Chặn phiên đã xác thực, bỏ qua hoàn toàn trong chế độ phát triển."""
    if request.app.state.auth_settings.auth_mode == "off":
        return
    if principal.het_han_luc is None:
        raise AuthError()
    request.app.state.revocations.revoke(
        session_key(principal, _bearer(request)), principal.het_han_luc
    )
