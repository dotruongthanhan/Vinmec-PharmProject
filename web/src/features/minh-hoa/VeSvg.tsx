import { useId, useState } from 'react'
import type {
  HinhDangDiem,
  HoaTietCot,
  KieuVien,
  MoHinhVe,
  PhanTuVe,
} from './dungMoHinh'

export interface VeSvgProps {
  moHinh: MoHinhVe
  className?: string
}

interface ThongTinDangChon {
  ma: string
  moTa: string
  nguon: readonly string[]
}

function netVienSvg(kieu: KieuVien): string | undefined {
  if (kieu === 'dut') return '4 2'
  if (kieu === 'cham') return '2 2'
  return undefined
}

function VeDauDiem({
  hinhDang,
  cx,
  cy,
  r,
  mau,
  laGiaDinh,
}: {
  hinhDang: HinhDangDiem
  cx: number
  cy: number
  r: number
  mau: string
  laGiaDinh: boolean
}) {
  if (hinhDang === 'vuong') {
    return (
      <rect
        x={cx - r}
        y={cy - r}
        width={r * 2}
        height={r * 2}
        fill={mau}
        stroke="var(--color-surface)"
        strokeWidth={1.5}
      />
    )
  }
  if (hinhDang === 'tam_giac') {
    const h = r * 1.25
    const points = `${cx},${cy - h} ${cx - h},${cy + r} ${cx + h},${cy + r}`
    return (
      <polygon
        points={points}
        fill={mau}
        stroke="var(--color-surface)"
        strokeWidth={1.5}
      />
    )
  }
  if (hinhDang === 'thoi') {
    const d = r * 1.25
    const points = `${cx},${cy - d} ${cx + d},${cy} ${cx},${cy + d} ${cx - d},${cy}`
    return (
      <g>
        {laGiaDinh ? (
          <circle
            cx={cx}
            cy={cy}
            r={r + 5}
            fill="none"
            stroke={mau}
            strokeWidth={1.5}
            strokeDasharray="3 2"
          />
        ) : null}
        <polygon
          points={points}
          fill={mau}
          stroke="var(--color-surface)"
          strokeWidth={1.5}
        />
      </g>
    )
  }
  if (hinhDang === 'dau_cong') {
    return (
      <g stroke={mau} strokeWidth={2} strokeLinecap="round">
        <line x1={cx - r} y1={cy} x2={cx + r} y2={cy} />
        <line x1={cx} y1={cy - r} x2={cx} y2={cy + r} />
      </g>
    )
  }
  if (hinhDang === 'vong') {
    return (
      <circle
        cx={cx}
        cy={cy}
        r={r}
        fill="var(--color-surface)"
        stroke={mau}
        strokeWidth={2}
      />
    )
  }
  return (
    <circle
      cx={cx}
      cy={cy}
      r={r}
      fill={mau}
      stroke="var(--color-surface)"
      strokeWidth={1.75}
    />
  )
}

function layUrlHoaTiet(prefix: string, hoaTiet: HoaTietCot): string | null {
  if (hoaTiet === 'soc_cheo') return `url(#${prefix}-soc)`
  if (hoaTiet === 'cham') return `url(#${prefix}-cham)`
  if (hoaTiet === 'ngang') return `url(#${prefix}-ngang)`
  return null
}

function tachToiDaHaiDong(text: string, maxChars: number): string[] {
  const cleaned = text.trim().replace(/\s+/g, ' ')
  if (!cleaned || maxChars < 6) return []
  if (cleaned.length <= maxChars) return [cleaned]

  const words = cleaned.split(' ')
  let line1 = ''
  let idx = 0
  while (idx < words.length) {
    const candidate = line1 ? `${line1} ${words[idx]}` : words[idx]
    if (candidate.length <= maxChars) {
      line1 = candidate
      idx += 1
    } else {
      break
    }
  }
  if (!line1) {
    line1 = words[0].slice(0, maxChars)
    const restFirst = words[0].slice(maxChars)
    const restWords = restFirst ? [restFirst, ...words.slice(1)] : words.slice(1)
    const rest = restWords.join(' ')
    if (!rest) return [line1]
    return [
      line1,
      rest.length <= maxChars ? rest : `${rest.slice(0, Math.max(1, maxChars - 1)).trimEnd()}…`,
    ]
  }

  const remaining = words.slice(idx).join(' ')
  if (!remaining) return [line1]
  if (remaining.length <= maxChars) return [line1, remaining]
  const cut = remaining.slice(0, Math.max(1, maxChars - 1)).trimEnd()
  return [line1, `${cut}…`]
}

/** Bộ vẽ JSX SVG chung cho mọi đặc tả ngữ pháp `mh-0`, hỗ trợ di chuột và tiêu điểm bàn phím. */
export function VeSvg({ moHinh, className = '' }: VeSvgProps) {
  const uid = useId().replace(/:/g, '')
  const [dangChon, setDangChon] = useState<ThongTinDangChon | null>(null)

  const laMaTran = moHinh.phanTu.some((p) => p.loai === 'o')
  const cacDai = moHinh.phanTu.filter((p) => p.loai === 'dai')
  const daiBottom = cacDai.length > 0 ? Math.max(...cacDai.map((d) => d.y + d.cao)) : null
  const { trai, phai, tren, duoi } = moHinh.vungVe

  const chonPhanTu = (pt: PhanTuVe) => {
    setDangChon({ ma: pt.ma, moTa: pt.moTa, nguon: pt.nguon })
  }

  const boChon = (ma: string) => {
    setDangChon((prev) => (prev?.ma === ma ? null : prev))
  }

  return (
    <div className={`flex min-w-0 w-full flex-col gap-2 ${className}`}>
      {moHinh.chuGiai.length > 0 ? (
        <ul className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-fg-muted">
          {moHinh.chuGiai.map((item) => (
            <li key={item.nhan} className="inline-flex items-center gap-1.5">
              {item.kyHieu ? (
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 20 20"
                  aria-hidden="true"
                  className="shrink-0"
                >
                  <rect
                    x="1"
                    y="1"
                    width="18"
                    height="18"
                    rx="4"
                    fill={item.mauNen ?? 'var(--color-surface-muted)'}
                    stroke={item.mau}
                    strokeWidth="1.4"
                    strokeDasharray={item.netVien ? netVienSvg(item.netVien) : undefined}
                  />
                  <text
                    x="10"
                    y="14"
                    textAnchor="middle"
                    fontSize="11"
                    fontWeight="700"
                    fill={item.mauChu ?? 'var(--color-fg)'}
                  >
                    {item.kyHieu}
                  </text>
                </svg>
              ) : (
                <svg width="20" height="12" viewBox="0 0 20 12" aria-hidden="true" className="shrink-0">
                  {item.coSoc !== undefined ? (
                    <>
                      <rect
                        x="1"
                        y="1"
                        width="18"
                        height="10"
                        rx="2"
                        fill={item.mauNen ?? item.mau}
                        stroke={item.mau}
                        strokeWidth="1.2"
                      />
                      {item.coSoc ? (
                        <line
                          x1="4"
                          y1="10"
                          x2="14"
                          y2="2"
                          stroke={item.mau}
                          strokeWidth="1.2"
                        />
                      ) : null}
                    </>
                  ) : (
                    <>
                      <line
                        x1="1"
                        y1="6"
                        x2="19"
                        y2="6"
                        stroke={item.mau}
                        strokeWidth="2"
                        strokeDasharray={item.netDut || undefined}
                      />
                      {item.hinhDang ? (
                        <VeDauDiem
                          hinhDang={item.hinhDang}
                          cx={10}
                          cy={6}
                          r={3}
                          mau={item.mau}
                          laGiaDinh={false}
                        />
                      ) : null}
                    </>
                  )}
                </svg>
              )}
              <span>{item.nhan}</span>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="min-w-0 w-full overflow-x-auto">
        <svg
          viewBox={`0 0 ${moHinh.rong} ${moHinh.cao}`}
          role="img"
          aria-label={`${moHinh.tieuDe}${moHinh.phuDe ? ` — ${moHinh.phuDe}` : ''}`}
          className="block h-auto w-full min-w-[280px]"
        >
          <title>{moHinh.tieuDe}</title>
          <defs>
            <pattern
              id={`${uid}-dai-soc`}
              width="8"
              height="8"
              patternUnits="userSpaceOnUse"
              patternTransform="rotate(45)"
            >
              <line
                x1="0"
                y1="0"
                x2="0"
                y2="8"
                stroke="var(--color-warning-line)"
                strokeWidth="1.5"
                opacity="0.55"
              />
            </pattern>
            <pattern
              id={`${uid}-soc`}
              width="6"
              height="6"
              patternUnits="userSpaceOnUse"
              patternTransform="rotate(45)"
            >
              <line
                x1="0"
                y1="0"
                x2="0"
                y2="6"
                stroke="var(--color-surface)"
                strokeWidth="1.5"
                opacity="0.45"
              />
            </pattern>
            <pattern id={`${uid}-cham`} width="6" height="6" patternUnits="userSpaceOnUse">
              <circle cx="3" cy="3" r="1" fill="var(--color-surface)" opacity="0.55" />
            </pattern>
            <pattern id={`${uid}-ngang`} width="6" height="5" patternUnits="userSpaceOnUse">
              <line
                x1="0"
                y1="2.5"
                x2="6"
                y2="2.5"
                stroke="var(--color-surface)"
                strokeWidth="1.2"
                opacity="0.45"
              />
            </pattern>
          </defs>

          {/* Lưới ngang và trục Y cho biểu đồ 2 chiều (không phải ma trận) */}
          {!laMaTran && moHinh.trucY ? (
            <g>
              {moHinh.trucY.vach.map((tick, idx) => (
                <g key={`yt-${idx}`}>
                  <line
                    x1={trai}
                    y1={tick.toaDo}
                    x2={phai}
                    y2={tick.toaDo}
                    stroke="var(--color-line)"
                    strokeWidth={1}
                  />
                  <text
                    x={trai - 8}
                    y={tick.toaDo + 3.5}
                    textAnchor="end"
                    fontSize="11"
                    fill="var(--color-fg-subtle)"
                    className="font-mono tabular-nums"
                  >
                    {tick.nhan}
                  </text>
                </g>
              ))}
              {moHinh.trucY.tieuDe ? (
                <text
                  x={12}
                  y={(tren + duoi) / 2}
                  textAnchor="middle"
                  fontSize="11"
                  fill="var(--color-fg-muted)"
                  transform={`rotate(-90 12 ${(tren + duoi) / 2})`}
                >
                  {moHinh.trucY.tieuDe}
                </text>
              ) : null}
            </g>
          ) : null}

          {/* Nhãn trục của ma trận */}
          {laMaTran && moHinh.trucX && moHinh.trucY ? (
            <g>
              {moHinh.trucX.vach.map((tick, idx) => (
                <text
                  key={`mx-${idx}`}
                  x={tick.toaDo}
                  y={tren - 10}
                  textAnchor="start"
                  fontSize="11"
                  fill="var(--color-fg-muted)"
                  transform={`rotate(-32 ${tick.toaDo} ${tren - 10})`}
                >
                  {tick.nhan}
                </text>
              ))}
              {moHinh.trucY.vach.map((tick, idx) => (
                <text
                  key={`my-${idx}`}
                  x={trai - 8}
                  y={tick.toaDo + 4}
                  textAnchor="end"
                  fontSize="11"
                  fill="var(--color-fg-muted)"
                >
                  {tick.nhan}
                </text>
              ))}
              {/* Ô đường chéo trung tính của ma trận */}
              {moHinh.trucX.vach.map((xt, idx) => {
                const yt = moHinh.trucY?.vach[idx]
                if (!yt) return null
                const step =
                  moHinh.trucX && moHinh.trucX.vach.length > 1
                    ? Math.abs(moHinh.trucX.vach[1].toaDo - moHinh.trucX.vach[0].toaDo)
                    : 32
                const size = Math.max(12, step - 4)
                return (
                  <rect
                    key={`diag-${idx}`}
                    x={xt.toaDo - size / 2}
                    y={yt.toaDo - size / 2}
                    width={size}
                    height={size}
                    rx={4}
                    fill="var(--color-surface-muted)"
                    stroke="var(--color-line)"
                    strokeWidth={1}
                  />
                )
              })}
            </g>
          ) : null}

          {/* Vẽ từng phần tử theo thứ tự lớp */}
          {moHinh.phanTu.map((pt) => {
            const active = dangChon?.ma === pt.ma

            if (pt.loai === 'dai') {
              const maxChars = Math.floor((pt.rong - 10) / 5.8)
              const dongNhan = pt.nhan && maxChars >= 8 ? tachToiDaHaiDong(pt.nhan, maxChars) : []
              const centerX = pt.x + pt.rong / 2
              return (
                <g
                  key={pt.ma}
                  tabIndex={0}
                  role="img"
                  aria-label={pt.moTa}
                  className="cursor-pointer outline-none"
                  onMouseEnter={() => chonPhanTu(pt)}
                  onMouseLeave={() => boChon(pt.ma)}
                  onFocus={() => chonPhanTu(pt)}
                  onBlur={() => boChon(pt.ma)}
                >
                  <title>{pt.moTa}</title>
                  <rect
                    x={pt.x}
                    y={pt.y}
                    width={pt.rong}
                    height={pt.cao}
                    rx={4}
                    fill={pt.mauNen}
                    stroke={active ? 'var(--color-primary)' : pt.mauVien}
                    strokeWidth={active ? 2 : 1}
                  />
                  {pt.coSoc ? (
                    <rect
                      x={pt.x}
                      y={pt.y}
                      width={pt.rong}
                      height={pt.cao}
                      rx={4}
                      fill={`url(#${uid}-dai-soc)`}
                      pointerEvents="none"
                    />
                  ) : null}
                  {pt.khoangChu && pt.rong >= 30 ? (
                    <text
                      x={centerX}
                      y={pt.y + 16}
                      textAnchor="middle"
                      fontSize="11"
                      fontWeight="600"
                      fill={pt.mauChu}
                      className="font-mono tabular-nums"
                      pointerEvents="none"
                    >
                      {pt.khoangChu}
                    </text>
                  ) : null}
                  {dongNhan.length > 0 ? (
                    <text
                      x={centerX}
                      y={dongNhan.length === 2 ? pt.y + pt.cao - 22 : pt.y + pt.cao - 12}
                      textAnchor="middle"
                      fontSize="10"
                      fill={pt.mauChu}
                      pointerEvents="none"
                    >
                      {dongNhan.map((line, idx) => (
                        <tspan key={`${pt.ma}-l-${idx}`} x={centerX} dy={idx === 0 ? 0 : 12.5}>
                          {line}
                        </tspan>
                      ))}
                    </text>
                  ) : null}
                </g>
              )
            }

            if (pt.loai === 'vung') {
              return (
                <path
                  key={pt.ma}
                  d={pt.path}
                  fill={pt.mau}
                  opacity={0.18}
                  aria-label={pt.moTa}
                />
              )
            }

            if (pt.loai === 'duong') {
              return (
                <polyline
                  key={pt.ma}
                  fill="none"
                  stroke={pt.mau}
                  strokeWidth={pt.doDay}
                  strokeDasharray={pt.netDut || undefined}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  points={pt.diemPath}
                />
              )
            }

            if (pt.loai === 'cot') {
              const patUrl = layUrlHoaTiet(uid, pt.hoaTiet)
              return (
                <g
                  key={pt.ma}
                  tabIndex={0}
                  role="img"
                  aria-label={pt.moTa}
                  className="cursor-pointer outline-none"
                  onMouseEnter={() => chonPhanTu(pt)}
                  onMouseLeave={() => boChon(pt.ma)}
                  onFocus={() => chonPhanTu(pt)}
                  onBlur={() => boChon(pt.ma)}
                >
                  <rect
                    x={pt.x}
                    y={pt.y}
                    width={pt.rong}
                    height={pt.cao}
                    rx={4}
                    fill={pt.mau}
                    stroke={active ? 'var(--color-fg)' : pt.mau}
                    strokeWidth={active ? 2 : 1}
                  />
                  {patUrl ? (
                    <rect
                      x={pt.x}
                      y={pt.y}
                      width={pt.rong}
                      height={pt.cao}
                      rx={4}
                      fill={patUrl}
                      pointerEvents="none"
                    />
                  ) : null}
                  <text
                    x={pt.x + pt.rong / 2}
                    y={Math.max(tren + 10, pt.y - 6)}
                    textAnchor="middle"
                    fontSize="11"
                    fontWeight="600"
                    fill="var(--color-fg)"
                    className="font-mono tabular-nums"
                    pointerEvents="none"
                  >
                    {pt.giaTriChu}
                  </text>
                </g>
              )
            }

            if (pt.loai === 'doan') {
              return (
                <g key={pt.ma} role="img" aria-label={pt.moTa}>
                  <title>{pt.moTa}</title>
                  <line x1={pt.x1} y1={pt.y} x2={pt.x2} y2={pt.y} stroke="var(--color-primary)" strokeWidth="4" strokeDasharray={pt.dangDung ? '6 3' : undefined} />
                  {pt.dangDung ? <path d={`M ${pt.x2 - 6} ${pt.y - 5} L ${pt.x2} ${pt.y} L ${pt.x2 - 6} ${pt.y + 5}`} fill="none" stroke="var(--color-primary)" strokeWidth="2" /> : null}
                </g>
              )
            }

            if (pt.loai === 'quy_tac') {
              return (
                <g
                  key={pt.ma}
                  tabIndex={0}
                  role="img"
                  aria-label={pt.moTa}
                  className="cursor-pointer outline-none"
                  onMouseEnter={() => chonPhanTu(pt)}
                  onMouseLeave={() => boChon(pt.ma)}
                  onFocus={() => chonPhanTu(pt)}
                  onBlur={() => boChon(pt.ma)}
                >
                  <title>{pt.moTa}</title>
                  <line
                    x1={pt.x1}
                    y1={pt.y1}
                    x2={pt.x2}
                    y2={pt.y2}
                    stroke={active ? 'var(--color-primary)' : 'var(--color-fg-muted)'}
                    strokeWidth={active ? 2 : 1.5}
                    strokeDasharray="4 3"
                  />
                  {pt.nhan ? (
                    <text
                      x={pt.huong === 'doc' ? Math.min(phai - 34, Math.max(trai + 34, pt.x1)) : phai - 4}
                      y={pt.huong === 'doc' ? Math.max(12, pt.y1 - 8) : pt.y1 - 6}
                      textAnchor={pt.huong === 'doc' ? 'middle' : 'end'}
                      fontSize="10"
                      fill="var(--color-fg-muted)"
                    >
                      {pt.nhan}
                    </text>
                  ) : null}
                </g>
              )
            }

            if (pt.loai === 'diem') {
              const showValue = !moHinh.trucY || active
              const diemDatDuoiDai = !moHinh.trucY ? daiBottom : null
              const nhanDiem =
                pt.laGiaDinh && pt.nhan ? `${pt.giaTriChu} · ${pt.nhan}` : pt.giaTriChu
              const nuaRongNhan = Math.max(24, Math.min(72, nhanDiem.length * 3.8))
              const labelX = Math.min(phai - nuaRongNhan, Math.max(trai + nuaRongNhan, pt.cx))
              const labelY =
                diemDatDuoiDai !== null
                  ? Math.min(duoi - 8, diemDatDuoiDai + 19)
                  : Math.max(12, pt.cy - pt.r - 8)
              return (
                <g
                  key={pt.ma}
                  tabIndex={0}
                  role="img"
                  aria-label={pt.moTa}
                  className="cursor-pointer outline-none"
                  onMouseEnter={() => chonPhanTu(pt)}
                  onMouseLeave={() => boChon(pt.ma)}
                  onFocus={() => chonPhanTu(pt)}
                  onBlur={() => boChon(pt.ma)}
                >
                  <title>{pt.moTa}</title>
                  <VeDauDiem
                    hinhDang={pt.hinhDang}
                    cx={pt.cx}
                    cy={pt.cy}
                    r={active ? pt.r + 1.5 : pt.r}
                    mau={pt.mau}
                    laGiaDinh={pt.laGiaDinh}
                  />
                  {showValue ? (
                    <>
                      {diemDatDuoiDai !== null ? (
                        <line
                          x1={pt.cx}
                          y1={diemDatDuoiDai}
                          x2={pt.cx}
                          y2={diemDatDuoiDai + 6}
                          stroke={pt.mau}
                          strokeWidth={1.5}
                          strokeDasharray={pt.laGiaDinh ? '2 2' : undefined}
                          pointerEvents="none"
                        />
                      ) : null}
                      <text
                        x={labelX}
                        y={labelY}
                        textAnchor="middle"
                        fontSize="11"
                        fontWeight="600"
                        fill={pt.laGiaDinh ? 'var(--color-offlabel-fg)' : 'var(--color-fg)'}
                        className="font-mono tabular-nums"
                        pointerEvents="none"
                      >
                        {nhanDiem}
                      </text>
                    </>
                  ) : null}
                </g>
              )
            }

            if (pt.loai === 'o') {
              const coChuLon = pt.cao >= 52
              return (
                <g
                  key={pt.ma}
                  tabIndex={0}
                  role="img"
                  aria-label={pt.moTa}
                  className="cursor-pointer outline-none"
                  onMouseEnter={() => chonPhanTu(pt)}
                  onMouseLeave={() => boChon(pt.ma)}
                  onFocus={() => chonPhanTu(pt)}
                  onBlur={() => boChon(pt.ma)}
                >
                  <title>{pt.moTa}</title>
                  <rect
                    x={pt.x}
                    y={pt.y}
                    width={pt.rong}
                    height={pt.cao}
                    rx={5}
                    fill={pt.mauNen}
                    stroke={active ? 'var(--color-fg)' : pt.mauVien}
                    strokeWidth={active ? 2.25 : 1.5}
                    strokeDasharray={netVienSvg(pt.netVien)}
                  />
                  <text
                    x={pt.x + pt.rong / 2}
                    y={pt.y + pt.cao / 2 + (coChuLon ? 5 : 4)}
                    textAnchor="middle"
                    fontSize={coChuLon ? '14' : '12'}
                    fontWeight="700"
                    fill={pt.mauChu}
                    pointerEvents="none"
                  >
                    {pt.kyHieu}
                  </text>
                </g>
              )
            }

            if (pt.loai === 'chu') {
              return (
                <text
                  key={pt.ma}
                  x={pt.x}
                  y={pt.y}
                  textAnchor="middle"
                  fontSize="11"
                  fill={pt.mau}
                >
                  {pt.noiDung}
                </text>
              )
            }

            return null
          })}

          {/* Trục X cho biểu đồ không phải ma trận */}
          {!laMaTran && moHinh.trucX ? (
            <g>
              <line
                x1={trai}
                y1={duoi}
                x2={phai}
                y2={duoi}
                stroke="var(--color-line-strong)"
                strokeWidth={1}
              />
              {moHinh.trucX.vach.map((tick, idx) => (
                <g key={`xt-${idx}`}>
                  <line
                    x1={tick.toaDo}
                    y1={duoi}
                    x2={tick.toaDo}
                    y2={duoi + 4}
                    stroke="var(--color-line-strong)"
                    strokeWidth={1}
                  />
                  <text
                    x={tick.toaDo}
                    y={duoi + 17}
                    textAnchor="middle"
                    fontSize="11"
                    fill="var(--color-fg-subtle)"
                    className="font-mono tabular-nums"
                  >
                    {tick.nhan}
                  </text>
                </g>
              ))}
              {moHinh.trucX.tieuDe ? (
                <text
                  x={(trai + phai) / 2}
                  y={moHinh.cao - 6}
                  textAnchor="middle"
                  fontSize="11"
                  fill="var(--color-fg-muted)"
                >
                  {moHinh.trucX.tieuDe}
                </text>
              ) : null}
            </g>
          ) : null}
        </svg>
      </div>

      {/* Dòng chi tiết khi di chuột hoặc focus bàn phím vào phần tử */}
      <div
        role="status"
        aria-live="polite"
        className="flex min-h-8 flex-wrap items-center justify-between gap-2 rounded-sm border border-line bg-surface-muted/60 px-3 py-1.5 text-xs text-fg-muted"
      >
        {dangChon ? (
          <>
            <span className="font-medium text-fg">{dangChon.moTa}</span>
            <span className="font-mono text-2xs text-fg-subtle">
              Nguồn: {dangChon.nguon.join(', ')}
            </span>
          </>
        ) : (
          <span className="text-fg-subtle">
            Di chuột hoặc dùng phím Tab vào từng phần tử trên hình để xem giá trị và căn cứ.
          </span>
        )}
      </div>
    </div>
  )
}
