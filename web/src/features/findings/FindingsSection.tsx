import type { RefObject } from 'react'
import type { ChiSo, GuiPhanHoi, NhanDinh, TrangThaiAI } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { InlineAlert } from '@/components/ui/inline-alert'
import type { EvidenceTarget } from '@/lib/uiTypes'
import { AiStatusBar } from './AiStatusBar'
import { FindingCard } from './FindingCard'
import { PassedList } from './PassedList'

export interface FindingsSectionProps {
  caId: string
  attentionFindings: readonly NhanDinh[]
  passedFindings: readonly NhanDinh[]
  yeuToChuaKiem: readonly string[]
  soLuatDaChay: number
  chiSo: readonly ChiSo[]
  nhomLyDo: readonly string[]
  aiTrangThai: TrangThaiAI
  aiThoiGianMs: number | null
  aiCoDienGiai: number
  aiDoAiThem: number
  aiCanhBao: readonly string[]
  onRerunAi: () => void
  isFeedbackSubmitting: (caId: string, id: string) => boolean
  getFeedbackError: (caId: string, id: string) => string | null
  onSubmitFeedback: (caId: string, payload: GuiPhanHoi) => Promise<boolean>
  onClearFeedbackError: (caId: string, id: string) => void
  onOpenEvidence: (target: EvidenceTarget, trigger: HTMLButtonElement) => void
  sectionRef?: RefObject<HTMLElement | null>
}

/** Vùng trọng tâm hiển thị bảng nhận định cần chú ý, trạng thái AI và các mục đạt. */
export function FindingsSection({
  caId,
  attentionFindings,
  passedFindings,
  yeuToChuaKiem,
  soLuatDaChay,
  chiSo,
  nhomLyDo,
  aiTrangThai,
  aiThoiGianMs,
  aiCoDienGiai,
  aiDoAiThem,
  aiCanhBao,
  onRerunAi,
  isFeedbackSubmitting,
  getFeedbackError,
  onSubmitFeedback,
  onClearFeedbackError,
  onOpenEvidence,
  sectionRef,
}: FindingsSectionProps) {
  return (
    <section
      ref={sectionRef}
      aria-label="Bảng nhận định"
      className="flex flex-col gap-3"
    >
      <div className="flex flex-wrap items-center gap-2.5">
        <h2 className="text-lg font-semibold text-fg">Bảng nhận định</h2>
        <Badge
          tone={attentionFindings.length > 0 ? 'neutral' : 'success'}
          variant="soft"
          className="tabular-nums"
        >
          {attentionFindings.length} mục cần chú ý
        </Badge>
      </div>

      {yeuToChuaKiem.length > 0 ? (
        <InlineAlert tone="neutral">
          Chưa có luật kiểm tra cho các yếu tố: {yeuToChuaKiem.join(', ')}
        </InlineAlert>
      ) : null}

      <AiStatusBar
        trangThai={aiTrangThai}
        thoiGianMs={aiThoiGianMs}
        coDienGiai={aiCoDienGiai}
        doAiThem={aiDoAiThem}
        canhBao={aiCanhBao}
        onRerun={onRerunAi}
      />

      {attentionFindings.length === 0 ? (
        <InlineAlert tone="success">
          Không có mục cần chú ý trong phạm vi {soLuatDaChay} luật đã chạy.
        </InlineAlert>
      ) : (
        <div className="flex flex-col gap-3">
          {attentionFindings.map((finding) => (
            <FindingCard
              key={`${caId}::${finding.nhan_dinh_id}`}
              caId={caId}
              finding={finding}
              chiSo={chiSo}
              nhomLyDo={nhomLyDo}
              submitting={isFeedbackSubmitting(caId, finding.nhan_dinh_id)}
              feedbackError={getFeedbackError(caId, finding.nhan_dinh_id)}
              onSubmitFeedback={onSubmitFeedback}
              onClearFeedbackError={onClearFeedbackError}
              onOpenEvidence={onOpenEvidence}
            />
          ))}
        </div>
      )}

      <PassedList key={`passed-${caId}`} passed={passedFindings} />
    </section>
  )
}
