"""Lỗi xác thực cố định, không phản chiếu token hay ngoại lệ gốc."""

from fastapi import HTTPException

_ERRORS = {
    "chua_dang_nhap": (401, "Bạn cần đăng nhập để tiếp tục."),
    "phien_het_han": (401, "Phiên đăng nhập đã hết hạn."),
    "khong_co_quyen": (403, "Bạn không có quyền thực hiện thao tác này."),
    "xac_thuc_khong_san_sang": (503, "Xác thực chưa sẵn sàng. Vui lòng thử lại sau."),
}


class AuthError(HTTPException):
    """Dùng chung trình xử lý lỗi HTTP của API."""

    def __init__(self, code: str = "chua_dang_nhap") -> None:
        status, message = _ERRORS[code]
        super().__init__(status, {"ma": code, "thong_bao": message})
