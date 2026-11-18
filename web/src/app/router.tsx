import { Suspense, lazy } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { ProtectedRoute } from '@/features/auth/ProtectedRoute'
import { NotFoundPage } from './NotFoundPage'

const LandingPage = lazy(() => import('@/features/landing/LandingPage'))
const LoginPage = lazy(() => import('@/features/auth/LoginPage'))
const WorkspacePage = lazy(() => import('./WorkspacePage').then((module) => ({ default: module.WorkspacePage })))

function PageFallback() {
  return (
    <div
      className="flex min-h-screen items-center justify-center bg-paper text-sm text-fg-subtle"
      role="status"
      aria-live="polite"
    >
      Đang tải…
    </div>
  )
}

/** Định tuyến phía trình duyệt cho trang chủ, đăng nhập và bàn làm việc được bảo vệ. */
export function AppRouter() {
  return (
    <BrowserRouter>
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/dang-nhap" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/app" element={<WorkspacePage />} />
            <Route path="/app/ho-so" element={<WorkspacePage />} />
            <Route path="/app/y-lenh/:caId" element={<WorkspacePage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
