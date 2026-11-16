import type { LucideIcon } from 'lucide-react'
import { isValidElement } from 'react'
import type { ComponentPropsWithRef, ReactNode } from 'react'
import { cn } from '@/lib/cn'

export interface EmptyStateProps extends ComponentPropsWithRef<'div'> {
  icon?: LucideIcon | ReactNode
  title: string
  description?: string
  action?: ReactNode
}

function isLucideComponent(icon: LucideIcon | ReactNode): icon is LucideIcon {
  if (typeof icon === 'function') {
    return true
  }
  if (typeof icon === 'object' && icon !== null && !isValidElement(icon)) {
    return '$$typeof' in icon && ('render' in icon || 'type' in icon)
  }
  return false
}

/** Khối trạng thái rỗng canh giữa gồm biểu tượng, tiêu đề, mô tả và nút tuỳ chọn. */
export function EmptyState({
  ref,
  icon,
  title,
  description,
  action,
  className,
  ...props
}: EmptyStateProps) {
  let renderedIcon: ReactNode = null

  if (isLucideComponent(icon)) {
    const IconComponent = icon
    renderedIcon = (
      <IconComponent
        size={32}
        strokeWidth={1.75}
        className="text-fg-disabled"
        aria-hidden="true"
      />
    )
  } else if (icon !== undefined && icon !== null && typeof icon !== 'boolean') {
    renderedIcon = icon
  }

  return (
    <div
      ref={ref}
      className={cn(
        'flex flex-col items-center justify-center px-6 py-8 text-center',
        className,
      )}
      {...props}
    >
      {renderedIcon && (
        <div
          className="mb-3 flex items-center justify-center text-fg-disabled [&_svg]:size-8"
          aria-hidden="true"
        >
          {renderedIcon}
        </div>
      )}
      <p className="text-md font-semibold text-fg">{title}</p>
      {description && (
        <p className="mt-1 max-w-md text-sm text-fg-muted">{description}</p>
      )}
      {action && (
        <div className="mt-4 flex items-center justify-center">{action}</div>
      )}
    </div>
  )
}
