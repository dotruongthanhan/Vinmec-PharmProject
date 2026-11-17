import * as PopoverPrimitive from '@radix-ui/react-popover'
import type { ComponentPropsWithRef } from 'react'
import { cn } from '@/lib/cn'

/** Gốc điều khiển trạng thái đóng mở Popover. */
export function Popover(props: PopoverPrimitive.PopoverProps) {
  return <PopoverPrimitive.Root {...props} />
}

/** Phần tử kích hoạt mở Popover. */
export function PopoverTrigger(
  props: ComponentPropsWithRef<typeof PopoverPrimitive.Trigger>,
) {
  return <PopoverPrimitive.Trigger {...props} />
}

/** Nút đóng Popover theo ngữ cảnh Radix. */
export function PopoverClose(
  props: ComponentPropsWithRef<typeof PopoverPrimitive.Close>,
) {
  return <PopoverPrimitive.Close {...props} />
}

/** Khung nội dung nổi của Popover, kết xuất qua Portal để tránh bị cắt bởi vùng cuộn. */
export function PopoverContent({
  className,
  align = 'center',
  sideOffset = 6,
  collisionPadding = 16,
  ...props
}: ComponentPropsWithRef<typeof PopoverPrimitive.Content>) {
  return (
    <PopoverPrimitive.Portal>
      <PopoverPrimitive.Content
        align={align}
        sideOffset={sideOffset}
        collisionPadding={collisionPadding}
        className={cn(
          'z-50 w-96 max-w-[calc(100vw-32px)] rounded-md border border-line bg-surface-raised p-4 text-sm text-fg shadow-md focus:outline-none transition-[opacity,transform] duration-120 ease-out opacity-100 scale-100 starting:opacity-0 starting:scale-[0.98]',
          className,
        )}
        {...props}
      />
    </PopoverPrimitive.Portal>
  )
}
