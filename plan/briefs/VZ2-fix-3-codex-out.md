**TRẠNG THÁI: CHƯA XONG** — các thay đổi đã được kiểm thử ngoại tuyến, nhưng chưa chạy đủ một test API và chưa nghiệm thu giao diện thật.

**FILE ĐÃ TẠO / SỬA:**

- Máy chủ: `app/agent/minh_hoa/models.py`, `app/agent/nodes.py`, các tool `gateway.py`, `lay_du_lieu_ca.py`, `tra_thuoc.py`.
- Giao diện và test: `web/src/features/minh-hoa/` và `tests/agent/`.
- Prompt, hợp đồng và báo cáo: `config/prompts/ky_nang_minh_hoa.v1.md`, `plan/api-hop-dong-v1.10-minh-hoa.md`, [VZ2-bao-cao.md](D:/create/Vinmec-PharmProject/plan/briefs/VZ2-bao-cao.md).

Đã sửa nhãn logic, nhãn cột dữ liệu ca, định dạng thời gian, trục và chú giải biểu đồ; đồng thời lọc câu nhắc hình khi không có hình sau kiểm chứng.

**LỆNH ĐÃ CHẠY VÀ KẾT QUẢ:**

- Ruff: đạt.
- Pytest `tests/agent`: **270 đạt, 1 không chạy**.
- TypeScript, oxlint, Vitest và Vite build: đạt. Vitest toàn bộ đạt **427 test**; sau đó test riêng bổ sung đạt **12 test**. Oxlint có một cảnh báo ở trang tra cứu ngoài phạm vi brief.
- `git diff --check` trên các tệp mã được sửa: đạt.

**ĐIỂM LỆCH SO VỚI BRIEF VÀ LÝ DO:** Test API bị loại vì import `app.api.main` sẽ gọi `load_env_file()`, trái chỉ dẫn trực tiếp. Các bộ `tinh_chi_so`, `tra_thuoc`, `tra_tuong_tac` đã được rà; một số cột chưa có nhãn vẫn có thể hiện tên kỹ thuật.

**VIỆC CHƯA LÀM / CÂU HỎI:** Cần Claude kiểm thử ba câu trên giao diện thật và chụp ảnh theo brief. Chưa đọc `.env` hoặc gọi `load_env_file()`.

Hướng dẫn [modern-web-guidance](D:/create/Vinmec-PharmProject/.agents/skills/modern-web-guidance/SKILL.md) yêu cầu chạy `npx -y` qua mạng; tôi không chạy bước đó vì brief và quy tắc bảo mật dự án cấm.