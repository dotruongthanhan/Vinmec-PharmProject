import { CircleCheck, CircleHelp, MinusCircle, OctagonAlert } from 'lucide-react'
import { cn } from '@/lib/cn'
import type { SixFactorItem, SixFactorStatus } from '@/lib/orderDetail'

export interface SixFactorStripProps {
  factors: readonly SixFactorItem[]
  onSelectFactor: (factor: SixFactorItem) => void
}

const FACTOR_TILE_CLASSES: Record<SixFactorStatus, string> = {
  co_van_de: 'border-danger-line bg-danger-bg/70 text-danger-fg hover:bg-danger-bg',
  dat: 'border-success-line bg-success-bg/70 text-success-fg hover:bg-success-bg',
  thieu_du_lieu: 'border-missing-line bg-missing-bg/70 text-missing-fg hover:bg-missing-bg',
  chua_co_luat: 'border-line bg-surface-muted/60 text-fg-subtle hover:bg-surface-muted',
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
      return <MinusCircle className="size-3.5 shrink-0" strokeWidth={1.75} aria-hidden="true" />
  }
}

/** Dải sáu yếu tố thẩm định trên một hàng; bấm từng ô để cuộn tới nhận định tương ứng. */
export function SixFactorStrip({ factors, onSelectFactor }: SixFactorStripProps) {
  return (
    <div
      className="factor-strip grid grid-cols-2 gap-2"
      role="group"
      aria-label="Sáu yếu tố thẩm định"
    >
      {factors.map((factor) => {
        const clickable = factor.firstFindingId !== null
        return (
          <button
            key={factor.index}
            type="button"
            disabled={!clickable}
            onClick={() => onSelectFactor(factor)}
            className={cn(
              'flex flex-col items-start gap-1 rounded-sm border px-2.5 py-2 text-left transition-colors duration-120',
              clickable ? 'cursor-pointer' : 'cursor-default opacity-85',
              FACTOR_TILE_CLASSES[factor.status],
            )}
          >
            <div className="flex w-full items-center justify-between gap-1.5">
              <span className="font-mono text-2xs font-medium tabular-nums">
                {factor.index}
              </span>
              <span className="inline-flex items-center gap-1 text-2xs font-medium">
                <FactorIcon status={factor.status} />
                <span>{factor.statusLabel}</span>
              </span>
            </div>
            <span className="min-h-8 text-xs font-medium text-fg">{factor.title}</span>
          </button>
        )
      })}
    </div>
  )
}
