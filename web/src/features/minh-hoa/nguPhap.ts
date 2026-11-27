/** Ngữ pháp đặc tả minh hoạ tương tác `mh-0` và bộ kiểm định nghiêm ngặt. */

export type PhienBanNguPhap = 'mh-0' | 'mh-1'
export type KieuCot = 'dinh_luong' | 'thu_tu' | 'danh_muc' | 'thoi_gian' | 'logic'
export type LoaiDau = 'duong' | 'vung' | 'cot' | 'diem' | 'o' | 'dai' | 'quy_tac' | 'chu'
export type LoaiThamSo = 'thanh_keo' | 'chon_mot' | 'bat_tat' | 'loc' | 'dat_lai'
export type DinhDangSo = '0' | '0.0' | '0.00'
export type MienTruc = 'tu_du_lieu' | 'tu_0'
export type GiaTriO = string | number | boolean | null

export interface CotDuLieu {
  ten: string
  kieu: KieuCot
  don_vi: string | null
  nhan?: string | null
}

export interface BoDuLieu {
  ma: string
  ten?: string
  cot: readonly CotDuLieu[]
  dong: readonly Record<string, GiaTriO>[]
  can_cu?: readonly string[]
}

export interface ThamChieuO {
  ds: string
  cot: string
  dong?: number
  theo_tham_so?: boolean
  dinh_dang?: DinhDangSo
}

export interface PhanPhuDeChu {
  chu: string
}

export interface PhanPhuDeO {
  o: ThamChieuO
}

export interface ThamChieuKhoang {
  ds: string
  cot: string
  tu: string
  den: string
  bao_gom_tu: string
  bao_gom_den: string
  gia_tri: ThamChieuO
}
export type PhanPhuDe = PhanPhuDeChu | PhanPhuDeO | { o_theo_khoang: ThamChieuKhoang }

export interface BoLocLop {
  cot: string
  bang_tham_so?: string
  trong_tham_so?: string
}

export interface MaHoaCot {
  cot: string
  kieu?: KieuCot
}

export interface MaHoaO {
  o: ThamChieuO
}

export interface MaHoaChu {
  chu: string
}

export type KenhViTri = MaHoaCot | MaHoaO
export type KenhNhan = MaHoaCot | MaHoaChu

export interface MaHoaLop {
  x?: KenhViTri
  y?: KenhViTri
  x_tu?: KenhViTri
  x_den?: KenhViTri
  y_tu?: KenhViTri
  y_den?: KenhViTri
  mau?: MaHoaCot
  nhom?: MaHoaCot
  nhan?: KenhNhan
  kich_thuoc?: MaHoaCot
  can_cu?: MaHoaCot
}

export interface LopMinhHoa {
  dau: LoaiDau
  du_lieu: string
  loc?: readonly BoLocLop[]
  ma_hoa: MaHoaLop
}

export interface CauHinhTruc {
  tieu_de: string
  mien?: MienTruc
}

export interface CauHinhHaiTruc {
  x?: CauHinhTruc | null
  y?: CauHinhTruc | null
}

export interface NguonGiaTriThamSo {
  ds: string
  cot: string
}

export interface MacDinhThamSo {
  o: ThamChieuO
}

export interface ThamSoDieuKhien {
  ma?: string
  loai: LoaiThamSo
  nhan: string
  gia_tri_tu?: NguonGiaTriThamSo
  mac_dinh?: MacDinhThamSo
  nhan_gia_dinh?: boolean
}

export interface MucSoHien {
  nhan: string
  o?: ThamChieuO
  o_theo_khoang?: ThamChieuKhoang
}

export interface DacTaMinhHoa {
  phien_ban: PhienBanNguPhap
  tieu_de: string
  phu_de?: readonly PhanPhuDe[]
  lop: readonly LopMinhHoa[]
  truc?: CauHinhHaiTruc
  tham_so?: readonly ThamSoDieuKhien[]
  so_hien?: readonly MucSoHien[]
  cong_thuc?: string
  nguon: readonly string[]
}

export interface TepMauMinhHoa {
  dac_ta: DacTaMinhHoa | readonly DacTaMinhHoa[]
  bo_du_lieu: readonly BoDuLieu[]
  cong_thuc_hien_thi?: Readonly<Record<string, string>>
  gia_lap?: boolean
  ghi_chu_nguon?: string
}

export type KetQuaKiemDacTa =
  | {
      hopLe: true
      dacTa: DacTaMinhHoa
      tongDiem: number
    }
  | {
      hopLe: false
      lyDo: string[]
    }

export const PHIEN_BAN_HO_TRO: PhienBanNguPhap = 'mh-0'
export const TOI_DA_LOP = 6
export const TOI_DA_THAM_SO = 6
export const TOI_DA_DIEM = 2000
export const TOI_DA_KY_TU_CHU = 120
export const TOI_DA_DAC_TA_BYTE = 16 * 1024

const KHOA_GOC = new Set([
  'phien_ban',
  'tieu_de',
  'phu_de',
  'lop',
  'truc',
  'tham_so',
  'so_hien',
  'cong_thuc',
  'nguon',
])
const KHOA_THAM_CHIEU_O = new Set(['ds', 'cot', 'dong', 'theo_tham_so', 'dinh_dang'])
const KHOA_LOP = new Set(['dau', 'du_lieu', 'loc', 'ma_hoa'])
const KHOA_LOC = new Set(['cot', 'bang_tham_so', 'trong_tham_so'])
const KHOA_MA_HOA = new Set([
  'x',
  'y',
  'x_tu',
  'x_den',
  'y_tu',
  'y_den',
  'mau',
  'nhom',
  'nhan',
  'kich_thuoc',
  'can_cu',
])
const KHOA_TRUC_GOC = new Set(['x', 'y'])
const KHOA_TRUC = new Set(['tieu_de', 'mien'])
const KHOA_THAM_SO = new Set(['ma', 'loai', 'nhan', 'gia_tri_tu', 'mac_dinh', 'nhan_gia_dinh'])
const KHOA_GIA_TRI_TU = new Set(['ds', 'cot'])
const KHOA_SO_HIEN = new Set(['nhan', 'o', 'o_theo_khoang'])

const TAP_DAU = new Set<LoaiDau>(['duong', 'vung', 'cot', 'diem', 'o', 'dai', 'quy_tac', 'chu'])
const TAP_KIEU_COT = new Set<KieuCot>(['dinh_luong', 'thu_tu', 'danh_muc', 'thoi_gian', 'logic'])
const TAP_LOAI_THAM_SO = new Set<LoaiThamSo>([
  'thanh_keo',
  'chon_mot',
  'bat_tat',
  'loc',
  'dat_lai',
])
const TAP_DINH_DANG = new Set<DinhDangSo>(['0', '0.0', '0.00'])
const TAP_MIEN_TRUC = new Set<MienTruc>(['tu_du_lieu', 'tu_0'])

const MAU_MA_ID = /^[a-z][a-z0-9_]{0,31}$/
const MAU_MA_CONG_THUC = /^[a-z][a-z0-9_]{1,63}$/
const MAU_KY_TU_AN = /[\u200B-\u200F\u202A-\u202E\u2066-\u2069\uFEFF]/
const MAU_SO_TU_DO = /\d/
const MAU_CHEN_LENH: readonly RegExp[] = [
  /ignore\s+(?:all\s+)?previous\s+instructions?/i,
  /disregard\s+(?:all\s+)?previous/i,
  /system\s+prompt/i,
  /bỏ\s+qua\s+mọi\s+(?:hướng\s+dẫn|chỉ\s+dẫn|cảnh\s+báo)/i,
]
const MAU_GIAO_THUC_NGUY_HIEM: readonly RegExp[] = [
  /javascript\s*:/i,
  /vbscript\s*:/i,
  /data\s*:/i,
  /http/i,
]

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function kiemMangGiaTri(items: unknown[], path: string, lyDo: string[]): void {
  const cells = items.flatMap((item, index) =>
    isRecord(item) && isRecord(item.o) ? [{ index, ref: item.o }] : [],
  )
  const intervals = items.flatMap((item, index) =>
    isRecord(item) && isRecord(item.o_theo_khoang) && isRecord(item.o_theo_khoang.gia_tri)
      ? [{ index, ref: item.o_theo_khoang.gia_tri }] : [],
  )
  const columns = new Set([...cells, ...intervals].filter(({ ref }) => ref.theo_tham_so === true).map(({ ref }) => ref.cot))
  for (const { index, ref } of cells) {
    if (columns.has(ref.cot) && ref.theo_tham_so !== true) {
      lyDo.push(`tron_gia_tri_ca_va_gia_dinh:${path}[${index}]; dùng giá trị theo tham số hoặc tách số của ca sang dòng khác`)
    }
  }
  for (const { index, ref } of intervals) {
    if (ref.theo_tham_so === true && !cells.some(({ ref: cell }) =>
      cell.theo_tham_so === true && cell.ds === ref.ds && cell.cot === ref.cot)) {
      lyDo.push(`thieu_gia_tri_tra:${path}[${index}]; thêm ô theo tham số cùng bộ dữ liệu và cột`)
    }
  }
}

function kiemKhoaLa(
  obj: Record<string, unknown>,
  choPhep: ReadonlySet<string>,
  viTri: string,
  lyDo: string[],
): void {
  for (const khoa of Object.keys(obj)) {
    if (!choPhep.has(khoa)) {
      lyDo.push(`Khoá lạ "${khoa}" tại ${viTri}`)
    }
  }
}

function kiemChuAnToan(
  value: unknown,
  viTri: string,
  lyDo: string[],
  options: { camSoTuDo?: boolean; choPhepRong?: boolean } = {},
): value is string {
  if (typeof value !== 'string') {
    lyDo.push(`${viTri} phải là chuỗi`)
    return false
  }
  if (!options.choPhepRong && value.trim().length === 0) {
    lyDo.push(`${viTri} không được để trống`)
    return false
  }
  if (value.length > TOI_DA_KY_TU_CHU) {
    lyDo.push(`${viTri} vượt quá ${TOI_DA_KY_TU_CHU} ký tự`)
    return false
  }
  if (value.includes('<') || value.includes('>')) {
    lyDo.push(`${viTri} chứa ký tự thẻ HTML (< hoặc >)`)
    return false
  }
  if (MAU_KY_TU_AN.test(value)) {
    lyDo.push(`${viTri} chứa ký tự điều khiển ẩn`)
    return false
  }
  for (const regex of MAU_GIAO_THUC_NGUY_HIEM) {
    if (regex.test(value)) {
      lyDo.push(`${viTri} chứa liên kết hoặc giao thức không được phép`)
      return false
    }
  }
  for (const regex of MAU_CHEN_LENH) {
    if (regex.test(value)) {
      lyDo.push(`${viTri} chứa mẫu chèn lệnh không hợp lệ`)
      return false
    }
  }
  if (options.camSoTuDo && MAU_SO_TU_DO.test(value)) {
    lyDo.push(`${viTri} chứa số tự do; số phải lấy từ tham chiếu ô dữ liệu`)
    return false
  }
  return true
}

function tinhKichThuocByte(value: unknown): number {
  try {
    const serialized = JSON.stringify(value)
    if (typeof serialized !== 'string') {
      return Number.POSITIVE_INFINITY
    }
    return new TextEncoder().encode(serialized).length
  } catch {
    return Number.POSITIVE_INFINITY
  }
}

function kiemKieuGiaTriCot(cot: CotDuLieu, ds: BoDuLieu, lyDo: string[]): void {
  for (let i = 0; i < ds.dong.length; i++) {
    const val = ds.dong[i][cot.ten]
    if (val === null || val === undefined) {
      continue
    }
    if (cot.kieu === 'dinh_luong' && (typeof val !== 'number' || !Number.isFinite(val))) {
      lyDo.push(`Bộ dữ liệu ${ds.ma} dòng ${i} cột "${cot.ten}" sai kiểu dinh_luong`)
      return
    }
    if (cot.kieu === 'logic' && typeof val !== 'boolean') {
      lyDo.push(`Bộ dữ liệu ${ds.ma} dòng ${i} cột "${cot.ten}" sai kiểu logic`)
      return
    }
    if (cot.kieu === 'thoi_gian' && typeof val !== 'string') {
      lyDo.push(`Bộ dữ liệu ${ds.ma} dòng ${i} cột "${cot.ten}" sai kiểu thoi_gian`)
      return
    }
  }
}

function kiemThamChieuO(
  raw: unknown,
  viTri: string,
  dsMap: ReadonlyMap<string, { ds: BoDuLieu; cotMap: ReadonlyMap<string, CotDuLieu> }>,
  lyDo: string[],
): CotDuLieu | null {
  if (!isRecord(raw)) {
    lyDo.push(`${viTri} phải là tham chiếu ô dạng đối tượng, không nhận số tự do`)
    return null
  }
  kiemKhoaLa(raw, KHOA_THAM_CHIEU_O, viTri, lyDo)
  const dsId = raw.ds
  const cotTen = raw.cot
  if (typeof dsId !== 'string' || !dsMap.has(dsId)) {
    lyDo.push(`${viTri} trỏ tới bộ dữ liệu "${String(dsId ?? '')}" không tồn tại`)
    return null
  }
  const dsEntry = dsMap.get(dsId)
  if (!dsEntry || typeof cotTen !== 'string' || !dsEntry.cotMap.has(cotTen)) {
    lyDo.push(`${viTri} trỏ tới cột "${String(cotTen ?? '')}" không có trong ${dsId}`)
    return null
  }
  const hasDong = raw.dong !== undefined
  const hasTheoThamSo = raw.theo_tham_so === true
  if (hasDong && hasTheoThamSo) {
    lyDo.push(`${viTri} không thể dùng đồng thời "dong" và "theo_tham_so"`)
  } else if (!hasDong && !hasTheoThamSo) {
    lyDo.push(`${viTri} phải chỉ rõ "dong" hoặc "theo_tham_so": true`)
  }
  if (hasDong) {
    if (
      typeof raw.dong !== 'number' ||
      !Number.isInteger(raw.dong) ||
      raw.dong < 0 ||
      raw.dong >= dsEntry.ds.dong.length
    ) {
      lyDo.push(`${viTri} có chỉ số dòng ngoài phạm vi của ${dsId}`)
    }
  }
  if (raw.theo_tham_so !== undefined && typeof raw.theo_tham_so !== 'boolean') {
    lyDo.push(`${viTri}.theo_tham_so phải là kiểu logic`)
  }
  if (raw.dinh_dang !== undefined) {
    if (typeof raw.dinh_dang !== 'string' || !TAP_DINH_DANG.has(raw.dinh_dang as DinhDangSo)) {
      lyDo.push(`${viTri}.dinh_dang không được hỗ trợ`)
    }
  }
  return dsEntry.cotMap.get(cotTen) ?? null
}

function kiemKhoang(raw: unknown, viTri: string, dsMap: ReadonlyMap<string, { ds: BoDuLieu; cotMap: ReadonlyMap<string, CotDuLieu> }>, lyDo: string[]): void {
  if (!isRecord(raw)) { lyDo.push(`${viTri} phải là đối tượng`); return }
  kiemKhoaLa(raw, new Set(['ds', 'cot', 'tu', 'den', 'bao_gom_tu', 'bao_gom_den', 'gia_tri']), viTri, lyDo)
  const ds = typeof raw.ds === 'string' ? dsMap.get(raw.ds) : undefined
  for (const key of ['cot', 'tu', 'den', 'bao_gom_tu', 'bao_gom_den'] as const) {
    const cot = typeof raw[key] === 'string' ? ds?.cotMap.get(raw[key] as string) : undefined
    if (!cot) lyDo.push(`${viTri}.${key} không có trong bộ dữ liệu`)
    else if ((key === 'tu' || key === 'den') && cot.kieu !== 'dinh_luong') lyDo.push(`${viTri}.${key} phải là định lượng`)
    else if ((key === 'bao_gom_tu' || key === 'bao_gom_den') && cot.kieu !== 'logic') lyDo.push(`${viTri}.${key} phải là logic`)
  }
  const cot = kiemThamChieuO(raw.gia_tri, `${viTri}.gia_tri`, dsMap, lyDo)
  if (cot && cot.kieu !== 'dinh_luong') lyDo.push(`${viTri}.gia_tri phải là định lượng`)
}

function kiemKenhViTri(
  raw: unknown,
  viTri: string,
  dsEntry: { ds: BoDuLieu; cotMap: ReadonlyMap<string, CotDuLieu> },
  dsMap: ReadonlyMap<string, { ds: BoDuLieu; cotMap: ReadonlyMap<string, CotDuLieu> }>,
  lyDo: string[],
): CotDuLieu | null {
  if (!isRecord(raw)) {
    lyDo.push(`${viTri} phải là ánh xạ cột hoặc tham chiếu ô, không nhận số tự do`)
    return null
  }
  if ('o' in raw) {
    kiemKhoaLa(raw, new Set(['o']), viTri, lyDo)
    return kiemThamChieuO(raw.o, `${viTri}.o`, dsMap, lyDo)
  }
  kiemKhoaLa(raw, new Set(['cot', 'kieu']), viTri, lyDo)
  const cotTen = raw.cot
  if (typeof cotTen !== 'string' || !dsEntry.cotMap.has(cotTen)) {
    lyDo.push(`${viTri} trỏ tới cột "${String(cotTen ?? '')}" không có trong ${dsEntry.ds.ma}`)
    return null
  }
  const cot = dsEntry.cotMap.get(cotTen) ?? null
  if (raw.kieu !== undefined) {
    if (typeof raw.kieu !== 'string' || !TAP_KIEU_COT.has(raw.kieu as KieuCot)) {
      lyDo.push(`${viTri}.kieu không hợp lệ`)
    } else if (cot && raw.kieu !== cot.kieu) {
      lyDo.push(`${viTri} khai báo kiểu "${raw.kieu}" không khớp kiểu "${cot.kieu}" của cột "${cotTen}"`)
    }
  }
  return cot
}

function kiemMaHoaCot(
  raw: unknown,
  viTri: string,
  dsEntry: { ds: BoDuLieu; cotMap: ReadonlyMap<string, CotDuLieu> },
  lyDo: string[],
): CotDuLieu | null {
  if (!isRecord(raw)) {
    lyDo.push(`${viTri} phải là ánh xạ cột`)
    return null
  }
  kiemKhoaLa(raw, new Set(['cot', 'kieu']), viTri, lyDo)
  const cotTen = raw.cot
  if (typeof cotTen !== 'string' || !dsEntry.cotMap.has(cotTen)) {
    lyDo.push(`${viTri} trỏ tới cột "${String(cotTen ?? '')}" không có trong ${dsEntry.ds.ma}`)
    return null
  }
  const cot = dsEntry.cotMap.get(cotTen) ?? null
  if (raw.kieu !== undefined) {
    if (typeof raw.kieu !== 'string' || !TAP_KIEU_COT.has(raw.kieu as KieuCot)) {
      lyDo.push(`${viTri}.kieu không hợp lệ`)
    } else if (cot && raw.kieu !== cot.kieu) {
      lyDo.push(`${viTri} khai báo kiểu "${raw.kieu}" không khớp kiểu "${cot.kieu}" của cột "${cotTen}"`)
    }
  }
  return cot
}

/**
 * Kiểm tra đặc tả ngữ pháp `mh-0` đối chiếu với danh sách bộ dữ liệu đi kèm.
 * Trả `{ hopLe: false, lyDo }` nếu có bất kỳ vi phạm nào về cấu trúc, kiểu, trần hoặc bảo mật.
 */
export function kiemDacTa(dacTa: unknown, boDuLieu: readonly BoDuLieu[]): KetQuaKiemDacTa {
  const lyDo: string[] = []

  if (!isRecord(dacTa)) {
    return { hopLe: false, lyDo: ['Đặc tả phải là một đối tượng JSON'] }
  }

  const bytes = tinhKichThuocByte(dacTa)
  if (bytes > TOI_DA_DAC_TA_BYTE) {
    lyDo.push(`Đặc tả vượt trần ${TOI_DA_DAC_TA_BYTE} byte (${bytes} byte)`)
  }

  kiemKhoaLa(dacTa, KHOA_GOC, 'dac_ta', lyDo)

  if (dacTa.phien_ban !== 'mh-0' && dacTa.phien_ban !== 'mh-1') {
    lyDo.push(`Phiên bản ngữ pháp phải là "${PHIEN_BAN_HO_TRO}"`)
  }

  kiemChuAnToan(dacTa.tieu_de, 'tieu_de', lyDo)

  const dsMap = new Map<string, { ds: BoDuLieu; cotMap: Map<string, CotDuLieu> }>()
  for (const ds of boDuLieu) {
    const cotMap = new Map<string, CotDuLieu>()
    for (const cot of ds.cot) {
      cotMap.set(cot.ten, cot)
      kiemKieuGiaTriCot(cot, ds, lyDo)
    }
    dsMap.set(ds.ma, { ds, cotMap })
  }

  // Kiểm phụ đề (mọi số trong phụ đề phải là tham chiếu ô)
  if (dacTa.phu_de !== undefined) {
    if (!Array.isArray(dacTa.phu_de)) {
      lyDo.push('phu_de phải là mảng các phần chữ hoặc tham chiếu ô')
    } else {
      kiemMangGiaTri(dacTa.phu_de, 'phu_de', lyDo)
      dacTa.phu_de.forEach((item, idx) => {
        const viTri = `phu_de[${idx}]`
        if (!isRecord(item)) {
          lyDo.push(`${viTri} phải là đối tượng { chu } hoặc { o }, không nhận số tự do`)
          return
        }
        const hasChu = 'chu' in item
        const hasO = 'o' in item
        if ([hasChu, hasO, 'o_theo_khoang' in item].filter(Boolean).length !== 1) {
          lyDo.push(`${viTri} không được chứa cả "chu" và "o"`)
          return
        }
        if (hasChu) {
          kiemKhoaLa(item, new Set(['chu']), viTri, lyDo)
          kiemChuAnToan(item.chu, `${viTri}.chu`, lyDo, { camSoTuDo: true, choPhepRong: true })
        } else if (hasO) {
          kiemKhoaLa(item, new Set(['o']), viTri, lyDo)
          kiemThamChieuO(item.o, `${viTri}.o`, dsMap, lyDo)
        } else if ('o_theo_khoang' in item) {
          kiemKhoaLa(item, new Set(['o_theo_khoang']), viTri, lyDo)
          kiemKhoang(item.o_theo_khoang, viTri, dsMap, lyDo)
        } else {
          lyDo.push(`${viTri} phải có khoá "chu" hoặc "o"`)
        }
      })
    }
  }

  // Kiểm tham số điều khiển trước để đối chiếu với bộ lọc của các lớp
  const thamSoMap = new Map<string, LoaiThamSo>()
  if (dacTa.tham_so !== undefined) {
    if (!Array.isArray(dacTa.tham_so)) {
      lyDo.push('tham_so phải là mảng')
    } else {
      if (dacTa.tham_so.length > TOI_DA_THAM_SO) {
        lyDo.push(`Quá ${TOI_DA_THAM_SO} điều khiển (${dacTa.tham_so.length})`)
      }
      dacTa.tham_so.forEach((rawParam, idx) => {
        const viTri = `tham_so[${idx}]`
        if (!isRecord(rawParam)) {
          lyDo.push(`${viTri} phải là đối tượng`)
          return
        }
        kiemKhoaLa(rawParam, KHOA_THAM_SO, viTri, lyDo)
        const loai = rawParam.loai
        if (typeof loai !== 'string' || !TAP_LOAI_THAM_SO.has(loai as LoaiThamSo)) {
          lyDo.push(`${viTri}.loai không hợp lệ`)
          return
        }
        kiemChuAnToan(rawParam.nhan, `${viTri}.nhan`, lyDo)
        if (rawParam.nhan_gia_dinh !== undefined && typeof rawParam.nhan_gia_dinh !== 'boolean') {
          lyDo.push(`${viTri}.nhan_gia_dinh phải là kiểu logic`)
        }
        if (loai === 'dat_lai') {
          return
        }
        if (typeof rawParam.ma !== 'string' || !MAU_MA_ID.test(rawParam.ma)) {
          lyDo.push(`${viTri}.ma không hợp lệ`)
        } else if (thamSoMap.has(rawParam.ma)) {
          lyDo.push(`${viTri}.ma "${rawParam.ma}" bị trùng`)
        } else {
          thamSoMap.set(rawParam.ma, loai as LoaiThamSo)
        }

        if (!isRecord(rawParam.gia_tri_tu)) {
          lyDo.push(`${viTri}.gia_tri_tu phải trỏ tới cột trong bộ dữ liệu`)
        } else {
          kiemKhoaLa(rawParam.gia_tri_tu, KHOA_GIA_TRI_TU, `${viTri}.gia_tri_tu`, lyDo)
          const gDs = rawParam.gia_tri_tu.ds
          const gCot = rawParam.gia_tri_tu.cot
          const dsEntry = typeof gDs === 'string' ? dsMap.get(gDs) : undefined
          if (!dsEntry) {
            lyDo.push(`${viTri}.gia_tri_tu trỏ tới bộ dữ liệu "${String(gDs ?? '')}" không tồn tại`)
          } else if (typeof gCot !== 'string' || !dsEntry.cotMap.has(gCot)) {
            lyDo.push(`${viTri}.gia_tri_tu trỏ tới cột "${String(gCot ?? '')}" không tồn tại`)
          } else {
            const cotDef = dsEntry.cotMap.get(gCot)
            if (loai === 'thanh_keo' && cotDef && cotDef.kieu !== 'dinh_luong' && cotDef.kieu !== 'thu_tu') {
              lyDo.push(`${viTri} kiểu thanh_keo yêu cầu cột dinh_luong hoặc thu_tu`)
            }
          }
        }

        if (rawParam.mac_dinh !== undefined) {
          if (!isRecord(rawParam.mac_dinh) || !('o' in rawParam.mac_dinh)) {
            lyDo.push(`${viTri}.mac_dinh phải là tham chiếu ô { o: ... }, không nhận số tự do`)
          } else {
            kiemKhoaLa(rawParam.mac_dinh, new Set(['o']), `${viTri}.mac_dinh`, lyDo)
            kiemThamChieuO(rawParam.mac_dinh.o, `${viTri}.mac_dinh.o`, dsMap, lyDo)
          }
        }
      })
    }
  }

  // Kiểm các lớp vẽ
  let tongDiem = 0
  if (!Array.isArray(dacTa.lop) || dacTa.lop.length === 0) {
    lyDo.push('lop phải là mảng có ít nhất 1 lớp')
  } else {
    if (dacTa.lop.length > TOI_DA_LOP) {
      lyDo.push(`Quá ${TOI_DA_LOP} lớp (${dacTa.lop.length})`)
    }
    dacTa.lop.forEach((rawLayer, idx) => {
      const viTri = `lop[${idx}]`
      if (!isRecord(rawLayer)) {
        lyDo.push(`${viTri} phải là đối tượng`)
        return
      }
      kiemKhoaLa(rawLayer, KHOA_LOP, viTri, lyDo)
      const dau = rawLayer.dau
      if (typeof dau !== 'string' || !TAP_DAU.has(dau as LoaiDau)) {
        lyDo.push(`${viTri}.dau "${String(dau ?? '')}" không hợp lệ`)
        return
      }
      const dsId = rawLayer.du_lieu
      const dsEntry = typeof dsId === 'string' ? dsMap.get(dsId) : undefined
      if (!dsEntry) {
        lyDo.push(`${viTri}.du_lieu "${String(dsId ?? '')}" không tồn tại`)
        return
      }
      tongDiem += dsEntry.ds.dong.length

      if (rawLayer.loc !== undefined) {
        if (!Array.isArray(rawLayer.loc)) {
          lyDo.push(`${viTri}.loc phải là mảng`)
        } else {
          rawLayer.loc.forEach((rawFilter, fIdx) => {
            const fViTri = `${viTri}.loc[${fIdx}]`
            if (!isRecord(rawFilter)) {
              lyDo.push(`${fViTri} phải là đối tượng`)
              return
            }
            kiemKhoaLa(rawFilter, KHOA_LOC, fViTri, lyDo)
            if (typeof rawFilter.cot !== 'string' || !dsEntry.cotMap.has(rawFilter.cot)) {
              lyDo.push(`${fViTri}.cot "${String(rawFilter.cot ?? '')}" không có trong ${dsId}`)
            }
            const hasBang = typeof rawFilter.bang_tham_so === 'string'
            const hasTrong = typeof rawFilter.trong_tham_so === 'string'
            if (hasBang === hasTrong) {
              lyDo.push(`${fViTri} phải có đúng một trong bang_tham_so hoặc trong_tham_so`)
            } else {
              const targetParam = hasBang
                ? (rawFilter.bang_tham_so as string)
                : (rawFilter.trong_tham_so as string)
              if (!thamSoMap.has(targetParam)) {
                lyDo.push(`${fViTri} trỏ tới tham số "${targetParam}" chưa khai báo`)
              }
            }
          })
        }
      }

      if (!isRecord(rawLayer.ma_hoa)) {
        lyDo.push(`${viTri}.ma_hoa phải là đối tượng`)
        return
      }
      kiemKhoaLa(rawLayer.ma_hoa, KHOA_MA_HOA, `${viTri}.ma_hoa`, lyDo)
      const mh = rawLayer.ma_hoa
      const xCot = mh.x !== undefined ? kiemKenhViTri(mh.x, `${viTri}.ma_hoa.x`, dsEntry, dsMap, lyDo) : null
      const yCot = mh.y !== undefined ? kiemKenhViTri(mh.y, `${viTri}.ma_hoa.y`, dsEntry, dsMap, lyDo) : null
      const xTuCot = mh.x_tu !== undefined ? kiemKenhViTri(mh.x_tu, `${viTri}.ma_hoa.x_tu`, dsEntry, dsMap, lyDo) : null
      const xDenCot = mh.x_den !== undefined ? kiemKenhViTri(mh.x_den, `${viTri}.ma_hoa.x_den`, dsEntry, dsMap, lyDo) : null
      const yTuCot = mh.y_tu !== undefined ? kiemKenhViTri(mh.y_tu, `${viTri}.ma_hoa.y_tu`, dsEntry, dsMap, lyDo) : null
      const yDenCot = mh.y_den !== undefined ? kiemKenhViTri(mh.y_den, `${viTri}.ma_hoa.y_den`, dsEntry, dsMap, lyDo) : null

      if (mh.mau !== undefined) kiemMaHoaCot(mh.mau, `${viTri}.ma_hoa.mau`, dsEntry, lyDo)
      if (mh.nhom !== undefined) kiemMaHoaCot(mh.nhom, `${viTri}.ma_hoa.nhom`, dsEntry, lyDo)
      if (mh.can_cu !== undefined) kiemMaHoaCot(mh.can_cu, `${viTri}.ma_hoa.can_cu`, dsEntry, lyDo)
      if (mh.kich_thuoc !== undefined) {
        const ktCot = kiemMaHoaCot(mh.kich_thuoc, `${viTri}.ma_hoa.kich_thuoc`, dsEntry, lyDo)
        if (ktCot && ktCot.kieu !== 'dinh_luong') {
          lyDo.push(`${viTri}.ma_hoa.kich_thuoc yêu cầu cột dinh_luong`)
        }
      }
      if (mh.nhan !== undefined) {
        if (!isRecord(mh.nhan)) {
          lyDo.push(`${viTri}.ma_hoa.nhan phải là đối tượng { cot } hoặc { chu }`)
        } else if ('chu' in mh.nhan) {
          kiemKhoaLa(mh.nhan, new Set(['chu']), `${viTri}.ma_hoa.nhan`, lyDo)
          kiemChuAnToan(mh.nhan.chu, `${viTri}.ma_hoa.nhan.chu`, lyDo, { camSoTuDo: true })
        } else {
          kiemMaHoaCot(mh.nhan, `${viTri}.ma_hoa.nhan`, dsEntry, lyDo)
        }
      }

      // Kiểm ràng buộc theo loại dấu
      if (dau === 'dai') {
        const hasXRange = mh.x_tu !== undefined && mh.x_den !== undefined
        const hasYRange = mh.y_tu !== undefined && mh.y_den !== undefined
        if (!hasXRange && !hasYRange) {
          lyDo.push(`${viTri} dấu "dai" cần cặp x_tu/x_den hoặc y_tu/y_den`)
        }
        if (hasXRange && xTuCot && xDenCot) {
          if (xTuCot.kieu !== 'dinh_luong' && xTuCot.kieu !== 'thoi_gian') {
            lyDo.push(`${viTri}.ma_hoa.x_tu phải là cột dinh_luong hoặc thoi_gian`)
          }
          if (xDenCot.kieu !== 'dinh_luong' && xDenCot.kieu !== 'thoi_gian') {
            lyDo.push(`${viTri}.ma_hoa.x_den phải là cột dinh_luong hoặc thoi_gian`)
          }
        }
        if (hasYRange && yTuCot && yDenCot) {
          if (yTuCot.kieu !== 'dinh_luong' && yTuCot.kieu !== 'thoi_gian') {
            lyDo.push(`${viTri}.ma_hoa.y_tu phải là cột dinh_luong hoặc thoi_gian`)
          }
          if (yDenCot.kieu !== 'dinh_luong' && yDenCot.kieu !== 'thoi_gian') {
            lyDo.push(`${viTri}.ma_hoa.y_den phải là cột dinh_luong hoặc thoi_gian`)
          }
        }
      } else if (dau === 'o') {
        if (mh.x === undefined || mh.y === undefined) {
          lyDo.push(`${viTri} dấu "o" cần đủ kênh x và y`)
        }
      } else if (dau === 'duong' || dau === 'vung') {
        if (mh.x === undefined || mh.y === undefined) {
          lyDo.push(`${viTri} dấu "${dau}" cần đủ kênh x và y`)
        } else if (yCot && yCot.kieu !== 'dinh_luong') {
          lyDo.push(`${viTri} dấu "${dau}" yêu cầu kênh y kiểu dinh_luong`)
        }
      } else if (dau === 'cot') {
        if (mh.x === undefined || mh.y === undefined) {
          lyDo.push(`${viTri} dấu "cot" cần đủ kênh x và y`)
        } else if (xCot && yCot && xCot.kieu !== 'dinh_luong' && yCot.kieu !== 'dinh_luong') {
          lyDo.push(`${viTri} dấu "cot" cần ít nhất một trục kiểu dinh_luong`)
        }
      } else if (mh.x === undefined && mh.y === undefined) {
        lyDo.push(`${viTri} dấu "${dau}" cần ít nhất một kênh x hoặc y`)
      }
    })
  }

  if (tongDiem > TOI_DA_DIEM) {
    lyDo.push(`Tổng số điểm vượt quá trần ${TOI_DA_DIEM} (${tongDiem} điểm)`)
  }

  // Kiểm cấu hình trục
  if (dacTa.truc !== undefined) {
    if (!isRecord(dacTa.truc)) {
      lyDo.push('truc phải là đối tượng')
    } else {
      kiemKhoaLa(dacTa.truc, KHOA_TRUC_GOC, 'truc', lyDo)
      for (const tenTruc of ['x', 'y'] as const) {
        const trucVal = dacTa.truc[tenTruc]
        if (trucVal === undefined || trucVal === null) {
          continue
        }
        if (!isRecord(trucVal)) {
          lyDo.push(`truc.${tenTruc} phải là đối tượng hoặc null`)
          continue
        }
        kiemKhoaLa(trucVal, KHOA_TRUC, `truc.${tenTruc}`, lyDo)
        kiemChuAnToan(trucVal.tieu_de, `truc.${tenTruc}.tieu_de`, lyDo)
        if (trucVal.mien !== undefined) {
          if (typeof trucVal.mien !== 'string' || !TAP_MIEN_TRUC.has(trucVal.mien as MienTruc)) {
            lyDo.push(`truc.${tenTruc}.mien chỉ nhận "tu_du_lieu" hoặc "tu_0"`)
          }
        }
      }
    }
  }

  // Kiểm so_hien
  if (dacTa.so_hien !== undefined) {
    if (!Array.isArray(dacTa.so_hien)) {
      lyDo.push('so_hien phải là mảng')
    } else {
      kiemMangGiaTri(dacTa.so_hien, 'so_hien', lyDo)
      dacTa.so_hien.forEach((rawItem, idx) => {
        const viTri = `so_hien[${idx}]`
        if (!isRecord(rawItem)) {
          lyDo.push(`${viTri} phải là đối tượng`)
          return
        }
        kiemKhoaLa(rawItem, KHOA_SO_HIEN, viTri, lyDo)
        kiemChuAnToan(rawItem.nhan, `${viTri}.nhan`, lyDo, { camSoTuDo: true })
        if (('o' in rawItem) === ('o_theo_khoang' in rawItem)) lyDo.push(`${viTri} cần đúng một tham chiếu`)
        else if ('o' in rawItem) kiemThamChieuO(rawItem.o, `${viTri}.o`, dsMap, lyDo)
        else kiemKhoang(rawItem.o_theo_khoang, `${viTri}.o_theo_khoang`, dsMap, lyDo)
      })
    }
  }

  // Kiểm cong_thuc (chỉ mã đăng ký, không nhận biểu thức công thức)
  if (dacTa.cong_thuc !== undefined) {
    if (typeof dacTa.cong_thuc !== 'string' || !MAU_MA_CONG_THUC.test(dacTa.cong_thuc)) {
      lyDo.push('cong_thuc phải là mã công thức hợp lệ (snake_case)')
    }
  }

  // Kiểm nguon
  if (!Array.isArray(dacTa.nguon) || dacTa.nguon.length === 0) {
    lyDo.push('nguon phải là mảng có ít nhất 1 mã căn cứ')
  } else {
    dacTa.nguon.forEach((item, idx) => {
      kiemChuAnToan(item, `nguon[${idx}]`, lyDo)
    })
  }

  if (lyDo.length > 0) {
    return { hopLe: false, lyDo }
  }

  return {
    hopLe: true,
    dacTa: dacTa as unknown as DacTaMinhHoa,
    tongDiem,
  }
}
