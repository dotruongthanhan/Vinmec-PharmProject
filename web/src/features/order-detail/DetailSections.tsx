import { ArrowDown, ArrowUp, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'
import type { BangYLenh, ChiSo, ChiTietXetNghiemDong, DienBienTomTat } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  DataTable,
  DataTableBody,
  DataTableCell,
  DataTableHead,
  DataTableHeader,
  DataTableRow,
} from '@/components/ui/data-table'
import { cn } from '@/lib/cn'
import { buildLabPivot, groupScheduleByDay, parseSchedule } from '@/lib/detailTables'
import { formatClinicalText, parseLeadingSymbolLabel, parseTrendValue } from '@/lib/displayFormat'
import { ICON_OF_TONE } from '@/lib/severity'
import type { EvidenceTarget } from '@/lib/uiTypes'

/** Tiêu đề một khối nội dung trong thẻ chi tiết, kèm chú thích phụ căn phải. */
export function SectionHeading({ title, aside }: { title: string; aside?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-2">
      <h2 className="text-base font-semibold tracking-tight text-fg">{title}</h2>
      {aside ? <div className="text-xs text-fg-subtle tabular-nums">{aside}</div> : null}
    </div>
  )
}

export interface InfoItem {
  label: string
  value: ReactNode
  /** Chiếm trọn bề ngang (cho nội dung dài như chẩn đoán). */
  wide?: boolean
}

/** Khối thông tin cơ bản: mỗi mục là một dòng "nhãn – giá trị", xếp hai hoặc ba cột. */
export function InfoRows({ items }: { items: readonly InfoItem[] }) {
  return (
    <dl className="grid grid-cols-1 gap-x-10 rounded-md border border-line bg-surface px-4 py-2 @xl:grid-cols-2 @5xl:grid-cols-3">
      {items.map((item) => (
        <div
          key={item.label}
          className={cn(
            'flex items-baseline gap-3 py-1.5 text-sm',
            item.wide && '@xl:col-span-2 @5xl:col-span-3',
          )}
        >
          <dt className="w-28 shrink-0 text-fg-subtle">{item.label}</dt>
          <dd className="min-w-0 font-medium text-fg tabular-nums">{item.value}</dd>
        </div>
      ))}
    </dl>
  )
}

/** Bảng nằm ngang các chỉ số lâm sàng tính từ hồ sơ: mỗi chỉ số một dòng. */
export function MetricsTable({
  metrics,
  crclAbnormal,
  onOpenEvidence,
}: {
  metrics: readonly ChiSo[]
  crclAbnormal: boolean
  onOpenEvidence: (target: EvidenceTarget, trigger: HTMLButtonElement) => void
}) {
  return (
    <DataTable>
      <DataTableHeader>
        <tr>
          <DataTableHead>Chỉ số</DataTableHead>
          <DataTableHead align="right">Giá trị</DataTableHead>
          <DataTableHead>Đơn vị</DataTableHead>
          <DataTableHead>Dữ liệu đầu vào</DataTableHead>
          <DataTableHead align="right">
            <span className="sr-only">Mở chi tiết</span>
          </DataTableHead>
        </tr>
      </DataTableHeader>
      <DataTableBody>
        {metrics.map((metric) => {
          const isMissing = metric.thieu.length > 0 || metric.gia_tri_text === '—'
          const abnormal = metric.cong_thuc === 'cockcroft_gault' && crclAbnormal && !isMissing
          return (
            <DataTableRow key={metric.cong_thuc}>
              <DataTableCell className="font-medium break-words">{metric.nhan}</DataTableCell>
              <DataTableCell
                align="right"
                className={cn(
                  'text-md font-semibold whitespace-nowrap',
                  abnormal ? 'text-danger-fg' : isMissing ? 'text-missing-fg' : 'text-fg',
                )}
              >
                {parseTrendValue(metric.gia_tri_text).text}
              </DataTableCell>
              <DataTableCell className="text-fg-subtle whitespace-nowrap">
                {isMissing ? '' : metric.don_vi}
              </DataTableCell>
              <DataTableCell className="text-fg-muted">
                {metric.thieu.length > 0 ? (
                  <span className="text-missing-fg">Thiếu: {metric.thieu.join(', ')}</span>
                ) : (
                  metric.dau_vao
                    .map(
                      (dv) =>
                        `${dv.nhan} ${formatClinicalText(dv.gia_tri_text)} ${formatClinicalText(dv.don_vi)}`.trim(),
                    )
                    .join(' · ')
                )}
              </DataTableCell>
              <DataTableCell align="right" className="py-1">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) =>
                    onOpenEvidence(
                      {
                        kind: 'metric',
                        metric,
                        titleHint: `${metric.nhan}: ${metric.gia_tri_text} ${metric.don_vi}`.trim(),
                      },
                      e.currentTarget,
                    )
                  }
                >
                  Chi tiết
                </Button>
              </DataTableCell>
            </DataTableRow>
          )
        })}
      </DataTableBody>
    </DataTable>
  )
}

const KNOWN_ORDER_COLS = new Set(['Thuốc', 'Liều', 'Tần suất', 'Đường dùng', 'Lịch dùng', 'Nhận định'])

/** Bảng chi tiết y lệnh: mỗi dòng một thuốc, có liều đầu, liều cuối và lịch dùng gom theo ngày. */
export function OrderLinesTable({
  table,
  selectedDrug,
  onSelectDrug,
}: {
  table: BangYLenh
  selectedDrug: string | null
  onSelectDrug?: (drugName: string) => void
}) {
  if (table.dong.length === 0) {
    return <p className="text-sm text-fg-subtle">Không có dòng thuốc.</p>
  }
  const extraCols = table.cot.filter((col) => !KNOWN_ORDER_COLS.has(col))

  return (
    <DataTable>
      <DataTableHeader>
        <tr>
          <DataTableHead className="w-10">STT</DataTableHead>
          <DataTableHead>Tên thuốc</DataTableHead>
          <DataTableHead>Liều</DataTableHead>
          <DataTableHead>Tần suất</DataTableHead>
          <DataTableHead>Đường dùng</DataTableHead>
          <DataTableHead>Bắt đầu, kết thúc</DataTableHead>
          <DataTableHead>Lịch dùng</DataTableHead>
          {extraCols.map((col) => (
            <DataTableHead key={col}>{col}</DataTableHead>
          ))}
          <DataTableHead>Kết quả thẩm định</DataTableHead>
        </tr>
      </DataTableHeader>
      <DataTableBody>
        {table.dong.map((row, idx) => {
          const drugName = row['Thuốc'] ?? ''
          const isSelected = Boolean(
            selectedDrug && drugName && selectedDrug.toLowerCase() === drugName.toLowerCase(),
          )
          const doses = parseSchedule(row['Lịch dùng'] ?? '')
          const days = groupScheduleByDay(doses)
          const first = doses[0]
          const last = doses[doses.length - 1]
          const findingText = onSelectDrug ? (row['Nhận định'] ?? '').trim() : ''
          const parsed = parseLeadingSymbolLabel(findingText)
          const ToneIcon = parsed.tone ? ICON_OF_TONE[parsed.tone] : TriangleAlert

          return (
            <DataTableRow
              key={`${drugName}-${idx}`}
              tone={isSelected ? 'primary' : undefined}
              tabIndex={drugName && onSelectDrug ? 0 : undefined}
              aria-selected={isSelected}
              onClick={drugName && onSelectDrug ? () => onSelectDrug(drugName) : undefined}
              onKeyDown={(e) => {
                if (drugName && onSelectDrug && (e.key === 'Enter' || e.key === ' ')) {
                  e.preventDefault()
                  onSelectDrug(drugName)
                }
              }}
              className={cn(drugName && onSelectDrug && 'cursor-pointer')}
            >
              <DataTableCell className="text-fg-subtle">{idx + 1}</DataTableCell>
              <DataTableCell className="min-w-36 font-semibold">{drugName || '—'}</DataTableCell>
              <DataTableCell className="whitespace-nowrap">
                {formatClinicalText(row['Liều'] ?? '—')}
              </DataTableCell>
              <DataTableCell className="whitespace-nowrap">{row['Tần suất'] ?? '—'}</DataTableCell>
              <DataTableCell className="whitespace-nowrap">{row['Đường dùng'] ?? '—'}</DataTableCell>
              <DataTableCell className="whitespace-nowrap tabular-nums">
                {first && last ? (
                  <div className="flex flex-col text-xs leading-5">
                    <span>
                      <span className="text-fg-subtle">Từ </span>
                      {first.time} · {first.date}
                    </span>
                    <span>
                      <span className="text-fg-subtle">Đến </span>
                      {last.time} · {last.date}
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
                    {formatClinicalText(row['Lịch dùng'] ?? '—')}
                  </span>
                )}
              </DataTableCell>
              {extraCols.map((col) => (
                <DataTableCell key={col}>{formatClinicalText(row[col] ?? '—')}</DataTableCell>
              ))}
              <DataTableCell className="whitespace-nowrap">
                {findingText ? (
                  <Badge
                    tone={parsed.tone ?? 'warning'}
                    variant="soft"
                    icon={<ToneIcon className="size-3.5" strokeWidth={1.75} />}
                  >
                    {parsed.text}
                  </Badge>
                ) : (
                  <span className="text-xs text-fg-subtle">{onSelectDrug ? 'Không có nhận định' : 'Chưa có thẩm định cho y lệnh này'}</span>
                )}
              </DataTableCell>
            </DataTableRow>
          )
        })}
      </DataTableBody>
    </DataTable>
  )
}

/** Bảng phiếu điều trị hoặc diễn biến: mỗi dòng một lần ghi, theo thứ tự thời gian. */
export function NotesTable({ notes }: { notes: readonly DienBienTomTat[] }) {
  return (
    <DataTable>
      <DataTableHeader>
        <tr>
          <DataTableHead className="w-10">STT</DataTableHead>
          <DataTableHead className="w-40">Ngày giờ ghi</DataTableHead>
          <DataTableHead className="w-36">Loại phiếu</DataTableHead>
          <DataTableHead>Theo dõi diễn biến và y lệnh</DataTableHead>
        </tr>
      </DataTableHeader>
      <DataTableBody>
        {notes.map((note, idx) => (
          <DataTableRow key={`${note.thoi_diem_text}-${note.loai_nhan}-${idx}`}>
            <DataTableCell className="text-fg-subtle">{idx + 1}</DataTableCell>
            <DataTableCell className="whitespace-nowrap tabular-nums">
              {formatClinicalText(note.thoi_diem_text)}
            </DataTableCell>
            <DataTableCell className="break-words text-fg-muted">{note.loai_nhan}</DataTableCell>
            <DataTableCell className="whitespace-pre-wrap leading-relaxed">
              {formatClinicalText(note.noi_dung)}
            </DataTableCell>
          </DataTableRow>
        ))}
      </DataTableBody>
    </DataTable>
  )
}

/** Bảng xét nghiệm dài: mỗi dòng một chỉ số, mỗi cột một thời điểm lấy mẫu, cột mới nhất ở bên phải. */
export function LabPivotTable({ labs }: { labs: readonly ChiTietXetNghiemDong[] }) {
  const pivot = buildLabPivot(labs)
  const lastCol = pivot.times.length - 1

  return (
    <DataTable>
      <DataTableHeader>
        <tr>
          <DataTableHead className="w-10">STT</DataTableHead>
          <DataTableHead>Chỉ số xét nghiệm</DataTableHead>
          <DataTableHead>Đơn vị</DataTableHead>
          <DataTableHead>Khoảng tham chiếu</DataTableHead>
          {pivot.times.map((time, idx) => (
            <DataTableHead key={time} align="right" className={cn(idx === lastCol && 'text-fg')}>
              {time}
              {idx === lastCol && pivot.times.length > 1 ? ' (mới nhất)' : ''}
            </DataTableHead>
          ))}
          <DataTableHead>Đánh giá</DataTableHead>
        </tr>
      </DataTableHeader>
      <DataTableBody>
        {pivot.rows.map((row, idx) => {
          const latest = [...row.cells].reverse().find((cell) => cell !== null) ?? null
          return (
            <DataTableRow key={row.name}>
              <DataTableCell className="text-fg-subtle">{idx + 1}</DataTableCell>
              <DataTableCell className="font-medium">{row.name}</DataTableCell>
              <DataTableCell className="text-fg-subtle whitespace-nowrap">{row.unit}</DataTableCell>
              <DataTableCell className="text-fg-muted whitespace-nowrap tabular-nums">
                {row.reference}
              </DataTableCell>
              {row.cells.map((cell, colIdx) => {
                const Arrow =
                  cell?.direction === 'up' ? ArrowUp : cell?.direction === 'down' ? ArrowDown : null
                return (
                  <DataTableCell
                    key={pivot.times[colIdx]}
                    align="right"
                    className={cn(
                      'whitespace-nowrap',
                      cell?.abnormal && 'bg-danger-bg/60 font-semibold text-danger-fg',
                      !cell && 'text-fg-disabled',
                    )}
                  >
                    {cell ? (
                      <span className="inline-flex items-center justify-end gap-1">
                        {cell.abnormal && Arrow ? (
                          <Arrow className="size-3.5" strokeWidth={2} aria-hidden="true" />
                        ) : null}
                        {cell.text}
                      </span>
                    ) : (
                      '—'
                    )}
                  </DataTableCell>
                )
              })}
              <DataTableCell className="whitespace-nowrap">
                {latest?.abnormal ? (
                  <Badge tone="danger" variant="soft">
                    {latest.direction === 'up'
                      ? 'Cao hơn tham chiếu'
                      : latest.direction === 'down'
                        ? 'Thấp hơn tham chiếu'
                        : 'Ngoài tham chiếu'}
                  </Badge>
                ) : (
                  <span className="text-xs text-fg-subtle">Trong tham chiếu</span>
                )}
              </DataTableCell>
            </DataTableRow>
          )
        })}
      </DataTableBody>
    </DataTable>
  )
}
