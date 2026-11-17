import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { loadDemoMode, saveDemoMode } from '@/lib/demoSession'
import { defaultAuthClient } from './authClient'
import type { AuthClient, AuthSession } from './authClient'
import { AuthContext } from './useAuth'
import type { AuthContextValue } from './useAuth'

export interface AuthProviderProps {
  client?: AuthClient
  children: ReactNode
}

/** Cung cấp ngữ cảnh xác thực Supabase và chế độ demo trong phiên trình duyệt. */
export function AuthProvider({ client = defaultAuthClient, children }: AuthProviderProps) {
  const [session, setSession] = useState<AuthSession | null>(null)
  const [isDemoMode, setIsDemoMode] = useState<boolean>(() => loadDemoMode(client.isConfigured))
  const [isLoading, setIsLoading] = useState<boolean>(client.isConfigured)

  useEffect(() => {
    if (!client.isConfigured) {
      return
    }

    let cancelled = false

    void client
      .getSession()
      .then((initialSession) => {
        if (cancelled) {
          return
        }
        setSession(initialSession)
        setIsLoading(false)
      })
      .catch(() => {
        if (cancelled) {
          return
        }
        setSession(null)
        setIsLoading(false)
      })

    const unsubscribe = client.onAuthStateChange((nextSession) => {
      if (cancelled) {
        return
      }
      setSession(nextSession)
      if (nextSession) {
        saveDemoMode(false)
        setIsDemoMode(false)
      }
    })

    return () => {
      cancelled = true
      unsubscribe()
    }
  }, [client])

  const signIn = useCallback(
    async (email: string, password: string): Promise<string | null> => {
      const result = await client.signInWithPassword(email, password)
      if (result.error) {
        return result.error
      }
      setSession(result.session)
      saveDemoMode(false)
      setIsDemoMode(false)
      return null
    },
    [client],
  )

  const enterDemoMode = useCallback(() => {
    saveDemoMode(true)
    setSession(null)
    setIsDemoMode(true)
  }, [])

  const signOut = useCallback(async () => {
    saveDemoMode(false)
    setIsDemoMode(false)
    if (client.isConfigured) {
      await client.signOut()
    }
    setSession(null)
  }, [client])

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      isAuthenticated: session !== null,
      isDemoMode,
      isConfigured: client.isConfigured,
      isLoading,
      userEmail: session?.user.email ?? null,
      signIn,
      enterDemoMode,
      signOut,
    }),
    [session, isDemoMode, client.isConfigured, isLoading, signIn, enterDemoMode, signOut],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
