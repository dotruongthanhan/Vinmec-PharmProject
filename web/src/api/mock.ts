import { ApiError } from './client.ts'
import { MOCK_DRUGS, MOCK_FORMULAS, buildMockDrugDetail } from './mockLookup.ts'
import { foldName } from '../lib/lookup.ts'
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
  BuocAI,
  ChiTietCa,
  ChiTietThuoc,
  DanhMucCongThuc,
  DanhSachThuoc,
  DanhSachCa,
  DoanNguon,
  GoiYThuoc,
  GuiCauHoi,
  GuiPhanHoi,
  HealthResponse,
  KetQuaAI,
  KetQuaCongThuc,
  KetQuaGoiYThuoc,
  KetQuaTraTuongTac,
  MeResponse,
  NguonTomTat,
  NhanDinh,
  PhanHoiDaGhi,
  PhanHoiMa,
  TienTrinhHoiDap,
  TinhCongThucYeuCau,
  TraTuongTacYeuCau,
  TraLoi,
} from './types.ts'

export interface MockClientOptions {
  delayMs?: number
  aiDelayMs?: number
  askDelayMs?: number
  failAiCases?: readonly string[]
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

const MOCK_THUONG_LE_MS = 25_000

const MOCK_NGUON_TOM_TAT: NguonTomTat[] = [
  { nhan: 'openFDA', so_doan: 6 },
  { nhan: 'Bộ Y tế', so_doan: 4 },
  { nhan: 'DDInter', so_doan: 2 },
]

const MOCK_ASK_NGUON_TOM_TAT: NguonTomTat[] = [
  { nhan: 'openFDA', so_doan: 5 },
  { nhan: 'Bộ Y tế', so_doan: 3 },
]

const MOCK_ASK_DONE_RETENTION_MS = 60_000

interface MockAiRunState {
  startedAt: number
  status: 'dang_chay' | 'xong' | 'loi'
  attempt: number
  shouldFail: boolean
}

interface MockAskRunState {
  startedAt: number
  finishedAt: number | null
  status: 'dang_chay' | 'xong' | 'loi'
  isGlobal: boolean
  shouldFail: boolean
  stepsSnapshot: BuocAI[] | null
  daChayMsSnapshot: number | null
}

/** Client giả lập chạy độc lập không cần backend, lưu phản hồi trong bộ nhớ phiên. */
export class MockClient implements ReviewApiClient {
  private readonly delayMs: number
  private readonly aiDelayMs: number
  private readonly askDelayMs: number
  private readonly explicitFailAiCases: readonly string[] | null
  private readonly casesData: DanhSachCa
  private readonly detailsData: Record<string, ChiTietCa>
  private readonly recordsData: Record<string, Record<string, BanGhi>>
  private readonly sourcesData: Record<string, Record<string, DoanNguon>>
  private readonly aiRuns: Record<string, MockAiRunState> = {}
  private readonly askRuns: Record<string, MockAskRunState> = {}
  private readonly aiFeedbackByCase: Record<string, Record<string, PhanHoiDaGhi>> = {}

  constructor(options: MockClientOptions = {}) {
    this.delayMs = options.delayMs ?? 90
    this.aiDelayMs = options.aiDelayMs ?? 3000
    this.askDelayMs = options.askDelayMs ?? 1500
    this.explicitFailAiCases = options.failAiCases ?? null
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

  private async waitAskDelay(signal?: AbortSignal): Promise<void> {
    if (signal?.aborted) {
      throw new DOMException('Đã huỷ yêu cầu.', 'AbortError')
    }
    if (this.askDelayMs <= 0) {
      return
    }
    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => {
        signal?.removeEventListener('abort', onAbort)
        resolve()
      }, this.askDelayMs)

      const onAbort = () => {
        clearTimeout(timer)
        signal?.removeEventListener('abort', onAbort)
        reject(new DOMException('Đã huỷ yêu cầu.', 'AbortError'))
      }

      signal?.addEventListener('abort', onAbort, { once: true })
    })
  }

  async getHealth(): Promise<HealthResponse> {
    await this.waitDelay()
    return {
      ok: true,
      che_do: cloneData(this.casesData.che_do),
    }
  }

  async getMe(): Promise<MeResponse> {
    return { id: 'demo', email: null, vai_tro: 'duoc_si_ls', phien_id: null }
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

  async ask(
    caId: string,
    payload: GuiCauHoi,
    options?: { signal?: AbortSignal },
  ): Promise<TraLoi> {
    const isGlobal = caId === '__global__'
    if (isGlobal) {
      if (!payload.cau_hoi.trim()) {
        await this.waitDelay()
        throw new ApiError('du_lieu_khong_hop_le', 'Câu hỏi không được để trống.', 422)
      }
      if (payload.cau_hoi.trim().length > 1000) {
        await this.waitDelay()
        throw new ApiError('du_lieu_khong_hop_le', 'Câu hỏi vượt quá 1000 ký tự.', 422)
      }
    } else {
      const detail = this.detailsData[caId]
      if (!detail) {
        await this.waitDelay()
        throw new ApiError('khong_tim_thay', `Không tìm thấy ca ${caId}.`, 404)
      }
      if (!payload.cau_hoi.trim()) {
        await this.waitDelay()
        throw new ApiError('du_lieu_khong_hop_le', 'Câu hỏi không được để trống.', 422)
      }
      if (payload.cau_hoi.trim().length > 1000) {
        await this.waitDelay()
        throw new ApiError('du_lieu_khong_hop_le', 'Câu hỏi vượt quá 1000 ký tự.', 422)
      }
      if (!detail.che_do.hoi_them) {
        await this.waitDelay()
        return {
          trang_thai: 'chua_san_sang',
          noi_dung: 'Máy chủ chưa bật trợ lý.',
          trich_dan: [],
          cong_cu_da_goi: [],
          thoi_gian_ms: 0,
        }
      }
    }

    const shouldFail = payload.cau_hoi.toLowerCase().includes('lỗi')
    const run: MockAskRunState = {
      startedAt: Date.now(),
      finishedAt: null,
      status: 'dang_chay',
      isGlobal,
      shouldFail,
      stepsSnapshot: null,
      daChayMsSnapshot: null,
    }
    this.askRuns[caId] = run

    try {
      await this.waitAskDelay(options?.signal)
    } catch (err: unknown) {
      if (this.askRuns[caId] === run) {
        delete this.askRuns[caId]
      }
      throw err
    }

    const elapsed = Math.max(0, Date.now() - run.startedAt)
    if (run.shouldFail) {
      run.status = 'loi'
      run.finishedAt = Date.now()
      run.daChayMsSnapshot = elapsed
      run.stepsSnapshot = this.buildAskErrorSteps(isGlobal, elapsed)
      return {
        trang_thai: 'loi',
        noi_dung: 'Không hoàn tất xử lý câu hỏi do mô hình tạm thời gián đoạn.',
        trich_dan: [],
        cong_cu_da_goi: isGlobal ? ['danh_sach_y_lenh', 'truy_xuat'] : ['du_lieu_ca', 'truy_xuat'],
        thoi_gian_ms: elapsed,
      }
    }

    run.status = 'xong'
    run.finishedAt = Date.now()
    run.daChayMsSnapshot = elapsed
    run.stepsSnapshot = this.buildAskDoneSteps(isGlobal, elapsed)

    if (isGlobal) {
      return {
        trang_thai: 'ok',
        noi_dung:
          'Hiện tại danh sách có 6 y lệnh chờ thẩm định, trong đó DEMO-02 (Meropenem 1 g trên bệnh nhân CrCl 16,0 mL/phút) và DEMO-06 (Amoxicillin trên bệnh nhân có tiền sử dị ứng nhóm beta-lactam) ở mức nghiêm trọng cần ưu tiên xem trước.',
        trich_dan: [],
        cong_cu_da_goi: ['danh_sach_y_lenh', 'bo_luat'],
        thoi_gian_ms: elapsed || 800,
      }
    }

    const coHinh = /minh hoạ|minh họa|meropenem/i.test(payload.cau_hoi)
    if (caId !== 'DEMO-02' && coHinh) {
      const minhHoa = (await import('@/features/minh-hoa/mau/khoi-that-demo02-da-chinh.json')).default
      return {
        trang_thai: 'ok',
        noi_dung: 'Đây là hình minh hoạ từ dữ liệu giả lập DEMO-02.',
        minh_hoa: minhHoa as TraLoi['minh_hoa'],
        trich_dan: [],
        cong_cu_da_goi: [],
        thoi_gian_ms: elapsed || 1500,
      }
    }
    if (caId === 'DEMO-02') {
      const minhHoa = coHinh ? (await import('@/features/minh-hoa/mau/khoi-that-demo02-da-chinh.json')).default : []
      const focusNote = payload.nhan_dinh_id
        ? ' Đối với nhận định đang chọn về hiệu chỉnh liều theo chức năng thận,'
        : ''
      return {
        trang_thai: 'ok',
        minh_hoa: minhHoa as TraLoi['minh_hoa'],
        noi_dung: `${focusNote ? `${focusNote.trim()} ` : ''}Hồ sơ xét nghiệm ghi nhận creatinin máu tăng lên 212,0 µmol/L lúc 05:30 · 10/11/2026 [1], tương ứng CrCl ước tính theo Cockcroft-Gault là 16,0 mL/phút. Theo nhãn thuốc FDA MERREM IV, người bệnh suy giảm chức năng thận cần được xem xét hiệu chỉnh liều dùng [2].`,
        trich_dan: [
          {
            so: 1,
            loai_ma: 'du_lieu',
            nhan: 'Creatinin máu (XN-DEMO02-01)',
            ban_ghi_id: 'XN-DEMO02-01',
            doan_trich_id: null,
            trich_nguyen_van: null,
          },
          {
            so: 2,
            loai_ma: 'tai_lieu',
            nhan: 'Nhãn FDA MERREM IV · Liều dùng ở người bệnh suy thận',
            ban_ghi_id: null,
            doan_trich_id: 'fda_merrem_iv|renal_01',
            trich_nguyen_van:
              'Dosage adjustment is recommended for adult patients with impaired renal function.',
          },
        ],
        cong_cu_da_goi: ['du_lieu_ca', 'bo_luat', 'truy_xuat'],
        thoi_gian_ms: elapsed || 1500,
      }
    }

    return {
      trang_thai: 'khong_co_nguon',
      noi_dung: 'Không tìm thấy căn cứ trong kho nguồn hiện có cho câu hỏi này trên ca đang mở.',
      trich_dan: [],
      cong_cu_da_goi: ['du_lieu_ca', 'truy_xuat'],
      thoi_gian_ms: elapsed || 1500,
    }
  }

  async getAskProgress(
    caId: string,
    init?: { signal?: AbortSignal },
  ): Promise<TienTrinhHoiDap> {
    if (init?.signal?.aborted) {
      return { dang_chay: false, cac_buoc: [], da_chay_ms: null }
    }
    const run = this.askRuns[caId]
    if (!run) {
      return { dang_chay: false, cac_buoc: [], da_chay_ms: null }
    }
    if (run.status === 'dang_chay') {
      const elapsed = Math.max(0, Date.now() - run.startedAt)
      return {
        dang_chay: true,
        cac_buoc: this.buildAskRunningSteps(run.isGlobal, elapsed),
        da_chay_ms: elapsed,
      }
    }
    if (run.finishedAt !== null && Date.now() - run.finishedAt > MOCK_ASK_DONE_RETENTION_MS) {
      delete this.askRuns[caId]
      return { dang_chay: false, cac_buoc: [], da_chay_ms: null }
    }
    return {
      dang_chay: false,
      cac_buoc: cloneData(run.stepsSnapshot ?? []),
      da_chay_ms: run.daChayMsSnapshot,
    }
  }

  private buildAskRunningSteps(isGlobal: boolean, elapsedMs: number): BuocAI[] {
    const prepLabel = isGlobal ? 'Tổng hợp danh sách y lệnh' : 'Chuẩn bị ngữ cảnh ca'
    const prepDoneDetail = isGlobal ? '6 y lệnh' : 'đã sẵn sàng'
    const total = Math.max(1, this.askDelayMs)
    const t1 = Math.round(total * 0.15)
    const t2 = Math.round(total * 0.45)
    const t3 = Math.round(total * 0.8)

    if (elapsedMs < t1) {
      return [
        {
          ma: 'chuan_bi',
          ten: prepLabel,
          trang_thai: 'dang_chay',
          chi_tiet: isGlobal ? 'đang gom danh sách y lệnh…' : 'đang dựng dữ liệu ca…',
          nguon: [],
          thoi_gian_ms: elapsedMs,
          ly_do: null,
          goi_y: null,
        },
        {
          ma: 'truy_xuat',
          ten: 'Tra cứu nguồn',
          trang_thai: 'cho',
          chi_tiet: null,
          nguon: [],
          thoi_gian_ms: null,
          ly_do: null,
          goi_y: null,
        },
        {
          ma: 'goi_mo_hinh',
          ten: 'Soạn câu trả lời',
          trang_thai: 'cho',
          chi_tiet: null,
          nguon: [],
          thoi_gian_ms: null,
          ly_do: null,
          goi_y: null,
        },
        {
          ma: 'kiem_chung',
          ten: 'Kiểm chứng trích dẫn và số liệu',
          trang_thai: 'cho',
          chi_tiet: null,
          nguon: [],
          thoi_gian_ms: null,
          ly_do: null,
          goi_y: null,
        },
      ]
    }

    if (elapsedMs < t2) {
      return [
        {
          ma: 'chuan_bi',
          ten: prepLabel,
          trang_thai: 'xong',
          chi_tiet: prepDoneDetail,
          nguon: [],
          thoi_gian_ms: t1,
          ly_do: null,
          goi_y: null,
        },
        {
          ma: 'truy_xuat',
          ten: 'Tra cứu nguồn',
          trang_thai: 'dang_chay',
          chi_tiet: 'đang tìm trong kho nguồn…',
          nguon: [],
          thoi_gian_ms: Math.max(0, elapsedMs - t1),
          ly_do: null,
          goi_y: null,
        },
        {
          ma: 'goi_mo_hinh',
          ten: 'Soạn câu trả lời',
          trang_thai: 'cho',
          chi_tiet: null,
          nguon: [],
          thoi_gian_ms: null,
          ly_do: null,
          goi_y: null,
        },
        {
          ma: 'kiem_chung',
          ten: 'Kiểm chứng trích dẫn và số liệu',
          trang_thai: 'cho',
          chi_tiet: null,
          nguon: [],
          thoi_gian_ms: null,
          ly_do: null,
          goi_y: null,
        },
      ]
    }

    if (elapsedMs < t3) {
      return [
        {
          ma: 'chuan_bi',
          ten: prepLabel,
          trang_thai: 'xong',
          chi_tiet: prepDoneDetail,
          nguon: [],
          thoi_gian_ms: t1,
          ly_do: null,
          goi_y: null,
        },
        {
          ma: 'truy_xuat',
          ten: 'Tra cứu nguồn',
          trang_thai: 'xong',
          chi_tiet: '8 đoạn từ 2 nguồn',
          nguon: cloneData(MOCK_ASK_NGUON_TOM_TAT),
          thoi_gian_ms: Math.max(0, t2 - t1),
          ly_do: null,
          goi_y: null,
        },
        {
          ma: 'goi_mo_hinh',
          ten: 'Soạn câu trả lời',
          trang_thai: 'dang_chay',
          chi_tiet: 'đang gọi mô hình…',
          nguon: [],
          thoi_gian_ms: Math.max(0, elapsedMs - t2),
          ly_do: null,
          goi_y: null,
        },
        {
          ma: 'kiem_chung',
          ten: 'Kiểm chứng trích dẫn và số liệu',
          trang_thai: 'cho',
          chi_tiet: null,
          nguon: [],
          thoi_gian_ms: null,
          ly_do: null,
          goi_y: null,
        },
      ]
    }

    return [
      {
        ma: 'chuan_bi',
        ten: prepLabel,
        trang_thai: 'xong',
        chi_tiet: prepDoneDetail,
        nguon: [],
        thoi_gian_ms: t1,
        ly_do: null,
        goi_y: null,
      },
      {
        ma: 'truy_xuat',
        ten: 'Tra cứu nguồn',
        trang_thai: 'xong',
        chi_tiet: '8 đoạn từ 2 nguồn',
        nguon: cloneData(MOCK_ASK_NGUON_TOM_TAT),
        thoi_gian_ms: Math.max(0, t2 - t1),
        ly_do: null,
        goi_y: null,
      },
      {
        ma: 'goi_mo_hinh',
        ten: 'Soạn câu trả lời',
        trang_thai: 'xong',
        chi_tiet: 'đã nhận đầu ra',
        nguon: [],
        thoi_gian_ms: Math.max(0, t3 - t2),
        ly_do: null,
        goi_y: null,
      },
      {
        ma: 'kiem_chung',
        ten: 'Kiểm chứng trích dẫn và số liệu',
        trang_thai: 'dang_chay',
        chi_tiet: 'đang đối chiếu trích dẫn…',
        nguon: [],
        thoi_gian_ms: Math.max(0, elapsedMs - t3),
        ly_do: null,
        goi_y: null,
      },
    ]
  }

  private buildAskDoneSteps(isGlobal: boolean, elapsedMs: number): BuocAI[] {
    const prepLabel = isGlobal ? 'Tổng hợp danh sách y lệnh' : 'Chuẩn bị ngữ cảnh ca'
    const prepDoneDetail = isGlobal ? '6 y lệnh' : 'đã sẵn sàng'
    const total = Math.max(0, elapsedMs)
    const t1 = Math.round(total * 0.15)
    const t2 = Math.round(total * 0.45)
    const t3 = Math.round(total * 0.8)
    const t4 = Math.max(0, total - t3)

    return [
      {
        ma: 'chuan_bi',
        ten: prepLabel,
        trang_thai: 'xong',
        chi_tiet: prepDoneDetail,
        nguon: [],
        thoi_gian_ms: t1,
        ly_do: null,
        goi_y: null,
      },
      {
        ma: 'truy_xuat',
        ten: 'Tra cứu nguồn',
        trang_thai: 'xong',
        chi_tiet: '8 đoạn từ 2 nguồn',
        nguon: cloneData(MOCK_ASK_NGUON_TOM_TAT),
        thoi_gian_ms: Math.max(0, t2 - t1),
        ly_do: null,
        goi_y: null,
      },
      {
        ma: 'goi_mo_hinh',
        ten: 'Soạn câu trả lời',
        trang_thai: 'xong',
        chi_tiet: 'đã soạn câu trả lời',
        nguon: [],
        thoi_gian_ms: Math.max(0, t3 - t2),
        ly_do: null,
        goi_y: null,
      },
      {
        ma: 'kiem_chung',
        ten: 'Kiểm chứng trích dẫn và số liệu',
        trang_thai: 'xong',
        chi_tiet: 'kiểm chứng đạt',
        nguon: [],
        thoi_gian_ms: t4,
        ly_do: null,
        goi_y: null,
      },
    ]
  }

  private buildAskErrorSteps(isGlobal: boolean, elapsedMs: number): BuocAI[] {
    const prepLabel = isGlobal ? 'Tổng hợp danh sách y lệnh' : 'Chuẩn bị ngữ cảnh ca'
    const prepDoneDetail = isGlobal ? '6 y lệnh' : 'đã sẵn sàng'
    const total = Math.max(0, elapsedMs)
    const t1 = Math.round(total * 0.15)
    const t2 = Math.round(total * 0.45)

    return [
      {
        ma: 'chuan_bi',
        ten: prepLabel,
        trang_thai: 'xong',
        chi_tiet: prepDoneDetail,
        nguon: [],
        thoi_gian_ms: t1,
        ly_do: null,
        goi_y: null,
      },
      {
        ma: 'truy_xuat',
        ten: 'Tra cứu nguồn',
        trang_thai: 'xong',
        chi_tiet: '8 đoạn từ 2 nguồn',
        nguon: cloneData(MOCK_ASK_NGUON_TOM_TAT),
        thoi_gian_ms: Math.max(0, t2 - t1),
        ly_do: null,
        goi_y: null,
      },
      {
        ma: 'goi_mo_hinh',
        ten: 'Soạn câu trả lời',
        trang_thai: 'loi',
        chi_tiet: 'TimeoutError',
        nguon: [],
        thoi_gian_ms: Math.max(0, total - t2),
        ly_do: 'Nhà cung cấp mô hình tạm thời không phản hồi đúng hạn.',
        goi_y: 'Thử gửi lại câu hỏi sau ít phút hoặc kiểm tra lại đoạn nguồn.',
      },
      {
        ma: 'kiem_chung',
        ten: 'Kiểm chứng trích dẫn và số liệu',
        trang_thai: 'bo_qua',
        chi_tiet: null,
        nguon: [],
        thoi_gian_ms: null,
        ly_do: null,
        goi_y: null,
      },
    ]
  }

  private getMockTypicalMs(): number | null {
    return this.aiDelayMs > 0 ? MOCK_THUONG_LE_MS : null
  }

  private buildRunningSteps(elapsedMs: number): BuocAI[] {
    const t1 = Math.round(this.aiDelayMs * 0.25)
    const t2 = Math.round(this.aiDelayMs * 0.75)

    if (elapsedMs < t1) {
      return [
        {
          ma: 'thu_thap_nguon',
          ten: 'Lấy nguồn',
          trang_thai: 'dang_chay',
          chi_tiet: 'đang tìm trong kho nguồn…',
          nguon: [],
          thoi_gian_ms: elapsedMs,
          ly_do: null,
          goi_y: null,
        },
        {
          ma: 'tong_hop_1',
          ten: 'Tổng hợp nhận định',
          trang_thai: 'cho',
          chi_tiet: null,
          nguon: [],
          thoi_gian_ms: null,
          ly_do: null,
          goi_y: null,
        },
        {
          ma: 'kiem_chung_1',
          ten: 'Kiểm chứng trích dẫn',
          trang_thai: 'cho',
          chi_tiet: null,
          nguon: [],
          thoi_gian_ms: null,
          ly_do: null,
          goi_y: null,
        },
      ]
    }

    if (elapsedMs < t2) {
      return [
        {
          ma: 'thu_thap_nguon',
          ten: 'Lấy nguồn',
          trang_thai: 'xong',
          chi_tiet: '12 đoạn',
          nguon: cloneData(MOCK_NGUON_TOM_TAT),
          thoi_gian_ms: t1,
          ly_do: null,
          goi_y: null,
        },
        {
          ma: 'tong_hop_1',
          ten: 'Tổng hợp nhận định',
          trang_thai: 'dang_chay',
          chi_tiet: 'đang gọi mô hình…',
          nguon: [],
          thoi_gian_ms: Math.max(0, elapsedMs - t1),
          ly_do: null,
          goi_y: null,
        },
        {
          ma: 'kiem_chung_1',
          ten: 'Kiểm chứng trích dẫn',
          trang_thai: 'cho',
          chi_tiet: null,
          nguon: [],
          thoi_gian_ms: null,
          ly_do: null,
          goi_y: null,
        },
      ]
    }

    return [
      {
        ma: 'thu_thap_nguon',
        ten: 'Lấy nguồn',
        trang_thai: 'xong',
        chi_tiet: '12 đoạn',
        nguon: cloneData(MOCK_NGUON_TOM_TAT),
        thoi_gian_ms: t1,
        ly_do: null,
        goi_y: null,
      },
      {
        ma: 'tong_hop_1',
        ten: 'Tổng hợp nhận định',
        trang_thai: 'xong',
        chi_tiet: 'đã nhận đầu ra',
        nguon: [],
        thoi_gian_ms: Math.max(0, t2 - t1),
        ly_do: null,
        goi_y: null,
      },
      {
        ma: 'kiem_chung_1',
        ten: 'Kiểm chứng trích dẫn',
        trang_thai: 'dang_chay',
        chi_tiet: 'đang đối chiếu trích dẫn…',
        nguon: [],
        thoi_gian_ms: Math.max(0, elapsedMs - t2),
        ly_do: null,
        goi_y: null,
      },
    ]
  }

  private buildAiDoneSteps(): BuocAI[] {
    const t1 = Math.round(this.aiDelayMs * 0.25)
    const t2 = Math.round(this.aiDelayMs * 0.75)
    const t3 = Math.max(0, this.aiDelayMs - t2)
    return [
      {
        ma: 'thu_thap_nguon',
        ten: 'Lấy nguồn',
        trang_thai: 'xong',
        chi_tiet: '12 đoạn',
        nguon: cloneData(MOCK_NGUON_TOM_TAT),
        thoi_gian_ms: t1,
        ly_do: null,
        goi_y: null,
      },
      {
        ma: 'tong_hop_1',
        ten: 'Tổng hợp nhận định',
        trang_thai: 'xong',
        chi_tiet: 'đã tổng hợp nhận định',
        nguon: [],
        thoi_gian_ms: Math.max(0, t2 - t1),
        ly_do: null,
        goi_y: null,
      },
      {
        ma: 'kiem_chung_1',
        ten: 'Kiểm chứng trích dẫn',
        trang_thai: 'xong',
        chi_tiet: '3/3 dòng đạt',
        nguon: [],
        thoi_gian_ms: t3,
        ly_do: null,
        goi_y: null,
      },
    ]
  }

  private buildAiErrorResult(): KetQuaAI {
    const t1 = Math.round(this.aiDelayMs * 0.25)
    const failAt = Math.round(this.aiDelayMs * 0.75)
    return {
      trang_thai: 'loi',
      nhan_dinh: null,
      canh_bao: ['Không gọi được mô hình tổng hợp.'],
      thoi_gian_ms: failAt,
      mo_hinh: null,
      cac_buoc: [
        {
          ma: 'thu_thap_nguon',
          ten: 'Lấy nguồn',
          trang_thai: 'xong',
          chi_tiet: '12 đoạn',
          nguon: cloneData(MOCK_NGUON_TOM_TAT),
          thoi_gian_ms: t1,
          ly_do: null,
          goi_y: null,
        },
        {
          ma: 'tong_hop_1',
          ten: 'Tổng hợp nhận định',
          trang_thai: 'loi',
          chi_tiet: 'TimeoutError',
          nguon: [],
          thoi_gian_ms: Math.max(0, failAt - t1),
          ly_do: 'Nhà cung cấp mô hình tạm thời không phản hồi đúng hạn.',
          goi_y: 'Sử dụng bảng nhận định của bộ luật bên dưới và bấm "Thử lại" sau ít phút.',
        },
        {
          ma: 'kiem_chung_1',
          ten: 'Kiểm chứng trích dẫn',
          trang_thai: 'bo_qua',
          chi_tiet: null,
          nguon: [],
          thoi_gian_ms: null,
          ly_do: null,
          goi_y: null,
        },
      ],
      da_chay_ms: failAt,
      thuong_le_ms: this.getMockTypicalMs(),
    }
  }

  private buildAiRunningResult(elapsedMs: number): KetQuaAI {
    return {
      trang_thai: 'dang_chay',
      nhan_dinh: null,
      canh_bao: [],
      thoi_gian_ms: null,
      mo_hinh: null,
      cac_buoc: this.buildRunningSteps(elapsedMs),
      da_chay_ms: elapsedMs,
      thuong_le_ms: this.getMockTypicalMs(),
    }
  }

  private resolveRunState(caId: string, detail: ChiTietCa, run: MockAiRunState): KetQuaAI {
    const elapsed = Math.max(0, Date.now() - run.startedAt)
    if (run.shouldFail) {
      const failAt = this.aiDelayMs > 0 ? Math.round(this.aiDelayMs * 0.75) : 0
      if (run.status === 'loi' || elapsed >= failAt) {
        run.status = 'loi'
        return this.buildAiErrorResult()
      }
      return this.buildAiRunningResult(elapsed)
    }

    if (run.status === 'xong' || elapsed >= this.aiDelayMs) {
      run.status = 'xong'
      return this.buildAiDoneResult(caId, detail)
    }
    return this.buildAiRunningResult(elapsed)
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
      cac_buoc: this.buildAiDoneSteps(),
      da_chay_ms: this.aiDelayMs,
      thuong_le_ms: this.getMockTypicalMs(),
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
        cac_buoc: [],
        da_chay_ms: null,
        thuong_le_ms: null,
      }
    }

    const existing = this.aiRuns[caId]
    if (existing && !chayLai) {
      return this.resolveRunState(caId, detail, existing)
    }

    const attempt = (existing?.attempt ?? 0) + 1
    const shouldFail = this.explicitFailAiCases !== null
      ? this.explicitFailAiCases.includes(caId)
      : caId === 'DEMO-04' && attempt === 1

    const nextRun: MockAiRunState = {
      startedAt: Date.now(),
      status: 'dang_chay',
      attempt,
      shouldFail,
    }
    this.aiRuns[caId] = nextRun
    return this.resolveRunState(caId, detail, nextRun)
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
        cac_buoc: [],
        da_chay_ms: null,
        thuong_le_ms: null,
      }
    }

    const existing = this.aiRuns[caId]
    if (!existing) {
      return null
    }
    return this.resolveRunState(caId, detail, existing)
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

  async searchDrugs(params: { q?: string; trang?: number; soDong?: number }): Promise<DanhSachThuoc> {
    await this.waitDelay()
    const q = (params.q ?? '').trim().toLowerCase()
    const found = MOCK_DRUGS.filter(
      (d) => !q || d.ten_inn.includes(q) || (d.ten_viet ?? '').toLowerCase().includes(q),
    )
    return {
      tong: found.length,
      trang: params.trang ?? 1,
      so_dong: params.soDong ?? 30,
      ket_qua: cloneData(found),
      goi_y_sua: null,
    }
  }

  async suggestDrugs(
    q: string,
    options?: { signal?: AbortSignal; gioiHan?: number },
  ): Promise<KetQuaGoiYThuoc> {
    if (options?.signal?.aborted) {
      throw new DOMException('Đã huỷ yêu cầu.', 'AbortError')
    }
    await this.waitDelay()
    if (options?.signal?.aborted) {
      throw new DOMException('Đã huỷ yêu cầu.', 'AbortError')
    }
    const folded = foldName(q)
    if (folded.length < 2) {
      return { ket_qua: [], goi_y_sua: null }
    }
    const limit = Math.max(1, Math.min(15, options?.gioiHan ?? 8))
    const matches: GoiYThuoc[] = []
    for (const drug of MOCK_DRUGS) {
      const innFolded = foldName(drug.ten_inn)
      const vietFolded = drug.ten_viet ? foldName(drug.ten_viet) : ''
      if (innFolded === folded || innFolded.startsWith(folded)) {
        matches.push({
          nhan: drug.ten_inn,
          loai: 'hoat_chat',
          hoat_chat_ids: [drug.hoat_chat_id],
          ten_hoat_chat: [drug.ten_inn],
          gia_tri_gui: drug.ten_inn,
          khop: innFolded === folded ? 'chinh_xac' : 'tien_to',
        })
      } else if (vietFolded && (vietFolded === folded || vietFolded.startsWith(folded))) {
        const display = drug.ten_viet ?? drug.ten_inn
        matches.push({
          nhan: display,
          loai: 'dong_nghia',
          hoat_chat_ids: [drug.hoat_chat_id],
          ten_hoat_chat: [drug.ten_inn],
          gia_tri_gui: display,
          khop: vietFolded === folded ? 'chinh_xac' : 'tien_to',
        })
      }
      if (matches.length >= limit) break
    }
    return { ket_qua: matches, goi_y_sua: null }
  }

  async getDrug(hoatChatId: string): Promise<ChiTietThuoc> {
    await this.waitDelay()
    const detail = buildMockDrugDetail(hoatChatId)
    if (!detail) {
      throw new ApiError('khong_tim_thay', `Không tìm thấy hoạt chất ${hoatChatId}.`, 404)
    }
    return detail
  }

  async checkInteractions(payload: TraTuongTacYeuCau): Promise<KetQuaTraTuongTac> {
    await this.waitDelay()
    if (payload.thuoc.length < 2 || payload.thuoc.length > 12) {
      throw new ApiError('du_lieu_khong_hop_le', 'Cần nhập từ 2 đến 12 tên thuốc.', 422)
    }
    const ids = payload.thuoc.map((_, i) => `T${i + 1}`)
    const cap = ids.flatMap((a, i) =>
      ids.slice(i + 1).map((b) => ({
        a, b, muc: 'khong_phat_hien' as const, nhan_dinh_id: null, tom_tat: null, ly_do: null,
      })),
    )
    return {
      ma_tran: {
        nguon: 'DDInter (mock)',
        ghi_chu: 'Dữ liệu mock.',
        thuoc: payload.thuoc.map((ten, i) => ({
          chi_tiet_y_lenh_id: ids[i], ten, nhom: 'cho_duyet' as const,
          phan_giai: 'da_phan_giai' as const, hoat_chat: [ten.toLowerCase()], ly_do: null,
        })),
        cap,
        thuc_an: [],
      },
      phan_giai: payload.thuoc.map((ten, i) => ({
        ten_nhap: ten, chi_tiet_y_lenh_id: ids[i], trang_thai: 'da_phan_giai' as const,
        hoat_chat: [ten.toLowerCase()], ly_do: null,
      })),
      chi_tiet: [],
    }
  }

  async getFormulas(): Promise<DanhMucCongThuc> {
    await this.waitDelay()
    return cloneData(MOCK_FORMULAS)
  }

  async calculateFormula(ma: string, payload: TinhCongThucYeuCau): Promise<KetQuaCongThuc> {
    await this.waitDelay()
    const spec = MOCK_FORMULAS.cong_thuc.find((f) => f.ma === ma)
    if (!spec) {
      throw new ApiError('khong_tim_thay', `Không tìm thấy công thức ${ma}.`, 404)
    }
    const empty = (v: unknown) => v === undefined || v === null || v === ''
    const missing = spec.dau_vao.filter((d) => d.bat_buoc && empty(payload.dau_vao[d.ten])).map((d) => d.ten)
    const w = Number(payload.dau_vao['can_nang_kg'])
    const h = Number(payload.dau_vao['chieu_cao_cm'])
    const value = ma === 'bmi' && missing.length === 0 ? w / (h / 100) ** 2 : null
    return {
      ma, cong_thuc: spec.ten, phien_ban: 'mock', ket_qua: value, don_vi: spec.dau_ra.don_vi[0] ?? '',
      dau_vao_da_dung: [], thieu_dau_vao: missing, ghi_chu: [], tham_khao: spec.tham_khao_goc[0] ?? '',
      trang_thai: spec.trang_thai,
    }
  }
}
