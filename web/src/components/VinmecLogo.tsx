import { cn } from '@/lib/cn'

/**
 * Logo Vinmec nền trong suốt, không viền hay ô trắng bao quanh.
 * Nền sáng dùng bản gốc (chữ xanh navy); nền tối dùng bản chữ trắng ngà, giữ nguyên cánh chim vàng.
 */
export function VinmecLogo({
  className,
  imageClassName,
  alwaysOnDark = false,
}: {
  className?: string
  imageClassName?: string
  /** Đặt trên nền luôn tối (như thanh bên): chỉ dùng bản chữ sáng, bất kể chủ đề. */
  alwaysOnDark?: boolean
}) {
  const image = cn('h-10 w-auto select-none', imageClassName)
  return (
    <span className={cn('inline-flex shrink-0 items-center', className)}>
      {alwaysOnDark ? (
        <img
          src="/vinmec-logo-dark.png"
          alt="Vinmec Healthcare System"
          draggable={false}
          className={image}
        />
      ) : (
        <>
          <img
            src="/vinmec-logo.png"
            alt="Vinmec Healthcare System"
            draggable={false}
            className={cn('logo-on-light', image)}
          />
          <img
            src="/vinmec-logo-dark.png"
            alt=""
            aria-hidden="true"
            draggable={false}
            className={cn('logo-on-dark', image)}
          />
        </>
      )}
    </span>
  )
}
