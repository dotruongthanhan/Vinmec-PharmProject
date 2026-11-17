import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { apiClient, ApiError } from '@/api/index'
import type { MeResponse } from '@/api/types'
import { clearSessionTimestamps, isDemoEnabled, loadDemoMode, saveDemoMode } from '@/lib/demoSession'
import { defaultAuthClient, parseAuthRole } from './authClient'
import type { AuthClient, AuthSession } from './authClient'
import { subscribeAuthEvents } from './authEvents'
import { AuthContext } from './useAuth'
import type { AuthContextValue, SignOutOptions, SignOutReason } from './useAuth'
import { startSessionPolicy, systemSessionClock } from './sessionPolicy'
import type { SessionClock } from './sessionPolicy'

export interface AuthProviderProps {
  client?: AuthClient
  getMe?: () => Promise<MeResponse>
  clock?: SessionClock
  children: ReactNode
}

const defaultGetMe = () => apiClient.getMe()

/** Cung cấp phiên; quyền được xác nhận một lần từ máy chủ cho mỗi phiên. */
export function AuthProvider({ client = defaultAuthClient, getMe = defaultGetMe, clock = systemSessionClock, children }: AuthProviderProps) {
  const [session, setSession] = useState<AuthSession | null>(null)
  const [isDemoMode, setIsDemoMode] = useState(() => loadDemoMode(client.isConfigured))
  const [isLoading, setIsLoading] = useState(client.isConfigured)
  const [isForbidden, setIsForbidden] = useState(false)
  const [verificationError, setVerificationError] = useState<string | null>(null)
  const [signOutReason, setSignOutReason] = useState<SignOutReason | null>(null)
  const sessionRef = useRef<AuthSession | null>(null)
  const versionRef = useRef(0)
  const confirmationRef = useRef<{ key: string; promise: Promise<MeResponse> } | null>(null)
  const signingOutRef = useRef(false)
  const signOutPromiseRef = useRef<Promise<void> | null>(null)
  const stopPolicyRef = useRef<(() => void) | null>(null)

  const clearSession = useCallback(() => {
    versionRef.current += 1
    sessionRef.current = null
    confirmationRef.current = null
    stopPolicyRef.current?.()
    stopPolicyRef.current = null
    clearSessionTimestamps()
    setSession(null)
    setIsLoading(false)
    setIsForbidden(false)
    setVerificationError(null)
    saveDemoMode(false)
    setIsDemoMode(false)
  }, [])

  const signOut = useCallback((options: SignOutOptions = {}): Promise<void> => {
    if (signingOutRef.current) return signOutPromiseRef.current ?? Promise.resolve()
    const previousLogout = signOutPromiseRef.current
    const hadRealSession = sessionRef.current !== null
    signingOutRef.current = true
    const { scope = 'local', reason = 'nguoi_dung' } = options
    apiClient.abortAll?.()
    setSignOutReason(reason)
    // Gỡ bàn làm việc ngay cả khi dịch vụ đăng xuất không phản hồi.
    clearSession()
    const pending = (async () => {
      // Giữ thứ tự cả khi người dùng mở rồi đóng demo trong lúc mạng còn chờ.
      await previousLogout
      if (!client.isConfigured || reason === 'da_dang_xuat_noi_khac') return
      if (!hadRealSession && reason !== '401') return
      if (reason !== '401') {
        let timeout: ReturnType<typeof setTimeout> | undefined
        let expired = false
        try {
          await Promise.race([
            (async () => {
              const token = await client.getAccessToken()
              if (token && !expired) await apiClient.signOut?.(token)
            })(),
            new Promise<void>((resolve) => { timeout = clock.setTimeout(() => { expired = true; resolve() }, 3_000) }),
          ])
        } catch {
          // Thu hồi backend là nỗ lực có hạn; luôn tiếp tục đăng xuất SDK.
        } finally {
          expired = true
          if (timeout !== undefined) clock.clearTimeout(timeout)
        }
      }
      try {
        await client.signOut({ scope })
      } catch {
        // Phiên giao diện đã bị xoá; không hiển thị chi tiết dịch vụ.
      }
    })()
    signOutPromiseRef.current = pending
    return pending
  }, [client, clearSession, clock])

  const confirmSession = useCallback(async (next: AuthSession, force = false) => {
    const key = `${next.user.id}:${next.phienId}`
    const version = versionRef.current
    const fresh = force || confirmationRef.current?.key !== key
    if (fresh) {
      setIsLoading(true)
      setVerificationError(null)
      // Hoãn API ra ngoài callback đồng bộ của Supabase để tránh khoá phiên.
      confirmationRef.current = { key, promise: Promise.resolve().then(getMe) }
    }
    const confirmation = confirmationRef.current!
    try {
      const me = await confirmation.promise
      if (version !== versionRef.current || confirmationRef.current !== confirmation) return
      const confirmed: AuthSession = {
        ...next,
        user: { id: me.id, email: me.email },
        vaiTro: parseAuthRole(me.vai_tro),
        phienId: me.phien_id,
      }
      sessionRef.current = confirmed
      setSession(confirmed)
      if (fresh) setIsForbidden(confirmed.vaiTro === null)
      setVerificationError(null)
    } catch (error) {
      if (version !== versionRef.current || confirmationRef.current !== confirmation) return
      setIsForbidden(true)
      if (!(error instanceof ApiError && error.status === 403)) {
        setVerificationError('Chưa kiểm tra được quyền truy cập. Vui lòng thử lại sau.')
      }
    } finally {
      if (version === versionRef.current && confirmationRef.current === confirmation) setIsLoading(false)
    }
  }, [getMe])

  const acceptSession = useCallback(async (next: AuthSession | null) => {
    if (!next) {
      clearSession()
      return
    }
    const previous = sessionRef.current
    if (previous?.user.id !== next.user.id || previous?.phienId !== next.phienId) {
      versionRef.current += 1
      sessionRef.current = next
      setSession(next)
    }
    saveDemoMode(false)
    setIsDemoMode(false)
    await confirmSession(next)
  }, [clearSession, confirmSession])

  useEffect(() => subscribeAuthEvents((event) => {
    if (event === 'unauthorized') return signOut({ reason: '401' })
    setIsForbidden(true)
  }), [signOut])

  useEffect(() => {
    if (!client.isConfigured) return
    let cancelled = false
    let receivedEvent = false
    const unsubscribe = client.onAuthStateChange((next, event) => {
      receivedEvent = true
      if (cancelled) return
      if (event === 'SIGNED_OUT') {
        if (!signingOutRef.current && sessionRef.current) {
          void signOut({ reason: 'da_dang_xuat_noi_khac' })
        } else {
          // Sự kiện về muộn không được xoá chế độ demo vừa mở.
          setIsLoading(false)
        }
        return
      }
      if (signingOutRef.current) return
      void acceptSession(next)
    })
    void client.getSession().then((initial) => {
      if (!cancelled && !receivedEvent && !signingOutRef.current) void acceptSession(initial)
    }).catch(() => {
      if (!cancelled && !receivedEvent) clearSession()
    })
    return () => {
      cancelled = true
      versionRef.current += 1
      unsubscribe()
    }
  }, [client, acceptSession, clearSession, signOut])

  const policyIdentity = session && !isDemoMode && client.isConfigured ? `${session.user.id}:${session.phienId}` : null
  useEffect(() => {
    if (!policyIdentity) return
    const stop = startSessionPolicy({ identity: policyIdentity, clock, onExpire: (reason) => { void signOut({ reason }) } })
    stopPolicyRef.current = stop
    return () => {
      stop()
      if (stopPolicyRef.current === stop) stopPolicyRef.current = null
    }
  }, [policyIdentity, clock, signOut])

  const signIn = useCallback(async (email: string, password: string): Promise<string | null> => {
    await signOutPromiseRef.current
    signingOutRef.current = false
    signOutPromiseRef.current = null
    setSignOutReason(null)
    clearSessionTimestamps()
    const result = await client.signInWithPassword(email, password)
    if (result.error) return result.error
    await acceptSession(result.session)
    return null
  }, [client, acceptSession])

  const enterDemoMode = useCallback(() => {
    if (!isDemoEnabled()) return
    clearSession()
    signingOutRef.current = false
    setSignOutReason(null)
    saveDemoMode(true)
    setIsDemoMode(true)
  }, [clearSession])

  const getAccessToken = useCallback(async () => {
    if (isDemoMode || signingOutRef.current) return null
    const version = versionRef.current
    const token = await client.getAccessToken()
    return signingOutRef.current || version !== versionRef.current ? null : token
  }, [client, isDemoMode])
  const refreshSession = useCallback(async () => {
    if (signingOutRef.current) return null
    const version = versionRef.current
    const refreshed = await client.refreshSession()
    if (signingOutRef.current || version !== versionRef.current) return null
    if (refreshed) await acceptSession(refreshed)
    return refreshed
  }, [client, acceptSession])
  const verifyRole = useCallback(async () => {
    const current = sessionRef.current
    if (current) await confirmSession(current, true)
  }, [confirmSession])

  const value = useMemo<AuthContextValue>(() => ({
    session,
    isAuthenticated: session !== null,
    isDemoMode,
    isConfigured: client.isConfigured,
    isLoading,
    isForbidden,
    verificationError,
    userEmail: session?.user.email ?? null,
    vaiTro: session?.vaiTro ?? null,
    phienId: session?.phienId ?? null,
    getAccessToken,
    refreshSession,
    verifyRole,
    signIn,
    enterDemoMode,
    signOut,
    signOutReason,
  }), [session, isDemoMode, client.isConfigured, isLoading, isForbidden, verificationError,
    getAccessToken, refreshSession, verifyRole, signIn, enterDemoMode, signOut, signOutReason])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
