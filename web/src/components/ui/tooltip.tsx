import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import type { ComponentPropsWithRef } from 'react'
import { cn } from '@/lib/cn'

/** Nhà cung cấp ngữ cảnh tooltip toàn ứng dụng với độ trễ mặc định 300 ms. */
export function TooltipProvider({
  delayDuration = 300,
  ...props
}: TooltipPrimitive.TooltipProviderProps) {
  return <TooltipPrimitive.Provider delayDuration={delayDuration} {...props} />
}

/** Gốc điều khiển trạng thái đóng mở tooltip. */
export function Tooltip(props: TooltipPrimitive.TooltipProps) {
  return <TooltipPrimitive.Root {...props} />
}

/** Phần tử kích hoạt hiển thị tooltip khi di chuột hoặc lấy tiêu điểm bàn phím. */
export function TooltipTrigger(
  props: ComponentPropsWithRef<typeof TooltipPrimitive.Trigger>,
) {
  return <TooltipPrimitive.Trigger {...props} />
}

/** Nội dung chú giải nổi của tooltip. */
export function TooltipContent({
  className,
  sideOffset = 6,
  ...props
}: ComponentPropsWithRef<typeof TooltipPrimitive.Content>) {
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content
        sideOffset={sideOffset}
        className={cn(
          'z-50 max-w-64 rounded-sm bg-fg px-2.5 py-1.5 text-xs font-normal text-surface shadow-md transition-[opacity,transform] duration-120 ease-out opacity-100 scale-100 starting:opacity-0 starting:scale-95',
          className,
        )}
        {...props}
      />
    </TooltipPrimitive.Portal>
  )
}
