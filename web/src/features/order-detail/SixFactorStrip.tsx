import { CircleCheck, CircleHelp, MinusCircle, OctagonAlert } from 'lucide-react'
import { cn } from '@/lib/cn'
import type { SixFactorItem, SixFactorStatus } from '@/lib/orderDetail'

export interface SixFactorStripProps {
  factors: readonly SixFactorItem[]
  onSelectFactor: (factor: SixFactorItem) => void
}

const FACTOR_TILE_CLASSES: Record<SixFactorStatus, string> = {
  co_van_de: 'border-danger-line bg-danger-bg/60 text-danger-fg hover:bg-danger-bg',
  dat: 'border-success-line/80 bg-success-bg/50 text-success-fg hover:bg-success-bg',
  thieu_du_lieu: 'border-missing-line bg-missing-bg/60 text-missing-fg hover:bg-missing-bg',
  chua_co_luat: 'border-line/70 bg-transparent text-fg-subtle',
}

function FactorIcon({ status }: { status: SixFactorStatus }) {
  switch (status) {
    case 'co_van_de':
      return <OctagonAlert className="size-3.5 shrink-0" strokeWidth={1.75} aria-hidden="true" />
    case 'dat':
      return <CircleCheck className="size-3.5 shrink-0" strokeWidth={1.75} aria-hidden="true" />
    case 'thieu_du_lieu':
      return <CircleHelp className="size-3.5 shrink-0" strokeWidth={1.75} aria-hidden="true" />
    case 'chua_co_luat':
      return <MinusCircle className="size-3.5 shrink-0 opacity-65" strokeWidth={1.75} aria-hidden="true" />
  }
}

/** Dải bảy yếu tố thẩm định gọn phẳng; bấm từng ô có luật để cuộn tới nhận định tương ứng. */
export function SixFactorStrip({ factors, onSelectFactor }: SixFactorStripProps) {
  return (
    <div
      className="factor-strip grid grid-cols-2 gap-1.5"
      role="group"
      aria-label="Bảy yếu tố thẩm định"
    >
      {factors.map((factor) => {
        const clickable = factor.firstFindingId !== null
        const isUntested = factor.status === 'chua_co_luat'
        return (
          <button
            key={factor.index}
            type="button"
            disabled={!clickable}
            onClick={() => onSelectFactor(factor)}
            className={cn(
              'flex flex-col items-start gap-1 rounded-sm border px-2.5 py-2 text-left transition-colors duration-120',
              clickable ? 'cursor-pointer' : 'cursor-default',
              isUntested ? 'opacity-75' : undefined,
              FACTOR_TILE_CLASSES[factor.status],
            )}
          >
            <div className="flex w-full items-center justify-between gap-1">
              <span className="font-mono text-2xs font-medium tabular-nums opacity-75">
                {factor.index}
              </span>
              <span className="inline-flex items-center gap-1 text-2xs font-medium whitespace-nowrap">
                <FactorIcon status={factor.status} />
                <span>{factor.statusLabel}</span>
              </span>
            </div>
            <span
              className={cn(
                'text-xs leading-snug',
                isUntested ? 'font-normal text-fg-subtle' : 'font-medium text-fg',
              )}
            >
              {factor.title}
            </span>
          </button>
        )
      })}
    </div>
  )
}
