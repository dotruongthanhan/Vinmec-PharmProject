"""Phụ thuộc xác thực và phân quyền FastAPI."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request

from app.auth.errors import AuthError
from app.auth.principal import Principal
from app.auth.roles import ADMIN


def _bearer(request: Request) -> str:
    """Từ chối tiêu đề thiếu, lặp hoặc sai dạng."""
    values = request.headers.getlist("authorization")
    parts = values[0].split() if len(values) == 1 else []
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthError()
    return parts[1]


def current_principal(request: Request) -> Principal:
    """Lấy danh tính hoặc danh tính phát triển khi đã tắt xác thực rõ ràng."""
    if request.app.state.auth_settings.auth_mode == "off":
        principal = Principal(nguoi_dung_id="dev-local", vai_tro=ADMIN)
        request.state.principal = principal
        return principal
    if not request.app.state.auth_settings.supabase_url:
        raise AuthError("xac_thuc_khong_san_sang")
    try:
        principal = request.app.state.auth.verify(_bearer(request))
        request.state.principal = principal
        return principal
    except AuthError:
        raise
    except Exception:
        raise AuthError() from None


def require_role(*roles: str) -> Callable[..., Principal]:
    """Tạo phụ thuộc giới hạn vai trò cho từng điểm cuối."""

    def check(principal: Annotated[Principal, Depends(current_principal)]) -> Principal:
        if principal.vai_tro not in roles:
            raise AuthError("khong_co_quyen")
        return principal

    return check


def require_online_check(
    request: Request, principal: Annotated[Principal, Depends(current_principal)]
) -> Principal:
    """Kiểm thu hồi trước thao tác ghi, mặc định từ chối ngoại lệ bất ngờ."""
    if request.app.state.auth_settings.auth_mode != "off":
        try:
            request.app.state.auth.online_check(_bearer(request))
        except AuthError:
            raise
        except Exception:
            raise AuthError("xac_thuc_khong_san_sang") from None
    return principal
