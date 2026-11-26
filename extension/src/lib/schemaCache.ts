/** Sàn nhãn PII tiếng Việt tất định + bộ nhớ đệm phân loại theo schemaHash (chỉ lưu tên nhãn). */

import type { ClassifiedField, SchemaFieldDescriptor, SchemaGroup } from './types'

const STORAGE_PREFIX = 'cdss_ext_schema_v1:'

const PII_FLOOR_TERMS = [
  'ho ten',
  'ho va ten',
  'ten benh nhan',
  'ngay sinh',
  'nam sinh',
  'cccd',
  'cmnd',
  'can cuoc',
  'chung minh',
  'bhyt',
  'so the',
  'han bhyt',
  'bao hiem y te',
  'ma benh nhan',
  'ma bn',
  'ma ho so',
  'ma ca',
  'pid',
  'patient id',
  'ma y te',
  'ma yt',
  'so luu tru',
  'so giuong',
  'hn',
  'mrn',
  'dia chi',
  'so nha',
  'thon pho',
  'xa phuong',
  'quan huyen',
  'tinh thanh',
  'dien thoai',
  'sdt',
  'so dien thoai',
  'phone',
  'email',
  'thu dien tu',
  'lien lac khan cap',
  'nguoi bao tin',
  'nguoi nha',
  'bo me',
  'ho ten bo',
  'ho ten me',
  'bac si dieu tri',
  'nguoi ke don',
  'nguoi lap phieu',
  'chu ky',
]

const CLINICAL_KEEP_BASELINE = [
  'tuoi',
  'gioi tinh',
  'can nang',
  'chieu cao',
  'bmi',
  'nhom mau',
  'khoa dieu tri',
  'khoa',
  'vao vien',
  'ngay vao vien',
  'thoi gian nam vien',
  'chan doan',
  'chan doan chinh',
  'chan doan kem',
  'benh chinh',
  'benh kem',
  'ma icd',
  'icd10',
  'di ung',
  'tinh trang di ung',
  'co dia',
  'sinh hieu',
  'xet nghiem',
  'creatinin',
  'egfr',
  'crcl',
  'vi sinh',
  'khang sinh do',
  'dien bien',
  'phieu dieu tri',
  'danh gia',
  'huong xu tri',
  'che do an',
  'theo doi',
  'thuoc',
  'y lenh',
  'lieu',
  'duong dung',
  'tan suat',
]

const QUASI_DOB_TERMS = ['ngay sinh', 'nam sinh', 'dob', 'date of birth']

export function foldVietnamese(input: string): string {
  return input
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[đĐ]/g, 'd')
    .toLowerCase()
    .replace(/[\s_:./-]+/g, ' ')
    .trim()
}

function containsTerm(folded: string, terms: readonly string[]): boolean {
  return terms.some(
    (term) =>
      folded === term ||
      folded.startsWith(`${term} `) ||
      folded.endsWith(` ${term}`) ||
      folded.includes(` ${term} `),
  )
}

export function isQuasiDobLabel(label: string): boolean {
  return containsTerm(foldVietnamese(label), QUASI_DOB_TERMS)
}

export function matchesLocalPiiFloor(label: string, sectionHint?: string | null): boolean {
  const folded = foldVietnamese(label)
  if (!folded) {
    return true
  }
  if (containsTerm(folded, PII_FLOOR_TERMS)) {
    return true
  }
  if (sectionHint && foldVietnamese(sectionHint).includes('hanh chinh')) {
    const allowedInAdmin = ['tuoi', 'gioi tinh', 'can nang', 'chieu cao', 'bmi', 'nhom mau']
    if (!containsTerm(folded, allowedInAdmin)) {
      return true
    }
  }
  return false
}

export function classifyLocalBaseline(fields: SchemaFieldDescriptor[]): ClassifiedField[] {
  return fields.map((field) => {
    const label = field.ten_nhan.trim()
    if (matchesLocalPiiFloor(label, field.ngu_canh_muc)) {
      return {
        ten_nhan: label,
        nhom: 'pii_xoa',
        nguon: 'san_pii',
        ly_do: 'Trùng danh mục nhãn định danh cá nhân',
      }
    }
    if (containsTerm(foldVietnamese(label), CLINICAL_KEEP_BASELINE)) {
      return {
        ten_nhan: label,
        nhom: 'lam_sang_giu',
        nguon: 'san_pii',
        ly_do: 'Nhãn lâm sàng chuẩn đã xác nhận',
      }
    }
    return {
      ten_nhan: label,
      nhom: 'nghi_ngo_pii',
      nguon: 'mac_dinh_an_toan',
      ly_do: 'Nhãn mới chưa phân loại, mặc định loại bỏ cho tới khi xác nhận',
    }
  })
}

export function mergeWithPiiFloor(
  fields: SchemaFieldDescriptor[],
  remote: ClassifiedField[],
): ClassifiedField[] {
  const byLabel = new Map<string, ClassifiedField>()
  for (const item of remote) {
    byLabel.set(item.ten_nhan.trim(), item)
  }
  return fields.map((field) => {
    const label = field.ten_nhan.trim()
    if (matchesLocalPiiFloor(label, field.ngu_canh_muc)) {
      return {
        ten_nhan: label,
        nhom: 'pii_xoa',
        nguon: 'san_pii',
        ly_do: 'Sàn PII tất định ưu tiên cắt bỏ',
      }
    }
    const found = byLabel.get(label)
    if (
      found &&
      (found.nhom === 'pii_xoa' || found.nhom === 'lam_sang_giu' || found.nhom === 'nghi_ngo_pii')
    ) {
      return found
    }
    return {
      ten_nhan: label,
      nhom: 'nghi_ngo_pii',
      nguon: 'mac_dinh_an_toan',
      ly_do: 'Chưa xác định rõ, mặc định cắt bỏ để an toàn PII',
    }
  })
}

export function buildGroupLookup(items: ClassifiedField[]): Map<string, SchemaGroup> {
  const map = new Map<string, SchemaGroup>()
  for (const item of items) {
    map.set(foldVietnamese(item.ten_nhan), item.nhom)
  }
  return map
}

export interface CachedSchemaEntry {
  schemaHash: string
  approvedAt: number
  fields: ClassifiedField[]
}

export async function loadCachedSchema(schemaHash: string): Promise<CachedSchemaEntry | null> {
  if (typeof chrome === 'undefined' || !chrome.storage?.local) {
    return null
  }
  const key = `${STORAGE_PREFIX}${schemaHash}`
  const data = await chrome.storage.local.get(key)
  const entry = data[key] as CachedSchemaEntry | undefined
  if (!entry || entry.schemaHash !== schemaHash || !Array.isArray(entry.fields)) {
    return null
  }
  return entry
}

export async function saveCachedSchema(
  schemaHash: string,
  fields: ClassifiedField[],
): Promise<void> {
  if (typeof chrome === 'undefined' || !chrome.storage?.local) {
    return
  }
  // Tuyệt đối chỉ lưu tên nhãn trường và nhóm phân loại — không bao giờ lưu giá trị bệnh nhân.
  const entry: CachedSchemaEntry = {
    schemaHash,
    approvedAt: Date.now(),
    fields: fields.map((item) => ({
      ten_nhan: item.ten_nhan,
      nhom: item.nhom,
      nguon: item.nguon,
      ly_do: item.ly_do,
    })),
  }
  await chrome.storage.local.set({ [`${STORAGE_PREFIX}${schemaHash}`]: entry })
}
