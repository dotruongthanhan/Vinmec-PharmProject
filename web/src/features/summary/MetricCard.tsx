import { useRef, useState } from 'react'
import { Calculator, CircleHelp, X } from 'lucide-react'
import type { ChiSo } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import {
  DataTable,
  DataTableBody,
  DataTableCell,
  DataTableHead,
  DataTableHeader,
  DataTableRow,
} from '@/components/ui/data-table'
import { IconButton } from '@/components/ui/icon-button'
import {
  Popover,
  PopoverClose,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { RecordId } from '@/components/ui/record-id'
import type { EvidenceTarget } from '@/lib/uiTypes'

export interface MetricCardProps {
  caId: string
  metric: ChiSo
  abnormal?: boolean
  onOpenEvidence: (target: EvidenceTarget, trigger: HTMLButtonElement) => void
}

/** Ô chỉ số lâm sàng gọn, mở Popover để xem đầu vào, ghi chú và tài liệu tham khảo. */
export function MetricCard({
  caId,
  metric,
  abnormal = false,
  onOpenEvidence,
}: MetricCardProps) {
  const [popoverOpen, setPopoverOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement | null>(null)
  const hasMissing = metric.thieu.length > 0

  return (
    <Card className="p-3 flex flex-col gap-1 min-w-0">
      <div className="flex items-start justify-between gap-1.5">
        <div className="flex items-start gap-1.5 min-w-0">
          {abnormal ? (
            <span
              className="mt-1.5 size-1.5 rounded-full bg-danger-solid shrink-0"
              aria-label="Giá trị bất thường"
            />
          ) : null}
          <span className="text-xs font-medium text-fg-muted leading-snug">
            {metric.nhan}
          </span>
        </div>

        <Popover open={popoverOpen} onOpenChange={setPopoverOpen}>
          <PopoverTrigger asChild>
            <IconButton
              ref={triggerRef}
              icon={<Calculator className="size-4" strokeWidth={1.75} />}
              aria-label={`Xem đầu vào và công thức ${metric.nhan}`}
              className="shrink-0 -mr-1 -mt-0.5"
            />
          </PopoverTrigger>
          <PopoverContent
            align="end"
            tabIndex={-1}
            onOpenAutoFocus={(e) => {
              e.preventDefault()
              if (e.currentTarget instanceof HTMLElement) {
                e.currentTarget.focus()
              }
            }}
            className="w-[420px] max-w-[calc(100vw-32px)] p-4 flex flex-col gap-3"
          >
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-semibold text-fg">{metric.nhan}</p>
              <PopoverClose asChild>
                <IconButton
                  icon={<X className="size-4" strokeWidth={1.75} />}
                  aria-label={`Đóng công thức ${metric.nhan}`}
                  className="-mr-1.5 -mt-1"
                />
              </PopoverClose>
            </div>

            {metric.dau_vao.length > 0 ? (
              <DataTable>
                <DataTableHeader>
                  <tr>
                    <DataTableHead>Đầu vào</DataTableHead>
                    <DataTableHead align="right">Giá trị</DataTableHead>
                    <DataTableHead>Thời điểm / Mã</DataTableHead>
                  </tr>
                </DataTableHeader>
                <DataTableBody>
                  {metric.dau_vao.map((inp, idx) => {
                    const banGhiId = inp.ban_ghi_id
                    return (
                      <DataTableRow key={`${inp.nhan}-${idx}`}>
                        <DataTableCell className="font-medium text-fg">
                          {inp.nhan}
                        </DataTableCell>
                        <DataTableCell align="right" className="whitespace-nowrap">
                          {inp.gia_tri_text}
                          {inp.don_vi ? ` ${inp.don_vi}` : ''}
                        </DataTableCell>
                        <DataTableCell className="text-fg-subtle">
                          <div className="flex flex-col items-start gap-1">
                            {inp.thoi_diem_text ? (
                              <span className="text-xs tabular-nums">
                                {inp.thoi_diem_text}
                              </span>
                            ) : null}
                            {banGhiId ? (
                              <button
                                type="button"
                                aria-label={`Mở bản ghi ${banGhiId}`}
                                className="inline-flex cursor-pointer rounded-sm"
                                onClick={(e) => {
                                  const returnTarget =
                                    triggerRef.current ?? e.currentTarget
                                  setPopoverOpen(false)
                                  onOpenEvidence(
                                    {
                                      kind: 'record',
                                      caId,
                                      banGhiId,
                                      titleHint: `${inp.nhan}: ${inp.gia_tri_text} ${inp.don_vi}`.trim(),
                                    },
                                    returnTarget,
                                  )
                                }}
                              >
                                <RecordId
                                  id={banGhiId}
                                  className="hover:border-primary hover:text-primary transition-colors duration-120"
                                />
                              </button>
                            ) : !inp.thoi_diem_text ? (
                              <span className="text-xs">—</span>
                            ) : null}
                          </div>
                        </DataTableCell>
                      </DataTableRow>
                    )
                  })}
                </DataTableBody>
              </DataTable>
            ) : (
              <p className="text-sm text-fg-subtle">Không có đầu vào hợp lệ.</p>
            )}

            {metric.ghi_chu.length > 0 ? (
              <ul className="flex flex-col gap-1 text-xs text-fg-muted">
                {metric.ghi_chu.map((note, idx) => (
                  <li key={`note-${idx}`} className="whitespace-pre-wrap">
                    {note}
                  </li>
                ))}
              </ul>
            ) : null}

            {metric.tham_khao ? (
              <p className="text-xs text-fg-subtle border-t border-line pt-2">
                {metric.tham_khao}
              </p>
            ) : null}
          </PopoverContent>
        </Popover>
      </div>

      <div className="flex flex-wrap items-baseline gap-x-1.5 gap-y-0.5 min-w-0">
        <span className="text-metric font-semibold text-fg tabular-nums tracking-tight">
          {metric.gia_tri_text}
        </span>
        {metric.don_vi ? (
          <span className="text-xs text-fg-subtle leading-snug">{metric.don_vi}</span>
        ) : null}
      </div>

      {hasMissing ? (
        <div>
          <Badge
            tone="missing"
            variant="soft"
            icon={<CircleHelp className="size-3.5" strokeWidth={1.75} />}
            className="max-w-full h-auto min-h-[22px] whitespace-normal py-0.5 leading-tight"
          >
            Thiếu: {metric.thieu.join(', ')}
          </Badge>
        </div>
      ) : null}
    </Card>
  )
}
