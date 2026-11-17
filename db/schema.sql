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
    ca_id text NOT NULL UNIQUE,
    mo_ta_ngan text NOT NULL,
    co_dia jsonb NOT NULL,
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text
);

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
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text
);

CREATE TABLE IF NOT EXISTS nghiep_vu.y_lenh (
    y_lenh_id text PRIMARY KEY,
    khoa_ke_don text NOT NULL,
    luong_duyet text NOT NULL CHECK (luong_duyet IN ('truc_tiep', 'hau_kiem')),
    muc_uu_tien text,
    thoi_diem_ke timestamptz NOT NULL,
    dot_dieu_tri_id text NOT NULL REFERENCES nghiep_vu.dot_dieu_tri,
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text
);

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
    y_lenh_id text REFERENCES nghiep_vu.y_lenh,
    dot_dieu_tri_id text NOT NULL REFERENCES nghiep_vu.dot_dieu_tri,
    thuoc_dang_dung boolean NOT NULL,
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text,
    CHECK (COALESCE(length(trim(thuoc_id)), 0) > 0 OR COALESCE(length(trim(ten_tu_do)), 0) > 0)
);

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
    ca_id text NOT NULL REFERENCES nghiep_vu.dot_dieu_tri(ca_id),
    van_ban_bat_thuong boolean NOT NULL,
    ghi_chu text,
    nap_luc timestamptz DEFAULT now(),
    nguon_tep text
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
    ca_id text NOT NULL REFERENCES nghiep_vu.dot_dieu_tri(ca_id),
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
