import * as ToggleGroupPrimitive from '@radix-ui/react-toggle-group'
import { useState } from 'react'
import type { ComponentPropsWithRef } from 'react'
import { cn } from '@/lib/cn'

export interface SegmentedControlProps
  extends Omit<
    ComponentPropsWithRef<typeof ToggleGroupPrimitive.Root>,
    'type' | 'value' | 'defaultValue' | 'onValueChange'
  > {
  value?: string
  defaultValue?: string
  onValueChange?: (value: string) => void
}

/** Nhóm nút phân đoạn chọn một mục duy nhất, không cho bỏ chọn về rỗng. */
export function SegmentedControl({
  className,
  value,
  defaultValue,
  onValueChange,
  ...props
}: SegmentedControlProps) {
  const [internalValue, setInternalValue] = useState<string>(defaultValue ?? '')
  const currentValue = value !== undefined ? value : internalValue

  const handleValueChange = (nextValue: string) => {
    if (!nextValue) {
      return
    }
    if (value === undefined) {
      setInternalValue(nextValue)
    }
    onValueChange?.(nextValue)
  }

  return (
    <ToggleGroupPrimitive.Root
      type="single"
      value={currentValue}
      onValueChange={handleValueChange}
      className={cn(
        'inline-flex items-center gap-0.5 rounded-sm border border-line/60 bg-surface-muted p-1',
        className,
      )}
      {...props}
    />
  )
}

/** Một mục chọn bên trong thanh phân đoạn. */
export function SegmentedControlItem({
  className,
  ...props
}: ComponentPropsWithRef<typeof ToggleGroupPrimitive.Item>) {
  return (
    <ToggleGroupPrimitive.Item
      className={cn(
        'cursor-pointer whitespace-nowrap rounded-sm px-2.5 py-1 text-xs font-medium text-fg-muted transition-all duration-120 hover:text-fg disabled:pointer-events-none disabled:opacity-50 data-[state=on]:bg-surface data-[state=on]:font-semibold data-[state=on]:text-fg data-[state=on]:shadow-xs',
        className,
      )}
      {...props}
    />
  )
}
