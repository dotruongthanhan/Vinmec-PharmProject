import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'

/** Trang 404 khi đường dẫn không tồn tại. */
export function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-paper px-6 text-center text-fg">
      <div className="max-w-md space-y-4">
        <p className="font-mono text-xs text-fg-subtle">404</p>
        <h1 className="font-serif text-[28px] leading-[36px] font-normal text-fg">
          Không tìm thấy trang này
        </h1>
        <p className="text-sm text-fg-muted leading-relaxed">
          Đường dẫn không tồn tại hoặc đã thay đổi. Quay về trang chủ hoặc bàn làm việc để tiếp
          tục.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-2 pt-2">
          <Button asChild variant="primary" size="md">
            <Link to="/app">Vào bàn làm việc</Link>
          </Button>
          <Button asChild variant="secondary" size="md">
            <Link to="/">Về trang chủ</Link>
          </Button>
        </div>
      </div>
    </div>
  )
}
