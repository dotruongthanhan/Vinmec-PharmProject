import * as CollapsiblePrimitive from '@radix-ui/react-collapsible'
import { ChevronRight } from 'lucide-react'
import type { LucideProps } from 'lucide-react'
import type { ComponentPropsWithRef } from 'react'
import { cn } from '@/lib/cn'

/** Gốc điều khiển khối đóng mở thu gọn. */
export function Collapsible(
  props: ComponentPropsWithRef<typeof CollapsiblePrimitive.Root>,
) {
  return <CollapsiblePrimitive.Root {...props} />
}

/** Nút kích hoạt mở hoặc thu gọn nội dung, gắn sẵn lớp group cho biểu tượng mũi tên. */
export function CollapsibleTrigger({
  className,
  ...props
}: ComponentPropsWithRef<typeof CollapsiblePrimitive.Trigger>) {
  return (
    <CollapsiblePrimitive.Trigger
      className={cn('group', className)}
      {...props}
    />
  )
}

/** Vùng nội dung được ẩn hiện theo trạng thái Collapsible. */
export function CollapsibleContent({
  className,
  ...props
}: ComponentPropsWithRef<typeof CollapsiblePrimitive.Content>) {
  return (
    <CollapsiblePrimitive.Content className={cn(className)} {...props} />
  )
}

export type CollapsibleChevronProps = Omit<LucideProps, 'ref'>

/** Biểu tượng mũi tên xoay 90 độ theo trạng thái mở của CollapsibleTrigger. */
export function CollapsibleChevron({
  className,
  size = 16,
  strokeWidth = 1.75,
  ...props
}: CollapsibleChevronProps) {
  return (
    <ChevronRight
      size={size}
      strokeWidth={strokeWidth}
      aria-hidden="true"
      className={cn(
        'shrink-0 transition-transform duration-180 ease-out group-data-[state=open]:rotate-90',
        className,
      )}
      {...props}
    />
  )
}
