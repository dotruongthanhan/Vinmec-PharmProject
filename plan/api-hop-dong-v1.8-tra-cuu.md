# Hợp đồng API v1.8 – Tra cứu thuốc, tra tương tác thủ công, máy tính công thức (chỉ đọc)

Ngày 20/11/2026. Bổ sung cho `api-hop-dong-v1.md` … `v1.7`. Chỉ **thêm** điểm cuối, không đổi hay xoá trường cũ.

- Mọi điểm cuối cần đăng nhập (vai trò `duoc_si_ls` hoặc `admin`), chỉ đọc, trả `Cache-Control: private, no-store`. Không ghi DB, không ghi `ket_qua_tham_dinh`.
- Lỗi theo thân chuẩn `{ "loi": { "ma", "thong_bao" } }`. 404 khi không có tài nguyên; 422 khi dữ liệu không hợp lệ (thông báo tiếng Việt, không có dấu vết ngăn xếp); 503 khi cơ sở dữ liệu hoặc chỉ mục tra cứu chưa sẵn sàng.
- Nguồn dữ liệu theo `KB_SOURCE`: `db` đọc `tri_thuc.*` trên PostgreSQL qua `read_pool`; `file` đọc `tra_cuu.sqlite`, `ddinter.sqlite`, `chunks.jsonl`, `data/kb/*.json`.
- Mỗi phần của chi tiết thuốc ghi `nguon` và `trang_thai` (trạng thái duyệt lấy nguyên từ dữ liệu, ví dụ `cho_duoc_si_duyet`; `null` nghĩa là nguồn không có trường trạng thái, **không** suy diễn là đã duyệt). Dữ liệu chưa được dược sĩ duyệt thì web phải hiển thị nhãn "chờ dược sĩ duyệt" theo `trang_thai`.

```ts
interface KetQuaThuoc {
  hoat_chat_id: string;
  ten_inn: string;
  ten_viet: string | null;
  ma_atc: string[];
  so_che_pham: number;          // số chế phẩm Cục QLD chứa hoạt chất này
  co_nhan_fda: boolean;         // có ít nhất một đoạn nhãn FDA
  so_quy_tac: number;           // số hàng trong bảng luật D1-D7 + nhóm trùng điều trị
}

interface DanhSachThuoc {
  tong: number;
  trang: number;
  so_dong: number;
  ket_qua: KetQuaThuoc[];
  goi_y_sua?: string | null;    // tên gợi ý gần đúng khi LIKE trả 0 kết quả
}

interface GoiYThuoc {
  nhan: string;
  loai: "hoat_chat" | "dong_nghia" | "biet_duoc";
  hoat_chat_ids: string[];
  ten_hoat_chat: string[];
  gia_tri_gui: string;
  khop: "chinh_xac" | "tien_to" | "gan_dung";
}

interface KetQuaGoiYThuoc {
  ket_qua: GoiYThuoc[];
  goi_y_sua: string | null;
}

interface DinhDanhThuoc {
  hoat_chat_id: string;
  ten_inn: string;
  ten_viet: string | null;
  rxcui: string | null;
  ma_atc: string[];
  ddinter_id: string | null;
  loai: string;
  nguon: string;
  trang_thai: string | null;
}

interface ChePham {
  ten_thuoc: string;
  so_dang_ky: string | null;
  dang_bao_che: string | null;
  ham_luong: number | null;     // hàm lượng của chính hoạt chất này trong chế phẩm
  don_vi: string | null;
}

interface DanhSachChePham {
  nguon: string;
  trang_thai: string | null;
  tong: number;                 // tổng số chế phẩm; danh_sach tối đa 50
  danh_sach: ChePham[];
}

interface DoanNhanFda {
  doan_trich_id: string;
  duong_dan_muc: string;
  noi_dung_goc: string;         // nguyên văn, giữ tiếng Anh
  url_goc: string | null;
  tai_lieu_id: string;
  set_id: string | null;        // null ở chế độ tệp
  nguon: string;
  phien_ban_nguon: string | null;
  tang_tin_cay: number;
}

interface NhomNhanFda {
  muc: string;                  // chi_dinh | chong_chi_dinh | lieu | lieu_than | lieu_gan | canh_bao | tuong_tac | thai_ky_cho_bu | nhi_cao_tuoi | tac_dung_phu | qua_lieu | duoc_ly | khac
  doan: DoanNhanFda[];          // rỗng nếu nhãn không có mục này
}

interface NhanFda {
  nguon: string;
  trang_thai: string | null;
  tong_doan: number;
  nhom: NhomNhanFda[];          // luôn đủ 13 mục theo thứ tự trên
}

interface QuyTacDong {
  nhom: string;                 // lieu_than | lieu_gan | nguong_xet_nghiem | thuoc_benh | duong_dung | lieu_toi_da | doc_tinh | khang_sinh_quan_ly | di_ung_cheo | nhom_trung_dieu_tri
  bang_luat: string;            // mã tài liệu bảng luật nguồn
  phan: string;                 // danh sách trong tài liệu (quy_tac, nhom, khong_co_nguong...)
  phien_ban: string | null;
  trang_thai: string | null;
  du_lieu: Record<string, unknown>;  // nguyên hàng bảng luật, gồm trich_nguyen_van và trang_thai nếu có
}

interface SoCapTuongTac {
  major: number;
  moderate: number;
  minor: number;
  unknown: number;
}

interface CapMajor {
  ddinter_id: string;
  ten_thuoc_khac: string;
  co_che: string[];
}

interface TuongTacTomTat {
  nguon: string;
  trang_thai: string | null;
  ddinter_id: string | null;
  co_du_lieu: boolean;
  so_cap: SoCapTuongTac;
  major: CapMajor[];            // tối đa 20 cặp, theo tên thuốc kia
  ghi_chu: string;
}

interface ChiTietThuoc {
  dinh_danh: DinhDanhThuoc;
  che_pham: DanhSachChePham;
  nhan_fda: NhanFda;
  quy_tac: QuyTacDong[];
  tuong_tac_tom_tat: TuongTacTomTat;
}

interface TraTuongTacYeuCau {
  thuoc: string[];              // 2-12 tên tự do, không rỗng, không trùng (sau khi bỏ dấu)
}

interface PhanGiaiTen {
  ten_nhap: string;
  chi_tiet_y_lenh_id: string;   // "T1".."Tn", khớp ma_tran.thuoc[].chi_tiet_y_lenh_id
  trang_thai: "da_phan_giai" | "mot_phan" | "khong_nhan_dien" | "khong_ap_dung";
  hoat_chat: string[];
  ly_do: string | null;
}

interface CapChiTiet {
  a: string;                    // chi_tiet_y_lenh_id
  b: string;
  muc: string;                  // tuong_tac_thuoc | tuong_tac_thieu_du_lieu
  mo_ta: string;
  can_cu: string[];             // nguyên văn căn cứ DDInter: mức, cơ chế, hậu quả, xử trí, URL
  thong_tin_con_thieu: string[];
}

interface KetQuaTraTuongTac {
  ma_tran: MaTranTuongTac;      // đúng mô hình v1.6; cap[].nhan_dinh_id luôn null
  phan_giai: PhanGiaiTen[];     // theo thứ tự nhập
  chi_tiet: CapChiTiet[];       // cặp nghiem_trong / can_luu_y / thieu_du_lieu
}

interface DauVaoCongThuc {
  ten: string;
  nhan: string;                 // nhãn hiển thị tiếng Việt có dấu của trường
  kieu: "so" | "lua_chon";
  don_vi: string[];             // đơn vị cho phép (rỗng nếu không có đơn vị hoặc là lựa chọn)
  lua_chon: string[];           // giá trị cho phép khi kieu = "lua_chon"
  nhan_lua_chon: Record<string, string>; // nhãn hiển thị cho từng giá trị trong lua_chon
  truong_don_vi: string | null; // tên trường đơn vị đi kèm trong dau_vao, ví dụ "creatinin_don_vi"
  bat_buoc: boolean;            // thông tin; thiếu đầu vào vẫn trả 200 với thieu_dau_vao
  mac_dinh: string | number | null;
}

interface DauRaCongThuc {
  don_vi: string[];
  phan_hang: string[];
}

interface CongThucMuc {
  ma: string;
  ten: string;
  loai: string;
  dau_vao: DauVaoCongThuc[];
  dau_ra: DauRaCongThuc;
  tham_khao_goc: string[];
  tham_chieu_mdcalc: string | null;
  trang_thai: string;           // chua_duoc_si_duyet
}

interface DanhMucCongThuc {
  cong_thuc: CongThucMuc[];
}

interface TinhCongThucYeuCau {
  dau_vao: Record<string, string | number | null>;
}

interface DauVaoDaDung {
  ten: string;
  gia_tri: number;
  don_vi: string;
}

interface KetQuaCongThuc {
  ma: string;
  cong_thuc: string;
  phien_ban: string;
  ket_qua: number | null;       // null khi thiếu đầu vào
  don_vi: string;
  dau_vao_da_dung: DauVaoDaDung[];
  thieu_dau_vao: string[];
  ghi_chu: string[];
  tham_khao: string;
  trang_thai: string;
}
```

| Phương thức | Đường dẫn | Trả về | Ghi chú |
| :--- | :--- | :--- | :--- |
| GET | `/api/thuoc?q=&trang=1&so_dong=30` | `DanhSachThuoc` | `q` không dấu, không phân biệt hoa thường; tìm trên tên hoạt chất, đồng nghĩa (kể cả tên Việt) và tên chế phẩm Cục QLD. Xếp: khớp đúng tên trước, rồi khớp đầu, rồi khớp chứa, cuối cùng là hoạt chất chỉ xuất hiện trong tên chế phẩm phối hợp. Khi `q` có giá trị mà truy vấn `LIKE` trả 0 hoạt chất, tự fallback sang chỉ mục gợi ý (30 mục) và trả kèm `goi_y_sua` nếu chỉ khớp gần đúng. `q` rỗng: chỉ liệt kê hoạt chất có nhãn FDA hoặc có quy tắc (hoạt chất khác tìm được bằng `q`). `so_dong` tối đa 100 |
| GET | `/api/thuoc/goi-y?q=&gioi_han=8` | `KetQuaGoiYThuoc` | Gợi ý tên thuốc khi gõ (hoạt chất, đồng nghĩa, biệt dược có thành phần); `q` bắt buộc tối đa 100 ký tự, `gioi_han` từ 1 đến 15 (mặc định 8). Dưới 2 ký tự sau chuẩn hoá trả rỗng. Không ghi `q` vào log |
| GET | `/api/thuoc/{hoat_chat_id}` | `ChiTietThuoc` | 404 nếu không có hoạt chất. `che_pham.danh_sach` tối đa 50; `tuong_tac_tom_tat.major` tối đa 20 |
| POST | `/api/tuong-tac` | `KetQuaTraTuongTac` | Mỗi tên phân giải bằng bộ phân giải thuốc như dòng y lệnh `ten_tu_do`, dựng một ca tạm **trong bộ nhớ** (tất cả dòng chờ duyệt), chạy đúng luật yếu tố 4. Tên lạ vẫn trả 200: `phan_giai[].trang_thai = "khong_nhan_dien"` và các ô liên quan là `thieu_du_lieu`. 422 nếu ít hơn 2 hoặc nhiều hơn 12 tên, tên rỗng, tên quá 200 ký tự, hoặc trùng (so sánh sau khi bỏ dấu, bỏ hoa thường; hai liều khác nhau của cùng thuốc là hai tên khác nhau và được báo "trùng hoạt chất – xem yếu tố 2") |
| GET | `/api/cong-thuc` | `DanhMucCongThuc` | Từ `config/kb/cong_thuc.yaml` (14 công thức) |
| POST | `/api/cong-thuc/{ma}` | `KetQuaCongThuc` | Gọi đúng hàm trong `app/calc` theo danh sách cho phép (không `eval`, không import động). Đơn vị đi kèm gửi trong `dau_vao` ở trường `truong_don_vi` (ví dụ `creatinin` + `creatinin_don_vi`). Trường không có trong đặc tả, đơn vị hoặc lựa chọn không cho phép, giá trị ngoài miền hợp lệ: 422. Thiếu đầu vào: 200, `ket_qua = null`, `thieu_dau_vao` liệt kê trường thiếu. `ma` không có: 404. Số có thể gửi dạng chuỗi dùng dấu phẩy thập phân ("1,2") |

Ví dụ `POST /api/cong-thuc/cockcroft_gault` với `{"dau_vao": {"tuoi": 75, "gioi_tinh": "nu", "can_nang_kg": 50, "creatinin": 1.2, "creatinin_don_vi": "mg/dL"}}` trả `ket_qua ≈ 31.97`, `don_vi = "mL/min"`.

## Ghi chú cho giao diện

- Tên hoạt chất trong ma trận tra tương tác là INN trên trục (`hoat_chat`), cùng cách hiển thị với trang ca.
- Làm tròn chỉ ở lớp hiển thị; `ket_qua` là số thô từ hàm tính.
- Mọi công thức đều đang ở `trang_thai = chua_duoc_si_duyet`: hiển thị nhãn tương ứng, không trình bày là kết luận lâm sàng.
