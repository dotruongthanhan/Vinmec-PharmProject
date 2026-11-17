import { createContext, useContext } from 'react'
import type { AuthRole, AuthSession } from './authClient'

export interface AuthContextValue {
  session: AuthSession | null
  isAuthenticated: boolean
  isDemoMode: boolean
  isConfigured: boolean
  isLoading: boolean
  userEmail: string | null
  vaiTro: AuthRole | null
  phienId: string | null
  isForbidden: boolean
  verificationError: string | null
  getAccessToken: () => Promise<string | null>
  refreshSession: () => Promise<AuthSession | null>
  verifyRole: () => Promise<void>
  signIn: (email: string, password: string) => Promise<string | null>
  enterDemoMode: () => void
  signOut: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

/** Truy cập trạng thái phiên đăng nhập và chế độ demo từ AuthProvider. */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth phải được gọi bên trong AuthProvider.')
  }
  return ctx
}
