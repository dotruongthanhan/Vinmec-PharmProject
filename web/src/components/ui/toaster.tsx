import {
  CircleCheck,
  Info,
  LoaderCircle,
  OctagonAlert,
  TriangleAlert,
  X,
} from 'lucide-react'
import { Toaster as SonnerToaster, toast as sonnerToast } from 'sonner'
import type { ToasterProps } from 'sonner'
import { useTheme } from '@/features/theme/useTheme'

/** Khung thông báo nổi góc dưới phải, theo chế độ màu hiện tại. */
export function Toaster({
  position = 'bottom-right',
  duration = 4000,
  theme,
  closeButton = true,
  offset = { bottom: 88, right: 16 },
  toastOptions,
  icons,
  ...props
}: ToasterProps) {
  const { theme: resolvedTheme } = useTheme()
  return (
    <SonnerToaster
      position={position}
      duration={duration}
      theme={theme ?? resolvedTheme}
      closeButton={closeButton}
      offset={offset}
      icons={{
        success: (
          <CircleCheck className="size-4 shrink-0" strokeWidth={1.75} aria-hidden="true" />
        ),
        info: <Info className="size-4 shrink-0" strokeWidth={1.75} aria-hidden="true" />,
        warning: (
          <TriangleAlert className="size-4 shrink-0" strokeWidth={1.75} aria-hidden="true" />
        ),
        error: (
          <OctagonAlert className="size-4 shrink-0" strokeWidth={1.75} aria-hidden="true" />
        ),
        loading: (
          <LoaderCircle
            className="size-4 shrink-0 animate-spin"
            strokeWidth={1.75}
            aria-hidden="true"
          />
        ),
        close: <X className="size-3.5 shrink-0" strokeWidth={1.75} aria-hidden="true" />,
        ...icons,
      }}
      toastOptions={{
        ...toastOptions,
        unstyled: toastOptions?.unstyled ?? true,
        closeButtonAriaLabel: toastOptions?.closeButtonAriaLabel ?? 'Đóng thông báo',
        classNames: {
          toast:
            'group pointer-events-auto relative flex w-full items-start gap-2.5 rounded-md border p-3.5 pr-9 text-sm shadow-md',
          default: 'bg-surface border-line text-fg',
          loading: 'bg-surface border-line text-fg',
          success: 'bg-success-bg border-success-line text-success-fg',
          error: 'bg-danger-bg border-danger-line text-danger-fg',
          warning: 'bg-warning-bg border-warning-line text-warning-fg',
          info: 'bg-missing-bg border-missing-line text-missing-fg',
          icon: 'mt-0.5 flex size-4 shrink-0 items-center justify-center',
          content: 'flex min-w-0 flex-1 flex-col gap-0.5',
          title: 'text-sm font-medium leading-snug',
          description: 'text-xs text-fg-muted leading-normal',
          actionButton:
            'inline-flex h-7 shrink-0 cursor-pointer items-center justify-center rounded-sm bg-primary px-2.5 text-xs font-medium text-on-primary transition-colors duration-120 hover:bg-primary-hover',
          cancelButton:
            'inline-flex h-7 shrink-0 cursor-pointer items-center justify-center rounded-sm border border-line-strong bg-surface px-2.5 text-xs font-medium text-fg transition-colors duration-120 hover:bg-surface-hover',
          closeButton:
            'absolute right-1.5 top-1.5 inline-flex size-7 cursor-pointer items-center justify-center rounded-sm text-fg-subtle transition-colors duration-120 hover:bg-surface-muted/80 hover:text-fg',
          ...toastOptions?.classNames,
        },
      }}
      {...props}
    />
  )
}

// Cho phép xuất kèm helper toast từ toaster.tsx theo đúng quy ước sử dụng của ứng dụng.
// oxlint-disable-next-line react/only-export-components
export const toast: typeof sonnerToast = Object.assign(
  (...args: Parameters<typeof sonnerToast>) => sonnerToast(...args),
  sonnerToast,
  {
    error: (
      ...[message, data]: Parameters<typeof sonnerToast.error>
    ): ReturnType<typeof sonnerToast.error> =>
      sonnerToast.error(message, { duration: Infinity, ...data }),
  },
)
