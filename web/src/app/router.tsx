import { Suspense, lazy } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { ProtectedRoute } from '@/features/auth/ProtectedRoute'
import { NotFoundPage } from './NotFoundPage'

const LandingPage = lazy(() => import('@/features/landing/LandingPage'))
const LoginPage = lazy(() => import('@/features/auth/LoginPage'))
const WorkspacePage = lazy(() => import('./WorkspacePage').then((module) => ({ default: module.WorkspacePage })))

const DrugSearchPage = lazy(() => import('@/features/lookup/DrugSearchPage'))
const DrugDetailPage = lazy(() => import('@/features/lookup/DrugDetailPage'))
const InteractionLookupPage = lazy(() => import('@/features/lookup/InteractionLookupPage'))
const FormulaListPage = lazy(() => import('@/features/lookup/FormulaPages').then((module) => ({ default: module.FormulaListPage })))
const FormulaPage = lazy(() => import('@/features/lookup/FormulaPages').then((module) => ({ default: module.FormulaPage })))

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

/** Bảng tuyến của ứng dụng (tách riêng để kiểm thử). Đường dẫn cũ /app/ho-so chuyển về /app. */
export function AppRoutes() {
  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/dang-nhap" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/app" element={<WorkspacePage />} />
          <Route path="/app/ho-so/*" element={<Navigate to="/app" replace />} />
          <Route path="/app/y-lenh/:caId" element={<WorkspacePage />} />
          <Route path="/app/thuoc" element={<DrugSearchPage />} />
          <Route path="/app/thuoc/:hoat_chat_id" element={<DrugDetailPage />} />
          <Route path="/app/tuong-tac" element={<InteractionLookupPage />} />
          <Route path="/app/cong-thuc" element={<FormulaListPage />} />
          <Route path="/app/cong-thuc/:ma" element={<FormulaPage />} />
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  )
}

/** Định tuyến phía trình duyệt cho trang chủ, đăng nhập và bàn làm việc được bảo vệ. */
export function AppRouter() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}
