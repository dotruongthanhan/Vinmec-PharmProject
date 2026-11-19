"""Đối chiếu trực tiếp tên trường với hợp đồng TypeScript."""

import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

from tests.api.test_routes import client as client  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]

# Các đối tượng viết trực tiếp trong interface được đối chiếu bằng tay.
INLINE_FIELDS: dict[str, set[str]] = {
    "ApiModel": set(),
    "LoadError": {"tep", "loi"},
    "FindingCounts": {"nghiem_trong", "can_luu_y", "thieu_du_lieu", "ngoai_hdsd", "dat"},
    "Diagnosis": {"loai_nhan", "noi_dung", "ma_icd10"},
    "ProgressNote": {"thoi_diem_text", "loai_nhan", "noi_dung"},
    "AbnormalLab": {
        "ten",
        "gia_tri_text",
        "don_vi",
        "huong",
        "thoi_diem_text",
        "so_voi_truoc",
    },
    "MetricInput": {"nhan", "gia_tri_text", "don_vi", "ban_ghi_id", "thoi_diem_text"},
    "Findings": {"can_chu_y", "dat", "yeu_to_chua_kiem", "so_luat_da_chay"},
    "Orders": {"thong_tin_text", "cho_duyet", "dang_dung"},
    "LabResult": {
        "thoi_diem_text",
        "ten",
        "gia_tri_text",
        "don_vi",
        "khoang_tham_chieu",
        "ngoai_nguong",
        "huong",
    },
    "Susceptibility": {"hoat_chat", "ket_qua", "mic_text", "dang_ke"},
    "Culture": {"benh_pham", "lay_mau_text", "vi_khuan", "khang_sinh_do"},
    "CaseDetails": {"y_lenh", "xet_nghiem", "vi_sinh", "dien_bien"},
    "ChatMessage": {"vai", "noi_dung"},
    "Citation": {
        "so",
        "loai_ma",
        "nhan",
        "ban_ghi_id",
        "doan_trich_id",
        "trich_nguyen_van",
    },
    "AiFindings": {"can_chu_y", "dat"},
    "ChayAI": {"chay_lai"},
}


def _parse_contract_interfaces(path: Path) -> dict[str, set[str]]:
    """Trích tên giao diện và tập trường cấp 1 từ khối TypeScript trong tài liệu hợp đồng."""
    document = path.read_text(encoding="utf-8")
    block = re.search(r"```ts\s+(.*?)```", document, re.S).group(1)
    block = re.sub(r"//[^\n]*", "", block)
    parsed: dict[str, set[str]] = {}
    for match in re.finditer(r"interface\s+(\w+)\s*\{", block):
        name = match.group(1)
        depth = 1
        visible = []
        for char in block[match.end() :]:
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            if depth == 0:
                break
            visible.append(char if depth == 1 and char != "}" else " ")
        fields = set(re.findall(r"(?:^|;)\s*(\w+)\??\s*:", "".join(visible)))
        assert fields, name
        parsed.setdefault(name, set()).update(fields)
    return parsed


def test_interface_field_sets_match_contract() -> None:
    from app.api import schemas

    contract_fields = _parse_contract_interfaces(ROOT / "plan/api-hop-dong-v1.md")
    assert len(contract_fields) == 15
    v11_fields = _parse_contract_interfaces(ROOT / "plan/api-hop-dong-v1.1-bo-sung.md")
    for name, fields in v11_fields.items():
        contract_fields.setdefault(name, set()).update(fields)
    assert len(contract_fields) == 18

    v12_doc = (ROOT / "plan/api-hop-dong-v1.2-hoi-dap.md").read_text(encoding="utf-8")
    for field in ("nhan_dinh_id", "thoi_gian_ms", "doan_trich_id", "trich_nguyen_van"):
        assert f"`{field}`" in v12_doc
    contract_fields["GuiCauHoi"].add("nhan_dinh_id")
    contract_fields["TraLoi"].add("thoi_gian_ms")
    queue_fields = {"ma_y_lenh", "thoi_diem_ke", "nguoi_benh_tom_tat", "thuoc"}
    for field in queue_fields:
        assert f"`{field}`" in v12_doc
    contract_fields["DongHangDoi"].update(queue_fields)
    for name, fields in _parse_contract_interfaces(
        ROOT / "plan/api-hop-dong-v1.5-hanh-chinh.md"
    ).items():
        contract_fields.setdefault(name, set()).update(fields)

    for name, fields in _parse_contract_interfaces(
        ROOT / "plan/api-hop-dong-v1.4-ho-so-y-lenh-phieu.md"
    ).items():
        contract_fields.setdefault(name, set()).update(fields)

    v16_doc = (ROOT / "plan/api-hop-dong-v1.6-ma-tran-tuong-tac.md").read_text(encoding="utf-8")
    assert "ma_tran_tuong_tac: MaTranTuongTac | null" in v16_doc
    contract_fields["ChiTietCa"].add("ma_tran_tuong_tac")

    for name, fields in _parse_contract_interfaces(
        ROOT / "plan/api-hop-dong-v1.7-lich-su-tham-dinh.md"
    ).items():
        contract_fields.setdefault(name, set()).update(fields)

    v18_fields = _parse_contract_interfaces(ROOT / "plan/api-hop-dong-v1.8-tra-cuu.md")
    assert len(v18_fields) == 24
    for name, fields in v18_fields.items():
        contract_fields.setdefault(name, set()).update(fields)

    for name, fields in contract_fields.items():
        model = getattr(schemas, name)
        assert set(model.model_fields) == fields, name
        assert model.model_config["extra"] == "forbid"
    for name, fields in INLINE_FIELDS.items():
        model = getattr(schemas, name)
        assert set(model.model_fields) == fields, name
        assert model.model_config["extra"] == "forbid"
    models = {
        name
        for name, value in vars(schemas).items()
        if isinstance(value, type)
        and issubclass(value, BaseModel)
        and value.__module__ == schemas.__name__
    }
    assert models == set(contract_fields) | INLINE_FIELDS.keys()


def _check_display_strings(value: Any, display: bool = False) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            is_display = key.endswith(("_text", "_nhan")) or key in {"nhan", "yeu_to", "huy_hieu"}
            _check_display_strings(item, is_display)
    elif isinstance(value, list):
        for item in value:
            _check_display_strings(item, display)
    elif display and isinstance(value, str):
        assert "_" not in value, value


@pytest.mark.parametrize("case_id", [f"DEMO-{i:02}" for i in range(1, 7)])
def test_all_demo_cases_validate_without_internal_display_codes(
    client: TestClient, case_id: str
) -> None:
    from app.api.schemas import ChiTietCa

    response = client.get(f"/api/cases/{case_id}")
    assert response.status_code == 200
    body = response.json()
    ChiTietCa.model_validate(body, extra="forbid")
    _check_display_strings(body)
    all_findings = body["nhan_dinh"]["can_chu_y"] + body["nhan_dinh"]["dat"]
    base_counts: dict[str, int] = {}
    for finding in all_findings:
        base = finding["ma_luat"] + "|" + ",".join(sorted(finding["chi_tiet_y_lenh_id"]))
        base_counts[base] = base_counts.get(base, 0) + 1
    assert len({f["nhan_dinh_id"] for f in all_findings}) == len(all_findings)
    for finding in all_findings:
        base = finding["ma_luat"] + "|" + ",".join(sorted(finding["chi_tiet_y_lenh_id"]))
        if base_counts[base] == 1:
            assert finding["nhan_dinh_id"] == base
        else:
            assert finding["nhan_dinh_id"].startswith(base + "|")
        assert finding["dien_giai_ai"] is None
        assert finding["de_xuat_ai"] is None
        assert finding["trich_dan"] == []
    body["dinh_danh"]["truong_la"] = True
    with pytest.raises(ValidationError):
        ChiTietCa.model_validate(body)


def test_queue_display_strings(client: TestClient) -> None:
    _check_display_strings(client.get("/api/cases").json())
