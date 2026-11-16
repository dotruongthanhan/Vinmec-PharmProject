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
import { findMetricByFormula } from '@/lib/presentation'
import type { EvidenceTarget } from '@/lib/uiTypes'
import { SourceList } from './SourceList'

export interface EvidenceListProps {
  caId: string
  canCu: readonly CanCu[]
  trichDan?: readonly TrichDan[]
  chiSo: readonly ChiSo[]
  defaultExpanded: boolean
  onOpenEvidence: (target: EvidenceTarget, trigger: HTMLButtonElement) => void
}

/** Danh sách căn cứ dạng dòng thời gian đánh số và nguồn tài liệu trích dẫn. */
export function EvidenceList({
  caId,
  canCu,
  trichDan = [],
  chiSo,
  defaultExpanded,
  onOpenEvidence,
}: EvidenceListProps) {
  const handleOpen = (ev: CanCu, trigger: HTMLButtonElement) => {
    if (ev.loai_ma === 'du_lieu' && ev.ban_ghi_id) {
      onOpenEvidence(
        {
          kind: 'record',
          caId,
          banGhiId: ev.ban_ghi_id,
          titleHint: ev.mo_ta,
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
            titleHint: ev.mo_ta,
          },
          trigger,
        )
        return
      }
    }
    onOpenEvidence(
      {
        kind: 'document',
        moTa: ev.mo_ta,
        ghiChu: ev.ghi_chu,
      },
      trigger,
    )
  }

  return (
    <Collapsible defaultOpen={defaultExpanded} className="pt-1">
      <CollapsibleTrigger className="inline-flex cursor-pointer items-center gap-1.5 py-1 text-sm font-medium text-fg transition-colors duration-120 hover:text-primary">
        <CollapsibleChevron />
        <span className="tabular-nums">
          Căn cứ ({canCu.length})
          {trichDan.length > 0 ? ` · Nguồn tài liệu (${trichDan.length})` : ''}
        </span>
      </CollapsibleTrigger>

      <CollapsibleContent className="flex flex-col gap-3 pt-2">
        {canCu.length > 0 ? (
          <ol className="flex flex-col">
            {canCu.map((ev, idx) => {
              const showRecordButton =
                ev.mo_duoc && ev.loai_ma === 'du_lieu' && Boolean(ev.ban_ghi_id)
              const showCalcButton = ev.mo_duoc && ev.loai_ma === 'tinh_toan'
              const showDocButton = ev.loai_ma === 'tai_lieu'
              const btnLabel = showCalcButton
                ? 'Xem phép tính'
                : showDocButton
                  ? 'Mở nguồn'
                  : 'Mở bản ghi'
              const isLast = idx === canCu.length - 1

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
                      <span className="text-sm text-fg">{ev.mo_ta}</span>
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

                  {ev.ghi_chu ? (
                    <p className="mt-1 flex items-start gap-1.5 text-xs text-warning-fg">
                      <Info
                        className="mt-0.5 size-3.5 shrink-0"
                        strokeWidth={1.75}
                        aria-hidden="true"
                      />
                      <span className="whitespace-pre-wrap">{ev.ghi_chu}</span>
                    </p>
                  ) : null}
                </li>
              )
            })}
          </ol>
        ) : trichDan.length === 0 ? (
          <p className="text-xs text-fg-subtle">Không có căn cứ chi tiết.</p>
        ) : null}

        <SourceList caId={caId} trichDan={trichDan} onOpenEvidence={onOpenEvidence} />
      </CollapsibleContent>
    </Collapsible>
  )
}
