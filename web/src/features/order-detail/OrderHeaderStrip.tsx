import {
  ArrowDown,
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
} from 'lucide-react'
import { createElement } from 'react'
import type { ChiSo, DinhDanhCa, TomTat } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { RecordId } from '@/components/ui/record-id'
import { cn } from '@/lib/cn'
import { parseLeadingSymbolLabel, parseTrendValue } from '@/lib/displayFormat'
import { iconOfAllergy, toneOfAllergy } from '@/lib/severity'
import type { EvidenceTarget } from '@/lib/uiTypes'

export interface OrderHeaderStripProps {
  orderCode: string
  dinhDanh: DinhDanhCa
  tomTat: TomTat
  chiSo: readonly ChiSo[]
  canPrev: boolean
  canNext: boolean
  onBackToList: () => void
  onPrevOrder: () => void
  onNextOrder: () => void
  onOpenEvidence: (target: EvidenceTarget, trigger: HTMLButtonElement) => void
}

const METRIC_SHORT_LABELS: Record<string, string> = {
  cockcroft_gault: 'CrCl',
  egfr_ckd_epi_2021: 'eGFR',
  bmi: 'BMI',
  bsa_mosteller: 'BSA',
}

/** Dải người bệnh dính trên cùng khi xem chi tiết y lệnh: hành chính, dị ứng, chẩn đoán chính và 4 chỉ số. */
export function OrderHeaderStrip({
  orderCode,
  dinhDanh,
  tomTat,
  chiSo,
  canPrev,
  canNext,
  onBackToList,
  onPrevOrder,
  onNextOrder,
  onOpenEvidence,
}: OrderHeaderStripProps) {
  const allergyTone = toneOfAllergy(dinhDanh.di_ung_ma)
  const allergyIconEl = createElement(iconOfAllergy(dinhDanh.di_ung_ma), {
    className: 'size-3.5',
    strokeWidth: 1.75,
  })
  const allergyText = parseLeadingSymbolLabel(dinhDanh.di_ung_text).text
  const allergyVariant = dinhDanh.di_ung_ma === 'khong_di_ung_da_hoi' ? 'outline' : 'soft'

  const primaryDiagnosis = tomTat.chan_doan[0] ?? null

  return (
    <section
      aria-label="Thông tin người bệnh và chỉ số lâm sàng"
      className="order-header sticky top-0 z-20 shrink-0 border-b border-line bg-surface px-3 py-2.5 flex flex-col gap-2"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-2 gap-y-1">
          <Button
            variant="ghost"
            size="sm"
            iconLeft={<ArrowLeft className="size-3.5" strokeWidth={1.75} />}
            onClick={onBackToList}
            className="-ml-2"
          >
            Danh sách
          </Button>
          <span className="text-fg-disabled" aria-hidden="true">
            |
          </span>
          <span className="whitespace-nowrap font-mono text-sm font-semibold text-fg">{orderCode}</span>
          <span className="text-fg-disabled" aria-hidden="true">
            ·
          </span>
          <span className="text-sm text-fg-muted">{dinhDanh.gioi_tuoi}</span>
          <span className="text-fg-disabled" aria-hidden="true">
            ·
          </span>
          <span className="font-mono text-sm text-fg-muted tabular-nums">
            {dinhDanh.can_nang}
          </span>
          <span className="text-fg-disabled" aria-hidden="true">
            ·
          </span>
          <span className="text-sm text-fg-muted">{dinhDanh.khoa_loai}</span>

        </div>

        <div className="flex items-center gap-1 shrink-0">
          <Button
            variant="secondary"
            size="sm"
            disabled={!canPrev}
            iconLeft={<ChevronLeft className="size-3.5" strokeWidth={1.75} />}
            onClick={onPrevOrder}
            aria-label="Y lệnh trước"
            title="Y lệnh trước"
          >
            <span className="order-nav-label">Y lệnh trước</span>
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={!canNext}
            onClick={onNextOrder}
            className="gap-1"
            aria-label="Y lệnh sau"
            title="Y lệnh sau"
          >
            <span className="order-nav-label">Y lệnh sau</span>
            <ChevronRight className="size-3.5" strokeWidth={1.75} aria-hidden="true" />
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1.5">
        <div className="flex flex-wrap items-center gap-1.5 text-xs text-fg-muted min-w-0">
          <Badge tone={allergyTone} variant={allergyVariant} icon={allergyIconEl}
            className={cn('whitespace-normal text-left', dinhDanh.di_ung_ma === 'co_di_ung' && 'font-semibold', dinhDanh.di_ung_ma === 'chua_co_thong_tin' && 'border-dashed font-semibold')}>
            {allergyText}
          </Badge>
          {primaryDiagnosis ? (
            <>
              <span className="text-fg-subtle">{primaryDiagnosis.loai_nhan}:</span>
              <span className="font-medium text-fg">{primaryDiagnosis.noi_dung}</span>
              {primaryDiagnosis.ma_icd10 ? <RecordId id={primaryDiagnosis.ma_icd10} /> : null}
            </>
          ) : (
            <span className="text-fg-subtle">Chưa ghi nhận chẩn đoán chính</span>
          )}
          {tomTat.co_dia.length > 0 ? (
            <span className="text-fg-subtle">· {tomTat.co_dia.join(', ')}</span>
          ) : null}
        </div>

        <div
          className="flex flex-wrap items-center gap-1.5 font-mono text-xs tabular-nums"
          aria-label="Bốn chỉ số lâm sàng"
        >
          {chiSo.map((metric) => {
            const shortName = METRIC_SHORT_LABELS[metric.cong_thuc] ?? metric.nhan
            const isCrclAbnormal =
              metric.cong_thuc === 'cockcroft_gault' &&
              dinhDanh.crcl_bat_thuong &&
              metric.gia_tri_text !== '—'
            const isMissing = metric.thieu.length > 0 || metric.gia_tri_text === '—'
            const parsedVal = parseTrendValue(metric.gia_tri_text)

            return (
              <button
                key={metric.cong_thuc}
                type="button"
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
                title={
                  isMissing && metric.thieu.length > 0
                    ? `Thiếu: ${metric.thieu.join(', ')}`
                    : `Bấm để xem phép tính ${metric.nhan}`
                }
                className={cn(
                  'inline-flex cursor-pointer items-center gap-1 rounded-sm border px-2 py-0.5 transition-colors duration-120',
                  isCrclAbnormal
                    ? 'border-danger-line bg-danger-bg text-danger-fg hover:bg-danger-bg/80'
                    : isMissing
                      ? 'border-missing-line bg-missing-bg text-missing-fg hover:bg-missing-bg/80'
                      : 'border-line bg-surface-muted/70 text-fg hover:border-line-strong hover:bg-surface-muted',
                )}
              >
                <span className="text-fg-subtle">{shortName}</span>
                <span className="font-semibold">{parsedVal.text}</span>
                {metric.don_vi && metric.gia_tri_text !== '—' ? (
                  <span className="text-2xs opacity-80">{metric.don_vi}</span>
                ) : null}
                {isCrclAbnormal ? (
                  <ArrowDown className="size-3 shrink-0" strokeWidth={1.75} aria-hidden="true" />
                ) : null}
                {isMissing ? (
                  <CircleHelp className="size-3 shrink-0" strokeWidth={1.75} aria-hidden="true" />
                ) : null}
              </button>
            )
          })}
        </div>
      </div>
    </section>
  )
}
