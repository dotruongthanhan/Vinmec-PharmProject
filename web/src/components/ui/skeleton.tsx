import type { ComponentPropsWithRef } from 'react'
import { cn } from '@/lib/cn'

export type SkeletonProps = ComponentPropsWithRef<'div'>

/** Khối giữ chỗ khi đang nạp dữ liệu. */
export function Skeleton({ ref, className, ...props }: SkeletonProps) {
  return (
    <div
      ref={ref}
      aria-hidden={props['aria-hidden'] ?? true}
      className={cn('ui-skeleton animate-pulse rounded-md bg-surface-muted', className)}
      {...props}
    />
  )
}
