import { cva } from 'class-variance-authority'
import type { VariantProps } from 'class-variance-authority'
import type { ComponentPropsWithRef, ReactNode } from 'react'
import { cn } from '@/lib/cn'
import type { SemanticTone } from '@/lib/severity'

/** Khai báo biến thể nhãn dạng viên theo 7 tông màu nghĩa và kiểu hiển thị. */
// oxlint-disable-next-line react/only-export-components
export const badgeVariants = cva(
  'inline-flex min-h-[22px] items-center gap-1.5 whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium',
  {
    variants: {
      tone: {
        danger: 'text-danger-fg border-danger-line',
        warning: 'text-warning-fg border-warning-line',
        missing: 'text-missing-fg border-missing-line',
        offlabel: 'text-offlabel-fg border-offlabel-line',
        success: 'text-success-fg border-success-line',
        ai: 'text-ai-fg border-ai-line',
        neutral: 'text-neutral-fg border-neutral-line',
      } satisfies Record<SemanticTone, string>,
      variant: {
        soft: '',
        outline: 'bg-surface',
      },
    },
    compoundVariants: [
      { tone: 'danger', variant: 'soft', className: 'bg-danger-bg' },
      { tone: 'warning', variant: 'soft', className: 'bg-warning-bg' },
      { tone: 'missing', variant: 'soft', className: 'bg-missing-bg' },
      { tone: 'offlabel', variant: 'soft', className: 'bg-offlabel-bg' },
      { tone: 'success', variant: 'soft', className: 'bg-success-bg' },
      { tone: 'ai', variant: 'soft', className: 'bg-ai-bg' },
      { tone: 'neutral', variant: 'soft', className: 'bg-neutral-bg' },
    ],
    defaultVariants: {
      tone: 'neutral',
      variant: 'soft',
    },
  },
)

export interface BadgeProps
  extends ComponentPropsWithRef<'span'>,
    VariantProps<typeof badgeVariants> {
  tone?: SemanticTone
  variant?: 'soft' | 'outline'
  icon?: ReactNode
}

/** Nhãn hiển thị trạng thái, số đếm hoặc nguồn gốc với biểu tượng tuỳ chọn. */
export function Badge({
  ref,
  className,
  tone = 'neutral',
  variant = 'soft',
  icon,
  children,
  ...props
}: BadgeProps) {
  return (
    <span
      ref={ref}
      className={cn(badgeVariants({ tone, variant }), className)}
      {...props}
    >
      {icon && (
        <span
          className="inline-flex size-3.5 shrink-0 items-center justify-center [&_svg]:size-3.5"
          aria-hidden="true"
        >
          {icon}
        </span>
      )}
      {children}
    </span>
  )
}
