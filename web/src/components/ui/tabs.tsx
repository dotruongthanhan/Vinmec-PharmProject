import * as TabsPrimitive from '@radix-ui/react-tabs'
import type { ComponentPropsWithRef } from 'react'
import { cn } from '@/lib/cn'

/** Gốc điều khiển nhóm thẻ chuyển nội dung theo chuẩn Radix Tabs. */
export function Tabs(props: ComponentPropsWithRef<typeof TabsPrimitive.Root>) {
  return <TabsPrimitive.Root {...props} />
}

/** Thanh danh sách các nút chọn thẻ có viền gạch dưới. */
export function TabsList({
  className,
  ...props
}: ComponentPropsWithRef<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn('flex items-center gap-6 border-b border-line px-4', className)}
      {...props}
    />
  )
}

/** Nút chọn một thẻ nội dung với gạch chân nhấn màu primary khi đang chọn. */
export function TabsTrigger({
  className,
  ...props
}: ComponentPropsWithRef<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        "relative cursor-pointer whitespace-nowrap py-2.5 text-sm font-medium text-fg-muted transition-colors duration-120 hover:text-fg disabled:pointer-events-none disabled:opacity-50 data-[state=active]:font-semibold data-[state=active]:text-primary after:content-[''] after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:bg-transparent data-[state=active]:after:bg-primary",
        className,
      )}
      {...props}
    />
  )
}

/** Vùng hiển thị nội dung ứng với thẻ đang được chọn. */
export function TabsContent({
  className,
  ...props
}: ComponentPropsWithRef<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      className={cn('focus-visible:outline-none', className)}
      {...props}
    />
  )
}
