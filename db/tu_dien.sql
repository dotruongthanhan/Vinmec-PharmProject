-- DDL cho phiên bản từ điển có bằng chứng nguồn.
CREATE SCHEMA IF NOT EXISTS tri_thuc;

CREATE TABLE IF NOT EXISTS tri_thuc.tu_dien_hoat_chat (
    phien_ban text NOT NULL,
    hoat_chat_id text NOT NULL,
    ten_inn text NOT NULL,
    ten_viet text NOT NULL,
    rxcui text CHECK (rxcui ~ '^[0-9]+$'),
    ma_atc text[] NOT NULL,
    ten_lop_atc text[] NOT NULL,
    loai text NOT NULL CHECK (
        loai IN ('thuoc', 'dich_truyen_dien_giai', 'sinh_pham', 'vitamin_khoang', 'duoc_lieu')
    ),
    nguon_ban_ghi_ids text[] NOT NULL CHECK (cardinality(nguon_ban_ghi_ids) > 0),
    ngay_dung date NOT NULL,
    PRIMARY KEY (phien_ban, hoat_chat_id)
);

CREATE TABLE IF NOT EXISTS tri_thuc.tu_dien_thuoc (
    phien_ban text NOT NULL,
    thuoc_id text NOT NULL,
    dav_id text NOT NULL,
    ten_thuoc text,
    khoa_chuan_hoa text NOT NULL,
    so_dang_ky text NOT NULL,
    ham_luong text,
    dang_bao_che text,
    duong_dung_goc text,
    con_hieu_luc boolean,
    url_hdsd text,
    trang_thai_tach text NOT NULL CHECK (trang_thai_tach IN ('tach_duoc', 'chua_khop')),
    ly_do_tach text,
    loai_san_pham text NOT NULL CHECK (loai_san_pham IN ('thuoc', 'duoc_lieu', 'sinh_pham')),
    trang_thai_tra text NOT NULL CHECK (
        trang_thai_tra IN ('du_thanh_phan', 'chua_khop', 'khong_co_du_lieu_tra')
    ),
    nguon_ban_ghi_ids text[] NOT NULL CHECK (cardinality(nguon_ban_ghi_ids) > 0),
    ngay_dung date NOT NULL,
    PRIMARY KEY (phien_ban, thuoc_id),
    UNIQUE (phien_ban, so_dang_ky)
);

CREATE TABLE IF NOT EXISTS tri_thuc.tu_dien_dong_nghia (
    phien_ban text NOT NULL,
    stt bigint NOT NULL,
    khoa_chuan_hoa text NOT NULL,
    hoat_chat_id text NOT NULL,
    loai text NOT NULL CHECK (loai IN ('inn', 'viet', 'muoi', 'biet_duoc', 'viet_tat')),
    nguon text NOT NULL,
    cach_khop text NOT NULL CHECK (cach_khop IN (
        'ma_chuan', 'bang_viet_quoc_te', 'rxnav_chinh_xac', 'them_e_cuoi', 'bang_vitamin',
        'nguoi_duyet', 'ngu_nghia_tu_nhan'
    )),
    nguon_ban_ghi_ids text[] NOT NULL CHECK (cardinality(nguon_ban_ghi_ids) > 0),
    ngay_dung date NOT NULL,
    PRIMARY KEY (phien_ban, stt),
    FOREIGN KEY (phien_ban, hoat_chat_id) REFERENCES tri_thuc.tu_dien_hoat_chat
);

CREATE TABLE IF NOT EXISTS tri_thuc.tu_dien_thanh_phan (
    phien_ban text NOT NULL,
    stt bigint NOT NULL,
    thuoc_id text NOT NULL,
    hoat_chat_id text NOT NULL,
    ham_luong double precision,
    don_vi text,
    dang_muoi text,
    cach_khop text NOT NULL CHECK (cach_khop IN (
        'ma_chuan', 'bang_viet_quoc_te', 'rxnav_chinh_xac', 'them_e_cuoi', 'bang_vitamin',
        'nguoi_duyet', 'ngu_nghia_tu_nhan'
    )),
    nguon_ban_ghi_ids text[] NOT NULL CHECK (cardinality(nguon_ban_ghi_ids) > 0),
    ngay_dung date NOT NULL,
    PRIMARY KEY (phien_ban, stt),
    FOREIGN KEY (phien_ban, thuoc_id) REFERENCES tri_thuc.tu_dien_thuoc,
    FOREIGN KEY (phien_ban, hoat_chat_id) REFERENCES tri_thuc.tu_dien_hoat_chat
);

CREATE TABLE IF NOT EXISTS tri_thuc.tu_dien_anh_xa (
    phien_ban text NOT NULL,
    stt bigint NOT NULL,
    nguon text NOT NULL,
    ma_ban_ghi_nguon text NOT NULL,
    ten_goc text NOT NULL,
    khoa_chuan_hoa text,
    hoat_chat_id text NOT NULL,
    cach_khop text NOT NULL CHECK (cach_khop IN (
        'ma_chuan', 'bang_viet_quoc_te', 'rxnav_chinh_xac', 'them_e_cuoi', 'bang_vitamin',
        'nguoi_duyet', 'ngu_nghia_tu_nhan'
    )),
    do_tin_cay text NOT NULL CHECK (do_tin_cay IN ('chinh_xac', 'da_duyet', 'ngu_nghia')),
    nguoi_duyet text,
    ghi_chu text,
    nguon_ban_ghi_ids text[] NOT NULL CHECK (cardinality(nguon_ban_ghi_ids) > 0),
    ngay_dung date NOT NULL,
    PRIMARY KEY (phien_ban, stt),
    FOREIGN KEY (phien_ban, hoat_chat_id) REFERENCES tri_thuc.tu_dien_hoat_chat
);

CREATE TABLE IF NOT EXISTS tri_thuc.tu_dien_hang_duyet (
    phien_ban text NOT NULL,
    khoa_chuan_hoa text NOT NULL,
    ten_goc_vi_du text NOT NULL,
    so_che_pham integer NOT NULL CHECK (so_che_pham >= 0),
    so_luot integer NOT NULL CHECK (so_luot >= so_che_pham),
    ly_do text NOT NULL,
    ung_vien jsonb NOT NULL CHECK (jsonb_typeof(ung_vien) = 'array'),
    nguon_ban_ghi_ids text[] NOT NULL CHECK (cardinality(nguon_ban_ghi_ids) > 0),
    PRIMARY KEY (phien_ban, khoa_chuan_hoa)
);

CREATE INDEX IF NOT EXISTS tu_dien_hoat_chat_rxcui_idx
    ON tri_thuc.tu_dien_hoat_chat (phien_ban, rxcui);
CREATE INDEX IF NOT EXISTS tu_dien_thuoc_khoa_idx
    ON tri_thuc.tu_dien_thuoc (phien_ban, khoa_chuan_hoa);
CREATE INDEX IF NOT EXISTS tu_dien_dong_nghia_khoa_idx
    ON tri_thuc.tu_dien_dong_nghia (phien_ban, khoa_chuan_hoa);
CREATE INDEX IF NOT EXISTS tu_dien_thanh_phan_thuoc_idx
    ON tri_thuc.tu_dien_thanh_phan (phien_ban, thuoc_id);
CREATE INDEX IF NOT EXISTS tu_dien_anh_xa_nguon_idx
    ON tri_thuc.tu_dien_anh_xa (phien_ban, nguon, ma_ban_ghi_nguon);
CREATE INDEX IF NOT EXISTS tu_dien_hang_duyet_uu_tien_idx
    ON tri_thuc.tu_dien_hang_duyet (phien_ban, so_che_pham DESC, khoa_chuan_hoa);

ALTER TABLE tri_thuc.tu_dien_hoat_chat ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.tu_dien_thuoc ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.tu_dien_dong_nghia ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.tu_dien_thanh_phan ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.tu_dien_anh_xa ENABLE ROW LEVEL SECURITY;
ALTER TABLE tri_thuc.tu_dien_hang_duyet ENABLE ROW LEVEL SECURITY;
