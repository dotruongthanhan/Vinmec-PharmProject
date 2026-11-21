import { cn } from '@/lib/cn'

/**
 * Logo ứng dụng (chữ V kết hợp dấu thập y tế), nền trong suốt.
 * Một file SVG dùng cho cả nền sáng và nền tối; prop alwaysOnDark giữ để tương thích, không còn đổi ảnh.
 */
export function AppLogo({
  className,
  imageClassName,
}: {
  className?: string
  imageClassName?: string
  /** Giữ để tương thích với chỗ gọi cũ; logo SVG dùng chung cho mọi chủ đề. */
  alwaysOnDark?: boolean
}) {
  return (
    <span className={cn('inline-flex shrink-0 items-center', className)}>
      <img
        src="/logo-y-te.svg"
        alt="Logo Thẩm định y lệnh"
        draggable={false}
        className={cn('h-10 w-auto select-none', imageClassName)}
      />
    </span>
  )
}
