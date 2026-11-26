/** Ứng dụng chính trong Chrome Side Panel: quản lý cấu hình, phiên đăng nhập và 3 màn hình chính. */

import { createClient } from '@supabase/supabase-js'
import { Lock, Settings, ShieldCheck } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ExtensionApiClient,
  loadClientSettings,
  saveClientSettings,
  type ExtensionClientSettings,
} from '../api/extensionClient'
import type { ExtensionHealthResponse, ExtensionReviewResponse } from '../lib/types'
import { CapturePanel } from './CapturePanel'
import { ChatDrawer } from './ChatDrawer'
import { ResultsPanel } from './ResultsPanel'

const TOKEN_STORAGE_KEY = 'cdss_ext_access_token_v1'

export function App() {
  const [settings, setSettings] = useState<ExtensionClientSettings>({
    apiBaseUrl: 'http://localhost:8001',
    supabaseUrl: '',
    supabaseAnonKey: '',
  })
  const [token, setToken] = useState<string | null>(null)
  const [health, setHealth] = useState<ExtensionHealthResponse | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)

  const [review, setReview] = useState<ExtensionReviewResponse | null>(null)
  const [restoreMap, setRestoreMap] = useState<Record<string, string>>({})
  const [view, setView] = useState<'capture' | 'results' | 'chat' | 'settings'>('capture')
  const [chatFindingId, setChatFindingId] = useState<string | undefined>(undefined)

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [authError, setAuthError] = useState<string | null>(null)

  useEffect(() => {
    void (async () => {
      const loaded = await loadClientSettings()
      setSettings(loaded)
      if (typeof chrome !== 'undefined' && chrome.storage?.session) {
        const sess = await chrome.storage.session.get(TOKEN_STORAGE_KEY)
        if (typeof sess[TOKEN_STORAGE_KEY] === 'string') {
          setToken(sess[TOKEN_STORAGE_KEY])
        }
      }
    })()
  }, [])

  const client = useMemo(
    () => new ExtensionApiClient(settings.apiBaseUrl, token),
    [settings.apiBaseUrl, token],
  )

  const checkHealth = useCallback(async () => {
    setHealthError(null)
    try {
      const res = await client.health()
      setHealth(res)
    } catch {
      setHealth(null)
      setHealthError(`Chưa kết nối được dịch vụ Extension (${settings.apiBaseUrl}).`)
    }
  }, [client, settings.apiBaseUrl])

  useEffect(() => {
    void checkHealth()
  }, [checkHealth])

  const needsLogin = health !== null && health.xac_thuc !== 'off' && !token

  const handleSupabaseLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setAuthError(null)
    if (!settings.supabaseUrl || !settings.supabaseAnonKey) {
      setAuthError('Vui lòng nhập Supabase URL và Anon Key trong phần Cài đặt.')
      return
    }
    try {
      const sb = createClient(settings.supabaseUrl, settings.supabaseAnonKey)
      const { data, error } = await sb.auth.signInWithPassword({ email, password })
      if (error || !data.session?.access_token) {
        setAuthError(error?.message || 'Đăng nhập thất bại.')
        return
      }
      const nextToken = data.session.access_token
      setToken(nextToken)
      if (typeof chrome !== 'undefined' && chrome.storage?.session) {
        await chrome.storage.session.set({ [TOKEN_STORAGE_KEY]: nextToken })
      }
    } catch (err) {
      setAuthError(err instanceof Error ? err.message : 'Lỗi kết nối Supabase.')
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <header className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white px-3 py-2">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-teal-600 text-white">
            <ShieldCheck className="h-4 w-4" />
          </div>
          <div>
            <h1 className="text-xs font-bold text-slate-900">Thẩm định Y lệnh Độc lập</h1>
            <p className="text-[10px] text-slate-500">
              {health ? `Sẵn sàng · Zero-Retention` : 'Chờ kết nối máy chủ :8001'}
            </p>
          </div>
        </div>
        <button
          type="button"
          aria-label="Cài đặt"
          onClick={() => setView(view === 'settings' ? (review ? 'results' : 'capture') : 'settings')}
          className="rounded p-1.5 text-slate-600 hover:bg-slate-100"
        >
          <Settings className="h-4 w-4" />
        </button>
      </header>

      <main className="flex-1 p-3">
        {healthError && (
          <div className="mb-3 rounded-lg border border-amber-300 bg-amber-50 p-2.5 text-xs text-amber-900">
            <p className="font-semibold">Chưa thấy API Extension ở cổng 8001</p>
            <p className="text-[11px]">
              Chạy lệnh: <code className="font-mono">uv run uvicorn app.extension_api.main:app --port 8001</code>
            </p>
          </div>
        )}

        {view === 'settings' && (
          <section className="space-y-2.5 rounded-lg border border-slate-200 bg-white p-3 text-xs">
            <h2 className="font-semibold text-slate-800">Cấu hình kết nối Extension</h2>
            <label className="block space-y-1">
              <span className="text-[11px] font-medium text-slate-600">URL Extension API</span>
              <input
                type="url"
                value={settings.apiBaseUrl}
                onChange={(e) => setSettings({ ...settings, apiBaseUrl: e.target.value })}
                className="w-full rounded border border-slate-300 px-2 py-1 text-xs"
              />
            </label>
            <label className="block space-y-1">
              <span className="text-[11px] font-medium text-slate-600">
                Supabase URL (chỉ dùng đăng nhập JWT khi bật auth)
              </span>
              <input
                type="url"
                value={settings.supabaseUrl}
                onChange={(e) => setSettings({ ...settings, supabaseUrl: e.target.value })}
                className="w-full rounded border border-slate-300 px-2 py-1 text-xs"
              />
            </label>
            <label className="block space-y-1">
              <span className="text-[11px] font-medium text-slate-600">Supabase Anon Key</span>
              <input
                type="password"
                value={settings.supabaseAnonKey}
                onChange={(e) => setSettings({ ...settings, supabaseAnonKey: e.target.value })}
                className="w-full rounded border border-slate-300 px-2 py-1 text-xs"
              />
            </label>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  void saveClientSettings(settings).then(() => {
                    void checkHealth()
                    setView(review ? 'results' : 'capture')
                  })
                }}
                className="flex-1 rounded bg-teal-600 px-3 py-1.5 font-semibold text-white hover:bg-teal-700"
              >
                Lưu & Kiểm tra
              </button>
              {token && (
                <button
                  type="button"
                  onClick={() => {
                    setToken(null)
                    if (typeof chrome !== 'undefined' && chrome.storage?.session) {
                      void chrome.storage.session.remove(TOKEN_STORAGE_KEY)
                    }
                  }}
                  className="rounded border border-slate-300 px-3 py-1.5 text-slate-700"
                >
                  Đăng xuất
                </button>
              )}
            </div>
          </section>
        )}

        {view !== 'settings' && needsLogin && (
          <form
            onSubmit={(e) => void handleSupabaseLogin(e)}
            className="space-y-2.5 rounded-lg border border-slate-200 bg-white p-3 text-xs"
          >
            <div className="flex items-center gap-1.5 font-semibold text-slate-800">
              <Lock className="h-4 w-4 text-teal-600" />
              Đăng nhập Dược sĩ Lâm sàng (Supabase Auth)
            </div>
            <input
              type="email"
              required
              placeholder="Email công vụ"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded border border-slate-300 px-2.5 py-1.5"
            />
            <input
              type="password"
              required
              placeholder="Mật khẩu"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded border border-slate-300 px-2.5 py-1.5"
            />
            {authError && <p className="text-rose-600">{authError}</p>}
            <button
              type="submit"
              className="w-full rounded bg-teal-600 px-3 py-2 font-semibold text-white hover:bg-teal-700"
            >
              Đăng nhập
            </button>
          </form>
        )}

        {view === 'capture' && !needsLogin && (
          <CapturePanel
            client={client}
            onReviewed={(res, nextRestoreMap) => {
              setReview(res)
              setRestoreMap(nextRestoreMap)
              setView('results')
            }}
          />
        )}

        {view === 'results' && review && !needsLogin && (
          <ResultsPanel
            client={client}
            review={review}
            restoreMap={restoreMap}
            onUpdated={(next) => setReview(next)}
            onOpenChat={(fid) => {
              setChatFindingId(fid)
              setView('chat')
            }}
            onPurged={() => {
              setReview(null)
              setRestoreMap({})
              setView('capture')
            }}
          />
        )}

        {view === 'chat' && review && !needsLogin && (
          <ChatDrawer
            client={client}
            sessionId={review.session_id}
            suggestedQuestions={review.chi_tiet.cau_hoi_goi_y}
            initialFindingId={chatFindingId}
            onBack={() => setView('results')}
          />
        )}
      </main>
    </div>
  )
}
