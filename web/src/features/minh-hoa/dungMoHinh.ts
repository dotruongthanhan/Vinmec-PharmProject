/** Bộ dựng mô hình vẽ thuần từ đặc tả `mh-0`, bộ dữ liệu và trạng thái điều khiển. */

import type {
  BoDuLieu,
  BoLocLop,
  CotDuLieu,
  DacTaMinhHoa,
  DinhDangSo,
  GiaTriO,
  KenhViTri,
  KieuCot,
  LopMinhHoa,
  ThamChieuO,
  ThamSoDieuKhien,
} from './nguPhap'

export type GiaTriThamSo = GiaTriO | readonly GiaTriO[]
export type TrangThaiDieuKhien = Readonly<Record<string, GiaTriThamSo>>
export type HinhDangDiem = 'tron' | 'vuong' | 'tam_giac' | 'thoi' | 'dau_cong' | 'vong'
export type HoaTietCot = 'tron' | 'soc_cheo' | 'cham' | 'ngang'
export type KieuVien = 'lien' | 'dut' | 'cham'

export interface KichThuocKhung {
  rong?: number
  cao?: number
}

export interface VachTruc {
  toaDo: number
  nhan: string
}

export interface MoHinhTruc {
  tieuDe: string
  kieu: KieuCot
  vach: readonly VachTruc[]
}

export interface MucSoHienDaGiai {
  nhan: string
  giaTri: string
  giaTriGoc: GiaTriO
  donVi: string | null
  laGiaDinh: boolean
}

export interface MucChuGiai {
  nhan: string
  mau: string
  mauNen?: string
  mauChu?: string
  netDut?: string
  netVien?: KieuVien
  hinhDang?: HinhDangDiem
  kyHieu?: string
  coSoc?: boolean
}

export interface PhanTuDai {
  loai: 'dai'
  ma: string
  x: number
  y: number
  rong: number
  cao: number
  nhan: string
  khoangChu: string
  mauNen: string
  mauVien: string
  mauChu: string
  coSoc: boolean
  giaTriTu: number | null
  giaTriDen: number | null
  moTa: string
  nguon: readonly string[]
}

export interface PhanTuDuong {
  loai: 'duong'
  ma: string
  nhom: string
  diemPath: string
  mau: string
  netDut: string
  doDay: number
  moTa: string
  nguon: readonly string[]
}

export interface PhanTuVung {
  loai: 'vung'
  ma: string
  nhom: string
  path: string
  mau: string
  moTa: string
  nguon: readonly string[]
}

export interface PhanTuCot {
  loai: 'cot'
  ma: string
  x: number
  y: number
  rong: number
  cao: number
  giaTri: number
  giaTriChu: string
  nhanX: string
  nhom: string
  mau: string
  mauNen: string
  hoaTiet: HoaTietCot
  moTa: string
  nguon: readonly string[]
}

export interface PhanTuDiem {
  loai: 'diem'
  ma: string
  cx: number
  cy: number
  r: number
  giaTriX: GiaTriO
  giaTriY: GiaTriO
  giaTriChu: string
  nhom: string
  hinhDang: HinhDangDiem
  mau: string
  laGiaDinh: boolean
  nhan: string | null
  moTa: string
  nguon: readonly string[]
}

export interface PhanTuO {
  loai: 'o'
  ma: string
  x: number
  y: number
  rong: number
  cao: number
  thuocA: string
  thuocB: string
  mucDo: string
  nhanMucDo: string
  kyHieu: string
  mauNen: string
  mauVien: string
  mauChu: string
  netVien: KieuVien
  coChe: string
  maCanCu: string | null
  moTa: string
  nguon: readonly string[]
}

export interface PhanTuQuyTac {
  loai: 'quy_tac'
  ma: string
  huong: 'doc' | 'ngang'
  x1: number
  y1: number
  x2: number
  y2: number
  giaTri: number
  giaTriChu: string
  nhan: string | null
  moTa: string
  nguon: readonly string[]
}

export interface PhanTuChu {
  loai: 'chu'
  ma: string
  x: number
  y: number
  noiDung: string
  mau: string
  moTa: string
  nguon: readonly string[]
}

export type PhanTuVe =
  | PhanTuDai
  | PhanTuDuong
  | PhanTuVung
  | PhanTuCot
  | PhanTuDiem
  | PhanTuO
  | PhanTuQuyTac
  | PhanTuChu

export interface MoHinhVe {
  rong: number
  cao: number
  vungVe: { trai: number; phai: number; tren: number; duoi: number }
  tieuDe: string
  phuDe: string
  laGiaDinh: boolean
  nguon: readonly string[]
  soHien: readonly MucSoHienDaGiai[]
  trucX: MoHinhTruc | null
  trucY: MoHinhTruc | null
  phanTu: readonly PhanTuVe[]
  chuGiai: readonly MucChuGiai[]
}

export interface KieuMucDo {
  nhan: string
  kyHieu: string
  mauNen: string
  mauVien: string
  mauChu: string
  netVien: KieuVien
}

export const MUC_DO_HIEN_THI: Readonly<Record<string, KieuMucDo>> = {
  chong_chi_dinh: {
    nhan: 'Chống chỉ định',
    kyHieu: 'C',
    mauNen: 'var(--color-danger-bg)',
    mauVien: 'var(--color-danger-solid)',
    mauChu: 'var(--color-danger-fg)',
    netVien: 'lien',
  },
  nghiem_trong: {
    nhan: 'Nghiêm trọng',
    kyHieu: 'N',
    mauNen: 'var(--color-danger-bg)',
    mauVien: 'var(--color-danger-solid)',
    mauChu: 'var(--color-danger-fg)',
    netVien: 'lien',
  },
  can_luu_y: {
    nhan: 'Cần lưu ý',
    kyHieu: 'L',
    mauNen: 'var(--color-warning-bg)',
    mauVien: 'var(--color-warning-solid)',
    mauChu: 'var(--color-warning-fg)',
    netVien: 'lien',
  },
  thieu_du_lieu: {
    nhan: 'Thiếu dữ liệu',
    kyHieu: '?',
    mauNen: 'var(--color-missing-bg)',
    mauVien: 'var(--color-missing-solid)',
    mauChu: 'var(--color-missing-fg)',
    netVien: 'dut',
  },
  khong_phat_hien: {
    nhan: 'Không phát hiện',
    kyHieu: '–',
    mauNen: 'var(--color-success-bg)',
    mauVien: 'var(--color-success-line)',
    mauChu: 'var(--color-success-fg)',
    netVien: 'lien',
  },
  khong_ap_dung: {
    nhan: 'Không áp dụng',
    kyHieu: '×',
    mauNen: 'var(--color-neutral-bg)',
    mauVien: 'var(--color-neutral-line)',
    mauChu: 'var(--color-neutral-fg)',
    netVien: 'cham',
  },
}

const NHAN_MA_DANH_MUC: Readonly<Record<string, string>> = {
  thuc_te: 'Thực tế',
  ly_tuong: 'Lý tưởng (IBW)',
  hieu_chinh: 'Hiệu chỉnh (AdjBW)',
  chong_chi_dinh: 'Chống chỉ định',
  nghiem_trong: 'Nghiêm trọng',
  can_luu_y: 'Cần lưu ý',
  thieu_du_lieu: 'Thiếu dữ liệu',
  khong_phat_hien: 'Không phát hiện',
  khong_ap_dung: 'Không áp dụng',
}

interface PhongCachChuoi {
  mau: string
  mauNen: string
  netDut: string
  hinhDang: HinhDangDiem
  hoaTiet: HoaTietCot
}

const BANG_CHUOI: readonly PhongCachChuoi[] = [
  {
    mau: 'var(--color-primary)',
    mauNen: 'var(--color-primary-soft)',
    netDut: '',
    hinhDang: 'tron',
    hoaTiet: 'tron',
  },
  {
    mau: 'var(--color-warning-solid)',
    mauNen: 'var(--color-warning-bg)',
    netDut: '6 3',
    hinhDang: 'vuong',
    hoaTiet: 'soc_cheo',
  },
  {
    mau: 'var(--color-offlabel-solid)',
    mauNen: 'var(--color-offlabel-bg)',
    netDut: '2 3',
    hinhDang: 'tam_giac',
    hoaTiet: 'cham',
  },
  {
    mau: 'var(--color-success-solid)',
    mauNen: 'var(--color-success-bg)',
    netDut: '8 3 2 3',
    hinhDang: 'thoi',
    hoaTiet: 'ngang',
  },
  {
    mau: 'var(--color-danger-solid)',
    mauNen: 'var(--color-danger-bg)',
    netDut: '4 2',
    hinhDang: 'dau_cong',
    hoaTiet: 'soc_cheo',
  },
  {
    mau: 'var(--color-missing-solid)',
    mauNen: 'var(--color-missing-bg)',
    netDut: '10 4',
    hinhDang: 'vong',
    hoaTiet: 'cham',
  },
]

/** Đổi mã danh mục quen thuộc sang nhãn tiếng Việt dễ đọc; giữ nguyên chuỗi chưa biết. */
export function nhanHienThiGiaTri(value: GiaTriO): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'Cần chỉnh liều' : 'Không cần chỉnh'
  if (typeof value === 'number') return dinhDangGiaTri(value)
  return NHAN_MA_DANH_MUC[value] ?? value
}

/** Định dạng giá trị ô theo chuẩn dấu phẩy thập phân tiếng Việt (chỉ làm tròn ở lớp hiển thị). */
export function dinhDangGiaTri(value: GiaTriO, dinhDang?: DinhDangSo): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'Cần chỉnh liều' : 'Không cần chỉnh'
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return '—'
    if (dinhDang === '0') {
      return String(Math.round(value))
    }
    if (dinhDang === '0.0') {
      return value.toFixed(1).replace('.', ',')
    }
    if (dinhDang === '0.00') {
      return value.toFixed(2).replace('.', ',')
    }
    if (Number.isInteger(value)) {
      return String(value)
    }
    return value.toFixed(1).replace(/\.0$/, '').replace('.', ',')
  }
  return value
}

function dinhDangNgayNgan(raw: string): string {
  const iso = /^(\d{4})-(\d{2})-(\d{2})/.exec(raw.trim())
  if (iso) {
    return `${iso[3]}/${iso[2]}`
  }
  return raw
}

function chuyenThoiGianMs(raw: GiaTriO): number | null {
  if (typeof raw !== 'string') return null
  const ms = Date.parse(raw)
  return Number.isFinite(ms) ? ms : null
}

function timBoDuLieu(boDuLieu: readonly BoDuLieu[], ma: string): BoDuLieu | undefined {
  return boDuLieu.find((ds) => ds.ma === ma)
}

function timCot(ds: BoDuLieu, ten: string): CotDuLieu | undefined {
  return ds.cot.find((c) => c.ten === ten)
}

function giaTriBangNhau(a: GiaTriO, b: GiaTriO): boolean {
  if (typeof a === 'number' && typeof b === 'number') {
    return Math.abs(a - b) < 1e-9
  }
  return a === b
}

/** Lấy danh sách giá trị duy nhất cho một tham số điều khiển từ cột dữ liệu. */
export function layGiaTriThamSoTuyChon(
  thamSo: ThamSoDieuKhien,
  boDuLieu: readonly BoDuLieu[],
): GiaTriO[] {
  if (!thamSo.gia_tri_tu) return []
  const ds = timBoDuLieu(boDuLieu, thamSo.gia_tri_tu.ds)
  if (!ds) return []
  const tenCot = thamSo.gia_tri_tu.cot
  const result: GiaTriO[] = []
  for (const row of ds.dong) {
    const val = row[tenCot] ?? null
    if (val === null) continue
    if (!result.some((item) => giaTriBangNhau(item, val))) {
      result.push(val)
    }
  }
  if (thamSo.loai === 'thanh_keo') {
    result.sort((a, b) => Number(a) - Number(b))
  }
  return result
}

function layBoLocChoDs(dacTa: DacTaMinhHoa, dsMa: string): readonly BoLocLop[] {
  for (const lop of dacTa.lop) {
    if (lop.du_lieu === dsMa && lop.loc && lop.loc.length > 0) {
      return lop.loc
    }
  }
  const fallback: BoLocLop[] = []
  for (const ts of dacTa.tham_so ?? []) {
    if (!ts.ma || !ts.gia_tri_tu || ts.gia_tri_tu.ds !== dsMa) continue
    if (ts.loai === 'thanh_keo' || ts.loai === 'chon_mot') {
      fallback.push({ cot: ts.gia_tri_tu.cot, bang_tham_so: ts.ma })
    } else if (ts.loai === 'bat_tat' || ts.loai === 'loc') {
      fallback.push({ cot: ts.gia_tri_tu.cot, trong_tham_so: ts.ma })
    }
  }
  return fallback
}

function locDongTheoThamSo(
  dong: readonly Record<string, GiaTriO>[],
  loc: readonly BoLocLop[] | undefined,
  trangThai: TrangThaiDieuKhien,
): Record<string, GiaTriO>[] {
  if (!loc || loc.length === 0) {
    return [...dong]
  }
  return dong.filter((row) =>
    loc.every((rule) => {
      const cell = row[rule.cot] ?? null
      if (rule.bang_tham_so) {
        const expected = trangThai[rule.bang_tham_so]
        if (expected === undefined || Array.isArray(expected)) return true
        return giaTriBangNhau(cell, expected as GiaTriO)
      }
      if (rule.trong_tham_so) {
        const allowed = trangThai[rule.trong_tham_so]
        if (!Array.isArray(allowed)) return true
        return allowed.some((item) => giaTriBangNhau(cell, item))
      }
      return true
    }),
  )
}

function giaiThamChieuO(
  ref: ThamChieuO,
  dacTa: DacTaMinhHoa,
  boDuLieu: readonly BoDuLieu[],
  trangThai: TrangThaiDieuKhien,
): { giaTri: GiaTriO; donVi: string | null } {
  const ds = timBoDuLieu(boDuLieu, ref.ds)
  if (!ds) return { giaTri: null, donVi: null }
  const cot = timCot(ds, ref.cot)
  const donVi = cot?.don_vi ?? null

  if (ref.dong !== undefined) {
    const row = ds.dong[ref.dong]
    return { giaTri: row ? (row[ref.cot] ?? null) : null, donVi }
  }
  if (ref.theo_tham_so) {
    const loc = layBoLocChoDs(dacTa, ref.ds)
    const matched = locDongTheoThamSo(ds.dong, loc, trangThai)
    const first = matched[0]
    return { giaTri: first ? (first[ref.cot] ?? null) : null, donVi }
  }
  return { giaTri: null, donVi }
}

function giaiKhoang(ref: import('./nguPhap').ThamChieuKhoang, dacTa: DacTaMinhHoa, boDuLieu: readonly BoDuLieu[], trangThai: TrangThaiDieuKhien): { giaTri: GiaTriO; donVi: string | null } {
  const value = giaiThamChieuO(ref.gia_tri, dacTa, boDuLieu, trangThai).giaTri
  const ds = timBoDuLieu(boDuLieu, ref.ds)
  if (typeof value !== 'number' || !ds) return { giaTri: null, donVi: null }
  const row = ds.dong.find((r) => (r[ref.tu] === null || (typeof r[ref.tu] === 'number' &&
    (r[ref.bao_gom_tu] === true ? value >= (r[ref.tu] as number) : value > (r[ref.tu] as number)))) &&
    (r[ref.den] === null || (typeof r[ref.den] === 'number' &&
    (r[ref.bao_gom_den] === true ? value <= (r[ref.den] as number) : value < (r[ref.den] as number)))))
  return { giaTri: row?.[ref.cot] ?? null, donVi: timCot(ds, ref.cot)?.don_vi ?? null }
}

/** Tạo trạng thái mặc định cho tất cả điều khiển từ `mac_dinh` hoặc dữ liệu gốc. */
export function taoTrangThaiMacDinh(
  dacTa: DacTaMinhHoa,
  boDuLieu: readonly BoDuLieu[],
): Record<string, GiaTriThamSo> {
  const state: Record<string, GiaTriThamSo> = {}
  for (const ts of dacTa.tham_so ?? []) {
    if (ts.loai === 'dat_lai' || !ts.ma) continue
    if (ts.mac_dinh?.o) {
      const resolved = giaiThamChieuO(ts.mac_dinh.o, dacTa, boDuLieu, state)
      if (resolved.giaTri !== null) {
        state[ts.ma] =
          ts.loai === 'bat_tat' || ts.loai === 'loc' ? [resolved.giaTri] : resolved.giaTri
        continue
      }
    }
    const options = layGiaTriThamSoTuyChon(ts, boDuLieu)
    if (ts.loai === 'bat_tat' || ts.loai === 'loc') {
      state[ts.ma] = options
    } else {
      state[ts.ma] = options[0] ?? null
    }
  }
  return state
}

/** Kiểm tra xem tham số gắn cờ giả định có đang lệch khỏi giá trị mặc định của ca hay không. */
export function kiemTrangThaiGiaDinh(
  dacTa: DacTaMinhHoa,
  boDuLieu: readonly BoDuLieu[],
  trangThai: TrangThaiDieuKhien,
): boolean {
  const macDinh = taoTrangThaiMacDinh(dacTa, boDuLieu)
  for (const ts of dacTa.tham_so ?? []) {
    if (!ts.ma) continue
    const defVal = macDinh[ts.ma]
    const curVal = trangThai[ts.ma]
    if (curVal === undefined || defVal === undefined) continue
    if (Array.isArray(curVal) && Array.isArray(defVal)) {
      if (curVal.length !== defVal.length || curVal.some((v) => !defVal.some((d) => giaTriBangNhau(v, d)))) return true
    } else if (!Array.isArray(curVal) && !Array.isArray(defVal)) {
      if (!giaTriBangNhau(curVal as GiaTriO, defVal as GiaTriO)) {
        return true
      }
    } else return true
  }
  return false
}

function docKenhViTri(
  kenh: KenhViTri | undefined,
  row: Record<string, GiaTriO>,
  dacTa: DacTaMinhHoa,
  boDuLieu: readonly BoDuLieu[],
  trangThai: TrangThaiDieuKhien,
): GiaTriO {
  if (!kenh) return null
  if ('o' in kenh) {
    return giaiThamChieuO(kenh.o, dacTa, boDuLieu, trangThai).giaTri
  }
  return row[kenh.cot] ?? null
}

function taoVachSo(minVal: number, maxVal: number, soVach = 5): number[] {
  if (!Number.isFinite(minVal) || !Number.isFinite(maxVal)) return []
  if (Math.abs(maxVal - minVal) < 1e-9) return [minVal]
  const rawStep = (maxVal - minVal) / Math.max(1, soVach - 1)
  const magnitude = 10 ** Math.floor(Math.log10(rawStep))
  const normalized = rawStep / magnitude
  const niceNorm = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10
  const step = niceNorm * magnitude
  const start = Math.ceil(minVal / step) * step
  const ticks: number[] = []
  for (let v = start; v <= maxVal + step * 1e-6; v += step) {
    ticks.push(Number(v.toFixed(6)))
    if (ticks.length > 12) break
  }
  if (ticks.length === 0) {
    return [minVal, maxVal]
  }
  return ticks
}

function layKieuTrucTuCacLop(
  dacTa: DacTaMinhHoa,
  boDuLieu: readonly BoDuLieu[],
  kenh: 'x' | 'y',
): KieuCot {
  for (const lop of dacTa.lop) {
    const ds = timBoDuLieu(boDuLieu, lop.du_lieu)
    if (!ds) continue
    const mh = lop.ma_hoa
    const candidates: (KenhViTri | undefined)[] =
      kenh === 'x' ? [mh.x, mh.x_tu, mh.x_den] : [mh.y, mh.y_tu, mh.y_den]
    for (const item of candidates) {
      if (!item) continue
      if ('cot' in item) {
        const cot = timCot(ds, item.cot)
        if (cot) return cot.kieu
      } else {
        const refDs = timBoDuLieu(boDuLieu, item.o.ds)
        const cot = refDs ? timCot(refDs, item.o.cot) : undefined
        if (cot) return cot.kieu
      }
    }
  }
  return 'dinh_luong'
}

function layPhongCachNhom(danhSachNhom: readonly string[], nhom: string): PhongCachChuoi {
  const idx = Math.max(0, danhSachNhom.indexOf(nhom))
  return BANG_CHUOI[idx % BANG_CHUOI.length]
}

function taoKhoangChu(tu: number | null, den: number | null): string {
  if (tu === null && den !== null) return `<${dinhDangGiaTri(den)}`
  if (tu !== null && den === null) return `>${dinhDangGiaTri(tu)}`
  if (tu !== null && den !== null) return `${dinhDangGiaTri(tu)}–${dinhDangGiaTri(den)}`
  return ''
}

function dungMoHinhMaTran(
  dacTa: DacTaMinhHoa,
  boDuLieu: readonly BoDuLieu[],
  trangThai: TrangThaiDieuKhien,
  rong: number,
  phuDe: string,
  soHien: readonly MucSoHienDaGiai[],
): MoHinhVe {
  const lopO = dacTa.lop.find((item) => item.dau === 'o')
  const ds = lopO ? timBoDuLieu(boDuLieu, lopO.du_lieu) : undefined
  if (!lopO || !ds) {
    return {
      rong,
      cao: 200,
      vungVe: { trai: 40, phai: rong - 20, tren: 24, duoi: 170 },
      tieuDe: dacTa.tieu_de,
      phuDe,
      laGiaDinh: false,
      nguon: dacTa.nguon,
      soHien,
      trucX: null,
      trucY: null,
      phanTu: [],
      chuGiai: [],
    }
  }

  // Giữ đầy đủ danh sách thuốc trên cả hai trục từ toàn bộ bộ dữ liệu (không nhảy trục khi lọc)
  const danhSachThuoc: string[] = []
  for (const row of ds.dong) {
    const a = docKenhViTri(lopO.ma_hoa.x, row, dacTa, boDuLieu, trangThai)
    const b = docKenhViTri(lopO.ma_hoa.y, row, dacTa, boDuLieu, trangThai)
    if (typeof a === 'string' && !danhSachThuoc.includes(a)) danhSachThuoc.push(a)
    if (typeof b === 'string' && !danhSachThuoc.includes(b)) danhSachThuoc.push(b)
  }

  const n = Math.max(1, danhSachThuoc.length)
  const compact = rong < 480
  const labelLeft = compact ? 92 : 136
  const padRight = compact ? 28 : 56
  const tren = compact ? 52 : 76
  const vungRong = Math.max(120, rong - labelLeft - padRight)
  const cellSize = Math.max(32, Math.min(72, Math.floor(vungRong / n)))
  const gridWidth = cellSize * n
  const gridHeight = cellSize * n
  const tongRongNoiDung = labelLeft + gridWidth + padRight
  const leTraiThem = rong > tongRongNoiDung ? Math.floor((rong - tongRongNoiDung) / 2) : 0
  const trai = labelLeft + leTraiThem
  const cao = tren + gridHeight + 24

  const rows = locDongTheoThamSo(ds.dong, lopO.loc, trangThai)
  const phanTu: PhanTuVe[] = []
  const mucDoDaDung = new Set<string>()

  rows.forEach((row, idx) => {
    const aVal = docKenhViTri(lopO.ma_hoa.x, row, dacTa, boDuLieu, trangThai)
    const bVal = docKenhViTri(lopO.ma_hoa.y, row, dacTa, boDuLieu, trangThai)
    const thuocA = typeof aVal === 'string' ? aVal : String(aVal ?? '')
    const thuocB = typeof bVal === 'string' ? bVal : String(bVal ?? '')
    const colIdx = danhSachThuoc.indexOf(thuocA)
    const rowIdx = danhSachThuoc.indexOf(thuocB)
    if (colIdx < 0 || rowIdx < 0) return

    const mucDoRaw = lopO.ma_hoa.mau ? row[lopO.ma_hoa.mau.cot] : null
    const mucDo = typeof mucDoRaw === 'string' ? mucDoRaw : 'khong_ap_dung'
    mucDoDaDung.add(mucDo)
    const style = MUC_DO_HIEN_THI[mucDo] ?? MUC_DO_HIEN_THI.khong_ap_dung

    let coChe = ''
    if (lopO.ma_hoa.nhan) {
      if ('chu' in lopO.ma_hoa.nhan) {
        coChe = lopO.ma_hoa.nhan.chu
      } else {
        const rawText = row[lopO.ma_hoa.nhan.cot]
        coChe = rawText !== null && rawText !== undefined ? String(rawText) : ''
      }
    }
    const maCanCuRaw = lopO.ma_hoa.can_cu ? row[lopO.ma_hoa.can_cu.cot] : null
    const maCanCu = typeof maCanCuRaw === 'string' ? maCanCuRaw : null

    const pad = 2
    phanTu.push({
      loai: 'o',
      ma: `o-${idx}-${colIdx}-${rowIdx}`,
      x: Number((trai + colIdx * cellSize + pad).toFixed(2)),
      y: Number((tren + rowIdx * cellSize + pad).toFixed(2)),
      rong: Math.max(12, cellSize - pad * 2),
      cao: Math.max(12, cellSize - pad * 2),
      thuocA,
      thuocB,
      mucDo,
      nhanMucDo: style.nhan,
      kyHieu: style.kyHieu,
      mauNen: style.mauNen,
      mauVien: style.mauVien,
      mauChu: style.mauChu,
      netVien: style.netVien,
      coChe,
      maCanCu,
      moTa: `${thuocA} × ${thuocB} · ${style.nhan}${coChe ? ` — ${coChe}` : ''}`,
      nguon: maCanCu ? [maCanCu, ...dacTa.nguon] : dacTa.nguon,
    })
  })

  const vachX: VachTruc[] = danhSachThuoc.map((ten, idx) => ({
    toaDo: Number((trai + idx * cellSize + cellSize / 2).toFixed(2)),
    nhan: compact && ten.length > 10 ? `${ten.slice(0, 9)}…` : ten,
  }))
  const vachY: VachTruc[] = danhSachThuoc.map((ten, idx) => ({
    toaDo: Number((tren + idx * cellSize + cellSize / 2).toFixed(2)),
    nhan: compact && ten.length > 12 ? `${ten.slice(0, 11)}…` : ten,
  }))

  const thuTuMucDo = [
    'chong_chi_dinh',
    'nghiem_trong',
    'can_luu_y',
    'thieu_du_lieu',
    'khong_phat_hien',
    'khong_ap_dung',
  ]
  const chuGiai: MucChuGiai[] = thuTuMucDo
    .filter((key) => mucDoDaDung.has(key) || ds.dong.some((r) => lopO.ma_hoa.mau && r[lopO.ma_hoa.mau.cot] === key))
    .map((key) => {
      const st = MUC_DO_HIEN_THI[key]
      return {
        nhan: st.nhan,
        mau: st.mauVien,
        mauNen: st.mauNen,
        mauChu: st.mauChu,
        netVien: st.netVien,
        kyHieu: st.kyHieu,
      }
    })

  return {
    rong: Math.max(rong, trai + gridWidth + padRight),
    cao,
    vungVe: { trai, phai: trai + gridWidth, tren, duoi: tren + gridHeight },
    tieuDe: dacTa.tieu_de,
    phuDe,
    laGiaDinh: false,
    nguon: dacTa.nguon,
    soHien,
    trucX: { tieuDe: dacTa.truc?.x?.tieu_de ?? '', kieu: 'danh_muc', vach: vachX },
    trucY: { tieuDe: dacTa.truc?.y?.tieu_de ?? '', kieu: 'danh_muc', vach: vachY },
    phanTu,
    chuGiai,
  }
}

/**
 * Hàm thuần dựng toàn bộ toạ độ SVG, thang đo và chữ hiển thị từ đặc tả `mh-0`.
 * Mọi con số nghiệp vụ đều lấy từ `boDuLieu`; hàm chỉ tính toạ độ hình học và vạch chia trục.
 */
export function dungMoHinh(
  dacTa: DacTaMinhHoa,
  boDuLieu: readonly BoDuLieu[],
  trangThai: TrangThaiDieuKhien,
  kichThuoc: KichThuocKhung = {},
): MoHinhVe {
  const rong = Math.max(300, Math.round(kichThuoc.rong ?? 640))
  const laGiaDinh = kiemTrangThaiGiaDinh(dacTa, boDuLieu, trangThai)

  const phuDe = (dacTa.phu_de ?? [])
    .map((part) => {
      if ('chu' in part) return part.chu
      if ('o_theo_khoang' in part) return dinhDangGiaTri(giaiKhoang(part.o_theo_khoang, dacTa, boDuLieu, trangThai).giaTri) + (laGiaDinh && part.o_theo_khoang.gia_tri.theo_tham_so ? ' (giả định)' : '')
      const resolved = giaiThamChieuO(part.o, dacTa, boDuLieu, trangThai)
      return dinhDangGiaTri(resolved.giaTri, part.o.dinh_dang) + (laGiaDinh && part.o.theo_tham_so ? ' (giả định)' : '')
    })
    .join('')

  const soHien: MucSoHienDaGiai[] = (dacTa.so_hien ?? []).map((item) => {
    const resolved = item.o_theo_khoang ? giaiKhoang(item.o_theo_khoang, dacTa, boDuLieu, trangThai) : item.o ? giaiThamChieuO(item.o, dacTa, boDuLieu, trangThai) : { giaTri: null, donVi: null }
    return {
      nhan: item.nhan,
      giaTri: dinhDangGiaTri(resolved.giaTri, item.o?.dinh_dang),
      giaTriGoc: resolved.giaTri,
      donVi: resolved.donVi,
      laGiaDinh: laGiaDinh && (item.o?.theo_tham_so === true || item.o_theo_khoang?.gia_tri.theo_tham_so === true),
    }
  })

  if (dacTa.lop.some((item) => item.dau === 'o')) {
    return { ...dungMoHinhMaTran(dacTa, boDuLieu, trangThai, rong, phuDe, soHien), laGiaDinh }
  }

  const coTrucY = dacTa.truc?.y !== null && dacTa.lop.some((l) => l.ma_hoa.y !== undefined || l.ma_hoa.y_tu !== undefined)
  const coDai = dacTa.lop.some((l) => l.dau === 'dai')
  const cao = Math.round(kichThuoc.cao ?? (coTrucY ? 268 : coDai ? 196 : 148))
  const trai = coTrucY ? 52 : 20
  const phai = rong - 20
  const tren = coTrucY ? 20 : 28
  const duoi = cao - (coTrucY ? 46 : 44)
  const daiDuoi = !coTrucY && coDai ? duoi - 30 : duoi
  const daiCao = Math.max(40, daiDuoi - tren)
  const plotW = Math.max(1, phai - trai)
  const plotH = Math.max(1, duoi - tren)

  const kieuX = layKieuTrucTuCacLop(dacTa, boDuLieu, 'x')
  const kieuY = coTrucY ? layKieuTrucTuCacLop(dacTa, boDuLieu, 'y') : 'dinh_luong'

  // Thu thập miền trục X và Y từ toàn bộ bộ dữ liệu của các lớp để thang đo ổn định khi kéo thanh
  const xNums: number[] = []
  const yNums: number[] = []
  const xCats: string[] = []
  const yCats: string[] = []
  const xTimes: number[] = []
  const danhSachNhom: string[] = []

  const thuThapNhom = (lop: LopMinhHoa, ds: BoDuLieu) => {
    const kenhNhom = lop.ma_hoa.nhom ?? lop.ma_hoa.mau
    if (!kenhNhom) return
    for (const row of ds.dong) {
      const val = row[kenhNhom.cot]
      if (typeof val === 'string' && !danhSachNhom.includes(val)) {
        danhSachNhom.push(val)
      }
    }
  }

  for (const lop of dacTa.lop) {
    const ds = timBoDuLieu(boDuLieu, lop.du_lieu)
    if (!ds) continue
    thuThapNhom(lop, ds)
    for (const row of ds.dong) {
      const xs = [
        docKenhViTri(lop.ma_hoa.x, row, dacTa, boDuLieu, trangThai),
        docKenhViTri(lop.ma_hoa.x_tu, row, dacTa, boDuLieu, trangThai),
        docKenhViTri(lop.ma_hoa.x_den, row, dacTa, boDuLieu, trangThai),
      ]
      for (const val of xs) {
        if (val === null) continue
        if (kieuX === 'dinh_luong' && typeof val === 'number') xNums.push(val)
        else if (kieuX === 'thoi_gian') {
          const ms = chuyenThoiGianMs(val)
          if (ms !== null) xTimes.push(ms)
        } else if (typeof val === 'string' && !xCats.includes(val)) {
          xCats.push(val)
        }
      }

      if (coTrucY) {
        const ys = [
          docKenhViTri(lop.ma_hoa.y, row, dacTa, boDuLieu, trangThai),
          docKenhViTri(lop.ma_hoa.y_tu, row, dacTa, boDuLieu, trangThai),
          docKenhViTri(lop.ma_hoa.y_den, row, dacTa, boDuLieu, trangThai),
        ]
        for (const val of ys) {
          if (val === null) continue
          if (kieuY === 'dinh_luong' && typeof val === 'number') yNums.push(val)
          else if (typeof val === 'string' && !yCats.includes(val)) yCats.push(val)
        }
      }
    }
  }

  // Xây dựng hàm ánh xạ toạ độ X
  let xMin = 0
  let xMax = 100
  if (kieuX === 'dinh_luong' && xNums.length > 0) {
    const rawMin = Math.min(...xNums)
    const rawMax = Math.max(...xNums)
    const fromZero = dacTa.truc?.x?.mien === 'tu_0'
    const pad = Math.max((rawMax - rawMin) * 0.06, 1)
    xMin = fromZero ? Math.min(0, rawMin) : rawMin - pad
    xMax = rawMax + pad
  } else if (kieuX === 'thoi_gian' && xTimes.length > 0) {
    xMin = Math.min(...xTimes)
    xMax = Math.max(...xTimes)
    if (xMin === xMax) {
      xMax = xMin + 86_400_000
    }
  }

  const mapX = (val: GiaTriO): number | null => {
    if (val === null) return null
    if (kieuX === 'dinh_luong' && typeof val === 'number') {
      const span = Math.max(1e-9, xMax - xMin)
      return Number((trai + ((val - xMin) / span) * plotW).toFixed(2))
    }
    if (kieuX === 'thoi_gian') {
      const ms = chuyenThoiGianMs(val)
      if (ms === null) return null
      const span = Math.max(1, xMax - xMin)
      return Number((trai + ((ms - xMin) / span) * plotW).toFixed(2))
    }
    const idx = xCats.indexOf(String(val))
    if (idx < 0 || xCats.length === 0) return null
    const step = plotW / xCats.length
    return Number((trai + idx * step + step / 2).toFixed(2))
  }

  // Xây dựng hàm ánh xạ toạ độ Y
  let yMin = 0
  let yMax = 100
  if (coTrucY && kieuY === 'dinh_luong' && yNums.length > 0) {
    const rawMin = Math.min(...yNums)
    const rawMax = Math.max(...yNums)
    const fromZero =
      dacTa.truc?.y?.mien === 'tu_0' || dacTa.lop.some((item) => item.dau === 'cot')
    const pad = Math.max((rawMax - rawMin) * 0.1, 1)
    yMin = fromZero ? Math.min(0, rawMin) : rawMin - pad
    yMax = rawMax + pad
  }

  const mapY = (val: GiaTriO): number => {
    if (!coTrucY) {
      return Number(((tren + duoi) / 2).toFixed(2))
    }
    if (kieuY === 'dinh_luong' && typeof val === 'number') {
      const span = Math.max(1e-9, yMax - yMin)
      return Number((duoi - ((val - yMin) / span) * plotH).toFixed(2))
    }
    const idx = yCats.indexOf(String(val ?? ''))
    if (idx < 0 || yCats.length === 0) return Number(((tren + duoi) / 2).toFixed(2))
    const step = plotH / yCats.length
    return Number((tren + idx * step + step / 2).toFixed(2))
  }

  // Dựng phần tử cho từng lớp
  const phanTu: PhanTuVe[] = []
  let daThemChuGiaiDai = false
  const chuGiai: MucChuGiai[] = []
  const nhomDaChuGiai = new Set<string>()

  dacTa.lop.forEach((lop, lopIdx) => {
    const ds = timBoDuLieu(boDuLieu, lop.du_lieu)
    if (!ds) return
    const rows = locDongTheoThamSo(ds.dong, lop.loc, trangThai)

    if (lop.dau === 'dai') {
      rows.forEach((row, rIdx) => {
        const tuVal = docKenhViTri(lop.ma_hoa.x_tu, row, dacTa, boDuLieu, trangThai)
        const denVal = docKenhViTri(lop.ma_hoa.x_den, row, dacTa, boDuLieu, trangThai)
        const tuNum = typeof tuVal === 'number' ? tuVal : null
        const denNum = typeof denVal === 'number' ? denVal : null
        const x1 = tuNum !== null ? (mapX(tuNum) ?? trai) : trai
        const x2 = denNum !== null ? (mapX(denNum) ?? phai) : phai
        const left = Math.max(trai, Math.min(x1, x2))
        const right = Math.min(phai, Math.max(x1, x2))

        const mauVal = lop.ma_hoa.mau ? row[lop.ma_hoa.mau.cot] : null
        const canChinh = mauVal === true || mauVal === 'can_chinh' || mauVal === 'nghiem_trong'
        const nhan =
          lop.ma_hoa.nhan && 'cot' in lop.ma_hoa.nhan
            ? String(row[lop.ma_hoa.nhan.cot] ?? '')
            : lop.ma_hoa.nhan && 'chu' in lop.ma_hoa.nhan
              ? lop.ma_hoa.nhan.chu
              : ''
        const coNhanKhoang = 'crcl_tu' in row || 'crcl_den' in row
        const nhanTu = coNhanKhoang ? (typeof row.crcl_tu === 'number' ? row.crcl_tu : null) : tuNum
        const nhanDen = coNhanKhoang ? (typeof row.crcl_den === 'number' ? row.crcl_den : null) : denNum
        const khoangChu = taoKhoangChu(nhanTu, nhanDen)

        phanTu.push({
          loai: 'dai',
          ma: `dai-${lopIdx}-${rIdx}`,
          x: Number(left.toFixed(2)),
          y: tren,
          rong: Number(Math.max(4, right - left).toFixed(2)),
          cao: coTrucY ? plotH : daiCao,
          nhan,
          khoangChu,
          mauNen: canChinh ? 'var(--color-warning-bg)' : 'var(--color-success-bg)',
          mauVien: canChinh ? 'var(--color-warning-line)' : 'var(--color-success-line)',
          mauChu: canChinh ? 'var(--color-warning-fg)' : 'var(--color-success-fg)',
          coSoc: canChinh,
          giaTriTu: tuNum,
          giaTriDen: denNum,
          moTa: `Mức CrCl ${khoangChu}: ${nhan}`,
          nguon: dacTa.nguon,
        })
      })
      if (!daThemChuGiaiDai) {
        daThemChuGiaiDai = true
        chuGiai.push(
          {
            nhan: 'Cần chỉnh liều',
            mau: 'var(--color-warning-line)',
            mauNen: 'var(--color-warning-bg)',
            coSoc: true,
          },
          {
            nhan: 'Không cần chỉnh',
            mau: 'var(--color-success-line)',
            mauNen: 'var(--color-success-bg)',
            coSoc: false,
          },
        )
      }
      return
    }

    if (lop.dau === 'quy_tac') {
      rows.forEach((row, rIdx) => {
        const nhan =
          lop.ma_hoa.nhan && 'chu' in lop.ma_hoa.nhan
            ? lop.ma_hoa.nhan.chu
            : lop.ma_hoa.nhan && 'cot' in lop.ma_hoa.nhan
              ? String(row[lop.ma_hoa.nhan.cot] ?? '')
              : null
        if (lop.ma_hoa.x) {
          const val = docKenhViTri(lop.ma_hoa.x, row, dacTa, boDuLieu, trangThai)
          const px = mapX(val)
          if (px === null || typeof val !== 'number') return
          const valText = dinhDangGiaTri(val, '0.0')
          phanTu.push({
            loai: 'quy_tac',
            ma: `qt-${lopIdx}-${rIdx}`,
            huong: 'doc',
            x1: px,
            y1: tren,
            x2: px,
            y2: !coTrucY && coDai ? daiDuoi : duoi,
            giaTri: val,
            giaTriChu: valText,
            nhan,
            moTa: `${nhan ?? 'Ngưỡng'}: ${valText}`,
            nguon: dacTa.nguon,
          })
        } else if (lop.ma_hoa.y) {
          const val = docKenhViTri(lop.ma_hoa.y, row, dacTa, boDuLieu, trangThai)
          if (typeof val !== 'number') return
          const py = mapY(val)
          const valText = dinhDangGiaTri(val, '0.0')
          phanTu.push({
            loai: 'quy_tac',
            ma: `qt-${lopIdx}-${rIdx}`,
            huong: 'ngang',
            x1: trai,
            y1: py,
            x2: phai,
            y2: py,
            giaTri: val,
            giaTriChu: valText,
            nhan,
            moTa: `${nhan ?? 'Ngưỡng'}: ${valText}`,
            nguon: dacTa.nguon,
          })
        }
      })
      return
    }

    if (lop.dau === 'duong' || lop.dau === 'vung') {
      const kenhNhom = lop.ma_hoa.nhom ?? lop.ma_hoa.mau
      const nhomMap = new Map<string, { x: number; y: number; rawX: GiaTriO; rawY: number }[]>()
      for (const row of rows) {
        const nhom = kenhNhom ? String(row[kenhNhom.cot] ?? 'Chuỗi') : 'Chuỗi'
        const xVal = docKenhViTri(lop.ma_hoa.x, row, dacTa, boDuLieu, trangThai)
        const yVal = docKenhViTri(lop.ma_hoa.y, row, dacTa, boDuLieu, trangThai)
        const px = mapX(xVal)
        if (px === null || typeof yVal !== 'number') continue
        const py = mapY(yVal)
        const list = nhomMap.get(nhom) ?? []
        list.push({ x: px, y: py, rawX: xVal, rawY: yVal })
        nhomMap.set(nhom, list)
      }
      for (const [nhom, pts] of nhomMap.entries()) {
        if (pts.length === 0) continue
        pts.sort((a, b) => a.x - b.x)
        const style = layPhongCachNhom(danhSachNhom, nhom)
        const linePath = pts.map((p) => `${p.x},${p.y}`).join(' ')
        if (lop.dau === 'duong') {
          phanTu.push({
            loai: 'duong',
            ma: `duong-${lopIdx}-${nhom}`,
            nhom,
            diemPath: linePath,
            mau: style.mau,
            netDut: style.netDut,
            doDay: 2,
            moTa: `${nhom} (${pts.length} điểm)`,
            nguon: dacTa.nguon,
          })
        } else {
          const baseY = mapY(Math.max(yMin, 0))
          const dParts = [
            `M ${pts[0].x} ${baseY}`,
            ...pts.map((p) => `L ${p.x} ${p.y}`),
            `L ${pts[pts.length - 1].x} ${baseY}`,
            'Z',
          ]
          phanTu.push({
            loai: 'vung',
            ma: `vung-${lopIdx}-${nhom}`,
            nhom,
            path: dParts.join(' '),
            mau: style.mau,
            moTa: `${nhom}`,
            nguon: dacTa.nguon,
          })
        }
        if (!nhomDaChuGiai.has(nhom)) {
          nhomDaChuGiai.add(nhom)
          chuGiai.push({
            nhan: nhom,
            mau: style.mau,
            netDut: style.netDut,
            hinhDang: style.hinhDang,
          })
        }
      }
      return
    }

    if (lop.dau === 'cot') {
      const soCot = Math.max(1, xCats.length)
      const bandW = plotW / soCot
      const barW = Math.max(18, Math.min(64, bandW * 0.56))
      const baseY = mapY(0)

      rows.forEach((row, rIdx) => {
        const xVal = docKenhViTri(lop.ma_hoa.x, row, dacTa, boDuLieu, trangThai)
        const yVal = docKenhViTri(lop.ma_hoa.y, row, dacTa, boDuLieu, trangThai)
        const cx = mapX(xVal)
        if (cx === null || typeof yVal !== 'number') return
        const py = mapY(yVal)
        const top = Math.min(py, baseY)
        const height = Math.max(2, Math.abs(baseY - py))
        const nhom = lop.ma_hoa.mau ? String(row[lop.ma_hoa.mau.cot] ?? '') : String(xVal ?? '')
        const style = layPhongCachNhom(danhSachNhom.length > 0 ? danhSachNhom : xCats, nhom)
        const valChu = dinhDangGiaTri(yVal)

        phanTu.push({
          loai: 'cot',
          ma: `cot-${lopIdx}-${rIdx}`,
          x: Number((cx - barW / 2).toFixed(2)),
          y: Number(top.toFixed(2)),
          rong: Number(barW.toFixed(2)),
          cao: Number(height.toFixed(2)),
          giaTri: yVal,
          giaTriChu: valChu,
          nhanX: String(xVal ?? ''),
          nhom,
          mau: style.mau,
          mauNen: style.mauNen,
          hoaTiet: style.hoaTiet,
          moTa: `${String(xVal ?? '')}: ${valChu}`,
          nguon: dacTa.nguon,
        })
      })
      return
    }

    if (lop.dau === 'diem') {
      const kenhNhom = lop.ma_hoa.nhom ?? lop.ma_hoa.mau
      rows.forEach((row, rIdx) => {
        const xVal = docKenhViTri(lop.ma_hoa.x, row, dacTa, boDuLieu, trangThai)
        const yVal = coTrucY ? docKenhViTri(lop.ma_hoa.y, row, dacTa, boDuLieu, trangThai) : null
        const cx = mapX(xVal)
        if (cx === null) return
        const cy = coTrucY
          ? mapY(yVal)
          : coDai
            ? Number((tren + Math.min(38, daiCao * 0.4)).toFixed(2))
            : Number(((tren + duoi) / 2).toFixed(2))
        const nhom = kenhNhom ? String(row[kenhNhom.cot] ?? 'Điểm') : 'Điểm'
        const style =
          danhSachNhom.length > 0
            ? layPhongCachNhom(danhSachNhom, nhom)
            : BANG_CHUOI[0]

        const laLopGiaDinh =
          lop.ma_hoa.nhan !== undefined &&
          'chu' in lop.ma_hoa.nhan &&
          lop.ma_hoa.nhan.chu.toLowerCase().includes('giả định')
        const diemLaGiaDinh = laLopGiaDinh && laGiaDinh

        let nhan: string | null = null
        if (lop.ma_hoa.nhan) {
          if ('chu' in lop.ma_hoa.nhan) {
            nhan = laLopGiaDinh ? (diemLaGiaDinh ? lop.ma_hoa.nhan.chu : null) : lop.ma_hoa.nhan.chu
          } else {
            const raw = row[lop.ma_hoa.nhan.cot]
            nhan = raw !== null && raw !== undefined ? String(raw) : null
          }
        }

        const primaryVal = coTrucY ? yVal : xVal
        const giaTriChu =
          typeof primaryVal === 'number'
            ? dinhDangGiaTri(primaryVal, coTrucY ? undefined : '0.0')
            : dinhDangGiaTri(primaryVal)

        const xChu =
          kieuX === 'thoi_gian' && typeof xVal === 'string'
            ? dinhDangNgayNgan(xVal)
            : dinhDangGiaTri(xVal, typeof xVal === 'number' && !Number.isInteger(xVal) ? '0.0' : undefined)

        const moTa = coTrucY
          ? `${nhom} · ${xChu}: ${giaTriChu}`
          : `${diemLaGiaDinh ? 'Giả định · ' : ''}CrCl ${giaTriChu}`

        phanTu.push({
          loai: 'diem',
          ma: `diem-${lopIdx}-${rIdx}`,
          cx,
          cy,
          r: coTrucY ? 3.5 : 7,
          giaTriX: xVal,
          giaTriY: yVal,
          giaTriChu,
          nhom,
          hinhDang: diemLaGiaDinh ? 'thoi' : style.hinhDang,
          mau: diemLaGiaDinh ? 'var(--color-offlabel-solid)' : style.mau,
          laGiaDinh: diemLaGiaDinh,
          nhan,
          moTa,
          nguon: dacTa.nguon,
        })
      })
      return
    }

    if (lop.dau === 'chu') {
      rows.forEach((row, rIdx) => {
        const xVal = docKenhViTri(lop.ma_hoa.x, row, dacTa, boDuLieu, trangThai)
        const yVal = coTrucY ? docKenhViTri(lop.ma_hoa.y, row, dacTa, boDuLieu, trangThai) : null
        const px = mapX(xVal)
        if (px === null) return
        const py = coTrucY ? mapY(yVal) : Number((tren + 14).toFixed(2))
        const noiDung =
          lop.ma_hoa.nhan && 'chu' in lop.ma_hoa.nhan
            ? lop.ma_hoa.nhan.chu
            : lop.ma_hoa.nhan && 'cot' in lop.ma_hoa.nhan
              ? String(row[lop.ma_hoa.nhan.cot] ?? '')
              : ''
        if (!noiDung) return
        phanTu.push({
          loai: 'chu',
          ma: `chu-${lopIdx}-${rIdx}`,
          x: px,
          y: py,
          noiDung,
          mau: 'var(--color-fg)',
          moTa: noiDung,
          nguon: dacTa.nguon,
        })
      })
    }
  })

  // Dựng vạch chia trục X
  let vachX: VachTruc[] = []
  if (kieuX === 'dinh_luong') {
    const soVach = rong < 420 ? 4 : 6
    vachX = taoVachSo(xMin, xMax, soVach)
      .map((val) => ({
        toaDo: mapX(val) ?? trai,
        nhan: dinhDangGiaTri(val),
      }))
      .filter((t) => t.toaDo >= trai - 1 && t.toaDo <= phai + 1)
  } else if (kieuX === 'thoi_gian' && xTimes.length > 0) {
    const uniqueSorted = [...new Set(xTimes)].sort((a, b) => a - b)
    const maxTicks = rong < 440 ? 4 : 6
    const step = Math.max(1, Math.ceil((uniqueSorted.length - 1) / Math.max(1, maxTicks - 1)))
    const chosen: number[] = []
    for (let i = 0; i < uniqueSorted.length; i += step) {
      chosen.push(uniqueSorted[i])
    }
    const last = uniqueSorted[uniqueSorted.length - 1]
    if (chosen[chosen.length - 1] !== last) {
      chosen.push(last)
    }
    vachX = chosen.map((ms) => {
      const iso = new Date(ms).toISOString().slice(0, 10)
      return {
        toaDo: mapX(iso) ?? trai,
        nhan: dinhDangNgayNgan(iso),
      }
    })
  } else {
    vachX = xCats.map((cat) => ({
      toaDo: mapX(cat) ?? trai,
      nhan: cat,
    }))
  }

  // Dựng vạch chia trục Y
  let trucY: MoHinhTruc | null = null
  if (coTrucY) {
    const vachY: VachTruc[] =
      kieuY === 'dinh_luong'
        ? taoVachSo(yMin, yMax, 5).map((val) => ({
            toaDo: mapY(val),
            nhan: dinhDangGiaTri(val),
          }))
        : yCats.map((cat) => ({
            toaDo: mapY(cat),
            nhan: cat,
          }))
    trucY = {
      tieuDe: dacTa.truc?.y?.tieu_de ?? '',
      kieu: kieuY,
      vach: vachY,
    }
  }

  return {
    rong,
    cao,
    vungVe: { trai, phai, tren, duoi },
    tieuDe: dacTa.tieu_de,
    phuDe,
    laGiaDinh,
    nguon: dacTa.nguon,
    soHien,
    trucX: dacTa.truc?.x === null ? null : { tieuDe: dacTa.truc?.x?.tieu_de ?? '', kieu: kieuX, vach: vachX },
    trucY,
    phanTu,
    chuGiai,
  }
}
