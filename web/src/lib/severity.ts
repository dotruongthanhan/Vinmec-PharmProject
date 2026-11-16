import {
  CircleCheck,
  CircleHelp,
  FileQuestion,
  Info,
  OctagonAlert,
  Scale,
  ShieldAlert,
  ShieldCheck,
  ShieldQuestion,
  Sparkles,
  TriangleAlert,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { DiUngMa, KetLuanMa, MucDoMa, NguonGocMa } from '../api/types.ts'

export type SemanticTone =
  | 'danger'
  | 'warning'
  | 'missing'
  | 'offlabel'
  | 'success'
  | 'ai'
  | 'neutral'

export interface FindingToneInput {
  ket_luan_ma: KetLuanMa | string | null | undefined
  muc_do_ma?: MucDoMa | string | null | undefined
}

/** Ánh xạ mã kết luận và mức độ nhận định sang tông màu nghĩa. */
export function toneOfFinding({ ket_luan_ma, muc_do_ma }: FindingToneInput): SemanticTone {
  switch (ket_luan_ma) {
    case 'can_xem':
      return muc_do_ma === 'nghiem_trong' ? 'danger' : 'warning'
    case 'khong_du_du_lieu':
      return 'missing'
    case 'ngoai_hdsd':
      return 'offlabel'
    case 'dat':
      return 'success'
    default:
      return 'neutral'
  }
}

/** Ánh xạ mã nguồn gốc nhận định (luật hay AI) sang tông màu nghĩa. */
export function toneOfOrigin(nguon_goc_ma: NguonGocMa | string | null | undefined): SemanticTone {
  switch (nguon_goc_ma) {
    case 'luat':
      return 'neutral'
    case 'ai_da_kiem_chung':
    case 'ai_chua_kiem_chung':
      return 'ai'
    default:
      return 'neutral'
  }
}

/** Ánh xạ mã trạng thái dị ứng sang tông màu nghĩa. */
export function toneOfAllergy(di_ung_ma: DiUngMa | string | null | undefined): SemanticTone {
  switch (di_ung_ma) {
    case 'co_di_ung':
      return 'danger'
    case 'khong_di_ung_da_hoi':
      return 'neutral'
    case 'chua_co_thong_tin':
      return 'missing'
    default:
      return 'neutral'
  }
}

/** Bảng ánh xạ tông màu nghĩa sang biểu tượng lucide mặc định. */
export const ICON_OF_TONE: Record<SemanticTone, LucideIcon> = {
  danger: OctagonAlert,
  warning: TriangleAlert,
  missing: CircleHelp,
  offlabel: FileQuestion,
  success: CircleCheck,
  ai: Sparkles,
  neutral: Info,
}

/** Chọn biểu tượng lucide cho nguồn gốc nhận định. */
export function iconOfOrigin(nguon_goc_ma: NguonGocMa | string | null | undefined): LucideIcon {
  switch (nguon_goc_ma) {
    case 'luat':
      return Scale
    case 'ai_da_kiem_chung':
    case 'ai_chua_kiem_chung':
      return Sparkles
    default:
      return Info
  }
}

/** Chọn biểu tượng lucide cho ba trạng thái dị ứng. */
export function iconOfAllergy(di_ung_ma: DiUngMa | string | null | undefined): LucideIcon {
  switch (di_ung_ma) {
    case 'co_di_ung':
      return ShieldAlert
    case 'khong_di_ung_da_hoi':
      return ShieldCheck
    case 'chua_co_thong_tin':
      return ShieldQuestion
    default:
      return ShieldQuestion
  }
}
