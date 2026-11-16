import { LoaderCircle, RotateCw } from 'lucide-react'
import type { TrangThaiAI } from '@/api/types'
import { Button } from '@/components/ui/button'
import { InlineAlert } from '@/components/ui/inline-alert'
import { formatAiSeconds } from '@/lib/aiReview'

export interface AiStatusBarProps {
  trangThai: TrangThaiAI
  thoiGianMs: number | null
  coDienGiai: number
  doAiThem: number
  canhBao: readonly string[]
  onRerun: () => void
}

/** Dải trạng thái phân tích AI chạy nền đặt ngay trên bảng nhận định. */
export function AiStatusBar({
  trangThai,
  thoiGianMs,
  coDienGiai,
  doAiThem,
  canhBao,
  onRerun,
}: AiStatusBarProps) {
  if (trangThai === 'tat') {
    return null
  }

  if (trangThai === 'dang_chay') {
    return (
      <InlineAlert
        tone="ai"
        role="status"
        ariaLive="polite"
        icon={<LoaderCircle className="size-4 animate-spin" strokeWidth={1.75} />}
      >
        <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
          <span className="font-medium text-ai-fg">AI đang phân tích…</span>
          <span className="inline-flex flex-wrap items-center gap-1.5 text-xs text-ai-fg/80">
            <span className="inline-flex items-center gap-1">
              <span className="size-1.5 rounded-full bg-ai-solid" aria-hidden="true" />
              <span>Lấy nguồn</span>
            </span>
            <span aria-hidden="true">·</span>
            <span className="inline-flex items-center gap-1">
              <span className="size-1.5 rounded-full bg-ai-solid/70" aria-hidden="true" />
              <span>Tổng hợp</span>
            </span>
            <span aria-hidden="true">·</span>
            <span className="inline-flex items-center gap-1">
              <span className="size-1.5 rounded-full bg-ai-solid/40" aria-hidden="true" />
              <span>Kiểm chứng</span>
            </span>
          </span>
        </div>
        <p className="mt-0.5 text-xs text-fg-muted">
          Bảng dưới đây là kết quả của bộ luật.
        </p>
      </InlineAlert>
    )
  }

  if (trangThai === 'loi') {
    return (
      <InlineAlert
        tone="warning"
        role="alert"
        action={
          <Button
            variant="secondary"
            size="sm"
            iconLeft={<RotateCw className="size-3.5" strokeWidth={1.75} />}
            onClick={onRerun}
          >
            Thử lại
          </Button>
        }
      >
        <p className="font-medium">
          Bước AI không hoàn tất. Đang hiển thị kết quả của bộ luật.
        </p>
        {canhBao.length > 0 ? (
          <ul className="mt-1.5 flex list-disc flex-col gap-0.5 pl-4 text-xs text-warning-fg">
            {canhBao.map((msg, idx) => (
              <li key={`ai-err-warn-${idx}`} className="whitespace-pre-wrap">
                {msg}
              </li>
            ))}
          </ul>
        ) : null}
      </InlineAlert>
    )
  }

  const timeText = thoiGianMs !== null ? ` (${formatAiSeconds(thoiGianMs)} giây)` : ''

  return (
    <InlineAlert
      tone="ai"
      role="status"
      action={
        <Button
          variant="ghost"
          size="sm"
          iconLeft={<RotateCw className="size-3.5" strokeWidth={1.75} />}
          onClick={onRerun}
        >
          Chạy lại
        </Button>
      }
    >
      <p className="font-medium tabular-nums">
        AI đã phân tích xong{timeText}. {coDienGiai} nhận định có diễn giải, {doAiThem} nhận định do
        AI thêm.
      </p>
      {canhBao.length > 0 ? (
        <ul className="mt-1.5 flex list-disc flex-col gap-0.5 pl-4 text-xs text-fg-muted">
          {canhBao.map((msg, idx) => (
            <li key={`ai-done-warn-${idx}`} className="whitespace-pre-wrap">
              {msg}
            </li>
          ))}
        </ul>
      ) : null}
    </InlineAlert>
  )
}
