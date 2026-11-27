import {
  Minus,
  Plus,
  RotateCcw,
  Table2,
} from 'lucide-react'
import { useDeferredValue, useEffect, useId, useMemo, useRef, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { ExpandButton } from '@/components/ui/expand-button'
import { IconButton } from '@/components/ui/icon-button'
import { InlineAlert } from '@/components/ui/inline-alert'
import { cn } from '@/lib/cn'
import { lopBoCucKhung } from './boCucKhung'
import {
  dinhDangGiaTri,
  dungMoHinh,
  layGiaTriThamSoTuyChon,
  nhanHienThiGiaTri,
  taoTrangThaiMacDinh,
} from './dungMoHinh'
import type { GiaTriThamSo, TrangThaiDieuKhien } from './dungMoHinh'
import { kiemDacTa } from './nguPhap'
import type { BoDuLieu, DacTaMinhHoa, GiaTriO, ThamSoDieuKhien } from './nguPhap'
import { VeSvg } from './VeSvg'

export interface KhungMinhHoaProps {
  dacTa: unknown
  boDuLieu: readonly BoDuLieu[]
  congThucHienThi?: Readonly<Record<string, string>>
  giaLap?: boolean
  className?: string
}

function giaTriKhop(a: GiaTriO, b: GiaTriO): boolean {
  if (typeof a === 'number' && typeof b === 'number') {
    return Math.abs(a - b) < 1e-9
  }
  return a === b
}

function nhanBoDuLieu(ds: BoDuLieu, index: number): string {
  if (ds.ten?.trim()) return ds.ten.trim()
  const cot = new Set(ds.cot.map((item) => item.ten))
  if (cot.has('creatinin') && cot.has('crcl')) {
    return ds.dong.length === 1 ? 'Giá trị của ca' : 'Lưới CrCl theo creatinin'
  }
  if (cot.has('khuyen_cao')) return 'Mức liều'
  if (cot.has('thuoc_a') && cot.has('thuoc_b')) return 'Cặp tương tác'
  return `Bảng ${index + 1}`
}

export function BangDuLieuGoc({ boDuLieu }: { boDuLieu: readonly BoDuLieu[] }) {
  const [selectedDs, setSelectedDs] = useState<string>(boDuLieu[0]?.ma ?? '')
  const activeDs = boDuLieu.find((item) => item.ma === selectedDs) ?? boDuLieu[0]

  if (!activeDs) {
    return (
      <p className="rounded-sm border border-line bg-surface-muted/50 px-3 py-2 text-xs text-fg-muted">
        Không có bộ dữ liệu đi kèm.
      </p>
    )
  }

  return (
    <div className="flex min-w-0 flex-col gap-2">
      {boDuLieu.length > 1 ? (
        <div className="flex flex-wrap items-center gap-1.5" role="tablist" aria-label="Chọn bộ dữ liệu">
          {boDuLieu.map((ds, index) => {
            const active = ds.ma === activeDs.ma
            return (
              <button
                key={ds.ma}
                type="button"
                role="tab"
                title={ds.ma}
                aria-selected={active}
                onClick={() => setSelectedDs(ds.ma)}
                className={cn(
                  'min-h-8 cursor-pointer rounded-sm border px-2.5 py-1 text-xs font-medium transition-colors duration-120',
                  active
                    ? 'border-primary-line bg-primary-soft text-primary'
                    : 'border-line bg-surface text-fg-muted hover:bg-surface-hover hover:text-fg',
                )}
              >
                <span>{nhanBoDuLieu(ds, index)}</span>{' '}
                <span className="text-2xs opacity-80">({ds.dong.length} dòng)</span>
              </button>
            )
          })}
        </div>
      ) : null}

      <div className="max-h-72 min-w-0 w-full overflow-auto rounded-sm border border-line">
        <table className="w-full min-w-max border-collapse text-xs">
          <thead className="sticky top-0 z-10 bg-surface-muted">
            <tr>
              {activeDs.cot.map((col) => (
                <th
                  key={col.ten}
                  scope="col"
                  className={cn(
                    'border-b border-line px-3 py-2 font-semibold text-fg-muted whitespace-nowrap',
                    col.kieu === 'dinh_luong' ? 'text-right' : 'text-left',
                  )}
                >
                  {col.ten}
                  {col.don_vi ? (
                    <span className="ml-1 font-normal text-2xs text-fg-subtle">({col.don_vi})</span>
                  ) : null}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {activeDs.dong.map((row, rIdx) => (
              <tr key={rIdx} className="border-b border-line last:border-b-0 hover:bg-surface-hover">
                {activeDs.cot.map((col) => {
                  const val = row[col.ten] ?? null
                  const isNumeric = col.kieu === 'dinh_luong'
                  return (
                    <td
                      key={col.ten}
                      className={cn(
                        'px-3 py-1.5 text-fg',
                        isNumeric ? 'text-right font-mono tabular-nums whitespace-nowrap' : 'text-left',
                      )}
                    >
                      {dinhDangGiaTri(val, isNumeric && typeof val === 'number' && !Number.isInteger(val) ? '0.00' : undefined)}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function VungDieuKhien({
  dacTa,
  boDuLieu,
  trangThai,
  macDinh,
  onCapNhat,
  onDatLai,
}: {
  dacTa: DacTaMinhHoa
  boDuLieu: readonly BoDuLieu[]
  trangThai: TrangThaiDieuKhien
  macDinh: TrangThaiDieuKhien
  onCapNhat: (ma: string, value: GiaTriThamSo) => void
  onDatLai: () => void
}) {
  const baseId = useId()
  const params = dacTa.tham_so ?? []
  if (params.length === 0) return null

  const renderControl = (ts: ThamSoDieuKhien, idx: number) => {
    if (ts.loai === 'dat_lai') {
      return (
        <div key={`reset-${idx}`} className="flex items-end">
          <Button
            variant="secondary"
            size="md"
            iconLeft={<RotateCcw className="size-3.5" strokeWidth={1.75} />}
            onClick={onDatLai}
            className="min-h-8"
          >
            {ts.nhan}
          </Button>
        </div>
      )
    }

    if (!ts.ma) return null
    const ma = ts.ma
    const options = layGiaTriThamSoTuyChon(ts, boDuLieu)
    const ds = ts.gia_tri_tu ? boDuLieu.find((item) => item.ma === ts.gia_tri_tu?.ds) : undefined
    const donVi = ds?.cot.find((c) => c.ten === ts.gia_tri_tu?.cot)?.don_vi ?? null

    if (ts.loai === 'thanh_keo') {
      const current = (trangThai[ma] as GiaTriO | undefined) ?? options[0] ?? null
      const defaultVal = (macDinh[ma] as GiaTriO | undefined) ?? options[0] ?? null
      const currentIndex = Math.max(
        0,
        options.findIndex((item) => giaTriKhop(item, current)),
      )
      const dangGiaDinh = Boolean(ts.nhan_gia_dinh && !giaTriKhop(current, defaultVal))
      const inputId = `${baseId}-${ma}`

      const stepTo = (nextIdx: number) => {
        const clamped = Math.max(0, Math.min(options.length - 1, nextIdx))
        const val = options[clamped]
        if (val !== undefined) onCapNhat(ma, val)
      }

      return (
        <div key={ma} className="flex min-w-[220px] flex-1 flex-col gap-1.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <label htmlFor={inputId} className="text-xs font-medium text-fg-muted">
              {ts.nhan}
            </label>
            <div className="flex items-center gap-1.5">
              <span className="font-mono text-sm font-semibold text-fg tabular-nums">
                {dinhDangGiaTri(current)}
                {donVi ? ` ${donVi}` : ''}
              </span>
              {dangGiaDinh ? (
                <Badge tone="offlabel" variant="soft">
                  giả định
                </Badge>
              ) : null}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              aria-label={`Giảm ${ts.nhan}`}
              disabled={currentIndex <= 0}
              onClick={() => stepTo(currentIndex - 1)}
              className="inline-flex size-8 min-h-8 min-w-8 shrink-0 cursor-pointer items-center justify-center rounded-sm border border-line-strong bg-surface text-fg-muted transition-colors duration-120 hover:bg-surface-hover hover:text-fg disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Minus className="size-3.5" strokeWidth={1.75} aria-hidden="true" />
            </button>
            <input
              id={inputId}
              type="range"
              min={0}
              max={Math.max(0, options.length - 1)}
              step={1}
              value={currentIndex}
              aria-valuetext={`${dinhDangGiaTri(current)}${donVi ? ` ${donVi}` : ''}${dangGiaDinh ? ' (giả định)' : ''}`}
              onChange={(event) => stepTo(Number(event.target.value))}
              className="h-8 min-h-8 w-full cursor-pointer accent-primary"
            />
            <button
              type="button"
              aria-label={`Tăng ${ts.nhan}`}
              disabled={currentIndex >= options.length - 1}
              onClick={() => stepTo(currentIndex + 1)}
              className="inline-flex size-8 min-h-8 min-w-8 shrink-0 cursor-pointer items-center justify-center rounded-sm border border-line-strong bg-surface text-fg-muted transition-colors duration-120 hover:bg-surface-hover hover:text-fg disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Plus className="size-3.5" strokeWidth={1.75} aria-hidden="true" />
            </button>
          </div>
          {options.length >= 2 ? (
            <div className="flex justify-between font-mono text-2xs text-fg-subtle tabular-nums">
              <span>{dinhDangGiaTri(options[0])}</span>
              <span>{dinhDangGiaTri(options[options.length - 1])}</span>
            </div>
          ) : null}
        </div>
      )
    }

    if (ts.loai === 'chon_mot') {
      const current = (trangThai[ma] as GiaTriO | undefined) ?? options[0] ?? null
      return (
        <fieldset key={ma} className="flex min-w-0 flex-col gap-1.5 border-0 p-0">
          <legend className="text-xs font-medium text-fg-muted">{ts.nhan}</legend>
          <div className="flex flex-wrap gap-1.5">
            {options.map((opt) => {
              const active = giaTriKhop(current, opt)
              return (
                <button
                  key={String(opt)}
                  type="button"
                  aria-pressed={active}
                  onClick={() => onCapNhat(ma, opt)}
                  className={cn(
                    'min-h-8 cursor-pointer rounded-sm border px-3 py-1 text-xs font-medium transition-colors duration-120',
                    active
                      ? 'border-primary-line bg-primary-soft text-primary'
                      : 'border-line-strong bg-surface text-fg-muted hover:bg-surface-hover hover:text-fg',
                  )}
                >
                  {nhanHienThiGiaTri(opt)}
                </button>
              )
            })}
          </div>
        </fieldset>
      )
    }

    if (ts.loai === 'bat_tat' || ts.loai === 'loc') {
      const selected = Array.isArray(trangThai[ma]) ? (trangThai[ma] as readonly GiaTriO[]) : options
      const toggleItem = (opt: GiaTriO) => {
        const exists = selected.some((item) => giaTriKhop(item, opt))
        const next = exists
          ? selected.filter((item) => !giaTriKhop(item, opt))
          : [...selected, opt]
        onCapNhat(ma, next)
      }
      return (
        <fieldset key={ma} className="flex min-w-0 flex-col gap-1.5 border-0 p-0">
          <legend className="text-xs font-medium text-fg-muted">{ts.nhan}</legend>
          <div className="flex flex-wrap gap-1.5">
            {options.map((opt) => {
              const active = selected.some((item) => giaTriKhop(item, opt))
              return (
                <button
                  key={String(opt)}
                  type="button"
                  aria-pressed={active}
                  onClick={() => toggleItem(opt)}
                  className={cn(
                    'min-h-8 cursor-pointer rounded-sm border px-2.5 py-1 text-xs font-medium transition-colors duration-120',
                    active
                      ? 'border-primary-line bg-primary-soft text-primary'
                      : 'border-line-strong bg-surface text-fg-subtle line-through hover:bg-surface-hover hover:text-fg',
                  )}
                >
                  {nhanHienThiGiaTri(opt)}
                </button>
              )
            })}
          </div>
        </fieldset>
      )
    }

    return null
  }

  return (
    <div className="flex flex-wrap items-end gap-4 rounded-sm border border-line bg-surface-muted/40 p-3">
      {params.map((ts, idx) => renderControl(ts, idx))}
    </div>
  )
}

/**
 * Khung minh hoạ tương tác theo ngữ pháp `mh-0`:
 * tiêu đề, phụ đề tham chiếu ô, mở rộng toàn màn (Dialog UI1), xem dạng bảng,
 * bộ điều khiển, dòng số hiển thị, công thức, nguồn và nhãn cố định.
 */
export function KhungMinhHoa({
  dacTa,
  boDuLieu,
  congThucHienThi,
  giaLap = false,
  className = '',
}: KhungMinhHoaProps) {
  const kiem = useMemo(() => kiemDacTa(dacTa, boDuLieu), [dacTa, boDuLieu])
  const [xemBang, setXemBang] = useState(false)
  const [moToanMan, setMoToanMan] = useState(false)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [chieuRong, setChieuRong] = useState(640)

  const macDinh = useMemo(
    () => (kiem.hopLe ? taoTrangThaiMacDinh(kiem.dacTa, boDuLieu) : {}),
    [kiem, boDuLieu],
  )
  const [ghiDeState, setGhiDeState] = useState<{
    goc: Record<string, GiaTriThamSo>
    ghiDe: Record<string, GiaTriThamSo>
  }>(() => ({ goc: macDinh, ghiDe: {} }))

  const trangThai = useMemo<Record<string, GiaTriThamSo>>(
    () => (ghiDeState.goc === macDinh ? { ...macDinh, ...ghiDeState.ghiDe } : macDinh),
    [macDinh, ghiDeState],
  )
  const trangThaiVe = useDeferredValue(trangThai)

  useEffect(() => {
    const el = containerRef.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(([entry]) => {
      if (entry.contentRect.width > 0) {
        setChieuRong(Math.max(300, Math.floor(entry.contentRect.width)))
      }
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  const moHinhThuong = useMemo(
    () => (kiem.hopLe ? dungMoHinh(kiem.dacTa, boDuLieu, trangThaiVe, { rong: chieuRong }) : null),
    [kiem, boDuLieu, trangThaiVe, chieuRong],
  )
  const moHinhToanMan = useMemo(
    () =>
      kiem.hopLe && moToanMan
        ? dungMoHinh(kiem.dacTa, boDuLieu, trangThaiVe, { rong: Math.max(880, chieuRong) })
        : null,
    [kiem, boDuLieu, trangThaiVe, moToanMan, chieuRong],
  )

  const handleCapNhat = (ma: string, value: GiaTriThamSo) => {
    setGhiDeState((prev) => ({
      goc: macDinh,
      ghiDe: prev.goc === macDinh ? { ...prev.ghiDe, [ma]: value } : { [ma]: value },
    }))
  }
  const handleDatLai = () => {
    setGhiDeState({ goc: macDinh, ghiDe: {} })
  }

  // Đặc tả không hợp lệ: không vẽ hình, chỉ hiện thông báo gọn + nút xem bảng
  if (!kiem.hopLe) {
    return (
      <section
        aria-label="Minh hoạ không hợp lệ"
        className={cn(
          'flex min-w-0 flex-col gap-3 rounded-md border border-line bg-surface p-4 shadow-xs',
          className,
        )}
      >
        <InlineAlert
          tone="warning"
          role="alert"
          title="Không hiển thị được hình"
          action={
            <Button
              variant="secondary"
              size="md"
              iconLeft={<Table2 className="size-4" strokeWidth={1.75} />}
              onClick={() => setXemBang((prev) => !prev)}
              className="min-h-8"
            >
              {xemBang ? 'Ẩn bảng' : 'Xem dạng bảng'}
            </Button>
          }
        >
          <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs">
            {kiem.lyDo.slice(0, 5).map((reason, idx) => (
              <li key={idx}>{reason}</li>
            ))}
          </ul>
        </InlineAlert>

        {xemBang ? <BangDuLieuGoc boDuLieu={boDuLieu} /> : null}

        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line pt-2 text-xs text-fg-subtle">
          <span>Chỉ hiển thị dữ liệu gốc khi đặc tả bị từ chối.</span>
          <span className="font-medium text-fg-muted">Minh hoạ, không phải khuyến cáo</span>
        </div>
      </section>
    )
  }

  const dacTaHopLe = kiem.dacTa
  const chuoiCongThuc = dacTaHopLe.cong_thuc ? congThucHienThi?.[dacTaHopLe.cong_thuc] : undefined

  const renderNoiDungTuongTac = (moHinh: NonNullable<typeof moHinhThuong>) => (
    <div className="flex min-w-0 flex-col gap-3">
      {moHinh.phanTu.map((item) => item.loai === 'diem' && item.nhan && !item.laGiaDinh ? (
        <p key={item.ma} className="min-w-0 text-sm text-fg-muted tabular-nums break-words">
          {item.nhan}: {item.giaTriChu}
        </p>
      ) : null)}
      <VeSvg moHinh={moHinh} />

      {moHinh.soHien.length > 0 ? (
        <div className={lopBoCucKhung(chieuRong).soHien}>
          {moHinh.soHien.map((item) => (
            <div
              key={item.nhan}
              className="flex min-w-0 flex-col gap-0.5 rounded-sm border border-line bg-surface-muted/40 px-3 py-2"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-2xs font-medium uppercase tracking-wide text-fg-subtle">
                  {item.nhan}
                </span>
                {item.laGiaDinh ? (
                  <Badge tone="offlabel" variant="soft">
                    giả định
                  </Badge>
                ) : null}
              </div>
              <div className="text-sm font-semibold text-fg tabular-nums break-words">
                {item.giaTri}
              </div>
            </div>
          ))}
        </div>
      ) : null}

      <VungDieuKhien
        dacTa={dacTaHopLe}
        boDuLieu={boDuLieu}
        trangThai={trangThai}
        macDinh={macDinh}
        onCapNhat={handleCapNhat}
        onDatLai={handleDatLai}
      />

      {chuoiCongThuc ? (
        <div className="rounded-sm border border-line bg-surface-muted/50 px-3 py-2 text-xs text-fg-muted">
          <span className="font-semibold text-fg">Công thức ({dacTaHopLe.cong_thuc}): </span>
          <span className="font-mono text-2xs">{chuoiCongThuc}</span>
        </div>
      ) : null}
    </div>
  )

  return (
    <section
      aria-label={dacTaHopLe.tieu_de}
      className={cn(
        'flex min-w-0 flex-col gap-3 rounded-md border border-line bg-surface p-4 shadow-xs',
        className,
      )}
    >
      {/* Đầu khung: tiêu đề, phụ đề tham chiếu ô, nút mở rộng và xem bảng */}
      <div className="flex min-w-0 flex-col gap-0.5 border-b border-line pb-3">
        <div className="flex min-w-0 items-start justify-between gap-2">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <h2 className="min-w-0 text-md font-semibold text-fg break-words">{dacTaHopLe.tieu_de}</h2>
            {giaLap ? (
              <Badge tone="warning" variant="soft">
                Dữ liệu giả lập
              </Badge>
            ) : null}
            {moHinhThuong?.laGiaDinh ? (
              <Badge tone="offlabel" variant="outline">
                Đang xem giá trị giả định
              </Badge>
            ) : null}
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            <IconButton
              variant={xemBang ? 'soft' : 'ghost'}
              size="md"
              icon={<Table2 className="size-4" strokeWidth={1.75} />}
              aria-label={xemBang ? 'Ẩn bảng' : 'Xem dạng bảng'}
              onClick={() => setXemBang((prev) => !prev)}
              aria-pressed={xemBang}
            />

          <Dialog open={moToanMan} onOpenChange={setMoToanMan}>
            <DialogTrigger asChild>
              <ExpandButton label="Mở rộng hình" />
            </DialogTrigger>
            <DialogContent variant="fullscreen" aria-describedby={undefined}>
              <DialogHeader>
                <DialogTitle>{dacTaHopLe.tieu_de}</DialogTitle>
                {moHinhThuong?.phuDe ? (
                  <p className="text-sm text-fg-muted tabular-nums">{moHinhThuong.phuDe}</p>
                ) : null}
              </DialogHeader>
              <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
                {moHinhToanMan ? renderNoiDungTuongTac(moHinhToanMan) : null}
                <div className="mt-4">
                  <BangDuLieuGoc boDuLieu={boDuLieu} />
                </div>
              </div>
              <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-t border-line bg-surface-muted/50 px-6 py-3 text-xs text-fg-subtle">
                <span>Nguồn: {dacTaHopLe.nguon.join(' · ')}</span>
                <span className="font-medium text-fg-muted">Minh hoạ, không phải khuyến cáo</span>
              </div>
            </DialogContent>
          </Dialog>
          </div>
        </div>
        {moHinhThuong?.phuDe ? (
          <p className="mt-0.5 text-sm text-fg-muted tabular-nums">{moHinhThuong.phuDe}</p>
        ) : null}
      </div>

      {/* Thân khung: biểu đồ hoặc bảng */}
      <div ref={containerRef} className="min-w-0 w-full">
        {xemBang ? (
          <BangDuLieuGoc boDuLieu={boDuLieu} />
        ) : moHinhThuong ? (
          renderNoiDungTuongTac(moHinhThuong)
        ) : null}
      </div>

      {/* Chân khung: nguồn + nhãn cố định không thể tắt */}
      <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-line pt-2.5 text-xs text-fg-subtle">
        <div className="flex flex-wrap items-center gap-1.5">
          <span>Nguồn:</span>
          {dacTaHopLe.nguon.map((maNguon) => (
            <code
              key={maNguon}
              className="rounded-sm border border-line bg-surface-muted px-1.5 py-0.5 font-mono text-2xs text-fg-muted"
            >
              {maNguon}
            </code>
          ))}
        </div>
        <span className="font-medium text-fg-muted">Minh hoạ, không phải khuyến cáo</span>
      </footer>
    </section>
  )
}
