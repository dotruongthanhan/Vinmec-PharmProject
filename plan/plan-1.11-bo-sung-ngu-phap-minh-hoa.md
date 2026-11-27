# Plan 1.11 – Bổ sung: ngữ pháp minh hoạ (thay mục B.1, B.2 "danh sách kiểu" của plan 1.11)

Ngày 26/11/2026, tối. Chủ kho chốt trong phiên làm tool agent. Tệp `plan/plan-1.11-tracer-va-visualizer.md` do phiên khác giữ nên không sửa trực tiếp; khi có quyết định trái nhau thì **tệp này thắng** cho phần B.

## 1. Quyết định

1. **AI tự quyết dựng hình gì, không có danh mục cố định.** Trải nghiệm giống hình minh hoạ tương tác của ChatGPT (ví dụ chủ kho gửi: phân phối chuẩn có thanh kéo μ, σ, nút ±1σ/2σ/3σ, số "diện tích" đổi theo thanh, nút đặt lại, công thức bên dưới).
2. Mình làm **kỹ năng (skill) + ngữ pháp đặc tả + bộ vẽ**, không viết sẵn từng loại biểu đồ. V1–V8, S1–S8 của plan 1.11 chỉ còn là **ví dụ** trong skill và trong eval.
3. **AI không viết code** (không iframe, không HTML/JS do LLM sinh). AI viết **đặc tả theo ngữ pháp đồ hoạ** (kiểu Vega-Lite): tự ghép lớp, mã hoá trục/màu/nét, lọc, thanh điều khiển.
4. **Số chỉ đến từ bộ dữ liệu `ds-n` do tool trả.** Đặc tả chỉ trỏ tới cột/ô; mọi chỗ cần số (phụ đề, chú thích, đường ngưỡng, giá trị mặc định của thanh) đều là **tham chiếu ô**, không nhận số tự do.
5. **Tương tác có tính toán (thanh kéo đổi creatinin → CrCl, đổi mức liều) dùng "lưới tính sẵn":** máy chủ gọi công thức **đã đăng ký** trong `app/calc` cho một dải giá trị (ví dụ creatinin 50–400 µmol/L bước 5) và gửi kèm hình. Kéo thanh = tra lưới phía máy khách, tức thì, không gọi API, không có công thức nào trên web. Công thức hiển thị lấy từ `app/calc/hien_thi.py`.
6. Hình "khái niệm" không có công thức đăng ký (như chính phân phối Gauss) thì **không vẽ**. Muốn có thì đăng ký thêm công thức có trích dẫn.

## 2. Ngữ pháp `mh-0` (bản nháp, VZ0 thử nghiệm, VZ1 chốt)

```jsonc
{
  "phien_ban": "mh-0",
  "tieu_de": "Liều meropenem theo CrCl",                // ≤ 120 ký tự, chữ thường, qua bộ quét chèn lệnh
  "phu_de": [ {"chu": "CrCl "}, {"o": {"ds": "ds-2", "cot": "crcl", "theo_tham_so": true, "dinh_dang": "0.0"}}, {"chu": " ml/phút"} ],
  "lop": [                                              // ≤ 6 lớp, vẽ chồng theo thứ tự
    { "dau": "dai",                                     // dải nền (mức liều)
      "du_lieu": "ds-1",
      "ma_hoa": { "x_tu": {"cot": "crcl_tu"}, "x_den": {"cot": "crcl_den"}, "nhan": {"cot": "khuyen_cao"}, "mau": {"cot": "can_chinh"} } },
    { "dau": "diem",
      "du_lieu": "ds-2",
      "loc": [ {"cot": "creatinin", "bang_tham_so": "cr"}, {"cot": "loai_can_nang", "bang_tham_so": "cn"} ],
      "ma_hoa": { "x": {"cot": "crcl", "kieu": "dinh_luong"}, "nhan": {"chu": "giả định"} } }
  ],
  "truc": { "x": {"tieu_de": "CrCl (ml/phút)", "mien": "tu_du_lieu"}, "y": null },
  "tham_so": [                                          // ≤ 6 điều khiển
    { "ma": "cr", "loai": "thanh_keo", "nhan": "Creatinin (giả định)", "gia_tri_tu": {"ds": "ds-2", "cot": "creatinin"},
      "mac_dinh": {"o": {"ds": "ds-3", "cot": "creatinin", "dong": 0}}, "nhan_gia_dinh": true },
    { "ma": "cn", "loai": "chon_mot", "nhan": "Cân nặng", "gia_tri_tu": {"ds": "ds-2", "cot": "loai_can_nang"} },
    { "loai": "dat_lai", "nhan": "Về số của ca" }
  ],
  "so_hien": [ {"nhan": "Mức liều", "o": {"ds": "ds-2", "cot": "khuyen_cao", "theo_tham_so": true}} ],  // số/chữ đổi theo thanh
  "cong_thuc": "cockcroft_gault",                       // mã trong app/calc/hien_thi.py, không nhận chuỗi công thức
  "nguon": ["tinh:crcl_cg", "bang:meropenem"]           // phải là mã căn cứ của lượt
}
```

- **Dấu (`dau`):** `duong`, `vung`, `cot`, `diem`, `o` (ô ma trận nhiệt), `dai` (dải nền theo khoảng), `quy_tac` (đường ngưỡng, giá trị lấy từ ô), `chu`. Hình tròn/vành để VZ1 cân nhắc (dễ gây hiểu nhầm).
- **Kiểu cột:** `dinh_luong`, `thu_tu`, `danh_muc`, `thoi_gian`.
- **Điều khiển:** `thanh_keo` (giá trị rời rạc từ một cột của lưới), `chon_mot`, `bat_tat` (chuỗi), `loc` (theo một cột danh mục), `dat_lai`.
- **Luôn có, do code thêm, AI không tắt được:** nút "Xem dạng bảng", nút mở rộng toàn màn, dòng nguồn, nhãn "Minh hoạ, không phải khuyến cáo"; điểm/giá trị giả định có màu và nét riêng kèm chữ "giả định".
- **Trần:** 3 hình mỗi câu trả lời; 2.000 điểm mỗi hình; đặc tả ≤ 16 KB; khối hình (đặc tả + dữ liệu) ≤ 256 KB (nới từ 64 KB của plan 1.11 vì có lưới).

## 3. Skill `config/prompts/ky_nang_minh_hoa.v1.md` (VZ1 viết)

Dạy *cách nghĩ*, không phải danh mục: khi nào vẽ / không vẽ; chọn dấu theo câu hỏi; trung thực (trục cột từ 0, không phân biệt chỉ bằng màu, không quá 6 phần cho tỉ trọng); khi nào thêm thanh kéo (người bệnh sát ngưỡng, câu hỏi "nếu… thì…"); chữ trả lời phải tự đứng được; 4–6 ví dụ đặc tả hoàn chỉnh.

## 4. Thư viện vẽ

**Thẩm định sơ bộ 26/11 (npm + OSV, chưa thử Docker):**

| Gói | Bản mới nhất (ngày) | Bản dùng được (≥ 7 ngày) | OSV bản đó | Ghi chú |
| :--- | :--- | :--- | :--- | :--- |
| `vega` | 6.4.0 (14/8) | 6.4.0 | 0 | Lịch sử **8 cảnh báo** ở bản cũ (XSS/thoát sandbox qua biểu thức); nhóm duy trì UW IDL (jheer, domoritz) |
| `vega-lite` | 6.5.0 (8/10) | 6.5.0 | 0 | |
| `vega-interpreter` | 2.3.2 (14/8) | 2.3.2 | 0 | Bắt buộc nếu dùng Vega: chạy biểu thức không cần `unsafe-eval` |
| `vega-embed` | 7.4.0 (20/11) | 7.3.0 | – | Không cần; tự gọi `vega.View` |
| `recharts` | 3.11.1 (23/11) | 3.10.1 | 0 | Không có ngữ pháp; mình phải tự dịch `mh-0` sang component |

Hướng nếu chọn Vega: **LLM không bao giờ viết đặc tả Vega/biểu thức Vega**; code dịch `mh-0` (đã kiểm) sang Vega-Lite, nên bề mặt biểu thức chỉ do code mình sinh. Vega nặng (~ vài trăm KB nén) → tải lười khi có hình.

VZ0 tự vẽ SVG (0 gói mới) để thử ngữ pháp. Song song, Claude thẩm định `vega` / `vega-lite` / `vega-interpreter` (Vega có tiền sử lỗi thoát sandbox ở biểu thức, phải dùng trình thông dịch an toàn CSP) và `recharts` theo `CLAUDE.md` 6a. Chốt ở VZ1.

## 5. Dữ liệu thực tế đã đo (26/11)

- `data/kb/quy_tac_lieu_than.json`: **chỉ 1 hoạt chất đã duyệt (meropenem)**; còn lại ở `quy_tac_cho_duyet`. Hình liều theo CrCl chỉ demo chắc với meropenem cho tới khi dược sĩ duyệt thêm.
- Thống kê nhiều ca cần VZ3 (dữ liệu giả lập một tháng); VZ0 dùng số giả lập ghi nhãn rõ.

## 6. Bảo mật (bổ sung B.7)

- Bộ kiểm đặc tả chạy **ở cả máy chủ (Gateway) và web**: khoá lạ → bỏ; chữ có link, `<`, `javascript:`, mẫu chèn lệnh → bỏ; số tự do ở chỗ phải là tham chiếu → bỏ; vượt trần → bỏ. Bỏ thì câu trả lời chữ vẫn hiện, ghi lý do vào vết.
- Web vẽ bằng JSX/SVG, không `innerHTML`, không `eval`, không `new Function`; CSP giữ nguyên.
- Lưới tính sẵn chỉ chứa biến của công thức và kết quả, không họ tên/HN/SĐT.

## 7. Đợt việc (thay bảng B.9 cho phần B; phần A giữ nguyên)

| Đợt | Việc | Agent |
| :--- | :--- | :--- |
| TR1 | Tracer lõi (plan 1.11 A.1–A.8, chưa có DB) | agy Neon xhigh |
| VZ0 | Trang mẫu: bộ vẽ ngữ pháp `mh-0` tự vẽ SVG + 3 hình mẫu (liều meropenem có thanh kéo, ma trận tương tác, thống kê tháng giả lập) để chủ kho, dược sĩ xem | agy Neon high |
| VZ1 | Chốt ngữ pháp + thư viện; `BoDuLieu` trong tool; `ve_bieu_do` + Gateway kiểm; lưới tính sẵn; skill; hợp đồng `minh_hoa`; khung trong chat | sau góp ý VZ0 |
