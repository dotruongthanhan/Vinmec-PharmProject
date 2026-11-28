import * as DialogPrimitive from '@radix-ui/react-dialog'
import { cva } from 'class-variance-authority'
import type { VariantProps } from 'class-variance-authority'
import { X } from 'lucide-react'
import type { ComponentPropsWithRef } from 'react'
import { cn } from '@/lib/cn'

const dialogContentVariants = cva(
  'fixed z-50 flex flex-col bg-surface-raised shadow-xl focus:outline-none transition-[opacity,transform] duration-180 ease-out opacity-100',
  {
    variants: {
      variant: {
        fullscreen:
          'inset-4 overflow-hidden rounded-lg border border-line',
        record:
          'left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[calc(100vw-32px)] max-w-[640px] overflow-hidden rounded-lg border border-line scale-100 starting:opacity-0 starting:scale-[0.98]',
        source:
          'left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[calc(100vw-32px)] max-w-[800px] overflow-hidden rounded-lg border border-line scale-100 starting:opacity-0 starting:scale-[0.98]',
        'drawer-left':
          'inset-y-0 left-0 h-full w-[304px] max-w-[calc(100vw-48px)] border-r border-line translate-x-0 starting:opacity-0 starting:-translate-x-full',
        'drawer-right':
          'inset-y-0 right-0 h-full w-[384px] max-w-[calc(100vw-48px)] border-l border-line translate-x-0 starting:opacity-0 starting:translate-x-full',
      },
    },
    defaultVariants: {
      variant: 'record',
    },
  },
)

/** Gốc điều khiển trạng thái mở đóng hộp thoại hoặc ngăn trượt. */
export function Dialog(props: DialogPrimitive.DialogProps) {
  return <DialogPrimitive.Root {...props} />
}

/** Phần tử kích hoạt mở hộp thoại. */
export function DialogTrigger(
  props: ComponentPropsWithRef<typeof DialogPrimitive.Trigger>,
) {
  return <DialogPrimitive.Trigger {...props} />
}

/** Cổng đưa hộp thoại ra ngoài cây DOM hiện tại. */
export function DialogPortal(props: DialogPrimitive.DialogPortalProps) {
  return <DialogPrimitive.Portal {...props} />
}

/** Nút đóng hộp thoại theo ngữ cảnh Radix. */
export function DialogClose(
  props: ComponentPropsWithRef<typeof DialogPrimitive.Close>,
) {
  return <DialogPrimitive.Close {...props} />
}

/** Lớp nền mờ phía sau hộp thoại. */
export function DialogOverlay({
  className,
  ...props
}: ComponentPropsWithRef<typeof DialogPrimitive.Overlay>) {
  return (
    <DialogPrimitive.Overlay
      className={cn(
        'fixed inset-0 z-50 bg-overlay/55 transition-opacity duration-180 ease-out opacity-100 starting:opacity-0',
        className,
      )}
      {...props}
    />
  )
}

export interface DialogContentProps
  extends ComponentPropsWithRef<typeof DialogPrimitive.Content>,
    VariantProps<typeof dialogContentVariants> {}

/** Khung nội dung chính của hộp thoại (bản ghi, đoạn nguồn hoặc ngăn trượt hai bên). */
export function DialogContent({
  className,
  variant = 'record',
  tabIndex = -1,
  onCloseAutoFocus,
  children,
  ...props
}: DialogContentProps) {
  return (
    <DialogPortal>
      <DialogOverlay />
      <DialogPrimitive.Content
        tabIndex={tabIndex}
        onCloseAutoFocus={onCloseAutoFocus}
        className={cn(dialogContentVariants({ variant }), className)}
        {...props}
      >
        {children}
      </DialogPrimitive.Content>
    </DialogPortal>
  )
}

export interface DialogHeaderProps extends ComponentPropsWithRef<'div'> {
  showClose?: boolean
}

/** Phần đầu hộp thoại gồm tiêu đề và nút đóng X có aria-label tiếng Việt. */
export function DialogHeader({
  className,
  showClose = true,
  children,
  ...props
}: DialogHeaderProps) {
  return (
    <div
      className={cn(
        'flex shrink-0 items-start justify-between gap-4 border-b border-line px-6 py-4',
        className,
      )}
      {...props}
    >
      <div className="min-w-0 flex-1 space-y-1">{children}</div>
      {showClose ? (
        <DialogPrimitive.Close
          type="button"
          aria-label="Đóng"
          className="inline-flex size-7 min-h-7 min-w-7 shrink-0 cursor-pointer items-center justify-center rounded-sm text-fg-muted transition-colors duration-120 hover:bg-surface-muted hover:text-fg"
        >
          <X className="size-4" strokeWidth={1.75} aria-hidden="true" />
        </DialogPrimitive.Close>
      ) : null}
    </div>
  )
}

/** Tiêu đề hộp thoại. */
export function DialogTitle({
  className,
  ...props
}: ComponentPropsWithRef<typeof DialogPrimitive.Title>) {
  return (
    <DialogPrimitive.Title
      className={cn('text-md font-semibold text-fg leading-snug', className)}
      {...props}
    />
  )
}

/** Mô tả phụ dưới tiêu đề hộp thoại. */
export function DialogDescription({
  className,
  ...props
}: ComponentPropsWithRef<typeof DialogPrimitive.Description>) {
  return (
    <DialogPrimitive.Description
      className={cn('text-sm text-fg-muted', className)}
      {...props}
    />
  )
}

/** Phần thân hộp thoại có vùng cuộn riêng giới hạn 70vh. */
export function DialogBody({ className, ...props }: ComponentPropsWithRef<'div'>) {
  return (
    <div
      className={cn(
        'max-h-[70vh] flex-1 overflow-y-auto overscroll-contain px-6 py-4',
        className,
      )}
      {...props}
    />
  )
}

/** Phần chân hộp thoại chứa các nút hành động. */
export function DialogFooter({ className, ...props }: ComponentPropsWithRef<'div'>) {
  return (
    <div
      className={cn(
        'flex shrink-0 justify-end gap-2 border-t border-line bg-surface-muted/50 px-6 py-3',
        className,
      )}
      {...props}
    />
  )
}
