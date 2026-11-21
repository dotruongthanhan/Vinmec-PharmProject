import {
  Circle,
  CircleAlert,
  CircleCheck,
  CircleSlash,
  Info,
  LoaderCircle,
  RotateCw,
  Sparkles,
  TriangleAlert,
} from 'lucide-react'
import { useEffect, useId, useState } from 'react'
import type { BuocAI, TrangThaiAI, TrangThaiBuocAI } from '@/api/types'
import { Button } from '@/components/ui/button'
import {
  AI_STEP_STATUS_LABELS,
  evaluateSlowAi,
  formatAiDuration,
  formatAiElapsedClock,
  formatAiTypicalRange,
  pickStepStatusAnnouncement,
} from '@/lib/aiReview'
import { cn } from '@/lib/cn'

const EMPTY_STEPS: readonly BuocAI[] = []
const EMPTY_WARNINGS: readonly string[] = []

export interface AiProgressPanelProps {
  trangThai: TrangThaiAI
  cacBuoc?: readonly BuocAI[]
  daChayMs?: number | null
  thuongLeMs?: number | null
  thoiGianMs?: number | null
  summaryText?: string
  canhBao?: readonly string[]
  onRerun?: () => void
  defaultExpanded?: boolean
}

function toStepStatusMap(steps: readonly BuocAI[]): Record<string, TrangThaiBuocAI> {
  const map: Record<string, TrangThaiBuocAI> = {}
  for (const step of steps) {
    map[step.ma] = step.trang_thai
  }
  return map
}

function StepStatusIcon({ status }: { status: TrangThaiBuocAI }) {
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

function StepList({
  steps,
  liveDeltaMs,
}: {
  steps: readonly BuocAI[]
  liveDeltaMs: number
}) {
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
                <StepStatusIcon status={step.trang_thai} />
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

/** Hiển thị tiến trình phân tích AI theo từng bước thật ở các trạng thái đang chạy, xong (thu gọn) và lỗi. */
export function AiProgressPanel({
  trangThai,
  cacBuoc = EMPTY_STEPS,
  daChayMs = null,
  thuongLeMs = null,
  thoiGianMs = null,
  summaryText,
  canhBao = EMPTY_WARNINGS,
  onRerun,
  defaultExpanded = false,
}: AiProgressPanelProps) {
  const stepsRegionId = useId()
  const [stepsExpanded, setStepsExpanded] = useState<boolean>(defaultExpanded)

  const runningStep = cacBuoc.find((step) => step.trang_thai === 'dang_chay')
  const anchorKey = `${trangThai}:${daChayMs ?? 'null'}:${runningStep ? `${runningStep.ma}:${runningStep.thoi_gian_ms ?? 'null'}` : 'none'}`

  const [tickState, setTickState] = useState<{ key: string; deltaMs: number }>({
    key: anchorKey,
    deltaMs: 0,
  })
  const effectiveDeltaMs =
    trangThai === 'dang_chay' && tickState.key === anchorKey ? tickState.deltaMs : 0

  useEffect(() => {
    if (trangThai !== 'dang_chay') {
      return
    }
    const anchor = Date.now()
    const timer = setInterval(() => {
      setTickState({
        key: anchorKey,
        deltaMs: Math.max(0, Date.now() - anchor),
      })
    }, 500)
    return () => {
      clearInterval(timer)
    }
  }, [trangThai, anchorKey])

  const statusSignature = `${trangThai}|${cacBuoc.map((s) => `${s.ma}:${s.trang_thai}`).join('|')}`
  const [prevStatusSignature, setPrevStatusSignature] = useState<string>(statusSignature)
  const [prevStepMap, setPrevStepMap] = useState<Record<string, TrangThaiBuocAI>>(() =>
    toStepStatusMap(cacBuoc),
  )
  const [liveAnnouncement, setLiveAnnouncement] = useState<string>(() =>
    trangThai === 'dang_chay' || trangThai === 'loi'
      ? pickStepStatusAnnouncement(cacBuoc, null)
      : '',
  )

  if (statusSignature !== prevStatusSignature) {
    const nextMap = toStepStatusMap(cacBuoc)
    const isNewRun = prevStatusSignature.startsWith('xong|') && trangThai === 'dang_chay'
    const nextMessage = pickStepStatusAnnouncement(cacBuoc, isNewRun ? null : prevStepMap)
    setPrevStatusSignature(statusSignature)
    setPrevStepMap(nextMap)
    if (nextMessage) {
      setLiveAnnouncement(nextMessage)
    } else if (isNewRun) {
      setLiveAnnouncement('')
    }
  }

  if (trangThai === 'tat') {
    return null
  }

  const typicalRange = formatAiTypicalRange(thuongLeMs)

  if (trangThai === 'dang_chay') {
    const totalClockMs = (daChayMs ?? 0) + effectiveDeltaMs
    const slowStatus = evaluateSlowAi({
      cacBuoc,
      daChayMs,
      thuongLeMs,
      localDeltaMs: effectiveDeltaMs,
    })

    return (
      <div className="rounded-md border border-ai-line bg-ai-bg px-3 py-2.5 text-sm text-ai-fg">
        <div className="sr-only" aria-live="polite" aria-atomic="true">
          {liveAnnouncement}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
          <div className="flex min-w-0 items-center gap-2">
            {cacBuoc.length === 0 ? (
              <LoaderCircle
                className="size-4 shrink-0 motion-safe:animate-spin"
                strokeWidth={1.75}
                aria-hidden="true"
              />
            ) : (
              <Sparkles className="size-4 shrink-0" strokeWidth={1.75} aria-hidden="true" />
            )}
            <span className="font-medium break-words">AI đang phân tích ca này</span>
          </div>

          <div
            aria-hidden="true"
            className="flex flex-wrap items-center gap-x-1.5 text-xs text-ai-fg/80 tabular-nums"
          >
            <span>{formatAiElapsedClock(totalClockMs)}</span>
            {typicalRange ? (
              <>
                <span aria-hidden="true">·</span>
                <span>{typicalRange}</span>
              </>
            ) : null}
          </div>
        </div>

        {cacBuoc.length > 0 ? (
          <div className="mt-2.5">
            <StepList steps={cacBuoc} liveDeltaMs={effectiveDeltaMs} />
          </div>
        ) : null}

        {slowStatus.isSlow && slowStatus.message ? (
          <p
            role="status"
            className="mt-2.5 rounded-sm border border-warning-line bg-warning-bg px-2.5 py-1.5 text-xs text-warning-fg break-words"
          >
            {slowStatus.message}
          </p>
        ) : null}

        <p className="mt-2 text-xs text-fg-muted">Bảng bên dưới là kết quả của bộ luật.</p>
      </div>
    )
  }

  if (trangThai === 'loi') {
    const errorTotalText =
      daChayMs !== null ? formatAiDuration(daChayMs) : thoiGianMs !== null ? formatAiDuration(thoiGianMs) : ''

    return (
      <div
        role="alert"
        className="rounded-md border border-warning-line bg-warning-bg px-3 py-2.5 text-sm text-warning-fg"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex min-w-0 flex-1 items-start gap-2">
            <TriangleAlert className="mt-0.5 size-4 shrink-0" strokeWidth={1.75} aria-hidden="true" />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline justify-between gap-x-2 gap-y-0.5">
                <p className="font-medium break-words">
                  Bước AI không hoàn tất. Đang hiển thị kết quả của bộ luật.
                </p>
                {errorTotalText ? (
                  <span className="shrink-0 text-xs text-warning-fg/80 tabular-nums">
                    {errorTotalText}
                  </span>
                ) : null}
              </div>

              {canhBao.length > 0 ? (
                <ul className="mt-1.5 flex list-disc flex-col gap-0.5 pl-4 text-xs text-warning-fg">
                  {canhBao.map((msg, idx) => (
                    <li key={`ai-err-warn-${idx}`} className="whitespace-pre-wrap break-words">
                      {msg}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          </div>

          {onRerun ? (
            <div className="flex shrink-0 items-center self-center">
              <Button
                variant="secondary"
                size="sm"
                iconLeft={<RotateCw className="size-3.5" strokeWidth={1.75} />}
                onClick={onRerun}
              >
                Thử lại
              </Button>
            </div>
          ) : null}
        </div>

        {cacBuoc.length > 0 ? (
          <div className="mt-2.5 border-t border-warning-line/60 pt-2.5">
            <StepList steps={cacBuoc} liveDeltaMs={0} />
          </div>
        ) : null}
      </div>
    )
  }

  const stepsCount = cacBuoc.length
  const fallbackDoneDuration = thoiGianMs ?? daChayMs
  const resolvedSummary =
    summaryText ??
    (fallbackDoneDuration !== null
      ? `AI đã phân tích xong (${formatAiDuration(fallbackDoneDuration)}).`
      : 'AI đã phân tích xong.')

  return (
    <div
      role="status"
      className="rounded-md border border-ai-line bg-ai-bg px-3 py-2.5 text-sm text-ai-fg"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 flex-1 items-start gap-2">
          <Info className="mt-0.5 size-4 shrink-0" strokeWidth={1.75} aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <p className="font-medium tabular-nums break-words">{resolvedSummary}</p>
            {canhBao.length > 0 ? (
              <ul className="mt-1.5 flex list-disc flex-col gap-0.5 pl-4 text-xs text-fg-muted">
                {canhBao.map((msg, idx) => (
                  <li key={`ai-done-warn-${idx}`} className="whitespace-pre-wrap break-words">
                    {msg}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        </div>

        <div className="flex shrink-0 flex-wrap items-center gap-1.5 self-center">
          {stepsCount > 0 ? (
            <Button
              variant="ghost"
              size="sm"
              aria-expanded={stepsExpanded}
              aria-controls={stepsRegionId}
              onClick={() => setStepsExpanded((prev) => !prev)}
            >
              {stepsExpanded ? 'Ẩn các bước' : `Xem các bước (${stepsCount})`}
            </Button>
          ) : null}

          {onRerun ? (
            <Button
              variant="ghost"
              size="sm"
              iconLeft={<RotateCw className="size-3.5" strokeWidth={1.75} />}
              onClick={onRerun}
            >
              Chạy lại
            </Button>
          ) : null}
        </div>
      </div>

      {stepsCount > 0 ? (
        <div
          id={stepsRegionId}
          hidden={!stepsExpanded}
          className={stepsExpanded ? 'mt-2.5 border-t border-ai-line/60 pt-2.5' : undefined}
        >
          {stepsExpanded ? <StepList steps={cacBuoc} liveDeltaMs={0} /> : null}
        </div>
      ) : null}
    </div>
  )
}
