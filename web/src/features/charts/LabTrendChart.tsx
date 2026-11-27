import { X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { ChiTietXetNghiemDong } from '@/api/types'
import { Button } from '@/components/ui/button'
import { buildLabTrendCharts, buildSingleLabTrendChart } from '@/lib/labChart'
import type { LabTrendChartModel } from '@/lib/labChart'

export interface LabTrendChartProps {
  xetNghiem: readonly ChiTietXetNghiemDong[]
  orderTimeText?: string | null
}

function TrendChartCard({
  chart,
  title,
  plotRef,
  onClose,
}: {
  chart: LabTrendChartModel
  title?: string
  plotRef?: (el: HTMLDivElement | null) => void
  onClose?: () => void
}) {
  return (
    <div className="rounded-md border border-line bg-surface p-3 flex flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm font-semibold text-fg">
          {title ?? chart.ten}{' '}
          {chart.donVi ? (
            <span className="font-normal text-xs text-fg-subtle">({chart.donVi})</span>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-3 text-2xs text-fg-subtle">
          {chart.referenceBand ? (
            <span className="inline-flex items-center gap-1">
              <span
                className="inline-block size-2.5 rounded-xs bg-success-bg border border-success-line"
                aria-hidden="true"
              />
              <span>Tham chiếu ({chart.referenceBand.label})</span>
            </span>
          ) : null}
          <span className="inline-flex items-center gap-1">
            <span
              className="inline-block size-2 rounded-full bg-danger-solid"
              aria-hidden="true"
            />
            <span>Ngoài ngưỡng</span>
          </span>
          {onClose ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={onClose}
              aria-label="Đóng đồ thị diễn biến xét nghiệm"
              className="h-6 px-2 text-xs"
            >
              <X className="size-3.5" aria-hidden="true" />
              <span>Đóng</span>
            </Button>
          ) : null}
        </div>
      </div>

      <div ref={plotRef} className="min-w-0 w-full">
        <svg
          viewBox={`0 0 ${chart.width} ${chart.height}`}
          role="img"
          aria-label={chart.summaryText}
          className="h-auto w-full overflow-visible"
        >
          <title>{chart.summaryText}</title>

          {/* Vùng tô nhạt khoảng tham chiếu */}
          {chart.referenceBand ? (
            <rect
              x={chart.plotLeft}
              y={chart.referenceBand.yTop}
              width={chart.plotRight - chart.plotLeft}
              height={Math.max(1, chart.referenceBand.yBottom - chart.referenceBand.yTop)}
              fill="var(--color-success-bg)"
              opacity={0.75}
            />
          ) : null}

          {/* Đường lưới ngang và nhãn trục Y */}
          {chart.yTicks.map((tick, idx) => (
            <g key={`ytick-${idx}`}>
              <line
                x1={chart.plotLeft}
                y1={tick.y}
                x2={chart.plotRight}
                y2={tick.y}
                stroke="var(--color-line)"
                strokeWidth={1}
              />
              <text
                x={chart.plotLeft - 8}
                y={tick.y + 3.5}
                textAnchor="end"
                fontSize="12"
                fill="var(--color-fg-subtle)"
                className="font-mono tabular-nums"
              >
                {tick.label}
              </text>
            </g>
          ))}

          {/* Vạch dọc đánh dấu thời điểm kê y lệnh */}
          {chart.orderMarker ? (
            <g>
              <line
                x1={chart.orderMarker.x}
                y1={chart.plotTop}
                x2={chart.orderMarker.x}
                y2={chart.plotBottom}
                stroke="var(--color-fg-muted)"
                strokeWidth={1}
                strokeDasharray="3 3"
              />
              <text
                x={chart.orderMarker.x + (chart.orderMarker.x > chart.width / 2 ? -4 : 4)}
                y={chart.plotTop - 8}
                textAnchor={chart.orderMarker.x > chart.width / 2 ? 'end' : 'start'}
                fontSize="12"
                fill="var(--color-fg-muted)"
              >
                Kê y lệnh
              </text>
            </g>
          ) : null}

          {/* Đường nối các điểm thực đo (khi có >= 2 điểm) */}
          {chart.polylinePoints ? (
            <polyline
              fill="none"
              stroke="var(--color-primary)"
              strokeWidth={2}
              points={chart.polylinePoints}
            />
          ) : null}

          {/* Các điểm kết quả */}
          {chart.points.map((pt, idx) => {
            const pointColor = pt.ngoaiNguong ? 'var(--color-danger-solid)' : 'var(--color-primary)'
            const showValueLabel = pt.isSelected || pt.ngoaiNguong
            return (
              <g key={`pt-${idx}`}>
                {pt.isSelected ? (
                  <circle
                    cx={pt.x}
                    cy={pt.y}
                    r={9.5}
                    fill={pointColor}
                    opacity={0.22}
                  />
                ) : null}
                <circle
                  cx={pt.x}
                  cy={pt.y}
                  r={pt.isSelected ? 6.5 : pt.ngoaiNguong ? 4.5 : 3.5}
                  fill={pointColor}
                  stroke={pt.isSelected ? 'var(--color-fg)' : 'var(--color-surface)'}
                  strokeWidth={pt.isSelected ? 2 : 1.5}
                  data-selected={pt.isSelected ? 'true' : undefined}
                />
                {showValueLabel ? (
                  <text
                    x={pt.x}
                    y={Math.max(chart.plotTop + 10, pt.y - (pt.isSelected ? 12 : 9))}
                    textAnchor="middle"
                    fontSize={pt.isSelected ? '13' : '12'}
                    fontWeight={pt.isSelected ? '700' : '600'}
                    fill={pt.ngoaiNguong ? 'var(--color-danger-fg)' : 'var(--color-fg)'}
                    className="font-mono tabular-nums"
                  >
                    {pt.valueText}
                  </text>
                ) : null}
              </g>
            )
          })}

          {/* Nhãn trục thời gian */}
          {chart.xTicks.map((tick, idx) => (
            <text
              key={`xtick-${idx}`}
              x={tick.x}
              y={chart.plotBottom + 18}
              textAnchor={idx === 0 && chart.xTicks.length > 1 ? 'start' : chart.xTicks.length === 1 ? 'middle' : 'end'}
              fontSize="12"
              fill="var(--color-fg-subtle)"
              className="font-mono tabular-nums"
            >
              {tick.label}
            </text>
          ))}
        </svg>
      </div>

      {chart.points.length === 1 ? (
        <p className="text-xs text-fg-subtle">Chỉ số này hiện mới có 1 lần đo.</p>
      ) : null}
    </div>
  )
}

/** Vẽ biểu đồ đường bằng SVG cho các chỉ số xét nghiệm có từ 2 kết quả trở lên. */
export function LabTrendChart({ xetNghiem, orderTimeText }: LabTrendChartProps) {
  const plotRef = useRef<HTMLDivElement | null>(null)
  const [plotWidth, setPlotWidth] = useState(560)
  const charts = useMemo(
    () => buildLabTrendCharts(xetNghiem, orderTimeText, { width: plotWidth, height: 208 }),
    [xetNghiem, orderTimeText, plotWidth],
  )
  const hasCharts = charts.length > 0

  useEffect(() => {
    const container = plotRef.current
    if (!container) return
    const observer = new ResizeObserver(([entry]) => {
      if (entry.contentRect.width > 0) setPlotWidth(entry.contentRect.width)
    })
    observer.observe(container)
    return () => observer.disconnect()
  }, [hasCharts])

  if (charts.length === 0) {
    return null
  }

  return (
    <div className="mb-4 grid min-w-0 grid-cols-1 gap-3">
      {charts.map((chart, chartIndex) => (
        <TrendChartCard
          key={chart.ten}
          chart={chart}
          plotRef={
            chartIndex === 0
              ? (el) => {
                  plotRef.current = el
                }
              : undefined
          }
        />
      ))}
    </div>
  )
}

export interface SingleLabTrendChartProps {
  xetNghiem: readonly ChiTietXetNghiemDong[]
  metricName: string
  orderTimeText?: string | null
  selectedMatch?: { thoiDiemText: string; giaTriText: string } | null
  onClose?: () => void
}

/** Vẽ đồ thị diễn biến cho 1 chỉ số xét nghiệm được chọn từ bảng phẳng, in đậm điểm đo đang chọn. */
export function SingleLabTrendChart({
  xetNghiem,
  metricName,
  orderTimeText,
  selectedMatch,
  onClose,
}: SingleLabTrendChartProps) {
  const plotRef = useRef<HTMLDivElement | null>(null)
  const [plotWidth, setPlotWidth] = useState(560)
  const chart = useMemo(
    () =>
      buildSingleLabTrendChart(
        xetNghiem,
        metricName,
        orderTimeText,
        { width: plotWidth, height: 208 },
        selectedMatch,
      ),
    [xetNghiem, metricName, orderTimeText, plotWidth, selectedMatch],
  )

  const hasSingleChart = Boolean(chart)
  useEffect(() => {
    const container = plotRef.current
    if (!container) return
    const observer = new ResizeObserver(([entry]) => {
      if (entry.contentRect.width > 0) setPlotWidth(entry.contentRect.width)
    })
    observer.observe(container)
    return () => observer.disconnect()
  }, [hasSingleChart])

  if (!chart) {
    return null
  }

  return (
    <TrendChartCard
      chart={chart}
      title={`Diễn biến ${chart.ten} của bệnh nhân`}
      plotRef={(el) => {
        plotRef.current = el
      }}
      onClose={onClose}
    />
  )
}
