"""Đọc y lệnh và phiếu riêng cho giao diện, không dựng CaBenh."""

from collections import defaultdict
from collections.abc import Sequence

import psycopg
from psycopg import IsolationLevel, sql
from psycopg.rows import dict_row

from app.api import schemas as s
from app.config.settings import get_secret
from app.core.errors import ConfigError
from app.db.reader import DatabaseReadError, Row, Rows
from app.db.timezone import to_vn_time
from app.domain.models import ChiTietYLenh, LichDung
from app.ui import view_model as vm


def _order_lines(rows: Rows) -> dict[str, list[dict[str, str]]]:
    """Cùng cấu trúc dòng bảng cũ; giữ lịch dùng và trạng thái nguồn."""
    drugs = {row["thuoc_id"]: row for row in rows.get("nghiep_vu.thuoc", [])}
    schedules: dict[str, list[Row]] = defaultdict(list)
    for row in rows.get("nghiep_vu.lich_dung", []):
        schedules[row["chi_tiet_y_lenh_id"]].append(row)
    result: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in sorted(
        rows.get("nghiep_vu.chi_tiet_y_lenh", []),
        key=lambda row: (str(row["bat_dau"]), row["chi_tiet_y_lenh_id"]),
    ):
        line = ChiTietYLenh.model_validate(
            {
                **{key: row[key] for key in ChiTietYLenh.model_fields if key in row},
                "lich_dung": [
                    {key: item[key] for key in LichDung.model_fields if key in item}
                    for item in sorted(
                        schedules[row["chi_tiet_y_lenh_id"]], key=lambda item: item["thu_tu"]
                    )
                ],
            }
        )
        drug = drugs.get(line.thuoc_id, {})
        dose = (
            "—"
            if line.lieu_moi_lan is None
            else f"{vm.format_number(line.lieu_moi_lan)} {line.don_vi_lieu or ''}".strip()
        )
        frequency = line.tan_suat or (
            f"{line.so_lan_moi_ngay} lần/ngày" if line.so_lan_moi_ngay is not None else "—"
        )
        result[row["y_lenh_id"]].append(
            {
                "Thuốc": drug.get("ten_thuoc") or line.ten_tu_do or line.chi_tiet_y_lenh_id,
                "Liều": dose,
                "Tần suất": frequency,
                "Đường dùng": line.duong_dung or drug.get("duong_dung") or "—",
                "Lịch dùng": ", ".join(
                    f"{vm.format_dt(item.thoi_diem_du_kien)} "
                    f"({vm.format_number(item.lieu)} {item.don_vi})"
                    for item in line.lich_dung
                )
                or "—",
                "Trạng thái": vm.label_of(vm.NHAN_TRANG_THAI_DONG, line.trang_thai_dong),
            }
        )
    return result


def build_medical_record(rows: Rows, patient_id: str, case_id: str) -> s.MedicalRecord:
    """Dựng thuần từ hàng, chỉ lấy các đợt của người bệnh đã xác định."""
    encounters = {
        row["dot_dieu_tri_id"]: row
        for row in rows.get("nghiep_vu.dot_dieu_tri", [])
        if row["nguoi_benh_id"] == patient_id
    }
    lines = _order_lines(rows)
    orders = []
    for row in rows.get("nghiep_vu.y_lenh", []):
        if row["dot_dieu_tri_id"] not in encounters:
            continue
        data = {key: row[key] for key in s.MedicalOrder.model_fields if key in row}
        data.update(
            thu_tu_dot=encounters[row["dot_dieu_tri_id"]].get("thu_tu"),
            la_trong_tam=row.get("ca_id") == case_id,
            dong=lines[row["y_lenh_id"]],
        )
        data["cot"] = list(data["dong"][0]) if data["dong"] else []
        orders.append(s.MedicalOrder.model_validate(data))
    orders.sort(
        key=lambda item: (
            item.thu_tu_dot or 0,
            item.thoi_diem_ke.timestamp() if item.thoi_diem_ke else float("-inf"),
            item.y_lenh_id,
        )
    )
    links: dict[str, list[str]] = defaultdict(list)
    for row in rows.get("nghiep_vu.phieu_y_lenh", []):
        if row["dot_dieu_tri_id"] in encounters:
            links[row["phieu_dieu_tri_id"]].append(row["y_lenh_id"])
    sheets = []
    for row in rows.get("nghiep_vu.phieu_dieu_tri", []):
        if row["dot_dieu_tri_id"] not in encounters:
            continue
        data = {key: row[key] for key in s.TreatmentSheet.model_fields if key in row}
        data.update(
            thu_tu_dot=encounters[row["dot_dieu_tri_id"]].get("thu_tu"),
            y_lenh_trong_ngay=sorted(links[row["phieu_dieu_tri_id"]]),
        )
        sheets.append(s.TreatmentSheet.model_validate(data))
    sheets.sort(
        key=lambda item: (
            item.thu_tu_dot or 0,
            item.ngay_dieu_tri,
            item.thoi_diem_lap,
            item.phieu_dieu_tri_id,
        )
    )
    return s.MedicalRecord(danh_sach_y_lenh=orders, phieu_dieu_tri=sheets)


def read_medical_record_rows(patient_ids: Sequence[str] | None = None) -> dict[str, list[Row]]:
    """Bảy SELECT gộp theo tập khoá, một ảnh chụp chỉ đọc, không log hàng."""
    try:
        url = get_secret("DATABASE_URL").strip()
        if not url:
            raise ConfigError("DATABASE_URL")
        with psycopg.connect(
            url,
            options="-c default_transaction_read_only=on",
            row_factory=dict_row,
            connect_timeout=10,
        ) as connection:
            connection.isolation_level = IsolationLevel.REPEATABLE_READ
            connection.read_only = True
            rows: dict[str, list[Row]] = {}

            def select(table: str, column: str, keys: Sequence[str]) -> list[Row]:
                query = sql.SQL("SELECT * FROM {} WHERE {} = ANY(%s)").format(
                    sql.Identifier("nghiep_vu", table), sql.Identifier(column)
                )
                selected = to_vn_time(connection.execute(query, (sorted(set(keys)),)).fetchall())
                rows[f"nghiep_vu.{table}"] = selected
                return selected

            if patient_ids is None:
                encounters = to_vn_time(
                    connection.execute(
                        "SELECT d.* FROM nghiep_vu.dot_dieu_tri d WHERE d.nguoi_benh_id IN "
                        "(SELECT e.nguoi_benh_id FROM nghiep_vu.dot_dieu_tri e "
                        "JOIN nghiep_vu.y_lenh y ON y.dot_dieu_tri_id = e.dot_dieu_tri_id "
                        "WHERE y.ca_id IS NOT NULL)"
                    ).fetchall()
                )
                rows["nghiep_vu.dot_dieu_tri"] = encounters
            else:
                encounters = select("dot_dieu_tri", "nguoi_benh_id", patient_ids)
            ids = [row["dot_dieu_tri_id"] for row in encounters]
            select("y_lenh", "dot_dieu_tri_id", ids)
            lines = select("chi_tiet_y_lenh", "dot_dieu_tri_id", ids)
            select("phieu_dieu_tri", "dot_dieu_tri_id", ids)
            select("phieu_y_lenh", "dot_dieu_tri_id", ids)
            select("thuoc", "thuoc_id", [row["thuoc_id"] for row in lines if row.get("thuoc_id")])
            select("lich_dung", "chi_tiet_y_lenh_id", [row["chi_tiet_y_lenh_id"] for row in lines])
            return rows
    except (ConfigError, psycopg.Error, ValueError, TypeError, KeyError, OSError):
        raise DatabaseReadError(
            "Không thể đọc y lệnh và phiếu điều trị từ cơ sở dữ liệu."
        ) from None


def read_medical_record(patient_id: str, case_id: str) -> s.MedicalRecord:
    """Đọc mới mỗi yêu cầu; không lưu vào bộ đệm AI hay ca bệnh."""
    try:
        return build_medical_record(read_medical_record_rows([patient_id]), patient_id, case_id)
    except (ValueError, TypeError, KeyError):
        raise DatabaseReadError("Dữ liệu y lệnh và phiếu điều trị không hợp lệ.") from None


def verify_ho_so() -> int:
    """Đối chiếu số lượng từng ca từ tập hàng DB, không dựng mô hình AI."""
    try:
        rows = read_medical_record_rows()
        encounters = {
            row["dot_dieu_tri_id"]: row["nguoi_benh_id"] for row in rows["nghiep_vu.dot_dieu_tri"]
        }
        focuses = [row for row in rows["nghiep_vu.y_lenh"] if row.get("ca_id")]
        if not focuses:
            print("Không có ca để kiểm tra.")
            return 1
        matched = True
        for focus in sorted(focuses, key=lambda row: row["ca_id"]):
            pid = encounters[focus["dot_dieu_tri_id"]]
            record = build_medical_record(rows, pid, focus["ca_id"])
            order_count = sum(
                encounters[row["dot_dieu_tri_id"]] == pid for row in rows["nghiep_vu.y_lenh"]
            )
            sheet_count = sum(
                encounters[row["dot_dieu_tri_id"]] == pid
                for row in rows["nghiep_vu.phieu_dieu_tri"]
            )
            ok = (
                len(record.danh_sach_y_lenh) == order_count
                and len(record.phieu_dieu_tri) == sheet_count
            )
            ok = ok and (focus["ca_id"] != "HS-022" or order_count == 7)
            matched = matched and ok
            print(
                f"{focus['ca_id']}: y_lệnh={len(record.danh_sach_y_lenh)}/{order_count}, "
                f"phiếu={len(record.phieu_dieu_tri)}/{sheet_count}, {'KHỚP' if ok else 'LỆCH'}"
            )
        return 0 if matched else 1
    except (DatabaseReadError, ValueError, TypeError, KeyError):
        print("Không thể kiểm tra hồ sơ từ cơ sở dữ liệu.")
        return 1
