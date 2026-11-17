# Hợp đồng API v1.3 – Xác thực và phân quyền

Bổ sung cho `api-hop-dong-v1.md`, v1.1, v1.2. Nguồn quyết định: `plan-1.5-bao-mat-xac-thuc-phan-quyen.md`. Muốn đổi tên trường hay mã lỗi thì sửa file này trước.

## 1. Tiêu đề yêu cầu

Mọi điểm cuối dưới `/api`, **trừ `GET /api/health`**, đòi:

```
Authorization: Bearer <access token JWT do Supabase cấp>
```

Backend không nhận và không bao giờ nhận refresh token.

## 2. Mã lỗi mới

Thân lỗi giữ dạng cũ `{"loi": {"ma": "...", "thong_bao": "..."}}`.

| HTTP | `ma` | Khi nào | Web làm gì |
| :-: | :--- | :--- | :--- |
| 401 | `chua_dang_nhap` | Thiếu tiêu đề, sai dạng, chữ ký sai, `iss` hoặc `aud` sai, thuật toán không cho phép | Thử gia hạn một lần; vẫn lỗi thì đăng xuất |
| 401 | `phien_het_han` | Token hết hạn (`exp`) | Gia hạn bằng refresh token, gửi lại đúng một lần |
| 403 | `khong_co_quyen` | Token hợp lệ nhưng thiếu vai trò, vai trò lạ, vai trò không đủ cho điểm cuối, hoặc khoá ẩn danh | Hiện thông báo, **không** đăng xuất |
| 503 | `xac_thuc_khong_san_sang` | Không lấy được khoá công khai (JWKS) hoặc thiếu cấu hình xác thực | Hiện thông báo thử lại sau |

`thong_bao` bằng tiếng Việt, không chứa token, không phản chiếu đầu vào.

## 3. Điểm cuối mới

### `GET /api/me`

Cần token hợp lệ và vai trò hợp lệ. Trả:

```json
{ "id": "uuid", "email": "a@b.c", "vai_tro": "duoc_si_ls", "phien_id": "uuid" }
```

`email` có thể là `null`. `phien_id` có thể là `null` nếu token không có `session_id`.

### `GET /api/health`

Công khai. Thêm trường `xac_thuc`: `"required"` hoặc `"off"`. Không thêm dữ liệu nào khác.

## 4. Vai trò

Giá trị hợp lệ của `vai_tro`: `duoc_si_ls`, `admin`. Nguồn: `app_metadata.role` trong JWT. `user_metadata` không bao giờ được dùng.

## 5. Dữ liệu ghi

Mỗi dòng mới trong `data/runtime/hoi_thoai.jsonl` và `data/runtime/phan_hoi.jsonl` thêm hai trường:

| Trường | Giá trị |
| :--- | :--- |
| `nguoi_dung_id` | `sub` của JWT |
| `phien_id` | `session_id` của JWT, hoặc `null` |

Dòng cũ không có hai trường này vẫn đọc được; coi là **không có chủ**.

## 6. Hành vi hội thoại

- `GET /api/conversations`: chỉ trả lượt của người gọi (`nguoi_dung_id == sub`). Người gọi là `admin` còn thấy thêm các dòng cũ không có chủ.
- `POST /api/conversations/{ca_id}/clear`: chỉ xoá lượt của người gọi trong phạm vi đó. Lượt của người khác giữ nguyên. Người gọi là `admin` xoá được thêm các dòng cũ không có chủ trong phạm vi đó.
- Hình dạng phản hồi của hai điểm cuối này không đổi.
