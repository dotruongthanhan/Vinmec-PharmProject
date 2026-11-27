# Hợp đồng API v1.10 – Khối minh hoạ trong câu trả lời hỏi đáp

Ngày 27/11/2026. Bổ sung `api-hop-dong-v1.2-hoi-dap.md`. Ngữ pháp đặc tả: `plan/plan-1.11-bo-sung-ngu-phap-minh-hoa.md` (bản `mh-0`; tệp này chốt thành `mh-1`).

## 1. `TraLoi` thêm trường

```jsonc
{
  "trang_thai": "ok",
  "noi_dung": "...",
  "trich_dan": [...],
  "cong_cu_da_goi": [...],
  "thoi_gian_ms": 0,
  "ma_vet": "…",
  "minh_hoa": [ KhoiMinhHoa ]          // mới; mặc định []; tối đa 3 phần tử
}
```

- Chỉ có khi `trang_thai == "ok"` **và** câu trả lời đã qua kiểm chứng. Câu trả lời bị chặn/dự phòng → `minh_hoa: []`.
- Chỉ engine `agentic` sinh hình; `co_dinh` luôn `[]`.
- Không lưu vào lịch sử hội thoại ở v1.10 (lịch sử chỉ có chữ; web ghi "Hình minh hoạ không lưu trong lịch sử").

## 2. `KhoiMinhHoa`

```jsonc
{
  "ma": "mh-1",                         // duy nhất trong câu trả lời
  "phien_ban": "mh-1",
  "dac_ta": { ...DacTaMinhHoa... },     // đã qua kiểm ở máy chủ
  "bo_du_lieu": [ BoDuLieu ],           // chỉ các bộ mà dac_ta trỏ tới
  "cong_thuc_hien_thi": "…" | null,     // máy chủ lấy từ app/calc/hien_thi.py theo dac_ta.cong_thuc
  "nguon": ["tinh:…", "bang:…", "ddinter:…"]  // mã căn cứ của lượt, đã kiểm
}
```

`BoDuLieu`:

```jsonc
{ "ma": "ds-1",
  "cot": [ { "ten": "crcl", "kieu": "dinh_luong|thu_tu|danh_muc|thoi_gian|logic", "don_vi": "mL/min" | null, "nhan": "CrCl" | null } ],
  "dong": [ { "crcl": 16.0, ... } ],     // giá trị: số, chuỗi ≤ 200 ký tự, bool, null
  "can_cu": ["tinh:crcl_cg"] }
```

Trần (máy chủ cắt bỏ cả khối nếu vượt, không cắt nửa vời): 20 cột, 2.000 dòng mỗi bộ; 2.000 phần tử vẽ mỗi hình; `dac_ta` ≤ 16 KB; **cả khối ≤ 100 KB** sau `json.dumps`; tối đa 3 khối.

## 3. Ngữ pháp `mh-1` = `mh-0` + các điểm chốt

1. Giữ toàn bộ khoá của `mh-0` (xem tệp bổ sung mục 2 và `web/src/features/minh-hoa/nguPhap.ts`).
2. **Tra khoảng** (so sánh, không tính toán) để lấy chữ/số theo giá trị đang chọn:
   ```jsonc
   {"o_theo_khoang": {"ds": "ds-1", "cot": "khuyen_cao",
                      "tu": "bien_ve_tu", "den": "bien_ve_den",
                      "bao_gom_tu": "bao_gom_tu", "bao_gom_den": "bao_gom_den",
                      "gia_tri": {"ds": "ds-2", "cot": "crcl", "theo_tham_so": true}}}
   ```
   Dùng được ở `phu_de`, `so_hien`. Các cột `bao_gom_*` là cột logic do code điền.
3. `cong_thuc` chỉ nhận mã có trong `CONG_THUC_HIEN_THI`.
4. Chữ trong đặc tả (`tieu_de`, `nhan`, `chu`…): ≤ 120 ký tự, không `<`, `>`, `http`, `javascript:`, ký tự rộng 0, mẫu chèn lệnh.

## 4. Lỗi

Không có mã HTTP mới. Đặc tả hỏng → máy chủ bỏ khối, câu trả lời chữ vẫn trả; lý do nằm trong vết (`ma_vet`). Web nhận khối không qua `kiemDacTa` → hiện "Không hiển thị được hình" + nút xem bảng, không vẽ.

## 5. Bảo mật

- Ô dữ liệu kiểu chuỗi đi qua bộ che PII của Gateway như nội dung tool; không có họ tên, HN, SĐT, CCCD, địa chỉ.
- Web vẽ bằng JSX/SVG; không `innerHTML`, `eval`, `new Function`, `iframe`; CSP giữ nguyên.
