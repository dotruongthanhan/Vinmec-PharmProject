import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { apiClient, ApiError } from '@/api/index'
import type { MeResponse } from '@/api/types'
import { isDemoEnabled, loadDemoMode, saveDemoMode } from '@/lib/demoSession'
import { defaultAuthClient, parseAuthRole } from './authClient'
import type { AuthClient, AuthSession } from './authClient'
import { subscribeAuthEvents } from './authEvents'
import { AuthContext } from './useAuth'
import type { AuthContextValue } from './useAuth'

export interface AuthProviderProps {
  client?: AuthClient
  getMe?: () => Promise<MeResponse>
  children: ReactNode
}

const defaultGetMe = () => apiClient.getMe()

/** Cung cấp phiên; quyền được xác nhận một lần từ máy chủ cho mỗi phiên. */
export function AuthProvider({ client = defaultAuthClient, getMe = defaultGetMe, children }: AuthProviderProps) {
  const [session, setSession] = useState<AuthSession | null>(null)
  const [isDemoMode, setIsDemoMode] = useState(() => loadDemoMode(client.isConfigured))
  const [isLoading, setIsLoading] = useState(client.isConfigured)
  const [isForbidden, setIsForbidden] = useState(false)
  const [verificationError, setVerificationError] = useState<string | null>(null)
  const sessionRef = useRef<AuthSession | null>(null)
  const versionRef = useRef(0)
  const confirmationRef = useRef<{ key: string; promise: Promise<MeResponse> } | null>(null)

  const clearSession = useCallback(() => {
    versionRef.current += 1
    sessionRef.current = null
    confirmationRef.current = null
    setSession(null)
    setIsLoading(false)
    setIsForbidden(false)
    setVerificationError(null)
    saveDemoMode(false)
    setIsDemoMode(false)
  }, [])

  const signOut = useCallback(async () => {
    // Gỡ bàn làm việc ngay cả khi dịch vụ đăng xuất không phản hồi.
    clearSession()
    try {
      if (client.isConfigured) await client.signOut()
    } catch {
      // Phiên giao diện đã bị xoá; không hiển thị chi tiết dịch vụ.
    }
  }, [client, clearSession])

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
    if (event === 'unauthorized') return signOut()
    setIsForbidden(true)
  }), [signOut])

  useEffect(() => {
    if (!client.isConfigured) return
    let cancelled = false
    let receivedEvent = false
    const unsubscribe = client.onAuthStateChange((next) => {
      receivedEvent = true
      if (!cancelled) void acceptSession(next)
    })
    void client.getSession().then((initial) => {
      if (!cancelled && !receivedEvent) void acceptSession(initial)
    }).catch(() => {
      if (!cancelled && !receivedEvent) clearSession()
    })
    return () => {
      cancelled = true
      versionRef.current += 1
      unsubscribe()
    }
  }, [client, acceptSession, clearSession])

  const signIn = useCallback(async (email: string, password: string): Promise<string | null> => {
    const result = await client.signInWithPassword(email, password)
    if (result.error) return result.error
    await acceptSession(result.session)
    return null
  }, [client, acceptSession])

  const enterDemoMode = useCallback(() => {
    if (!isDemoEnabled()) return
    clearSession()
    saveDemoMode(true)
    setIsDemoMode(true)
  }, [clearSession])

  const getAccessToken = useCallback(() => isDemoMode ? Promise.resolve(null) : client.getAccessToken(), [client, isDemoMode])
  const refreshSession = useCallback(async () => {
    const refreshed = await client.refreshSession()
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
  }), [session, isDemoMode, client.isConfigured, isLoading, isForbidden, verificationError,
    getAccessToken, refreshSession, verifyRole, signIn, enterDemoMode, signOut])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
