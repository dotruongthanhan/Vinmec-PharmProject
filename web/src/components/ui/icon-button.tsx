import type { TooltipContentProps } from '@radix-ui/react-tooltip'
import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'
import { Button } from './button'
import type { ButtonProps } from './button'
import { Tooltip, TooltipContent, TooltipTrigger } from './tooltip'

export interface IconButtonProps
  extends Omit<ButtonProps, 'children' | 'iconLeft' | 'aria-label'> {
  'aria-label': string
  tooltip?: string
  tooltipSide?: TooltipContentProps['side']
  icon: ReactNode
}

const SIZE_SQUARE_CLASS = {
  sm: 'w-7',
  md: 'w-8',
  lg: 'w-10',
} as const

/** Nút chỉ có biểu tượng, bắt buộc aria-label và tích hợp sẵn Tooltip. */
export function IconButton({
  ref,
  'aria-label': ariaLabel,
  tooltip,
  tooltipSide,
  variant = 'ghost',
  size = 'sm',
  icon,
  loading = false,
  className,
  ...props
}: IconButtonProps) {
  const label = tooltip ?? ariaLabel
  const squareClass = SIZE_SQUARE_CLASS[size ?? 'sm']

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          ref={ref}
          variant={variant}
          size={size}
          loading={loading}
          aria-label={ariaLabel}
          className={cn('min-w-7 min-h-7 p-0', squareClass, className)}
          {...props}
        >
          {loading ? null : (
            <span className="inline-flex shrink-0 items-center justify-center" aria-hidden="true">
              {icon}
            </span>
          )}
        </Button>
      </TooltipTrigger>
      <TooltipContent side={tooltipSide}>{label}</TooltipContent>
    </Tooltip>
  )
}
