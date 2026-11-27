import type { ChiTietCa, NhanDinh } from '../api/types.ts'
import { drugKey, parseInfoPairs, parseSchedule } from './detailTables.ts'
import {
  administrativeDate,
  formatClinicalText,
  formatIsoTimestamp,
  parseVietnamDate,
} from './displayFormat.ts'
import { medicalOrders } from './medicalRecord.ts'

export type UnifiedLineStatusCode =
  | 'cho_duyet'
  | 'dang_dung'
  | 'dang_cho'
  | 'dung_xong'
  | 'da_huy'

export type UnifiedLineSeverity =
  | 'nghiem_trong'
  | 'can_luu_y'
  | 'thieu_du_lieu'
  | 'none'

export interface UnifiedOrderLine {
  key: string
  chiTietYLenhId: string | null
  yLenhId: string
  laTrongTam: boolean
  tenThuoc: string
  lieu: string
  tanSuat: string
  duongDung: string
  ngayKe: string
  ngayKeIso: string | null
  trangThaiCode: UnifiedLineStatusCode
  trangThaiLabel: 'Chờ duyệt' | 'Đang dùng' | 'Đang chờ' | 'Dùng xong' | 'Đã hủy'
  batDauText: string | null
  ketThucText: string | null
  lichDungRaw: string
  khoaKe: string
  luongDuyet: string | null
  loaiYLenh: string | null
  nguoiKe: string | null
  lyDoNgung: string | null
  thoiDiemNgung: string | null
  thayTheYLenhId: string | null
  cachDung: string | null
}

export interface LineFindingBucket {
  attention: NhanDinh[]
  passed: NhanDinh[]
}

export interface PartitionedFindings {
  byLineKey: Record<string, LineFindingBucket>
  caseWideAttention: NhanDinh[]
  caseWidePassed: NhanDinh[]
}

const MISSING = 'Chưa ghi nhận'

const STATUS_LABELS: Record<UnifiedLineStatusCode, UnifiedOrderLine['trangThaiLabel']> = {
  cho_duyet: 'Chờ duyệt',
  dang_dung: 'Đang dùng',
  dang_cho: 'Đang chờ',
  dung_xong: 'Dùng xong',
  da_huy: 'Đã hủy',
}

const STATUS_SORT_RANK: Record<UnifiedLineStatusCode, number> = {
  cho_duyet: 0,
  dang_dung: 1,
  dang_cho: 2,
  dung_xong: 3,
  da_huy: 4,
}

const ORDER_FLOW_LABELS: Record<string, string> = {
  truc_tiep: 'Trực tiếp',
  hau_kiem: 'Hậu kiểm',
}

const ORDER_TYPE_LABELS: Record<string, string> = {
  thuong_quy: 'Thường quy',
  cap_cuu: 'Cấp cứu',
  khi_can: 'Khi cần',
  hoi_chan: 'Hội chẩn',
}

const PRESCRIBER_ROLE_LABELS: Record<string, string> = {
  bac_si_dieu_tri: 'Bác sĩ điều trị',
  bac_si_truc: 'Bác sĩ trực',
  hoi_chan: 'Hội chẩn',
}

function foldVi(raw: string): string {
  return raw
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/gi, 'd')
    .trim()
    .toLowerCase()
}

/** Chuẩn hoá trạng thái từng dòng thuốc về đúng 5 nhãn quy ước mới. */
export function normalizeLineStatus(
  lineStatusRaw: string | null | undefined,
  orderStatusRaw: string | null | undefined,
  batDauIso?: string | null,
  nowMs: number = Date.now(),
): { code: UnifiedLineStatusCode; label: UnifiedOrderLine['trangThaiLabel'] } {
  const lineNorm = foldVi(lineStatusRaw ?? '')
  const orderNorm = foldVi(orderStatusRaw ?? '')

  const finish = (code: UnifiedLineStatusCode) => ({ code, label: STATUS_LABELS[code] })

  if (lineNorm === 'pending' || lineNorm === 'cho duyet') {
    return finish('cho_duyet')
  }
  if (lineNorm === 'discontinued' || lineNorm === 'ngung' || lineNorm === 'da ngung' || lineNorm === 'da huy') {
    return finish('da_huy')
  }
  if (
    lineNorm === 'completed' ||
    lineNorm === 'hoan tat' ||
    lineNorm === 'da hoan thanh' ||
    lineNorm === 'dung xong'
  ) {
    return finish('dung_xong')
  }
  if (lineNorm === 'waiting' || lineNorm === 'dang cho') {
    return finish('dang_cho')
  }
  if (lineNorm === 'active' || lineNorm === 'dang dung') {
    if (orderNorm === 'da_duyet' && batDauIso) {
      const start = parseVietnamDate(batDauIso)
      if (start && start.getTime() > nowMs) {
        return finish('dang_cho')
      }
    }
    return finish('dang_dung')
  }

  if (orderNorm === 'cho_duyet' || orderNorm === 'cho duyet') return finish('cho_duyet')
  if (orderNorm === 'da_duyet' || orderNorm === 'da duyet') return finish('dang_cho')
  if (orderNorm === 'dang_thuc_hien' || orderNorm === 'dang thuc hien') return finish('dang_dung')
  if (orderNorm === 'hoan_tat' || orderNorm === 'hoan tat') return finish('dung_xong')
  if (orderNorm === 'ngung' || orderNorm === 'da_huy') return finish('da_huy')

  return finish('cho_duyet')
}

function formatDateTimeValue(raw: string | null | undefined): string | null {
  const trimmed = raw?.trim()
  if (!trimmed) return null
  if (trimmed.includes('T')) {
    return formatIsoTimestamp(trimmed)
  }
  return administrativeDate(trimmed)
}

/** Chuyển toàn bộ y lệnh (chờ duyệt, đang dùng, lịch sử) thành một danh sách dòng thuốc phẳng. */
export function flattenOrderLines(detail: ChiTietCa, nowMs?: number): UnifiedOrderLine[] {
  const orders = medicalOrders(detail)
  const infoPairs = parseInfoPairs(formatClinicalText(detail.chi_tiet.y_lenh.thong_tin_text))
  const pairValue = (prefix: string): string | null => {
    const found = infoPairs.find((p) => p.label.toLowerCase().startsWith(prefix))
    return found?.value?.trim() || null
  }
  const fallbackFocusKhoa = pairValue('khoa')
  const fallbackFocusLuong = pairValue('luồng')
  const fallbackFocusTime = pairValue('thời điểm')

  const seenLineIds = new Set<string>()
  const lines: UnifiedOrderLine[] = []

  for (const order of orders) {
    const khoaKe =
      order.khoa_ke_don?.trim() ||
      (order.la_trong_tam ? fallbackFocusKhoa : null) ||
      detail.quan_ly_nguoi_benh?.khoa_dieu_tri?.trim() ||
      detail.dinh_danh.khoa_loai.split(',')[0]?.trim() ||
      MISSING

    const ngayKeIso = order.thoi_diem_ke?.trim() || null
    const ngayKe = ngayKeIso
      ? administrativeDate(ngayKeIso)
      : order.la_trong_tam && fallbackFocusTime
        ? fallbackFocusTime
        : MISSING

    const luongDuyet = order.luong_duyet
      ? (ORDER_FLOW_LABELS[order.luong_duyet] ?? order.luong_duyet)
      : order.la_trong_tam
        ? fallbackFocusLuong
        : null

    const loaiYLenh = order.loai ? (ORDER_TYPE_LABELS[order.loai] ?? order.loai) : null
    const nguoiKe = order.vai_tro_nguoi_ke
      ? (PRESCRIBER_ROLE_LABELS[order.vai_tro_nguoi_ke] ?? order.vai_tro_nguoi_ke)
      : null

    for (let idx = 0; idx < order.dong.length; idx += 1) {
      const row = order.dong[idx]
      const meta = order.dong_meta?.[idx]
      const lineId = meta?.chi_tiet_y_lenh_id?.trim() || null

      if (lineId) {
        if (seenLineIds.has(lineId)) {
          continue
        }
        seenLineIds.add(lineId)
      }

      const rawSchedule = row['Lịch dùng'] ?? ''
      const doses = parseSchedule(rawSchedule)
      const firstDose = doses[0]
      const lastDose = doses[doses.length - 1]

      const batDauText =
        formatDateTimeValue(meta?.bat_dau) ??
        (firstDose ? `${firstDose.time} · ${firstDose.date}` : null)
      const ketThucText =
        formatDateTimeValue(meta?.ket_thuc) ??
        (lastDose ? `${lastDose.time} · ${lastDose.date}` : null)

      const { code: trangThaiCode, label: trangThaiLabel } = normalizeLineStatus(
        meta?.trang_thai_dong ?? row['Trạng thái'],
        order.trang_thai,
        meta?.bat_dau,
        nowMs,
      )

      const tenThuoc = (row['Thuốc'] ?? '').trim() || lineId || '—'

      lines.push({
        key: `${order.y_lenh_id}::${lineId ?? idx}`,
        chiTietYLenhId: lineId,
        yLenhId: order.y_lenh_id,
        laTrongTam: order.la_trong_tam,
        tenThuoc,
        lieu: formatClinicalText((row['Liều'] ?? '').trim() || '—'),
        tanSuat: (row['Tần suất'] ?? '').trim() || '—',
        duongDung: (row['Đường dùng'] ?? '').trim() || '—',
        ngayKe,
        ngayKeIso,
        trangThaiCode,
        trangThaiLabel,
        batDauText,
        ketThucText,
        lichDungRaw: rawSchedule,
        khoaKe,
        luongDuyet,
        loaiYLenh,
        nguoiKe,
        lyDoNgung: order.ly_do_ngung?.trim() || null,
        thoiDiemNgung: order.thoi_diem_ngung ? administrativeDate(order.thoi_diem_ngung) : null,
        thayTheYLenhId: order.thay_the_y_lenh_id?.trim() || null,
        cachDung: meta?.cach_dung?.trim() || null,
      })
    }
  }

  return lines.sort((a, b) => {
    const rankDiff = STATUS_SORT_RANK[a.trangThaiCode] - STATUS_SORT_RANK[b.trangThaiCode]
    if (rankDiff !== 0) return rankDiff
    if (a.laTrongTam !== b.laTrongTam) return a.laTrongTam ? -1 : 1
    const aMs = a.ngayKeIso ? (parseVietnamDate(a.ngayKeIso)?.getTime() ?? 0) : 0
    const bMs = b.ngayKeIso ? (parseVietnamDate(b.ngayKeIso)?.getTime() ?? 0) : 0
    return bMs - aMs
  })
}

function lineMatchesByDrugName(line: UnifiedOrderLine, finding: NhanDinh): boolean {
  const hay = finding.thuoc.trim().toLowerCase()
  if (!hay) return false
  const full = line.tenThuoc.trim().toLowerCase()
  const baseKey = drugKey(line.tenThuoc)
  return Boolean((full && hay.includes(full)) || (baseKey.length >= 3 && hay.includes(baseKey)))
}

/** Chia toàn bộ nhận định (cần chú ý + đạt) về đúng từng dòng thuốc; phần không gắn dòng thuốc đưa vào cấp hồ sơ. */
export function partitionFindingsByLine(
  lines: readonly UnifiedOrderLine[],
  allAttention: readonly NhanDinh[],
  allPassed: readonly NhanDinh[],
): PartitionedFindings {
  const byLineKey: Record<string, LineFindingBucket> = {}
  for (const line of lines) {
    byLineKey[line.key] = { attention: [], passed: [] }
  }

  const linesById = new Map<string, UnifiedOrderLine>()
  for (const line of lines) {
    if (line.chiTietYLenhId) {
      linesById.set(line.chiTietYLenhId, line)
    }
  }

  const eligibleForNameFallback = lines.filter(
    (line) =>
      line.laTrongTam ||
      line.trangThaiCode === 'cho_duyet' ||
      line.trangThaiCode === 'dang_dung' ||
      line.trangThaiCode === 'dang_cho',
  )

  const assignList = (
    items: readonly NhanDinh[],
    targetField: 'attention' | 'passed',
    caseWideOut: NhanDinh[],
  ) => {
    for (const finding of items) {
      const matched: UnifiedOrderLine[] = []
      if (finding.chi_tiet_y_lenh_id.length > 0) {
        for (const id of finding.chi_tiet_y_lenh_id) {
          const hit = linesById.get(id)
          if (hit && !matched.some((item) => item.key === hit.key)) {
            matched.push(hit)
          }
        }
      }

      if (matched.length === 0 && finding.thuoc.trim()) {
        for (const line of eligibleForNameFallback) {
          if (lineMatchesByDrugName(line, finding) && !matched.some((item) => item.key === line.key)) {
            matched.push(line)
          }
        }
      }

      if (matched.length === 0) {
        caseWideOut.push(finding)
        continue
      }

      for (const line of matched) {
        const bucket = byLineKey[line.key][targetField]
        if (!bucket.some((existing) => existing.nhan_dinh_id === finding.nhan_dinh_id)) {
          bucket.push(finding)
        }
      }
    }
  }

  const caseWideAttention: NhanDinh[] = []
  const caseWidePassed: NhanDinh[] = []
  assignList(allAttention, 'attention', caseWideAttention)
  assignList(allPassed, 'passed', caseWidePassed)

  return { byLineKey, caseWideAttention, caseWidePassed }
}

/** Xác định mức cảnh báo cao nhất của một dòng thuốc để tô nền màu sáng dễ đọc. */
export function lineHighlightSeverity(attention: readonly NhanDinh[]): UnifiedLineSeverity {
  if (attention.some((f) => f.ket_luan_ma === 'can_xem' && f.muc_do_ma === 'nghiem_trong')) {
    return 'nghiem_trong'
  }
  if (attention.some((f) => f.ket_luan_ma === 'can_xem' || f.ket_luan_ma === 'ngoai_hdsd')) {
    return 'can_luu_y'
  }
  if (attention.some((f) => f.ket_luan_ma === 'khong_du_du_lieu')) {
    return 'thieu_du_lieu'
  }
  return 'none'
}

/** Nhận diện hồ sơ ngoại trú từ chuỗi khoa, loại hồ sơ. */
export function isOutpatientCase(detail: Pick<ChiTietCa, 'dinh_danh'>): boolean {
  return foldVi(detail.dinh_danh.khoa_loai ?? '').includes('ngoai tru')
}
