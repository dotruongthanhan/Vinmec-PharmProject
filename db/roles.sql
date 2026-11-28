-- Tạo vai trò DB quyền tối thiểu cho ứng dụng API (bvienx_app) và script nạp (bvienx_loader).
-- Chạy bằng psql dưới tài khoản chủ RDS; an toàn khi chạy lại nhiều lần.
-- Không chứa mật khẩu; đặt mật khẩu riêng ở cuối hướng dẫn bằng \password.
-- Lưu ý: khi thêm bảng mới vào db/schema.sql, cần chạy lại db/roles.sql để cấp GRANT và tạo policy RLS
-- (ALTER DEFAULT PRIVILEGES chỉ áp dụng cho quyền bảng/sequence, không tự tạo policy RLS).

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bvienx_app') THEN
        CREATE ROLE bvienx_app WITH
            LOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOINHERIT
            CONNECTION LIMIT 20;
    ELSE
        ALTER ROLE bvienx_app WITH
            LOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOINHERIT
            CONNECTION LIMIT 20;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bvienx_loader') THEN
        CREATE ROLE bvienx_loader WITH
            LOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOINHERIT;
    ELSE
        ALTER ROLE bvienx_loader WITH
            LOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOINHERIT;
    END IF;
END
$$;

ALTER ROLE bvienx_app SET statement_timeout = '15s';
ALTER ROLE bvienx_app SET idle_in_transaction_session_timeout = '30s';

REVOKE CREATE ON SCHEMA public FROM PUBLIC;

DO $$
BEGIN
    EXECUTE format('REVOKE ALL ON DATABASE %I FROM PUBLIC', current_database());
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), current_user);
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO bvienx_app, bvienx_loader', current_database());
END
$$;

GRANT USAGE ON SCHEMA tri_thuc, nghiep_vu TO bvienx_app, bvienx_loader;
REVOKE CREATE ON SCHEMA tri_thuc, nghiep_vu FROM bvienx_app, bvienx_loader;

-- Đưa quyền trên bảng về trạng thái sạch trước khi cấp lại đúng quyền tối thiểu.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA tri_thuc, nghiep_vu FROM bvienx_app;
REVOKE USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA tri_thuc, nghiep_vu FROM bvienx_app;

-- bvienx_app: chỉ SELECT trên toàn bộ tri_thuc và nghiep_vu (gồm bảng tạo sau).
GRANT SELECT ON ALL TABLES IN SCHEMA tri_thuc, nghiep_vu TO bvienx_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA tri_thuc GRANT SELECT ON TABLES TO bvienx_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA nghiep_vu GRANT SELECT ON TABLES TO bvienx_app;

-- bvienx_app: chỉ ghi đúng các bảng và thao tác mà đường chạy API sử dụng.
GRANT INSERT, UPDATE ON TABLE nghiep_vu.phan_hoi TO bvienx_app;
GRANT INSERT, DELETE ON TABLE nghiep_vu.hoi_thoai TO bvienx_app;
GRANT USAGE, SELECT ON SEQUENCE nghiep_vu.hoi_thoai_id_seq TO bvienx_app;
GRANT INSERT ON TABLE nghiep_vu.ket_qua_tham_dinh TO bvienx_app;
GRANT INSERT ON TABLE nghiep_vu.ket_qua_nhan_dinh TO bvienx_app;

-- bvienx_loader: nạp và thay thế dữ liệu kho tri_thuc và các bảng ca giả lập trong nghiep_vu.
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA tri_thuc TO bvienx_loader;
ALTER DEFAULT PRIVILEGES IN SCHEMA tri_thuc
    GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON TABLES TO bvienx_loader;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA tri_thuc TO bvienx_loader;
ALTER DEFAULT PRIVILEGES IN SCHEMA tri_thuc
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO bvienx_loader;

GRANT SELECT ON TABLE nghiep_vu.v_thuoc_dang_dung TO bvienx_loader;
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON TABLE
    nghiep_vu.nguoi_benh,
    nghiep_vu.dot_dieu_tri,
    nghiep_vu.di_ung,
    nghiep_vu.thuoc,
    nghiep_vu.thuoc_hoat_chat,
    nghiep_vu.chan_doan,
    nghiep_vu.sinh_hieu,
    nghiep_vu.ket_qua_xet_nghiem,
    nghiep_vu.vi_sinh,
    nghiep_vu.khang_sinh_do,
    nghiep_vu.dien_bien,
    nghiep_vu.y_lenh,
    nghiep_vu.phieu_dieu_tri,
    nghiep_vu.phieu_y_lenh,
    nghiep_vu.chi_tiet_y_lenh,
    nghiep_vu.lich_dung,
    nghiep_vu.lan_tham_dinh,
    nghiep_vu.nhan_dinh,
    nghiep_vu.nhan_dinh_thuoc,
    nghiep_vu.can_cu
TO bvienx_loader;

-- Policy RLS: schema.sql bật RLS trên toàn bộ 63 bảng tri_thuc và nghiep_vu; thiếu policy thì vai trò thường không đọc/ghi được.
DO $$
DECLARE
    tbl record;
    loader_nghiep_vu_tables text[] := ARRAY[
        'nguoi_benh',
        'dot_dieu_tri',
        'di_ung',
        'thuoc',
        'thuoc_hoat_chat',
        'chan_doan',
        'sinh_hieu',
        'ket_qua_xet_nghiem',
        'vi_sinh',
        'khang_sinh_do',
        'dien_bien',
        'y_lenh',
        'phieu_dieu_tri',
        'phieu_y_lenh',
        'chi_tiet_y_lenh',
        'lich_dung',
        'lan_tham_dinh',
        'nhan_dinh',
        'nhan_dinh_thuoc',
        'can_cu'
    ];
BEGIN
    FOR tbl IN
        SELECT schemaname, tablename
        FROM pg_tables
        WHERE schemaname IN ('tri_thuc', 'nghiep_vu')
        ORDER BY schemaname, tablename
    LOOP
        EXECUTE format(
            'DROP POLICY IF EXISTS bvienx_app_doc ON %I.%I',
            tbl.schemaname,
            tbl.tablename
        );
        EXECUTE format(
            'CREATE POLICY bvienx_app_doc ON %I.%I FOR SELECT TO bvienx_app USING (true)',
            tbl.schemaname,
            tbl.tablename
        );

        EXECUTE format(
            'DROP POLICY IF EXISTS bvienx_loader_nap ON %I.%I',
            tbl.schemaname,
            tbl.tablename
        );
        IF tbl.schemaname = 'tri_thuc' OR (
            tbl.schemaname = 'nghiep_vu'
            AND tbl.tablename::text = ANY(loader_nghiep_vu_tables)
        ) THEN
            EXECUTE format(
                'CREATE POLICY bvienx_loader_nap ON %I.%I FOR ALL TO bvienx_loader USING (true) WITH CHECK (true)',
                tbl.schemaname,
                tbl.tablename
            );
        END IF;
    END LOOP;
END
$$;

-- bvienx_app: policy ghi khớp đúng các bảng và thao tác đã GRANT ở trên.
DROP POLICY IF EXISTS bvienx_app_them ON nghiep_vu.phan_hoi;
CREATE POLICY bvienx_app_them ON nghiep_vu.phan_hoi
    FOR INSERT TO bvienx_app WITH CHECK (true);

DROP POLICY IF EXISTS bvienx_app_cap_nhat ON nghiep_vu.phan_hoi;
CREATE POLICY bvienx_app_cap_nhat ON nghiep_vu.phan_hoi
    FOR UPDATE TO bvienx_app USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS bvienx_app_them ON nghiep_vu.hoi_thoai;
CREATE POLICY bvienx_app_them ON nghiep_vu.hoi_thoai
    FOR INSERT TO bvienx_app WITH CHECK (true);

DROP POLICY IF EXISTS bvienx_app_xoa ON nghiep_vu.hoi_thoai;
CREATE POLICY bvienx_app_xoa ON nghiep_vu.hoi_thoai
    FOR DELETE TO bvienx_app USING (true);

DROP POLICY IF EXISTS bvienx_app_them ON nghiep_vu.ket_qua_tham_dinh;
CREATE POLICY bvienx_app_them ON nghiep_vu.ket_qua_tham_dinh
    FOR INSERT TO bvienx_app WITH CHECK (true);

DROP POLICY IF EXISTS bvienx_app_them ON nghiep_vu.ket_qua_nhan_dinh;
CREATE POLICY bvienx_app_them ON nghiep_vu.ket_qua_nhan_dinh
    FOR INSERT TO bvienx_app WITH CHECK (true);

-- Bước tiếp theo trong psql (chủ kho tự nhập mật khẩu, không lưu vào git):
--   \password bvienx_app
--   \password bvienx_loader

-- Chỉ cấp quyền ghi vết sau khi chủ kho đã tạo từng bảng.
DO $$
BEGIN
    IF to_regclass('nghiep_vu.vet_chay') IS NOT NULL THEN
        GRANT INSERT, SELECT, DELETE ON TABLE nghiep_vu.vet_chay TO bvienx_app;
        ALTER TABLE nghiep_vu.vet_chay ENABLE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS bvienx_app_doc ON nghiep_vu.vet_chay;
        CREATE POLICY bvienx_app_doc ON nghiep_vu.vet_chay FOR SELECT TO bvienx_app USING (true);
        DROP POLICY IF EXISTS bvienx_app_them ON nghiep_vu.vet_chay;
        CREATE POLICY bvienx_app_them ON nghiep_vu.vet_chay FOR INSERT TO bvienx_app WITH CHECK (true);
        DROP POLICY IF EXISTS bvienx_app_xoa ON nghiep_vu.vet_chay;
        CREATE POLICY bvienx_app_xoa ON nghiep_vu.vet_chay FOR DELETE TO bvienx_app USING (true);
    END IF;
    IF to_regclass('nghiep_vu.vet_buoc') IS NOT NULL THEN
        GRANT INSERT, SELECT, DELETE ON TABLE nghiep_vu.vet_buoc TO bvienx_app;
        ALTER TABLE nghiep_vu.vet_buoc ENABLE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS bvienx_app_doc ON nghiep_vu.vet_buoc;
        CREATE POLICY bvienx_app_doc ON nghiep_vu.vet_buoc FOR SELECT TO bvienx_app USING (true);
        DROP POLICY IF EXISTS bvienx_app_them ON nghiep_vu.vet_buoc;
        CREATE POLICY bvienx_app_them ON nghiep_vu.vet_buoc FOR INSERT TO bvienx_app WITH CHECK (true);
        DROP POLICY IF EXISTS bvienx_app_xoa ON nghiep_vu.vet_buoc;
        CREATE POLICY bvienx_app_xoa ON nghiep_vu.vet_buoc FOR DELETE TO bvienx_app USING (true);
    END IF;
END
$$;
