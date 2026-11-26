/**
 * Trình dán & cắt ảnh chụp bảng y lệnh OH không suy hao (lossless PNG).
 * Hỗ trợ Ctrl+V trực tiếp, kéo thả, tô đen vùng nhạy cảm và cảnh báo mềm khi cắt chưa hết thanh trên.
 */

import { AlertTriangle, CheckSquare, Crop, Eraser, RotateCcw, Upload } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'

const PRESET_KEY = 'cdss_ext_oh_crop_preset_v1'
const MAX_DIMENSION = 3072

export interface NormRect {
  x: number
  y: number
  w: number
  h: number
}

export interface CroppedOhImageValue {
  blob: Blob
  previewUrl: string
  width: number
  height: number
  sizeBytes: number
  confirmedNoPii: boolean
  softWarning: string | null
}

interface Props {
  value: CroppedOhImageValue | null
  onChange: (next: CroppedOhImageValue | null) => void
}

export function computeTopStripSoftWarning(crop: NormRect, imgHeight: number): string | null {
  if (crop.y <= 0.01 && crop.h >= 0.85 && imgHeight > 520) {
    return 'Ảnh có chiều cao lớn và chưa cắt phần mép trên. Hãy kiểm tra lại xem đã cắt bỏ thanh tên/mã bệnh nhân OH chưa.'
  }
  return null
}

function clampNormRect(r: NormRect): NormRect {
  const x = Math.max(0, Math.min(0.95, r.x))
  const y = Math.max(0, Math.min(0.95, r.y))
  const w = Math.max(0.05, Math.min(1 - x, r.w))
  const h = Math.max(0.05, Math.min(1 - y, r.h))
  return { x, y, w, h }
}

export function OhImageCropper({ value, onChange }: Props) {
  const [sourceImg, setSourceImg] = useState<HTMLImageElement | null>(null)
  const [cropRect, setCropRect] = useState<NormRect>({ x: 0, y: 0.14, w: 1, h: 0.86 })
  const [blackoutRects, setBlackoutRects] = useState<NormRect[]>([])
  const [mode, setMode] = useState<'crop' | 'blackout'>('crop')
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null)
  const [draftRect, setDraftRect] = useState<NormRect | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const [presetStatus, setPresetStatus] = useState<string | null>(null)

  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const loadPresetIfAny = useCallback(async (): Promise<NormRect | null> => {
    if (typeof chrome === 'undefined' || !chrome.storage?.local) return null
    const data = await chrome.storage.local.get(PRESET_KEY)
    const raw = data[PRESET_KEY] as NormRect | undefined
    if (raw && typeof raw.x === 'number' && typeof raw.y === 'number') {
      return clampNormRect(raw)
    }
    return null
  }, [])

  const exportLosslessPng = useCallback(
    (img: HTMLImageElement, rect: NormRect, masks: NormRect[], isConfirmed: boolean) => {
      const sx = Math.round(rect.x * img.naturalWidth)
      const sy = Math.round(rect.y * img.naturalHeight)
      const sw = Math.max(1, Math.round(rect.w * img.naturalWidth))
      const sh = Math.max(1, Math.round(rect.h * img.naturalHeight))

      let outW = sw
      let outH = sh
      const maxSide = Math.max(sw, sh)
      if (maxSide > MAX_DIMENSION) {
        const scale = MAX_DIMENSION / maxSide
        outW = Math.round(sw * scale)
        outH = Math.round(sh * scale)
      }

      const offscreen = document.createElement('canvas')
      offscreen.width = outW
      offscreen.height = outH
      const ctx = offscreen.getContext('2d')
      if (!ctx) return

      ctx.imageSmoothingEnabled = true
      ctx.imageSmoothingQuality = 'high'
      ctx.drawImage(img, sx, sy, sw, sh, 0, 0, outW, outH)

      ctx.fillStyle = '#0f172a'
      for (const m of masks) {
        const mx = Math.round(((m.x - rect.x) / rect.w) * outW)
        const my = Math.round(((m.y - rect.y) / rect.h) * outH)
        const mw = Math.round((m.w / rect.w) * outW)
        const mh = Math.round((m.h / rect.h) * outH)
        ctx.fillRect(mx, my, mw, mh)
      }

      offscreen.toBlob((blob) => {
        if (!blob) return
        if (value?.previewUrl) {
          URL.revokeObjectURL(value.previewUrl)
        }
        const previewUrl = URL.createObjectURL(blob)
        onChange({
          blob,
          previewUrl,
          width: outW,
          height: outH,
          sizeBytes: blob.size,
          confirmedNoPii: isConfirmed,
          softWarning: computeTopStripSoftWarning(rect, img.naturalHeight),
        })
      }, 'image/png')
    },
    [onChange, value?.previewUrl],
  )

  const handleImageFile = useCallback(
    async (file: File) => {
      const readerUrl = URL.createObjectURL(file)
      const img = new Image()
      img.onload = async () => {
        URL.revokeObjectURL(readerUrl)
        const saved = await loadPresetIfAny()
        const initialCrop = saved ?? {
          x: 0,
          y: img.naturalHeight > 520 ? 0.14 : 0,
          w: 1,
          h: img.naturalHeight > 520 ? 0.86 : 1,
        }
        setSourceImg(img)
        setCropRect(initialCrop)
        setBlackoutRects([])
        setConfirmed(false)
        exportLosslessPng(img, initialCrop, [], false)
      }
      img.onerror = () => URL.revokeObjectURL(readerUrl)
      img.src = readerUrl
    },
    [exportLosslessPng, loadPresetIfAny],
  )

  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      const items = e.clipboardData?.items
      if (!items) return
      for (const item of Array.from(items)) {
        if (item.type.startsWith('image/')) {
          const blob = item.getAsFile()
          if (blob) {
            e.preventDefault()
            void handleImageFile(blob)
            break
          }
        }
      }
    }
    window.addEventListener('paste', onPaste)
    return () => window.removeEventListener('paste', onPaste)
  }, [handleImageFile])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !sourceImg) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const maxPreviewW = 420
    const scale = Math.min(1, maxPreviewW / sourceImg.naturalWidth)
    canvas.width = Math.max(200, Math.round(sourceImg.naturalWidth * scale))
    canvas.height = Math.max(120, Math.round(sourceImg.naturalHeight * scale))

    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.drawImage(sourceImg, 0, 0, canvas.width, canvas.height)

    const rx = cropRect.x * canvas.width
    const ry = cropRect.y * canvas.height
    const rw = cropRect.w * canvas.width
    const rh = cropRect.h * canvas.height

    ctx.fillStyle = 'rgba(15, 23, 42, 0.55)'
    ctx.fillRect(0, 0, canvas.width, ry)
    ctx.fillRect(0, ry + rh, canvas.width, canvas.height - (ry + rh))
    ctx.fillRect(0, ry, rx, rh)
    ctx.fillRect(rx + rw, ry, canvas.width - (rx + rw), rh)

    ctx.strokeStyle = '#0d9488'
    ctx.lineWidth = 2
    ctx.strokeRect(rx, ry, rw, rh)

    ctx.fillStyle = '#0f172a'
    for (const m of blackoutRects) {
      ctx.fillRect(m.x * canvas.width, m.y * canvas.height, m.w * canvas.width, m.h * canvas.height)
    }

    if (draftRect) {
      ctx.strokeStyle = mode === 'crop' ? '#f59e0b' : '#ef4444'
      ctx.setLineDash([4, 4])
      ctx.strokeRect(
        draftRect.x * canvas.width,
        draftRect.y * canvas.height,
        draftRect.w * canvas.width,
        draftRect.h * canvas.height,
      )
      ctx.setLineDash([])
    }
  }, [sourceImg, cropRect, blackoutRects, draftRect, mode])

  const normPoint = (e: React.MouseEvent<HTMLCanvasElement>): { x: number; y: number } => {
    const canvas = canvasRef.current
    if (!canvas) return { x: 0, y: 0 }
    const rect = canvas.getBoundingClientRect()
    return {
      x: Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width)),
      y: Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height)),
    }
  }

  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!sourceImg) return
    const pt = normPoint(e)
    setDragStart(pt)
    setDraftRect({ x: pt.x, y: pt.y, w: 0.01, h: 0.01 })
  }

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!dragStart) return
    const pt = normPoint(e)
    setDraftRect({
      x: Math.min(dragStart.x, pt.x),
      y: Math.min(dragStart.y, pt.y),
      w: Math.max(0.02, Math.abs(pt.x - dragStart.x)),
      h: Math.max(0.02, Math.abs(pt.y - dragStart.y)),
    })
  }

  const handleMouseUp = () => {
    if (!dragStart || !draftRect || !sourceImg) {
      setDragStart(null)
      setDraftRect(null)
      return
    }
    if (draftRect.w >= 0.04 && draftRect.h >= 0.04) {
      const normalized = clampNormRect(draftRect)
      if (mode === 'crop') {
        setCropRect(normalized)
        exportLosslessPng(sourceImg, normalized, blackoutRects, confirmed)
      } else {
        const nextMasks = [...blackoutRects, normalized]
        setBlackoutRects(nextMasks)
        exportLosslessPng(sourceImg, cropRect, nextMasks, confirmed)
      }
    }
    setDragStart(null)
    setDraftRect(null)
  }

  const savePreset = async () => {
    if (typeof chrome !== 'undefined' && chrome.storage?.local) {
      await chrome.storage.local.set({ [PRESET_KEY]: cropRect })
      setPresetStatus('Đã lưu khung cắt mặc định cho OH')
      setTimeout(() => setPresetStatus(null), 2500)
    }
  }

  const toggleConfirm = (checked: boolean) => {
    setConfirmed(checked)
    if (value) {
      onChange({ ...value, confirmedNoPii: checked })
    }
  }

  const clearImage = () => {
    if (value?.previewUrl) URL.revokeObjectURL(value.previewUrl)
    setSourceImg(null)
    setBlackoutRects([])
    setConfirmed(false)
    onChange(null)
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div>
          <h3 className="text-xs font-semibold text-slate-800">
            Ảnh chụp bảng y lệnh OH (PNG nguyên nét)
          </h3>
          <p className="text-[11px] text-slate-500">
            Nhấn <kbd className="rounded bg-slate-100 px-1 font-mono">Ctrl+V</kbd> để dán ảnh chụp
            vùng thuốc từ phần mềm OH, hoặc chọn tệp.
          </p>
        </div>
        {sourceImg && (
          <button
            type="button"
            onClick={clearImage}
            className="text-[11px] font-medium text-rose-600 hover:underline"
          >
            Gỡ ảnh
          </button>
        )}
      </div>

      {!sourceImg ? (
        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault()
            const file = e.dataTransfer.files?.[0]
            if (file) void handleImageFile(file)
          }}
          className="flex flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed border-slate-300 bg-slate-50 p-4 text-center"
        >
          <Upload className="h-5 w-5 text-teal-600" />
          <p className="text-xs text-slate-600">
            Dán (Ctrl+V) hoặc kéo thả ảnh bảng y lệnh OH vào đây
          </p>
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="rounded bg-white px-2.5 py-1 text-xs font-medium text-slate-700 shadow-sm ring-1 ring-slate-300 hover:bg-slate-100"
          >
            Chọn ảnh từ máy
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) void handleImageFile(file)
            }}
          />
        </div>
      ) : (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-1.5">
            <button
              type="button"
              onClick={() => setMode('crop')}
              className={`inline-flex items-center gap-1 rounded px-2 py-1 text-[11px] font-medium ${
                mode === 'crop'
                  ? 'bg-teal-600 text-white'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              <Crop className="h-3 w-3" /> Cắt khung bảng
            </button>
            <button
              type="button"
              onClick={() => setMode('blackout')}
              className={`inline-flex items-center gap-1 rounded px-2 py-1 text-[11px] font-medium ${
                mode === 'blackout'
                  ? 'bg-slate-900 text-white'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              <Eraser className="h-3 w-3" /> Tô đen che PII
            </button>
            <button
              type="button"
              onClick={() => {
                const full = { x: 0, y: 0, w: 1, h: 1 }
                setCropRect(full)
                setBlackoutRects([])
                exportLosslessPng(sourceImg, full, [], confirmed)
              }}
              className="inline-flex items-center gap-1 rounded bg-slate-100 px-2 py-1 text-[11px] text-slate-700 hover:bg-slate-200"
            >
              <RotateCcw className="h-3 w-3" /> Đặt lại
            </button>
            <button
              type="button"
              onClick={() => void savePreset()}
              className="ml-auto rounded bg-teal-50 px-2 py-1 text-[11px] font-medium text-teal-700 hover:bg-teal-100"
            >
              Lưu khung OH
            </button>
          </div>

          {presetStatus && <p className="text-[11px] text-teal-700">{presetStatus}</p>}

          <canvas
            ref={canvasRef}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            className="w-full cursor-crosshair rounded border border-slate-200 bg-slate-900/5"
          />

          {value && (
            <div className="flex items-center justify-between text-[11px] text-slate-500">
              <span>
                Độ phân giải PNG: <strong>{value.width} × {value.height} px</strong>
              </span>
              <span>
                Dung lượng: <strong>{(value.sizeBytes / 1024).toFixed(0)} KB</strong>
              </span>
            </div>
          )}

          {value?.softWarning && (
            <div className="flex items-start gap-2 rounded border border-amber-300 bg-amber-50 p-2 text-[11px] text-amber-800">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600" />
              <span>{value.softWarning}</span>
            </div>
          )}

          <label className="flex cursor-pointer items-start gap-2 rounded border border-slate-200 bg-slate-50 p-2 text-[11px] text-slate-700">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => toggleConfirm(e.target.checked)}
              className="mt-0.5 rounded border-slate-300 text-teal-600 focus:ring-teal-500"
            />
            <span className="inline-flex items-center gap-1">
              <CheckSquare className="h-3.5 w-3.5 shrink-0 text-teal-600" />
              Tôi xác nhận ảnh chụp OH đã cắt bỏ thanh định danh cá nhân bệnh nhân.
            </span>
          </label>
        </div>
      )}
    </div>
  )
}
