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

export interface LoiNapCa {
  tep: string
  loi: string
}

export interface DanhSachCa {
  cases: DongHangDoi[]
  loi_nap: LoiNapCa[]
  che_do: CheDo
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

export interface BangYLenh {
  cot: string[]
  dong: Record<string, string>[]
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

export interface ChiTietCa {
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
