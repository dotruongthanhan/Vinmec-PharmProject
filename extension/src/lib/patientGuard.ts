/**
 * Bộ bảo vệ chống trộn lẫn hồ sơ giữa nhiều tab đang chọn.
 * So sánh theo từng chiều định danh chung (mã hồ sơ/ca, họ tên, mã y tế, BHYT, ngày sinh, URL ca)
 * bằng băm SHA-256 cục bộ rồi huỷ ngay giá trị gốc — tránh báo nhầm khi 2 tab hiện khác nhau về tập trường.
 */

import { foldVietnamese } from './schemaCache'
import type { PatientGuardResult, RawTabExtraction } from './types'

type IdentityDimension = 'case_id' | 'medical_id' | 'full_name' | 'bhyt' | 'dob' | 'url_case'

const DIMENSION_LABELS: Record<Exclude<IdentityDimension, 'url_case'>, readonly string[]> = {
  case_id: ['ma ho so', 'ma ca'],
  medical_id: ['ma y te', 'ma yt', 'ma benh nhan', 'ma bn', 'pid', 'hn', 'mrn', 'so luu tru'],
  full_name: ['ho va ten', 'ho ten'],
  bhyt: ['bhyt', 'so the', 'so the bhyt'],
  dob: ['ngay sinh'],
}

const CASE_URL_RE = /\/y-lenh\/([A-Za-z0-9_-]+)/i
const BHYT_CODE_RE = /[a-z]{2}\d{13}/i

async function sha256Hex(value: string): Promise<string> {
  const bytes = new TextEncoder().encode(value)
  if (typeof globalThis.crypto?.subtle !== 'undefined') {
    const digest = await globalThis.crypto.subtle.digest('SHA-256', bytes)
    return Array.from(new Uint8Array(digest))
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('')
  }
  let h = 2166136261
  for (const b of bytes) {
    h ^= b
    h = Math.imul(h, 16777619)
  }
  return (h >>> 0).toString(16).padStart(8, '0')
}

function normalizeDimensionValue(dim: IdentityDimension, raw: string): string {
  const folded = foldVietnamese(raw)
  if (dim === 'bhyt') {
    const m = BHYT_CODE_RE.exec(folded.replace(/\s+/g, ''))
    return m ? m[0].toLowerCase() : folded
  }
  return folded
}

async function extractHashedDimensions(
  tab: RawTabExtraction,
): Promise<Partial<Record<IdentityDimension, string>>> {
  const rawMap: Partial<Record<IdentityDimension, string>> = {}

  for (const [dim, keys] of Object.entries(DIMENSION_LABELS) as Array<
    [Exclude<IdentityDimension, 'url_case'>, readonly string[]]
  >) {
    for (const pair of tab.fieldPairs) {
      const label = foldVietnamese(pair.label)
      if (!keys.includes(label)) continue
      const normVal = normalizeDimensionValue(dim, pair.value)
      if (normVal) {
        rawMap[dim] = normVal
        break
      }
    }
  }

  if (tab.url) {
    const match = CASE_URL_RE.exec(tab.url)
    if (match) {
      rawMap.url_case = match[1].toLowerCase()
    }
  }

  const hashed: Partial<Record<IdentityDimension, string>> = {}
  for (const [dim, val] of Object.entries(rawMap) as Array<[IdentityDimension, string]>) {
    hashed[dim] = await sha256Hex(`${dim}=${val}`)
  }
  return hashed
}

const ALL_DIMENSIONS: readonly IdentityDimension[] = [
  'case_id',
  'medical_id',
  'full_name',
  'bhyt',
  'dob',
  'url_case',
]

export async function verifySamePatientAcrossTabs(
  tabs: RawTabExtraction[],
): Promise<PatientGuardResult> {
  if (tabs.length <= 1) {
    return {
      status: 'SINGLE_OR_UNKNOWN',
      message: 'Đang đọc 1 tab EMR duy nhất.',
      fingerprints: [],
    }
  }

  const perTab = await Promise.all(
    tabs.map(async (tab) => ({
      tab,
      dims: await extractHashedDimensions(tab),
    })),
  )

  const fingerprints = perTab.map(({ tab, dims }) => {
    const primaryHash =
      dims.case_id ??
      dims.medical_id ??
      dims.full_name ??
      dims.bhyt ??
      dims.url_case ??
      dims.dob ??
      'unknown'
    return {
      tabId: tab.tabId,
      tabTitle: tab.tabTitle,
      hashPrefix: primaryHash.slice(0, 8),
    }
  })

  let sharedMatchPairs = 0
  const totalPairs = (perTab.length * (perTab.length - 1)) / 2

  for (let i = 0; i < perTab.length; i += 1) {
    for (let j = i + 1; j < perTab.length; j += 1) {
      let pairShared = false
      for (const dim of ALL_DIMENSIONS) {
        const a = perTab[i].dims[dim]
        const b = perTab[j].dims[dim]
        if (!a || !b) continue
        pairShared = true
        if (a !== b) {
          return {
            status: 'MISMATCH_BLOCKED',
            message:
              'Cảnh báo: Các tab đã chọn thuộc ít nhất 2 người bệnh khác nhau. Vui lòng bỏ chọn tab không cùng bệnh nhân trước khi thẩm định.',
            fingerprints,
          }
        }
      }
      if (pairShared) {
        sharedMatchPairs += 1
      }
    }
  }

  if (sharedMatchPairs > 0 && sharedMatchPairs === totalPairs) {
    return {
      status: 'MATCH',
      message: `Đã xác nhận ${tabs.length} tab thuộc cùng một người bệnh.`,
      fingerprints,
    }
  }

  return {
    status: 'SINGLE_OR_UNKNOWN',
    message:
      'Không tìm thấy đủ mã định danh chung trên nhiều tab — hãy kiểm tra bằng mắt các tab đã chọn.',
    fingerprints,
  }
}
