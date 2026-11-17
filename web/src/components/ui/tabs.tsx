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
      className={cn('tabs-scroller items-center gap-5 border-b border-line px-4', className)}
      {...props}
    />
  )
}

/** Nút chọn một thẻ nội dung với gạch chân nét liền theo aria-selected khi đang chọn. */
export function TabsTrigger({
  className,
  ...props
}: ComponentPropsWithRef<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        "relative shrink-0 cursor-pointer whitespace-nowrap py-2.5 text-sm font-medium text-fg-muted transition-colors duration-120 hover:text-fg disabled:pointer-events-none disabled:opacity-50 aria-[selected=true]:text-fg data-[state=active]:text-fg after:content-[''] after:pointer-events-none after:absolute after:inset-x-0 after:bottom-0 after:border-b-2 after:border-transparent aria-[selected=true]:after:border-primary data-[state=active]:after:border-primary",
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
