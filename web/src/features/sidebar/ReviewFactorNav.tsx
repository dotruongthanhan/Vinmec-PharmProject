import { CircleCheck, CircleHelp, MinusCircle, OctagonAlert } from 'lucide-react'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/cn'
import { SIX_FACTOR_DEFINITIONS, SIX_FACTOR_STATUS_LABELS } from '@/lib/orderDetail'
import type {
  FactorIndex,
  ReviewSectionId,
  SixFactorItem,
  SixFactorStatus,
} from '@/lib/orderDetail'

export interface ReviewFactorNavProps {
  selected: ReviewSectionId
  factors: readonly SixFactorItem[]
  attentionCountByFactor: Readonly<Record<FactorIndex, number>>
  severeByFactor: Readonly<Record<FactorIndex, boolean>>
  totalAttention: number
  hasAnySevere: boolean
  soLuatDaChay: number
  onSelect: (target: ReviewSectionId) => void
  collapsed?: boolean
}

interface NavItemData {
  id: ReviewSectionId
  index: FactorIndex | null
  title: string
  status: SixFactorStatus
  statusLabel: string
  count: number
  hasSevere: boolean
}

/** Bộ biểu tượng trạng thái dùng chung theo SixFactorStrip. */
export function FactorStatusIcon({
  status,
  className,
}: {
  status: SixFactorStatus
  className?: string
}) {
  switch (status) {
    case 'co_van_de':
      return <OctagonAlert className={cn('size-3.5 shrink-0', className)} strokeWidth={1.75} aria-hidden="true" />
    case 'dat':
      return <CircleCheck className={cn('size-3.5 shrink-0', className)} strokeWidth={1.75} aria-hidden="true" />
    case 'thieu_du_lieu':
      return <CircleHelp className={cn('size-3.5 shrink-0', className)} strokeWidth={1.75} aria-hidden="true" />
    case 'chua_co_luat':
      return <MinusCircle className={cn('size-3.5 shrink-0 opacity-65', className)} strokeWidth={1.75} aria-hidden="true" />
  }
}

function statusIconToneClass(status: SixFactorStatus, hasSevere: boolean): string {
  if (hasSevere) {
    return 'text-danger-solid'
  }
  switch (status) {
    case 'co_van_de':
      return 'text-warning-solid'
    case 'thieu_du_lieu':
      return 'text-missing-solid'
    case 'dat':
      return 'text-success-solid'
    case 'chua_co_luat':
      return 'text-ink-muted'
  }
}

function countBadgeToneClass(status: SixFactorStatus, hasSevere: boolean): string {
  if (hasSevere) {
    return 'border-danger-line bg-danger-bg text-danger-fg'
  }
  switch (status) {
    case 'co_van_de':
      return 'border-warning-line bg-warning-bg text-warning-fg'
    case 'thieu_du_lieu':
      return 'border-missing-line bg-missing-bg text-missing-fg'
    case 'dat':
      return 'border-success-line bg-success-bg text-success-fg'
    case 'chua_co_luat':
      return 'border-ink-line bg-ink-soft text-ink-fg'
  }
}

function itemSurfaceClass(item: NavItemData, isSelected: boolean): string {
  // Chỉ mục đang chọn có nền và viền; mức nghiêm trọng thể hiện qua biểu tượng và huy hiệu đỏ,
  // không tô khung, để không trông giống mục đang chọn.
  if (isSelected) {
    return 'bg-ink-soft font-semibold text-ink-fg ring-1 ring-inset ring-primary/60'
  }
  if (item.hasSevere) {
    return 'font-medium text-ink-fg hover:bg-ink-soft'
  }
  if (item.status === 'chua_co_luat') {
    return 'text-ink-muted/75 hover:bg-ink-soft hover:text-ink-fg'
  }
  return 'text-ink-muted hover:bg-ink-soft hover:text-ink-fg'
}

/** Điều hướng 8 mục của tab Thẩm định (Tổng quan và 7 yếu tố) đặt ở nửa dưới thanh bên. */
export function ReviewFactorNav({
  selected,
  factors,
  attentionCountByFactor,
  severeByFactor,
  totalAttention,
  hasAnySevere,
  soLuatDaChay,
  onSelect,
  collapsed = false,
}: ReviewFactorNavProps) {
  const factorByIndex = new Map(factors.map((f) => [f.index, f]))
  const orderedFactors: SixFactorItem[] = SIX_FACTOR_DEFINITIONS.map(
    (def) =>
      factorByIndex.get(def.index) ?? {
        index: def.index,
        title: def.title,
        status: 'chua_co_luat',
        statusLabel: SIX_FACTOR_STATUS_LABELS.chua_co_luat,
        firstFindingId: null,
        inPassedOnly: false,
      },
  )

  const overviewStatus: SixFactorStatus = orderedFactors.some((f) => f.status === 'co_van_de')
    ? 'co_van_de'
    : orderedFactors.some((f) => f.status === 'thieu_du_lieu')
      ? 'thieu_du_lieu'
      : orderedFactors.some((f) => f.status === 'dat')
        ? 'dat'
        : 'chua_co_luat'

  const items: NavItemData[] = [
    {
      id: 'tong_quan',
      index: null,
      title: 'Tổng quan',
      status: overviewStatus,
      statusLabel: SIX_FACTOR_STATUS_LABELS[overviewStatus],
      count: totalAttention,
      hasSevere: hasAnySevere,
    },
    ...orderedFactors.map((factor) => ({
      id: factor.index,
      index: factor.index,
      title: factor.title,
      status: factor.status,
      statusLabel: factor.statusLabel,
      count: attentionCountByFactor[factor.index] ?? 0,
      hasSevere: Boolean(severeByFactor[factor.index]),
    })),
  ]

  return (
    <nav
      aria-label="Mục thẩm định"
      className={cn('flex flex-col', collapsed ? 'items-center gap-1' : 'gap-1')}
    >
      {items.map((item) => {
        const isSelected = selected === item.id
        const iconTone = statusIconToneClass(item.status, item.hasSevere)

        if (collapsed) {
          const prefix = item.index !== null ? `${item.index}. ` : ''
          const countSuffix = item.count > 0 ? ` (${item.count} cần chú ý)` : ''
          const ariaLabel = `${prefix}${item.title} · ${item.statusLabel}${countSuffix}`
          const tooltipText = `${prefix}${item.title}${item.count > 0 ? ` (${item.count})` : ''}`

          return (
            <Tooltip key={String(item.id)}>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  aria-label={ariaLabel}
                  aria-current={isSelected ? 'page' : undefined}
                  onClick={() => onSelect(item.id)}
                  className={cn(
                    'flex h-8 w-full cursor-pointer items-center justify-center gap-0.5 rounded-sm transition-colors duration-120 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary',
                    itemSurfaceClass(item, isSelected),
                  )}
                >
                  {item.index !== null ? (
                    <>
                      <span className="font-mono text-2xs font-semibold tabular-nums">
                        {item.index}
                      </span>
                      <FactorStatusIcon status={item.status} className={cn('size-3', iconTone)} />
                    </>
                  ) : (
                    <FactorStatusIcon status={item.status} className={iconTone} />
                  )}
                </button>
              </TooltipTrigger>
              <TooltipContent side="right">{tooltipText}</TooltipContent>
            </Tooltip>
          )
        }

        return (
          <button
            key={String(item.id)}
            type="button"
            aria-current={isSelected ? 'page' : undefined}
            onClick={() => onSelect(item.id)}
            className={cn(
              'flex w-full min-w-0 cursor-pointer items-start gap-2 rounded-sm px-2.5 py-1.5 text-left text-sm transition-colors duration-120 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary',
              itemSurfaceClass(item, isSelected),
            )}
          >
            {item.index !== null ? (
              <span className="mt-0.5 w-3.5 shrink-0 font-mono text-xs text-ink-muted tabular-nums">
                {item.index}
              </span>
            ) : null}
            <span className="mt-0.5 shrink-0">
              <FactorStatusIcon status={item.status} className={iconTone} />
            </span>
            <span className="min-w-0 flex-1 leading-snug break-words">
              {item.title}
              <span className="sr-only"> ({item.statusLabel})</span>
            </span>
            {item.count > 0 ? (
              <span
                className={cn(
                  'mt-0.5 ml-auto inline-flex min-w-5 shrink-0 items-center justify-center rounded-full border px-1.5 py-0.5 font-mono text-2xs font-semibold leading-none tabular-nums',
                  countBadgeToneClass(item.status, item.hasSevere),
                )}
              >
                {item.count}
              </span>
            ) : null}
          </button>
        )
      })}

      <p
        className={
          collapsed
            ? 'sr-only'
            : 'px-2.5 pt-1.5 text-2xs text-ink-muted tabular-nums'
        }
      >
        {soLuatDaChay} luật đã chạy
      </p>
    </nav>
  )
}
