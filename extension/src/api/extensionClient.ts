/**
 * Máy khách HTTP gọi dịch vụ Extension độc lập (cổng 8001).
 * Hỗ trợ cấu hình URL API, Supabase Bearer JWT và lọc liên kết chỉ nhận `https:`.
 */

import type {
  ClassifiedField,
  DoanNguon,
  ExtensionHealthResponse,
  ExtensionReviewResponse,
  ExtractEmrPayload,
  KetQuaAI,
  RecalcPayload,
  SchemaFieldDescriptor,
  TraLoi,
} from '../lib/types'

const EXT_VERSION = '1.10.0'
const DEFAULT_API_BASE = 'http://localhost:8001'
const SETTINGS_KEY = 'cdss_ext_settings_v1'

export interface ExtensionClientSettings {
  apiBaseUrl: string
  supabaseUrl: string
  supabaseAnonKey: string
}

export class ExtensionApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

export function sanitizeHttpsUrl(raw: string | null | undefined): string | null {
  if (!raw) return null
  try {
    const parsed = new URL(raw)
    if (parsed.protocol === 'https:') {
      return parsed.toString()
    }
    return null
  } catch {
    return null
  }
}

export async function loadClientSettings(): Promise<ExtensionClientSettings> {
  const fallback: ExtensionClientSettings = {
    apiBaseUrl: DEFAULT_API_BASE,
    supabaseUrl: '',
    supabaseAnonKey: '',
  }
  if (typeof chrome === 'undefined' || !chrome.storage?.local) {
    return fallback
  }
  const stored = await chrome.storage.local.get(SETTINGS_KEY)
  const raw = stored[SETTINGS_KEY] as Partial<ExtensionClientSettings> | undefined
  return {
    apiBaseUrl: (raw?.apiBaseUrl || DEFAULT_API_BASE).replace(/\/+$/, ''),
    supabaseUrl: (raw?.supabaseUrl || '').trim().replace(/\/+$/, ''),
    supabaseAnonKey: (raw?.supabaseAnonKey || '').trim(),
  }
}

export async function saveClientSettings(next: ExtensionClientSettings): Promise<void> {
  if (typeof chrome === 'undefined' || !chrome.storage?.local) return
  await chrome.storage.local.set({
    [SETTINGS_KEY]: {
      apiBaseUrl: (next.apiBaseUrl || DEFAULT_API_BASE).replace(/\/+$/, ''),
      supabaseUrl: next.supabaseUrl.trim().replace(/\/+$/, ''),
      supabaseAnonKey: next.supabaseAnonKey.trim(),
    },
  })
}

export class ExtensionApiClient {
  private readonly baseUrl: string
  private readonly token: string | null

  constructor(baseUrl: string = DEFAULT_API_BASE, token: string | null = null) {
    this.baseUrl = baseUrl.replace(/\/+$/, '')
    this.token = token
  }

  private headers(isJson: boolean): Record<string, string> {
    const out: Record<string, string> = {
      'X-Extension-Version': EXT_VERSION,
    }
    if (isJson) {
      out['Content-Type'] = 'application/json'
    }
    if (this.token) {
      out.Authorization = `Bearer ${this.token}`
    }
    return out
  }

  private async request<T>(path: string, init: RequestInit, isJson = true): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers: {
        ...this.headers(isJson),
        ...init.headers,
      },
    })
    if (!response.ok) {
      let code = `http_${response.status}`
      let message = `Lỗi máy chủ (${response.status})`
      try {
        const errBody = (await response.json()) as { ma?: string; thong_bao?: string }
        if (errBody.ma) code = errBody.ma
        if (errBody.thong_bao) message = errBody.thong_bao
      } catch {
        // Giữ thông báo mặc định.
      }
      throw new ExtensionApiError(response.status, code, message)
    }
    return (await response.json()) as T
  }

  health(): Promise<ExtensionHealthResponse> {
    return this.request<ExtensionHealthResponse>('/api/extension/health', { method: 'GET' }, false)
  }

  classifySchema(
    schemaHash: string,
    fields: SchemaFieldDescriptor[],
    sourceDomain?: string,
  ): Promise<{ schema_hash: string; mo_hinh: string | null; fields: ClassifiedField[] }> {
    return this.request('/api/extension/classify-schema', {
      method: 'POST',
      body: JSON.stringify({
        schema_hash: schemaHash,
        source_domain: sourceDomain ?? null,
        fields,
      }),
    })
  }

  extractAndReview(
    emrPayload: ExtractEmrPayload,
    ohImage: { blob: Blob; confirmedNoPii: boolean } | null,
  ): Promise<ExtensionReviewResponse> {
    const form = new FormData()
    form.append('emr_json', JSON.stringify(emrPayload))
    form.append('oh_crop_confirmed', ohImage?.confirmedNoPii ? 'true' : 'false')
    if (ohImage) {
      form.append('oh_image', ohImage.blob, 'oh-order-crop.png')
    }
    return this.request<ExtensionReviewResponse>(
      '/api/extension/extract-and-review',
      {
        method: 'POST',
        body: form,
      },
      false,
    )
  }

  recalc(sessionId: string, patch: RecalcPayload): Promise<ExtensionReviewResponse> {
    return this.request(`/api/extension/sessions/${encodeURIComponent(sessionId)}/recalc`, {
      method: 'POST',
      body: JSON.stringify(patch),
    })
  }

  startAi(sessionId: string, restart = false): Promise<KetQuaAI> {
    return this.request(`/api/extension/sessions/${encodeURIComponent(sessionId)}/ai`, {
      method: 'POST',
      body: JSON.stringify({ chay_lai: restart }),
    })
  }

  getAi(sessionId: string): Promise<KetQuaAI> {
    return this.request(
      `/api/extension/sessions/${encodeURIComponent(sessionId)}/ai`,
      { method: 'GET' },
      false,
    )
  }

  ask(sessionId: string, question: string, nhanDinhId?: string): Promise<TraLoi> {
    return this.request(`/api/extension/sessions/${encodeURIComponent(sessionId)}/ask`, {
      method: 'POST',
      body: JSON.stringify({
        cau_hoi: question,
        nhan_dinh_id: nhanDinhId ?? null,
      }),
    })
  }

  getAskProgress(
    sessionId: string,
  ): Promise<{ dang_chay: boolean; cac_buoc: KetQuaAI['cac_buoc']; da_chay_ms: number | null }> {
    return this.request(
      `/api/extension/sessions/${encodeURIComponent(sessionId)}/ask-progress`,
      { method: 'GET' },
      false,
    )
  }

  getSource(sessionId: string, chunkId: string): Promise<DoanNguon> {
    return this.request(
      `/api/extension/sessions/${encodeURIComponent(sessionId)}/sources/${encodeURIComponent(chunkId)}`,
      { method: 'GET' },
      false,
    )
  }

  deleteSession(sessionId: string): Promise<{ ok: boolean }> {
    return this.request(
      `/api/extension/sessions/${encodeURIComponent(sessionId)}`,
      { method: 'DELETE' },
      false,
    )
  }
}
