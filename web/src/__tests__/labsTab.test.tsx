import { Children, isValidElement } from 'react'
import type { ReactElement, ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ChiTietXetNghiemDong } from '../api/types'
import { DataTableRow } from '../components/ui/data-table'
import { LabsTabContent } from '../features/order-detail/LabsTabContent'
import { buildSingleLabTrendChart } from '../lib/labChart'

const hooks = vi.hoisted(() => {
  type Slot = { value?: unknown; deps?: unknown[] }
  let slots: Slot[] = []
  let cursor = 0
  const slot = () => slots[cursor++] ?? (slots[cursor - 1] = {})
  return {
    useState(initial: unknown) {
      const cell = slot()
      if (!('value' in cell)) cell.value = typeof initial === 'function' ? initial() : initial
      return [
        cell.value,
        (next: unknown) => {
          cell.value = typeof next === 'function' ? next(cell.value) : next
        },
      ]
    },
    useRef(initial: unknown) {
      const cell = slot()
      return cell.value ?? (cell.value = { current: initial })
    },
    useMemo(fn: () => unknown) {
      return fn()
    },
    useEffect() {},
    reset() {
      slots = []
      cursor = 0
    },
    nextRender() {
      cursor = 0
    },
  }
})

vi.mock('react', async (original) => ({
  ...(await original<typeof import('react')>()),
  ...hooks,
}))

const SAMPLE_LABS: ChiTietXetNghiemDong[] = [
  {
    thoi_diem_text: '09/11/2026 08:00',
    ten: 'Creatinin máu',
    gia_tri_text: '165',
    don_vi: 'umol/L',
    khoang_tham_chieu: '44 – 80',
    ngoai_nguong: true,
    huong: '▲',
  },
  {
    thoi_diem_text: '10/11/2026 08:00',
    ten: 'Creatinin máu',
    gia_tri_text: '212',
    don_vi: 'umol/L',
    khoang_tham_chieu: '44 – 80',
    ngoai_nguong: true,
    huong: '▲',
  },
  {
    thoi_diem_text: '10/11/2026 08:00',
    ten: 'INR',
    gia_tri_text: '2,4',
    don_vi: '',
    khoang_tham_chieu: '2,0 – 3,0',
    ngoai_nguong: false,
    huong: null,
  },
]

describe('LabsTabContent (bảng phẳng 7 cột + đồ thị on-click in đậm)', () => {
  beforeEach(() => hooks.reset())
  afterEach(() => hooks.reset())

  it('hiển thị đúng 7 cột (Đơn vị → Kết quả → Khoảng tham chiếu) và mặc định không có đồ thị', () => {
    const html = renderToStaticMarkup(<LabsTabContent labs={SAMPLE_LABS} />)

    const headers = [
      '>STT<',
      '>Chỉ số xét nghiệm<',
      '>Đơn vị<',
      '>Kết quả<',
      '>Khoảng tham chiếu<',
      '>Thời gian đo<',
      '>Đánh giá<',
    ]
    let pos = -1
    for (const h of headers) {
      const idx = html.indexOf(h)
      expect(idx).toBeGreaterThan(pos)
      pos = idx
    }

    expect(html).not.toContain('Diễn biến Creatinin máu của bệnh nhân')
    expect(html).not.toContain('data-selected="true"')
  })

  it('click hàng xét nghiệm mở đồ thị diễn biến và in đậm hàng + điểm đang chọn; click lại thì đóng', () => {
    function collectElements(node: ReactNode): ReactElement<{ children?: ReactNode; onClick?: () => void }>[] {
      if (!isValidElement(node)) return []
      const el = node as ReactElement<{ children?: ReactNode; onClick?: () => void }>
      return [el, ...Children.toArray(el.props.children).flatMap(collectElements)]
    }

    hooks.nextRender()
    const tree = LabsTabContent({ labs: SAMPLE_LABS })
    const rows = collectElements(tree).filter((el) => el.type === DataTableRow)
    expect(rows).toHaveLength(3)

    rows[0].props.onClick?.()
    hooks.nextRender()
    const htmlAfterClick = renderToStaticMarkup(<LabsTabContent labs={SAMPLE_LABS} />)
    expect(htmlAfterClick).toContain('aria-selected="true"')
    expect(htmlAfterClick).toContain('font-bold')
    expect(htmlAfterClick).toContain('Diễn biến Creatinin máu của bệnh nhân')
    expect(htmlAfterClick).toContain('data-selected="true"')

    hooks.nextRender()
    const tree2 = LabsTabContent({ labs: SAMPLE_LABS })
    const rows2 = collectElements(tree2).filter((el) => el.type === DataTableRow)
    rows2[0].props.onClick?.()
    hooks.nextRender()
    const htmlAfterSecondClick = renderToStaticMarkup(<LabsTabContent labs={SAMPLE_LABS} />)
    expect(htmlAfterSecondClick).not.toContain('Diễn biến Creatinin máu của bệnh nhân')
  })

  it('buildSingleLabTrendChart hỗ trợ 1 điểm đo và gắn isSelected đúng điểm đang chọn', () => {
    const single = buildSingleLabTrendChart(SAMPLE_LABS, 'INR', null, undefined, {
      thoiDiemText: '10/11/2026 08:00',
      giaTriText: '2,4',
    })
    expect(single).not.toBeNull()
    expect(single!.points).toHaveLength(1)
    expect(single!.points[0].isSelected).toBe(true)

    const multi = buildSingleLabTrendChart(SAMPLE_LABS, 'Creatinin máu', null, undefined, {
      thoiDiemText: '09/11/2026 08:00',
      giaTriText: '165',
    })
    expect(multi!.points.map((p) => p.isSelected)).toEqual([true, false])
  })
})
