import type {
  BanGhi,
  ChiTietCa,
  ChiTietThuoc,
  DanhMucCongThuc,
  DanhSachCa,
  DanhSachThuoc,
  DoanNguon,
  GuiCauHoi,
  GuiPhanHoi,
  HealthResponse,
  KetQuaAI,
  KetQuaCongThuc,
  KetQuaTraTuongTac,
  MeResponse,
  PhanHoiDaGhi,
  TinhCongThucYeuCau,
  TraLoi,
  TraTuongTacYeuCau,
} from './types.ts'

/** Lỗi chuẩn hoá từ API backend hoặc lỗi kết nối / định dạng. */
export class ApiError extends Error {
  readonly ma: string
  readonly thong_bao: string
  readonly status: number

  constructor(ma: string, thong_bao: string, status: number) {
    super(thong_bao)
    this.name = 'ApiError'
    this.ma = ma
    this.thong_bao = thong_bao
    this.status = status
  }
}

export interface SavedConversationTurn {
  cau_hoi: string
  tra_loi: TraLoi
  thoi_diem?: string
}

export interface ReviewApiClient {
  abortAll?(): void
  signOut?(token: string): Promise<void>
  getMe(): Promise<MeResponse>
  getHealth(): Promise<HealthResponse>
  getCases(options?: { signal?: AbortSignal }): Promise<DanhSachCa>
  getCase(caId: string, options?: { signal?: AbortSignal }): Promise<ChiTietCa>
  getRecord(caId: string, banGhiId: string): Promise<BanGhi>
  sendFeedback(caId: string, payload: GuiPhanHoi): Promise<PhanHoiDaGhi>
  ask(caId: string, payload: GuiCauHoi, options?: { signal?: AbortSignal }): Promise<TraLoi>
  startAi(caId: string, chayLai?: boolean): Promise<KetQuaAI>
  getAi(caId: string): Promise<KetQuaAI | null>
  getSource(caId: string, doanTrichId: string): Promise<DoanNguon>
  /** Tra cứu thuốc (hợp đồng v1.8). `trang` bắt đầu từ 1. */
  searchDrugs(params: { q?: string; trang?: number; soDong?: number }, options?: { signal?: AbortSignal }): Promise<DanhSachThuoc>
  getDrug(hoatChatId: string, options?: { signal?: AbortSignal }): Promise<ChiTietThuoc>
  checkInteractions(payload: TraTuongTacYeuCau, options?: { signal?: AbortSignal }): Promise<KetQuaTraTuongTac>
  getFormulas(options?: { signal?: AbortSignal }): Promise<DanhMucCongThuc>
  calculateFormula(ma: string, payload: TinhCongThucYeuCau, options?: { signal?: AbortSignal }): Promise<KetQuaCongThuc>
  getConversations?(): Promise<Record<string, SavedConversationTurn[]>>
  clearConversation?(caId: string): Promise<void>
}

export type FetchLike = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>

export interface AuthHooks {
  getAccessToken(): Promise<string | null>
  refreshSession(): Promise<unknown | null>
  onUnauthorized(): void | Promise<void>
  onForbidden?(): void
}

function isRecordObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function extractApiError(parsed: unknown): { ma: string; thong_bao: string } | null {
  if (!isRecordObject(parsed)) {
    return null
  }
  const loi = parsed['loi']
  if (!isRecordObject(loi)) {
    return null
  }
  const ma = loi['ma']
  const thongBao = loi['thong_bao']
  if (typeof ma === 'string' && typeof thongBao === 'string') {
    return { ma, thong_bao: thongBao }
  }
  return null
}

/** Giao tiếp HTTP với backend FastAPI qua đường dẫn gốc /api. */
export class ApiClient implements ReviewApiClient {
  private readonly baseUrl: string
  private readonly fetchImpl?: FetchLike
  private readonly auth?: AuthHooks
  private refreshPromise: Promise<string | null> | null = null
  private refreshRevision = 0
  private controller = new AbortController()

  constructor(baseUrl = '/api', fetchImpl?: FetchLike, auth?: AuthHooks) {
    this.baseUrl = baseUrl.replace(/\/+$/, '')
    this.fetchImpl = fetchImpl
    this.auth = auth
  }

  private async refreshToken(revision: number): Promise<string | null> {
    if (!this.auth) return null
    if (this.refreshPromise) return this.refreshPromise
    // Một phản hồi 401 đến muộn dùng lại kết quả gia hạn vừa hoàn tất.
    if (revision !== this.refreshRevision) return this.auth.getAccessToken()
    this.refreshPromise = (async () => {
      try {
        if (!await this.auth!.refreshSession()) return null
        return await this.auth!.getAccessToken()
      } catch {
        return null
      } finally {
        this.refreshRevision += 1
      }
    })().finally(() => { this.refreshPromise = null })
    return this.refreshPromise
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const controller = new AbortController()
    const signals = [this.controller.signal, init?.signal].filter((signal): signal is AbortSignal => !!signal)
    const abort = () => controller.abort()
    for (const signal of signals) {
      if (signal.aborted) abort()
      else signal.addEventListener('abort', abort, { once: true })
    }
    try {
      const revision = this.refreshRevision
      const token = await this.auth?.getAccessToken() ?? null
      controller.signal.throwIfAborted()
      return await this.send<T>(path, { ...init, signal: controller.signal }, token, revision, false, token ? [token] : [])
    } finally {
      for (const signal of signals) signal.removeEventListener('abort', abort)
    }
  }

  /** Huỷ mọi yêu cầu của phiên hiện tại, kể cả khi đang chờ token. */
  abortAll(): void {
    this.controller.abort()
    this.controller = new AbortController()
  }

  /** Báo thu hồi một lần; lỗi hoặc quá ba giây không cản đăng xuất. */
  async signOut(token: string): Promise<void> {
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout> | undefined
    try {
      await Promise.race([
        (this.fetchImpl ?? globalThis.fetch)(`${this.baseUrl}/dang-xuat`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        }),
        new Promise<void>((resolve) => {
          timer = setTimeout(() => { controller.abort(); resolve() }, 3000)
        }),
      ])
    } catch {
      // Không đưa token hoặc chi tiết lỗi ra giao diện và nhật ký.
    } finally {
      if (timer !== undefined) clearTimeout(timer)
    }
  }

  private async send<T>(path: string, init: RequestInit | undefined, token: string | null,
    revision: number, retried: boolean, secrets: string[]): Promise<T> {
    init?.signal?.throwIfAborted()
    const fetchFn: FetchLike = this.fetchImpl ?? globalThis.fetch
    const headers = new Headers(init?.headers)
    if (token) headers.set('Authorization', `Bearer ${token}`)
    const redact = (message: string): string => secrets.reduce(
      (safe, secret) => safe.split(secret).join('[ẩn]'), message,
    )
    let response: Response
    try {
      response = await fetchFn(`${this.baseUrl}${path}`, { ...init, headers })
      init?.signal?.throwIfAborted()
    } catch (err) {
      if (
        (err instanceof DOMException && err.name === 'AbortError') ||
        (err instanceof Error && err.name === 'AbortError')
      ) {
        throw err
      }
      if (err instanceof ApiError) {
        throw new ApiError(redact(err.ma), redact(err.thong_bao), err.status)
      }
      const message =
        err instanceof Error && err.message
          ? `Không thể kết nối máy chủ: ${err.message}`
          : 'Không thể kết nối máy chủ.'
      throw new ApiError('loi_he_thong', redact(message), 0)
    }

    if (response.status === 401 && this.auth && !retried) {
      const nextToken = await this.refreshToken(revision)
      init?.signal?.throwIfAborted()
      if (nextToken) {
        return this.send<T>(path, init, nextToken, this.refreshRevision, true, [...secrets, nextToken])
      }
    }
    let rawText = ''
    try {
      rawText = await response.text()
    } catch {
      init?.signal?.throwIfAborted()
      throw new ApiError('loi_he_thong', 'Không đọc được phản hồi từ máy chủ.', response.status)
    }
    init?.signal?.throwIfAborted()

    let parsed: unknown = null
    let jsonValid = false
    if (rawText.trim() !== '') {
      try {
        parsed = JSON.parse(rawText) as unknown
        jsonValid = true
      } catch {
        jsonValid = false
      }
    }

    if (response.status === 401 && this.auth) {
      await this.auth.onUnauthorized()
    }

    if (!response.ok) {
      if (jsonValid) {
        const structured = extractApiError(parsed)
        if (structured !== null) {
          if (response.status === 403 && structured.ma === 'khong_co_quyen') this.auth?.onForbidden?.()
          throw new ApiError(redact(structured.ma), redact(structured.thong_bao), response.status)
        }
      }
      const fallbackMsg = rawText.trim() || `Yêu cầu thất bại (HTTP ${response.status})`
      const fallbackCode = response.status === 401 ? 'chua_dang_nhap' : 'loi_he_thong'
      throw new ApiError(fallbackCode, redact(fallbackMsg), response.status)
    }

    if (!jsonValid) {
      throw new ApiError(
        'loi_he_thong',
        'Phản hồi máy chủ không đúng định dạng JSON.',
        response.status,
      )
    }

    return parsed as T
  }

  getHealth(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/health')
  }

  getMe(): Promise<MeResponse> {
    return this.request<MeResponse>('/me')
  }

  getCases(options?: { signal?: AbortSignal }): Promise<DanhSachCa> {
    return this.request<DanhSachCa>('/cases', { signal: options?.signal })
  }

  getCase(caId: string, options?: { signal?: AbortSignal }): Promise<ChiTietCa> {
    return this.request<ChiTietCa>(`/cases/${encodeURIComponent(caId)}`, { signal: options?.signal })
  }

  getRecord(caId: string, banGhiId: string): Promise<BanGhi> {
    return this.request<BanGhi>(
      `/cases/${encodeURIComponent(caId)}/records/${encodeURIComponent(banGhiId)}`,
    )
  }

  sendFeedback(caId: string, payload: GuiPhanHoi): Promise<PhanHoiDaGhi> {
    return this.request<PhanHoiDaGhi>(`/cases/${encodeURIComponent(caId)}/feedback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    })
  }

  ask(caId: string, payload: GuiCauHoi, options?: { signal?: AbortSignal }): Promise<TraLoi> {
    return this.request<TraLoi>(`/cases/${encodeURIComponent(caId)}/ask`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
      signal: options?.signal,
    })
  }

  startAi(caId: string, chayLai?: boolean): Promise<KetQuaAI> {
    return this.request<KetQuaAI>(`/cases/${encodeURIComponent(caId)}/ai`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ chay_lai: Boolean(chayLai) }),
    })
  }

  async getAi(caId: string): Promise<KetQuaAI | null> {
    try {
      return await this.request<KetQuaAI>(`/cases/${encodeURIComponent(caId)}/ai`)
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 404 && err.ma === 'chua_chay') {
        return null
      }
      throw err
    }
  }

  getSource(caId: string, doanTrichId: string): Promise<DoanNguon> {
    return this.request<DoanNguon>(
      `/cases/${encodeURIComponent(caId)}/sources/${encodeURIComponent(doanTrichId)}`,
    )
  }

  searchDrugs(params: { q?: string; trang?: number; soDong?: number }, options?: { signal?: AbortSignal }): Promise<DanhSachThuoc> {
    const query = new URLSearchParams()
    if (params.q) query.set('q', params.q)
    query.set('trang', String(params.trang ?? 1))
    query.set('so_dong', String(params.soDong ?? 30))
    return this.request<DanhSachThuoc>(`/thuoc?${query.toString()}`, { signal: options?.signal })
  }

  getDrug(hoatChatId: string, options?: { signal?: AbortSignal }): Promise<ChiTietThuoc> {
    return this.request<ChiTietThuoc>(`/thuoc/${encodeURIComponent(hoatChatId)}`, { signal: options?.signal })
  }

  checkInteractions(payload: TraTuongTacYeuCau, options?: { signal?: AbortSignal }): Promise<KetQuaTraTuongTac> {
    return this.request<KetQuaTraTuongTac>('/tuong-tac', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: options?.signal,
    })
  }

  getFormulas(options?: { signal?: AbortSignal }): Promise<DanhMucCongThuc> {
    return this.request<DanhMucCongThuc>('/cong-thuc', { signal: options?.signal })
  }

  calculateFormula(ma: string, payload: TinhCongThucYeuCau, options?: { signal?: AbortSignal }): Promise<KetQuaCongThuc> {
    return this.request<KetQuaCongThuc>(`/cong-thuc/${encodeURIComponent(ma)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: options?.signal,
    })
  }

  getConversations(): Promise<Record<string, SavedConversationTurn[]>> {
    return this.request<Record<string, SavedConversationTurn[]>>('/conversations')
  }

  async clearConversation(caId: string): Promise<void> {
    await this.request<{ ok: boolean }>(`/conversations/${encodeURIComponent(caId)}/clear`, {
      method: 'POST',
    })
  }
}
