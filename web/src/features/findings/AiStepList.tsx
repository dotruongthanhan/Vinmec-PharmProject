import {
  Circle,
  CircleAlert,
  CircleCheck,
  CircleSlash,
  LoaderCircle,
} from 'lucide-react'
import type { BuocAI, TrangThaiBuocAI } from '@/api/types'
import { AI_STEP_STATUS_LABELS, formatAiDuration } from '@/lib/aiReview'
import { cn } from '@/lib/cn'

/** Ánh xạ danh sách bước sang bản đồ mã bước → trạng thái để theo dõi đổi trạng thái. */
// oxlint-disable-next-line react/only-export-components
export function toStepStatusMap(steps: readonly BuocAI[]): Record<string, TrangThaiBuocAI> {
  const map: Record<string, TrangThaiBuocAI> = {}
  for (const step of steps) {
    map[step.ma] = step.trang_thai
  }
  return map
}

/** Biểu tượng trạng thái cho từng bước AI (luôn đi kèm chữ ẩn cho trình đọc màn hình). */
export function AiStepStatusIcon({ status }: { status: TrangThaiBuocAI }) {
  switch (status) {
    case 'cho':
      return <Circle className="size-4 shrink-0 text-fg-subtle" strokeWidth={1.75} aria-hidden="true" />
    case 'dang_chay':
      return (
        <LoaderCircle
          className="size-4 shrink-0 text-ai-fg motion-safe:animate-spin"
          strokeWidth={1.75}
          aria-hidden="true"
        />
      )
    case 'xong':
      return <CircleCheck className="size-4 shrink-0 text-success-fg" strokeWidth={1.75} aria-hidden="true" />
    case 'loi':
      return <CircleAlert className="size-4 shrink-0 text-warning-fg" strokeWidth={1.75} aria-hidden="true" />
    case 'bo_qua':
      return <CircleSlash className="size-4 shrink-0 text-fg-disabled" strokeWidth={1.75} aria-hidden="true" />
  }
}

export interface AiStepListProps {
  steps: readonly BuocAI[]
  liveDeltaMs?: number
}

/** Danh sách các bước tiến trình AI dùng chung cho cả bảng nhận định và khung hỏi đáp. */
export function AiStepList({ steps, liveDeltaMs = 0 }: AiStepListProps) {
  return (
    <ol className="flex flex-col gap-2">
      {steps.map((step, index) => {
        const nguonList = Array.isArray(step.nguon) ? step.nguon : []
        const isRunning = step.trang_thai === 'dang_chay'
        const isSkipped = step.trang_thai === 'bo_qua'
        const isError = step.trang_thai === 'loi'
        const rawDurationMs =
          isRunning && (step.thoi_gian_ms !== null || liveDeltaMs > 0)
            ? (step.thoi_gian_ms ?? 0) + liveDeltaMs
            : step.thoi_gian_ms
        const durationText =
          step.trang_thai === 'cho' || isSkipped ? '' : formatAiDuration(rawDurationMs)

        return (
          <li
            key={`${step.ma || 'buoc'}-${index}`}
            className={cn(
              'flex items-start justify-between gap-2 text-sm',
              isSkipped && 'opacity-55',
            )}
          >
            <div className="flex min-w-0 flex-1 items-start gap-2">
              <span className="mt-0.5 inline-flex shrink-0 items-center">
                <AiStepStatusIcon status={step.trang_thai} />
              </span>

              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                  <span
                    className={cn(
                      'font-medium break-words',
                      isSkipped ? 'text-fg-muted' : 'text-fg',
                    )}
                  >
                    {step.ten}
                    <span className="sr-only"> ({AI_STEP_STATUS_LABELS[step.trang_thai]})</span>
                  </span>
                  {step.chi_tiet ? (
                    <span className="text-xs text-fg-muted break-words">{step.chi_tiet}</span>
                  ) : null}
                </div>

                {nguonList.length > 0 ? (
                  <div className="mt-1 flex flex-wrap items-center gap-1.5">
                    {nguonList.map((src, srcIdx) => (
                      <span
                        key={`${src.nhan}-${srcIdx}`}
                        className="inline-flex max-w-full items-center gap-1 rounded-full border border-line bg-surface px-2 py-0.5 text-2xs font-medium text-fg-muted tabular-nums"
                      >
                        <span className="break-words">{src.nhan}</span>
                        <span>{src.so_doan}</span>
                      </span>
                    ))}
                  </div>
                ) : null}

                {isError && step.ly_do ? (
                  <p className="mt-1 text-xs text-warning-fg whitespace-pre-wrap break-words">
                    {step.ly_do}
                  </p>
                ) : null}
                {isError && step.goi_y ? (
                  <p className="mt-0.5 text-xs text-fg-muted whitespace-pre-wrap break-words">
                    {step.goi_y}
                  </p>
                ) : null}
              </div>
            </div>

            {durationText ? (
              <span
                aria-hidden={isRunning ? 'true' : undefined}
                className="shrink-0 pt-0.5 text-xs text-fg-subtle tabular-nums"
              >
                {durationText}
              </span>
            ) : null}
          </li>
        )
      })}
    </ol>
  )
}
