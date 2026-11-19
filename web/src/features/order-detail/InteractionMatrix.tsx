import { useMemo, useState } from 'react'
import type { BangYLenh, MaTranTuongTac, NhanDinh } from '@/api/types'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/cn'
import { INTERACTION_LEVEL_META, buildInteractionMatrix } from '@/lib/detailTables'
import type { InteractionLevel, InteractionPair } from '@/lib/detailTables'

const LEVEL_ORDER: readonly InteractionLevel[] = [
  'nghiem_trong',
  'can_luu_y',
  'thieu_du_lieu',
  'khong_phat_hien',
  'khong_ap_dung',
  'chua_kiem',
]

const LEVEL_CHIP: Record<InteractionLevel, string> = {
  nghiem_trong: 'bg-danger-solid text-on-primary',
  can_luu_y: 'bg-warning-solid text-on-primary',
  thieu_du_lieu: 'bg-missing-solid text-on-primary',
  khong_phat_hien: 'bg-success-solid text-on-primary',
  khong_ap_dung: 'border border-line-strong bg-surface-muted text-fg-muted',
  chua_kiem: 'border border-dashed border-line-strong bg-surface-muted text-fg-subtle',
}

function LevelChip({ level, className }: { level: InteractionLevel; className?: string }) {
  return (
    <span
      className={cn(
        'inline-flex size-7 shrink-0 items-center justify-center rounded-sm text-sm font-bold',
        LEVEL_CHIP[level],
        className,
      )}
      aria-hidden="true"
    >
      {INTERACTION_LEVEL_META[level].code}
    </span>
  )
}

export interface InteractionMatrixProps {
  choDuyet: BangYLenh
  dangDung: BangYLenh | null
  nhanDinh: {
    can_chu_y: readonly NhanDinh[]
    dat: readonly NhanDinh[]
    yeu_to_chua_kiem: readonly string[]
  }
  onOpenFinding: (findingId: string) => void
  maTranTuongTac?: MaTranTuongTac | null
}

/**
 * Bảng tương tác thuốc theo bố cục dược sĩ quen dùng: cột trái là danh sách thuốc của y lệnh,
 * bên phải là chú giải mức độ, ma trận từng cặp và danh sách cặp có ghi nhận.
 */
export function InteractionMatrix({
  choDuyet,
  dangDung,
  nhanDinh,
  onOpenFinding,
  maTranTuongTac,
}: InteractionMatrixProps) {
  const data = useMemo(
    () => buildInteractionMatrix(choDuyet, dangDung, nhanDinh, maTranTuongTac),
    [choDuyet, dangDung, nhanDinh, maTranTuongTac],
  )
  const [focus, setFocus] = useState<number | null>(null)
  const activeFocus = focus !== null && focus < data.drugs.length ? focus : null

  const pairAt = (row: number, col: number): InteractionPair | undefined =>
    data.pairs.find(
      (pair) => (pair.a === row && pair.b === col) || (pair.a === col && pair.b === row),
    )

  const visiblePairs = data.pairs.filter(
    (pair) => activeFocus === null || pair.a === activeFocus || pair.b === activeFocus,
  )
  const flagged = visiblePairs.filter(
    (pair) => pair.findingId !== null || ['nghiem_trong', 'can_luu_y', 'thieu_du_lieu'].includes(pair.level),
  )
  const allNotApplicable = visiblePairs.length > 0 && visiblePairs.every((pair) => pair.level === 'khong_ap_dung')
  const hasMatrix = data.drugs.length >= 2

  return (
    <TooltipProvider>
    <div className="grid grid-cols-1 overflow-hidden rounded-md border border-line bg-surface @3xl:grid-cols-[minmax(200px,260px)_minmax(0,1fr)]">
      {/* Cột trái: danh sách thuốc */}
      <div className="flex flex-col border-b border-line bg-surface-muted/60 @3xl:border-b-0 @3xl:border-r">
        <div className="border-b border-line px-4 py-2.5 text-xs font-semibold tracking-wide text-fg-muted">
          THUỐC TRONG Y LỆNH ({data.drugs.length})
        </div>
        <ul className="flex flex-col">
          {data.drugs.map((drug, idx) => {
            const selected = activeFocus === idx
            return (
              <li key={drug.key} className="border-b border-line last:border-b-0">
                <button
                  type="button"
                  aria-pressed={selected}
                  onClick={() => setFocus(selected ? null : idx)}
                  className={cn(
                    'flex w-full cursor-pointer items-center gap-2.5 px-4 py-2.5 text-left text-sm transition-colors duration-120 hover:bg-surface-hover',
                    selected && 'bg-primary-soft',
                  )}
                >
                  <span className="flex size-5 shrink-0 items-center justify-center rounded-full border border-line-strong text-2xs font-semibold text-fg-muted tabular-nums">
                    {idx + 1}
                  </span>
                  <span className="min-w-0">
                    <span className={cn('block font-medium', selected ? 'text-primary' : 'text-fg')}>
                      {drug.name}
                    </span>
                    <span className="block text-2xs text-fg-subtle">
                      {drug.group === 'cho_duyet' ? 'Y lệnh chờ duyệt' : 'Thuốc đang dùng'}
                    </span>
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
        <p className="mt-auto px-4 py-3 text-2xs leading-relaxed text-fg-subtle">
          Bấm tên một thuốc để chỉ xem các cặp có thuốc đó.
        </p>
      </div>

      {/* Cột phải: chú giải, ma trận, kết quả */}
      <div className="flex min-w-0 flex-col gap-4 p-4">
        <ul className="grid grid-cols-2 gap-px overflow-hidden rounded-sm border border-line bg-line @2xl:grid-cols-3 @6xl:grid-cols-5">
          {LEVEL_ORDER.map((level) => (
            <li key={level} className="flex items-center gap-2 bg-surface px-2.5 py-1.5">
              <LevelChip level={level} className="size-6 text-xs" />
              <span className="min-w-0">
                <span className="block text-xs font-medium text-fg">
                  {INTERACTION_LEVEL_META[level].label}
                </span>
                <span className="block text-2xs leading-4 text-fg-subtle">
                  {INTERACTION_LEVEL_META[level].hint}
                </span>
              </span>
            </li>
          ))}
        </ul>

        {hasMatrix ? (
          <div className="overflow-x-auto">
            <table className="border-separate border-spacing-1 text-sm">
              <thead>
                <tr>
                  <th scope="col" className="sr-only">
                    Thuốc
                  </th>
                  {data.drugs.map((drug, idx) => (
                    <th
                      key={drug.key}
                      scope="col"
                      title={drug.name}
                      className={cn(
                        'w-12 pb-1 text-center text-xs font-semibold tabular-nums',
                        activeFocus === idx ? 'text-primary' : 'text-fg-muted',
                      )}
                    >
                      {idx + 1}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.drugs.map((rowDrug, row) => (
                  <tr key={rowDrug.key}>
                    <th
                      scope="row"
                      className={cn(
                        'max-w-64 truncate pr-3 text-left text-sm font-medium whitespace-nowrap',
                        activeFocus === row ? 'text-primary' : 'text-fg',
                      )}
                    >
                      <span className="mr-2 text-xs text-fg-subtle tabular-nums">{row + 1}</span>
                      {rowDrug.name}
                    </th>
                    {data.drugs.map((colDrug, col) => {
                      if (row === col) {
                        return (
                          <td key={colDrug.key} className="rounded-sm bg-surface-muted" aria-hidden="true" />
                        )
                      }
                      const pair = pairAt(row, col)
                      const level = pair?.level ?? 'chua_kiem'
                      const dimmed = activeFocus !== null && activeFocus !== row && activeFocus !== col
                      const label = [
                        `${rowDrug.name} và ${colDrug.name}: ${INTERACTION_LEVEL_META[level].label}`,
                        pair?.reason, pair?.summary,
                      ].filter(Boolean).join('. ')
                      return (
                        <td key={colDrug.key} className={cn('text-center', dimmed && 'opacity-30')}>
                          <Tooltip>
                          <TooltipTrigger asChild>
                          {pair?.findingId ? (
                            <button
                              type="button"
                              title={label}
                              aria-label={label}
                              onClick={() => onOpenFinding(pair.findingId!)}
                              className="cursor-pointer rounded-sm"
                            >
                              <LevelChip level={level} className="size-10 text-base" />
                            </button>
                          ) : (
                            <span title={label} role="img" aria-label={label} tabIndex={0} className="inline-flex rounded-sm">
                              <LevelChip level={level} className="size-10 text-base" />
                            </span>
                          )}
                          </TooltipTrigger>
                          <TooltipContent>{label}</TooltipContent>
                          </Tooltip>
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        {/* Hộp kết quả */}
        {!hasMatrix ? (
          <p className="rounded-sm border border-line px-4 py-3 text-center text-sm text-fg-muted">
            Y lệnh này chỉ có một thuốc nên không có cặp nào để đối chiếu tương tác.
          </p>
        ) : data.untested ? (
          <p className="rounded-sm border border-dashed border-line-strong px-4 py-3 text-center text-sm text-fg-muted">
            Bộ luật chưa kiểm tương tác thuốc cho ca này. Các ô{' '}
            <span className="font-semibold text-fg">Chưa kiểm</span> không có nghĩa là không có
            tương tác.
          </p>
        ) : allNotApplicable ? (
          <p className="rounded-sm border border-line bg-surface-muted px-4 py-3 text-center text-sm text-fg-muted">
            Không có cặp áp dụng để sàng lọc tương tác. Xem lý do tại từng ô.
          </p>
        ) : flagged.length === 0 ? (
          <p className="rounded-sm border border-success-line bg-success-bg/50 px-4 py-3 text-center text-sm font-semibold text-success-fg">
            Không ghi nhận tương tác ở mức cần lưu ý trở lên
            {activeFocus !== null ? ` với ${data.drugs[activeFocus].name}` : ''}.
          </p>
        ) : (
          <ul className="flex flex-col divide-y divide-line rounded-sm border border-line">
            {flagged.map((pair) => (
              <li key={`${pair.a}-${pair.b}`}>
                <div
                  className="flex w-full items-start gap-3 px-3 py-2.5 text-left"
                >
                  <LevelChip level={pair.level} />
                  <span className="min-w-0">
                    <span className="block text-sm font-semibold text-fg">
                      {data.drugs[pair.a].name} + {data.drugs[pair.b].name}
                    </span>
                    <span className="block text-sm text-fg-muted">{pair.finding?.nhan_xet ?? pair.summary ?? pair.reason}</span>
                    {pair.findingId ? (
                      <button type="button" className="mt-1 cursor-pointer text-sm text-primary underline"
                        onClick={() => onOpenFinding(pair.findingId!)}>Mở nhận định</button>
                    ) : null}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}

        {data.foods.length > 0 ? (
          <div className="text-sm text-fg-muted">
            <p className="font-semibold text-fg">Tương tác thuốc – thức ăn</p>
            <ul className="mt-1 flex flex-col gap-1">
              {data.foods.map((food, index) => (
                <li key={`${food.chi_tiet_y_lenh_id}-${food.hoat_chat}-${food.thuc_an}-${index}`}>
                  <details>
                    <summary className="cursor-pointer">
                      {food.hoat_chat} × {food.thuc_an} — {
                        food.muc === 'thong_tin' ? 'Thông tin' : food.muc === 'chua_ro' ? 'Chưa rõ' : INTERACTION_LEVEL_META[food.muc].label
                      }
                    </summary>
                    {food.mo_ta ? <p className="mt-1">{food.mo_ta}</p> : null}
                    {food.xu_tri ? <p className="mt-1">{food.xu_tri}</p> : null}
                  </details>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {data.source ? <p className="text-2xs leading-relaxed text-fg-subtle">{data.source} · {data.note}</p> : null}
        <p className="text-2xs leading-relaxed text-fg-subtle">
          Kết quả sàng lọc tham khảo. Quyết định dùng thuốc dựa trên đánh giá độc lập của dược sĩ và
          thông tin sản phẩm hiện hành.
        </p>
      </div>
    </div>
    </TooltipProvider>
  )
}
