"""Tải và truy vấn bảng dị ứng chéo theo nhóm hoạt chất."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.kb.names import normalize_key

CROSS_RISK_LEVEL = Literal["cao", "thap", "rat_thap"]
CROSS_RISK_ORDER: dict[CROSS_RISK_LEVEL, int] = {
    "cao": 3,
    "thap": 2,
    "rat_thap": 1,
}

_DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "kb" / "di_ung_cheo.json"
)
_PAREN_RE = re.compile(r"\([^)]*\)")


def strip_parenthetical(text: str) -> str:
    """Loại bỏ phần chú thích trong ngoặc đơn và gộp khoảng trắng thừa."""
    without_parens = _PAREN_RE.sub(" ", text)
    return " ".join(without_parens.split())


class CrossSource(BaseModel):
    """Nguồn trích dẫn của một nhóm trong bảng dị ứng chéo."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    loai: str
    muc_nhan: str | None = None
    ten_nhan: str | None = None
    set_id: str | None = None
    tieu_de: str | None = None
    nam: int | None = None
    pmid: str | None = None
    doi: str | None = None
    trich_nguyen_van: str
    url: str


class RelatedIngredientGroup(BaseModel):
    """Nhóm hoạt chất liên quan và mức nguy cơ dị ứng chéo."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    hoat_chat_ids: tuple[str, ...]
    muc_cheo: CROSS_RISK_LEVEL
    muc_canh_bao_nhan: str | None = None
    ly_do: str


class AllergyCrossGroup(BaseModel):
    """Một quy tắc nhóm trong bảng dị ứng chéo."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    ma_nhom: str
    ten_nhom: str
    hoat_chat_ids: tuple[str, ...]
    hoat_chat_lien_quan: tuple[RelatedIngredientGroup, ...]
    huong: Literal["hai_chieu", "mot_chieu"]
    co_so: str | None = None
    nguon: tuple[CrossSource, ...]
    ghi_chu: str | None = None
    trang_thai: str | None = None


class GroupAlias(BaseModel):
    """Ánh xạ tên nhóm dị ứng ghi trên hồ sơ sang tập hoạt chất đại diện."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    hoat_chat_ids: tuple[str, ...]
    ma_nhom: str


class CrossMatch(BaseModel):
    """Một kết quả khớp cặp dị ứng – y lệnh theo bảng dị ứng chéo."""

    model_config = ConfigDict(frozen=True)

    group: AllergyCrossGroup
    related: RelatedIngredientGroup
    allergen_id: str
    order_id: str


class AllergyCrossConfig(BaseModel):
    """Cấu hình đầy đủ của bảng dị ứng chéo."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    ten: str
    phien_ban: str
    trang_thai: str
    ten_nhom_di_ung_sang_hoat_chat: dict[str, GroupAlias]
    nhom: tuple[AllergyCrossGroup, ...]

    def resolve_group_alias(self, name: str) -> GroupAlias | None:
        """Tìm ánh xạ nhóm dị ứng theo tên đã chuẩn hoá, bỏ dấu và viết thường."""
        normalized_map = {
            normalize_key(alias_name): alias
            for alias_name, alias in self.ten_nhom_di_ung_sang_hoat_chat.items()
        }
        candidates = [name]
        stripped = strip_parenthetical(name)
        if stripped and stripped != name:
            candidates.append(stripped)

        for candidate in candidates:
            key = normalize_key(candidate)
            if not key:
                continue
            if key in normalized_map:
                return normalized_map[key]
            if len(key) > 3 and key.endswith("s") and key[:-1] in normalized_map:
                return normalized_map[key[:-1]]
        return None

    def find_cross_matches(
        self,
        allergen_ids: set[str],
        order_ids: set[str],
        alias: GroupAlias | None = None,
    ) -> list[CrossMatch]:
        """Tìm tất cả nhóm chéo khớp giữa hoạt chất dị ứng và hoạt chất y lệnh."""
        if not allergen_ids or not order_ids:
            return []

        sorted_allergens = sorted(allergen_ids)
        sorted_orders = sorted(order_ids)
        indexed_matches: list[tuple[tuple[int, int, int], CrossMatch]] = []

        for idx, group in enumerate(self.nhom):
            same_alias_group = alias is not None and group.ma_nhom == alias.ma_nhom
            primary = set(group.hoat_chat_ids)
            for rel_idx, rel in enumerate(group.hoat_chat_lien_quan):
                related = set(rel.hoat_chat_ids)
                matched_pair: tuple[str, str] | None = None
                for allergen_id in sorted_allergens:
                    for order_id in sorted_orders:
                        if not same_alias_group and allergen_id == order_id:
                            continue
                        forward = allergen_id in primary and order_id in related
                        backward = (
                            group.huong == "hai_chieu"
                            and allergen_id in related
                            and order_id in primary
                        )
                        if forward or backward:
                            matched_pair = (allergen_id, order_id)
                            break
                    if matched_pair is not None:
                        break
                if matched_pair is None:
                    continue
                rank = (
                    -CROSS_RISK_ORDER[rel.muc_cheo],
                    0 if same_alias_group else 1,
                    idx * 100 + rel_idx,
                )
                indexed_matches.append(
                    (
                        rank,
                        CrossMatch(
                            group=group,
                            related=rel,
                            allergen_id=matched_pair[0],
                            order_id=matched_pair[1],
                        ),
                    )
                )

        indexed_matches.sort(key=lambda item: item[0])
        return [match for _, match in indexed_matches]


@lru_cache(maxsize=1)
def _load_default_allergy_config() -> AllergyCrossConfig:
    """Đọc và cache bảng dị ứng chéo mặc định trong dữ liệu KB."""
    return AllergyCrossConfig.model_validate_json(
        _DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
    )


def load_allergy_config(path: Path | None = None) -> AllergyCrossConfig:
    """Nạp bảng dị ứng chéo từ tệp mặc định hoặc đường dẫn chỉ định."""
    if path is None:
        return _load_default_allergy_config()
    return AllergyCrossConfig.model_validate_json(path.read_text(encoding="utf-8"))


def try_load_default_allergy_config() -> AllergyCrossConfig | None:
    """Thử nạp bảng dị ứng chéo mặc định; trả None nếu tệp chưa tồn tại."""
    try:
        return load_allergy_config()
    except OSError:
        return None
