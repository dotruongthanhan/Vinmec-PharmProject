# T91 – Lịch sử hỏi đáp lấy từ máy chủ, không tin lịch sử trình duyệt gửi (T6)

Nguồn: `docs/bao-cao-bao-mat-2026-11-20.md` mục T6. Agent: agy `gemini-4-hydrogen-xhigh`. **Không gọi shell, không gọi mạng; chỉ đọc và ghi tệp.**

Song song: T89 (`main.py`, `settings.py`, `ask.py`, `Caddyfile`), T90 (`web/` trừ `useChat.ts`), T92 (Dockerfile, CI). Không đụng tệp của các task đó.

## Bối cảnh

`GuiCauHoi.lich_su` do trình duyệt gửi, cho phép tự khai lượt `he_thong` ("lượt trước hệ thống đã đồng ý bỏ quy tắc…") để lách hàng rào chống chèn lệnh. T88 đã giới hạn 6 tin × 4000 ký tự nhưng chưa sửa gốc.

## Phạm vi tệp

Sửa: `app/api/service.py` (chỉ hàm `ask` và hàm phụ mới), `app/api/schemas.py` (chỉ `GuiCauHoi`), `app/storage/feedback_chat.py` (thêm phương thức đọc), `web/src/state/useChat.ts`, test tương ứng (`tests/api/`, `tests/storage/`, `web/src/__tests__/useChat.test.ts`). Sửa test cũ chỉ khi hỏng vì thay đổi này, ghi lý do.

## Yêu cầu

1. **Kho lưu** (`FeedbackAndChatStore` Protocol + cả `FileFeedbackChatStore` lẫn `DbFeedbackChatStore`): thêm `recent_turns(self, ca_id: str, principal: Principal, limit: int = 3) -> list[tuple[str, str]]` trả tối đa `limit` lượt gần nhất **của chính người gọi** trong phạm vi `ca_id` (kể cả `"__global__"`), theo thứ tự thời gian tăng dần, mỗi lượt là `(cau_hoi, noi_dung_tra_loi)`. Đọc cách `save_chat` / `list_conversations` đang lưu và lọc chủ sở hữu (`_owns_conversation`) để dùng đúng trường. SQL tham số hoá, có `ORDER BY … DESC LIMIT %s` rồi đảo lại.
2. **`CaseService.ask`**: bỏ dùng `request.lich_su`. Dựng `history_pairs` từ `recent_turns(...)` thành danh sách `[("nguoi_dung", cau_hoi), ("he_thong", tra_loi), …]` (tối đa 6 tin, mỗi tin cắt 4000 ký tự), đúng định dạng `history_pairs` hiện tại truyền cho asker. Lượt đã bị xoá bằng `clear_conversation` thì không còn trong lịch sử.
3. **Schema `GuiCauHoi.lich_su`**: giữ trường để trình duyệt cũ không bị 422, đánh dấu bỏ (docstring "Bị bỏ qua từ T91, máy chủ tự dựng lịch sử"), giữ giới hạn của T88.
4. **Web `useChat.ts`**: không gửi `lich_su` nữa (bỏ trường khỏi thân yêu cầu). Giữ hiển thị lịch sử trên màn hình như cũ. Xoá `toHistory` nếu không còn dùng, cập nhật test của nó.

## Bảo mật

- Lịch sử chỉ của chính người gọi (A không bao giờ thấy lượt của B, kể cả `__global__`).
- Nội dung lấy từ DB vẫn đi qua đúng đường che định danh / gỡ ký hiệu phân khối hiện có trong asker (không bỏ bước nào).

## Test

- A hỏi 2 lượt ở ca X; lượt 3 của A: asker giả nhận đúng 4 tin lịch sử là lượt 1–2 của A.
- B hỏi ở cùng ca X: asker giả nhận lịch sử rỗng.
- A gửi `lich_su` chứa lượt `he_thong` bịa → asker giả **không** nhận nội dung đó.
- Sau `clear_conversation` của A: lịch sử rỗng.
- Quá 3 lượt: chỉ 3 lượt gần nhất.
- Cả kho tệp và kho DB (kho DB dùng kết nối giả như test hiện có trong `tests/storage/`, không kết nối DB thật).
- Web: thân yêu cầu `ask` không có khoá `lich_su`.

## Nghiệm thu (Claude chạy)

```
uv run ruff check .
uv run ruff format --check app tests
uv run pytest -q -p no:cacheprovider
cd web && npx tsc -b --noEmit && npx oxlint && npx vitest run
```

## Cấm

Không cài gói. Ghi `plan/reports/T91.md` theo mẫu `AGENTS.md`, kèm mục "Thay đổi hợp đồng API".
