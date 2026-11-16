import { ApiError } from './client.ts'
import type { ReviewApiClient } from './client.ts'
import {
  MOCK_AI_ADDED_FINDINGS,
  MOCK_AI_ANNOTATIONS,
  MOCK_CASE_DETAILS,
  MOCK_CASES,
  MOCK_RECORDS,
  MOCK_SOURCES,
} from './mockData.ts'
import type {
  BanGhi,
  ChiTietCa,
  DanhSachCa,
  DoanNguon,
  GuiCauHoi,
  GuiPhanHoi,
  HealthResponse,
  KetQuaAI,
  NhanDinh,
  PhanHoiDaGhi,
  PhanHoiMa,
  TraLoi,
} from './types.ts'

export interface MockClientOptions {
  delayMs?: number
  aiDelayMs?: number
  cases?: DanhSachCa
  details?: Record<string, ChiTietCa>
  records?: Record<string, Record<string, BanGhi>>
  sources?: Record<string, Record<string, DoanNguon>>
}

const PHAN_HOI_NHAN: Record<PhanHoiMa, string> = {
  dong_y: 'Đồng ý',
  bac_bo: 'Bác bỏ',
  can_sua: 'Cần sửa',
}

function cloneData<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function formatNowTime(): string {
  const now = new Date()
  const dd = String(now.getDate()).padStart(2, '0')
  const mm = String(now.getMonth() + 1).padStart(2, '0')
  const yyyy = String(now.getFullYear())
  const hh = String(now.getHours()).padStart(2, '0')
  const min = String(now.getMinutes()).padStart(2, '0')
  return `${dd}/${mm}/${yyyy} ${hh}:${min}`
}

/** Client giả lập chạy độc lập không cần backend, lưu phản hồi trong bộ nhớ phiên. */
export class MockClient implements ReviewApiClient {
  private readonly delayMs: number
  private readonly aiDelayMs: number
  private readonly casesData: DanhSachCa
  private readonly detailsData: Record<string, ChiTietCa>
  private readonly recordsData: Record<string, Record<string, BanGhi>>
  private readonly sourcesData: Record<string, Record<string, DoanNguon>>
  private readonly aiRuns: Record<string, { startedAt: number; status: 'dang_chay' | 'xong' }> = {}
  private readonly aiFeedbackByCase: Record<string, Record<string, PhanHoiDaGhi>> = {}

  constructor(options: MockClientOptions = {}) {
    this.delayMs = options.delayMs ?? 90
    this.aiDelayMs = options.aiDelayMs ?? 3000
    this.casesData = cloneData(options.cases ?? MOCK_CASES)
    this.detailsData = cloneData(options.details ?? MOCK_CASE_DETAILS)
    this.recordsData = cloneData(options.records ?? MOCK_RECORDS)
    this.sourcesData = cloneData(options.sources ?? MOCK_SOURCES)
  }

  private async waitDelay(): Promise<void> {
    if (this.delayMs <= 0) {
      return
    }
    await new Promise<void>((resolve) => {
      setTimeout(resolve, this.delayMs)
    })
  }

  async getHealth(): Promise<HealthResponse> {
    await this.waitDelay()
    return {
      ok: true,
      che_do: cloneData(this.casesData.che_do),
    }
  }

  async getCases(): Promise<DanhSachCa> {
    await this.waitDelay()
    return cloneData(this.casesData)
  }

  async getCase(caId: string): Promise<ChiTietCa> {
    await this.waitDelay()
    const detail = this.detailsData[caId]
    if (!detail) {
      throw new ApiError('khong_tim_thay', `Không tìm thấy chi tiết ca ${caId}.`, 404)
    }
    return cloneData(detail)
  }

  async getRecord(caId: string, banGhiId: string): Promise<BanGhi> {
    await this.waitDelay()
    const caseRecords = this.recordsData[caId]
    const record = caseRecords?.[banGhiId]
    if (!record) {
      throw new ApiError(
        'khong_tim_thay',
        `Không tìm thấy bản ghi ${banGhiId} trong ca ${caId}.`,
        404,
      )
    }
    return cloneData(record)
  }

  async sendFeedback(caId: string, payload: GuiPhanHoi): Promise<PhanHoiDaGhi> {
    await this.waitDelay()
    const detail = this.detailsData[caId]
    if (!detail) {
      throw new ApiError('khong_tim_thay', `Không tìm thấy ca ${caId}.`, 404)
    }

    const detailTarget =
      detail.nhan_dinh.can_chu_y.find((item) => item.nhan_dinh_id === payload.nhan_dinh_id) ??
      detail.nhan_dinh.dat.find((item) => item.nhan_dinh_id === payload.nhan_dinh_id)

    const aiAdded = MOCK_AI_ADDED_FINDINGS[caId]
    const aiTarget =
      aiAdded?.can_chu_y.find((item) => item.nhan_dinh_id === payload.nhan_dinh_id) ??
      aiAdded?.dat.find((item) => item.nhan_dinh_id === payload.nhan_dinh_id)

    if (!detailTarget && !aiTarget) {
      throw new ApiError(
        'khong_tim_thay',
        `Không tìm thấy nhận định ${payload.nhan_dinh_id} trong ca ${caId}.`,
        404,
      )
    }

    if (payload.phan_hoi === 'bac_bo' || payload.phan_hoi === 'can_sua') {
      const reasonGroup = payload.nhom_ly_do?.trim() ?? ''
      if (!reasonGroup) {
        throw new ApiError(
          'du_lieu_khong_hop_le',
          'Vui lòng chọn nhóm lý do khi bác bỏ hoặc yêu cầu sửa.',
          422,
        )
      }
      if (!detail.nhom_ly_do.includes(reasonGroup)) {
        throw new ApiError('du_lieu_khong_hop_le', 'Nhóm lý do không nằm trong danh sách hợp lệ.', 422)
      }
    }

    const recorded: PhanHoiDaGhi = {
      phan_hoi: payload.phan_hoi,
      phan_hoi_nhan: PHAN_HOI_NHAN[payload.phan_hoi],
      nhom_ly_do: payload.nhom_ly_do ?? null,
      ly_do: payload.ly_do ?? null,
      thoi_diem_text: formatNowTime(),
    }

    if (detailTarget) {
      detailTarget.phan_hoi = recorded
    }
    if (!this.aiFeedbackByCase[caId]) {
      this.aiFeedbackByCase[caId] = {}
    }
    this.aiFeedbackByCase[caId][payload.nhan_dinh_id] = cloneData(recorded)

    const aiRun = this.aiRuns[caId]
    const attentionList =
      aiRun?.status === 'xong'
        ? this.buildAiDoneResult(caId, detail).nhan_dinh?.can_chu_y ?? detail.nhan_dinh.can_chu_y
        : detail.nhan_dinh.can_chu_y

    const allAttentionDone =
      attentionList.length > 0 && attentionList.every((item) => item.phan_hoi !== null)

    const queueRow = this.casesData.cases.find((item) => item.ca_id === caId)
    if (queueRow && allAttentionDone) {
      queueRow.da_phan_hoi_het = true
    }

    return cloneData(recorded)
  }

  async ask(caId: string, payload: GuiCauHoi): Promise<TraLoi> {
    await this.waitDelay()
    if (!this.detailsData[caId]) {
      throw new ApiError('khong_tim_thay', `Không tìm thấy ca ${caId}.`, 404)
    }
    if (!payload.cau_hoi.trim()) {
      throw new ApiError('du_lieu_khong_hop_le', 'Câu hỏi không được để trống.', 422)
    }
    return {
      trang_thai: 'chua_san_sang',
      noi_dung:
        'Chức năng hỏi thêm chưa được nối với hệ thống. Bảng nhận định bên trái vẫn dùng được.',
      trich_dan: [],
      cong_cu_da_goi: [],
    }
  }

  private buildAiDoneResult(caId: string, detail: ChiTietCa): KetQuaAI {
    const annotations = MOCK_AI_ANNOTATIONS[caId] ?? {}
    const added = MOCK_AI_ADDED_FINDINGS[caId]
    const feedbackMap = this.aiFeedbackByCase[caId] ?? {}

    const mapFinding = (item: NhanDinh): NhanDinh => {
      const cloned = cloneData(item)
      const patch = annotations[cloned.nhan_dinh_id]
      if (patch) {
        cloned.dien_giai_ai = patch.dien_giai_ai
        cloned.de_xuat_ai = patch.de_xuat_ai
        cloned.trich_dan = cloneData(patch.trich_dan)
      }
      const savedFeedback = feedbackMap[cloned.nhan_dinh_id]
      if (savedFeedback) {
        cloned.phan_hoi = cloneData(savedFeedback)
      }
      return cloned
    }

    const canChuY = [
      ...detail.nhan_dinh.can_chu_y.map(mapFinding),
      ...(added?.can_chu_y ?? []).map(mapFinding),
    ]
    const dat = [
      ...detail.nhan_dinh.dat.map(mapFinding),
      ...(added?.dat ?? []).map(mapFinding),
    ]

    return {
      trang_thai: 'xong',
      nhan_dinh: {
        can_chu_y: canChuY,
        dat,
      },
      canh_bao: [],
      thoi_gian_ms: this.aiDelayMs,
      mo_hinh: 'mock-ai',
    }
  }

  async startAi(caId: string, chayLai = false): Promise<KetQuaAI> {
    await this.waitDelay()
    const detail = this.detailsData[caId]
    if (!detail) {
      throw new ApiError('khong_tim_thay', `Không tìm thấy ca ${caId}.`, 404)
    }
    if (!detail.che_do.co_llm) {
      return {
        trang_thai: 'tat',
        nhan_dinh: null,
        canh_bao: [],
        thoi_gian_ms: null,
        mo_hinh: null,
      }
    }

    const existing = this.aiRuns[caId]
    if (existing && !chayLai) {
      if (existing.status === 'xong' || Date.now() - existing.startedAt >= this.aiDelayMs) {
        existing.status = 'xong'
        return this.buildAiDoneResult(caId, detail)
      }
      return {
        trang_thai: 'dang_chay',
        nhan_dinh: null,
        canh_bao: [],
        thoi_gian_ms: null,
        mo_hinh: null,
      }
    }

    this.aiRuns[caId] = { startedAt: Date.now(), status: 'dang_chay' }
    return {
      trang_thai: 'dang_chay',
      nhan_dinh: null,
      canh_bao: [],
      thoi_gian_ms: null,
      mo_hinh: null,
    }
  }

  async getAi(caId: string): Promise<KetQuaAI | null> {
    await this.waitDelay()
    const detail = this.detailsData[caId]
    if (!detail) {
      throw new ApiError('khong_tim_thay', `Không tìm thấy ca ${caId}.`, 404)
    }
    if (!detail.che_do.co_llm) {
      return {
        trang_thai: 'tat',
        nhan_dinh: null,
        canh_bao: [],
        thoi_gian_ms: null,
        mo_hinh: null,
      }
    }

    const existing = this.aiRuns[caId]
    if (!existing) {
      return null
    }
    if (existing.status === 'xong' || Date.now() - existing.startedAt >= this.aiDelayMs) {
      existing.status = 'xong'
      return this.buildAiDoneResult(caId, detail)
    }
    return {
      trang_thai: 'dang_chay',
      nhan_dinh: null,
      canh_bao: [],
      thoi_gian_ms: null,
      mo_hinh: null,
    }
  }

  async getSource(caId: string, doanTrichId: string): Promise<DoanNguon> {
    await this.waitDelay()
    if (!this.detailsData[caId]) {
      throw new ApiError('khong_tim_thay', `Không tìm thấy ca ${caId}.`, 404)
    }
    const source = this.sourcesData[caId]?.[doanTrichId]
    if (!source) {
      throw new ApiError(
        'khong_tim_thay',
        `Không tìm thấy đoạn nguồn ${doanTrichId} trong ca ${caId}.`,
        404,
      )
    }
    return cloneData(source)
  }
}
