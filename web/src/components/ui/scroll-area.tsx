import * as ScrollAreaPrimitive from '@radix-ui/react-scroll-area'
import type { ComponentPropsWithRef } from 'react'
import { cn } from '@/lib/cn'

export interface ScrollAreaProps
  extends ComponentPropsWithRef<typeof ScrollAreaPrimitive.Root> {
  viewportClassName?: string
}

/** Vùng cuộn tuỳ biến dùng Radix ScrollArea với thanh cuộn mảnh. */
export function ScrollArea({
  className,
  viewportClassName,
  children,
  ...props
}: ScrollAreaProps) {
  return (
    <ScrollAreaPrimitive.Root
      className={cn('relative overflow-hidden', className)}
      {...props}
    >
      <ScrollAreaPrimitive.Viewport
        className={cn('size-full rounded-[inherit]', viewportClassName)}
      >
        {children}
      </ScrollAreaPrimitive.Viewport>
      <ScrollBar />
      <ScrollAreaPrimitive.Corner />
    </ScrollAreaPrimitive.Root>
  )
}

/** Thanh cuộn dọc hoặc ngang với tay cầm mảnh, dịu mắt. */
export function ScrollBar({
  className,
  orientation = 'vertical',
  ...props
}: ComponentPropsWithRef<typeof ScrollAreaPrimitive.ScrollAreaScrollbar>) {
  return (
    <ScrollAreaPrimitive.ScrollAreaScrollbar
      orientation={orientation}
      className={cn(
        'flex touch-none select-none transition-colors duration-120',
        orientation === 'vertical'
          ? 'h-full w-2 border-l border-l-transparent p-px'
          : 'h-2 flex-col border-t border-t-transparent p-px',
        className,
      )}
      {...props}
    >
      <ScrollAreaPrimitive.ScrollAreaThumb className="relative flex-1 rounded-full bg-line-strong/70 transition-colors duration-120 hover:bg-fg-disabled" />
    </ScrollAreaPrimitive.ScrollAreaScrollbar>
  )
}
