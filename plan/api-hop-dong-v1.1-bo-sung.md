# Hợp đồng API v1.1 – bổ sung cho `api-hop-dong-v1.md`

**Ngày:** 16/11/2026 (phiên 3). Mọi thứ ở v1 giữ nguyên; file này chỉ thêm.

**Lý do:** gọi DeepSeek mất khoảng 20–25 giây mỗi ca. Vì vậy `GET /api/cases/{ca_id}` **giữ nguyên, chỉ trả kết quả của luật** (nhanh); phần AI chạy nền và web hỏi trạng thái.

## 1. Kiểu dữ liệu thêm

```ts
// Thêm vào NhanDinh (mỗi dòng trong can_chu_y và dat). Ba trường luôn có mặt; chưa có AI thì null / [].
interface NhanDinh {
  // ... các trường v1 giữ nguyên ...
  dien_giai_ai: string | null;   // câu diễn giải của AI cho một phát hiện của luật (đã qua kiểm chứng)
  de_xuat_ai: string | null;     // đề xuất xử trí của AI (đã qua kiểm chứng)
  trich_dan: TrichDan[];         // đoạn nguồn AI trích, đã khớp nguyên văn với kho
}

interface TrichDan { so: number; doan_trich_id: string; nhan: string; trich_nguyen_van: string; }
// nhan = "<tên nguồn> · <đường dẫn mục>"

interface KetQuaAI {
  trang_thai: "tat" | "dang_chay" | "xong" | "loi";
  nhan_dinh: { can_chu_y: NhanDinh[]; dat: NhanDinh[] } | null;  // chỉ có khi "xong"
  canh_bao: string[];            // câu tiếng Việt hiển thị được
  thoi_gian_ms: number | null;
  mo_hinh: string | null;
}

interface DoanNguon {
  doan_trich_id: string; nguon_nhan: string; duong_dan_muc: string;
  tang_tin_cay: number; phien_ban: string; url_goc: string | null; noi_dung: string;
}
```

## 2. Điểm cuối thêm

| Phương thức | Đường dẫn | Trả về | Ghi chú |
| :--- | :--- | :--- | :--- |
| POST | `/api/cases/{ca_id}/ai` | `KetQuaAI` | Khởi động phân tích nếu chưa chạy; đang chạy hoặc đã xong thì trả trạng thái hiện có, không chạy lại. Thân tuỳ chọn `{ "chay_lai": boolean }`; `true` thì bỏ kết quả cũ và chạy lại. AI tắt → `trang_thai: "tat"`. Ca không tồn tại → 404 |
| GET | `/api/cases/{ca_id}/ai` | `KetQuaAI` | Chỉ đọc trạng thái. AI tắt → `"tat"`. AI bật nhưng chưa từng khởi động cho ca này → 404, mã lỗi `chua_chay` |
| GET | `/api/cases/{ca_id}/sources/{doan_trich_id}` | `DoanNguon` | Chỉ trả đoạn đã được cấp cho ca đó trong lần phân tích gần nhất; khác → 404 |

## 3. Bất biến của `KetQuaAI.nhan_dinh` (backend bảo đảm, web được tin)

1. Mọi phát hiện của luật có trong `ChiTietCa.nhan_dinh` đều có mặt, cùng `nhan_dinh_id`, cùng `ket_luan_ma`, cùng `muc_do_ma`, `nguon_goc_ma = "luat"`. AI chỉ được thêm `dien_giai_ai`, `de_xuat_ai`, `trich_dan`.
2. Dòng do AI thêm có `nguon_goc_ma = "ai_da_kiem_chung"`, `ma_luat = null`, và `nhan_dinh_id` bắt đầu bằng `ai|`. Dòng AI trượt kiểm chứng **không được trả về**.
3. Khi `trang_thai` là `"loi"` hoặc `"tat"` thì `nhan_dinh = null`; web tiếp tục hiển thị bảng của luật từ `ChiTietCa`.
4. `che_do.co_llm` là `true` khi bước AI bật được: có khoá, cấu hình hợp lệ, và biến môi trường `CDSS_AI` khác `off`. `che_do.truy_xuat` là `"san_sang"` khi có kho đoạn (`data/kb_curated/chunks.jsonl`), ngược lại `"chua_co"`.
5. Phản hồi (`POST …/feedback`) nhận cả `nhan_dinh_id` của dòng AI trong lần phân tích gần nhất của ca.

## 4. v1.10 – tiến trình

Từ v1.10, `KetQuaAI` (POST và GET `/api/cases/{ca_id}/ai`) bổ sung ba trường tuỳ chọn có mặc định (`cac_buoc: BuocAI[] = []`, `da_chay_ms: number | null = null`, `thuong_le_ms: number | null = null`) và kiểu phụ `BuocAI` / `NguonTomTat` để phản ánh tiến trình phân tích theo thời gian thực. Chi tiết hợp đồng và thiết kế ở `plan/plan-1.10-tien-trinh-ai-ui.md` (mục 4 và 5).
