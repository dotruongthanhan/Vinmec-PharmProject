import { LoaderCircle } from 'lucide-react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { evaluateProtectedRoute } from '@/lib/routeGuard'
import { useAuth } from './useAuth'
import { ForbiddenPage } from './ForbiddenPage'

/** Bảo vệ các tuyến /app/*: chuyển hướng sang /dang-nhap và giữ đường dẫn quay lại khi chưa đăng nhập. */
export function ProtectedRoute() {
  const { session, vaiTro, isForbidden, isAuthenticated, isDemoMode, isLoading } = useAuth()
  const location = useLocation()

  const currentPath = `${location.pathname}${location.search}`
  const decision = evaluateProtectedRoute({
    isAuthenticated,
    isDemoMode,
    isLoading,
    currentPath,
    vaiTro: isForbidden ? null : vaiTro,
  })

  if (decision.action === 'loading') {
    return (
      <div
        className="flex h-screen w-full items-center justify-center bg-canvas text-fg-muted"
        role="status"
        aria-live="polite"
      >
        <div className="flex items-center gap-2 text-sm">
          <LoaderCircle className="size-4 animate-spin text-primary" strokeWidth={1.75} />
          <span>Đang kiểm tra phiên làm việc…</span>
        </div>
      </div>
    )
  }

  if (decision.action === 'redirect') {
    return (
      <Navigate
        to={decision.to}
        replace
        state={decision.returnTo ? { from: decision.returnTo } : undefined}
      />
    )
  }

  if (decision.action === 'forbidden') return <ForbiddenPage />

  return <Outlet key={session ? `${session.user.id}:${session.phienId}` : 'demo'} />
}
