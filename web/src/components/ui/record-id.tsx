import type { ComponentPropsWithRef } from 'react'
import { cn } from '@/lib/cn'

export interface RecordIdProps extends Omit<ComponentPropsWithRef<'span'>, 'id'> {
  id: string
}

/** Nhãn hiển thị mã bản ghi lâm sàng bằng phông mono đều cột. */
export function RecordId({ ref, id, className, ...props }: RecordIdProps) {
  return (
    <span
      ref={ref}
      className={cn(
        'inline-flex items-center rounded-sm border border-line bg-surface-muted px-1.5 py-0.5 font-mono text-xs text-fg-subtle tabular-nums whitespace-nowrap',
        className,
      )}
      {...props}
    >
      {id}
    </span>
  )
}
