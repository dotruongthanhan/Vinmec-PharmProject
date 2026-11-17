import type { ChiSo } from '../api/types.ts'

export type DetailTabId =
  | 'ho_so_benh_an'
  | 'y_lenh'
  | 'phieu_dieu_tri'
  | 'xet_nghiem'
  | 'vi_sinh'
  | 'dien_bien'
  | 'tham_dinh'

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
