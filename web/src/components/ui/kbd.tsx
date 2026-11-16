import type { ComponentPropsWithRef } from 'react'
import { cn } from '@/lib/cn'

export type KbdProps = ComponentPropsWithRef<'kbd'>

/** Nhãn hiển thị phím tắt với phông mono và viền mảnh. */
export function Kbd({ ref, className, ...props }: KbdProps) {
  return (
    <kbd
      ref={ref}
      className={cn(
        'inline-flex items-center justify-center rounded-sm border border-line bg-surface-muted px-1.5 py-0.5 font-mono text-2xs leading-none text-fg-muted select-none',
        className,
      )}
      {...props}
    />
  )
}
