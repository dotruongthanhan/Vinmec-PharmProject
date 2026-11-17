import type { SupabaseClient } from '@supabase/supabase-js'

export interface AuthUser {
  email: string | null
}

export interface AuthSession {
  user: AuthUser
}

export interface SignInResult {
  session: AuthSession | null
  error: string | null
}

export type AuthStateListener = (session: AuthSession | null) => void

export interface AuthClient {
  readonly isConfigured: boolean
  getSession(): Promise<AuthSession | null>
  onAuthStateChange(listener: AuthStateListener): () => void
  signInWithPassword(email: string, password: string): Promise<SignInResult>
  signOut(): Promise<void>
}

function mapSupabaseSession(session: { user?: { email?: string | null } } | null): AuthSession | null {
  if (!session) {
    return null
  }
  return {
    user: {
      email: session.user?.email ?? null,
    },
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
  return message || 'Không thể đăng nhập. Vui lòng thử lại.'
}

function createUnconfiguredAuthClient(): AuthClient {
  return {
    isConfigured: false,
    async getSession() {
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

  const getClient = async (): Promise<SupabaseClient> => {
    if (!clientPromise) {
      clientPromise = import('@supabase/supabase-js').then(({ createClient }) =>
        createClient(url, anonKey),
      )
    }
    return clientPromise
  }

  return {
    isConfigured: true,
    async getSession() {
      const client = await getClient()
      const { data, error } = await client.auth.getSession()
      if (error) {
        return null
      }
      return mapSupabaseSession(data.session)
    },
    onAuthStateChange(listener) {
      let unsubscribed = false
      let cleanup: (() => void) | null = null

      void getClient().then((client) => {
        if (unsubscribed) {
          return
        }
        const { data } = client.auth.onAuthStateChange((_event, session) => {
          listener(mapSupabaseSession(session))
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
      const client = await getClient()
      await client.auth.signOut()
    },
  }
}

export const defaultAuthClient: AuthClient = createSupabaseAuthClient()
