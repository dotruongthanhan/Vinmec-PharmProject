import { Children, isValidElement } from 'react'
import type { ReactElement, ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MOCK_CASE_DETAILS, MOCK_CASES } from '../api/mockData'
import { MockClient } from '../api/mock'
import type { ChiTietCa, MedicalOrder, PhanHoiDaGhi } from '../api/types'
import { OrderDetailView } from '../features/order-detail/OrderDetailView'
import { OrderChoices, OrderSelector, TreatmentSheets } from '../features/order-detail/MedicalRecordSections'
import { OrderLinesTable } from '../features/order-detail/DetailSections'
import { Popover } from '../components/ui/popover'
import { FeedbackBar } from '../features/findings/FeedbackBar'
import { FindingCard } from '../features/findings/FindingCard'
import { useCases } from '../state/useCases'
import { useCaseDetail } from '../state/useCaseDetail'
import { EMPTY_FEEDBACK_DRAFT } from '../lib/uiTypes'
import type { FeedbackDraft } from '../lib/uiTypes'

// Bộ chạy hook cục bộ theo mẫu test vòng đời có sẵn; không cần DOM hay thư viện mới.
const hooks = vi.hoisted(() => {
  type Slot = { value?: unknown; deps?: unknown[]; cleanup?: () => void }
  let slots: Slot[] = []
  let cursor = 0
  let effects: (() => void)[] = []
  const slot = () => slots[cursor++] ?? (slots[cursor - 1] = {})
  return {
    useState(initial: unknown) {
      const cell = slot()
      if (!('value' in cell)) cell.value = typeof initial === 'function' ? initial() : initial
      return [cell.value, (next: unknown) => { cell.value = typeof next === 'function' ? next(cell.value) : next }]
    },
    useRef(initial: unknown) {
      const cell = slot()
      return cell.value ?? (cell.value = { current: initial })
    },
    useMemo(fn: () => unknown) { return fn() },
    useCallback(fn: unknown) { return fn },
    useEffect(fn: () => void | (() => void), deps: unknown[]) {
      const cell = slot()
      if (!cell.deps || deps.some((value, index) => !Object.is(value, cell.deps![index]))) {
        cell.deps = deps
        effects.push(() => {
          cell.cleanup?.()
          cell.cleanup = fn() || undefined
        })
      }
    },
    run<T,>(fn: () => T): T {
      cursor = 0
      const result = fn()
      for (const effect of effects.splice(0)) effect()
      return result
    },
    reset() {
      for (const cell of slots) cell.cleanup?.()
      slots = []; effects = []; cursor = 0
    },
  }
})
const navigation = vi.hoisted(() => ({
  params: new URLSearchParams(),
  state: { fromRecords: true },
  options: {} as { replace?: boolean; state?: unknown },
  set(next: URLSearchParams | ((previous: URLSearchParams) => URLSearchParams), options = {}) {
    navigation.params = typeof next === 'function' ? next(navigation.params) : next
    navigation.options = options
  },
}))
vi.mock('react', async (original) => ({ ...await original<typeof import('react')>(), ...hooks }))
vi.mock('react-router-dom', async (original) => ({
  ...await original<typeof import('react-router-dom')>(),
  useSearchParams: () => [navigation.params, navigation.set],
  useLocation: () => ({ state: navigation.state }),
}))

type Element = ReactElement<{
  children?: ReactNode
  open?: boolean
  onOpenChange?: (open: boolean) => void
  selected?: MedicalOrder
  selectedDrug?: string | null
  onSelect?: (id: string) => void
  onSelectDrug?: (name: string) => void
  onFollowOrder?: () => void
  feedbackDraft?: FeedbackDraft
  onFeedbackDraftChange?: (draft: FeedbackDraft) => void
  onValueChange?: (value: string) => void
  onClick?: (event: { button: number }) => void
  onChange?: (event: { target: { value: string } }) => void
  value?: string
  onKeyDown?: (event: { key: string; target: object; currentTarget: object; preventDefault: () => void }) => void
  role?: string
}>
function elements(node: ReactNode): Element[] {
  if (!isValidElement(node)) return []
  const item = node as Element
  return [item, ...Children.toArray(item.props.children).flatMap(elements)]
}
const base = MOCK_CASE_DETAILS['DEMO-02']
const focus: MedicalOrder = { y_lenh_id: 'YL-TT', dot_dieu_tri_id: 'DT-2', thu_tu_dot: 2,
  la_trong_tam: true, ...base.chi_tiet.y_lenh.cho_duyet }
const other: MedicalOrder = { ...focus, y_lenh_id: 'YL-CU', la_trong_tam: false }
const detail = { ...base, danh_sach_y_lenh: [other, focus] }
function detailTree(value: ChiTietCa, orderSelectionReady = true) {
  return OrderDetailView({ detail: value, orderSelectionReady, aiTrangThai: 'tat', aiKetQua: null,
    aiThoiGianMs: null, aiCanhBao: [], sessionFeedbackForCase: {}, onRerunAi() {},
    isFeedbackSubmitting: () => false, getFeedbackError: () => null, onSubmitFeedback: async () => true,
    onClearFeedbackError() {}, onOpenEvidence() {}, onAskAboutFinding() {},
  })
}
function render(value: ChiTietCa = detail) {
  return hooks.run(() => detailTree(value))
}
function selector(tree: ReactNode) { return elements(tree).find((item) => item.type === OrderSelector)! }

beforeEach(() => {
  hooks.reset()
  navigation.params = new URLSearchParams('tab=y_lenh')
  navigation.options = {}
  vi.stubGlobal('requestAnimationFrame', (fn: () => void) => fn())
})

afterEach(() => {
  hooks.reset()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  vi.useRealTimers()
})

describe('vòng đời lựa chọn y lệnh', () => {
  it('gọi bộ chọn đổi URL và nội dung, tải lại giữ mã đã chọn', () => {
    const initial = render()
    expect(selector(initial).props.selected?.y_lenh_id).toBe('YL-TT')
    selector(initial).props.onSelect!('YL-CU')
    expect(navigation.params.toString()).toBe('tab=y_lenh&yl=YL-CU')
    expect(navigation.options).toEqual({ replace: true, state: navigation.state })
    expect(selector(render()).props.selected?.y_lenh_id).toBe('YL-CU')
    hooks.reset()
    expect(selector(render()).props.selected?.y_lenh_id).toBe('YL-CU')
  })
  it('đổi ca bỏ lựa chọn cũ khi URL đích không có yl và Back giữ yl', () => {
    const previous = new URLSearchParams('tab=y_lenh&yl=YL-CU')
    navigation.params = previous
    expect(selector(render()).props.selected?.y_lenh_id).toBe('YL-CU')
    const next = { ...detail, ca_id: 'CA-MOI', danh_sach_y_lenh: [other, { ...focus, y_lenh_id: 'YL-MOI' }] }
    navigation.params = new URLSearchParams('tab=y_lenh')
    expect(selector(render(next)).props.selected?.y_lenh_id).toBe('YL-MOI')
    expect(navigation.params.get('yl')).toBeNull()
    navigation.params = previous
    expect(selector(render()).props.selected?.y_lenh_id).toBe('YL-CU')
    expect(navigation.params.get('yl')).toBe('YL-CU')
  })
  it('liên kết sâu sang ca khác giữ yl hợp lệ', () => {
    render()
    navigation.params = new URLSearchParams('tab=y_lenh&yl=YL-CU')
    const next = { ...detail, ca_id: 'CA-MOI', danh_sach_y_lenh: [other, { ...focus, y_lenh_id: 'YL-MOI' }] }
    expect(selector(render(next)).props.selected?.y_lenh_id).toBe('YL-CU')
    expect(navigation.params.get('yl')).toBe('YL-CU')
  })
  it('yl rác về trọng tâm, thay URL, giữ tab và hiện thông báo', () => {
    navigation.params = new URLSearchParams('tab=y_lenh&yl=RAC&khac=1')
    expect(selector(render()).props.selected?.y_lenh_id).toBe('YL-TT')
    expect(navigation.params.toString()).toBe('tab=y_lenh&khac=1')
    expect(navigation.options).toEqual({ replace: true, state: navigation.state })
    expect(elements(render()).some((item) => item.props.role === 'status' &&
      String(item.props.children).includes('RAC'))).toBe(true)
  })
  it('đổi tab giữ nguồn điều hướng và liên kết phiếu xóa lọc thuốc', () => {
    const withSheets = { ...detail, phieu_dieu_tri: [{
      phieu_dieu_tri_id: 'P-1', dot_dieu_tri_id: 'DT-2', ngay_dieu_tri: 1, thoi_diem_lap: '',
      vai_tro_nguoi_lap: '', dien_bien: '', danh_gia: '', huong_xu_tri: '', che_do_an: '',
      che_do_cham_soc: null, dan_do: null,
      theo_doi: [], y_lenh_trong_ngay: ['YL-TT'],
    }] }
    const initial = render(withSheets)
    elements(initial).find((item) => item.type === OrderLinesTable)!.props.onSelectDrug!('Meropenem')
    expect(elements(render(withSheets)).find((item) => item.type === OrderLinesTable)!.props.selectedDrug).toBe('Meropenem')
    render(withSheets).props.onValueChange('phieu_dieu_tri')
    expect(navigation.options.state).toEqual(navigation.state)
    const sheetView = elements(render(withSheets)).find((item) => item.type === TreatmentSheets)!
    const link = elements(TreatmentSheets({ detail: withSheets, onFollowOrder: sheetView.props.onFollowOrder }))
      .find((item) => item.props.children === 'YL-TT' && item.props.onClick)
    link!.props.onClick!({ button: 0 })
    navigation.params = new URLSearchParams('tab=y_lenh&yl=YL-TT')
    expect(elements(render(withSheets)).find((item) => item.type === OrderLinesTable)!.props.selectedDrug).toBeNull()
  })
  it('dòng thuốc trọng tâm giữ hành động chuyển sang thẩm định', () => {
    const tree = render()
    const table = elements(tree).find((item) => item.type === OrderLinesTable)!
    table.props.onSelectDrug!('Meropenem')
    expect(navigation.params.get('tab')).toBeNull()
  })
})

describe('bàn phím của bộ chọn', () => {
  it('mũi tên chỉ đi đến mục kế, kích hoạt mục mới đóng popover', () => {
    const onSelect = vi.fn()
    const renderSelector = () => hooks.run(() => {
      const tree = OrderSelector({ orders: [other, focus], selected: other, detail, onSelect })
      const popover = elements(tree).find((item) => item.type === Popover)!
      const choices = elements(popover).find((item) => item.type === OrderChoices)!
      const list = OrderChoices(choices.props as Parameters<typeof OrderChoices>[0])
      return { popover, list }
    })
    renderSelector().popover.props.onOpenChange!(true)
    const { list } = renderSelector()
    const first = { focus: vi.fn() }
    const second = { focus: vi.fn() }
    const preventDefault = vi.fn()
    list.props.onKeyDown({ key: 'ArrowDown', target: first,
      currentTarget: { querySelectorAll: () => [first, second] }, preventDefault })
    expect(second.focus).toHaveBeenCalledOnce()
    expect(preventDefault).toHaveBeenCalledOnce()
    expect(onSelect).not.toHaveBeenCalled()
    expect(renderSelector().popover.props.open).toBe(true)
    const next = elements(list).filter((item) => item.props.role === 'option')[1]
    expect(next.type).toBe('button')
    next.props.onClick!({ button: 0 })
    expect(onSelect).toHaveBeenCalledExactlyOnceWith('YL-TT')
    expect(renderSelector().popover.props.open).toBe(false)
  })
})

describe('làm mới danh sách và ca đang mở', () => {
  function fakeBrowser() {
    vi.useFakeTimers()
    vi.stubGlobal('document', Object.assign(new EventTarget(), { hidden: false }))
    const window = new EventTarget()
    vi.stubGlobal('window', window)
    return window
  }

  const recorded: PhanHoiDaGhi = {
    phan_hoi: 'dong_y', phan_hoi_nhan: 'Đồng ý', nhom_ly_do: null, ly_do: null, thoi_diem_text: '17:00',
  }

  it('sau 60 giây giữ dữ liệu đang tải và yl; lỗi nền được thử lại khi focus', async () => {
    const browser = fakeBrowser()
    vi.setSystemTime(new Date('2026-11-18T10:00:00Z'))
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const client = new MockClient()
    const getCases = vi.spyOn(client, 'getCases')
      .mockResolvedValueOnce({ ...MOCK_CASES, lam_moi_luc: '2026-11-18T16:59:34+07:00' })
      .mockRejectedValueOnce(new Error('Mất kết nối giả lập'))
      .mockResolvedValue(MOCK_CASES)
    const fresh = { ...detail, danh_sach_y_lenh: [focus, { ...other, ly_do_ngung: 'Dữ liệu mới' }] }
    let resolveDetail: (value: ChiTietCa) => void = () => {}
    const pendingDetail = new Promise<ChiTietCa>((resolve) => { resolveDetail = resolve })
    const getCase = vi.spyOn(client, 'getCase')
      .mockResolvedValueOnce(detail)
      .mockReturnValueOnce(pendingDetail)
      .mockResolvedValue(fresh)

    navigation.params = new URLSearchParams('tab=y_lenh&yl=YL-CU')
    const renderWorkspace = () => hooks.run(() => {
      const list = useCases(client)
      const current = useCaseDetail(client, detail.ca_id)
      return { list, current, tree: current.detail && detailTree(current.detail, current.orderSelectionReady) }
    })
    renderWorkspace()
    await vi.advanceTimersByTimeAsync(0)
    const initial = renderWorkspace()
    expect(initial.list.updatedAt?.toISOString()).toBe('2026-11-18T09:59:34.000Z')
    expect(selector(initial.tree).props.selected?.y_lenh_id).toBe('YL-CU')
    await vi.advanceTimersByTimeAsync(60_000)
    expect(getCases).toHaveBeenCalledTimes(2)
    expect(getCase).toHaveBeenCalledTimes(2)
    const pending = renderWorkspace()
    expect(pending.current).toMatchObject({ detail, loading: false, error: null })
    expect(pending.list).toMatchObject({ data: initial.list.data, loading: false, error: null })
    expect(warn).toHaveBeenCalledOnce()
    resolveDetail(fresh)
    await vi.advanceTimersByTimeAsync(0)
    const refreshed = renderWorkspace()
    expect(refreshed.current.detail).toBe(fresh)
    expect(selector(refreshed.tree).props.selected?.y_lenh_id).toBe('YL-CU')
    expect(navigation.params.toString()).toBe('tab=y_lenh&yl=YL-CU')

    await vi.advanceTimersByTimeAsync(30_001)
    browser.dispatchEvent(new Event('focus'))
    await vi.advanceTimersByTimeAsync(0)
    expect(getCases).toHaveBeenCalledTimes(3)
    expect(getCase).toHaveBeenCalledTimes(3)
    expect(renderWorkspace().list.updatedAt?.getTime()).toBe(Date.now())
  })

  it('chờ chi tiết mới trước khi xác thực liên kết sâu vào ca đã lưu đệm', async () => {
    fakeBrowser()
    const client = new MockClient()
    let resolveDetail: (value: ChiTietCa) => void = () => {}
    const nextLoad = new Promise<ChiTietCa>((resolve) => { resolveDetail = resolve })
    vi.spyOn(client, 'getCase').mockResolvedValueOnce(detail).mockReturnValueOnce(nextLoad)
    const renderCase = (id: string | null) => hooks.run(() => {
      const result = useCaseDetail(client, id)
      return result.detail && detailTree(result.detail, result.orderSelectionReady)
    })
    renderCase(detail.ca_id)
    await vi.advanceTimersByTimeAsync(0)
    expect(selector(renderCase(detail.ca_id)).props.selected?.y_lenh_id).toBe('YL-TT')
    renderCase(null)

    navigation.params.set('yl', 'YL-VUA-THEM')
    renderCase(detail.ca_id)
    expect(navigation.params.get('yl')).toBe('YL-VUA-THEM')
    resolveDetail({ ...detail, danh_sach_y_lenh: [...detail.danh_sach_y_lenh, { ...other, y_lenh_id: 'YL-VUA-THEM' }] })
    await vi.advanceTimersByTimeAsync(0)
    expect(selector(renderCase(detail.ca_id)).props.selected?.y_lenh_id).toBe('YL-VUA-THEM')
    expect(navigation.params.get('yl')).toBe('YL-VUA-THEM')
  })

  it('phản hồi đã lưu trong lúc tải nền vẫn có trong danh sách và chi tiết khi GET cũ về sau', async () => {
    fakeBrowser()
    const client = new MockClient()
    let resolveList: (value: typeof MOCK_CASES) => void = () => {}
    let resolveDetail: (value: ChiTietCa) => void = () => {}
    const pendingList = new Promise<typeof MOCK_CASES>((resolve) => { resolveList = resolve })
    const pendingDetail = new Promise<ChiTietCa>((resolve) => { resolveDetail = resolve })
    vi.spyOn(client, 'getCases').mockResolvedValueOnce(MOCK_CASES).mockReturnValueOnce(pendingList)
    vi.spyOn(client, 'getCase').mockResolvedValueOnce(detail).mockReturnValueOnce(pendingDetail)
    const renderWorkspace = () => hooks.run(() => ({
      list: useCases(client), current: useCaseDetail(client, detail.ca_id),
    }))
    renderWorkspace()
    await vi.advanceTimersByTimeAsync(60_000)
    const pending = renderWorkspace()
    const id = detail.nhan_dinh.can_chu_y[0].nhan_dinh_id
    pending.current.applyFeedbackToCase(detail.ca_id, id, recorded)
    pending.list.markAllResponded(detail.ca_id, true)
    resolveList(MOCK_CASES)
    resolveDetail(detail)
    await vi.advanceTimersByTimeAsync(0)
    const refreshed = renderWorkspace()
    expect(refreshed.list.data?.cases.find((row) => row.ca_id === detail.ca_id)?.da_phan_hoi_het).toBe(true)
    expect(refreshed.current.detail?.nhan_dinh.can_chu_y[0].phan_hoi).toBe(recorded)
  })

  it('giữ ghi chú đang soạn khi dữ liệu mới có phản hồi cho cùng nhận định', () => {
    let draft = EMPTY_FEEDBACK_DRAFT
    const renderFeedback = (recorded: PhanHoiDaGhi | null) => hooks.run(() => FeedbackBar({
      caId: detail.ca_id, finding: { ...detail.nhan_dinh.can_chu_y[0], phan_hoi: recorded },
      nhomLyDo: [], submitting: false, error: null,
      draft, onDraftChange: (next) => { draft = next },
      onSubmit: async () => true, onClearError() {},
    }))
    elements(renderFeedback(null)).find((item) => item.props.children === 'Cần sửa')!.props.onClick!({ button: 0 })
    const draftInput = elements(renderFeedback(null)).find((item) => item.type === 'input')!
    draftInput.props.onChange!({ target: { value: 'Ghi chú đang soạn' } })
    const refreshed = renderFeedback(recorded)
    expect(elements(refreshed).find((item) => item.type === 'input')?.props.value).toBe('Ghi chú đang soạn')
  })

  it('giữ bản nháp khi nhận định rời danh sách cần chú ý', () => {
    navigation.params = new URLSearchParams()
    const findingCard = (tree: ReactNode) => elements(tree).find((item) => item.type === FindingCard)
    const draft: FeedbackDraft = { ...EMPTY_FEEDBACK_DRAFT, pendingAction: 'can_sua', note: 'Bản nháp giả lập' }
    findingCard(render())!.props.onFeedbackDraftChange!(draft)
    const refreshed = render({ ...detail, nhan_dinh: { ...detail.nhan_dinh, can_chu_y: [] } })
    expect(findingCard(refreshed)).toBeUndefined()
    expect(elements(refreshed).some((item) => item.props.children === draft.note)).toBe(true)
    expect(findingCard(render())?.props.feedbackDraft).toEqual(draft)
  })
})
