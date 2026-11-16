import type { ChiSo } from '../api/types.ts'

export type DetailTabId = 'y_lenh' | 'xet_nghiem' | 'vi_sinh' | 'dien_bien'

export type EvidenceTarget =
  | {
      kind: 'record'
      caId: string
      banGhiId: string
      titleHint: string
    }
  | {
      kind: 'metric'
      metric: ChiSo
      titleHint?: string
    }
  | {
      kind: 'document'
      moTa: string
      ghiChu: string | null
    }
  | {
      kind: 'source'
      caId: string
      doanTrichId: string
      nhan: string
      trichNguyenVan: string
    }
