import { Children, isValidElement } from 'react'
import type { ReactElement, ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MOCK_CASE_DETAILS } from '../api/mockData'
import type { ChiTietCa, MedicalOrder } from '../api/types'
import { OrderDetailView } from '../features/order-detail/OrderDetailView'
import { OrderSelector } from '../features/order-detail/MedicalRecordSections'
import { OrderLinesTable } from '../features/order-detail/DetailSections'

// Bộ chạy hook cục bộ theo mẫu test vòng đời có sẵn; không cần DOM hay thư viện mới.
const hooks = vi.hoisted(() => {
  type Slot = { value?: unknown; deps?: unknown[] }
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
    useEffect(fn: () => void, deps: unknown[]) {
      const cell = slot()
      if (!cell.deps || deps.some((value, index) => !Object.is(value, cell.deps![index]))) {
        cell.deps = deps
        effects.push(fn)
      }
    },
    run<T,>(fn: () => T): T {
      cursor = 0
      const result = fn()
      for (const effect of effects.splice(0)) effect()
      return result
    },
    reset() { slots = []; effects = []; cursor = 0 },
  }
})
const navigation = vi.hoisted(() => ({
  params: new URLSearchParams(),
  set(next: URLSearchParams | ((previous: URLSearchParams) => URLSearchParams)) {
    navigation.params = typeof next === 'function' ? next(navigation.params) : next
  },
}))
vi.mock('react', async (original) => ({ ...await original<typeof import('react')>(), ...hooks }))
vi.mock('react-router-dom', async (original) => ({
  ...await original<typeof import('react-router-dom')>(),
  useSearchParams: () => [navigation.params, navigation.set],
}))

type Element = ReactElement<{ children?: ReactNode; selected?: MedicalOrder; onSelect?: (id: string) => void; onSelectDrug?: (name: string) => void }>
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
function render(value: ChiTietCa = detail) {
  return hooks.run(() => OrderDetailView({ detail: value, aiTrangThai: 'tat', aiKetQua: null,
    aiThoiGianMs: null, aiCanhBao: [], sessionFeedbackForCase: {}, onRerunAi() {},
    isFeedbackSubmitting: () => false, getFeedbackError: () => null, onSubmitFeedback: async () => true,
    onClearFeedbackError() {}, onOpenEvidence() {}, onAskAboutFinding() {},
  }))
}
function selector(tree: ReactNode) { return elements(tree).find((item) => item.type === OrderSelector)! }

beforeEach(() => {
  hooks.reset()
  navigation.params = new URLSearchParams('tab=y_lenh')
  vi.stubGlobal('requestAnimationFrame', (fn: () => void) => fn())
})

describe('vòng đời lựa chọn y lệnh', () => {
  it('gọi bộ chọn đổi URL và nội dung, tải lại giữ mã đã chọn', () => {
    const initial = render()
    expect(selector(initial).props.selected?.y_lenh_id).toBe('YL-TT')
    selector(initial).props.onSelect!('YL-CU')
    expect(navigation.params.toString()).toBe('tab=y_lenh&yl=YL-CU')
    expect(selector(render()).props.selected?.y_lenh_id).toBe('YL-CU')
    hooks.reset()
    expect(selector(render()).props.selected?.y_lenh_id).toBe('YL-CU')
  })
  it('đổi ca xoá lựa chọn cũ kể cả khi mã đó vẫn có trong danh sách mới', () => {
    navigation.params.set('yl', 'YL-CU')
    render()
    const next = { ...detail, ca_id: 'CA-MOI', danh_sach_y_lenh: [other, { ...focus, y_lenh_id: 'YL-MOI' }] }
    expect(selector(render(next)).props.selected?.y_lenh_id).toBe('YL-MOI')
    expect(navigation.params.get('yl')).toBeNull()
    expect(selector(render(next)).props.selected?.y_lenh_id).toBe('YL-MOI')
  })
  it('dòng thuốc trọng tâm giữ hành động chuyển sang thẩm định', () => {
    const tree = render()
    const table = elements(tree).find((item) => item.type === OrderLinesTable)!
    table.props.onSelectDrug!('Meropenem')
    expect(navigation.params.get('tab')).toBeNull()
  })
})
