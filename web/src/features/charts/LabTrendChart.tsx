import { useEffect, useMemo, useRef, useState } from 'react'
import type { ChiTietXetNghiemDong } from '@/api/types'
import { buildLabTrendCharts } from '@/lib/labChart'

export interface LabTrendChartProps {
  xetNghiem: readonly ChiTietXetNghiemDong[]
  orderTimeText?: string | null
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
        <div
          key={chart.ten}
          className="rounded-md border border-line bg-surface p-3 flex flex-col gap-2"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="text-sm font-semibold text-fg">
              {chart.ten}{' '}
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
            </div>
          </div>

          <div ref={chartIndex === 0 ? plotRef : undefined} className="min-w-0 w-full">
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

            {/* Đường nối các điểm thực đo (không ngoại suy) */}
            <polyline
              fill="none"
              stroke="var(--color-primary)"
              strokeWidth={2}
              points={chart.polylinePoints}
            />

            {/* Các điểm kết quả */}
            {chart.points.map((pt, idx) => (
              <g key={`pt-${idx}`}>
                <circle
                  cx={pt.x}
                  cy={pt.y}
                  r={pt.ngoaiNguong ? 4.5 : 3.5}
                  fill={pt.ngoaiNguong ? 'var(--color-danger-solid)' : 'var(--color-primary)'}
                  stroke="var(--color-surface)"
                  strokeWidth={1.5}
                />
                {pt.ngoaiNguong ? (
                  <text
                    x={pt.x}
                    y={Math.max(chart.plotTop + 10, pt.y - 9)}
                    textAnchor="middle"
                    fontSize="12"
                    fontWeight="600"
                    fill="var(--color-danger-fg)"
                    className="font-mono tabular-nums"
                  >
                    {pt.valueText}
                  </text>
                ) : null}
              </g>
            ))}

            {/* Nhãn trục thời gian */}
            {chart.xTicks.map((tick, idx) => (
              <text
                key={`xtick-${idx}`}
                x={tick.x}
                y={chart.plotBottom + 18}
                textAnchor={idx === 0 ? 'start' : 'end'}
                fontSize="12"
                fill="var(--color-fg-subtle)"
                className="font-mono tabular-nums"
              >
                {tick.label}
              </text>
            ))}
          </svg>
          </div>
        </div>
      ))}
    </div>
  )
}
