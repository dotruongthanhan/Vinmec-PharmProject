import { Fragment, useState } from 'react'
import type { ChiSo, GuiPhanHoi, NhanDinh } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { InlineAlert } from '@/components/ui/inline-alert'
import { FindingCard } from '@/features/findings/FindingCard'
import { PassedList } from '@/features/findings/PassedList'
import { factorIndexOf } from '@/lib/orderDetail'
import type { FactorIndex } from '@/lib/orderDetail'
import type { FeedbackDraft } from '@/lib/uiTypes'
import { EMPTY_FEEDBACK_DRAFT } from '@/lib/uiTypes'
import type { EvidenceTarget } from '@/lib/uiTypes'
import type { UnifiedLineStatusCode, UnifiedOrderLine } from '@/lib/unifiedOrderLines'
import { InfoRows } from './DetailSections'
import type { InfoItem } from './DetailSections'

const STATUS_BADGE_TONE: Record<
  UnifiedLineStatusCode,
  'warning' | 'success' | 'missing' | 'neutral'
> = {
  cho_duyet: 'warning',
  dang_dung: 'success',
  dang_cho: 'missing',
  dung_xong: 'neutral',
  da_huy: 'neutral',
}

const MISSING = 'Chưa ghi nhận'

export interface OrderLineExpandedPanelProps {
  caId: string
  line: UnifiedOrderLine
  attention: readonly NhanDinh[]
  passed: readonly NhanDinh[]
  chiSo: readonly ChiSo[]
  nhomLyDo: readonly string[]
  feedbackDrafts: Readonly<Record<string, FeedbackDraft>>
  onFeedbackDraftChange: (nhanDinhId: string, draft: FeedbackDraft) => void
  isFeedbackSubmitting: (caId: string, id: string) => boolean
  getFeedbackError: (caId: string, id: string) => string | null
  onSubmitFeedback: (caId: string, payload: GuiPhanHoi) => Promise<boolean>
  onClearFeedbackError: (caId: string, id: string) => void
  onOpenEvidence: (target: EvidenceTarget, trigger: HTMLButtonElement) => void
  onAskAboutFinding: (finding: NhanDinh) => void
  onOpenFactorInReviewTab?: (factor: FactorIndex) => void
}

/** Ngăn mở rộng của 1 dòng thuốc: hiển thị metadata y lệnh và toàn bộ nhận định của thuốc đó. */
export function OrderLineExpandedPanel({
  caId,
  line,
  attention,
  passed,
  chiSo,
  nhomLyDo,
  feedbackDrafts,
  onFeedbackDraftChange,
  isFeedbackSubmitting,
  getFeedbackError,
  onSubmitFeedback,
  onClearFeedbackError,
  onOpenEvidence,
  onAskAboutFinding,
  onOpenFactorInReviewTab,
}: OrderLineExpandedPanelProps) {
  const [passedOpen, setPassedOpen] = useState(false)

  const summaryDose = [line.lieu, line.tanSuat, line.duongDung]
    .filter((v) => v && v !== '—')
    .join(' · ')
  const drugSummary = summaryDose ? `${line.tenThuoc} (${summaryDose})` : line.tenThuoc

  const metadataItems: InfoItem[] = [
    { label: 'Thuốc dùng', value: drugSummary, wide: true },
    {
      label: 'Trạng thái',
      value: (
        <Badge tone={STATUS_BADGE_TONE[line.trangThaiCode]} variant="soft">
          {line.trangThaiLabel}
        </Badge>
      ),
    },
    { label: 'Khoa kê', value: line.khoaKe || MISSING },
    { label: 'Luồng', value: line.luongDuyet || MISSING },
    { label: 'Loại y lệnh', value: line.loaiYLenh || MISSING },
    { label: 'Người kê', value: line.nguoiKe || MISSING },
  ]

  if (line.cachDung) {
    metadataItems.push({ label: 'Cách dùng', value: line.cachDung, wide: true })
  }
  if (line.lyDoNgung) {
    metadataItems.push({ label: 'Lý do ngừng', value: line.lyDoNgung, wide: true })
  }
  if (line.thoiDiemNgung) {
    metadataItems.push({ label: 'Thời điểm ngừng', value: line.thoiDiemNgung })
  }
  if (line.thayTheYLenhId) {
    metadataItems.push({
      label: 'Y lệnh thay thế',
      value: <span className="font-mono">{line.thayTheYLenhId}</span>,
    })
  }

  return (
    <div className="flex flex-col gap-4 rounded-md border border-line bg-surface p-4 shadow-xs">
      <InfoRows items={metadataItems} />

      <div className="flex flex-col gap-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold text-fg">Nhận định thuốc</h3>
          <Badge tone={attention.length > 0 ? 'neutral' : 'success'} variant="soft">
            {attention.length} mục cần chú ý
          </Badge>
        </div>

        {attention.length > 0 ? (
          <div className="flex flex-col gap-3">
            {attention.map((finding) => {
              const factorIdx = onOpenFactorInReviewTab
                ? factorIndexOf(finding.yeu_to)
                : null
              return (
                <Fragment key={`${caId}::${line.key}::${finding.nhan_dinh_id}`}>
                  <FindingCard
                    caId={caId}
                    finding={finding}
                    chiSo={chiSo}
                    nhomLyDo={nhomLyDo}
                    submitting={isFeedbackSubmitting(caId, finding.nhan_dinh_id)}
                    feedbackError={getFeedbackError(caId, finding.nhan_dinh_id)}
                    feedbackDraft={feedbackDrafts[finding.nhan_dinh_id] ?? EMPTY_FEEDBACK_DRAFT}
                    onFeedbackDraftChange={(draft) =>
                      onFeedbackDraftChange(finding.nhan_dinh_id, draft)
                    }
                    onSubmitFeedback={onSubmitFeedback}
                    onClearFeedbackError={onClearFeedbackError}
                    onOpenEvidence={onOpenEvidence}
                    onAskAboutFinding={onAskAboutFinding}
                    onOpenFactor={
                      factorIdx !== null && onOpenFactorInReviewTab
                        ? () => onOpenFactorInReviewTab(factorIdx)
                        : undefined
                    }
                  />
                </Fragment>
              )
            })}
          </div>
        ) : line.trangThaiCode === 'da_huy' || line.trangThaiCode === 'dung_xong' ? (
          <p className="text-xs text-fg-subtle">
            Chưa ghi nhận nhận định thẩm định cho dòng thuốc thuộc y lệnh lịch sử này.
          </p>
        ) : (
          <InlineAlert tone="success">
            Không có nhận định cần chú ý cho {line.tenThuoc}.
          </InlineAlert>
        )}

        {passed.length > 0 ? (
          <PassedList
            key={`passed-${caId}-${line.key}`}
            passed={passed}
            open={passedOpen}
            onOpenChange={setPassedOpen}
          />
        ) : null}
      </div>
    </div>
  )
}
