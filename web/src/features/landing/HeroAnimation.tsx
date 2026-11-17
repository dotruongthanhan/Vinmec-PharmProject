import { OctagonAlert, RotateCw } from 'lucide-react'
import { animate, motion, useInView, useReducedMotion } from 'motion/react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { RecordId } from '@/components/ui/record-id'

const TARGET_CRCL = 16.0

function formatCrclDecimal(value: number): string {
  return value.toFixed(1).replace('.', ',')
}

/** Đoạn diễn hoạt chính trên trang chủ, dựng bằng thành phần thật của ứng dụng cho ca DEMO-02. */
export function HeroAnimation() {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const isInView = useInView(containerRef, { once: true, amount: 0.35 })
  const prefersReducedMotion = useReducedMotion()

  const [runId, setRunId] = useState<number>(0)
  const [step, setStep] = useState<number>(() => (prefersReducedMotion ? 4 : 0))
  const [crclDisplay, setCrclDisplay] = useState<string>(() =>
    prefersReducedMotion ? '16,0' : '0,0',
  )

  const startSequence = useCallback(() => {
    if (prefersReducedMotion) {
      return () => {}
    }

    const timers: ReturnType<typeof setTimeout>[] = []
    let stopCounter: { stop: () => void } | null = null

    timers.push(setTimeout(() => {
      setStep(1)
      setCrclDisplay('0,0')
    }, 0))

    timers.push(
      setTimeout(() => {
        setStep(2)
        stopCounter = animate(0, TARGET_CRCL, {
          duration: 0.75,
          ease: 'easeOut',
          onUpdate(latest) {
            setCrclDisplay(formatCrclDecimal(latest))
          },
          onComplete() {
            setCrclDisplay('16,0')
          },
        })
      }, 260),
    )

    timers.push(
      setTimeout(() => {
        setStep(3)
      }, 1050),
    )

    timers.push(
      setTimeout(() => {
        setStep(4)
      }, 1480),
    )

    return () => {
      for (const timer of timers) {
        clearTimeout(timer)
      }
      stopCounter?.stop()
    }
  }, [prefersReducedMotion])

  useEffect(() => {
    if (prefersReducedMotion) {
      return
    }
    if (!isInView && runId === 0) {
      return
    }
    return startSequence()
  }, [isInView, runId, prefersReducedMotion, startSequence])

  const handleReplay = () => {
    setRunId((n) => n + 1)
  }

  const showRow = prefersReducedMotion || step >= 1
  const showCrcl = prefersReducedMotion || step >= 2
  const showBadge = prefersReducedMotion || step >= 3
  const showSource = prefersReducedMotion || step >= 4

  return (
    <div
      ref={containerRef}
      className="rounded-md border border-line bg-surface"
      aria-label="Mô phỏng quy trình thẩm định y lệnh trên ca DEMO-02"
    >
      <div className="flex items-center justify-between gap-3 border-b border-line bg-surface-muted/60 px-4 py-2.5">
        <div className="flex items-center gap-2 min-w-0">
          <RecordId id="DEMO-02" />
          <span className="text-xs text-fg-muted truncate">Nữ 75 tuổi · 50,0 kg · Hô hấp</span>
        </div>

        <Button
          variant="ghost"
          size="sm"
          iconLeft={<RotateCw className="size-3.5" strokeWidth={1.75} />}
          onClick={handleReplay}
        >
          Xem lại
        </Button>
      </div>

      <div className="p-4 flex flex-col gap-3">
        <motion.div
          initial={prefersReducedMotion ? false : { opacity: 0, y: 6 }}
          animate={showRow ? { opacity: 1, y: 0 } : { opacity: 0, y: 6 }}
          transition={{ duration: 0.2, ease: 'easeOut' }}
          className="flex flex-wrap items-center justify-between gap-2 rounded-sm border border-line bg-surface px-3 py-2.5"
        >
          <div className="min-w-0">
            <div className="text-sm font-medium text-fg">
              Meropenem 1 g · truyền tĩnh mạch · 3 lần/ngày
            </div>
            <div className="mt-0.5 font-mono text-xs text-fg-subtle tabular-nums">
              Creatinin máu: 212,0 µmol/L · 05:30 · 10/11/2026
            </div>
          </div>

          <motion.div
            initial={prefersReducedMotion ? false : { opacity: 0 }}
            animate={showBadge ? { opacity: 1 } : { opacity: 0 }}
            transition={{ duration: 0.18 }}
          >
            <Badge
              tone="danger"
              variant="soft"
              icon={<OctagonAlert className="size-3.5" strokeWidth={1.75} />}
            >
              Nghiêm trọng · Cần xem
            </Badge>
          </motion.div>
        </motion.div>

        <motion.div
          initial={prefersReducedMotion ? false : { opacity: 0, y: 6 }}
          animate={showCrcl ? { opacity: 1, y: 0 } : { opacity: 0, y: 6 }}
          transition={{ duration: 0.18, ease: 'easeOut' }}
          className="flex items-center justify-between gap-3 rounded-sm border border-danger-line bg-danger-bg/60 px-3 py-2"
        >
          <div className="text-xs font-medium text-fg-muted">
            Chỉ số tính toán · Cockcroft-Gault
          </div>
          <div className="flex items-baseline gap-1.5 font-mono tabular-nums">
            <span className="text-xs text-fg-subtle">CrCl</span>
            <span className="text-md font-semibold text-danger-fg">{prefersReducedMotion ? '16,0' : crclDisplay}</span>
            <span className="text-xs text-danger-fg">mL/phút</span>
          </div>
        </motion.div>

        <motion.div
          initial={prefersReducedMotion ? false : { opacity: 0, y: 8 }}
          animate={showSource ? { opacity: 1, y: 0 } : { opacity: 0, y: 8 }}
          transition={{ duration: 0.22, ease: 'easeOut' }}
          className="rounded-sm border border-line bg-surface-muted/40 p-3 flex flex-col gap-1.5"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-semibold text-fg">
              Nhãn FDA MERREM IV (meropenem) · Suy thận ở người lớn
            </span>
            <span className="font-mono text-2xs text-fg-subtle">Tầng 3</span>
          </div>
          <p className="border-l-2 border-line-strong pl-2.5 font-mono text-xs leading-relaxed text-fg-muted">
            CrCl (mL/phút):{' '}
            <mark className="rounded-sm bg-warning-bg px-1 py-0.5 font-medium text-fg">
              10-25 | One-half recommended dose | Every 12 hours
            </mark>
          </p>
        </motion.div>
      </div>
    </div>
  )
}
