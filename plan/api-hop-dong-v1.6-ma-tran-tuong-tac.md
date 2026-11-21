# Hợp đồng API v1.6 – Ma trận tương tác thuốc có cấu trúc (yếu tố 4)

Ngày 19/11/2026. Bổ sung cho `api-hop-dong-v1.md` … `v1.5`. Chỉ **thêm** trường tuỳ chọn, không đổi hay xoá trường cũ.

## Lý do

Hiện tại `web/src/lib/detailTables.ts` (`buildInteractionMatrix`) dò nhận định yếu tố 4 bằng cách tìm chuỗi tên thuốc trong `thuoc` / `nhan_xet`. Cách này có hai vấn đề:
- Dễ sai khi tên trùng một phần.
- Không phân biệt được từng cặp "thiếu dữ liệu" với "không phát hiện".

Từ v1.6, backend trả trạng thái **từng cặp** dựa trên bộ phân giải tên thuốc (T53) và dữ liệu DDInter.

## Thay đổi

`ChiTietCa` (`GET /api/cases/{ca_id}` và các điểm trả chi tiết ca hiện có) thêm:

```text
ma_tran_tuong_tac: MaTranTuongTac | null   // null khi luật yếu tố 4 không chạy (thiếu chỉ mục tra cứu)
```

```text
MaTranTuongTac
  nguon: str                      // ví dụ "DDInter 2.0 (sàng lọc, CC BY-NC-SA 4.0)"
  ghi_chu: str                    // câu giới hạn hiển thị dưới ma trận
  thuoc: list[ThuocMaTran]        // thứ tự hiển thị: dòng chờ duyệt trước, rồi thuốc đang dùng
  cap: list[CapMaTran]            // mọi cặp i < j trong `thuoc`
  thuc_an: list[TuongTacThucAn]   // tương tác thuốc – thức ăn của các thuốc trong `thuoc`

ThuocMaTran
  chi_tiet_y_lenh_id: str
  ten: str                        // đúng tên đang hiện ở bảng y lệnh
  nhom: "cho_duyet" | "dang_dung"
  phan_giai: "da_phan_giai" | "mot_phan" | "khong_nhan_dien" | "khong_ap_dung"
  hoat_chat: list[str]            // tên hoạt chất hiển thị (INN), có thể rỗng
  ly_do: str | null               // khi không phân giải đủ

CapMaTran
  a: str                          // chi_tiet_y_lenh_id
  b: str
  muc: "nghiem_trong" | "can_luu_y" | "thieu_du_lieu" | "khong_phat_hien" | "khong_ap_dung"
  nhan_dinh_id: str | null        // trỏ tới NhanDinh yếu tố 4 tương ứng (khi có)
  tom_tat: str | null             // một dòng, ví dụ "warfarin × amiodarone – Major – Metabolism"
  ly_do: str | null               // vì sao thieu_du_lieu / khong_ap_dung

TuongTacThucAn
  chi_tiet_y_lenh_id: str
  hoat_chat: str
  thuc_an: str
  muc: "nghiem_trong" | "can_luu_y" | "thong_tin" | "chua_ro"
  mo_ta: str | null
  xu_tri: str | null
```

## Quy tắc mức của một cặp thuốc

Một cặp thuốc có thể gồm nhiều cặp hoạt chất (thuốc phối hợp). Mức của cặp thuốc là mức **nặng nhất** trong các cặp hoạt chất, theo thứ tự `nghiem_trong` > `can_luu_y` > `thieu_du_lieu` > `khong_phat_hien` > `khong_ap_dung`.

| Mức | Khi nào |
|:--|:--|
| `nghiem_trong` | Có cặp hoạt chất mức DDInter **Major** |
| `can_luu_y` | Có cặp Moderate hoặc Minor (Minor ghi trong `tom_tat`) |
| `thieu_du_lieu` | Một bên `khong_nhan_dien` / `mot_phan`, một hoạt chất không có `ddinter_id`, hoặc cặp mức **Unknown** |
| `khong_phat_hien` | **Cả hai** hoạt chất có trong DDInter với danh sách tương tác đã cào đủ, và cặp không có trong danh sách |
| `khong_ap_dung` | Một bên chỉ gồm thành phần dịch truyền / điện giải / dược liệu (`khong_ap_dung` của bộ phân giải) |

Hai dòng cùng hoạt chất thì không xét ở yếu tố 4 (thuộc yếu tố 2): `muc = khong_ap_dung`, `ly_do = "trùng hoạt chất – xem yếu tố 2"`.

## Nhận định (`NhanDinh`) đi kèm

- Mỗi cặp `nghiem_trong` / `can_luu_y` / `thieu_du_lieu` có **ít nhất một bên là dòng chờ duyệt** sinh một `NhanDinh` yếu tố 4:
  - `ma_luat`: `tuong_tac_thuoc`, hoặc `tuong_tac_thieu_du_lieu`.
  - `chi_tiet_y_lenh_id`: hai dòng.
  - `can_cu`: loại `tai_lieu`, nguồn DDInter, mức, cơ chế, hậu quả, xử trí (nguyên văn tiếng Anh), đường dẫn trang gốc.
- Cặp chỉ giữa hai thuốc đang dùng vẫn có trong `cap` để hiển thị, nhưng **không** sinh nhận định.
- DDInter là nguồn **tầng 4 – sàng lọc**: nhận định ghi rõ "sàng lọc, cần đối chiếu nhãn"; không dùng chữ "chống chỉ định".

## Giao diện

`buildInteractionMatrix` dùng `ma_tran_tuong_tac` khi có; khi `null` thì giữ cách cũ. Thêm mức hiển thị `khong_ap_dung` (mã "–", "Không áp dụng", gợi ý "Dịch truyền, điện giải hoặc dược liệu").
