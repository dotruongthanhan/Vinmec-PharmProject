"""Danh mục đăng ký công cụ và xuất mô tả lược đồ cho LLM."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel

from app.agent.tools.base import Tool


class DanhMucCongCu:
    """Sổ đăng ký tập trung các công cụ hợp lệ theo tên duy nhất."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def dang_ky(self, tool: Tool) -> None:
        """Đăng ký một công cụ sau khi kiểm tra tên, extra='forbid' và cấm tham số ca_id."""
        if not tool.ten:
            raise ValueError("Tên công cụ không được rỗng")
        if tool.ten in self._tools:
            raise ValueError(f"Trùng tên công cụ: {tool.ten}")
        schema_cls = getattr(tool, "LuocDoThamSo", None)
        if not (isinstance(schema_cls, type) and issubclass(schema_cls, BaseModel)):
            raise ValueError(f"LuocDoThamSo của {tool.ten} phải là lớp Pydantic BaseModel")
        if schema_cls.model_config.get("extra") != "forbid":
            raise ValueError(f"LuocDoThamSo của {tool.ten} phải đặt extra='forbid'")
        if "ca_id" in schema_cls.model_fields:
            raise ValueError(f"LuocDoThamSo của {tool.ten} không được chứa trường ca_id")
        self._tools[tool.ten] = tool

    def lay(self, ten: str) -> Tool | None:
        """Lấy thực thể công cụ theo tên, trả None nếu chưa đăng ký."""
        return self._tools.get(ten)

    def ten_da_dang_ky(self) -> list[str]:
        """Danh sách tên công cụ đã đăng ký theo đúng thứ tự đăng ký."""
        return list(self._tools.keys())

    def mo_ta_cho_llm(self, cac_ten: Sequence[str]) -> list[dict[str, Any]]:
        """Xuất danh sách mô tả và JSON schema chỉ cho các tên được yêu cầu và đã đăng ký."""
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for ten in cac_ten:
            if ten in seen:
                continue
            tool = self._tools.get(ten)
            if tool is None:
                continue
            seen.add(ten)
            result.append(
                {
                    "ten": tool.ten,
                    "mo_ta": tool.mo_ta,
                    "tham_so": tool.LuocDoThamSo.model_json_schema(),
                }
            )
        return result
