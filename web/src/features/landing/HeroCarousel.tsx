import { ChevronLeft, ChevronRight } from 'lucide-react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import type { ReactNode } from 'react'
import { useCallback, useEffect, useState } from 'react'
import { cn } from '@/lib/cn'

/** Thời gian giữa hai lần tự trượt (mili giây). */
export const HERO_SLIDE_INTERVAL_MS = 5000

export interface HeroSlide {
  id: string
  /** Ảnh nền tràn khung; lật ngang để chủ thể nằm bên phải, chữ nằm bên trái. */
  image: { src: string; alt: string; flip?: boolean; position?: string; pushRight?: boolean }
  /** Khối chữ nổi trên ảnh. */
  content: ReactNode
}

const EASE = [0.32, 0.72, 0, 1] as const

const slideVariants = {
  enter: (direction: number) => ({ x: direction > 0 ? '100%' : '-100%' }),
  center: { x: 0 },
  exit: (direction: number) => ({ x: direction > 0 ? '-100%' : '100%' }),
}

/** Banner tràn ngang: ảnh phủ kín, chữ nổi trên lớp tối; cứ sau vài giây slide mới trượt sang. */
export function HeroCarousel({
  slides,
  intervalMs = HERO_SLIDE_INTERVAL_MS,
}: {
  slides: readonly HeroSlide[]
  intervalMs?: number
}) {
  const prefersReducedMotion = useReducedMotion()
  const [[index, direction], setPage] = useState<[number, number]>([0, 1])
  const [paused, setPaused] = useState(false)
  const total = slides.length

  const goTo = useCallback(
    (next: number, dir: number) => {
      setPage([((next % total) + total) % total, dir])
    },
    [total],
  )

  // Hẹn giờ theo từng slide: bấm tay hoặc đổi slide sẽ tính lại từ đầu. Khi người dùng giảm chuyển động, vẫn tự chuyển nhưng đổi tức thì, không trượt.
  useEffect(() => {
    if (paused || total < 2) {
      return
    }
    const timer = window.setTimeout(() => goTo(index + 1, 1), intervalMs)
    return () => window.clearTimeout(timer)
  }, [index, paused, total, intervalMs, goTo])

  const slide = slides[index]

  return (
    <div
      role="region"
      aria-roledescription="carousel"
      aria-label="Giới thiệu hệ thống"
      className="group/hero relative h-[600px] w-full overflow-hidden bg-ink md:h-[640px] lg:h-[680px]"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <AnimatePresence initial={false} custom={direction}>
        <motion.div
          key={slide.id}
          custom={direction}
          variants={slideVariants}
          initial={prefersReducedMotion ? false : 'enter'}
          animate="center"
          exit={prefersReducedMotion ? undefined : 'exit'}
          transition={{ duration: prefersReducedMotion ? 0 : 0.7, ease: EASE }}
          role="group"
          aria-roledescription="slide"
          aria-label={`${index + 1} / ${total}`}
          className="absolute inset-0"
        >
          <img
            src={slide.image.src}
            alt={slide.image.alt}
            decoding="async"
            draggable={false}
            style={{ objectPosition: slide.image.position ?? 'center' }}
            className={cn('absolute inset-0 size-full object-cover', slide.image.flip && '-scale-x-100', slide.image.pushRight && 'origin-right scale-[1.3]')}
          />
          <div aria-hidden="true" className="hero-shade absolute inset-0" />
          <div className="relative mx-auto flex h-full max-w-[1200px] items-center px-6 pb-14">
            <div className="flex max-w-[640px] flex-col gap-6 text-ink-fg">{slide.content}</div>
          </div>
        </motion.div>
      </AnimatePresence>

      {total > 1 ? (
        <>
          <button
            type="button"
            aria-label="Slide trước"
            onClick={() => goTo(index - 1, -1)}
            className="absolute top-1/2 left-4 z-10 hidden size-10 -translate-y-1/2 cursor-pointer items-center justify-center rounded-full border border-ink-line bg-ink/55 text-ink-fg backdrop-blur-sm transition-colors duration-150 hover:bg-ink/80 sm:inline-flex"
          >
            <ChevronLeft className="size-5" strokeWidth={2} aria-hidden="true" />
          </button>
          <button
            type="button"
            aria-label="Slide sau"
            onClick={() => goTo(index + 1, 1)}
            className="absolute top-1/2 right-4 z-10 hidden size-10 -translate-y-1/2 cursor-pointer items-center justify-center rounded-full border border-ink-line bg-ink/55 text-ink-fg backdrop-blur-sm transition-colors duration-150 hover:bg-ink/80 sm:inline-flex"
          >
            <ChevronRight className="size-5" strokeWidth={2} aria-hidden="true" />
          </button>
          <div
            className="absolute inset-x-0 bottom-6 z-10 flex items-center justify-center gap-1.5"
            role="tablist"
            aria-label="Chọn slide"
          >
            {slides.map((item, dotIndex) => {
              const active = dotIndex === index
              return (
                <button
                  key={item.id}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  aria-label={`Chuyển tới slide ${dotIndex + 1}`}
                  onClick={() => goTo(dotIndex, dotIndex > index ? 1 : -1)}
                  className={cn(
                    'h-2 cursor-pointer rounded-full transition-all duration-300',
                    active ? 'w-8 bg-primary' : 'w-2 bg-ink-muted/60 hover:bg-ink-fg',
                  )}
                />
              )
            })}
          </div>
        </>
      ) : null}
    </div>
  )
}
