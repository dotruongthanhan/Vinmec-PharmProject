import type {
  BanGhi,
  ChiTietCa,
  DanhSachCa,
  DoanNguon,
  GuiCauHoi,
  GuiPhanHoi,
  HealthResponse,
  KetQuaAI,
  PhanHoiDaGhi,
  TraLoi,
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

export interface ReviewApiClient {
  getHealth(): Promise<HealthResponse>
  getCases(): Promise<DanhSachCa>
  getCase(caId: string): Promise<ChiTietCa>
  getRecord(caId: string, banGhiId: string): Promise<BanGhi>
  sendFeedback(caId: string, payload: GuiPhanHoi): Promise<PhanHoiDaGhi>
  ask(caId: string, payload: GuiCauHoi, options?: { signal?: AbortSignal }): Promise<TraLoi>
  startAi(caId: string, chayLai?: boolean): Promise<KetQuaAI>
  getAi(caId: string): Promise<KetQuaAI | null>
  getSource(caId: string, doanTrichId: string): Promise<DoanNguon>
}

export type FetchLike = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>

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

  constructor(baseUrl = '/api', fetchImpl?: FetchLike) {
    this.baseUrl = baseUrl.replace(/\/+$/, '')
    this.fetchImpl = fetchImpl
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const fetchFn: FetchLike = this.fetchImpl ?? globalThis.fetch
    let response: Response
    try {
      response = await fetchFn(`${this.baseUrl}${path}`, init)
    } catch (err) {
      if (
        (err instanceof DOMException && err.name === 'AbortError') ||
        (err instanceof Error && err.name === 'AbortError')
      ) {
        throw err
      }
      if (err instanceof ApiError) {
        throw err
      }
      const message =
        err instanceof Error && err.message
          ? `Không thể kết nối máy chủ: ${err.message}`
          : 'Không thể kết nối máy chủ.'
      throw new ApiError('loi_he_thong', message, 0)
    }

    let rawText = ''
    try {
      rawText = await response.text()
    } catch {
      throw new ApiError('loi_he_thong', 'Không đọc được phản hồi từ máy chủ.', response.status)
    }

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

    if (!response.ok) {
      if (jsonValid) {
        const structured = extractApiError(parsed)
        if (structured !== null) {
          throw new ApiError(structured.ma, structured.thong_bao, response.status)
        }
      }
      const fallbackMsg = rawText.trim() || `Yêu cầu thất bại (HTTP ${response.status})`
      throw new ApiError('loi_he_thong', fallbackMsg, response.status)
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

  getCases(): Promise<DanhSachCa> {
    return this.request<DanhSachCa>('/cases')
  }

  getCase(caId: string): Promise<ChiTietCa> {
    return this.request<ChiTietCa>(`/cases/${encodeURIComponent(caId)}`)
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
}
