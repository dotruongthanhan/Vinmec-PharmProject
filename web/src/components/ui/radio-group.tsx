import * as RadioGroupPrimitive from '@radix-ui/react-radio-group'
import type { ComponentPropsWithRef } from 'react'
import { cn } from '@/lib/cn'

/** Nhóm nút chọn đơn dạng radio chuẩn theo Radix RadioGroup. */
export function RadioGroup({
  className,
  ...props
}: ComponentPropsWithRef<typeof RadioGroupPrimitive.Root>) {
  return (
    <RadioGroupPrimitive.Root
      className={cn('grid gap-2', className)}
      {...props}
    />
  )
}

/** Một lựa chọn dạng chấm tròn bên trong RadioGroup. */
export function RadioGroupItem({
  className,
  ...props
}: ComponentPropsWithRef<typeof RadioGroupPrimitive.Item>) {
  return (
    <RadioGroupPrimitive.Item
      className={cn(
        'inline-flex aspect-square size-4 cursor-pointer items-center justify-center rounded-full border border-line-strong bg-surface text-primary shadow-xs transition-colors duration-120 data-[state=checked]:border-primary disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    >
      <RadioGroupPrimitive.Indicator className="flex items-center justify-center">
        <span className="size-2 rounded-full bg-primary" />
      </RadioGroupPrimitive.Indicator>
    </RadioGroupPrimitive.Item>
  )
}

/** Nhóm lựa chọn radio trình bày dạng hàng thẻ viên linh hoạt (dùng chọn nhóm lý do). */
export function RadioPillGroup({
  className,
  ...props
}: ComponentPropsWithRef<typeof RadioGroupPrimitive.Root>) {
  return (
    <RadioGroupPrimitive.Root
      className={cn('flex flex-wrap items-center gap-2', className)}
      {...props}
    />
  )
}

/** Một lựa chọn radio dạng viên thuốc có vùng bấm tối thiểu 28 px. */
export function RadioPillItem({
  className,
  ...props
}: ComponentPropsWithRef<typeof RadioGroupPrimitive.Item>) {
  return (
    <RadioGroupPrimitive.Item
      className={cn(
        'inline-flex min-h-7 cursor-pointer items-center justify-center rounded-full border border-line-strong bg-surface px-3 py-1 text-xs text-fg-muted transition-colors duration-120 hover:border-primary/60 hover:text-fg disabled:pointer-events-none disabled:opacity-50 data-[state=checked]:border-primary-line data-[state=checked]:bg-primary-soft data-[state=checked]:font-medium data-[state=checked]:text-primary',
        className,
      )}
      {...props}
    />
  )
}
