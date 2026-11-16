import { ArrowDown, ArrowUp } from 'lucide-react'
import type { ChiSo, TomTat } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { RecordId } from '@/components/ui/record-id'
import { parseTrendValue } from '@/lib/displayFormat'
import type { EvidenceTarget } from '@/lib/uiTypes'
import { MetricCard } from './MetricCard'

export interface SummarySectionProps {
  caId: string
  tomTat: TomTat
  chiSo: ChiSo[]
  crclBatThuong?: boolean
  onViewAllNotes: () => void
  onOpenEvidence: (target: EvidenceTarget, trigger: HTMLButtonElement) => void
}

/** Thành phần B: 3 thẻ tóm tắt ngang và hàng 4 chỉ số lâm sàng. */
export function SummarySection({
  caId,
  tomTat,
  chiSo,
  crclBatThuong = false,
  onViewAllNotes,
  onOpenEvidence,
}: SummarySectionProps) {
  const abnormalLabs = tomTat.bat_thuong.slice(0, 5)

  return (
    <section aria-label="Tóm tắt ca bệnh" className="flex flex-col gap-2.5">
      <h2 className="sr-only">Tóm tắt ca bệnh</h2>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
        <Card className="p-3 flex flex-col gap-1.5 min-w-0">
          <div className="flex items-center justify-between gap-2 min-h-7">
            <h3 className="text-2xs uppercase tracking-[0.04em] font-medium text-fg-subtle">
              Chẩn đoán và cơ địa
            </h3>
          </div>

          {tomTat.chan_doan.length > 0 ? (
            <ul className="flex flex-col gap-1.5">
              {tomTat.chan_doan.map((cd, idx) => {
                const isPrimary = cd.loai_nhan.trim().toLowerCase() === 'chính'
                return (
                  <li
                    key={`${cd.noi_dung}-${idx}`}
                    className="flex flex-wrap items-baseline gap-1.5"
                  >
                    <Badge
                      tone="neutral"
                      variant={isPrimary ? 'soft' : 'outline'}
                      className="shrink-0"
                    >
                      {cd.loai_nhan}
                    </Badge>
                    <span
                      className={
                        isPrimary
                          ? 'text-sm font-medium text-fg'
                          : 'text-sm text-fg-muted'
                      }
                    >
                      {cd.noi_dung}
                    </span>
                    {cd.ma_icd10 ? <RecordId id={cd.ma_icd10} /> : null}
                  </li>
                )
              })}
            </ul>
          ) : (
            <p className="text-sm text-fg-subtle">Chưa có chẩn đoán</p>
          )}

          {tomTat.co_dia.length > 0 ? (
            <div className="flex flex-col gap-1 border-t border-line pt-1.5">
              <span className="text-2xs uppercase tracking-[0.04em] font-medium text-fg-subtle">
                Cơ địa đặc biệt
              </span>
              <ul className="flex flex-col gap-0.5 text-sm text-fg-muted">
                {tomTat.co_dia.map((item, idx) => (
                  <li key={`${item}-${idx}`}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}

          <p className="text-xs text-fg-subtle tabular-nums mt-auto pt-1">
            Vào viện: {tomTat.vao_vien_text}
            {tomTat.nam_vien_text ? ` · Nằm viện: ${tomTat.nam_vien_text}` : ''}
          </p>
        </Card>

        <Card className="p-3 flex flex-col gap-1.5 min-w-0">
          <div className="flex items-center justify-between gap-2 min-h-7">
            <h3 className="text-2xs uppercase tracking-[0.04em] font-medium text-fg-subtle">
              Diễn biến mới nhất
            </h3>
            <Button variant="ghost" size="sm" onClick={onViewAllNotes}>
              Xem tất cả
            </Button>
          </div>

          {tomTat.dien_bien_moi_nhat ? (
            <div className="flex flex-col gap-1 min-w-0">
              <p className="text-xs text-fg-subtle tabular-nums">
                {tomTat.dien_bien_moi_nhat.thoi_diem_text} ·{' '}
                {tomTat.dien_bien_moi_nhat.loai_nhan}
              </p>
              <p className="text-sm text-fg whitespace-pre-wrap line-clamp-4">
                {tomTat.dien_bien_moi_nhat.noi_dung}
              </p>
            </div>
          ) : (
            <p className="text-sm text-fg-subtle">Chưa có ghi nhận diễn biến</p>
          )}
        </Card>

        <Card className="p-3 flex flex-col gap-1.5 min-w-0">
          <div className="flex items-center justify-between gap-2 min-h-7">
            <h3 className="text-2xs uppercase tracking-[0.04em] font-medium text-fg-subtle">
              Bất thường gần nhất
            </h3>
          </div>

          {abnormalLabs.length > 0 ? (
            <ul className="flex flex-col gap-2">
              {abnormalLabs.map((item, idx) => {
                const parsedValue = parseTrendValue(item.gia_tri_text)
                const parsedDir = parseTrendValue(item.huong)
                const direction = parsedDir.direction ?? parsedValue.direction

                return (
                  <li key={`${item.ten}-${idx}`} className="flex flex-col gap-0.5 min-w-0">
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="text-sm text-fg truncate">{item.ten}</span>
                      <span className="inline-flex items-center gap-1 text-sm font-semibold text-fg tabular-nums shrink-0">
                        <span>
                          {parsedValue.text}
                          {item.don_vi ? (
                            <span className="font-normal text-xs text-fg-subtle ml-1">
                              {item.don_vi}
                            </span>
                          ) : null}
                        </span>
                        {direction === 'up' ? (
                          <ArrowUp
                            className="size-3.5 text-danger-fg inline shrink-0"
                            strokeWidth={1.75}
                            aria-label="Tăng"
                          />
                        ) : direction === 'down' ? (
                          <ArrowDown
                            className="size-3.5 text-danger-fg inline shrink-0"
                            strokeWidth={1.75}
                            aria-label="Giảm"
                          />
                        ) : null}
                      </span>
                    </div>
                    <span className="text-xs text-fg-subtle tabular-nums">
                      {item.so_voi_truoc
                        ? `${item.so_voi_truoc} · ${item.thoi_diem_text}`
                        : item.thoi_diem_text}
                    </span>
                  </li>
                )
              })}
            </ul>
          ) : null}

          {tomTat.bat_thuong_ghi_chu ? (
            <p className="text-xs text-fg-muted">{tomTat.bat_thuong_ghi_chu}</p>
          ) : null}
        </Card>
      </div>

      <div
        className="grid grid-cols-2 lg:grid-cols-4 gap-2.5"
        aria-label="Bốn chỉ số lâm sàng"
      >
        {chiSo.map((metric) => (
          <MetricCard
            key={`${caId}-${metric.cong_thuc}`}
            caId={caId}
            metric={metric}
            abnormal={
              metric.cong_thuc === 'cockcroft_gault' &&
              crclBatThuong &&
              metric.gia_tri_text !== '—'
            }
            onOpenEvidence={onOpenEvidence}
          />
        ))}
      </div>
    </section>
  )
}
