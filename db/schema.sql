CREATE SCHEMA IF NOT EXISTS nghiep_vu;
CREATE SCHEMA IF NOT EXISTS tri_thuc;
-- Cài mới ngay đầu file, vào lược đồ của task để không tạo đối tượng trong public.
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA tri_thuc;

-- RLS không có policy: khoá công khai bị từ chối mặc định.
-- Bộ nạp dùng kết nối PostgreSQL trực tiếp với tài khoản có quyền thích hợp.
-- Không tạo/sửa/xoá đối tượng trong các lược đồ hệ thống của Supabase.
-- Kiểu vector được tìm cả trong lược đồ extensions khi Supabase đã bật sẵn.
SELECT set_config(
    'search_path',
    format('tri_thuc, nghiep_vu, %I, pg_catalog', n.nspname),
    true
)
FROM pg_extension e JOIN pg_namespace n ON n.oid = e.extnamespace
WHERE e.extname = 'vector';

CREATE TABLE IF NOT EXISTS tri_thuc.hoat_chat (
    hoat_chat_id text PRIMARY KEY,
    ten_hoat_chat text NOT NULL,
    ten_quoc_te text,
    ma_atc text,
    nhom_duoc_ly text,
    thanh_phan jsonb,
    can_duyet boolean,
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text
);

CREATE TABLE IF NOT EXISTS nghiep_vu.nguoi_benh (
    nguoi_benh_id text PRIMARY KEY,
    tuoi integer CHECK (tuoi BETWEEN 0 AND 120),
    gioi_tinh text CHECK (gioi_tinh IN ('nam', 'nu')),
    tinh_trang_di_ung jsonb NOT NULL CHECK (tinh_trang_di_ung->>'trang_thai' IN ('co_di_ung', 'khong_di_ung_da_hoi', 'chua_co_thong_tin')),
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text
);

CREATE TABLE IF NOT EXISTS nghiep_vu.dot_dieu_tri (
    dot_dieu_tri_id text PRIMARY KEY,
    khoa_dieu_tri text NOT NULL,
    loai_dieu_tri text NOT NULL CHECK (loai_dieu_tri IN ('noi_tru', 'ngoai_tru')),
    thoi_diem_bat_dau timestamptz NOT NULL,
    nguoi_benh_id text NOT NULL REFERENCES nghiep_vu.nguoi_benh,
    thu_tu integer,
    thoi_diem_ket_thuc timestamptz,
    so_ngay_dieu_tri integer,
    hinh_thuc_vao text,
    lich_su_khoa jsonb,
    ly_do_vao_vien text,
    benh_su text,
    tien_su jsonb,
    kham_benh text,
    tom_tat text,
    tong_ket text,
    tuoi_luc_vao integer,
    co_dia jsonb NOT NULL,
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text,
    UNIQUE (nguoi_benh_id, thu_tu)
);

-- Chỉ khối thêm cột T45 dưới đây có thể áp dụng lại an toàn cho kho đã có dữ liệu.
-- Tệp này không nâng cấp lược đồ cũ trước T40.
ALTER TABLE nghiep_vu.nguoi_benh
    ADD COLUMN IF NOT EXISTS ho_ten text CHECK (ho_ten IS NULL OR length(trim(ho_ten)) > 0),
    ADD COLUMN IF NOT EXISTS ngay_sinh date,
    ADD COLUMN IF NOT EXISTS dan_toc text CHECK (dan_toc IN ('Kinh', 'Tày', 'Mường', 'Nùng', 'Hoa')),
    ADD COLUMN IF NOT EXISTS ngoai_kieu text,
    ADD COLUMN IF NOT EXISTS nghe_nghiep text,
    ADD COLUMN IF NOT EXISTS dia_chi jsonb CHECK (dia_chi IS NULL OR (jsonb_typeof(dia_chi) = 'object' AND dia_chi ?& ARRAY['so_nha', 'thon_pho', 'xa_phuong', 'huyen', 'tinh_thanh'])),
    ADD COLUMN IF NOT EXISTS doi_tuong text CHECK (doi_tuong IN ('bhyt', 'thu_phi', 'mien', 'khac')),
    ADD COLUMN IF NOT EXISTS bhyt jsonb CHECK (bhyt IS NULL OR (jsonb_typeof(bhyt) = 'object' AND bhyt ?& ARRAY['so_the', 'gia_tri_den'] AND bhyt->>'so_the' ~ '^[A-Z]{2}[0-9]{13}$' AND bhyt->>'gia_tri_den' ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$')),
    ADD COLUMN IF NOT EXISTS nguoi_bao_tin jsonb CHECK (nguoi_bao_tin IS NULL OR (jsonb_typeof(nguoi_bao_tin) = 'object' AND nguoi_bao_tin ?& ARRAY['ho_ten', 'quan_he', 'dien_thoai'] AND nguoi_bao_tin->>'dien_thoai' ~ '^0900 000 0[0-9]{2}$')),
    ADD COLUMN IF NOT EXISTS bo_me jsonb CHECK (bo_me IS NULL OR (tuoi < 16 AND jsonb_typeof(bo_me) = 'object' AND bo_me ?& ARRAY['bo', 'me'])),
    ADD COLUMN IF NOT EXISTS chieu_cao_cm double precision CHECK (chieu_cao_cm > 0),
    ADD COLUMN IF NOT EXISTS can_nang_kg double precision CHECK (can_nang_kg > 0),
    ADD COLUMN IF NOT EXISTS nhom_mau text CHECK (nhom_mau IN ('A', 'B', 'AB', 'O'));

ALTER TABLE nghiep_vu.dot_dieu_tri
    ADD COLUMN IF NOT EXISTS noi_gioi_thieu text CHECK (noi_gioi_thieu IN ('co_quan_y_te', 'tu_den', 'khac')),
    ADD COLUMN IF NOT EXISTS tuyen_chuyen_den text,
    ADD COLUMN IF NOT EXISTS vao_khoa_luc timestamptz CHECK (vao_khoa_luc >= thoi_diem_bat_dau),
    ADD COLUMN IF NOT EXISTS so_giuong text,
    ADD COLUMN IF NOT EXISTS so_luu_tru text CHECK (so_luu_tru ~ '^LT-2026-[0-9]{5}$'),
    ADD COLUMN IF NOT EXISTS ma_yt text,
    ADD COLUMN IF NOT EXISTS ra_vien jsonb CHECK (ra_vien IS NULL OR (thoi_diem_ket_thuc IS NOT NULL AND jsonb_typeof(ra_vien) = 'object' AND ra_vien ?& ARRAY['hinh_thuc', 'chuyen_vien_den', 'ly_do'] AND ra_vien->>'hinh_thuc' IN ('ra_vien', 'xin_ve', 'bo_ve', 'dua_ve', 'chuyen_vien'))),
    ADD COLUMN IF NOT EXISTS bac_si_dieu_tri text CHECK (bac_si_dieu_tri = 'Bác sĩ điều trị');

CREATE TABLE IF NOT EXISTS nghiep_vu.di_ung (
    di_ung_id text PRIMARY KEY,
    tac_nhan text NOT NULL,
    loai_tac_nhan text NOT NULL CHECK (loai_tac_nhan IN ('thuoc', 'thuc_an', 'khac')),
    hoat_chat_id text REFERENCES tri_thuc.hoat_chat,
    nhom_duoc_ly text,
    phan_ung text,
    muc_do text,
    nguoi_benh_id text NOT NULL REFERENCES nghiep_vu.nguoi_benh,
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text
);

CREATE TABLE IF NOT EXISTS nghiep_vu.thuoc (
    thuoc_id text PRIMARY KEY,
    ten_thuoc text NOT NULL,
    ham_luong text,
    duong_dung text,
    la_thuoc_nguy_co_cao boolean NOT NULL,
    la_khang_sinh boolean NOT NULL,
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text
);

CREATE TABLE IF NOT EXISTS nghiep_vu.thuoc_hoat_chat (
    thuoc_id text NOT NULL REFERENCES nghiep_vu.thuoc,
    hoat_chat_id text NOT NULL REFERENCES tri_thuc.hoat_chat,
    ham_luong_thanh_phan double precision,
    don_vi text,
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text,
    PRIMARY KEY (thuoc_id, hoat_chat_id)
);

CREATE TABLE IF NOT EXISTS nghiep_vu.chan_doan (
    chan_doan_id text PRIMARY KEY,
    ma_icd10 text,
    noi_dung text NOT NULL,
    loai text NOT NULL CHECK (loai IN ('chinh', 'kem')),
    dot_dieu_tri_id text NOT NULL REFERENCES nghiep_vu.dot_dieu_tri,
    thoi_diem timestamptz,
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text
);

CREATE TABLE IF NOT EXISTS nghiep_vu.sinh_hieu (
    sinh_hieu_id text PRIMARY KEY,
    loai text NOT NULL,
    gia_tri double precision NOT NULL,
    don_vi text NOT NULL,
    thoi_diem_do timestamptz NOT NULL,
    dot_dieu_tri_id text NOT NULL REFERENCES nghiep_vu.dot_dieu_tri,
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text
);

CREATE TABLE IF NOT EXISTS nghiep_vu.ket_qua_xet_nghiem (
    xet_nghiem_id text PRIMARY KEY,
    ma_xet_nghiem text NOT NULL,
    ten_xet_nghiem text NOT NULL,
    gia_tri_so double precision,
    gia_tri_text text,
    don_vi text,
    nguong_duoi double precision,
    nguong_tren double precision,
    thoi_diem_ket_qua timestamptz NOT NULL,
    dot_dieu_tri_id text NOT NULL REFERENCES nghiep_vu.dot_dieu_tri,
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text,
    CHECK (gia_tri_so IS NOT NULL OR COALESCE(length(trim(gia_tri_text)), 0) > 0)
);

CREATE TABLE IF NOT EXISTS nghiep_vu.vi_sinh (
    vi_sinh_id text PRIMARY KEY,
    benh_pham text NOT NULL,
    vi_khuan text,
    thoi_diem_lay_mau timestamptz NOT NULL,
    dot_dieu_tri_id text NOT NULL REFERENCES nghiep_vu.dot_dieu_tri,
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text
);

CREATE TABLE IF NOT EXISTS nghiep_vu.khang_sinh_do (
    vi_sinh_id text NOT NULL REFERENCES nghiep_vu.vi_sinh,
    hoat_chat_id text NOT NULL REFERENCES tri_thuc.hoat_chat,
    ket_qua text NOT NULL CHECK (ket_qua IN ('S', 'I', 'R')),
    mic double precision,
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text,
    PRIMARY KEY (vi_sinh_id, hoat_chat_id)
);

CREATE TABLE IF NOT EXISTS nghiep_vu.dien_bien (
    dien_bien_id text PRIMARY KEY,
    loai_ho_so text NOT NULL,
    noi_dung text NOT NULL,
    thoi_diem_ghi timestamptz NOT NULL,
    dot_dieu_tri_id text NOT NULL REFERENCES nghiep_vu.dot_dieu_tri,
    nguoi_ghi_vai_tro text,
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text
);

CREATE TABLE IF NOT EXISTS nghiep_vu.y_lenh (
    y_lenh_id text PRIMARY KEY,
    ca_id text UNIQUE,
    mo_ta_ngan text,
    vai_tro_nguoi_ke text CHECK (vai_tro_nguoi_ke IN ('bac_si_dieu_tri', 'bac_si_truc', 'hoi_chan')),
    loai text CHECK (loai IN ('thuong_quy', 'cap_cuu', 'khi_can', 'hoi_chan')),
    trang_thai text NOT NULL CHECK (trang_thai IN ('cho_duyet', 'da_duyet', 'dang_thuc_hien', 'ngung', 'hoan_tat')),
    thay_the_y_lenh_id text REFERENCES nghiep_vu.y_lenh(y_lenh_id) DEFERRABLE INITIALLY DEFERRED,
    ly_do_ngung text,
    thoi_diem_ngung timestamptz,
    khoa_ke_don text NOT NULL,
    luong_duyet text NOT NULL CHECK (luong_duyet IN ('truc_tiep', 'hau_kiem')),
    muc_uu_tien text,
    thoi_diem_ke timestamptz NOT NULL,
    dot_dieu_tri_id text NOT NULL REFERENCES nghiep_vu.dot_dieu_tri,
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text,
    UNIQUE (y_lenh_id, ca_id)
);

-- Khoá kép bảo đảm liên kết phiếu/y lệnh không vượt sang đợt khác.
CREATE UNIQUE INDEX IF NOT EXISTS y_lenh_id_dot_unique
ON nghiep_vu.y_lenh(y_lenh_id, dot_dieu_tri_id);

CREATE TABLE IF NOT EXISTS nghiep_vu.phieu_dieu_tri (
    phieu_dieu_tri_id text PRIMARY KEY,
    dot_dieu_tri_id text NOT NULL REFERENCES nghiep_vu.dot_dieu_tri,
    ngay_dieu_tri integer NOT NULL CHECK (ngay_dieu_tri >= 1),
    thoi_diem_lap timestamptz NOT NULL,
    vai_tro_nguoi_lap text NOT NULL CHECK (vai_tro_nguoi_lap IN ('bac_si_dieu_tri', 'bac_si_truc', 'hoi_chan')),
    dien_bien text NOT NULL,
    danh_gia text NOT NULL,
    huong_xu_tri text NOT NULL,
    che_do_cham_soc text,
    che_do_an text NOT NULL,
    theo_doi jsonb NOT NULL CHECK (jsonb_typeof(theo_doi) = 'array'),
    dan_do text,
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text,
    UNIQUE (phieu_dieu_tri_id, dot_dieu_tri_id)
);

CREATE TABLE IF NOT EXISTS nghiep_vu.phieu_y_lenh (
    phieu_dieu_tri_id text NOT NULL,
    y_lenh_id text NOT NULL,
    dot_dieu_tri_id text NOT NULL,
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text,
    PRIMARY KEY (phieu_dieu_tri_id, y_lenh_id),
    FOREIGN KEY (phieu_dieu_tri_id, dot_dieu_tri_id) REFERENCES nghiep_vu.phieu_dieu_tri(phieu_dieu_tri_id, dot_dieu_tri_id),
    FOREIGN KEY (y_lenh_id, dot_dieu_tri_id) REFERENCES nghiep_vu.y_lenh(y_lenh_id, dot_dieu_tri_id)
);
CREATE INDEX IF NOT EXISTS phieu_dieu_tri_dot_idx ON nghiep_vu.phieu_dieu_tri(dot_dieu_tri_id);
CREATE INDEX IF NOT EXISTS phieu_y_lenh_dot_idx ON nghiep_vu.phieu_y_lenh(dot_dieu_tri_id);
REVOKE ALL ON nghiep_vu.phieu_dieu_tri, nghiep_vu.phieu_y_lenh FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        EXECUTE 'REVOKE ALL ON nghiep_vu.phieu_dieu_tri, nghiep_vu.phieu_y_lenh FROM anon';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        EXECUTE 'REVOKE ALL ON nghiep_vu.phieu_dieu_tri, nghiep_vu.phieu_y_lenh FROM authenticated';
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS nghiep_vu.chi_tiet_y_lenh (
    chi_tiet_y_lenh_id text PRIMARY KEY,
    thuoc_id text REFERENCES nghiep_vu.thuoc,
    ten_tu_do text,
    loai_san_pham text NOT NULL CHECK (loai_san_pham IN ('thuoc', 'tpcn', 'dinh_duong', 'khac')),
    lieu_moi_lan double precision,
    don_vi_lieu text,
    tan_suat text,
    so_lan_moi_ngay integer,
    khoang_cach_gio double precision,
    duong_dung text,
    cach_dung text,
    bat_dau timestamptz NOT NULL,
    ket_thuc timestamptz,
    nguon_thuoc text,
    trang_thai_dong text NOT NULL CHECK (trang_thai_dong IN ('active', 'pending', 'discontinued', 'completed')),
    y_lenh_id text NOT NULL REFERENCES nghiep_vu.y_lenh,
    dot_dieu_tri_id text NOT NULL REFERENCES nghiep_vu.dot_dieu_tri,
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text,
    CHECK (COALESCE(length(trim(thuoc_id)), 0) > 0 OR COALESCE(length(trim(ten_tu_do)), 0) > 0)
);

-- Chạy với quyền của bên gọi để giữ hiệu lực RLS của bảng nguồn.
CREATE OR REPLACE VIEW nghiep_vu.v_thuoc_dang_dung WITH (security_invoker = true) AS
SELECT ct.*
FROM nghiep_vu.chi_tiet_y_lenh ct
JOIN nghiep_vu.y_lenh yl ON yl.y_lenh_id = ct.y_lenh_id
WHERE ct.trang_thai_dong = 'active'
  AND yl.trang_thai IN ('da_duyet', 'dang_thuc_hien');
REVOKE ALL ON nghiep_vu.v_thuoc_dang_dung FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        EXECUTE 'REVOKE ALL ON nghiep_vu.v_thuoc_dang_dung FROM anon';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        EXECUTE 'REVOKE ALL ON nghiep_vu.v_thuoc_dang_dung FROM authenticated';
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS nghiep_vu.lich_dung (
    chi_tiet_y_lenh_id text NOT NULL REFERENCES nghiep_vu.chi_tiet_y_lenh,
    thu_tu integer NOT NULL,
    thoi_diem_du_kien timestamptz NOT NULL,
    lieu double precision NOT NULL,
    don_vi text NOT NULL,
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text,
    PRIMARY KEY (chi_tiet_y_lenh_id, thu_tu)
);

-- Các bảng lan_tham_dinh, nhan_dinh, nhan_dinh_thuoc, can_cu là đáp án mẫu (gold) từ data/gold,
-- không phải kết quả thẩm định của hệ thống hay quyết định dược sĩ; không ghi kết quả hệ thống vào đây.
CREATE TABLE IF NOT EXISTS nghiep_vu.lan_tham_dinh (
    tham_dinh_id text PRIMARY KEY,
    y_lenh_id text NOT NULL REFERENCES nghiep_vu.y_lenh,
    ca_id text NOT NULL REFERENCES nghiep_vu.y_lenh(ca_id),
    van_ban_bat_thuong boolean NOT NULL,
    ghi_chu text,
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text,
    FOREIGN KEY (y_lenh_id, ca_id) REFERENCES nghiep_vu.y_lenh(y_lenh_id, ca_id)
);

CREATE TABLE IF NOT EXISTS nghiep_vu.nhan_dinh (
    nhan_dinh_id text PRIMARY KEY,
    tham_dinh_id text NOT NULL REFERENCES nghiep_vu.lan_tham_dinh,
    yeu_to integer NOT NULL CHECK (yeu_to BETWEEN 1 AND 7),
    ket_luan text NOT NULL CHECK (ket_luan IN ('dat', 'can_xem', 'khong_du_du_lieu', 'ngoai_hdsd')),
    muc_do text CHECK (muc_do IN ('nghiem_trong', 'can_luu_y', 'thong_tin')),
    mo_ta text NOT NULL,
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text
);

CREATE TABLE IF NOT EXISTS nghiep_vu.nhan_dinh_thuoc (
    nhan_dinh_id text NOT NULL REFERENCES nghiep_vu.nhan_dinh,
    chi_tiet_y_lenh_id text NOT NULL REFERENCES nghiep_vu.chi_tiet_y_lenh,
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text,
    PRIMARY KEY (nhan_dinh_id, chi_tiet_y_lenh_id)
);

CREATE TABLE IF NOT EXISTS nghiep_vu.can_cu (
    can_cu_id text PRIMARY KEY,
    nhan_dinh_id text NOT NULL REFERENCES nghiep_vu.nhan_dinh,
    loai text NOT NULL CHECK (loai IN ('du_lieu', 'tinh_toan', 'tai_lieu')),
    ban_ghi_id text,
    mo_ta text NOT NULL,
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text
);

CREATE TABLE IF NOT EXISTS nghiep_vu.phan_hoi (
    thoi_diem timestamptz NOT NULL,
    ca_id text NOT NULL REFERENCES nghiep_vu.y_lenh(ca_id),
    ma_luat text NOT NULL,
    yeu_to integer NOT NULL CHECK (yeu_to BETWEEN 1 AND 7),
    chi_tiet_y_lenh_id jsonb NOT NULL,
    phan_hoi text NOT NULL CHECK (phan_hoi IN ('dong_y', 'bac_bo', 'can_sua')),
    nhom_ly_do text,
    ly_do text,
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text,
    PRIMARY KEY (ca_id, ma_luat, thoi_diem)
);

ALTER TABLE nghiep_vu.phan_hoi
    ADD COLUMN IF NOT EXISTS nguoi_dung_id text;

CREATE TABLE IF NOT EXISTS nghiep_vu.hoi_thoai (
    id bigserial PRIMARY KEY,
    thoi_diem timestamptz NOT NULL,
    ca_id text NOT NULL,
    cau_hoi text NOT NULL,
    tra_loi jsonb NOT NULL,
    nguoi_dung_id text,
    phien_id text
);
CREATE INDEX IF NOT EXISTS hoi_thoai_nguoi_dung_ca_thoi_diem_idx
    ON nghiep_vu.hoi_thoai (nguoi_dung_id, ca_id, thoi_diem);
REVOKE ALL ON nghiep_vu.hoi_thoai FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        EXECUTE 'REVOKE ALL ON nghiep_vu.hoi_thoai FROM anon';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        EXECUTE 'REVOKE ALL ON nghiep_vu.hoi_thoai FROM authenticated';
    END IF;
END
$$;

-- Kết quả thẩm định của hệ thống khi chạy ở chế độ DB (tách biệt với các bảng đáp án mẫu gold).
CREATE TABLE IF NOT EXISTS nghiep_vu.ket_qua_tham_dinh (
    ket_qua_id text PRIMARY KEY,
    ca_id text NOT NULL REFERENCES nghiep_vu.y_lenh(ca_id),
    thoi_diem timestamptz NOT NULL,
    phien_ban_luat text NOT NULL,
    so_luat_da_chay integer NOT NULL CHECK (so_luat_da_chay >= 0),
    che_do text NOT NULL CHECK (che_do IN ('file', 'db')),
    tom_tat jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS ket_qua_tham_dinh_ca_thoi_diem_idx
    ON nghiep_vu.ket_qua_tham_dinh (ca_id, thoi_diem DESC, ket_qua_id DESC);

CREATE TABLE IF NOT EXISTS nghiep_vu.ket_qua_nhan_dinh (
    ket_qua_id text NOT NULL REFERENCES nghiep_vu.ket_qua_tham_dinh(ket_qua_id) ON DELETE CASCADE,
    thu_tu integer NOT NULL CHECK (thu_tu >= 0),
    nhom text NOT NULL CHECK (nhom IN ('can_chu_y', 'dat')),
    nhan_dinh_id text NOT NULL,
    thuoc text NOT NULL,
    ma_luat text,
    yeu_to integer NOT NULL CHECK (yeu_to BETWEEN 1 AND 7),
    yeu_to_nhan text NOT NULL,
    ket_luan text NOT NULL CHECK (ket_luan IN ('dat', 'can_xem', 'khong_du_du_lieu', 'ngoai_hdsd')),
    ket_luan_nhan text NOT NULL,
    muc_do text CHECK (muc_do IS NULL OR muc_do IN ('nghiem_trong', 'can_luu_y', 'thong_tin')),
    muc_do_nhan text,
    nguon_goc_ma text NOT NULL CHECK (nguon_goc_ma IN ('luat', 'ai_da_kiem_chung', 'ai_chua_kiem_chung')),
    nguon_goc_nhan text NOT NULL,
    chi_tiet_y_lenh_id jsonb NOT NULL,
    nhan_xet text NOT NULL,
    can_cu jsonb NOT NULL,
    du_lieu_thieu jsonb NOT NULL,
    PRIMARY KEY (ket_qua_id, thu_tu)
);
REVOKE ALL ON nghiep_vu.ket_qua_tham_dinh, nghiep_vu.ket_qua_nhan_dinh FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        EXECUTE 'REVOKE ALL ON nghiep_vu.ket_qua_tham_dinh, nghiep_vu.ket_qua_nhan_dinh FROM anon';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        EXECUTE 'REVOKE ALL ON nghiep_vu.ket_qua_tham_dinh, nghiep_vu.ket_qua_nhan_dinh FROM authenticated';
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS tri_thuc.ten_thuoc (
    ten_thuoc text NOT NULL,
    hoat_chat_id text NOT NULL REFERENCES tri_thuc.hoat_chat,
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text,
    PRIMARY KEY (ten_thuoc, hoat_chat_id)
);

CREATE TABLE IF NOT EXISTS tri_thuc.tai_lieu (
    tai_lieu_id text PRIMARY KEY,
    nguon text NOT NULL,
    tang_tin_cay integer NOT NULL CHECK (tang_tin_cay BETWEEN 1 AND 4),
    giay_phep text NOT NULL,
    phien_ban_nguon text NOT NULL,
    set_id text NOT NULL,
    url_goc text NOT NULL,
    sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text
);

CREATE TABLE IF NOT EXISTS tri_thuc.doan_trich (
    doan_trich_id text PRIMARY KEY,
    tai_lieu_id text NOT NULL REFERENCES tri_thuc.tai_lieu,
    muc_cha_id text,
    nhom_nguon text NOT NULL,
    nguon text NOT NULL,
    tang_tin_cay integer NOT NULL CHECK (tang_tin_cay BETWEEN 1 AND 4),
    hoat_chat_ids jsonb NOT NULL,
    muc text NOT NULL,
    duong_dan_muc text NOT NULL,
    loai_noi_dung text NOT NULL CHECK (loai_noi_dung IN ('van_ban', 'bang', 'danh_sach', 'dong_bang')),
    ngon_ngu text NOT NULL CHECK (ngon_ngu IN ('vi', 'en')),
    phien_ban_nguon text,
    url_goc text,
    noi_dung_goc text NOT NULL,
    noi_dung_nhung text NOT NULL,
    embedding halfvec(2048),
    tu_khoa tsvector GENERATED ALWAYS AS (to_tsvector('simple'::regconfig, noi_dung_goc)) STORED,
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text
);

CREATE INDEX IF NOT EXISTS doan_trich_embedding_hnsw ON tri_thuc.doan_trich USING hnsw (embedding halfvec_cosine_ops);
CREATE INDEX IF NOT EXISTS doan_trich_tu_khoa_gin ON tri_thuc.doan_trich USING gin (tu_khoa);

CREATE TABLE IF NOT EXISTS tri_thuc.quy_tac_lieu_than (
    quy_tac_id text PRIMARY KEY,
    ten_quoc_te text NOT NULL,
    nguon text NOT NULL,
    nguoi_duyet text,
    phien_ban text NOT NULL,
    ghi_chu text,
    crcl_tu double precision,
    crcl_den double precision,
    bao_gom_can_duoi boolean NOT NULL,
    can_chinh boolean NOT NULL,
    khuyen_cao text NOT NULL,
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text
);

-- Toàn bộ cặp DDInter giữ mã nguồn, không đoán ánh xạ sang hoạt chất nội bộ.
CREATE TABLE IF NOT EXISTS tri_thuc.tuong_tac_sang_loc (
    ddinter_id_a text NOT NULL,
    ddinter_id_b text NOT NULL,
    ten_thuoc_a text NOT NULL,
    ten_thuoc_b text NOT NULL,
    muc_do text NOT NULL CHECK (muc_do IN ('Major', 'Moderate', 'Minor', 'Unknown')),
    muc_do_nguon jsonb NOT NULL,
    co_muc_lech boolean NOT NULL,
    cac_tep_nguon jsonb NOT NULL,
    nguon text NOT NULL,
    tang_tin_cay integer NOT NULL CHECK (tang_tin_cay = 4),
    giay_phep text NOT NULL,
    trang_thai text NOT NULL CHECK (trang_thai = 'sang_loc'),
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text,
    PRIMARY KEY (ddinter_id_a, ddinter_id_b),
    CHECK (ddinter_id_a < ddinter_id_b)
);

-- Bản sao hai chỉ mục SQLite (ddinter.sqlite, tra_cuu.sqlite) phục vụ runtime đọc từ PostgreSQL.
CREATE TABLE IF NOT EXISTS tri_thuc.ddinter_cap (
    ddinter_id_a text NOT NULL,
    ddinter_id_b text NOT NULL,
    muc_do text NOT NULL,
    muc_do_so integer NOT NULL,
    co_che_json text NOT NULL,
    co_lech_muc integer NOT NULL,
    cac_muc_nguon_json text NOT NULL,
    ma_trang_cap_json text NOT NULL,
    hau_qua text,
    xu_tri text,
    tai_lieu_json text NOT NULL,
    url_goc text,
    PRIMARY KEY (ddinter_id_a, ddinter_id_b),
    CHECK (ddinter_id_a < ddinter_id_b)
);

CREATE TABLE IF NOT EXISTS tri_thuc.ddinter_thuoc (
    ddinter_id text PRIMARY KEY,
    ten text NOT NULL,
    da_cao_du integer NOT NULL
);

CREATE TABLE IF NOT EXISTS tri_thuc.ddinter_thuc_an (
    id bigserial PRIMARY KEY,
    ddinter_id text NOT NULL,
    thuc_an text NOT NULL,
    muc_do text NOT NULL,
    mo_ta text,
    xu_tri text,
    co_che_json text NOT NULL
);

CREATE TABLE IF NOT EXISTS tri_thuc.tra_cuu_hoat_chat (
    hoat_chat_id text PRIMARY KEY,
    ten_inn text NOT NULL,
    ten_viet text,
    rxcui text,
    ma_atc_json text NOT NULL,
    loai text NOT NULL,
    ddinter_id text UNIQUE,
    ddinter_cach_khop text
);

CREATE TABLE IF NOT EXISTS tri_thuc.tra_cuu_dong_nghia (
    khoa_chuan_hoa text NOT NULL,
    hoat_chat_id text NOT NULL REFERENCES tri_thuc.tra_cuu_hoat_chat,
    loai text NOT NULL,
    cach_khop text NOT NULL,
    PRIMARY KEY (khoa_chuan_hoa, hoat_chat_id, loai, cach_khop)
);

CREATE TABLE IF NOT EXISTS tri_thuc.tra_cuu_thuoc (
    khoa_ten_thuoc text NOT NULL,
    thuoc_id text PRIMARY KEY,
    ten_thuoc text NOT NULL,
    so_dang_ky text,
    dang_bao_che text
);
CREATE INDEX IF NOT EXISTS tra_cuu_thuoc_khoa_ten_idx
    ON tri_thuc.tra_cuu_thuoc (khoa_ten_thuoc, thuoc_id);

CREATE TABLE IF NOT EXISTS tri_thuc.tra_cuu_thuoc_thanh_phan (
    thuoc_id text NOT NULL REFERENCES tri_thuc.tra_cuu_thuoc,
    hoat_chat_id text NOT NULL REFERENCES tri_thuc.tra_cuu_hoat_chat,
    ham_luong double precision,
    don_vi text,
    PRIMARY KEY (thuoc_id, hoat_chat_id)
);

CREATE TABLE IF NOT EXISTS tri_thuc.tra_cuu_chuyen_ma_ca (
    ma_ca text PRIMARY KEY,
    hoat_chat_id text NOT NULL REFERENCES tri_thuc.tra_cuu_hoat_chat,
    cach_khop text NOT NULL
);

CREATE TABLE IF NOT EXISTS tri_thuc.tra_cuu_meta (
    phien_ban text,
    ngay_dung text,
    nguon_tep_json text,
    sha256_json text
);

-- Bảng luật lâm sàng D1-D7 và từ điển hoạt chất phục vụ runtime đọc từ PostgreSQL.
CREATE TABLE IF NOT EXISTS tri_thuc.bang_luat_meta (
    ma text PRIMARY KEY,
    ten text,
    phien_ban text,
    ngay text,
    trang_thai text,
    ghi_chu text,
    nguon text,
    phan_khac jsonb NOT NULL DEFAULT '{}'::jsonb,
    sha256_tep text NOT NULL,
    nap_luc timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tri_thuc.quy_tac_lieu_than_v2 (
    id bigserial PRIMARY KEY,
    danh_sach text NOT NULL CHECK (danh_sach IN ('quy_tac', 'quy_tac_cho_duyet')),
    thu_tu integer NOT NULL,
    ten_quoc_te text NOT NULL,
    hoat_chat_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
    hoat_chat_id text,
    chi_so text,
    trang_thai text,
    nguon text NOT NULL,
    nguoi_duyet text,
    muc jsonb NOT NULL,
    nguon_chi_tiet jsonb,
    phoi_hop text,
    bi_danh jsonb,
    phien_ban text NOT NULL,
    bo_sung jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS quy_tac_lieu_than_v2_hc_id_idx
    ON tri_thuc.quy_tac_lieu_than_v2 (hoat_chat_id);
CREATE INDEX IF NOT EXISTS quy_tac_lieu_than_v2_hc_ids_gin
    ON tri_thuc.quy_tac_lieu_than_v2 USING gin (hoat_chat_ids);

CREATE TABLE IF NOT EXISTS tri_thuc.quy_tac_lieu_than_khong_nguong (
    id bigserial PRIMARY KEY,
    thu_tu integer NOT NULL,
    hoat_chat_id text NOT NULL,
    loai text NOT NULL,
    ly_do text NOT NULL,
    set_id text,
    url text,
    phien_ban text NOT NULL,
    bo_sung jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS quy_tac_lieu_than_khong_nguong_hc_id_idx
    ON tri_thuc.quy_tac_lieu_than_khong_nguong (hoat_chat_id);

CREATE TABLE IF NOT EXISTS tri_thuc.quy_tac_gan (
    id bigserial PRIMARY KEY,
    thu_tu integer NOT NULL,
    ten_quoc_te text NOT NULL,
    hoat_chat_ids jsonb NOT NULL,
    hoat_chat_id text,
    phan_loai_gan jsonb NOT NULL,
    hanh_dong_nhan text NOT NULL,
    khuyen_cao text NOT NULL,
    trang_thai text,
    nguon_chi_tiet jsonb NOT NULL,
    phien_ban text,
    bo_sung jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS quy_tac_gan_hc_id_idx
    ON tri_thuc.quy_tac_gan (hoat_chat_id);
CREATE INDEX IF NOT EXISTS quy_tac_gan_hc_ids_gin
    ON tri_thuc.quy_tac_gan USING gin (hoat_chat_ids);

CREATE TABLE IF NOT EXISTS tri_thuc.nguong_xet_nghiem (
    id bigserial PRIMARY KEY,
    thu_tu integer NOT NULL,
    ten_quoc_te text,
    hoat_chat_ids jsonb NOT NULL,
    hoat_chat_id text,
    xet_nghiem text NOT NULL,
    dieu_kien jsonb NOT NULL,
    hanh_dong_nhan text NOT NULL,
    don_vi_nhan text,
    don_vi_trong_ca text,
    trang_thai text,
    kieu_dieu_kien text,
    muc_do_de_xuat text,
    dieu_kien_khac text,
    ghi_chu text,
    nguon_chi_tiet jsonb NOT NULL,
    phien_ban text,
    bo_sung jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS nguong_xet_nghiem_hc_id_idx
    ON tri_thuc.nguong_xet_nghiem (hoat_chat_id);
CREATE INDEX IF NOT EXISTS nguong_xet_nghiem_xn_idx
    ON tri_thuc.nguong_xet_nghiem (xet_nghiem);
CREATE INDEX IF NOT EXISTS nguong_xet_nghiem_hc_ids_gin
    ON tri_thuc.nguong_xet_nghiem USING gin (hoat_chat_ids);

CREATE TABLE IF NOT EXISTS tri_thuc.tuong_tac_benh (
    id bigserial PRIMARY KEY,
    thu_tu integer NOT NULL,
    hoat_chat_id text NOT NULL,
    ddinter_id text,
    ten_benh text NOT NULL,
    ma_icd10 jsonb NOT NULL,
    muc_do text NOT NULL,
    noi_dung text NOT NULL,
    url text,
    trang_thai text,
    phien_ban text,
    bo_sung jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS tuong_tac_benh_hc_id_idx
    ON tri_thuc.tuong_tac_benh (hoat_chat_id);

CREATE TABLE IF NOT EXISTS tri_thuc.anh_xa_benh_icd (
    id bigserial PRIMARY KEY,
    thu_tu integer NOT NULL,
    ten_benh text NOT NULL,
    ma_icd10 jsonb NOT NULL,
    ghi_chu text,
    khong_anh_xa boolean NOT NULL,
    hoat_chat_ids jsonb NOT NULL,
    hoat_chat_id text,
    so_dong_ddinter integer,
    muc_do_cao_nhat text,
    trang_thai text,
    phien_ban text,
    bo_sung jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS anh_xa_benh_icd_hc_id_idx
    ON tri_thuc.anh_xa_benh_icd (hoat_chat_id);
CREATE INDEX IF NOT EXISTS anh_xa_benh_icd_hc_ids_gin
    ON tri_thuc.anh_xa_benh_icd USING gin (hoat_chat_ids);

CREATE TABLE IF NOT EXISTS tri_thuc.tuong_tac_benh_khop_ca (
    id bigserial PRIMARY KEY,
    thu_tu integer NOT NULL,
    ca_id text NOT NULL,
    hoat_chat_id text NOT NULL,
    ten_benh text NOT NULL,
    ma_icd10_ca text,
    phien_ban text,
    bo_sung jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS tuong_tac_benh_khop_ca_hc_id_idx
    ON tri_thuc.tuong_tac_benh_khop_ca (hoat_chat_id);

CREATE TABLE IF NOT EXISTS tri_thuc.duong_dung_hop_le (
    id bigserial PRIMARY KEY,
    ma_dong text NOT NULL,
    thu_tu integer NOT NULL,
    hoat_chat_ids jsonb NOT NULL,
    hoat_chat_id text,
    nhom_dang_bao_che text NOT NULL,
    ten_nhom_dang text,
    duong_dung_hop_le jsonb NOT NULL,
    muc_chac_chan text,
    nguon jsonb NOT NULL,
    ghi_chu text,
    trang_thai text,
    phien_ban text,
    bo_sung jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS duong_dung_hop_le_ma_dong_idx
    ON tri_thuc.duong_dung_hop_le (ma_dong);
CREATE INDEX IF NOT EXISTS duong_dung_hop_le_hc_id_idx
    ON tri_thuc.duong_dung_hop_le (hoat_chat_id);
CREATE INDEX IF NOT EXISTS duong_dung_hop_le_hc_ids_gin
    ON tri_thuc.duong_dung_hop_le USING gin (hoat_chat_ids);

CREATE TABLE IF NOT EXISTS tri_thuc.chuan_hoa_duong_dung (
    id bigserial PRIMARY KEY,
    thu_tu integer NOT NULL,
    loai text NOT NULL CHECK (loai IN ('ma_chuan', 'khoa_sang_ma', 'tu_mo_ho', 'cach_viet_trong_66_ca', 'ma_fda_sang_ma_chuan')),
    khoa text NOT NULL,
    duong_dung text,
    gia_tri jsonb NOT NULL,
    phien_ban text
);
CREATE INDEX IF NOT EXISTS chuan_hoa_duong_dung_loai_khoa_idx
    ON tri_thuc.chuan_hoa_duong_dung (loai, khoa);

CREATE TABLE IF NOT EXISTS tri_thuc.lieu_toi_da (
    id bigserial PRIMARY KEY,
    ma_dong text NOT NULL,
    thu_tu integer NOT NULL,
    hoat_chat_ids jsonb NOT NULL,
    hoat_chat_id text,
    duong_dung jsonb NOT NULL,
    doi_tuong text NOT NULL,
    dieu_kien text,
    dieu_kien_khac text,
    loai_gioi_han text NOT NULL,
    lieu_toi_da_lan jsonb,
    lieu_toi_da_ngay jsonb,
    lieu_toi_da_tuan jsonb,
    theo_kg jsonb,
    thuoc_dung_cung_hoat_chat_ids jsonb,
    quy_doi_don_vi jsonb,
    ghi_chu text,
    nguon jsonb,
    trang_thai text,
    phien_ban text,
    bo_sung jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS lieu_toi_da_ma_dong_idx
    ON tri_thuc.lieu_toi_da (ma_dong);
CREATE INDEX IF NOT EXISTS lieu_toi_da_hc_id_idx
    ON tri_thuc.lieu_toi_da (hoat_chat_id);
CREATE INDEX IF NOT EXISTS lieu_toi_da_hc_ids_gin
    ON tri_thuc.lieu_toi_da USING gin (hoat_chat_ids);

CREATE TABLE IF NOT EXISTS tri_thuc.doi_tuong_dinh_nghia (
    ma text PRIMARY KEY,
    thu_tu integer NOT NULL,
    tuoi_tu double precision,
    tuoi_den double precision,
    tuoi_tren double precision,
    tuoi_duoi double precision,
    bao_gom_can_duoi boolean,
    bao_gom_can_tren boolean,
    tuoi_thang_tu double precision,
    tuoi_thang_den double precision,
    tuoi_ngay_tu double precision,
    tuoi_ngay_den double precision,
    can_nang_tu double precision,
    can_nang_den double precision,
    can_nang_tren double precision,
    can_nang_duoi double precision,
    dieu_kien_khac text,
    phien_ban text,
    bo_sung jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS tri_thuc.lieu_toi_da_khong_ghi (
    id bigserial PRIMARY KEY,
    thu_tu integer NOT NULL,
    hoat_chat_id text NOT NULL,
    co_dong_theo_nhom_dac_biet jsonb,
    ly_do text NOT NULL,
    phien_ban text,
    bo_sung jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS lieu_toi_da_khong_ghi_hc_id_idx
    ON tri_thuc.lieu_toi_da_khong_ghi (hoat_chat_id);

CREATE TABLE IF NOT EXISTS tri_thuc.lieu_toi_da_khong_ghi_duong_ca (
    id bigserial PRIMARY KEY,
    thu_tu integer NOT NULL,
    hoat_chat_ids jsonb NOT NULL,
    hoat_chat_id text,
    duong_dung text NOT NULL,
    phien_ban text,
    bo_sung jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS lieu_toi_da_khong_ghi_duong_ca_hc_id_idx
    ON tri_thuc.lieu_toi_da_khong_ghi_duong_ca (hoat_chat_id);
CREATE INDEX IF NOT EXISTS lieu_toi_da_khong_ghi_duong_ca_hc_ids_gin
    ON tri_thuc.lieu_toi_da_khong_ghi_duong_ca USING gin (hoat_chat_ids);

CREATE TABLE IF NOT EXISTS tri_thuc.canh_bao_doc_tinh (
    id bigserial PRIMARY KEY,
    thu_tu integer NOT NULL,
    loai text NOT NULL CHECK (loai IN ('doc_than', 'keo_dai_qt', 'khoang_dieu_tri_hep', 'doc_gan_livertox', 'khong_co_nguon')),
    hoat_chat_id text NOT NULL,
    nhom text,
    muc_nhan text,
    ma_xet_nghiem_nong_do jsonb,
    likelihood_score text,
    danh_sach text,
    ly_do text,
    nguon jsonb,
    trang_thai text,
    phien_ban text,
    bo_sung jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS canh_bao_doc_tinh_hc_id_loai_idx
    ON tri_thuc.canh_bao_doc_tinh (hoat_chat_id, loai);

CREATE TABLE IF NOT EXISTS tri_thuc.khang_sinh_han_che_nhom (
    ma_nhom text PRIMARY KEY,
    thu_tu integer NOT NULL,
    ten_nhom_van_ban text NOT NULL,
    yeu_cau text NOT NULL,
    trang_pdf integer NOT NULL,
    phien_ban text,
    bo_sung jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS tri_thuc.khang_sinh_han_che (
    id bigserial PRIMARY KEY,
    thu_tu integer NOT NULL,
    ten_trong_van_ban text NOT NULL,
    hoat_chat_ids jsonb NOT NULL,
    hoat_chat_id text,
    ma_nhom text NOT NULL REFERENCES tri_thuc.khang_sinh_han_che_nhom,
    trang_pdf integer NOT NULL,
    trang_thai text,
    phien_ban text,
    bo_sung jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS khang_sinh_han_che_hc_id_idx
    ON tri_thuc.khang_sinh_han_che (hoat_chat_id);
CREATE INDEX IF NOT EXISTS khang_sinh_han_che_hc_ids_gin
    ON tri_thuc.khang_sinh_han_che USING gin (hoat_chat_ids);

CREATE TABLE IF NOT EXISTS tri_thuc.khang_sinh_khong_anh_xa (
    id bigserial PRIMARY KEY,
    thu_tu integer NOT NULL,
    ten_trong_van_ban text NOT NULL,
    ma_nhom text NOT NULL REFERENCES tri_thuc.khang_sinh_han_che_nhom,
    trang_pdf integer NOT NULL,
    ly_do text NOT NULL,
    phien_ban text,
    bo_sung jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS tri_thuc.nhom_di_ung_cheo (
    ma_nhom text PRIMARY KEY,
    thu_tu integer NOT NULL,
    ten_nhom text NOT NULL,
    hoat_chat_ids jsonb NOT NULL,
    hoat_chat_id text,
    hoat_chat_lien_quan jsonb NOT NULL,
    huong text NOT NULL CHECK (huong IN ('hai_chieu', 'mot_chieu')),
    co_so text,
    nguon jsonb NOT NULL,
    ghi_chu text,
    trang_thai text,
    phien_ban text,
    bo_sung jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS nhom_di_ung_cheo_hc_id_idx
    ON tri_thuc.nhom_di_ung_cheo (hoat_chat_id);
CREATE INDEX IF NOT EXISTS nhom_di_ung_cheo_hc_ids_gin
    ON tri_thuc.nhom_di_ung_cheo USING gin (hoat_chat_ids);

CREATE TABLE IF NOT EXISTS tri_thuc.nhom_di_ung_anh_xa (
    ten_alias text PRIMARY KEY,
    thu_tu integer NOT NULL,
    hoat_chat_ids jsonb NOT NULL,
    hoat_chat_id text,
    ma_nhom text NOT NULL,
    phien_ban text,
    bo_sung jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS nhom_di_ung_anh_xa_hc_id_idx
    ON tri_thuc.nhom_di_ung_anh_xa (hoat_chat_id);
CREATE INDEX IF NOT EXISTS nhom_di_ung_anh_xa_hc_ids_gin
    ON tri_thuc.nhom_di_ung_anh_xa USING gin (hoat_chat_ids);

CREATE TABLE IF NOT EXISTS tri_thuc.danh_muc_hoat_chat_demo (
    hoat_chat_id text PRIMARY KEY,
    thu_tu integer NOT NULL,
    ten_inn text NOT NULL,
    ten_viet text,
    dong_nghia jsonb NOT NULL DEFAULT '[]'::jsonb,
    thanh_phan jsonb,
    nhom text,
    phien_ban text,
    bo_sung jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS tri_thuc.danh_muc_hoat_chat_demo_nhan (
    ten_goi text PRIMARY KEY,
    thu_tu integer NOT NULL,
    hoat_chat_ids jsonb NOT NULL,
    hoat_chat_id text,
    phien_ban text
);
CREATE INDEX IF NOT EXISTS danh_muc_hoat_chat_demo_nhan_hc_id_idx
    ON tri_thuc.danh_muc_hoat_chat_demo_nhan (hoat_chat_id);
CREATE INDEX IF NOT EXISTS danh_muc_hoat_chat_demo_nhan_hc_ids_gin
    ON tri_thuc.danh_muc_hoat_chat_demo_nhan USING gin (hoat_chat_ids);

CREATE TABLE IF NOT EXISTS tri_thuc.nhom_dieu_tri_trung (
    ma_nhom text PRIMARY KEY,
    thu_tu integer NOT NULL,
    ten text NOT NULL,
    tien_to_atc jsonb NOT NULL,
    tien_to_atc_loai_tru jsonb,
    muc_do text NOT NULL,
    ly_do text NOT NULL,
    nguon text NOT NULL,
    ngoai_le jsonb NOT NULL DEFAULT '[]'::jsonb,
    phien_ban text,
    bo_sung jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS tri_thuc.atc_bo_sung (
    hoat_chat_id text PRIMARY KEY,
    thu_tu integer NOT NULL,
    ma_atc jsonb NOT NULL,
    phien_ban text
);

REVOKE ALL ON
    tri_thuc.ddinter_cap,
    tri_thuc.ddinter_thuoc,
    tri_thuc.ddinter_thuc_an,
    tri_thuc.tra_cuu_hoat_chat,
    tri_thuc.tra_cuu_dong_nghia,
    tri_thuc.tra_cuu_thuoc,
    tri_thuc.tra_cuu_thuoc_thanh_phan,
    tri_thuc.tra_cuu_chuyen_ma_ca,
    tri_thuc.tra_cuu_meta
FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        EXECUTE 'REVOKE ALL ON tri_thuc.ddinter_cap, tri_thuc.ddinter_thuoc, tri_thuc.ddinter_thuc_an, tri_thuc.tra_cuu_hoat_chat, tri_thuc.tra_cuu_dong_nghia, tri_thuc.tra_cuu_thuoc, tri_thuc.tra_cuu_thuoc_thanh_phan, tri_thuc.tra_cuu_chuyen_ma_ca, tri_thuc.tra_cuu_meta FROM anon';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        EXECUTE 'REVOKE ALL ON tri_thuc.ddinter_cap, tri_thuc.ddinter_thuoc, tri_thuc.ddinter_thuc_an, tri_thuc.tra_cuu_hoat_chat, tri_thuc.tra_cuu_dong_nghia, tri_thuc.tra_cuu_thuoc, tri_thuc.tra_cuu_thuoc_thanh_phan, tri_thuc.tra_cuu_chuyen_ma_ca, tri_thuc.tra_cuu_meta FROM authenticated';
    END IF;
END
$$;

REVOKE ALL ON
    tri_thuc.bang_luat_meta,
    tri_thuc.quy_tac_lieu_than_v2,
    tri_thuc.quy_tac_lieu_than_khong_nguong,
    tri_thuc.quy_tac_gan,
    tri_thuc.nguong_xet_nghiem,
    tri_thuc.tuong_tac_benh,
    tri_thuc.anh_xa_benh_icd,
    tri_thuc.tuong_tac_benh_khop_ca,
    tri_thuc.duong_dung_hop_le,
    tri_thuc.chuan_hoa_duong_dung,
    tri_thuc.lieu_toi_da,
    tri_thuc.doi_tuong_dinh_nghia,
    tri_thuc.lieu_toi_da_khong_ghi,
    tri_thuc.lieu_toi_da_khong_ghi_duong_ca,
    tri_thuc.canh_bao_doc_tinh,
    tri_thuc.khang_sinh_han_che_nhom,
    tri_thuc.khang_sinh_han_che,
    tri_thuc.khang_sinh_khong_anh_xa,
    tri_thuc.nhom_di_ung_cheo,
    tri_thuc.nhom_di_ung_anh_xa,
    tri_thuc.danh_muc_hoat_chat_demo,
    tri_thuc.danh_muc_hoat_chat_demo_nhan,
    tri_thuc.nhom_dieu_tri_trung,
    tri_thuc.atc_bo_sung
FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        EXECUTE 'REVOKE ALL ON tri_thuc.bang_luat_meta, tri_thuc.quy_tac_lieu_than_v2, tri_thuc.quy_tac_lieu_than_khong_nguong, tri_thuc.quy_tac_gan, tri_thuc.nguong_xet_nghiem, tri_thuc.tuong_tac_benh, tri_thuc.anh_xa_benh_icd, tri_thuc.tuong_tac_benh_khop_ca, tri_thuc.duong_dung_hop_le, tri_thuc.chuan_hoa_duong_dung, tri_thuc.lieu_toi_da, tri_thuc.doi_tuong_dinh_nghia, tri_thuc.lieu_toi_da_khong_ghi, tri_thuc.lieu_toi_da_khong_ghi_duong_ca, tri_thuc.canh_bao_doc_tinh, tri_thuc.khang_sinh_han_che_nhom, tri_thuc.khang_sinh_han_che, tri_thuc.khang_sinh_khong_anh_xa, tri_thuc.nhom_di_ung_cheo, tri_thuc.nhom_di_ung_anh_xa, tri_thuc.danh_muc_hoat_chat_demo, tri_thuc.danh_muc_hoat_chat_demo_nhan, tri_thuc.nhom_dieu_tri_trung, tri_thuc.atc_bo_sung FROM anon';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        EXECUTE 'REVOKE ALL ON tri_thuc.bang_luat_meta, tri_thuc.quy_tac_lieu_than_v2, tri_thuc.quy_tac_lieu_than_khong_nguong, tri_thuc.quy_tac_gan, tri_thuc.nguong_xet_nghiem, tri_thuc.tuong_tac_benh, tri_thuc.anh_xa_benh_icd, tri_thuc.tuong_tac_benh_khop_ca, tri_thuc.duong_dung_hop_le, tri_thuc.chuan_hoa_duong_dung, tri_thuc.lieu_toi_da, tri_thuc.doi_tuong_dinh_nghia, tri_thuc.lieu_toi_da_khong_ghi, tri_thuc.lieu_toi_da_khong_ghi_duong_ca, tri_thuc.canh_bao_doc_tinh, tri_thuc.khang_sinh_han_che_nhom, tri_thuc.khang_sinh_han_che, tri_thuc.khang_sinh_khong_anh_xa, tri_thuc.nhom_di_ung_cheo, tri_thuc.nhom_di_ung_anh_xa, tri_thuc.danh_muc_hoat_chat_demo, tri_thuc.danh_muc_hoat_chat_demo_nhan, tri_thuc.nhom_dieu_tri_trung, tri_thuc.atc_bo_sung FROM authenticated';
    END IF;
END
$$;

ALTER TABLE tri_thuc.hoat_chat ENABLE ROW LEVEL SECURITY;
ALTER TABLE nghiep_vu.nguoi_benh ENABLE ROW LEVEL SECURITY;
ALTER TABLE nghiep_vu.dot_dieu_tri ENABLE ROW LEVEL SECURITY;
ALTER TABLE nghiep_vu.di_ung ENABLE ROW LEVEL SECURITY;
ALTER TABLE nghiep_vu.thuoc ENABLE ROW LEVEL SECURITY;
ALTER TABLE nghiep_vu.thuoc_hoat_chat ENABLE ROW LEVEL SECURITY;
ALTER TABLE nghiep_vu.chan_doan ENABLE ROW LEVEL SECURITY;
ALTER TABLE nghiep_vu.sinh_hieu ENABLE ROW LEVEL SECURITY;
ALTER TABLE nghiep_vu.ket_qua_xet_nghiem ENABLE ROW LEVEL SECURITY;
ALTER TABLE nghiep_vu.vi_sinh ENABLE ROW LEVEL SECURITY;
ALTER TABLE nghiep_vu.khang_sinh_do ENABLE ROW LEVEL SECURITY;
ALTER TABLE nghiep_vu.dien_bien ENABLE ROW LEVEL SECURITY;
ALTER TABLE nghiep_vu.y_lenh ENABLE ROW LEVEL SECURITY;
ALTER TABLE nghiep_vu.phieu_dieu_tri ENABLE ROW LEVEL SECURITY;
ALTER TABLE nghiep_vu.phieu_y_lenh ENABLE ROW LEVEL SECURITY;
ALTER TABLE nghiep_vu.chi_tiet_y_lenh ENABLE ROW LEVEL SECURITY;
ALTER TABLE nghiep_vu.lich_dung ENABLE ROW LEVEL SECURITY;
ALTER TABLE nghiep_vu.lan_tham_dinh ENABLE ROW LEVEL SECURITY;
ALTER TABLE nghiep_vu.nhan_dinh ENABLE ROW LEVEL SECURITY;
ALTER TABLE nghiep_vu.nhan_dinh_thuoc ENABLE ROW LEVEL SECURITY;
ALTER TABLE nghiep_vu.can_cu ENABLE ROW LEVEL SECURITY;
ALTER TABLE nghiep_vu.phan_hoi ENABLE ROW LEVEL SECURITY;
ALTER TABLE nghiep_vu.hoi_thoai ENABLE ROW LEVEL SECURITY;
ALTER TABLE nghiep_vu.ket_qua_tham_dinh ENABLE ROW LEVEL SECURITY;
ALTER TABLE nghiep_vu.ket_qua_nhan_dinh ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.ten_thuoc ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.tai_lieu ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.doan_trich ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.quy_tac_lieu_than ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.tuong_tac_sang_loc ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.ddinter_cap ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.ddinter_thuoc ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.ddinter_thuc_an ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.tra_cuu_hoat_chat ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.tra_cuu_dong_nghia ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.tra_cuu_thuoc ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.tra_cuu_thuoc_thanh_phan ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.tra_cuu_chuyen_ma_ca ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.tra_cuu_meta ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.bang_luat_meta ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.quy_tac_lieu_than_v2 ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.quy_tac_lieu_than_khong_nguong ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.quy_tac_gan ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.nguong_xet_nghiem ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.tuong_tac_benh ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.anh_xa_benh_icd ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.tuong_tac_benh_khop_ca ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.duong_dung_hop_le ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.chuan_hoa_duong_dung ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.lieu_toi_da ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.doi_tuong_dinh_nghia ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.lieu_toi_da_khong_ghi ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.lieu_toi_da_khong_ghi_duong_ca ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.canh_bao_doc_tinh ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.khang_sinh_han_che_nhom ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.khang_sinh_han_che ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.khang_sinh_khong_anh_xa ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.nhom_di_ung_cheo ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.nhom_di_ung_anh_xa ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.danh_muc_hoat_chat_demo ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.danh_muc_hoat_chat_demo_nhan ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.nhom_dieu_tri_trung ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.atc_bo_sung ENABLE ROW LEVEL SECURITY;
