import type { CongThucMuc, DauVaoCongThuc, NhomNhanFda } from '@/api/types'

/** Nhãn tiếng Việt cho 13 mục của nhãn FDA (khoá theo hợp đồng v1.8, đúng thứ tự). */
export const FDA_SECTION_LABELS: Record<string, string> = {
  chi_dinh: 'Chỉ định',
  chong_chi_dinh: 'Chống chỉ định',
  lieu: 'Liều',
  lieu_than: 'Liều khi suy thận',
  lieu_gan: 'Liều khi suy gan',
  canh_bao: 'Cảnh báo',
  tuong_tac: 'Tương tác',
  thai_ky_cho_bu: 'Thai kỳ – cho con bú',
  nhi_cao_tuoi: 'Nhi – cao tuổi',
  tac_dung_phu: 'Tác dụng phụ',
  qua_lieu: 'Quá liều',
  duoc_ly: 'Dược lý',
  khac: 'Khác',
}

/** Nhãn nhóm quy tắc thẩm định (D1–D7) trong chi tiết thuốc. */
export const RULE_GROUP_LABELS: Record<string, string> = {
  lieu_than: 'Liều theo chức năng thận',
  lieu_gan: 'Liều theo chức năng gan',
  nguong_xet_nghiem: 'Ngưỡng xét nghiệm',
  thuoc_benh: 'Thuốc – bệnh',
  duong_dung: 'Đường dùng',
  lieu_toi_da: 'Liều tối đa',
  doc_tinh: 'Độc tính',
  khang_sinh_quan_ly: 'Kháng sinh quản lý',
  di_ung_cheo: 'Dị ứng chéo',
  nhom_trung_dieu_tri: 'Nhóm trùng điều trị',
}

export function fdaSectionLabel(muc: string): string {
  return FDA_SECTION_LABELS[muc] ?? muc
}

export function ruleGroupLabel(nhom: string): string {
  return RULE_GROUP_LABELS[nhom] ?? nhom
}

/** Chỉ các nhóm FDA có đoạn văn mới cần mở rộng; giữ thứ tự hợp đồng. */
export function nonEmptyFdaGroups(nhom: readonly NhomNhanFda[]): NhomNhanFda[] {
  return nhom.filter((item) => item.doan.length > 0)
}

export interface ApprovalLabel {
  text: string
  tone: 'warning' | 'success' | 'neutral'
}

/**
 * Nhãn trạng thái duyệt lấy nguyên từ dữ liệu. `null` nghĩa là nguồn không có trường trạng thái:
 * không suy diễn là đã duyệt, chỉ trả null để giao diện không vẽ nhãn.
 */
export function approvalLabel(trangThai: string | null | undefined): ApprovalLabel | null {
  if (trangThai === null || trangThai === undefined || trangThai === '') return null
  const key = trangThai.toLowerCase()
  if (key.includes('chua_duoc_si_duyet') || key.includes('cho_duoc_si_duyet') || key.includes('cho_duyet')) {
    return { text: 'Chờ dược sĩ duyệt', tone: 'warning' }
  }
  if (key === 'da_duyet' || key === 'duoc_si_da_duyet') {
    return { text: 'Dược sĩ đã duyệt', tone: 'success' }
  }
  return { text: trangThai.replaceAll('_', ' '), tone: 'neutral' }
}

/** Bỏ dấu tiếng Việt và chuẩn hoá để so trùng tên thuốc (phản chiếu quy tắc backend). */
export function foldName(value: string): string {
  return value
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .replaceAll('đ', 'd')
    .replaceAll('Đ', 'D')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim()
}

export const MIN_INTERACTION_DRUGS = 2
export const MAX_INTERACTION_DRUGS = 12
export const MAX_DRUG_NAME_LENGTH = 200

export interface AddDrugResult {
  list: string[]
  error: string | null
}

/** Thêm một tên thuốc vào danh sách thẻ; trả lỗi tiếng Việt thay vì ném. */
export function addDrugName(list: readonly string[], raw: string): AddDrugResult {
  const name = raw.trim().replace(/\s+/g, ' ')
  if (name === '') return { list: [...list], error: null }
  if (name.length > MAX_DRUG_NAME_LENGTH) {
    return { list: [...list], error: `Tên thuốc quá dài (tối đa ${MAX_DRUG_NAME_LENGTH} ký tự).` }
  }
  if (list.length >= MAX_INTERACTION_DRUGS) {
    return { list: [...list], error: `Tối đa ${MAX_INTERACTION_DRUGS} thuốc mỗi lần kiểm tra.` }
  }
  const folded = foldName(name)
  if (list.some((item) => foldName(item) === folded)) {
    return { list: [...list], error: `“${name}” đã có trong danh sách.` }
  }
  return { list: [...list, name], error: null }
}

/** Gom nhiều tên dán cách nhau bằng dấu phẩy, chấm phẩy hoặc xuống dòng. */
export function splitDrugNames(raw: string): string[] {
  return raw.split(/[,;\n]/).map((item) => item.trim()).filter(Boolean)
}

/** Nhóm hiển thị của công thức, theo mã (danh mục backend không có trường nhóm). */
export const FORMULA_GROUPS: { id: string; label: string; match: (ma: string) => boolean }[] = [
  { id: 'co_the', label: 'Cơ thể', match: (ma) => /^(bmi|bsa_|ibw_|adjusted_body_weight)/.test(ma) },
  { id: 'than', label: 'Thận', match: (ma) => /^(cockcroft_gault|egfr_)/.test(ma) },
  { id: 'gan', label: 'Gan', match: (ma) => ma.startsWith('child_pugh') },
  { id: 'tim_mach', label: 'Tim mạch', match: (ma) => ma.startsWith('qtc_') },
  { id: 'dien_giai', label: 'Điện giải', match: (ma) => ma.startsWith('calcium_') || ma.startsWith('sodium_') },
]

export function groupFormulas(list: readonly CongThucMuc[]): { id: string; label: string; items: CongThucMuc[] }[] {
  const used = new Set<string>()
  const groups = FORMULA_GROUPS.map((group) => {
    const items = list.filter((item) => group.match(item.ma))
    items.forEach((item) => used.add(item.ma))
    return { id: group.id, label: group.label, items }
  }).filter((group) => group.items.length > 0)
  const rest = list.filter((item) => !used.has(item.ma))
  if (rest.length > 0) groups.push({ id: 'khac', label: 'Khác', items: [...rest] })
  return groups
}

const INPUT_LABELS: Record<string, string> = {
  can_nang_kg: 'Cân nặng',
  chieu_cao_cm: 'Chiều cao',
  tuoi: 'Tuổi',
  gioi_tinh: 'Giới tính',
  loai_can_nang: 'Loại cân nặng',
  creatinin: 'Creatinin huyết thanh',
  creatinin_don_vi: 'Đơn vị creatinin',
  bilirubin: 'Bilirubin toàn phần',
  bilirubin_don_vi: 'Đơn vị bilirubin',
  albumin: 'Albumin',
  albumin_don_vi: 'Đơn vị albumin',
  albumin_binh_thuong: 'Albumin bình thường',
  inr: 'INR',
  co_truong: 'Cổ trướng',
  nao_gan: 'Bệnh não gan',
  qt_ms: 'Khoảng QT',
  nhip_tim: 'Nhịp tim',
  canxi: 'Canxi toàn phần',
  canxi_don_vi: 'Đơn vị canxi',
}

const CHOICE_LABELS: Record<string, string> = {
  nam: 'Nam',
  nu: 'Nữ',
  thuc_te: 'Thực tế',
  ly_tuong: 'Lý tưởng',
  hieu_chinh: 'Hiệu chỉnh',
  khong: 'Không',
  nhe: 'Nhẹ',
  vua: 'Vừa',
  do_1_2: 'Độ 1–2',
  do_3_4: 'Độ 3–4',
}

export function formulaInputLabel(ten: string): string {
  return INPUT_LABELS[ten] ?? ten.replaceAll('_', ' ')
}

export function formulaChoiceLabel(value: string): string {
  return CHOICE_LABELS[value] ?? value.replaceAll('_', ' ')
}

/** Giá trị mặc định của ô đơn vị: lựa chọn đầu tiên. */
export function defaultUnit(spec: DauVaoCongThuc): string {
  return spec.don_vi[0] ?? ''
}

/** Đầu vào dùng ô chọn đơn vị (có trường đơn vị đi kèm và nhiều hơn một đơn vị). */
export function hasUnitSelect(spec: DauVaoCongThuc): boolean {
  return spec.kieu === 'so' && spec.truong_don_vi !== null && spec.don_vi.length > 0
}

export type FormulaFormValues = Record<string, string>

/**
 * Dựng `dau_vao` gửi lên: số giữ nguyên chuỗi người nhập (backend nhận dấu phẩy), ô trống bị bỏ
 * để backend trả `thieu_dau_vao`; đơn vị đi kèm gửi ở `<ten>_don_vi` (trường `truong_don_vi`).
 */
export function buildFormulaBody(
  spec: CongThucMuc,
  values: FormulaFormValues,
): Record<string, string | number | null> {
  const body: Record<string, string | number | null> = {}
  for (const input of spec.dau_vao) {
    const raw = (values[input.ten] ?? '').trim()
    if (raw === '') continue
    body[input.ten] = raw
    if (input.truong_don_vi !== null) {
      body[input.truong_don_vi] = values[input.truong_don_vi] || defaultUnit(input)
    }
  }
  return body
}

/** Giá trị khởi tạo của biểu mẫu: mặc định của đặc tả và đơn vị đầu tiên. */
export function initialFormulaValues(spec: CongThucMuc): FormulaFormValues {
  const values: FormulaFormValues = {}
  for (const input of spec.dau_vao) {
    values[input.ten] = input.mac_dinh === null || input.mac_dinh === undefined ? '' : String(input.mac_dinh)
    if (input.truong_don_vi !== null) values[input.truong_don_vi] = defaultUnit(input)
  }
  return values
}

/** Làm tròn chỉ ở lớp hiển thị; `ket_qua` là số thô từ hàm tính. */
export function formatFormulaResult(value: number): string {
  const abs = Math.abs(value)
  const digits = abs >= 100 ? 1 : abs >= 10 ? 2 : 3
  return new Intl.NumberFormat('vi-VN', { maximumFractionDigits: digits }).format(value)
}
