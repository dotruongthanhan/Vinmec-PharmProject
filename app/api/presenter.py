"""Hàm thuần chuyển dữ liệu thẩm định sang hợp đồng hiển thị web."""

import hashlib
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Literal, cast

from app.api import schemas as s
from app.calc.types import CalcResult
from app.core.types import Chunk
from app.domain.models import CaBenh, ChiTietYLenh
from app.feedback import PhanHoi
from app.llm.schema import KetQuaLLM, NhanDinhDeXuat, TrichDanNguon
from app.orchestration.ai_review import AiRunResult
from app.pipeline import KetQuaThamDinh
from app.rules.registry import default_rules
from app.rules.types import PhatHien
from app.ui import labels as labels
from app.ui import view_model as vm

_SOURCE_LABELS: dict[str, str] = {
    "openfda": "Nhãn FDA",
    "openfda_drug_label": "Nhãn FDA",
    "byt": "Hướng dẫn Bộ Y tế",
    "van_ban_byt": "Văn bản Bộ Y tế",
    "duoc_thu": "Dược thư Quốc gia",
}

_WARNING_MESSAGES: dict[str, str] = {
    "sai_luoc_do": "Đầu ra của AI không đúng cấu trúc yêu cầu.",
    "dien_giai_khong_khop": (
        "Một số diễn giải của AI không khớp phát hiện của bộ luật nên đã bị bỏ qua."
    ),
    "ai_ha_muc_bi_loai": "Một số đề xuất của AI hạ mức cảnh báo của bộ luật nên đã bị loại.",
    "trung_voi_luat": "Một số đề xuất của AI trùng với phát hiện của bộ luật nên đã bị bỏ qua.",
    "ai_dat_bi_loai": "Một số đề xuất kết luận đạt của AI đã bị loại theo quy tắc an toàn.",
}


def source_label(nguon: str) -> str:
    """Đổi mã nguồn đoạn trích sang tên hiển thị tiếng Việt."""
    return _SOURCE_LABELS.get(nguon, nguon.replace("_", " "))


def present_warnings(warnings: Sequence[str]) -> list[str]:
    """Đổi mã cảnh báo nội bộ sang câu tiếng Việt hiển thị được, bỏ trùng giữ thứ tự."""
    result: list[str] = []
    for item in warnings:
        text = _WARNING_MESSAGES.get(item, item)
        if text not in result:
            result.append(text)
    return result


def current_mode(
    *,
    co_llm: bool = False,
    has_corpus: bool = False,
    hoi_them: bool = False,
) -> s.CheDo:
    """Trả trạng thái thực tế của đường chạy hiện tại theo bất biến 4 v1.1."""
    notices: list[str] = []
    if not co_llm:
        notices.append("Đang chạy không có bước AI: bảng nhận định do bộ luật sinh ra")
    elif not has_corpus:
        notices.append("Chưa có kho đoạn nguồn: bước AI chỉ dùng dữ liệu ca")
    return s.CheDo(
        co_llm=co_llm,
        truy_xuat="san_sang" if has_corpus else "chua_co",
        hoi_them=hoi_them,
        thong_bao=notices,
    )


def ai_finding_id(de_xuat: NhanDinhDeXuat) -> str:
    """Tạo mã nhận định ổn định cho dòng do AI đề xuất đã kiểm chứng."""
    line_ids = ",".join(sorted(de_xuat.chi_tiet_y_lenh_id))
    raw = f"{de_xuat.yeu_to}|{de_xuat.nhan_xet}|{line_ids}".encode()
    return "ai|" + hashlib.sha256(raw).hexdigest()[:12]


def present_source(chunk: Chunk) -> s.DoanNguon:
    """Chuyển đoạn nguồn nội bộ sang hợp đồng DoanNguon."""
    return s.DoanNguon(
        doan_trich_id=chunk.doan_trich_id,
        nguon_nhan=source_label(chunk.nguon),
        duong_dan_muc=chunk.duong_dan_muc,
        tang_tin_cay=chunk.tang_tin_cay,
        phien_ban=chunk.phien_ban_nguon or "",
        url_goc=chunk.url_goc or None,
        noi_dung=chunk.noi_dung_goc,
    )


def finding_id(finding: PhatHien) -> str:
    """Tạo mã nhận định ổn định theo luật và các dòng y lệnh."""
    return finding.ma_luat + "|" + ",".join(sorted(finding.chi_tiet_y_lenh_id))


def present_feedback(feedback: PhanHoi) -> s.PhanHoiDaGhi:
    """Đổi phản hồi đã lưu thành nhãn và thời điểm hiển thị."""
    reason = feedback.nhom_ly_do
    return s.PhanHoiDaGhi(
        phan_hoi=feedback.phan_hoi,
        phan_hoi_nhan=vm.label_of(labels.NHAN_PHAN_HOI, feedback.phan_hoi),
        nhom_ly_do=vm.label_of(labels.NHOM_LY_DO, reason) if reason is not None else None,
        ly_do=feedback.ly_do,
        thoi_diem_text=vm.format_dt(feedback.thoi_diem),
    )


def present_queue(
    cases: Sequence[CaBenh],
    results: Mapping[str, KetQuaThamDinh],
    feedbacks: Sequence[PhanHoi],
) -> list[s.DongHangDoi]:
    """Dùng thứ tự hàng đợi và phản hồi mới nhất từ giao diện hiện có."""
    by_id = {case.ca_id: case for case in cases}
    rows = []
    for row in vm.queue_rows(cases, results):
        case_id = str(row["ca_id"])
        case = by_id[case_id]
        attention, _ = vm.split_findings(
            vm.finding_rows(by_id[case_id], results[case_id].phat_hien)
        )
        done = bool(attention) and all(
            vm.feedback_status(case_id, item, feedbacks) is not None for item in attention
        )
        patient = case.nguoi_benh
        sex = {"nam": "Nam", "nu": "Nữ"}.get(patient.gioi_tinh or "", "Thiếu giới tính")
        age = f"{patient.tuoi} tuổi" if patient.tuoi is not None else "thiếu tuổi"
        drugs_by_id = {drug.thuoc_id: drug for drug in case.danh_muc_thuoc}
        drugs: list[str] = []
        for line in case.y_lenh_cho_duyet.chi_tiet:
            drug = drugs_by_id.get(line.thuoc_id or "")
            if drug is None:
                drugs.append(line.ten_tu_do or f"Thiếu thuốc: {line.thuoc_id}")
                continue
            name = drug.ten_thuoc.strip()
            strength = (drug.ham_luong or "").strip()
            if strength and strength.casefold() not in name.casefold():
                name = f"{name} {strength}"
            drugs.append(name)
        rows.append(
            s.DongHangDoi.model_validate(
                {
                    **row,
                    "da_phan_hoi_het": done,
                    "ma_y_lenh": case.y_lenh_cho_duyet.y_lenh_id,
                    "thoi_diem_ke": case.y_lenh_cho_duyet.thoi_diem_ke.isoformat(),
                    "nguoi_benh_tom_tat": f"{sex}, {age}",
                    "thuoc": drugs,
                }
            )
        )
    return rows


def present_record(case: CaBenh, record_id: str) -> s.BanGhi | None:
    """Chỉ tra bản ghi trong ca đã được nạp."""
    detail = vm.record_detail(case, record_id)
    return s.BanGhi.model_validate(detail) if detail is not None else None


def _present_metric(calc: CalcResult) -> s.ChiSo:
    """Định dạng chỉ số ở lớp hiển thị và giữ nguồn từng đầu vào."""
    return s.ChiSo(
        cong_thuc=calc.cong_thuc,
        nhan=vm.label_of(labels.NHAN_CONG_THUC, calc.cong_thuc),
        don_vi=calc.don_vi,
        gia_tri_text=vm.metric_text(calc.cong_thuc, calc.ket_qua),
        thieu=[vm.label_of(labels.NHAN_DAU_VAO, name) for name in calc.thieu_dau_vao],
        dau_vao=[
            s.MetricInput(
                nhan=vm.label_of(labels.NHAN_DAU_VAO, item.ten),
                gia_tri_text=vm.format_number(item.gia_tri),
                don_vi=item.don_vi,
                ban_ghi_id=item.ban_ghi_id,
                thoi_diem_text=vm.format_dt(item.thoi_diem) if item.thoi_diem is not None else None,
            )
            for item in calc.dau_vao
        ],
        ghi_chu=list(calc.ghi_chu),
        tham_khao=calc.tham_khao,
    )


def _present_finding(
    case: CaBenh,
    finding: PhatHien,
    row: Mapping[str, object],
    feedbacks: Sequence[PhanHoi],
) -> s.NhanDinh:
    """Đổi nhãn nhận định, thứ tự căn cứ và phản hồi mới nhất."""
    evidence = []
    for item in vm.evidence_rows(finding.can_cu):
        kind = cast(s.LoaiCanCuMa, item["loai"])
        formula = None
        if kind == "tinh_toan" and finding.ma_luat.startswith("lieu_than_"):
            formula = "cockcroft_gault"
        evidence.append(
            s.CanCu.model_validate(
                {
                    **{key: value for key, value in item.items() if key != "loai"},
                    "loai_ma": kind,
                    "cong_thuc": formula,
                    "mo_duoc": bool(item["mo_duoc"])
                    and (kind != "tinh_toan" or formula is not None),
                    "ghi_chu": (
                        "Nguyên văn đoạn nguồn sẽ có khi nối kho tri thức."
                        if kind == "tai_lieu"
                        else None
                    ),
                }
            )
        )
    feedback = vm.feedback_status(case.ca_id, row, feedbacks)
    level = finding.muc_do if finding.muc_do in ("nghiem_trong", "can_luu_y") else None
    return s.NhanDinh(
        nhan_dinh_id=finding_id(finding),
        thuoc=str(row["thuoc"]),
        yeu_to=str(row["yeu_to"]),
        nhan_xet=str(row["nhan_xet"]),
        ket_luan_ma=finding.ket_luan,
        ket_luan_nhan=str(row["ket_luan"]),
        muc_do_ma=level,
        muc_do_nhan=vm.label_of(labels.NHAN_MUC_DO, level) if level is not None else None,
        nguon_goc_ma="luat",
        nguon_goc_nhan="Luật",
        ma_luat=finding.ma_luat,
        chi_tiet_y_lenh_id=list(finding.chi_tiet_y_lenh_id),
        thong_tin_con_thieu=list(finding.thong_tin_con_thieu),
        can_cu=evidence,
        phan_hoi=present_feedback(feedback) if feedback is not None else None,
        dien_giai_ai=None,
        de_xuat_ai=None,
        trich_dan=[],
    )


def _present_summary(case: CaBenh, notes: list[s.ProgressNote]) -> s.TomTat:
    """Giữ nguyên câu chữ tóm tắt đang dùng trong Streamlit."""
    trends = vm.lab_trends(case)
    missing = vm.labs_without_range(case)
    note = None
    if trends and missing:
        note = f"{missing} kết quả khác không có khoảng tham chiếu."
    elif not trends and missing:
        note = f"Chưa đánh giá được: {missing} kết quả không có khoảng tham chiếu."
    elif not trends:
        note = "Không có xét nghiệm ngoài ngưỡng."
    days = vm.length_of_stay_days(case, now=case.y_lenh_cho_duyet.thoi_diem_ke)
    return s.TomTat(
        chan_doan=[
            s.Diagnosis(
                loai_nhan="Chính" if item.loai == "chinh" else "Kèm",
                noi_dung=item.noi_dung,
                ma_icd10=item.ma_icd10,
            )
            for item in sorted(case.chan_doan, key=lambda item: item.loai != "chinh")
        ],
        co_dia=[
            f"{vm.label_of(labels.NHAN_CO_DIA_LOAI, item.loai)}: "
            f"{vm.label_of(labels.NHAN_CO_DIA_TRANG_THAI, item.trang_thai)}"
            + (f" ({item.gia_tri})" if item.gia_tri else "")
            for item in case.co_dia
        ],
        vao_vien_text=vm.format_dt(case.dot_dieu_tri.thoi_diem_bat_dau),
        nam_vien_text=f"{days} ngày (tính tới lúc kê y lệnh)" if days is not None else None,
        dien_bien_moi_nhat=notes[0] if notes else None,
        bat_thuong=[
            s.AbnormalLab.model_validate(
                {
                    **{key: value for key, value in trend.items() if key != "thoi_diem"},
                    "thoi_diem_text": vm.format_dt(cast(datetime, trend["thoi_diem"])),
                }
            )
            for trend in trends
        ],
        bat_thuong_ghi_chu=note,
    )


def _present_order_table(
    case: CaBenh,
    lines: Sequence[ChiTietYLenh],
    attention_ids: set[str],
    *,
    include_status: bool = False,
) -> s.BangYLenh:
    """Giữ nguyên cột và cách định dạng bảng y lệnh hiện có."""
    rows = vm.order_table_rows(
        case,
        lines,
        include_status=include_status,
        finding_line_ids=attention_ids,
    )
    return s.BangYLenh(cot=list(rows[0]) if rows else [], dong=rows)


def _present_labs(case: CaBenh) -> list[s.LabResult]:
    """Đổi tên trường của bảng xét nghiệm và tách hướng bất thường."""
    rows = []
    for item in vm.lab_rows(case):
        value = cast(float | None, item["gia_tri_so"])
        low = cast(float | None, item["nguong_duoi"])
        high = cast(float | None, item["nguong_tren"])
        direction: Literal["▲", "▼"] | None = None
        if value is not None:
            if high is not None and value > high:
                direction = "▲"
            elif low is not None and value < low:
                direction = "▼"
        rows.append(
            s.LabResult.model_validate(
                {
                    "thoi_diem_text": vm.format_dt(cast(datetime, item["thoi_diem_ket_qua"])),
                    "ten": item["ten_xet_nghiem"],
                    "gia_tri_text": vm.format_number(value)
                    if value is not None
                    else (item["gia_tri_text"] or "—"),
                    "don_vi": item["don_vi"] or "",
                    "khoang_tham_chieu": vm.format_ref_range(low, high),
                    "ngoai_nguong": item["ngoai_nguong"],
                    "huong": direction,
                }
            )
        )
    return rows


def present_case(
    case: CaBenh,
    result: KetQuaThamDinh,
    feedbacks: Sequence[PhanHoi],
    che_do: s.CheDo | None = None,
) -> s.ChiTietCa:
    """Lắp dữ liệu hiển thị của ca mà không thực hiện thao tác vào/ra."""
    header = vm.header_info(case, result)
    allergy = header.pop("di_ung_trang_thai")
    notes = [
        s.ProgressNote(
            thoi_diem_text=vm.format_dt(item.thoi_diem_ghi),
            loai_nhan=vm.label_of(labels.NHAN_LOAI_HO_SO, item.loai_ho_so),
            noi_dung=item.noi_dung,
        )
        for item in sorted(case.dien_bien, key=lambda item: item.thoi_diem_ghi, reverse=True)
    ]
    rows = vm.finding_rows(case, result.phat_hien)
    attention, passed = vm.split_findings(rows)
    by_key = {(item.ma_luat, tuple(item.chi_tiet_y_lenh_id)): item for item in result.phat_hien}

    def convert(row: Mapping[str, object]) -> s.NhanDinh:
        """Tìm phát hiện gốc cho dòng đã sắp xếp."""
        key = (str(row["ma_luat"]), tuple(cast(list[str], row["chi_tiet_y_lenh_id"])))
        return _present_finding(case, by_key[key], row, feedbacks)

    attention_ids = {
        line_id for row in attention for line_id in cast(list[str], row["chi_tiet_y_lenh_id"])
    }
    order = case.y_lenh_cho_duyet
    prescribed = vm.prescribed_active_ingredient_ids(case)
    ingredients = {item.hoat_chat_id: item.ten_hoat_chat for item in case.danh_muc_hoat_chat}
    return s.ChiTietCa(
        ca_id=case.ca_id,
        dinh_danh=s.DinhDanhCa.model_validate(
            {
                **header,
                "di_ung_ma": allergy,
                "dem": vm.count_by_level(result.phat_hien),
            }
        ),
        tom_tat=_present_summary(case, notes),
        chi_so=[_present_metric(calc) for calc in result.chi_so],
        nhan_dinh=s.Findings(
            can_chu_y=[convert(row) for row in vm.sort_attention_rows(attention)],
            dat=[convert(row) for row in passed],
            yeu_to_chua_kiem=vm.unchecked_factors(result.phat_hien),
            so_luat_da_chay=len(default_rules()),
        ),
        chi_tiet=s.CaseDetails(
            y_lenh=s.Orders(
                thong_tin_text=(
                    f"Mã y lệnh: {order.y_lenh_id} · Khoa kê: {order.khoa_ke_don} · "
                    f"Luồng: {vm.label_of(labels.NHAN_LUONG_DUYET, order.luong_duyet)} · "
                    f"Thời điểm kê: {vm.format_dt(order.thoi_diem_ke)}"
                ),
                cho_duyet=_present_order_table(case, order.chi_tiet, attention_ids),
                dang_dung=_present_order_table(
                    case,
                    case.thuoc_dang_dung,
                    attention_ids,
                    include_status=True,
                )
                if case.thuoc_dang_dung
                else None,
            ),
            xet_nghiem=_present_labs(case),
            vi_sinh=[
                s.Culture(
                    benh_pham=item.benh_pham,
                    lay_mau_text=vm.format_dt(item.thoi_diem_lay_mau),
                    vi_khuan=item.vi_khuan or "Chưa phân lập vi khuẩn",
                    khang_sinh_do=[
                        s.Susceptibility(
                            hoat_chat=ingredients.get(row.hoat_chat_id, row.hoat_chat_id),
                            ket_qua=row.ket_qua,
                            mic_text=vm.format_number(row.mic, digits=2),
                            dang_ke=row.hoat_chat_id in prescribed,
                        )
                        for row in item.khang_sinh_do
                    ],
                )
                for item in sorted(
                    case.vi_sinh, key=lambda item: item.thoi_diem_lay_mau, reverse=True
                )
            ],
            dien_bien=notes,
        ),
        cau_hoi_goi_y=vm.suggested_questions(case),
        nhom_ly_do=list(labels.NHOM_LY_DO.values()),
        thoi_gian_ms=result.thoi_gian_ms,
        che_do=che_do if che_do is not None else current_mode(),
    )


def _present_citations(
    quotes: Sequence[TrichDanNguon],
    chunk_by_id: Mapping[str, Chunk],
) -> list[s.TrichDan]:
    """Đổi trích dẫn nguồn sang TrichDan với số thứ tự bắt đầu từ 1."""
    result: list[s.TrichDan] = []
    for idx, quote in enumerate(quotes, start=1):
        chunk = chunk_by_id.get(quote.doan_trich_id)
        if chunk is not None:
            label = f"{source_label(chunk.nguon)} · {chunk.duong_dan_muc}"
        else:
            label = quote.doan_trich_id
        result.append(
            s.TrichDan(
                so=idx,
                doan_trich_id=quote.doan_trich_id,
                nhan=label,
                trich_nguyen_van=quote.trich_nguyen_van,
            )
        )
    return result


def _present_ai_finding(
    case: CaBenh,
    de_xuat: NhanDinhDeXuat,
    chunk_by_id: Mapping[str, Chunk],
    feedbacks: Sequence[PhanHoi],
) -> s.NhanDinh:
    """Chuyển một dòng ai_da_kiem_chung thành NhanDinh theo hợp đồng v1.1."""
    finding_code = ai_finding_id(de_xuat)
    factor_name = labels.TEN_YEU_TO.get(de_xuat.yeu_to, str(de_xuat.yeu_to))
    level = de_xuat.muc_do if de_xuat.muc_do in ("nghiem_trong", "can_luu_y") else None
    drug_text = " + ".join(vm.drug_label(case, line_id) for line_id in de_xuat.chi_tiet_y_lenh_id)

    evidence: list[s.CanCu] = []
    for idx, record_id in enumerate(dict.fromkeys(de_xuat.ban_ghi_ids), start=1):
        detail = vm.record_detail(case, record_id)
        if detail is not None:
            desc = f"{detail['loai']}: {detail['tieu_de']}"
            openable = True
        else:
            desc = f"Bản ghi {record_id}"
            openable = False
        evidence.append(
            s.CanCu(
                so=idx,
                loai_ma="du_lieu",
                loai_nhan=vm.label_of(labels.NHAN_LOAI_CAN_CU, "du_lieu"),
                mo_ta=desc,
                ban_ghi_id=record_id,
                mo_duoc=openable,
                cong_thuc=None,
                ghi_chu=None,
            )
        )

    row_key: dict[str, object] = {
        "ma_luat": finding_code,
        "chi_tiet_y_lenh_id": list(de_xuat.chi_tiet_y_lenh_id),
    }
    feedback = vm.feedback_status(case.ca_id, row_key, feedbacks)
    return s.NhanDinh(
        nhan_dinh_id=finding_code,
        thuoc=drug_text,
        yeu_to=f"{de_xuat.yeu_to}. {factor_name}",
        nhan_xet=de_xuat.nhan_xet,
        ket_luan_ma=de_xuat.ket_luan,
        ket_luan_nhan=vm.label_of(labels.NHAN_KET_LUAN, de_xuat.ket_luan),
        muc_do_ma=level,
        muc_do_nhan=vm.label_of(labels.NHAN_MUC_DO, level) if level is not None else None,
        nguon_goc_ma="ai_da_kiem_chung",
        nguon_goc_nhan="AI · đã kiểm chứng",
        ma_luat=None,
        chi_tiet_y_lenh_id=list(de_xuat.chi_tiet_y_lenh_id),
        thong_tin_con_thieu=list(de_xuat.thong_tin_con_thieu),
        can_cu=evidence,
        phan_hoi=present_feedback(feedback) if feedback is not None else None,
        dien_giai_ai=None,
        de_xuat_ai=de_xuat.de_xuat,
        trich_dan=_present_citations(de_xuat.trich_dan, chunk_by_id),
    )


def present_ai_result(
    case: CaBenh,
    rule_result: KetQuaThamDinh,
    ai_result: AiRunResult | KetQuaLLM,
    feedbacks: Sequence[PhanHoi] = (),
    *,
    chunks: Sequence[Chunk] = (),
    thoi_gian_ms: float | None = None,
) -> s.KetQuaAI:
    """Chuyển kết quả phân tích AI sang KetQuaAI và kiểm chứng bất biến 1 bằng code."""
    if isinstance(ai_result, AiRunResult):
        llm = ai_result.llm
        source_chunks = list(ai_result.doan)
        raw_warnings = list(ai_result.canh_bao)
        elapsed_ms: float | None = ai_result.thoi_gian_ms
    else:
        llm = ai_result
        source_chunks = list(chunks)
        raw_warnings = list(llm.canh_bao)
        elapsed_ms = thoi_gian_ms

    warnings = present_warnings(raw_warnings)
    if llm.trang_thai != "ok":
        return s.KetQuaAI(
            trang_thai="loi",
            nhan_dinh=None,
            canh_bao=warnings,
            thoi_gian_ms=elapsed_ms,
            mo_hinh=llm.mo_hinh,
        )

    base_case = present_case(case, rule_result, feedbacks)
    expected_rules = {
        row.nhan_dinh_id: row for row in (*base_case.nhan_dinh.can_chu_y, *base_case.nhan_dinh.dat)
    }
    chunk_by_id = {chunk.doan_trich_id: chunk for chunk in source_chunks}

    seen_rule_ids: set[str] = set()
    rule_mismatch = False
    presented_items: list[s.NhanDinh] = []

    for item in llm.nhan_dinh:
        if item.nguon_goc == "ai_chua_kiem_chung":
            continue
        if item.nguon_goc == "luat":
            if item.phat_hien is None:
                rule_mismatch = True
                continue
            fid = finding_id(item.phat_hien)
            expected = expected_rules.get(fid)
            if expected is None or fid in seen_rule_ids:
                rule_mismatch = True
                continue
            seen_rule_ids.add(fid)
            raw_level = item.phat_hien.muc_do
            level = raw_level if raw_level in ("nghiem_trong", "can_luu_y") else None
            if item.phat_hien.ket_luan != expected.ket_luan_ma or level != expected.muc_do_ma:
                rule_mismatch = True
                continue
            if item.dien_giai is not None:
                presented_items.append(
                    expected.model_copy(
                        update={
                            "dien_giai_ai": item.dien_giai.nhan_xet,
                            "de_xuat_ai": item.dien_giai.de_xuat,
                            "trich_dan": _present_citations(item.dien_giai.trich_dan, chunk_by_id),
                        }
                    )
                )
            else:
                presented_items.append(expected)
            continue
        if item.nguon_goc == "ai_da_kiem_chung" and item.de_xuat is not None:
            ai_row = _present_ai_finding(case, item.de_xuat, chunk_by_id, feedbacks)
            # Mã nhận định băm yếu tố, nhận xét và dòng thuốc. Câu chèn lệnh luôn có nhận xét
            # cố định, không có dòng thuốc, nên hai bản ghi chứa chỉ thị cho cùng mã. Gộp căn cứ
            # vào dòng đầu tiên để không mất bằng chứng và không tạo hai thẻ trùng khóa.
            previous = next(
                (row for row in presented_items if row.nhan_dinh_id == ai_row.nhan_dinh_id), None
            )
            if previous is not None:
                known = {evidence.ban_ghi_id for evidence in previous.can_cu}
                for evidence in ai_row.can_cu:
                    if evidence.ban_ghi_id not in known:
                        previous.can_cu.append(
                            evidence.model_copy(update={"so": len(previous.can_cu) + 1})
                        )
                        known.add(evidence.ban_ghi_id)
                previous.thong_tin_con_thieu = list(
                    dict.fromkeys([*previous.thong_tin_con_thieu, *ai_row.thong_tin_con_thieu])
                )
                if previous.de_xuat_ai is None:
                    previous.de_xuat_ai = ai_row.de_xuat_ai
                continue
            presented_items.append(ai_row)

    if rule_mismatch or seen_rule_ids != set(expected_rules):
        mismatch_warnings = [
            *warnings,
            "Kết quả AI không giữ đủ phát hiện của bộ luật, đã bị loại",
        ]
        return s.KetQuaAI(
            trang_thai="loi",
            nhan_dinh=None,
            canh_bao=present_warnings(mismatch_warnings),
            thoi_gian_ms=elapsed_ms,
            mo_hinh=llm.mo_hinh,
        )

    tagged_rows: list[dict[str, object]] = [
        {"ket_luan": row.ket_luan_nhan, "muc_do": row.muc_do_ma, "item": row}
        for row in presented_items
    ]
    attention, passed = vm.split_findings(tagged_rows)
    sorted_attention = vm.sort_attention_rows(attention)
    return s.KetQuaAI(
        trang_thai="xong",
        nhan_dinh=s.AiFindings(
            can_chu_y=[cast(s.NhanDinh, row["item"]) for row in sorted_attention],
            dat=[cast(s.NhanDinh, row["item"]) for row in passed],
        ),
        canh_bao=warnings,
        thoi_gian_ms=elapsed_ms,
        mo_hinh=llm.mo_hinh,
    )
