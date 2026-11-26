/** Kiểu dữ liệu dùng chung giữa Service Worker, thư viện De-ID và giao diện Side Panel. */

export type SchemaGroup = 'pii_xoa' | 'lam_sang_giu' | 'nghi_ngo_pii'

export interface SchemaFieldDescriptor {
  ten_nhan: string
  kieu_dom: string
  ngu_canh_muc?: string | null
}

export interface ClassifiedField {
  ten_nhan: string
  nhom: SchemaGroup
  nguon: 'san_pii' | 'gemini' | 'mac_dinh_an_toan'
  ly_do: string
}

export interface ExtractedFieldPair {
  label: string
  value: string
  domKind: 'dt_dd' | 'table_th' | 'label_control' | 'colon_pair'
  sectionTitle: string
}

export interface ExtractedSection {
  title: string
  bucket: 'demographics_dx' | 'labs_vitals' | 'meds_notes' | 'other'
  text: string
}

export interface RawTabExtraction {
  tabId: number
  tabTitle: string
  origin: string
  url: string
  schemaHash: string
  uniqueFields: SchemaFieldDescriptor[]
  fieldPairs: ExtractedFieldPair[]
  sections: ExtractedSection[]
}

export interface BrowserTabSummary {
  id: number
  title: string
  url: string
  origin: string
  isEmrCandidate: boolean
  active: boolean
}

export interface EmrSectionPayload {
  tieu_de: string
  loai_muc: 'demographics_dx' | 'labs_vitals' | 'meds_notes' | 'other'
  tab_id?: number
  tab_title?: string
  noi_dung: string
}

export interface ExtractEmrPayload {
  schema_hash?: string
  tab_count: number
  source_domains: string[]
  sections: EmrSectionPayload[]
}

export interface DeidReplacement {
  loai: string
  ma_tam: string
}

export interface DeidAuditSummary {
  droppedFields: string[]
  quasiTransforms: string[]
  regexRedactions: Record<string, number>
  knownValueRedactions: number
  dateAnchorCount: number
  totalCharsOut: number
}

export interface PatientGuardResult {
  status: 'MATCH' | 'SINGLE_OR_UNKNOWN' | 'MISMATCH_BLOCKED'
  message: string
  fingerprints: Array<{ tabId: number; tabTitle: string; hashPrefix: string }>
}

export interface OhCropResult {
  blob: Blob
  previewUrl: string
  width: number
  height: number
  sizeBytes: number
  softWarning: string | null
}

export interface CheDo {
  co_llm: boolean
  truy_xuat: 'chua_co' | 'tu_khoa' | 'lai' | 'san_sang'
  hoi_them: boolean
  thong_bao: string[]
}

export interface FindingCounts {
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
  di_ung_ma: 'co_di_ung' | 'khong_di_ung_da_hoi' | 'chua_co_thong_tin'
  di_ung_text: string
  dem: FindingCounts
}

export interface ChiSo {
  cong_thuc: string
  nhan: string
  don_vi: string
  gia_tri_text: string
  thieu: string[]
  ghi_chu: string[]
  tham_khao: string
}

export interface CanCu {
  so: number
  loai_ma: 'du_lieu' | 'tinh_toan' | 'tai_lieu'
  loai_nhan: string
  mo_ta: string
  ban_ghi_id: string | null
  mo_duoc: boolean
  cong_thuc: string | null
  ghi_chu: string | null
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
  ket_luan_ma: 'dat' | 'can_xem' | 'khong_du_du_lieu' | 'ngoai_hdsd'
  ket_luan_nhan: string
  muc_do_ma: 'nghiem_trong' | 'can_luu_y' | null
  muc_do_nhan: string | null
  nguon_goc_ma: 'luat' | 'ai_da_kiem_chung' | 'ai_chua_kiem_chung'
  nguon_goc_nhan: string
  ma_luat: string | null
  chi_tiet_y_lenh_id: string[]
  thong_tin_con_thieu: string[]
  can_cu: CanCu[]
  dien_giai_ai?: string | null
  de_xuat_ai?: string | null
  trich_dan?: TrichDan[]
}

export interface BangYLenh {
  cot: string[]
  dong: Array<Record<string, string>>
}

export interface ChiTietCa {
  ca_id: string
  dinh_danh: DinhDanhCa
  tom_tat: {
    chan_doan: Array<{ loai_nhan: string; noi_dung: string; ma_icd10: string | null }>
    co_dia: string[]
    vao_vien_text: string
    bat_thuong: Array<{
      ten: string
      gia_tri_text: string
      don_vi: string
      huong: '▲' | '▼'
      thoi_diem_text: string
    }>
  }
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
    xet_nghiem: Array<{
      thoi_diem_text: string
      ten: string
      gia_tri_text: string
      don_vi: string
      khoang_tham_chieu: string
      ngoai_nguong: boolean
      huong: '▲' | '▼' | null
    }>
  }
  cau_hoi_goi_y: string[]
  thoi_gian_ms: number
  che_do: CheDo
}

export interface ExtensionReviewResponse {
  session_id: string
  expires_in_seconds: number
  zero_retention: true
  chi_tiet: ChiTietCa
  canh_bao_trinh_duyet: string[]
  canh_bao_pii_anh: string[]
  mo_hinh_da_dung: Record<string, string>
  thoi_gian_ms: number
  che_do: CheDo
}

export interface BuocAI {
  ma: string
  ten: string
  trang_thai: 'cho' | 'dang_chay' | 'xong' | 'loi' | 'bo_qua'
  chi_tiet?: string | null
  thoi_gian_ms?: number | null
  ly_do?: string | null
  goi_y?: string | null
}

export interface TienTrinhHoiDap {
  dang_chay: boolean
  cac_buoc: BuocAI[]
  da_chay_ms: number | null
}

export interface KetQuaAI {
  trang_thai: 'tat' | 'dang_chay' | 'xong' | 'loi'
  nhan_dinh: {
    can_chu_y: NhanDinh[]
    dat: NhanDinh[]
  } | null
  canh_bao: string[]
  thoi_gian_ms?: number | null
  mo_hinh?: string | null
  cac_buoc: BuocAI[]
  da_chay_ms?: number | null
}

export interface CitationItem {
  so: number
  loai_ma: 'du_lieu' | 'tinh_toan' | 'tai_lieu'
  nhan: string
  ban_ghi_id?: string | null
  doan_trich_id?: string | null
  trich_nguyen_van?: string | null
}

export interface TraLoi {
  trang_thai: 'chua_san_sang' | 'ok' | 'khong_co_nguon' | 'ngoai_pham_vi' | 'loi'
  noi_dung: string
  trich_dan: CitationItem[]
  cong_cu_da_goi: string[]
  thoi_gian_ms: number
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

export interface ExtensionHealthResponse {
  ok: true
  zero_retention: true
  phien_ban: string
  che_do: CheDo
  xac_thuc: string
  mo_hinh_trich_xuat: Record<string, string>
}

export interface RecalcPayload {
  tuoi?: number
  gioi_tinh?: 'nam' | 'nu'
  can_nang_kg?: number
  chieu_cao_cm?: number
  tinh_trang_di_ung?: 'co_di_ung' | 'khong_di_ung_da_hoi' | 'chua_co_thong_tin'
  xet_nghiem?: Array<{
    ma_xet_nghiem: string
    ten_xet_nghiem?: string
    gia_tri_so: number
    don_vi?: string
  }>
  y_lenh?: Array<{
    chi_tiet_y_lenh_id: string
    ten_tu_do?: string
    lieu_moi_lan?: number
    don_vi_lieu?: string
    duong_dung?: string
    tan_suat?: string
    so_lan_moi_ngay?: number
    khoang_cach_gio?: number
  }>
}
