import type { SupabaseClient } from '@supabase/supabase-js'

export interface AuthUser {
  id: string | null
  email: string | null
}

export type AuthRole = 'duoc_si_ls' | 'admin'

export interface AuthSession {
  user: AuthUser
  vaiTro: AuthRole | null
  phienId: string | null
}

export interface SignInResult {
  session: AuthSession | null
  error: string | null
}

export type AuthStateListener = (session: AuthSession | null) => void

export interface AuthClient {
  readonly isConfigured: boolean
  getSession(): Promise<AuthSession | null>
  getAccessToken(): Promise<string | null>
  refreshSession(): Promise<AuthSession | null>
  onAuthStateChange(listener: AuthStateListener): () => void
  signInWithPassword(email: string, password: string): Promise<SignInResult>
  signOut(): Promise<void>
}

export function parseAuthRole(role: unknown): AuthRole | null {
  return role === 'duoc_si_ls' || role === 'admin' ? role : null
}

/** Chỉ đọc mã phiên; việc xác minh token thuộc về máy chủ. */
function readSessionId(token?: string): string | null {
  try {
    const part = token?.split('.')[1]
    if (!part) return null
    const base64 = part.replace(/-/g, '+').replace(/_/g, '/')
    const bytes = Uint8Array.from(atob(base64.padEnd(Math.ceil(base64.length / 4) * 4, '=')), (c) => c.charCodeAt(0))
    const payload: unknown = JSON.parse(new TextDecoder().decode(bytes))
    if (typeof payload !== 'object' || payload === null || !('session_id' in payload)) return null
    return typeof payload.session_id === 'string' ? payload.session_id : null
  } catch {
    return null
  }
}

export function mapSupabaseSession(session: {
  access_token?: string
  user?: { id?: string; email?: string | null; app_metadata?: Record<string, unknown> }
} | null): AuthSession | null {
  if (!session) {
    return null
  }
  return {
    user: {
      id: session.user?.id ?? null,
      email: session.user?.email ?? null,
    },
    vaiTro: parseAuthRole(session.user?.app_metadata?.role),
    phienId: readSessionId(session.access_token),
  }
}

function formatSupabaseAuthError(message: string): string {
  const lower = message.toLowerCase()
  if (lower.includes('invalid login credentials')) {
    return 'Thư điện tử hoặc mật khẩu không đúng.'
  }
  if (lower.includes('email not confirmed')) {
    return 'Tài khoản chưa xác nhận thư điện tử.'
  }
  if (lower.includes('too many requests')) {
    return 'Thử đăng nhập quá nhiều lần. Vui lòng đợi một lát.'
  }
  return 'Không thể đăng nhập. Vui lòng thử lại.'
}

function createUnconfiguredAuthClient(): AuthClient {
  return {
    isConfigured: false,
    async getSession() {
      return null
    },
    async getAccessToken() {
      return null
    },
    async refreshSession() {
      return null
    },
    onAuthStateChange() {
      return () => {}
    },
    async signInWithPassword() {
      return {
        session: null,
        error: 'Chưa cấu hình xác thực. Đang ở chế độ demo, không kiểm tra tài khoản.',
      }
    },
    async signOut() {},
  }
}

/** Tạo máy khách xác thực Supabase được nạp lười; không dựng khi thiếu biến môi trường. */
export function createSupabaseAuthClient(
  supabaseUrl = import.meta.env.VITE_SUPABASE_URL,
  supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY,
): AuthClient {
  const url = typeof supabaseUrl === 'string' ? supabaseUrl.trim() : ''
  const anonKey = typeof supabaseAnonKey === 'string' ? supabaseAnonKey.trim() : ''

  if (!url || !anonKey) {
    return createUnconfiguredAuthClient()
  }

  let clientPromise: Promise<SupabaseClient> | null = null
  let refreshPromise: Promise<AuthSession | null> | null = null
  let signedOut = false
  let revision = 0

  const getClient = async (): Promise<SupabaseClient> => {
    if (!clientPromise) {
      clientPromise = import('@supabase/supabase-js').then(({ createClient }) =>
        createClient(url, anonKey, { auth: { persistSession: true, autoRefreshToken: true } }),
      )
    }
    return clientPromise
  }

  return {
    isConfigured: true,
    async getSession() {
      if (signedOut) return null
      const currentRevision = revision
      const client = await getClient()
      const { data, error } = await client.auth.getSession()
      if (error || signedOut || currentRevision !== revision) {
        return null
      }
      return mapSupabaseSession(data.session)
    },
    async getAccessToken() {
      if (signedOut) return null
      const currentRevision = revision
      try {
        const client = await getClient()
        const { data, error } = await client.auth.getSession()
        return error || signedOut || currentRevision !== revision ? null : data.session?.access_token ?? null
      } catch {
        return null
      }
    },
    refreshSession() {
      if (signedOut) return Promise.resolve(null)
      if (!refreshPromise) {
        const currentRevision = revision
        refreshPromise = (async () => {
          try {
            const client = await getClient()
            const { data, error } = await client.auth.refreshSession()
            return error || signedOut || currentRevision !== revision ? null : mapSupabaseSession(data.session)
          } catch {
            return null
          }
        })().finally(() => { refreshPromise = null })
      }
      return refreshPromise
    },
    onAuthStateChange(listener) {
      let unsubscribed = false
      let cleanup: (() => void) | null = null

      void getClient().then((client) => {
        if (unsubscribed) {
          return
        }
        const { data } = client.auth.onAuthStateChange((event, session) => {
          if (event === 'SIGNED_IN') signedOut = false
          if (event === 'SIGNED_OUT') {
            signedOut = true
            revision += 1
          }
          listener(signedOut ? null : mapSupabaseSession(session))
        })
        cleanup = () => {
          data.subscription.unsubscribe()
        }
      })

      return () => {
        unsubscribed = true
        cleanup?.()
      }
    },
    async signInWithPassword(email, password) {
      try {
        const client = await getClient()
        const { data, error } = await client.auth.signInWithPassword({ email, password })
        if (error) {
          return {
            session: null,
            error: formatSupabaseAuthError(error.message),
          }
        }
        signedOut = false
        return {
          session: mapSupabaseSession(data.session),
          error: null,
        }
      } catch {
        return {
          session: null,
          error: 'Không kết nối được dịch vụ xác thực.',
        }
      }
    },
    async signOut() {
      signedOut = true
      revision += 1
      const client = await getClient()
      await client.auth.signOut()
    },
  }
}

export const defaultAuthClient: AuthClient = createSupabaseAuthClient()
