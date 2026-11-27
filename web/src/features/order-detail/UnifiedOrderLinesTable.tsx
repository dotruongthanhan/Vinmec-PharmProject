import { ChevronDown, ChevronRight } from 'lucide-react'
import { Fragment } from 'react'
import type { ChiSo, GuiPhanHoi, NhanDinh } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import {
  DataTable,
  DataTableBody,
  DataTableCell,
  DataTableHead,
  DataTableHeader,
  DataTableRow,
} from '@/components/ui/data-table'
import { cn } from '@/lib/cn'
import { groupScheduleByDay, parseSchedule } from '@/lib/detailTables'
import { formatClinicalText } from '@/lib/displayFormat'
import type { FactorIndex } from '@/lib/orderDetail'
import type { EvidenceTarget, FeedbackDraft } from '@/lib/uiTypes'
import { lineHighlightSeverity } from '@/lib/unifiedOrderLines'
import type {
  PartitionedFindings,
  UnifiedLineSeverity,
  UnifiedLineStatusCode,
  UnifiedOrderLine,
} from '@/lib/unifiedOrderLines'
import { OrderLineExpandedPanel } from './OrderLineExpandedPanel'

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

/** Tông nền sáng nhẹ theo mức độ nghiêm trọng nhất của thuốc để chữ tối màu luôn rõ. */
const ROW_SEVERITY_SURFACE: Record<UnifiedLineSeverity, string> = {
  nghiem_trong: 'bg-danger-bg/85 hover:bg-danger-bg text-fg',
  can_luu_y: 'bg-warning-bg/85 hover:bg-warning-bg text-fg',
  thieu_du_lieu: 'bg-offlabel-bg/85 hover:bg-offlabel-bg text-fg',
  none: 'bg-surface hover:bg-surface-hover text-fg',
}

export interface UnifiedOrderLinesTableProps {
  caId: string
  lines: readonly UnifiedOrderLine[]
  partitioned: PartitionedFindings
  expandedLineKey: string | null
  onToggleLine: (lineKey: string) => void
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

/** Bảng Chi tiết y lệnh gộp 9 cột: không STT, không Kết quả thẩm định, bôi màu cả dòng & mở rộng 1 thuốc/lúc. */
export function UnifiedOrderLinesTable({
  caId,
  lines,
  partitioned,
  expandedLineKey,
  onToggleLine,
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
}: UnifiedOrderLinesTableProps) {
  if (lines.length === 0) {
    return <p className="text-sm text-fg-subtle">Không có dòng thuốc.</p>
  }

  return (
    <DataTable>
      <DataTableHeader>
        <tr>
          <DataTableHead>Mã y lệnh</DataTableHead>
          <DataTableHead>Tên thuốc</DataTableHead>
          <DataTableHead>Liều</DataTableHead>
          <DataTableHead>Tần suất</DataTableHead>
          <DataTableHead>Đường dùng</DataTableHead>
          <DataTableHead>Ngày kê</DataTableHead>
          <DataTableHead>Trạng thái</DataTableHead>
          <DataTableHead>Bắt đầu, kết thúc</DataTableHead>
          <DataTableHead>Lịch dùng</DataTableHead>
        </tr>
      </DataTableHeader>
      <DataTableBody>
        {lines.map((line) => {
          const bucket = partitioned.byLineKey[line.key] ?? { attention: [], passed: [] }
          const severity = lineHighlightSeverity(bucket.attention)
          const isExpanded = expandedLineKey === line.key
          const doses = parseSchedule(line.lichDungRaw)
          const days = groupScheduleByDay(doses)

          return (
            <Fragment key={line.key}>
              <DataTableRow
                tabIndex={0}
                aria-expanded={isExpanded}
                data-severity={severity}
                data-line-key={line.key}
                onClick={() => onToggleLine(line.key)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    onToggleLine(line.key)
                  }
                }}
                className={cn(
                  'cursor-pointer',
                  ROW_SEVERITY_SURFACE[severity],
                  isExpanded && 'ring-1 ring-inset ring-primary/40',
                )}
              >
                <DataTableCell className="whitespace-nowrap font-mono text-xs text-fg-muted">
                  {line.yLenhId}
                </DataTableCell>
                <DataTableCell className="min-w-40 font-semibold text-fg">
                  <span className="inline-flex items-center gap-1.5">
                    {isExpanded ? (
                      <ChevronDown className="size-3.5 shrink-0 text-fg-muted" strokeWidth={2} aria-hidden="true" />
                    ) : (
                      <ChevronRight className="size-3.5 shrink-0 text-fg-muted" strokeWidth={2} aria-hidden="true" />
                    )}
                    <span>{line.tenThuoc}</span>
                  </span>
                </DataTableCell>
                <DataTableCell className="whitespace-nowrap">{line.lieu}</DataTableCell>
                <DataTableCell className="whitespace-nowrap">{line.tanSuat}</DataTableCell>
                <DataTableCell className="whitespace-nowrap">{line.duongDung}</DataTableCell>
                <DataTableCell className="whitespace-nowrap text-xs tabular-nums">
                  {line.ngayKe}
                </DataTableCell>
                <DataTableCell className="whitespace-nowrap">
                  <Badge tone={STATUS_BADGE_TONE[line.trangThaiCode]} variant="soft">
                    {line.trangThaiLabel}
                  </Badge>
                </DataTableCell>
                <DataTableCell className="whitespace-nowrap tabular-nums">
                  {line.batDauText || line.ketThucText ? (
                    <div className="flex flex-col text-xs leading-5">
                      <span>
                        <span className="text-fg-subtle">Từ </span>
                        {line.batDauText ?? '—'}
                      </span>
                      <span>
                        <span className="text-fg-subtle">Đến </span>
                        {line.ketThucText ?? '—'}
                      </span>
                    </div>
                  ) : (
                    '—'
                  )}
                </DataTableCell>
                <DataTableCell className="min-w-36">
                  {days.length > 0 ? (
                    <div className="flex flex-col gap-1">
                      {days.map((day) => (
                        <div key={day.date} className="flex flex-wrap items-center gap-1 tabular-nums">
                          <span className="w-12 shrink-0 text-xs text-fg-subtle">
                            {day.date.slice(0, 5)}
                          </span>
                          {day.doses.map((dose) => (
                            <span
                              key={`${dose.date}-${dose.time}`}
                              title={dose.dose ? `${dose.time}: ${dose.dose}` : dose.time}
                              className="rounded-sm bg-surface-muted px-1.5 py-0.5 text-xs text-fg"
                            >
                              {dose.time}
                            </span>
                          ))}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <span className="text-xs text-fg-muted">
                      {formatClinicalText(line.lichDungRaw || '—')}
                    </span>
                  )}
                </DataTableCell>
              </DataTableRow>

              {isExpanded ? (
                <tr className="border-b border-line bg-surface-muted/40">
                  <td colSpan={9} className="p-4">
                    <OrderLineExpandedPanel
                      caId={caId}
                      line={line}
                      attention={bucket.attention}
                      passed={bucket.passed}
                      chiSo={chiSo}
                      nhomLyDo={nhomLyDo}
                      feedbackDrafts={feedbackDrafts}
                      onFeedbackDraftChange={onFeedbackDraftChange}
                      isFeedbackSubmitting={isFeedbackSubmitting}
                      getFeedbackError={getFeedbackError}
                      onSubmitFeedback={onSubmitFeedback}
                      onClearFeedbackError={onClearFeedbackError}
                      onOpenEvidence={onOpenEvidence}
                      onAskAboutFinding={onAskAboutFinding}
                      onOpenFactorInReviewTab={onOpenFactorInReviewTab}
                    />
                  </td>
                </tr>
              ) : null}
            </Fragment>
          )
        })}
      </DataTableBody>
    </DataTable>
  )
}
