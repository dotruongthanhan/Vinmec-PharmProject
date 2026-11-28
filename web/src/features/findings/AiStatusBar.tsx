import type { BuocAI, TrangThaiAI } from '@/api/types'
import { formatAiDoneMessage } from '@/lib/aiReview'
import { AiProgressPanel } from './AiProgressPanel'

export interface AiStatusBarProps {
  trangThai: TrangThaiAI
  thoiGianMs: number | null
  coDienGiai: number
  coDienGiaiCanChuY?: number
  coDienGiaiDat?: number
  doAiThem: number
  canhBao: readonly string[]
  onRerun: () => void
  cacBuoc?: readonly BuocAI[]
  daChayMs?: number | null
  thuongLeMs?: number | null
}

/** Dải trạng thái phân tích AI chạy nền đặt ngay trên bảng nhận định. */
export function AiStatusBar({
  trangThai,
  thoiGianMs,
  coDienGiai,
  coDienGiaiCanChuY,
  coDienGiaiDat,
  doAiThem,
  canhBao,
  onRerun,
  cacBuoc,
  daChayMs = null,
  thuongLeMs = null,
}: AiStatusBarProps) {
  if (trangThai === 'tat') {
    return null
  }

  const summaryText =
    trangThai === 'xong'
      ? formatAiDoneMessage(thoiGianMs, {
          coDienGiai,
          coDienGiaiCanChuY,
          coDienGiaiDat,
          doAiThem,
        })
      : undefined

  return (
    <AiProgressPanel
      trangThai={trangThai}
      cacBuoc={cacBuoc}
      daChayMs={daChayMs}
      thuongLeMs={thuongLeMs}
      thoiGianMs={thoiGianMs}
      summaryText={summaryText}
      canhBao={canhBao}
      onRerun={onRerun}
    />
  )
}
