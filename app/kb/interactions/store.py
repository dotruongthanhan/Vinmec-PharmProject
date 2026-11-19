"""Kho DDInter mở chỉ đọc một lần rồi tra cứu trong bộ nhớ."""

import json
import sqlite3
from collections import defaultdict
from contextlib import closing
from pathlib import Path

from app.kb.interactions.models import FoodRecord, PairRecord


class InteractionStore:
    """Nạp chỉ mục bất biến, không giữ kết nối SQLite khi tra cứu."""

    @classmethod
    def from_path(cls, path: Path) -> "InteractionStore":
        store = cls()
        with closing(sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)) as db:
            db.row_factory = sqlite3.Row
            store._pairs: dict[tuple[str, str], PairRecord] = {}
            for row in db.execute(
                "SELECT ddinter_id_a, ddinter_id_b, muc_do, muc_do_so, co_che_json, "
                "co_lech_muc, cac_muc_nguon_json, ma_trang_cap_json, hau_qua, xu_tri, "
                "tai_lieu_json, url_goc FROM cap ORDER BY ddinter_id_a, ddinter_id_b"
            ):
                values = dict(row)
                for key in ("co_che", "cac_muc_nguon", "ma_trang_cap", "tai_lieu"):
                    values[key] = json.loads(values.pop(f"{key}_json"))
                pair = PairRecord.model_validate(values)
                store._pairs[(pair.ddinter_id_a, pair.ddinter_id_b)] = pair
            store._complete: dict[str, bool] = {
                row["ddinter_id"]: bool(row["da_cao_du"])
                for row in db.execute("SELECT ddinter_id, da_cao_du FROM thuoc")
            }
            store._foods: dict[str, list[FoodRecord]] = defaultdict(list)
            for row in db.execute(
                "SELECT ddinter_id, thuc_an, muc_do, mo_ta, xu_tri, co_che_json "
                "FROM thuc_an ORDER BY ddinter_id, thuc_an, muc_do"
            ):
                values = dict(row)
                values["co_che"] = json.loads(values.pop("co_che_json"))
                food = FoodRecord.model_validate(values)
                store._foods[food.ddinter_id].append(food)
        return store

    def pair(self, id_a: str, id_b: str) -> PairRecord | None:
        """Cùng kết quả cho hai chiều của cặp."""
        a, b = sorted((id_a, id_b))
        row = self._pairs.get((a, b))
        return row.model_copy(deep=True) if row is not None else None

    def drug_complete(self, identifier: str) -> bool:
        """Không coi mã chưa có hoặc chưa rõ tổng nguồn là đã cào đủ."""
        return self._complete.get(identifier, False)

    def foods(self, identifier: str) -> list[FoodRecord]:
        """Trả bản sao để người gọi không sửa dữ liệu dùng chung."""
        return [row.model_copy(deep=True) for row in self._foods.get(identifier, [])]
