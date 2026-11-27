import type { ChiTietXetNghiemDong } from '../api/types.ts'

export interface ReferenceRange {
  min: number | null
  max: number | null
  label: string
}

export interface ChartPoint {
  x: number
  y: number
  value: number
  valueText: string
  timestampMs: number
  timestampLabel: string
  ngoaiNguong: boolean
  isSelected?: boolean
}

export interface LabTrendChartModel {
  ten: string
  donVi: string
  width: number
  height: number
  plotLeft: number
  plotRight: number
  plotTop: number
  plotBottom: number
  yMin: number
  yMax: number
  yTicks: { y: number; label: string }[]
  xTicks: { x: number; label: string }[]
  points: ChartPoint[]
  polylinePoints: string
  referenceBand: { yTop: number; yBottom: number; label: string } | null
  orderMarker: { x: number; label: string } | null
  summaryText: string
}

/** Phân tích chuỗi số kiểu Việt, bỏ ký hiệu tăng/giảm nếu có. */
export function parseVietnameseNumber(raw: string): number | null {
  const cleaned = raw
    .replace(/[\u25B2\u25BC]/g, '')
    .replace(/\s+/g, '')
    .replace(',', '.')
    .trim()
  if (!cleaned) {
    return null
  }
  const parsed = Number(cleaned)
  return Number.isFinite(parsed) ? parsed : null
}

/** Chuyển chuỗi thời điểm ISO hoặc DD/MM/YYYY HH:MM sang mili-giây UTC ổn định. */
export function parseChartTimestamp(raw: string | null | undefined): number | null {
  if (!raw) {
    return null
  }
  const trimmed = raw.trim()
  if (!trimmed) {
    return null
  }
  if (trimmed.includes('T')) {
    const ms = Date.parse(trimmed)
    return Number.isFinite(ms) ? ms : null
  }
  const dmyMatch = /^(\d{2})\/(\d{2})\/(\d{4})\s+(\d{2}):(\d{2})$/.exec(trimmed)
  if (dmyMatch) {
    const [, dd, mm, yyyy, hh, min] = dmyMatch
    // Xem như mốc +07:00 để trục thời gian nhất quán giữa mọi môi trường.
    return Date.UTC(Number(yyyy), Number(mm) - 1, Number(dd), Number(hh) - 7, Number(min))
  }
  const hmDmyMatch = /^(\d{2}):(\d{2})\s*·\s*(\d{2})\/(\d{2})\/(\d{4})$/.exec(trimmed)
  if (hmDmyMatch) {
    const [, hh, min, dd, mm, yyyy] = hmDmyMatch
    return Date.UTC(Number(yyyy), Number(mm) - 1, Number(dd), Number(hh) - 7, Number(min))
  }
  return null
}

/** Định dạng ngắn gọn mốc thời gian theo múi giờ +07:00 cho trục X biểu đồ. */
export function formatShortChartTime(timestampMs: number): string {
  const vnDate = new Date(timestampMs + 7 * 60 * 60 * 1000)
  const dd = String(vnDate.getUTCDate()).padStart(2, '0')
  const mo = String(vnDate.getUTCMonth() + 1).padStart(2, '0')
  const hh = String(vnDate.getUTCHours()).padStart(2, '0')
  const min = String(vnDate.getUTCMinutes()).padStart(2, '0')
  return `${dd}/${mo} ${hh}:${min}`
}

/** Định dạng số bằng dấu phẩy thập phân để gắn nhãn trục Y và điểm dữ liệu. */
export function formatChartNumber(value: number): string {
  const rounded = Math.round(value * 10) / 10
  return rounded.toFixed(1).replace(/\.0$/, '').replace('.', ',')
}

/** Phân tích chuỗi khoảng tham chiếu ("44,0 – 80,0", "≤ 5,0", "≥ 3,5"). */
export function parseReferenceRange(raw: string): ReferenceRange | null {
  const trimmed = raw.trim()
  if (!trimmed) {
    return null
  }

  const betweenMatch = /^([0-9.,]+)\s*[–—-]\s*([0-9.,]+)$/.exec(trimmed)
  if (betweenMatch) {
    const min = parseVietnameseNumber(betweenMatch[1])
    const max = parseVietnameseNumber(betweenMatch[2])
    if (min !== null && max !== null && min <= max) {
      return { min, max, label: trimmed }
    }
  }

  const upperMatch = /^(?:≤|<=|<)\s*([0-9.,]+)$/.exec(trimmed)
  if (upperMatch) {
    const max = parseVietnameseNumber(upperMatch[1])
    if (max !== null) {
      return { min: null, max, label: trimmed }
    }
  }

  const lowerMatch = /^(?:≥|>=|>)\s*([0-9.,]+)$/.exec(trimmed)
  if (lowerMatch) {
    const min = parseVietnameseNumber(lowerMatch[1])
    if (min !== null) {
      return { min, max: null, label: trimmed }
    }
  }

  return null
}

/** Kiểm tra giá trị có nằm ngoài khoảng tham chiếu hay không. */
export function isOutsideReferenceRange(
  value: number,
  range: ReferenceRange | null,
  explicitFlag: boolean,
): boolean {
  if (explicitFlag) {
    return true
  }
  if (!range) {
    return false
  }
  if (range.min !== null && value < range.min) {
    return true
  }
  if (range.max !== null && value > range.max) {
    return true
  }
  return false
}

/**
 * Dựng mô hình toạ độ SVG cho các chỉ số xét nghiệm có từ 2 kết quả trở lên.
 * Chỉ số chỉ có 1 kết quả sẽ bị bỏ qua. Không ngoại suy ngoài các điểm thực đo.
 */
export function buildLabTrendCharts(
  labs: readonly ChiTietXetNghiemDong[],
  orderTimeText?: string | null,
  dimensions: { width?: number; height?: number } = {},
): LabTrendChartModel[] {
  const width = dimensions.width ?? 560
  const height = dimensions.height ?? 190
  const plotLeft = 52
  const plotRight = width - 24
  const plotTop = 22
  const plotBottom = height - 30
  const plotWidth = Math.max(1, plotRight - plotLeft)
  const plotHeight = Math.max(1, plotBottom - plotTop)

  const grouped = new Map<string, ChiTietXetNghiemDong[]>()
  for (const row of labs) {
    const list = grouped.get(row.ten) ?? []
    list.push(row)
    grouped.set(row.ten, list)
  }

  const orderTimeMs = parseChartTimestamp(orderTimeText)
  const models: LabTrendChartModel[] = []

  for (const [ten, rows] of grouped.entries()) {
    const parsedRows = rows
      .map((row) => {
        const value = parseVietnameseNumber(row.gia_tri_text)
        const timestampMs = parseChartTimestamp(row.thoi_diem_text)
        if (value === null || timestampMs === null) {
          return null
        }
        return { row, value, timestampMs }
      })
      .filter((item): item is NonNullable<typeof item> => item !== null)
      .sort((a, b) => a.timestampMs - b.timestampMs)

    if (parsedRows.length < 2) {
      continue
    }

    const latestRow = parsedRows[parsedRows.length - 1].row
    const donVi = latestRow.don_vi.replace(/\bumol\/[lL]\b/g, 'µmol/L')
    const range = parseReferenceRange(latestRow.khoang_tham_chieu)

    const yValues = parsedRows.map((p) => p.value)
    if (range?.min !== null && range?.min !== undefined) {
      yValues.push(range.min)
    }
    if (range?.max !== null && range?.max !== undefined) {
      yValues.push(range.max)
    }

    const rawYMin = Math.min(...yValues)
    const rawYMax = Math.max(...yValues)
    const ySpanRaw = rawYMax - rawYMin
    const yPad = ySpanRaw === 0 ? Math.max(Math.abs(rawYMin) * 0.15, 1) : ySpanRaw * 0.14
    const yMin = rawYMin - yPad
    const yMax = rawYMax + yPad
    const ySpan = yMax - yMin

    const xValues = parsedRows.map((p) => p.timestampMs)
    if (orderTimeMs !== null) {
      xValues.push(orderTimeMs)
    }
    const rawXMin = Math.min(...xValues)
    const rawXMax = Math.max(...xValues)
    const xSpanRaw = rawXMax - rawXMin
    const xPad = xSpanRaw === 0 ? 60 * 60 * 1000 : xSpanRaw * 0.08
    const xMin = rawXMin - xPad
    const xMax = rawXMax + xPad
    const xSpan = xMax - xMin

    const mapX = (ms: number): number => plotLeft + ((ms - xMin) / xSpan) * plotWidth
    const mapY = (val: number): number => plotBottom - ((val - yMin) / ySpan) * plotHeight

    const points: ChartPoint[] = parsedRows.map(({ row, value, timestampMs }) => ({
      x: Number(mapX(timestampMs).toFixed(2)),
      y: Number(mapY(value).toFixed(2)),
      value,
      valueText: formatChartNumber(value),
      timestampMs,
      timestampLabel: formatShortChartTime(timestampMs),
      ngoaiNguong: isOutsideReferenceRange(value, range, row.ngoai_nguong),
    }))

    const polylinePoints = points.map((pt) => `${pt.x},${pt.y}`).join(' ')

    const yMid = (yMin + yMax) / 2
    const yTicks = [yMin, yMid, yMax].map((val) => ({
      y: Number(mapY(val).toFixed(2)),
      label: formatChartNumber(val),
    }))

    const firstPt = points[0]
    const lastPt = points[points.length - 1]
    const xTicks =
      firstPt.timestampMs === lastPt.timestampMs
        ? [{ x: firstPt.x, label: firstPt.timestampLabel }]
        : [
            { x: firstPt.x, label: firstPt.timestampLabel },
            { x: lastPt.x, label: lastPt.timestampLabel },
          ]

    let referenceBand: LabTrendChartModel['referenceBand'] = null
    if (range) {
      const bandTopVal = range.max ?? yMax
      const bandBottomVal = range.min ?? yMin
      const yTop = Number(Math.max(plotTop, mapY(bandTopVal)).toFixed(2))
      const yBottom = Number(Math.min(plotBottom, mapY(bandBottomVal)).toFixed(2))
      if (yBottom > yTop) {
        referenceBand = { yTop, yBottom, label: range.label }
      }
    }

    const orderMarker =
      orderTimeMs !== null
        ? {
            x: Number(mapX(orderTimeMs).toFixed(2)),
            label: `Kê y lệnh (${formatShortChartTime(orderTimeMs)})`,
          }
        : null

    const outCount = points.filter((p) => p.ngoaiNguong).length
    const summaryText = `Biểu đồ ${ten} gồm ${points.length} kết quả: từ ${firstPt.valueText} ${donVi} (${firstPt.timestampLabel}) đến ${lastPt.valueText} ${donVi} (${lastPt.timestampLabel})${outCount > 0 ? `, có ${outCount} điểm ngoài ngưỡng` : ''}.`

    models.push({
      ten,
      donVi,
      width,
      height,
      plotLeft,
      plotRight,
      plotTop,
      plotBottom,
      yMin,
      yMax,
      yTicks,
      xTicks,
      points,
      polylinePoints,
      referenceBand,
      orderMarker,
      summaryText,
    })
  }

  return models
}

/**
 * Dựng mô hình toạ độ SVG cho ĐÚNG MỘT chỉ số xét nghiệm (hỗ trợ cả khi chỉ có 1 lần đo),
 * đồng thời đánh dấu điểm đang được chọn từ bảng phẳng.
 */
export function buildSingleLabTrendChart(
  labs: readonly ChiTietXetNghiemDong[],
  metricName: string,
  orderTimeText?: string | null,
  dimensions: { width?: number; height?: number } = {},
  selectedMatch?: { thoiDiemText: string; giaTriText: string } | null,
): LabTrendChartModel | null {
  const matching = labs.filter((row) => row.ten === metricName)
  if (matching.length === 0) {
    return null
  }

  const width = dimensions.width ?? 560
  const height = dimensions.height ?? 208
  const plotLeft = 52
  const plotRight = width - 24
  const plotTop = 22
  const plotBottom = height - 30
  const plotWidth = Math.max(1, plotRight - plotLeft)
  const plotHeight = Math.max(1, plotBottom - plotTop)

  const parsedRows = matching
    .map((row) => {
      const value = parseVietnameseNumber(row.gia_tri_text)
      const timestampMs = parseChartTimestamp(row.thoi_diem_text)
      if (value === null || timestampMs === null) {
        return null
      }
      return { row, value, timestampMs }
    })
    .filter((item): item is NonNullable<typeof item> => item !== null)
    .sort((a, b) => a.timestampMs - b.timestampMs)

  if (parsedRows.length === 0) {
    return null
  }

  const orderTimeMs = parseChartTimestamp(orderTimeText)
  const latestRow = parsedRows[parsedRows.length - 1].row
  const donVi = latestRow.don_vi.replace(/\bumol\/[lL]\b/g, 'µmol/L')
  const range = parseReferenceRange(latestRow.khoang_tham_chieu)

  const yValues = parsedRows.map((p) => p.value)
  if (range?.min !== null && range?.min !== undefined) yValues.push(range.min)
  if (range?.max !== null && range?.max !== undefined) yValues.push(range.max)

  const rawYMin = Math.min(...yValues)
  const rawYMax = Math.max(...yValues)
  const ySpanRaw = rawYMax - rawYMin
  const yPad = ySpanRaw === 0 ? Math.max(Math.abs(rawYMin) * 0.15, 1) : ySpanRaw * 0.14
  const yMin = rawYMin - yPad
  const yMax = rawYMax + yPad
  const ySpan = yMax - yMin

  const xValues = parsedRows.map((p) => p.timestampMs)
  if (orderTimeMs !== null) xValues.push(orderTimeMs)
  const rawXMin = Math.min(...xValues)
  const rawXMax = Math.max(...xValues)
  const xSpanRaw = rawXMax - rawXMin
  const xPad = xSpanRaw === 0 ? 60 * 60 * 1000 : xSpanRaw * 0.08
  const xMin = rawXMin - xPad
  const xMax = rawXMax + xPad
  const xSpan = xMax - xMin

  const mapX = (ms: number): number => plotLeft + ((ms - xMin) / xSpan) * plotWidth
  const mapY = (val: number): number => plotBottom - ((val - yMin) / ySpan) * plotHeight

  let matchedOnce = false
  const points: ChartPoint[] = parsedRows.map(({ row, value, timestampMs }) => {
    const isHit =
      !matchedOnce &&
      Boolean(selectedMatch) &&
      row.thoi_diem_text === selectedMatch!.thoiDiemText &&
      row.gia_tri_text === selectedMatch!.giaTriText
    if (isHit) {
      matchedOnce = true
    }
    return {
      x: Number(mapX(timestampMs).toFixed(2)),
      y: Number(mapY(value).toFixed(2)),
      value,
      valueText: formatChartNumber(value),
      timestampMs,
      timestampLabel: formatShortChartTime(timestampMs),
      ngoaiNguong: isOutsideReferenceRange(value, range, row.ngoai_nguong),
      isSelected: isHit,
    }
  })

  const polylinePoints = points.length >= 2 ? points.map((pt) => `${pt.x},${pt.y}`).join(' ') : ''
  const yMid = (yMin + yMax) / 2
  const yTicks = [yMin, yMid, yMax].map((val) => ({
    y: Number(mapY(val).toFixed(2)),
    label: formatChartNumber(val),
  }))

  const firstPt = points[0]
  const lastPt = points[points.length - 1]
  const xTicks =
    firstPt.timestampMs === lastPt.timestampMs
      ? [{ x: firstPt.x, label: firstPt.timestampLabel }]
      : [
          { x: firstPt.x, label: firstPt.timestampLabel },
          { x: lastPt.x, label: lastPt.timestampLabel },
        ]

  let referenceBand: LabTrendChartModel['referenceBand'] = null
  if (range) {
    const bandTopVal = range.max ?? yMax
    const bandBottomVal = range.min ?? yMin
    const yTop = Number(Math.max(plotTop, mapY(bandTopVal)).toFixed(2))
    const yBottom = Number(Math.min(plotBottom, mapY(bandBottomVal)).toFixed(2))
    if (yBottom > yTop) {
      referenceBand = { yTop, yBottom, label: range.label }
    }
  }

  const orderMarker =
    orderTimeMs !== null
      ? {
          x: Number(mapX(orderTimeMs).toFixed(2)),
          label: `Kê y lệnh (${formatShortChartTime(orderTimeMs)})`,
        }
      : null

  const outCount = points.filter((p) => p.ngoaiNguong).length
  const summaryText = `Biểu đồ ${metricName} gồm ${points.length} kết quả: từ ${firstPt.valueText} ${donVi} (${firstPt.timestampLabel}) đến ${lastPt.valueText} ${donVi} (${lastPt.timestampLabel})${outCount > 0 ? `, có ${outCount} điểm ngoài ngưỡng` : ''}.`

  return {
    ten: metricName,
    donVi,
    width,
    height,
    plotLeft,
    plotRight,
    plotTop,
    plotBottom,
    yMin,
    yMax,
    yTicks,
    xTicks,
    points,
    polylinePoints,
    referenceBand,
    orderMarker,
    summaryText,
  }
}
