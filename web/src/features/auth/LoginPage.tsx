import { ArrowLeft, Eye, EyeOff } from 'lucide-react'
import { useId, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { InlineAlert } from '@/components/ui/inline-alert'
import { VinmecLogo } from '@/components/VinmecLogo'
import { resolveLoginRedirect } from '@/lib/routeGuard'
import { isDemoEnabled } from '@/lib/demoSession'
import { ThemeControl } from '@/features/theme/ThemeControl'
import { useAuth } from './useAuth'

/** Trang đăng nhập hai nửa: giới thiệu nền ink, biểu mẫu nền paper. */
export function LoginPage() {
  const { isAuthenticated, isDemoMode, isConfigured, isLoading, signIn, enterDemoMode } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()

  const [email, setEmail] = useState<string>('')
  const [password, setPassword] = useState<string>('')
  const [showPassword, setShowPassword] = useState<boolean>(false)
  const [emailError, setEmailError] = useState<string | null>(null)
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState<boolean>(false)

  const emailId = useId()
  const emailErrorId = useId()
  const passwordId = useId()
  const passwordErrorId = useId()

  const returnTo = resolveLoginRedirect(location.state)

  if ((isAuthenticated && !isLoading) || isDemoMode) {
    return <Navigate to={returnTo} replace />
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!isConfigured || submitting) {
      return
    }

    const cleanEmail = email.trim()
    let hasError = false

    if (!cleanEmail) {
      setEmailError('Vui lòng nhập thư điện tử.')
      hasError = true
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleanEmail)) {
      setEmailError('Địa chỉ thư điện tử chưa đúng định dạng.')
      hasError = true
    } else {
      setEmailError(null)
    }

    if (!password) {
      setPasswordError('Vui lòng nhập mật khẩu.')
      hasError = true
    } else {
      setPasswordError(null)
    }

    if (hasError) {
      return
    }

    setFormError(null)
    setSubmitting(true)
    const err = await signIn(cleanEmail, password)
    setSubmitting(false)

    if (err) {
      setFormError(err)
      return
    }

    navigate(returnTo, { replace: true })
  }

  const handleEnterDemo = () => {
    if (!isDemoEnabled()) return
    enterDemoMode()
    navigate(returnTo, { replace: true })
  }

  return (
    <div className="min-h-screen w-full grid grid-cols-1 lg:grid-cols-2 bg-paper text-fg">
      <aside
        className="hidden lg:flex flex-col justify-between bg-ink text-ink-fg p-12 border-r border-ink-line"
        aria-label="Giới thiệu ngắn"
      >
        <div>
          <Link
            to="/"
            className="inline-flex items-center gap-3 text-sm font-semibold tracking-tight text-ink-fg hover:text-primary-line transition-colors duration-120"
          >
            <VinmecLogo alwaysOnDark imageClassName="h-12" />
            <span>Hỗ trợ thẩm định y lệnh</span>
          </Link>
        </div>

        <div className="max-w-md space-y-4">
          <h1 className="text-[30px] leading-[38px] font-semibold tracking-tight text-ink-fg">
            Mỗi nhận định đi kèm căn cứ để dược sĩ đối chiếu và quyết định.
          </h1>
          <p className="text-sm text-ink-muted leading-relaxed">
            Hệ thống tổng hợp hồ sơ lâm sàng, tính toán chỉ số bằng công thức chuẩn, chạy bộ luật
            thẩm định và trích dẫn nguyên văn nguồn thuốc tham chiếu.
          </p>
        </div>

        <div className="text-xs text-ink-muted">
          Bản thử nghiệm học thuật · Dược lâm sàng
        </div>
      </aside>

      <main className="flex flex-col justify-between px-6 py-8 sm:px-12 bg-paper">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-sm text-fg-muted hover:text-fg transition-colors duration-120"
          >
            <ArrowLeft className="size-4" strokeWidth={1.75} aria-hidden="true" />
            <span>Trang chủ</span>
          </Link>
          <ThemeControl />
        </div>

        <div className="mx-auto w-full max-w-[380px] py-10">
          <div className="mb-6 space-y-1.5">
            <p className="text-xs font-medium text-fg-subtle lg:hidden">Hỗ trợ thẩm định y lệnh</p>
            <h2 className="text-[24px] leading-[32px] font-semibold tracking-tight text-fg">
              Đăng nhập bàn làm việc
            </h2>
            <p className="text-sm text-fg-muted">
              Dùng tài khoản được cấp để mở danh sách y lệnh cần thẩm định.
            </p>
          </div>

          {!isConfigured ? (
            <div className="mb-6 flex flex-col gap-3">
              <InlineAlert tone="warning" role="status">
                {isDemoEnabled() ? 'Chưa cấu hình xác thực. Đang ở chế độ demo, không kiểm tra tài khoản.' : 'Chưa thể đăng nhập. Vui lòng liên hệ quản trị.'}
              </InlineAlert>
              {isDemoEnabled() ? <Button variant="primary" size="lg" className="w-full" onClick={handleEnterDemo}>
                Vào bản demo
              </Button> : null}
            </div>
          ) : null}

          {isConfigured && isDemoEnabled() ? (
            <Button variant="secondary" className="mb-4 w-full" onClick={handleEnterDemo}>
              Vào bản demo
            </Button>
          ) : null}

          <form onSubmit={(e) => void handleSubmit(e)} noValidate className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label htmlFor={emailId} className="text-sm font-medium text-fg">
                Thư điện tử
              </label>
              <input
                id={emailId}
                type="email"
                autoComplete="email"
                placeholder="duocsi@benhvien.vn"
                value={email}
                disabled={!isConfigured || submitting}
                aria-invalid={emailError ? true : undefined}
                aria-describedby={emailError ? emailErrorId : undefined}
                onChange={(e) => {
                  setEmail(e.target.value)
                  if (emailError) {
                    setEmailError(null)
                  }
                }}
                className="h-10 w-full rounded-sm border border-line-strong bg-surface px-3 text-sm text-fg placeholder:text-fg-subtle disabled:bg-surface-muted disabled:text-fg-disabled"
              />
              {emailError ? (
                <p id={emailErrorId} className="text-xs text-danger-fg">
                  {emailError}
                </p>
              ) : null}
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor={passwordId} className="text-sm font-medium text-fg">
                Mật khẩu
              </label>
              <div className="relative">
                <input
                  id={passwordId}
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  value={password}
                  disabled={!isConfigured || submitting}
                  aria-invalid={passwordError ? true : undefined}
                  aria-describedby={passwordError ? passwordErrorId : undefined}
                  onChange={(e) => {
                    setPassword(e.target.value)
                    if (passwordError) {
                      setPasswordError(null)
                    }
                  }}
                  className="h-10 w-full rounded-sm border border-line-strong bg-surface pl-3 pr-10 text-sm text-fg placeholder:text-fg-subtle disabled:bg-surface-muted disabled:text-fg-disabled"
                />
                <button
                  type="button"
                  aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                  disabled={!isConfigured || submitting}
                  onClick={() => setShowPassword((prev) => !prev)}
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 inline-flex size-7 items-center justify-center rounded-sm text-fg-muted hover:bg-surface-muted hover:text-fg cursor-pointer disabled:opacity-50"
                >
                  {showPassword ? (
                    <EyeOff className="size-4" strokeWidth={1.75} aria-hidden="true" />
                  ) : (
                    <Eye className="size-4" strokeWidth={1.75} aria-hidden="true" />
                  )}
                </button>
              </div>
              {passwordError ? (
                <p id={passwordErrorId} className="text-xs text-danger-fg">
                  {passwordError}
                </p>
              ) : null}
            </div>

            {formError ? (
              <InlineAlert tone="danger" role="alert">
                {formError}
              </InlineAlert>
            ) : null}

            <Button
              type="submit"
              variant={isConfigured ? 'primary' : 'secondary'}
              size="lg"
              loading={submitting}
              disabled={!isConfigured || submitting}
              className="mt-1 w-full"
            >
              Đăng nhập
            </Button>
          </form>
        </div>

        <div className="text-xs text-fg-subtle text-center lg:text-left">
          Hệ thống chỉ hỗ trợ tham chiếu; dược sĩ là người quyết định.
        </div>
      </main>
    </div>
  )
}

export default LoginPage
