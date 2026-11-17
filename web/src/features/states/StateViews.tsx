import { ClipboardList } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty-state'
import { InlineAlert } from '@/components/ui/inline-alert'
import { Skeleton } from '@/components/ui/skeleton'

export interface ErrorStateProps {
  title: string
  message: string
  onRetry?: () => void
}

/** Khung xương khi đang tải hàng đợi ca bệnh. */
export function QueueSkeleton() {
  return (
    <div className="flex flex-col gap-2" aria-busy="true" aria-label="Đang tải hàng đợi">
      <Skeleton className="h-[76px] w-full" />
      <Skeleton className="h-[76px] w-full" />
      <Skeleton className="h-[76px] w-full" />
      <Skeleton className="h-[76px] w-full" />
      <Skeleton className="h-[76px] w-full" />
    </div>
  )
}

/** Khung xương khớp bố cục chi tiết ca bệnh khi đang tải. */
export function DetailSkeleton() {
  return (
    <div className="flex flex-col gap-6" aria-busy="true" aria-label="Đang tải chi tiết ca">
      <Skeleton className="h-14 w-full" />

      <div className="flex flex-col gap-3">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <Skeleton className="h-44 w-full" />
        <Skeleton className="h-44 w-full" />
      </div>
    </div>
  )
}

/** Thông báo lỗi tại chỗ kèm nút thử lại khi cần. */
export function ErrorState({ title, message, onRetry }: ErrorStateProps) {
  return (
    <InlineAlert
      tone="danger"
      role="alert"
      title={title}
      action={
        onRetry ? (
          <Button variant="secondary" size="sm" onClick={onRetry}>
            Thử lại
          </Button>
        ) : undefined
      }
    >
      <span className="whitespace-pre-wrap">{message}</span>
    </InlineAlert>
  )
}

/** Trạng thái hàng đợi không có y lệnh chờ thẩm định. */
export function EmptyQueueState() {
  return (
    <EmptyState
      role="status"
      icon={ClipboardList}
      title="Không có y lệnh chờ thẩm định"
    />
  )
}

/** Trạng thái vùng chính khi chưa chọn ca nào ở hàng đợi. */
export function EmptyDetailState() {
  return (
    <EmptyState
      role="status"
      icon={ClipboardList}
      title="Chọn một y lệnh ở danh sách bên trái"
    />
  )
}
