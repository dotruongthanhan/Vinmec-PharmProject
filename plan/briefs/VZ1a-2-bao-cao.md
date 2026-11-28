# Báo cáo VZ1a-2

## Trạng thái: CHƯA XONG

Bộ kiểm và công cụ đã được triển khai và kiểm thử qua Gateway với danh mục dựng trong test. **Chưa đăng ký công cụ vào danh mục thực tế của ứng dụng**: danh mục đó được lắp bằng các lệnh `dang_ky` trong `app/container.py`, nhưng brief không cho sửa tệp này. `VeBieuDo` đã được xuất từ `app.agent.tools` và chính sách đã được cập nhật; chỉ hai việc đó không tự đăng ký công cụ. Vì vậy agent thực tế chưa thấy hoặc gọi được `ve_bieu_do`. Cần cho phép sửa `app/container.py` để bổ sung đăng ký theo đúng cách các tool hiện có được lắp.

## Tệp tạo hoặc sửa trong lượt này

- Tạo `app/agent/minh_hoa/kiem.py`, `app/agent/tools/ve_bieu_do.py`, `tests/agent/test_minh_hoa_kiem.py`, `tests/agent/test_tool_ve_bieu_do.py` và báo cáo này.
- Sửa `app/agent/tools/__init__.py`, `app/agent/tools/gateway.py`, `app/tracing/models.py`, `config/tool_policy.yaml`.
- Những thay đổi có sẵn trong workspace được giữ lại.

## Thực hiện và lý do từ chối

Bộ kiểm đối chiếu tham chiếu dữ liệu, cột, kiểu, nguồn và công thức; kiểm văn bản, số tự do và các trần. Gateway giữ căn cứ của lượt, tối đa ba khối đã kiểm, giới hạn thời gian và không ghi chữ đặc tả trong vết của tool. Test dựng danh mục riêng, đổi mã dữ liệu và dựng dữ liệu giả từ cấu trúc ba mẫu VZ0; kiểm PII giả, trần và trung vị thời gian cho lưới 300 dòng.

Các mã lý do bộ kiểm hoặc giới hạn khối trả về: `sai_cau_truc`, `khoa_la`, `chu_khong_hop_le`, `chu_khong_an_toan`, `chen_lenh`, `so_tu_do`, `dac_ta_qua_lon`, `dac_ta_khong_hop_le`, `ds_khong_ton_tai`, `cot_khong_ton_tai`, `tham_chieu_khong_hop_le`, `dong_khong_hop_le`, `dinh_dang_khong_hop_le`, `sai_kieu_cot`, `tham_so_khong_hop_le`, `dau_khong_hop_le`, `thieu_kenh`, `qua_2000_phan_tu`, `cong_thuc_khong_hop_le`, `nguon_khong_hop_le`, `sai_kieu_du_lieu`, `khoi_qua_lon`, `qua_3_khoi`. Các từ chối chung của Gateway như quyền, định danh, hạn giờ và ngân sách tiếp tục được dùng.

## Khác `nguPhap.ts`

- Máy chủ nhận `mh-1` và thêm `o_theo_khoang` cho phụ đề và số hiện; web hiện kiểm `mh-0`, chưa hỗ trợ phần mở rộng này. Đó là khác biệt theo hợp đồng và cần phần web ở đợt sau.
- Máy chủ chỉ nhận mã `ds-n` có trong lượt, nguồn thuộc tập căn cứ đã trả của lượt, và công thức có trong `CONG_THUC_HIEN_THI`; web không có cùng ngữ cảnh để kiểm. Bộ kiểm máy chủ dùng bộ quét chèn lệnh sẵn có và giới hạn khối 100 KB theo brief; web chỉ kiểm trần đặc tả và điểm vẽ.
- Máy chủ bổ sung trần 2.048 mục cho các danh sách phụ đề, số hiện, nguồn và bộ lọc, bên cạnh trần 16 KB, để giới hạn đầu vào; web không khai báo các trần số lượng này.
- Kích thước đặc tả dùng JSON không khoảng trắng và UTF-8 như web. Kích thước khối dùng `json.dumps` mặc định theo brief. Trường hợp đặc tả có giá trị `null` ở những trường tùy chọn được kiểm nghiêm theo cấu trúc và có thể bị từ chối khác với một số nhánh web.

## Lệnh và kết quả

Các lệnh `uv` dưới đây dùng thêm `--offline --no-sync`, với `UV_CACHE_DIR` đặt trong `%TEMP%` để không dùng mạng hay sửa môi trường. Lần đầu chạy `uv` không đổi cache bị từ chối quyền truy cập cache mặc định; đổi cache sang `%TEMP%` đã khắc phục. Lần test trước khi tạo bộ kiểm thất bại với `ModuleNotFoundError`, đúng trạng thái chưa có mã.

- `uv run --offline --no-sync ruff check app tests tools`: đạt.
- `uv run --offline --no-sync ruff format --check app tests/agent tools`: đạt, 243 tệp đã đúng định dạng.
- `uv run --offline --no-sync pytest -q -p no:cacheprovider tests/agent/test_tool_ve_bieu_do.py --basetemp "%TEMP%/vz1a2-v3-tool"`: 4 đạt.
- `uv run --offline --no-sync pytest -q -p no:cacheprovider tests/agent/test_minh_hoa_kiem.py --basetemp "%TEMP%/vz1a2-v3-kiem"`: 19 đạt.
- `uv run --offline --no-sync pytest -q -p no:cacheprovider tests/agent/test_gateway.py --basetemp "%TEMP%/vz1a2-v2-gateway"`: 31 đạt.
- `uv run --offline --no-sync pytest -q -p no:cacheprovider tests/tracing/test_tracing.py --basetemp "%TEMP%/vz1a2-v2-tracing"`: 14 đạt.

Các tệp pytest được chạy tuần tự, mỗi lần một tệp. Không cài gói, không dùng mạng và không commit.
