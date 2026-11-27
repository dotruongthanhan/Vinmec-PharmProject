# T110 – Tool `doc_doan_mo_rong` (mở cả mục cha của một đoạn nguồn)

Người làm: Codex `gpt-6.1-terra` effort `xhigh`, `-s workspace-write`.
Đọc trước: `AGENTS.md`; plan 1.9 mục 5.2 (A2), 5.10, 6.1; `plan/briefs/T107-tool-tim-doan-nguon.md`, `T107-bao-cao.md`; mã mẫu `app/agent/tools/tim_doan_nguon.py`, `app/agent/tools/gateway.py`, `app/orchestration/evidence.py` (`LazyRetrieverFactory.ingredient_items`).

## 1. Bối cảnh và bằng chứng cần làm

Plan 1.9 mục 5.10 hoãn tool này, "đo lại sau T107". Claude đo ngày 26/11 trên `data/kb_curated/chunks.jsonl` (3.730 đoạn, 1.551 mục cha):
- `tim_doan_nguon` cắt mỗi đoạn ở 1.200 ký tự: **286 đoạn bị cắt**, trong đó **51/247 đoạn dạng bảng (21%)**, 27 đoạn `lieu`, 11 đoạn `lieu_than`.
- 506 mục cha có nhiều hơn 1 đoạn (tối đa 39 đoạn). Bảng liều bị chia đôi qua hai đoạn thì LLM chỉ thấy nửa bảng.
- Tổng ký tự mỗi mục cha: p50 763, p90 5.207, p99 21.330.

Tool cho LLM xin xem **cả mục cha** của một đoạn mà `tim_doan_nguon` đã trả trong **cùng lượt hỏi**.

## 2. Thiết kế

`ten="doc_doan_mo_rong"`, `ten_hien_thi="Đọc thêm đoạn nguồn"`, `che_do_cho_phep = frozenset({"ca", "chung"})`, `goi_ra_ngoai=False`, không gọi nhúng, không gọi LLM.

Tham số (`extra="forbid"`, không có `ca_id`): `doan_trich_id: str` khớp đúng `^DT-[0-9a-f]{12}$` (đã kiểm: 3.730/3.730 mã thật khớp). Cắt khoảng trắng và bỏ `[ ]` trước khi kiểm, vì LLM hay chép kèm ngoặc.

### 2.1. Chỉ mở đoạn đã trả trong lượt (chốt ở Gateway)

Tool không tự biết đoạn nào đã trả. Thêm vào `ToolGateway` (thay đổi tối thiểu):
- Gateway giữ tập `_doan_da_tra: set[str]`: sau mỗi lần gọi tool thành công, thêm `cc.ma` của mọi `CanCu` có `loai == "doan"` **sau khi đã cắt** (chỉ căn cứ thực sự trả cho LLM).
- Thêm vào lớp `Tool` một `ClassVar[bool]` tên `chi_doan_da_tra = False`. `DocDoanMoRong` đặt `True`.
- Với tool `chi_doan_da_tra=True`: sau khi kiểm lược đồ, nếu `doan_trich_id` không nằm trong `_doan_da_tra` thì từ chối `ma_loi="sai_tham_so"`, câu "chỉ mở được đoạn đã trả trong lượt này", **không gọi tool**. Lần từ chối này vẫn ghi audit như các lần từ chối khác.
- Gateway đã được tạo mới cho mỗi lượt hỏi (`AgenticAsker.ask`, `ask_global`) nên tập này tự xoá giữa các lượt. Kiểm lại điều đó, ghi trong báo cáo.
- Cho tool đọc được đoạn gốc: Gateway lưu luôn `Chunk` (`cc.doan`) theo mã, và truyền cho tool qua một tham số khoá mới tuỳ chọn của `chay`, **hoặc** tool tự nạp lại đoạn từ nguồn theo mã. Chọn cách ít đụng chạm nhất, giải thích trong báo cáo. **Không** đưa đoạn vào `ToolContext` (đối tượng bất biến, dùng chung).

### 2.2. Lấy mục cha và thứ tự đoạn

- Từ đoạn gốc lấy `tai_lieu_id`, `muc_cha_id`, `hoat_chat_ids`. Gọi `nguon.ingredient_items(set(hoat_chat_ids))` (đã có cache), lọc đoạn cùng `tai_lieu_id` **và** cùng `muc_cha_id`. `muc_cha_id is None` thì chỉ trả đúng đoạn gốc, hiển thị đầy đủ.
- **Thứ tự:** DB sắp theo `doan_trich_id` (mã băm, không phải vị trí trong nhãn) và `tri_thuc.doan_trich` không có cột thứ tự. Thứ tự tài liệu chỉ còn ở **thứ tự dòng** của `data/kb_curated/chunks.jsonl`. Làm như sau:
  - Nếu tệp có: dựng một lần (lười, có khoá, cache cấp module) ánh xạ `doan_trich_id → số dòng`, chỉ đọc trường `doan_trich_id` từng dòng. Sắp đoạn theo số dòng.
  - Nếu tệp không có, hoặc có đoạn không có trong ánh xạ: sắp theo `doan_trich_id` và thêm dòng ghi chú "(thứ tự đoạn có thể không theo nhãn gốc)".
  - **Không** thêm cột DB, không sửa `db/schema.sql`, không sửa `app/retrieval/corpus.py`.

### 2.3. Nội dung trả về

- Một dòng đầu: nguồn (`_source_label(nguon)`), `duong_dan_muc`, tầng tin cậy, số đoạn của mục.
- Mỗi đoạn một khối, mở đầu `[doan_trich_id: ...]` rồi văn bản **đầy đủ** (gộp khoảng trắng, không cắt 1.200).
- Trần tổng nội dung **6.000 ký tự** (Gateway cắt ở 8.000). Vượt trần thì ưu tiên giữ đoạn gốc và các đoạn kề nó theo thứ tự (gốc, sau, trước, sau nữa, …), rồi hiển thị lại theo thứ tự tài liệu. Thêm dòng "(mục còn N đoạn chưa hiển thị)". Một đoạn đơn lẻ dài hơn 6.000 thì cắt ở ranh giới câu, đánh dấu "(đã cắt bớt; chỉ trích phần hiển thị ở trên)".
- `can_cu`: một `CanCu(loai="doan", ma=<doan_trich_id>, nhan=..., doan=<Chunk>)` cho **mỗi đoạn hiển thị**, giống `tim_doan_nguon`, để bộ kiểm chứng nhận trích nguyên văn từ các đoạn mới. `so_can_cu_toi_da = 12`.
- `chi_tiet_tien_trinh`: chỉ số đếm, ví dụ "1 mục, 4 đoạn".
- Lỗi nạp đoạn (`RetrievalError`, `ProviderError`, ngoại lệ khác) → `trang_thai="loi"`, `ma_loi="loi_cong_cu"`, thông báo chung, không lộ thông điệp ngoại lệ.

### 2.4. Gợi ý từ `tim_doan_nguon`

Trong `app/agent/tools/tim_doan_nguon.py`, chỉ sửa phần dựng khối: khi đoạn bị cắt (`bi_cat`) hoặc `loai_noi_dung in ("bang", "dong_bang")`, thêm một dòng "(có thể gọi doc_doan_mo_rong với mã này để xem cả mục)". Không đổi gì khác trong tệp, không đổi trần.

### 2.5. Đăng ký và prompt

- `app/container.py`: đăng ký trong `agentic_asker`, dùng cùng `self.evidence_retriever` với `TimDoanNguon`.
- `config/tool_policy.yaml`: khai báo `doc_doan_mo_rong: {bat: true}`, cho `duoc_si_ls` và `admin`.
- `config/prompts/tac_tu.v1.md`: một gạch đầu dòng trong mục 2, sau dòng `tim_doan_nguon`: khi đoạn bị cắt hoặc bảng có vẻ thiếu dòng thì gọi `doc_doan_mo_rong` với đúng `doan_trich_id` đã nhận. Trích dẫn đoạn mới dùng `loai="tai_lieu"` như đoạn của `tim_doan_nguon`.
- `app/agent/tools/__init__.py`: xuất lớp mới.

## 3. Tệp

Tạo: `app/agent/tools/doc_doan_mo_rong.py`, `tests/agent/test_tool_doc_doan_mo_rong.py`, báo cáo `plan/briefs/T110-bao-cao.md`.
Sửa: `app/agent/tools/gateway.py` (chỉ tập đoạn đã trả và chốt `chi_doan_da_tra`), `app/agent/tools/base.py` (chỉ thêm `ClassVar`; thêm tham số tuỳ chọn cho `chay` nếu chọn cách đó, mọi tool cũ phải chạy y như trước), `app/agent/tools/tim_doan_nguon.py` (chỉ mục 2.4), `app/container.py` (chỉ `agentic_asker`), `config/tool_policy.yaml`, `config/prompts/tac_tu.v1.md`, `app/agent/tools/__init__.py`, `tests/agent/test_gateway.py` (thêm test), `tests/agent/test_tool_tim_doan_nguon.py` (chỉ khi test cũ cần cập nhật vì dòng gợi ý mới).
Cấm: `app/agent/tools/tra_thuoc.py`, `tinh_chi_so.py`, `tra_tuong_tac.py`, `app/orchestration/` (trừ khi chỉ import), `app/retrieval/`, `db/`, `graph.py`, `nodes.py`, `web/`, `data/` (chỉ đọc), `pharm-overlay/`, `docs/`; cài gói; gọi mạng; ghi DB; commit; push.

## 4. Bảo mật (mỗi ý ít nhất một test)

1. **Chỉ đọc:** tool không ghi tệp hay DB, không gọi nhúng (stub `rank_by_vector` ném lỗi nếu bị gọi), không gọi LLM.
2. **Chỉ đoạn đã trả trong lượt:** gọi `doc_doan_mo_rong` với một mã có thật trong kho nhưng **chưa** trả trong lượt → `sai_tham_so`, tool không chạy (đếm số lần `chay`). Gọi `tim_doan_nguon` trước rồi mở đúng mã vừa trả → `ok`. Gateway mới (lượt mới) → mã cũ bị từ chối.
3. **Đoạn bị Gateway cắt không mở được:** căn cứ bị cắt khỏi `can_cu` (vượt `so_can_cu_toi_da`) hoặc bị xoá do nghi chèn lệnh thì không được thêm vào `_doan_da_tra`.
4. **Lược đồ:** mã sai dạng (`DT-xyz`, `'; DROP TABLE`, dài 500 ký tự), trường lạ (`ca_id`, `muc_cha_id`) → `sai_tham_so`. `[DT-...]` có ngoặc vẫn nhận.
5. **Không đi chéo tài liệu:** đoạn cùng `muc_cha_id` nhưng khác `tai_lieu_id` (dựng trong test) không được trả.
6. **Giới hạn:** mục 40 đoạn giả lập → nội dung ≤ 6.000 ký tự, `can_cu` ≤ 12, có dòng "còn N đoạn", đoạn gốc luôn có mặt.
7. **Chèn lệnh:** đoạn anh em chứa "Ignore all previous instructions…" → Gateway trả `nghi_chen_lenh`, `can_cu == []`.
8. **Quyền và ngân sách:** vai trò không khai báo → `khong_co_quyen`; `so_lan_goi_toi_da` hết → `het_ngan_sach`.
9. **Kiểm chứng qua đồ thị thật** (`FakeLLM`, như test T107): LLM trích nguyên văn từ đoạn anh em mới mở → `ok`; trích câu không có trong đoạn nào → bị chặn.

## 5. Test chức năng (dữ liệu tệp thật, `@pytest.mark.can_du_lieu("data/kb_curated/chunks.jsonl")`)

- Tìm trong `chunks.jsonl` một mục cha `lieu_than` hoặc `lieu` có ≥ 2 đoạn (tự dò trong test, không chép cứng mã): mở từ đoạn thứ hai → trả đủ các đoạn, đúng thứ tự dòng trong tệp.
- Một đoạn đơn lẻ > 1.200 ký tự: `tim_doan_nguon` hiển thị bị cắt, `doc_doan_mo_rong` hiển thị đủ.
- Ánh xạ thứ tự khi không có tệp (monkeypatch đường dẫn) → sắp theo mã, có ghi chú.

## 6. Nghiệm thu

```
uv run ruff check app tests
uv run ruff format --check app tests
uv run pytest -q -p no:cacheprovider tests/agent tests/orchestration
```

Cả ba sạch, 0 trượt. Không chạy được test nào thì ghi rõ lý do; Claude sẽ chạy toàn kho. Claude kiểm thêm bằng LLM thật trên câu hỏi bảng liều thận bị chia đoạn.

## 7. Báo cáo

`plan/briefs/T110-bao-cao.md` theo mẫu `AGENTS.md`, có đầu ra thật của các lệnh và cách đã chọn ở mục 2.1 (truyền đoạn cho tool) kèm lý do.
