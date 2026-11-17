"""Ánh xạ nguồn → cột; sửa tên trường và phép chuyển tại từng khối bảng."""

from collections.abc import Callable
from functools import cached_property
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, create_model

from app.core.types import Chunk
from app.domain import models as m
from app.feedback import PhanHoi
from app.rules.types import CanCu


class Column(BaseModel):
    """Một trường nguồn và kiểu kiểm tra trước khi nạp."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)
    source: str | tuple[str, ...]
    annotation: Any
    default: Any = Field(default_factory=lambda: ...)
    transform: Callable[[Any], Any] | None = None


class ForeignKey(BaseModel):
    """Tham chiếu khai báo dùng kiểm tra và đối chiếu."""

    columns: tuple[str, ...]
    table: str
    target: tuple[str, ...]


class Table(BaseModel):
    """Một khối ánh xạ; thứ tự khai báo cũng là thứ tự nạp."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)
    name: str
    primary_key: tuple[str, ...]
    columns: dict[str, Column]
    foreign_keys: tuple[ForeignKey, ...] = ()
    generated_columns: tuple[str, ...] = ("nap_luc",)
    json_columns: tuple[str, ...] = ()

    @property
    def column_names(self) -> tuple[str, ...]:
        return (*self.columns, "nguon_tep")

    @cached_property
    def row_model(self) -> type[BaseModel]:
        return create_model(
            self.name.replace(".", "_"),
            __config__=ConfigDict(extra="ignore", allow_inf_nan=False),
            **{key: (col.annotation, col.default) for key, col in self.columns.items()},
        )

    def convert(self, raw: dict[str, Any], source: str) -> dict[str, Any]:
        """Kiểm kiểu bằng pydantic, giữ nguyên số liệu và giá trị rỗng."""
        import json

        values = {}
        for key, column in self.columns.items():
            sources = (column.source,) if isinstance(column.source, str) else column.source
            for source_key in sources:
                if source_key in raw:
                    value = raw[source_key]
                    values[key] = column.transform(value) if column.transform else value
                    break
        row = self.row_model.model_validate_json(json.dumps(values), strict=True)
        result = row.model_dump(mode="json")
        for key in self.primary_key:
            if result[key] is None or result[key] == "":
                raise ValueError(f"thiếu {key}")
        if self.name.endswith("ket_qua_xet_nghiem"):
            if result["gia_tri_so"] is None and not (result["gia_tri_text"] or "").strip():
                raise ValueError("thiếu gia_tri_so hoặc gia_tri_text")
        if self.name.endswith("chi_tiet_y_lenh"):
            if not (result["thuoc_id"] or result["ten_tu_do"]):
                raise ValueError("thiếu thuoc_id hoặc ten_tu_do")
        result["nguon_tep"] = source
        return result


def field(name: str, annotation: Any = str, default: Any = ...) -> Column:
    return Column(source=name, annotation=annotation, default=default)


def model_columns(model: type[BaseModel], *exclude: str) -> dict[str, Column]:
    """Dùng đúng tên, ràng buộc và giá trị mặc định của mô hình gốc."""
    return {
        key: Column(
            source=key,
            annotation=info.rebuild_annotation(),
            default=(... if info.is_required() else info.get_default(call_default_factory=True)),
        )
        for key, info in model.model_fields.items()
        if key not in exclude
    }


def fk(column: str, table: str, target: str | None = None) -> ForeignKey:
    return ForeignKey(columns=(column,), table=table, target=(target or column,))


TABLE_LIST = (
    Table(
        name="tri_thuc.hoat_chat",
        primary_key=("hoat_chat_id",),
        columns={
            **model_columns(m.HoatChat),
            "ten_hoat_chat": Column(source=("ten_hoat_chat", "ten_viet"), annotation=str),
            "ten_quoc_te": Column(
                source=("ten_quoc_te", "ten_inn"), annotation=str | None, default=None
            ),
            "nhom_duoc_ly": Column(
                source=("nhom_duoc_ly", "nhom"), annotation=str | None, default=None
            ),
            "thanh_phan": field("thanh_phan", list[str] | None, None),
            "can_duyet": field("can_duyet", bool | None, None),
        },
        json_columns=("thanh_phan",),
    ),
    Table(
        name="nghiep_vu.nguoi_benh",
        primary_key=("nguoi_benh_id",),
        columns={
            **model_columns(m.NguoiBenh),
            "tinh_trang_di_ung": field("tinh_trang_di_ung", m.TinhTrangDiUng),
        },
        json_columns=("tinh_trang_di_ung",),
    ),
    Table(
        name="nghiep_vu.dot_dieu_tri",
        primary_key=("dot_dieu_tri_id",),
        columns={
            **model_columns(m.DotDieuTri),
            "nguoi_benh_id": field("nguoi_benh_id"),
            "ca_id": field("ca_id"),
            "mo_ta_ngan": field("mo_ta_ngan"),
            "co_dia": field("co_dia", list[m.CoDia], []),
        },
        foreign_keys=(fk("nguoi_benh_id", "nghiep_vu.nguoi_benh"),),
        json_columns=("co_dia",),
    ),
    Table(
        name="nghiep_vu.di_ung",
        primary_key=("di_ung_id",),
        columns={**model_columns(m.DiUng), "nguoi_benh_id": field("nguoi_benh_id")},
        foreign_keys=(
            fk("nguoi_benh_id", "nghiep_vu.nguoi_benh"),
            fk("hoat_chat_id", "tri_thuc.hoat_chat"),
        ),
    ),
    Table(
        name="nghiep_vu.thuoc",
        primary_key=("thuoc_id",),
        columns=model_columns(m.Thuoc, "thanh_phan"),
    ),
    Table(
        name="nghiep_vu.thuoc_hoat_chat",
        primary_key=("thuoc_id", "hoat_chat_id"),
        columns={"thuoc_id": field("thuoc_id"), **model_columns(m.ThanhPhan)},
        foreign_keys=(fk("thuoc_id", "nghiep_vu.thuoc"), fk("hoat_chat_id", "tri_thuc.hoat_chat")),
    ),
    Table(
        name="nghiep_vu.chan_doan",
        primary_key=("chan_doan_id",),
        columns={**model_columns(m.ChanDoan), "dot_dieu_tri_id": field("dot_dieu_tri_id")},
        foreign_keys=(fk("dot_dieu_tri_id", "nghiep_vu.dot_dieu_tri"),),
    ),
    Table(
        name="nghiep_vu.sinh_hieu",
        primary_key=("sinh_hieu_id",),
        columns={**model_columns(m.SinhHieu), "dot_dieu_tri_id": field("dot_dieu_tri_id")},
        foreign_keys=(fk("dot_dieu_tri_id", "nghiep_vu.dot_dieu_tri"),),
    ),
    Table(
        name="nghiep_vu.ket_qua_xet_nghiem",
        primary_key=("xet_nghiem_id",),
        columns={**model_columns(m.KetQuaXetNghiem), "dot_dieu_tri_id": field("dot_dieu_tri_id")},
        foreign_keys=(fk("dot_dieu_tri_id", "nghiep_vu.dot_dieu_tri"),),
    ),
    Table(
        name="nghiep_vu.vi_sinh",
        primary_key=("vi_sinh_id",),
        columns={
            **model_columns(m.ViSinh, "khang_sinh_do"),
            "dot_dieu_tri_id": field("dot_dieu_tri_id"),
        },
        foreign_keys=(fk("dot_dieu_tri_id", "nghiep_vu.dot_dieu_tri"),),
    ),
    Table(
        name="nghiep_vu.khang_sinh_do",
        primary_key=("vi_sinh_id", "hoat_chat_id"),
        columns={"vi_sinh_id": field("vi_sinh_id"), **model_columns(m.KhangSinhDo)},
        foreign_keys=(
            fk("vi_sinh_id", "nghiep_vu.vi_sinh"),
            fk("hoat_chat_id", "tri_thuc.hoat_chat"),
        ),
    ),
    Table(
        name="nghiep_vu.dien_bien",
        primary_key=("dien_bien_id",),
        columns={**model_columns(m.DienBien), "dot_dieu_tri_id": field("dot_dieu_tri_id")},
        foreign_keys=(fk("dot_dieu_tri_id", "nghiep_vu.dot_dieu_tri"),),
    ),
    Table(
        name="nghiep_vu.y_lenh",
        primary_key=("y_lenh_id",),
        columns={**model_columns(m.YLenh, "chi_tiet"), "dot_dieu_tri_id": field("dot_dieu_tri_id")},
        foreign_keys=(fk("dot_dieu_tri_id", "nghiep_vu.dot_dieu_tri"),),
    ),
    Table(
        name="nghiep_vu.chi_tiet_y_lenh",
        primary_key=("chi_tiet_y_lenh_id",),
        columns={
            **model_columns(m.ChiTietYLenh, "lich_dung"),
            "y_lenh_id": field("y_lenh_id", str | None, None),
            "dot_dieu_tri_id": field("dot_dieu_tri_id"),
            "thuoc_dang_dung": field("thuoc_dang_dung", bool),
        },
        foreign_keys=(
            fk("thuoc_id", "nghiep_vu.thuoc"),
            fk("y_lenh_id", "nghiep_vu.y_lenh"),
            fk("dot_dieu_tri_id", "nghiep_vu.dot_dieu_tri"),
        ),
    ),
    Table(
        name="nghiep_vu.lich_dung",
        primary_key=("chi_tiet_y_lenh_id", "thu_tu"),
        columns={
            "chi_tiet_y_lenh_id": field("chi_tiet_y_lenh_id"),
            "thu_tu": field("thu_tu", int),
            **model_columns(m.LichDung),
        },
        foreign_keys=(fk("chi_tiet_y_lenh_id", "nghiep_vu.chi_tiet_y_lenh"),),
    ),
    Table(
        name="nghiep_vu.lan_tham_dinh",
        primary_key=("tham_dinh_id",),
        columns={
            "tham_dinh_id": field("tham_dinh_id"),
            "y_lenh_id": field("y_lenh_id"),
            "ca_id": field("ca_id"),
            "van_ban_bat_thuong": field("van_ban_bat_thuong", bool, False),
            "ghi_chu": field("ghi_chu", str | None, None),
        },
        foreign_keys=(fk("y_lenh_id", "nghiep_vu.y_lenh"), fk("ca_id", "nghiep_vu.dot_dieu_tri")),
    ),
    Table(
        name="nghiep_vu.nhan_dinh",
        primary_key=("nhan_dinh_id",),
        columns={
            "nhan_dinh_id": field("nhan_dinh_id"),
            "tham_dinh_id": field("tham_dinh_id"),
            **model_columns(m.PhatHienKyVong, "chi_tiet_y_lenh_id"),
        },
        foreign_keys=(fk("tham_dinh_id", "nghiep_vu.lan_tham_dinh"),),
    ),
    Table(
        name="nghiep_vu.nhan_dinh_thuoc",
        primary_key=("nhan_dinh_id", "chi_tiet_y_lenh_id"),
        columns={
            "nhan_dinh_id": field("nhan_dinh_id"),
            "chi_tiet_y_lenh_id": field("chi_tiet_y_lenh_id"),
        },
        foreign_keys=(
            fk("nhan_dinh_id", "nghiep_vu.nhan_dinh"),
            fk("chi_tiet_y_lenh_id", "nghiep_vu.chi_tiet_y_lenh"),
        ),
    ),
    Table(
        name="nghiep_vu.can_cu",
        primary_key=("can_cu_id",),
        columns={
            "can_cu_id": field("can_cu_id"),
            "nhan_dinh_id": field("nhan_dinh_id"),
            **model_columns(CanCu),
        },
        foreign_keys=(fk("nhan_dinh_id", "nghiep_vu.nhan_dinh"),),
    ),
    Table(
        name="nghiep_vu.phan_hoi",
        primary_key=("ca_id", "ma_luat", "thoi_diem"),
        # nguoi_dung_id, phien_id chỉ có ở tệp JSONL tới khi bảng phan_hoi mở rộng (plan 1.6, T33).
        columns=model_columns(PhanHoi, "nguoi_dung_id", "phien_id"),
        foreign_keys=(fk("ca_id", "nghiep_vu.dot_dieu_tri"),),
        json_columns=("chi_tiet_y_lenh_id",),
    ),
    Table(
        name="tri_thuc.ten_thuoc",
        primary_key=("ten_thuoc", "hoat_chat_id"),
        columns={"ten_thuoc": field("ten_thuoc"), "hoat_chat_id": field("hoat_chat_id")},
        foreign_keys=(fk("hoat_chat_id", "tri_thuc.hoat_chat"),),
    ),
    Table(
        name="tri_thuc.tai_lieu",
        primary_key=("tai_lieu_id",),
        columns={
            "tai_lieu_id": field("tai_lieu_id"),
            "nguon": field("nguon"),
            "tang_tin_cay": field("tang_tin_cay", int),
            "giay_phep": field("giay_phep"),
            "phien_ban_nguon": field("phien_ban_nguon"),
            "set_id": field("set_id"),
            "url_goc": field("url_goc"),
            "sha256": field("sha256"),
        },
    ),
    Table(
        name="tri_thuc.doan_trich",
        primary_key=("doan_trich_id",),
        columns={**model_columns(Chunk), "embedding": field("embedding", str | None, None)},
        foreign_keys=(fk("tai_lieu_id", "tri_thuc.tai_lieu"),),
        generated_columns=("nap_luc", "tu_khoa"),
        json_columns=("hoat_chat_ids",),
    ),
    Table(
        name="tri_thuc.quy_tac_lieu_than",
        primary_key=("quy_tac_id",),
        columns={
            "quy_tac_id": field("quy_tac_id"),
            "ten_quoc_te": field("ten_quoc_te"),
            "nguon": field("nguon"),
            "nguoi_duyet": field("nguoi_duyet", str | None, None),
            "phien_ban": field("phien_ban"),
            "ghi_chu": field("ghi_chu", str | None, None),
            "crcl_tu": field("crcl_tu", float | None, None),
            "crcl_den": field("crcl_den", float | None, None),
            "bao_gom_can_duoi": field("bao_gom_can_duoi", bool),
            "can_chinh": field("can_chinh", bool),
            "khuyen_cao": field("khuyen_cao"),
        },
    ),
    Table(
        name="tri_thuc.tuong_tac_sang_loc",
        primary_key=("ddinter_id_a", "ddinter_id_b"),
        columns={
            "ddinter_id_a": field("DDInterID_A"),
            "ddinter_id_b": field("DDInterID_B"),
            "ten_thuoc_a": field("Drug_A"),
            "ten_thuoc_b": field("Drug_B"),
            "muc_do": field("Level", Literal["Major", "Moderate", "Minor", "Unknown"]),
            "muc_do_nguon": field("muc_do_nguon", list[str]),
            "co_muc_lech": field("co_muc_lech", bool),
            "cac_tep_nguon": field("cac_tep_nguon", list[str]),
            "nguon": field("nguon"),
            "tang_tin_cay": field("tang_tin_cay", int),
            "giay_phep": field("giay_phep"),
            "trang_thai": field("trang_thai"),
        },
        json_columns=("muc_do_nguon", "cac_tep_nguon"),
    ),
)

TABLES = {table.name: table for table in TABLE_LIST}
SCHEMAS = ("nghiep_vu", "tri_thuc")
DDINTER_LEVELS = {"Unknown": 0, "Minor": 1, "Moderate": 2, "Major": 3}
