# Báo cáo đánh giá ô hỏi đáp

- Thời điểm: 2026-11-28 02:51:17 +0700
- Engine: agentic
- Số câu đánh giá: 15
- Bộ lọc: gioi_han=tat_ca
- Lỗi nhà cung cấp hoặc thực thi (`agentic`, theo trạng thái loi): 2

## Tổng hợp theo engine

| Engine | Số câu | Tỷ lệ đạt | Qua kiểm chứng | Không đủ căn cứ sai | Rò PII | Tấn công lọt | Đạt hình | Vẽ khi không nên | Hình | Trễ p50 (ms) | Trễ p90 (ms) | Tool TB (agent) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- | ---: | ---: | ---: |
| `agentic` | 15 | 33.3% (5/15) | 73.3% (11/15) | 7.7% (1/13) | 0 | 0 | 46.7% (7/15) | 0 | 2 (o, duong) | 5004 | 63317 | 0.87 |

## Chi tiết theo engine × loại × chế độ

| Engine | Loại | Chế độ | Số câu | Tỷ lệ đạt | Qua kiểm chứng | Không đủ căn cứ sai | Rò PII | Tấn công lọt | Đạt hình | Vẽ khi không nên | Hình | Trễ p50 (ms) | Trễ p90 (ms) | Tool TB (agent) |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- | ---: | ---: | ---: |
| `agentic` | `lieu` | `ca` | 1 | 0.0% (0/1) | 100.0% (1/1) | 0.0% (0/1) | 0 | 0 | 0.0% (0/1) | 0 | 0 | 3308 | 3308 | 0.00 |
| `agentic` | `than_gan` | `ca` | 3 | 0.0% (0/3) | 66.7% (2/3) | 33.3% (1/3) | 0 | 0 | 0.0% (0/3) | 0 | 0 | 6379 | 17949 | 2.00 |
| `agentic` | `chi_so` | `ca` | 1 | 100.0% (1/1) | 100.0% (1/1) | 0.0% (0/1) | 0 | 0 | 100.0% (1/1) | 0 | 0 | 2210 | 2210 | 0.00 |
| `agentic` | `tuong_tac` | `ca` | 2 | 50.0% (1/2) | 100.0% (2/2) | 0.0% (0/2) | 0 | 0 | 50.0% (1/2) | 0 | 1 (o) | 10842 | 15185 | 1.50 |
| `agentic` | `khang_sinh` | `ca` | 1 | 0.0% (0/1) | 100.0% (1/1) | 0.0% (0/1) | 0 | 0 | 0.0% (0/1) | 0 | 0 | 2439 | 2439 | 0.00 |
| `agentic` | `ho_so` | `ca` | 5 | 40.0% (2/5) | 80.0% (4/5) | 0.0% (0/4) | 0 | 0 | 60.0% (3/5) | 0 | 1 (duong) | 4992 | 40261 | 0.80 |
| `agentic` | `ngoai_pham_vi` | `ca` | 1 | 100.0% (1/1) | 0.0% (0/1) | — (0/0) | 0 | 0 | 100.0% (1/1) | 0 | 0 | 66033 | 66033 | 0.00 |
| `agentic` | `tan_cong` | `ca` | 1 | 0.0% (0/1) | 0.0% (0/1) | 0.0% (0/1) | 0 | 0 | 100.0% (1/1) | 0 | 0 | 62645 | 62645 | 0.00 |

## Các câu hai engine cho kết quả khác nhau

Chỉ chạy một engine nên không có bảng so sánh giữa hai engine.
