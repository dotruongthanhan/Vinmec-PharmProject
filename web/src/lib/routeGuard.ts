export interface RouteGuardInput {
  isAuthenticated: boolean
  isDemoMode: boolean
  isLoading: boolean
  currentPath: string
  /** Bỏ qua chỉ cho lời gọi cũ; tuyến thực luôn truyền vai trò hoặc null. */
  vaiTro?: 'duoc_si_ls' | 'admin' | null
}

export type RouteGuardDecision =
  | { action: 'allow' }
  | { action: 'loading' }
  | { action: 'forbidden' }
  | { action: 'redirect'; to: '/dang-nhap'; returnTo?: string }

/** Hàm thuần quyết định cho phép vào tuyến được bảo vệ (/app/*) hay chuyển về /dang-nhap. */
export function evaluateProtectedRoute({
  isAuthenticated,
  isDemoMode,
  isLoading,
  currentPath,
  vaiTro,
}: RouteGuardInput): RouteGuardDecision {
  if (isLoading) {
    return { action: 'loading' }
  }
  if (isAuthenticated && vaiTro === null) return { action: 'forbidden' }
  if (isAuthenticated || isDemoMode) {
    return { action: 'allow' }
  }
  const safeReturnTo =
    currentPath.startsWith('/app') && !currentPath.startsWith('//') ? currentPath : undefined
  return safeReturnTo
    ? { action: 'redirect', to: '/dang-nhap', returnTo: safeReturnTo }
    : { action: 'redirect', to: '/dang-nhap' }
}

/** Lấy đường dẫn quay lại an toàn sau khi đăng nhập thành công (chỉ cho phép tuyến /app*). */
export function resolveLoginRedirect(state: unknown): string {
  if (typeof state === 'object' && state !== null && 'from' in state) {
    const candidate = (state as { from?: unknown }).from
    if (
      typeof candidate === 'string' &&
      candidate.startsWith('/app') &&
      !candidate.startsWith('//')
    ) {
      return candidate
    }
  }
  return '/app'
}
