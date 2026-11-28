CREATE TABLE IF NOT EXISTS nghiep_vu.vet_chay (
    ma_vet uuid PRIMARY KEY,
    bat_dau timestamptz NOT NULL,
    ket_thuc timestamptz NOT NULL,
    thoi_gian_ms double precision NOT NULL,
    loai text NOT NULL CHECK (loai IN ('hoi_dap', 'ai_review', 'danh_gia')),
    engine text NOT NULL,
    nguoi_dung_id text,
    vai_tro text,
    phien_id text,
    ca_bam text,
    phien_ban jsonb NOT NULL,
    trang_thai_cuoi text NOT NULL,
    tong_token_vao integer NOT NULL,
    tong_token_ra integer NOT NULL,
    chi_phi_uoc_tinh numeric NOT NULL,
    so_tool integer NOT NULL,
    so_bi_chan integer NOT NULL,
    ma_loi text,
    muc_noi_dung text NOT NULL CHECK (muc_noi_dung IN ('sieu_du_lieu', 'noi_dung_da_che', 'day_du')),
    vet_bi_cat boolean NOT NULL,
    so_khoa_la_bi_bo integer NOT NULL
);

CREATE TABLE IF NOT EXISTS nghiep_vu.vet_buoc (
    ma_vet uuid NOT NULL REFERENCES nghiep_vu.vet_chay(ma_vet) ON DELETE CASCADE,
    ma_buoc text NOT NULL,
    ma_buoc_cha text,
    loai text NOT NULL CHECK (loai IN ('node', 'llm', 'tool', 'kiem_chung', 'che_pii', 'chan_dau_vao', 'su_kien_bao_mat')),
    ten varchar(120) NOT NULL,
    bat_dau timestamptz NOT NULL,
    thoi_gian_ms double precision NOT NULL,
    trang_thai text NOT NULL,
    thuoc_tinh jsonb NOT NULL,
    noi_dung text,
    PRIMARY KEY (ma_vet, ma_buoc)
);

CREATE INDEX IF NOT EXISTS vet_chay_bat_dau_idx ON nghiep_vu.vet_chay (bat_dau DESC);
CREATE INDEX IF NOT EXISTS vet_chay_loai_engine_idx ON nghiep_vu.vet_chay (loai, engine, bat_dau DESC);
CREATE INDEX IF NOT EXISTS vet_chay_trang_thai_idx ON nghiep_vu.vet_chay (trang_thai_cuoi);
