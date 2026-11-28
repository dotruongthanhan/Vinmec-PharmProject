import { ArrowDown, ArrowUp, FileText } from 'lucide-react'
import { useState } from 'react'
import type { ChiTietXetNghiemDong } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import {
  DataTable,
  DataTableBody,
  DataTableCell,
  DataTableHead,
  DataTableHeader,
  DataTableRow,
} from '@/components/ui/data-table'
import { EmptyState } from '@/components/ui/empty-state'
import { InlineAlert } from '@/components/ui/inline-alert'
import { SingleLabTrendChart } from '@/features/charts/LabTrendChart'
import { cn } from '@/lib/cn'
import { formatClinicalText, formatReadableDateTime, parseTrendValue } from '@/lib/displayFormat'
import { parseVietnameseNumber } from '@/lib/labChart'
import { SectionHeading } from './DetailSections'

export interface LabsTabContentProps {
  labs: readonly ChiTietXetNghiemDong[]
  orderTimeText?: string | null
}

function labAssessmentLabel(lab: ChiTietXetNghiemDong): string {
  const parsedValue = parseTrendValue(lab.gia_tri_text)
  const dir = parseTrendValue(lab.huong ?? '').direction ?? parsedValue.direction
  if (!lab.ngoai_nguong) {
    return 'Trong tham chiếu'
  }
  if (dir === 'up') return 'Cao hơn tham chiếu'
  if (dir === 'down') return 'Thấp hơn tham chiếu'
  return 'Ngoài tham chiếu'
}

/** Tab Xét nghiệm: bảng phẳng theo từng lần đo (7 cột), mặc định không đồ thị, click hàng mở đồ thị có điểm in đậm. */
export function LabsTabContent({ labs, orderTimeText }: LabsTabContentProps) {
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)

  if (labs.length === 0) {
    return (
      <div className="rounded-md border border-line bg-surface">
        <EmptyState
          icon={FileText}
          title="Chưa có kết quả xét nghiệm"
          description="Ca bệnh này chưa ghi nhận dữ liệu xét nghiệm cận lâm sàng."
        />
      </div>
    )
  }

  const selectedLab =
    selectedIndex !== null && selectedIndex >= 0 && selectedIndex < labs.length
      ? labs[selectedIndex]
      : null
  const isNumericSelected =
    selectedLab !== null && parseVietnameseNumber(selectedLab.gia_tri_text) !== null

  const toggleRow = (idx: number) => {
    setSelectedIndex((prev) => (prev === idx ? null : idx))
  }

  return (
    <div className="flex flex-col gap-5">
      <section aria-label="Bảng xét nghiệm" className="flex flex-col gap-2.5">
        <SectionHeading
          title="Kết quả xét nghiệm"
          aside="Bấm vào một hàng để xem đồ thị diễn biến chỉ số"
        />

        <DataTable className="ui3-labs-table">
          <DataTableHeader>
            <tr>
              <DataTableHead className="w-10">STT</DataTableHead>
              <DataTableHead>Chỉ số xét nghiệm</DataTableHead>
              <DataTableHead className="ui3-labs-wide">Đơn vị</DataTableHead>
              <DataTableHead align="right">Kết quả</DataTableHead>
              <DataTableHead className="ui3-labs-wide">Khoảng tham chiếu</DataTableHead>
              <DataTableHead>Thời gian đo</DataTableHead>
              <DataTableHead>Đánh giá</DataTableHead>
            </tr>
          </DataTableHeader>
          <DataTableBody>
            {labs.map((lab, idx) => {
              const isSelected = selectedIndex === idx
              const parsedValue = parseTrendValue(lab.gia_tri_text)
              const dir = parseTrendValue(lab.huong ?? '').direction ?? parsedValue.direction
              const Arrow = dir === 'up' ? ArrowUp : dir === 'down' ? ArrowDown : null

              return (
                <DataTableRow
                  key={`${lab.ten}-${lab.thoi_diem_text}-${idx}`}
                  tabIndex={0}
                  aria-selected={isSelected}
                  data-selected={isSelected ? 'true' : undefined}
                  onClick={() => toggleRow(idx)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      toggleRow(idx)
                    }
                  }}
                  className={cn(
                    'cursor-pointer',
                    isSelected && 'bg-primary-soft/65 hover:bg-primary-soft border-l-2 border-l-primary font-bold',
                  )}
                >
                  <DataTableCell className={cn('text-fg-subtle', isSelected && 'font-bold text-fg')}>
                    {idx + 1}
                  </DataTableCell>
                  <DataTableCell className={cn('font-medium', isSelected && 'font-bold')}>
                    {lab.ten}
                  </DataTableCell>
                  <DataTableCell className={cn('ui3-labs-wide text-fg-subtle', isSelected && 'font-bold text-fg')}>
                    {formatClinicalText(lab.don_vi || '—')}
                  </DataTableCell>
                  <DataTableCell
                    align="right"
                    className={cn(
                      'break-words',
                      lab.ngoai_nguong && 'bg-danger-bg/60 font-semibold text-danger-fg',
                      isSelected && 'font-bold',
                    )}
                  >
                    <span className="inline-flex items-center justify-end gap-1">
                      {lab.ngoai_nguong && Arrow ? (
                        <Arrow className="size-3.5" strokeWidth={2} aria-hidden="true" />
                      ) : null}
                      {formatClinicalText(parsedValue.text)} <span className="ui3-labs-compact">{formatClinicalText(lab.don_vi || '—')}</span>
                    </span>
                    <div className="ui3-labs-compact text-xs text-fg-muted">{formatClinicalText(lab.khoang_tham_chieu || '—')}</div>
                  </DataTableCell>
                  <DataTableCell className={cn('ui3-labs-wide text-fg-muted tabular-nums', isSelected && 'font-bold text-fg')}>
                    {formatClinicalText(lab.khoang_tham_chieu || '—')}
                  </DataTableCell>
                  <DataTableCell className={cn('break-words tabular-nums', isSelected && 'font-bold')}>
                    {formatReadableDateTime(lab.thoi_diem_text)}
                  </DataTableCell>
                  <DataTableCell className={cn('whitespace-nowrap', isSelected && 'font-bold')}>
                    {lab.ngoai_nguong ? (
                      <Badge tone="danger" variant="soft">
                        {labAssessmentLabel(lab)}
                      </Badge>
                    ) : (
                      <span className={cn('text-xs text-fg-subtle', isSelected && 'font-bold text-fg')}>
                        Trong tham chiếu
                      </span>
                    )}
                  </DataTableCell>
                </DataTableRow>
              )
            })}
          </DataTableBody>
        </DataTable>
      </section>

      {selectedLab ? (
        <section
          aria-label={`Diễn biến ${selectedLab.ten} của bệnh nhân`}
          className="flex flex-col gap-2.5"
        >
          {isNumericSelected ? (
            <SingleLabTrendChart
              xetNghiem={labs}
              metricName={selectedLab.ten}
              orderTimeText={orderTimeText}
              selectedMatch={{
                thoiDiemText: selectedLab.thoi_diem_text,
                giaTriText: selectedLab.gia_tri_text,
              }}
              onClose={() => setSelectedIndex(null)}
            />
          ) : (
            <InlineAlert tone="neutral" title={`Diễn biến ${selectedLab.ten} của bệnh nhân`}>
              Kết quả định tính ({formatClinicalText(selectedLab.gia_tri_text)}) không có trục số để vẽ đồ thị.
            </InlineAlert>
          )}
        </section>
      ) : null}
    </div>
  )
}
