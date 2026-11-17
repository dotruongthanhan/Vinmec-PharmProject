# T13-fix-1 – Sửa sau review giao diện đợt 1

**Giao cho:** Codex CLI (`gpt-6.1-sol`, effort high) · **Ngày:** 16/11/2026
**Đọc trước:** `AGENTS.md` (bắt buộc), `plan/briefs/T13-giao-dien-dot-1.md`, `plan/plan-1.2-giao-dien-ui-ux.md` mục 2 (P2) và 3.3.

T13 đã chạy được: mở giao diện thật thấy đúng bố cục, 50 test giao diện qua. Brief này sửa 6 điểm người review thấy. Không làm gì ngoài 6 điểm này.

## 1. Phạm vi file được sửa

```text
app/ui/view_model.py
app/ui/components/findings.py
app/ui/components/summary.py
tests/ui/test_view_model.py
tests/ui/test_app_smoke.py          (mới)
data/mock/demo/DEMO-01.json … DEMO-06.json   (chỉ thêm khoảng tham chiếu creatinin, mục 2.3)
```

Không sửa `app/rules/`, `app/calc/`, `app/domain/`, `app/pipeline.py`, `app/config/`, `app/core/`, `app/providers/`, `app/container.py`, `data/gold/`, `data/kb/`, `data/kb_sources/`, `pyproject.toml`.

**Thư mục `tests/architecture/.tmp` bị khoá quyền (sót lại từ lần chạy trước): không đụng vào, không cố xoá.** Khi chạy `ruff` thêm `--exclude tests/architecture/.tmp`. Khi chạy `pytest`, đặt thư mục tạm ra ngoài kho (ví dụ `--basetemp` trỏ vào thư mục tạm của hệ điều hành) và **không tạo thư mục tạm nào bên trong kho**.

## 2. Sáu điểm

### 2.1 Lint và định dạng

`uv run ruff check . --exclude tests/architecture/.tmp` đang báo `I001` và `E501` ở `app/ui/view_model.py`; `ruff format --check` báo `app/ui/components/findings.py`. Sửa cho sạch, không đổi hành vi.

### 2.2 Số ngày nằm viện tính sai mốc

Giao diện đang ghi `Nằm viện: 10 ngày` cho DEMO-02 vì lấy mốc là giờ máy. Dữ liệu ca là ảnh chụp tại thời điểm kê y lệnh, nên mốc phải là `ca.y_lenh_cho_duyet.thoi_diem_ke`. Nơi gọi `length_of_stay_days` truyền `now = thoi_diem_ke` của y lệnh chờ duyệt. DEMO-02 (vào viện 06/11 10:00, kê 10/11 05:50) phải ra **3 ngày** (số ngày tròn đã qua). Nhãn hiển thị đổi thành `Nằm viện: 3 ngày (tính tới lúc kê y lệnh)`.

### 2.3 Khoảng tham chiếu creatinin trong 6 ca demo

Mọi kết quả `creatinin` trong `data/mock/demo/*.json` đang có `nguong_duoi` và `nguong_tren` là `null`, nên DEMO-02 (creatinin 212) hiện `Không có xét nghiệm ngoài ngưỡng`. Thêm khoảng tham chiếu **giả lập** theo giới của người bệnh trong ca (đơn vị µmol/L, người review cung cấp):

| Giới | `nguong_duoi` | `nguong_tren` |
| :--- | :-: | :-: |
| `nam` | 62 | 106 |
| `nu` | 44 | 80 |

Chỉ thêm hai trường này cho các bản ghi creatinin; không đổi giá trị, thời điểm, mã, hay bất cứ trường nào khác; giữ nguyên định dạng và thứ tự khoá của file. Không sửa `data/gold/`. Nếu sau khi thêm mà test nào ở `tests/rules`, `tests/domain`, `tests/test_pipeline.py` trượt thì **dừng và báo**, không sửa các test đó.

Sau khi thêm, bổ sung test: `lab_trends` DEMO-02 có đúng một dòng creatinin, `huong == "▲"`, `gia_tri_text` chứa `212`, `so_voi_truoc` chứa `150`.

### 2.4 Không được nói "không có bất thường" khi thiếu khoảng tham chiếu (nguyên tắc P2)

Thêm `labs_without_range(ca) -> int`: số kết quả xét nghiệm có `gia_tri_so` nhưng **cả hai** ngưỡng đều `None`. Ở cột "Bất thường gần nhất":

- có dòng ngoài ngưỡng → như hiện tại;
- không có dòng ngoài ngưỡng và `labs_without_range == 0` → `Không có xét nghiệm ngoài ngưỡng.`
- không có dòng ngoài ngưỡng và `labs_without_range > 0` → `Chưa đánh giá được: N kết quả không có khoảng tham chiếu.`
- có dòng ngoài ngưỡng và `labs_without_range > 0` → thêm dòng phụ `N kết quả khác không có khoảng tham chiếu.`

Có test cho hàm bằng ca dựng từ `model_copy`.

### 2.5 Câu "Chưa có luật kiểm tra" phải luôn hiện

Dòng `Chưa có luật kiểm tra cho các yếu tố: …` hiện đang nằm dưới khối "Các mục đạt". Đưa lên **ngay dưới tiêu đề bảng nhận định**, hiển thị bằng `st.caption`, ở mọi ca (kể cả ca có mục cần chú ý), để dược sĩ không hiểu nhầm im lặng là an toàn.

### 2.6 Test chạy thử cả ứng dụng

Thêm `tests/ui/test_app_smoke.py` dùng `streamlit.testing.v1.AppTest`:

- `AppTest.from_file("app/ui/streamlit_app.py", default_timeout=30).run()` không có ngoại lệ (`not at.exception`).
- Với **từng ca trong 6 ca demo**: đặt `at.session_state` về ca đó bằng đúng khoá mà `app/ui/state.py` dùng, `run()` lại, không có ngoại lệ, và trang có chứa `ca_id` đó.
- Test này bắt được lỗi import và lỗi lúc vẽ mà test hàm thuần không bắt được. Nếu `AppTest` không vẽ được `st.dialog` thì bỏ qua phần hộp thoại, không bỏ cả test.

Test không được ghi vào `data/runtime/` (không bấm nút phản hồi trong test).

## 3. Nghiệm thu

```bash
uv run ruff check . --exclude tests/architecture/.tmp
uv run ruff format --check . --exclude tests/architecture/.tmp
uv run pytest -q
```

Cả ba sạch. Hiện có 418 test qua; không test cũ nào bị xoá hay nới kỳ vọng.

## 4. Cấm làm

- Không đổi ngưỡng, liều, công thức, luật, đáp án.
- Không thêm thư viện, không gọi mạng, không đọc `.env`.
- Không commit, không push.
