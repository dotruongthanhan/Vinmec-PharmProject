import { cva } from 'class-variance-authority'
import type { ComponentPropsWithRef, ReactNode } from 'react'
import { cn } from '@/lib/cn'
import { ICON_OF_TONE } from '@/lib/severity'
import type { SemanticTone } from '@/lib/severity'

const inlineAlertVariants = cva(
  'flex items-start justify-between gap-3 rounded-md border px-3 py-2.5 text-sm',
  {
    variants: {
      tone: {
        danger: 'border-danger-line bg-danger-bg text-danger-fg',
        warning: 'border-warning-line bg-warning-bg text-warning-fg',
        missing: 'border-missing-line bg-missing-bg text-missing-fg',
        offlabel: 'border-offlabel-line bg-offlabel-bg text-offlabel-fg',
        success: 'border-success-line bg-success-bg text-success-fg',
        ai: 'border-ai-line bg-ai-bg text-ai-fg',
        neutral: 'border-neutral-line bg-neutral-bg text-neutral-fg',
      } satisfies Record<SemanticTone, string>,
    },
    defaultVariants: {
      tone: 'neutral',
    },
  },
)

export interface InlineAlertProps
  extends Omit<ComponentPropsWithRef<'div'>, 'title' | 'role'> {
  tone?: SemanticTone
  icon?: ReactNode
  title?: string
  children: ReactNode
  action?: ReactNode
  role?: 'status' | 'alert'
  ariaLive?: 'polite' | 'assertive'
}

/** Dải thông báo nội tuyến theo 7 tông màu nghĩa kèm biểu tượng và hành động tuỳ chọn. */
export function InlineAlert({
  ref,
  tone = 'neutral',
  icon,
  title,
  children,
  action,
  role,
  ariaLive,
  className,
  ...props
}: InlineAlertProps) {
  const DefaultIcon = ICON_OF_TONE[tone]
  const resolvedIcon =
    icon === undefined ? (
      <DefaultIcon
        size={16}
        strokeWidth={1.75}
        className="mt-0.5 shrink-0"
        aria-hidden="true"
      />
    ) : icon !== null && typeof icon !== 'boolean' ? (
      <span
        className="mt-0.5 inline-flex shrink-0 items-center [&_svg]:size-4"
        aria-hidden="true"
      >
        {icon}
      </span>
    ) : null

  return (
    <div
      ref={ref}
      className={cn(inlineAlertVariants({ tone }), className)}
      {...props}
      role={role}
      aria-live={ariaLive ?? props['aria-live']}
    >
      <div className="flex min-w-0 flex-1 items-start gap-2">
        {resolvedIcon}
        <div className="min-w-0 flex-1">
          {title && <div className="font-semibold leading-5">{title}</div>}
          <div className={cn(title && 'mt-0.5')}>{children}</div>
        </div>
      </div>
      {action && (
        <div className="flex shrink-0 items-center gap-2 self-center">{action}</div>
      )}
    </div>
  )
}
