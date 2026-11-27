import type { ChiSo } from '../api/types.ts'

export interface EncounterGroup<T> {
  id: string
  thuTu: number | null
  items: T[]
}

export type DetailTabId =
  | 'ho_so_benh_an'
  | 'y_lenh'
  | 'xet_nghiem'
  | 'vi_sinh'
  | 'dien_bien'
  | 'tham_dinh'

export interface FeedbackDraft {
  isEditing: boolean
  pendingAction: 'bac_bo' | 'can_sua' | null
  reasonGroup: string
  note: string
}

export const EMPTY_FEEDBACK_DRAFT: FeedbackDraft = {
  isEditing: false,
  pendingAction: null,
  reasonGroup: '',
  note: '',
}

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
