import { Slot, Slottable } from '@radix-ui/react-slot'
import { cva } from 'class-variance-authority'
import type { VariantProps } from 'class-variance-authority'
import { LoaderCircle } from 'lucide-react'
import type { ComponentPropsWithRef, HTMLAttributes, ReactNode, Ref } from 'react'
import { cn } from '@/lib/cn'

/** Khai báo biến thể kiểu dáng và kích thước cho nút bấm. */
// oxlint-disable-next-line react/only-export-components
export const buttonVariants = cva(
  'inline-flex items-center justify-center whitespace-nowrap rounded-sm border font-medium transition-colors duration-120 select-none cursor-pointer disabled:pointer-events-none disabled:opacity-50 aria-disabled:pointer-events-none aria-disabled:opacity-50',
  {
    variants: {
      variant: {
        primary: 'border-transparent bg-primary text-on-primary hover:bg-primary-hover',
        secondary:
          'border-line-strong bg-surface text-fg hover:bg-surface-hover',
        ghost:
          'border-transparent bg-transparent text-fg-muted hover:bg-surface-muted hover:text-fg',
        soft: 'border-transparent bg-primary-soft text-primary hover:bg-primary-line/40',
        'danger-ghost': 'border-transparent bg-transparent text-danger-fg hover:bg-danger-bg',
      },
      size: {
        sm: 'h-7 px-2.5 text-xs gap-1.5',
        md: 'h-8 px-3 text-sm gap-1.5',
        lg: 'h-10 px-4 text-base gap-2',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  },
)

export interface ButtonProps
  extends ComponentPropsWithRef<'button'>,
    VariantProps<typeof buttonVariants> {
  loading?: boolean
  iconLeft?: ReactNode
  asChild?: boolean
}

/** Nút bấm nền tảng hỗ trợ trạng thái chờ, biểu tượng trái và asChild. */
export function Button({
  ref,
  className,
  variant,
  size,
  loading = false,
  iconLeft,
  asChild = false,
  disabled,
  type,
  children,
  ...props
}: ButtonProps) {
  const isDisabled = Boolean(disabled || loading)
  const classes = cn(buttonVariants({ variant, size }), className)
  const leadingContent = loading ? (
    <LoaderCircle
      className="size-4 animate-spin shrink-0"
      strokeWidth={1.75}
      aria-hidden="true"
    />
  ) : iconLeft ? (
    <span className="inline-flex shrink-0 items-center" aria-hidden="true">
      {iconLeft}
    </span>
  ) : null

  if (asChild) {
    const slotProps = props as HTMLAttributes<HTMLElement>
    return (
      <Slot
        ref={ref as Ref<HTMLElement>}
        className={classes}
        aria-busy={loading || undefined}
        aria-disabled={isDisabled || undefined}
        {...slotProps}
        onClick={
          isDisabled
            ? (event) => {
                event.preventDefault()
                event.stopPropagation()
              }
            : slotProps.onClick
        }
      >
        {leadingContent}
        <Slottable>{children}</Slottable>
      </Slot>
    )
  }

  return (
    <button
      ref={ref}
      type={type ?? 'button'}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      className={classes}
      {...props}
    >
      {leadingContent}
      {children}
    </button>
  )
}
