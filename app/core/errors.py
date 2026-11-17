"""Các lỗi có kiểu của hệ thống."""


class CdssError(Exception):
    """Lỗi gốc của hệ thống hỗ trợ thẩm định."""


class ConfigError(CdssError):
    """Cấu hình thiếu hoặc không hợp lệ."""


class ProviderError(CdssError):
    """Lỗi nhà cung cấp kèm khả năng thử lại."""

    def __init__(self, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class RetrievalError(CdssError):
    """Lỗi lập chỉ mục hoặc truy xuất."""


class VerificationError(CdssError):
    """Lỗi kiểm chứng nhận định."""
