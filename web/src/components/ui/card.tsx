import type { ComponentPropsWithRef } from 'react'
import { cn } from '@/lib/cn'

export type CardProps = ComponentPropsWithRef<'div'>

/** Khung thẻ bề mặt trắng chuẩn với viền mảnh và bóng nhẹ. */
export function Card({ ref, className, ...props }: CardProps) {
  return (
    <div
      ref={ref}
      className={cn('rounded-md border border-line bg-surface shadow-xs', className)}
      {...props}
    />
  )
}

export interface CardHeaderProps extends ComponentPropsWithRef<'div'> {
  borderless?: boolean
}

/** Phần đầu thẻ chứa tiêu đề và vùng hành động bên phải. */
export function CardHeader({
  ref,
  className,
  borderless = false,
  ...props
}: CardHeaderProps) {
  return (
    <div
      ref={ref}
      className={cn(
        'flex items-center justify-between gap-3 px-4 py-3',
        !borderless && 'border-b border-line',
        className,
      )}
      {...props}
    />
  )
}

export type CardTitleProps = ComponentPropsWithRef<'h3'>

/** Tiêu đề chính trong phần đầu thẻ. */
export function CardTitle({ ref, className, ...props }: CardTitleProps) {
  return (
    <h3
      ref={ref}
      className={cn('text-md font-semibold text-fg', className)}
      {...props}
    />
  )
}

export type CardActionProps = ComponentPropsWithRef<'div'>

/** Vùng đặt nút hoặc nhãn hành động ở góc phải đầu thẻ. */
export function CardAction({ ref, className, ...props }: CardActionProps) {
  return (
    <div
      ref={ref}
      className={cn('flex shrink-0 items-center gap-2', className)}
      {...props}
    />
  )
}

export type CardBodyProps = ComponentPropsWithRef<'div'>

/** Phần thân nội dung bên trong thẻ với lề trong đồng nhất 16px. */
export function CardBody({ ref, className, ...props }: CardBodyProps) {
  return <div ref={ref} className={cn('p-4', className)} {...props} />
}
