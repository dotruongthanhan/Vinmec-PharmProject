"""Đọc hành chính riêng cho giao diện, không dùng bộ nhớ đệm hay pipeline AI."""

from collections.abc import Sequence
from typing import Any

import psycopg
from psycopg import sql

from app.api import schemas as s
from app.config.settings import get_secret
from app.core.errors import ConfigError
from app.db.read_pool import read_pool
from app.db.reader import DatabaseReadError, Rows
from app.db.timezone import to_vn_time


def build_administrative(
    rows: Rows, patient_ids: Sequence[str]
) -> dict[str, s.AdministrativeRecord]:
    """Chỉ chiếu trường hợp đồng, không truyền hàng DB sang mô hình lâm sàng."""
    result = {}
    diagnoses = sorted(rows.get("nghiep_vu.chan_doan", []), key=lambda row: row["chan_doan_id"])
    for patient in rows.get("nghiep_vu.nguoi_benh", []):
        patient_id = patient["nguoi_benh_id"]
        if patient_id not in patient_ids:
            continue
        identity = {key: patient[key] for key in s.FullIdentity.model_fields if key in patient}
        if patient.get("dia_chi"):
            identity["dia_chi_text"] = ", ".join(
                patient["dia_chi"][key]
                for key in s.Address.model_fields
                if patient["dia_chi"].get(key)
            )
        history = []
        for encounter in rows.get("nghiep_vu.dot_dieu_tri", []):
            if encounter["nguoi_benh_id"] != patient_id:
                continue
            encounter_id = encounter["dot_dieu_tri_id"]
            data = {
                key: encounter[key]
                for key in s.EncounterHistory.model_fields
                if key in encounter and encounter[key] is not None
            }
            data["chan_doan_chinh"] = (
                "; ".join(
                    row["noi_dung"]
                    for row in diagnoses
                    if row["dot_dieu_tri_id"] == encounter_id and row["loai"] == "chinh"
                )
                or None
            )
            data["y_lenh"] = [
                s.EncounterOrder(
                    **{
                        key: order[key]
                        for key in ("y_lenh_id", "thoi_diem_ke", "trang_thai")
                        if key in order
                    },
                    thuoc=[
                        line["thuoc_text"]
                        for line in rows.get("thuoc_hien_thi", [])
                        if line["y_lenh_id"] == order["y_lenh_id"]
                    ],
                )
                for order in rows.get("nghiep_vu.y_lenh", [])
                if order["dot_dieu_tri_id"] == encounter_id
            ]
            data["phieu_dieu_tri"] = [
                s.EncounterNote(
                    **{key: note[key] for key in s.EncounterNote.model_fields if key in note}
                )
                for note in rows.get("nghiep_vu.dien_bien", [])
                if note["dot_dieu_tri_id"] == encounter_id
                and note["loai_ho_so"].casefold()
                in ("phieu_dieu_tri", "phiếu điều trị", "tờ điều trị", "to_dieu_tri")
            ]
            history.append(s.EncounterHistory.model_validate(data))
        history.sort(key=lambda item: (item.thu_tu or 0, str(item.thoi_diem_bat_dau)))
        result[patient_id] = s.AdministrativeRecord(
            dinh_danh_day_du=s.FullIdentity.model_validate(identity), lich_su_vao_vien=history
        )
    return result


def read_administrative(patient_ids: Sequence[str]) -> dict[str, s.AdministrativeRecord]:
    """Truy vấn tham số hóa trong một ảnh chụp chỉ đọc, không ghi log dữ liệu."""
    if not patient_ids:
        return {}
    try:
        url = get_secret("DATABASE_URL").strip()
        if not url:
            raise ConfigError("DATABASE_URL")
        with read_pool.connection(url) as connection:
            rows: dict[str, list[dict[str, Any]]] = {}

            def select(table: str, column: str, keys: Sequence[str]) -> list[dict[str, Any]]:
                query = sql.SQL("SELECT * FROM {} WHERE {} = ANY(%s)").format(
                    sql.Identifier("nghiep_vu", table), sql.Identifier(column)
                )
                if table == "chan_doan":
                    query += sql.SQL(" ORDER BY chan_doan_id")
                selected = to_vn_time(connection.execute(query, (sorted(set(keys)),)).fetchall())
                rows[f"nghiep_vu.{table}"] = selected
                return selected

            select("nguoi_benh", "nguoi_benh_id", patient_ids)
            encounters = select("dot_dieu_tri", "nguoi_benh_id", patient_ids)
            encounter_ids = [item["dot_dieu_tri_id"] for item in encounters]
            for table in ("chan_doan", "y_lenh", "dien_bien"):
                select(table, "dot_dieu_tri_id", encounter_ids)
            rows["thuoc_hien_thi"] = connection.execute(
                "SELECT ct.y_lenh_id, concat_ws(' ', COALESCE(t.ten_thuoc, ct.ten_tu_do), "
                "ct.lieu_moi_lan::text, ct.don_vi_lieu, ct.duong_dung, ct.tan_suat) AS thuoc_text "
                "FROM nghiep_vu.chi_tiet_y_lenh ct LEFT JOIN nghiep_vu.thuoc t "
                "ON t.thuoc_id = ct.thuoc_id WHERE ct.dot_dieu_tri_id = ANY(%s) "
                "ORDER BY ct.bat_dau, ct.chi_tiet_y_lenh_id",
                (encounter_ids,),
            ).fetchall()
            return build_administrative(rows, patient_ids)
    except (ConfigError, psycopg.Error, ValueError, TypeError, KeyError, OSError):
        raise DatabaseReadError("Không thể đọc thông tin hành chính từ cơ sở dữ liệu.") from None
