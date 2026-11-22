import { useMemo } from 'react'
import type { ChiTietCa, KetQuaAI, NhanDinh, PhanHoiDaGhi, TrangThaiAI } from '@/api/types'
import { mergeFindingsFeedback, selectFindingsSource } from '@/lib/aiReview'
import type { BangNhanDinh } from '@/lib/aiReview'
import {
  computeSixFactorsStatus,
  countAttentionByFactor,
  hasSevereByFactor,
} from '@/lib/orderDetail'
import type { FactorIndex, SixFactorItem } from '@/lib/orderDetail'
import { sortAttentionFindings } from '@/lib/presentation'

export interface UseReviewFindingsInput {
  detail: ChiTietCa | null
  aiTrangThai: TrangThaiAI
  aiKetQua: KetQuaAI | null
  sessionFeedbackForCase: Readonly<Record<string, PhanHoiDaGhi>>
}

export interface UseReviewFindingsResult {
  displayedFindings: BangNhanDinh | null
  allAttention: NhanDinh[]
  allPassed: NhanDinh[]
  sixFactors: SixFactorItem[]
  attentionCountByFactor: Record<FactorIndex, number>
  severeByFactor: Record<FactorIndex, boolean>
  totalAttention: number
  hasAnySevere: boolean
}

const EMPTY_FINDINGS: NhanDinh[] = []
const EMPTY_SIX_FACTORS: SixFactorItem[] = []
const ZERO_COUNTS: Record<FactorIndex, number> = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0 }
const NO_SEVERE: Record<FactorIndex, boolean> = {
  1: false,
  2: false,
  3: false,
  4: false,
  5: false,
  6: false,
  7: false,
}

/** Nguồn tính toán dùng chung cho thanh điều hướng 8 mục và tab Thẩm định. */
export function useReviewFindings({
  detail,
  aiTrangThai,
  aiKetQua,
  sessionFeedbackForCase,
}: UseReviewFindingsInput): UseReviewFindingsResult {
  const displayedFindings = useMemo(() => {
    if (!detail) {
      return null
    }
    const raw = selectFindingsSource(detail.nhan_dinh, aiTrangThai, aiKetQua)
    const fallbackSources =
      raw === detail.nhan_dinh
        ? aiKetQua?.nhan_dinh
          ? [aiKetQua.nhan_dinh]
          : []
        : [detail.nhan_dinh]
    return mergeFindingsFeedback(raw, sessionFeedbackForCase, fallbackSources)
  }, [detail, aiTrangThai, aiKetQua, sessionFeedbackForCase])

  const allAttention = useMemo(
    () => (displayedFindings ? sortAttentionFindings(displayedFindings.can_chu_y) : EMPTY_FINDINGS),
    [displayedFindings],
  )

  const allPassed = displayedFindings ? displayedFindings.dat : EMPTY_FINDINGS

  const yeuToChuaKiem = detail?.nhan_dinh.yeu_to_chua_kiem
  const sixFactors = useMemo(() => {
    if (!yeuToChuaKiem) {
      return EMPTY_SIX_FACTORS
    }
    return computeSixFactorsStatus({
      can_chu_y: allAttention,
      dat: allPassed,
      yeu_to_chua_kiem: yeuToChuaKiem,
    })
  }, [allAttention, allPassed, yeuToChuaKiem])

  const attentionCountByFactor = useMemo(
    () => (displayedFindings ? countAttentionByFactor(allAttention) : ZERO_COUNTS),
    [displayedFindings, allAttention],
  )

  const severeByFactor = useMemo(
    () => (displayedFindings ? hasSevereByFactor(allAttention) : NO_SEVERE),
    [displayedFindings, allAttention],
  )

  const totalAttention = allAttention.length
  const hasAnySevere = useMemo(
    () => allAttention.some((item) => item.muc_do_ma === 'nghiem_trong'),
    [allAttention],
  )

  return {
    displayedFindings,
    allAttention,
    allPassed,
    sixFactors,
    attentionCountByFactor,
    severeByFactor,
    totalAttention,
    hasAnySevere,
  }
}
