import { Info } from 'lucide-react'
import type { CanCu, ChiSo, TrichDan } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Collapsible,
  CollapsibleChevron,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { RecordId } from '@/components/ui/record-id'
import { formatClinicalText } from '@/lib/displayFormat'
import { stripPendingSourceNote } from '@/lib/orderDetail'
import { findMetricByFormula } from '@/lib/presentation'
import type { EvidenceTarget } from '@/lib/uiTypes'

export interface EvidenceListProps {
  caId: string
  canCu: readonly CanCu[]
  trichDan?: readonly TrichDan[]
  chiSo: readonly ChiSo[]
  defaultExpanded: boolean
  onOpenEvidence: (target: EvidenceTarget, trigger: HTMLButtonElement) => void
}

/** Danh sách căn cứ dạng dòng thời gian đánh số, gộp phần Tài liệu với Nguồn trích để không lặp. */
export function EvidenceList({
  caId,
  canCu,
  trichDan = [],
  chiSo,
  defaultExpanded,
  onOpenEvidence,
}: EvidenceListProps) {
  const hasCitations = trichDan.length > 0
  const firstDocumentIndex = canCu.findIndex((ev) => ev.loai_ma === 'tai_lieu')
  const hasTaiLieuStep = firstDocumentIndex !== -1
  const totalSteps = canCu.length + (hasCitations && !hasTaiLieuStep ? trichDan.length : 0)

  const handleOpen = (ev: CanCu, trigger: HTMLButtonElement) => {
    if (ev.loai_ma === 'du_lieu' && ev.ban_ghi_id) {
      onOpenEvidence(
        {
          kind: 'record',
          caId,
          banGhiId: ev.ban_ghi_id,
          titleHint: formatClinicalText(ev.mo_ta),
        },
        trigger,
      )
      return
    }
    if (ev.loai_ma === 'tinh_toan') {
      const metric = findMetricByFormula(chiSo, ev.cong_thuc)
      if (metric) {
        onOpenEvidence(
          {
            kind: 'metric',
            metric,
            titleHint: formatClinicalText(ev.mo_ta),
          },
          trigger,
        )
        return
      }
    }
    if (ev.loai_ma === 'tai_lieu' && hasCitations) {
      const firstSource = trichDan[0]
      onOpenEvidence(
        {
          kind: 'source',
          caId,
          doanTrichId: firstSource.doan_trich_id,
          nhan: firstSource.nhan,
          trichNguyenVan: firstSource.trich_nguyen_van,
        },
        trigger,
      )
      return
    }
    onOpenEvidence(
      {
        kind: 'document',
        moTa: formatClinicalText(ev.mo_ta),
        ghiChu: stripPendingSourceNote(ev.ghi_chu, hasCitations),
      },
      trigger,
    )
  }

  return (
    <Collapsible defaultOpen={defaultExpanded} className="pt-1">
      <CollapsibleTrigger className="inline-flex cursor-pointer items-center gap-1.5 py-1 text-sm font-medium text-fg transition-colors duration-120 hover:text-primary">
        <CollapsibleChevron />
        <span className="tabular-nums">Căn cứ ({totalSteps})</span>
      </CollapsibleTrigger>

      <CollapsibleContent className="flex flex-col gap-3 pt-2">
        {canCu.length > 0 || hasCitations ? (
          <ol className="flex flex-col">
            {canCu.map((ev, idx) => {
              const showRecordButton =
                ev.mo_duoc && ev.loai_ma === 'du_lieu' && Boolean(ev.ban_ghi_id)
              const showCalcButton = ev.mo_duoc && ev.loai_ma === 'tinh_toan'
              const showDocButton = ev.loai_ma === 'tai_lieu' && !hasCitations
              const attachCitationsHere =
                hasCitations && idx === firstDocumentIndex

              const btnLabel = showCalcButton
                ? 'Xem phép tính'
                : showDocButton
                  ? 'Mở nguồn'
                  : 'Mở bản ghi'

              const cleanNote = stripPendingSourceNote(ev.ghi_chu, hasCitations)
              const isLast =
                idx === canCu.length - 1 && (!hasCitations || hasTaiLieuStep)

              return (
                <li
                  key={`${ev.so}-${ev.loai_ma}-${ev.ban_ghi_id ?? 'none'}`}
                  className="relative pl-7 pb-3 last:pb-0"
                >
                  {!isLast ? (
                    <span
                      className="absolute left-2.5 top-5 -bottom-1 w-px -translate-x-1/2 bg-line"
                      aria-hidden="true"
                    />
                  ) : null}

                  <span
                    className="absolute left-0 top-0.5 z-10 flex size-5 items-center justify-center rounded-full border border-line-strong bg-surface text-2xs font-medium text-fg-muted tabular-nums"
                    aria-hidden="true"
                  >
                    {ev.so}
                  </span>

                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="flex min-w-[200px] flex-1 flex-wrap items-center gap-2">
                      <Badge tone="neutral" variant="outline">
                        {ev.loai_nhan}
                      </Badge>
                      <span className="text-sm text-fg">{formatClinicalText(ev.mo_ta)}</span>
                      {ev.ban_ghi_id && ev.loai_ma === 'du_lieu' ? (
                        <RecordId id={ev.ban_ghi_id} />
                      ) : null}
                    </div>

                    {showRecordButton || showCalcButton || showDocButton ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="shrink-0"
                        onClick={(e) => handleOpen(ev, e.currentTarget)}
                      >
                        {btnLabel}
                      </Button>
                    ) : null}
                  </div>

                  {attachCitationsHere ? (
                    <div className="mt-2 flex flex-col gap-2">
                      {trichDan.map((td) => (
                        <div
                          key={`${td.so}-${td.doan_trich_id}`}
                          className="rounded-sm border border-line bg-surface-muted/40 p-2.5 flex flex-col gap-1.5"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <span className="text-xs font-medium text-fg">{td.nhan}</span>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={(e) =>
                                onOpenEvidence(
                                  {
                                    kind: 'source',
                                    caId,
                                    doanTrichId: td.doan_trich_id,
                                    nhan: td.nhan,
                                    trichNguyenVan: td.trich_nguyen_van,
                                  },
                                  e.currentTarget,
                                )
                              }
                            >
                              Mở nguồn
                            </Button>
                          </div>
                          <blockquote className="border-l-2 border-line-strong pl-2.5 text-xs text-fg-muted whitespace-pre-wrap">
                            {td.trich_nguyen_van}
                          </blockquote>
                        </div>
                      ))}
                    </div>
                  ) : null}

                  {cleanNote ? (
                    <p className="mt-1 flex items-start gap-1.5 text-xs text-warning-fg">
                      <Info
                        className="mt-0.5 size-3.5 shrink-0"
                        strokeWidth={1.75}
                        aria-hidden="true"
                      />
                      <span className="whitespace-pre-wrap">{formatClinicalText(cleanNote)}</span>
                    </p>
                  ) : null}
                </li>
              )
            })}

            {/* Nếu thẻ nhận định chưa có bước tai_lieu trong can_cu nhưng có trích dẫn nguồn AI */}
            {hasCitations && !hasTaiLieuStep
              ? trichDan.map((td, idx) => {
                  const stepNum = canCu.length + idx + 1
                  const isLast = idx === trichDan.length - 1
                  return (
                    <li
                      key={`src-${td.so}-${td.doan_trich_id}`}
                      className="relative pl-7 pb-3 last:pb-0"
                    >
                      {!isLast ? (
                        <span
                          className="absolute left-2.5 top-5 -bottom-1 w-px -translate-x-1/2 bg-line"
                          aria-hidden="true"
                        />
                      ) : null}
                      <span
                        className="absolute left-0 top-0.5 z-10 flex size-5 items-center justify-center rounded-full border border-line-strong bg-surface text-2xs font-medium text-fg-muted tabular-nums"
                        aria-hidden="true"
                      >
                        {stepNum}
                      </span>
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div className="flex min-w-[200px] flex-1 flex-wrap items-center gap-2">
                          <Badge tone="neutral" variant="outline">
                            Tài liệu
                          </Badge>
                          <span className="text-sm font-medium text-fg">{td.nhan}</span>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="shrink-0"
                          onClick={(e) =>
                            onOpenEvidence(
                              {
                                kind: 'source',
                                caId,
                                doanTrichId: td.doan_trich_id,
                                nhan: td.nhan,
                                trichNguyenVan: td.trich_nguyen_van,
                              },
                              e.currentTarget,
                            )
                          }
                        >
                          Mở nguồn
                        </Button>
                      </div>
                      <blockquote className="mt-1.5 border-l-2 border-line-strong pl-2.5 text-xs text-fg-muted whitespace-pre-wrap">
                        {td.trich_nguyen_van}
                      </blockquote>
                    </li>
                  )
                })
              : null}
          </ol>
        ) : (
          <p className="text-xs text-fg-subtle">Không có căn cứ chi tiết.</p>
        )}
      </CollapsibleContent>
    </Collapsible>
  )
}
