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
REVOKE ALL ON nghiep_vu.phieu_dieu_tri, nghiep_vu.phieu_y_lenh FROM PUBLIC, anon, authenticated;

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
REVOKE ALL ON nghiep_vu.v_thuoc_dang_dung FROM PUBLIC, anon, authenticated;

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

-- Các dòng gold là đáp án kỳ vọng, không phải kết quả AI hay quyết định dược sĩ.
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
ALTER TABLE tri_thuc.ten_thuoc ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.tai_lieu ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.doan_trich ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.quy_tac_lieu_than ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.tuong_tac_sang_loc ENABLE ROW LEVEL SECURITY;
