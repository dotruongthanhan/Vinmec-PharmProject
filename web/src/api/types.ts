export type MucDoMa = 'nghiem_trong' | 'can_luu_y' | null

export interface MeResponse {
  id: string
  email: string | null
  vai_tro: string
  phien_id: string | null
}

export type KetLuanMa = 'dat' | 'can_xem' | 'khong_du_du_lieu' | 'ngoai_hdsd'

export type DiUngMa = 'co_di_ung' | 'khong_di_ung_da_hoi' | 'chua_co_thong_tin'

export type LoaiCanCuMa = 'du_lieu' | 'tinh_toan' | 'tai_lieu'

export type PhanHoiMa = 'dong_y' | 'bac_bo' | 'can_sua'

export type NguonGocMa = 'luat' | 'ai_da_kiem_chung' | 'ai_chua_kiem_chung'

export type TruyXuatCheDo = 'chua_co' | 'tu_khoa' | 'lai' | 'san_sang'

export type TrangThaiAI = 'tat' | 'dang_chay' | 'xong' | 'loi'

export type TrangThaiBuocAI = 'cho' | 'dang_chay' | 'xong' | 'loi' | 'bo_qua'

export interface NguonTomTat {
  nhan: string
  so_doan: number
}

export interface BuocAI {
  ma: string
  ten: string
  trang_thai: TrangThaiBuocAI
  chi_tiet: string | null
  nguon: NguonTomTat[]
  thoi_gian_ms: number | null
  ly_do: string | null
  goi_y: string | null
}

export interface TienTrinhHoiDap {
  dang_chay: boolean
  cac_buoc: BuocAI[]
  da_chay_ms: number | null
}

export type TrangThaiTraLoi =
  | 'chua_san_sang'
  | 'ok'
  | 'khong_co_nguon'
  | 'ngoai_pham_vi'
  | 'loi'

export interface CheDo {
  co_llm: boolean
  truy_xuat: TruyXuatCheDo
  hoi_them: boolean
  thong_bao: string[]
}

export interface DongHangDoi {
  ho_ten?: string | null
  ngay_sinh?: string | null
  chan_doan_chinh?: string | null
  vao_vien?: string | null
  so_y_lenh?: number | null
  ca_id: string
  ma_y_lenh?: string | null
  thoi_diem_ke?: string | null
  nguoi_benh_tom_tat?: string | null
  thuoc?: string[] | null
  khoa: string
  mo_ta: string
  uu_tien: 0 | 1 | 2 | 3 | 4
  huy_hieu: string
  so_nghiem_trong: number
  so_can_luu_y: number
  so_thieu_du_lieu: number
  da_phan_hoi_het: boolean
}

export interface FullIdentity {
  ho_ten?: string | null
  ngay_sinh?: string | null
  tuoi?: number | null
  gioi_tinh?: 'nam' | 'nu' | null
  can_nang_kg?: number | null
  chieu_cao_cm?: number | null
  dan_toc?: string | null
  ngoai_kieu?: string | null
  nghe_nghiep?: string | null
  dia_chi?: { so_nha?: string | null; thon_pho?: string | null; xa_phuong?: string | null; huyen?: string | null; tinh_thanh?: string | null } | null
  dia_chi_text?: string | null
  doi_tuong?: 'bhyt' | 'thu_phi' | 'mien' | 'khac' | null
  bhyt?: { so_the?: string | null; gia_tri_den?: string | null } | null
  nguoi_bao_tin?: { ho_ten?: string | null; quan_he?: string | null; dien_thoai?: string | null } | null
  bo_me?: { bo?: { ho_ten?: string | null; nghe_nghiep?: string | null } | null; me?: { ho_ten?: string | null; nghe_nghiep?: string | null } | null } | null
  nhom_mau?: string | null
}

export interface PatientManagement {
  dot_dieu_tri_id: string
  khoa_dieu_tri?: string | null
  thoi_diem_bat_dau?: string | null
  thoi_diem_ket_thuc?: string | null
  hinh_thuc_vao?: string | null
  so_ngay_dieu_tri?: number | null
  lich_su_khoa?: { khoa: string; tu?: string | null; den?: string | null }[]
  noi_gioi_thieu?: 'co_quan_y_te' | 'tu_den' | 'khac' | null
  tuyen_chuyen_den?: string | null
  vao_khoa_luc?: string | null
  so_giuong?: string | null
  so_luu_tru?: string | null
  ma_yt?: string | null
  ra_vien?: { hinh_thuc: string; chuyen_vien_den?: string | null; ly_do?: string | null } | null
  bac_si_dieu_tri?: string | null
}

export interface EncounterHistory extends PatientManagement {
  thu_tu?: number | null
  chan_doan_chinh?: string | null
  y_lenh?: { y_lenh_id: string; thoi_diem_ke?: string | null; trang_thai?: string | null; thuoc?: string[] }[]
  phieu_dieu_tri?: { thoi_diem_ghi?: string | null; loai_ho_so?: string | null; noi_dung: string }[]
}

export interface LoiNapCa {
  tep: string
  loi: string
}

export interface DanhSachCa {
  cases: DongHangDoi[]
  loi_nap: LoiNapCa[]
  che_do: CheDo
  lam_moi_luc?: string | null
}

export interface DemNhanDinh {
  nghiem_trong: number
  can_luu_y: number
  thieu_du_lieu: number
  ngoai_hdsd: number
  dat: number
}

export interface DinhDanhCa {
  ca_id: string
  gioi_tuoi: string
  can_nang: string
  khoa_loai: string
  crcl: string
  crcl_bat_thuong: boolean
  di_ung_ma: DiUngMa
  di_ung_text: string
  dem: DemNhanDinh
}

export interface ChanDoanTomTat {
  loai_nhan: string
  noi_dung: string
  ma_icd10: string | null
}

export interface DienBienTomTat {
  thoi_diem_text: string
  loai_nhan: string
  noi_dung: string
}

export interface BatThuongTomTat {
  ten: string
  gia_tri_text: string
  don_vi: string
  huong: '▲' | '▼'
  thoi_diem_text: string
  so_voi_truoc: string | null
}

export interface TomTat {
  chan_doan: ChanDoanTomTat[]
  co_dia: string[]
  vao_vien_text: string
  nam_vien_text: string | null
  dien_bien_moi_nhat: DienBienTomTat | null
  bat_thuong: BatThuongTomTat[]
  bat_thuong_ghi_chu: string | null
}

export interface DauVaoChiSo {
  nhan: string
  gia_tri_text: string
  don_vi: string
  ban_ghi_id: string | null
  thoi_diem_text: string | null
}

export interface ChiSo {
  cong_thuc: string
  nhan: string
  don_vi: string
  gia_tri_text: string
  thieu: string[]
  dau_vao: DauVaoChiSo[]
  ghi_chu: string[]
  tham_khao: string
}

export interface CanCu {
  so: number
  loai_ma: LoaiCanCuMa
  loai_nhan: string
  mo_ta: string
  ban_ghi_id: string | null
  mo_duoc: boolean
  cong_thuc: string | null
  ghi_chu: string | null
}

export interface PhanHoiDaGhi {
  phan_hoi: PhanHoiMa
  phan_hoi_nhan: string
  nhom_ly_do: string | null
  ly_do: string | null
  thoi_diem_text: string
}

export interface TrichDan {
  so: number
  doan_trich_id: string
  nhan: string
  trich_nguyen_van: string
}

export interface NhanDinh {
  nhan_dinh_id: string
  thuoc: string
  yeu_to: string
  nhan_xet: string
  ket_luan_ma: KetLuanMa
  ket_luan_nhan: string
  muc_do_ma: MucDoMa
  muc_do_nhan: string | null
  nguon_goc_ma: NguonGocMa
  nguon_goc_nhan: string
  ma_luat: string | null
  chi_tiet_y_lenh_id: string[]
  thong_tin_con_thieu: string[]
  can_cu: CanCu[]
  phan_hoi: PhanHoiDaGhi | null
  dien_giai_ai: string | null
  de_xuat_ai: string | null
  trich_dan: TrichDan[]
}

export interface KetQuaAI {
  trang_thai: TrangThaiAI
  nhan_dinh: {
    can_chu_y: NhanDinh[]
    dat: NhanDinh[]
  } | null
  canh_bao: string[]
  thoi_gian_ms: number | null
  mo_hinh: string | null
  cac_buoc: BuocAI[]
  da_chay_ms: number | null
  thuong_le_ms: number | null
}

export interface DoanNguon {
  doan_trich_id: string
  nguon_nhan: string
  duong_dan_muc: string
  tang_tin_cay: number
  phien_ban: string
  url_goc: string | null
  noi_dung: string
}

export interface OrderLineMeta {
  chi_tiet_y_lenh_id: string
  trang_thai_dong?: string | null
  bat_dau?: string | null
  ket_thuc?: string | null
  cach_dung?: string | null
}

export interface BangYLenh {
  cot: string[]
  dong: Record<string, string>[]
  dong_meta?: OrderLineMeta[]
}

export interface ChiTietXetNghiemDong {
  thoi_diem_text: string
  ten: string
  gia_tri_text: string
  don_vi: string
  khoang_tham_chieu: string
  ngoai_nguong: boolean
  huong: '▲' | '▼' | null
}

export interface KhangSinhDoDong {
  hoat_chat: string
  ket_qua: string
  mic_text: string
  dang_ke: boolean
}

export interface ChiTietViSinhDong {
  benh_pham: string
  lay_mau_text: string
  vi_khuan: string
  khang_sinh_do: KhangSinhDoDong[]
}

export interface MedicalOrder {
  y_lenh_id: string
  dot_dieu_tri_id: string
  thu_tu_dot?: number | null
  thoi_diem_ke?: string | null
  trang_thai?: string | null
  loai?: string | null
  vai_tro_nguoi_ke?: string | null
  khoa_ke_don?: string | null
  luong_duyet?: string | null
  ly_do_ngung?: string | null
  thoi_diem_ngung?: string | null
  thay_the_y_lenh_id?: string | null
  la_trong_tam: boolean
  cot: string[]
  dong: Record<string, string>[]
  dong_meta?: OrderLineMeta[]
}

export interface TreatmentSheet {
  phieu_dieu_tri_id: string
  dot_dieu_tri_id: string
  thu_tu_dot?: number | null
  ngay_dieu_tri: number
  thoi_diem_lap: string
  vai_tro_nguoi_lap: string
  dien_bien: string
  danh_gia: string
  huong_xu_tri: string
  y_lenh_trong_ngay: string[]
  che_do_cham_soc: string | null
  che_do_an: string
  theo_doi: string[]
  dan_do: string | null
}

export interface ChiTietCa {
  ma_tran_tuong_tac?: MaTranTuongTac | null
  danh_sach_y_lenh?: MedicalOrder[]
  phieu_dieu_tri?: TreatmentSheet[]
  dinh_danh_day_du?: FullIdentity | null
  quan_ly_nguoi_benh?: PatientManagement | null
  lich_su_vao_vien?: EncounterHistory[]
  ca_id: string
  dinh_danh: DinhDanhCa
  tom_tat: TomTat
  chi_so: ChiSo[]
  nhan_dinh: {
    can_chu_y: NhanDinh[]
    dat: NhanDinh[]
    yeu_to_chua_kiem: string[]
    so_luat_da_chay: number
  }
  chi_tiet: {
    y_lenh: {
      thong_tin_text: string
      cho_duyet: BangYLenh
      dang_dung: BangYLenh | null
    }
    xet_nghiem: ChiTietXetNghiemDong[]
    vi_sinh: ChiTietViSinhDong[]
    dien_bien: DienBienTomTat[]
  }
  cau_hoi_goi_y: string[]
  nhom_ly_do: string[]
  thoi_gian_ms: number
  che_do: CheDo
}

export interface ThuocMaTran {
  chi_tiet_y_lenh_id: string
  ten: string
  nhom: 'cho_duyet' | 'dang_dung'
  phan_giai: 'da_phan_giai' | 'mot_phan' | 'khong_nhan_dien' | 'khong_ap_dung'
  hoat_chat: string[]
  ly_do: string | null
}

export interface CapMaTran {
  a: string
  b: string
  muc: 'nghiem_trong' | 'can_luu_y' | 'thieu_du_lieu' | 'khong_phat_hien' | 'khong_ap_dung'
  nhan_dinh_id: string | null
  tom_tat: string | null
  ly_do: string | null
}

export interface TuongTacThucAn {
  chi_tiet_y_lenh_id: string
  hoat_chat: string
  thuc_an: string
  muc: 'nghiem_trong' | 'can_luu_y' | 'thong_tin' | 'chua_ro'
  mo_ta: string | null
  xu_tri: string | null
}

export interface MaTranTuongTac {
  nguon: string
  ghi_chu: string
  thuoc: ThuocMaTran[]
  cap: CapMaTran[]
  thuc_an: TuongTacThucAn[]
}

export interface BanGhi {
  loai: string
  tieu_de: string
  dong: [string, string][]
}

export interface GuiPhanHoi {
  nhan_dinh_id: string
  phan_hoi: PhanHoiMa
  nhom_ly_do?: string | null
  ly_do?: string | null
}

export interface LichSuHoiDapItem {
  vai: 'nguoi_dung' | 'he_thong'
  noi_dung: string
}

export interface GuiCauHoi {
  cau_hoi: string
  lich_su: LichSuHoiDapItem[]
  nhan_dinh_id?: string | null
}

export interface TrichDanTraLoi {
  so: number
  loai_ma: LoaiCanCuMa
  nhan: string
  ban_ghi_id: string | null
  doan_trich_id?: string | null
  trich_nguyen_van?: string | null
}

export interface TraLoi {
  trang_thai: TrangThaiTraLoi
  noi_dung: string
  trich_dan: TrichDanTraLoi[]
  cong_cu_da_goi: string[]
  thoi_gian_ms?: number
}

export interface HealthResponse {
  ok: boolean
  che_do: CheDo
}

export interface ApiErrorBody {
  loi: {
    ma: string
    thong_bao: string
  }
}

// ---- Hợp đồng v1.8: tra cứu thuốc, tra tương tác thủ công, máy tính công thức (chỉ đọc) ----

export interface KetQuaThuoc {
  hoat_chat_id: string
  ten_inn: string
  ten_viet: string | null
  ma_atc: string[]
  so_che_pham: number
  co_nhan_fda: boolean
  so_quy_tac: number
}

export interface DanhSachThuoc {
  tong: number
  trang: number
  so_dong: number
  ket_qua: KetQuaThuoc[]
  goi_y_sua?: string | null
}

export type LoaiGoiYThuoc = 'hoat_chat' | 'dong_nghia' | 'biet_duoc'
export type KieuKhopGoiYThuoc = 'chinh_xac' | 'tien_to' | 'gan_dung'

export interface GoiYThuoc {
  nhan: string
  loai: LoaiGoiYThuoc
  hoat_chat_ids: string[]
  ten_hoat_chat: string[]
  gia_tri_gui: string
  khop: KieuKhopGoiYThuoc
}

export interface KetQuaGoiYThuoc {
  ket_qua: GoiYThuoc[]
  goi_y_sua: string | null
}

export interface DinhDanhThuoc {
  hoat_chat_id: string
  ten_inn: string
  ten_viet: string | null
  rxcui: string | null
  ma_atc: string[]
  ddinter_id: string | null
  loai: string
  nguon: string
  trang_thai: string | null
}

export interface ChePham {
  ten_thuoc: string
  so_dang_ky: string | null
  dang_bao_che: string | null
  ham_luong: number | null
  don_vi: string | null
}

export interface DanhSachChePham {
  nguon: string
  trang_thai: string | null
  tong: number
  danh_sach: ChePham[]
}

export interface DoanNhanFda {
  doan_trich_id: string
  duong_dan_muc: string
  noi_dung_goc: string
  url_goc: string | null
  tai_lieu_id: string
  set_id: string | null
  nguon: string
  phien_ban_nguon: string | null
  tang_tin_cay: number
}

export interface NhomNhanFda {
  muc: string
  doan: DoanNhanFda[]
}

export interface NhanFda {
  nguon: string
  trang_thai: string | null
  tong_doan: number
  nhom: NhomNhanFda[]
}

export interface QuyTacDong {
  nhom: string
  bang_luat: string
  phan: string
  phien_ban: string | null
  trang_thai: string | null
  du_lieu: Record<string, unknown>
}

export interface SoCapTuongTac {
  major: number
  moderate: number
  minor: number
  unknown: number
}

export interface CapMajor {
  ddinter_id: string
  ten_thuoc_khac: string
  co_che: string[]
}

export interface TuongTacTomTat {
  nguon: string
  trang_thai: string | null
  ddinter_id: string | null
  co_du_lieu: boolean
  so_cap: SoCapTuongTac
  major: CapMajor[]
  ghi_chu: string
}

export interface ChiTietThuoc {
  dinh_danh: DinhDanhThuoc
  che_pham: DanhSachChePham
  nhan_fda: NhanFda
  quy_tac: QuyTacDong[]
  tuong_tac_tom_tat: TuongTacTomTat
}

export interface TraTuongTacYeuCau {
  thuoc: string[]
}

export interface PhanGiaiTen {
  ten_nhap: string
  chi_tiet_y_lenh_id: string
  trang_thai: 'da_phan_giai' | 'mot_phan' | 'khong_nhan_dien' | 'khong_ap_dung'
  hoat_chat: string[]
  ly_do: string | null
}

export interface CapChiTiet {
  a: string
  b: string
  muc: string
  mo_ta: string
  can_cu: string[]
  thong_tin_con_thieu: string[]
}

export interface KetQuaTraTuongTac {
  ma_tran: MaTranTuongTac
  phan_giai: PhanGiaiTen[]
  chi_tiet: CapChiTiet[]
}

export interface DauVaoCongThuc {
  ten: string
  nhan: string
  kieu: 'so' | 'lua_chon'
  don_vi: string[]
  lua_chon: string[]
  nhan_lua_chon: Record<string, string>
  truong_don_vi: string | null
  bat_buoc: boolean
  mac_dinh: string | number | null
}

export interface DauRaCongThuc {
  don_vi: string[]
  phan_hang: string[]
}

export interface CongThucMuc {
  ma: string
  ten: string
  loai: string
  dau_vao: DauVaoCongThuc[]
  dau_ra: DauRaCongThuc
  tham_khao_goc: string[]
  tham_chieu_mdcalc: string | null
  trang_thai: string
}

export interface DanhMucCongThuc {
  cong_thuc: CongThucMuc[]
}

export interface TinhCongThucYeuCau {
  dau_vao: Record<string, string | number | null>
}

export interface DauVaoDaDung {
  ten: string
  gia_tri: number
  don_vi: string
}

export interface KetQuaCongThuc {
  ma: string
  cong_thuc: string
  phien_ban: string
  ket_qua: number | null
  don_vi: string
  dau_vao_da_dung: DauVaoDaDung[]
  thieu_dau_vao: string[]
  ghi_chu: string[]
  tham_khao: string
  trang_thai: string
}
