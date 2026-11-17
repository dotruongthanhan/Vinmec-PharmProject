import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { useAuth } from './useAuth'

/** Hướng dẫn tài khoản chưa được cấp quyền và cho phép kiểm tra lại. */
export function ForbiddenPage() {
  const { signOut, verifyRole, verificationError } = useAuth()
  const [retrying, setRetrying] = useState(false)
  const retry = async () => {
    setRetrying(true)
    try { await verifyRole() } finally { setRetrying(false) }
  }
  return (
    <main className="flex min-h-screen items-center justify-center bg-canvas px-6 text-fg">
      <div className="max-w-md space-y-4">
        <h1 className="text-xl font-semibold">Không có quyền</h1>
        <p className="text-sm text-fg-muted">
          {verificationError ?? 'Tài khoản chưa được cấp quyền. Vui lòng liên hệ quản trị để được hỗ trợ.'}
        </p>
        <div className="flex gap-3">
          <Button variant="secondary" onClick={() => { void signOut() }}>Đăng xuất</Button>
          <Button loading={retrying} disabled={retrying} onClick={() => { void retry() }}>Thử lại</Button>
        </div>
      </div>
    </main>
  )
}
