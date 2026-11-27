import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { MOCK_CASES, MOCK_CASE_DETAILS } from '../api/mockData'
import { TooltipProvider } from '../components/ui/tooltip'
import { OrdersTable } from '../features/orders/OrdersTable'
import { LabsTabContent } from '../features/order-detail/LabsTabContent'
import { UnifiedOrderLinesTable } from '../features/order-detail/UnifiedOrderLinesTable'
import { flattenOrderLines, partitionFindingsByLine } from '../lib/unifiedOrderLines'

function expectMatchingColumns(html: string, modeClasses: string[]) {
  const header = html.match(/<thead\b[^>]*>[\s\S]*?<\/thead>/)?.[0] ?? ''
  const row = html.match(/<tbody\b[^>]*>\s*<tr\b[^>]*>[\s\S]*?<\/tr>/)?.[0] ?? ''
  const heads = [...header.matchAll(/<th\b[^>]*>/g)].map((match) => match[0])
  const cells = [...row.matchAll(/<td\b[^>]*>/g)].map((match) => match[0])
  expect(heads.length).toBeGreaterThan(0)
  expect(heads).toHaveLength(cells.length)
  for (const modeClass of modeClasses) {
    const hasClass = (tag: string) => new RegExp(`\\b${modeClass}\\b`).test(tag)
    expect(heads.filter(hasClass)).toHaveLength(cells.filter(hasClass).length)
    expect(heads.map(hasClass)).toEqual(cells.map(hasClass))
  }
}

describe('bố cục co giãn', () => {
  it('giữ thông tin dòng thuốc trong cả hai chế độ', () => {
    const lines = flattenOrderLines(MOCK_CASE_DETAILS['DEMO-02'])
    const line = lines[0]
    const html = renderToStaticMarkup(<TooltipProvider><UnifiedOrderLinesTable caId="DEMO-02" lines={lines} partitioned={partitionFindingsByLine(lines, [], [])} expandedLineKey={line.key} onToggleLine={vi.fn()} chiSo={[]} nhomLyDo={[]} feedbackDrafts={{}} onFeedbackDraftChange={vi.fn()} isFeedbackSubmitting={() => false} getFeedbackError={() => null} onSubmitFeedback={async () => true} onClearFeedbackError={vi.fn()} onOpenEvidence={vi.fn()} onAskAboutFinding={vi.fn()} /></TooltipProvider>)
    expect(html).toContain('ui3-lines-wide')
    expect(html).toContain('ui3-lines-compact')
    expect(html).toContain([line.lieu, line.tanSuat, line.duongDung].join(' · '))
    expect(html).toContain(line.ngayKe)
    expect(html).toContain('ui3-expanded')
    for (const [mode, span] of [['wide', 9], ['medium', 4], ['narrow', 3]] as const) {
      expect(html).toMatch(new RegExp(`<td colSpan="${span}" class="ui3-detail-${mode}\\b`))
    }
    expectMatchingColumns(html, ['ui3-lines-wide', 'ui3-schedule'])
    expect(html).not.toMatch(/<td[^>]*\btruncate\b/)
  })
  it('giữ đơn vị và khoảng tham chiếu dưới kết quả', () => {
    const html = renderToStaticMarkup(<LabsTabContent labs={[{ ten: 'Mẫu', gia_tri_text: '2,4', don_vi: 'mmol/L', khoang_tham_chieu: '1–3', thoi_diem_text: '10/11/2026 08:00', ngoai_nguong: false, huong: null }]} />)
    expect(html).toContain('ui3-labs-wide')
    expect(html).toMatch(/ui3-labs-compact[^>]*>mmol\/L/)
    expect(html).toMatch(/ui3-labs-compact[^>]*>1–3/)
    expectMatchingColumns(html, ['ui3-labs-wide'])
    expect(html).not.toMatch(/<td[^>]*\btruncate\b/)
  })
  it('giữ mã, ngày sinh và khoa ở dòng phụ', () => {
    const row = { ...MOCK_CASES.cases[0], ngay_sinh: '1980-05-10', khoa: 'Khoa mẫu' }
    const html = renderToStaticMarkup(<TooltipProvider><OrdersTable filterTitle="Hồ sơ cần duyệt" orders={[row]} totalCount={1} loiNap={[]} loading={false} error={null} searchQuery="" sortField="ket_qua" sortDirection="desc" columnFilters={{}} onColumnFiltersChange={vi.fn()} onToggleSort={vi.fn()} onOpenOrder={vi.fn()} onResetFilters={vi.fn()} onRetry={vi.fn()} onRefresh={vi.fn()} /></TooltipProvider>)
    expect(html).toContain('ui3-orders-wide')
    expect(html).toMatch(new RegExp(`ui3-orders-compact[^>]*>[\\s\\S]*?<button[^>]*>NB-${row.ca_id}</button> · (?:<!-- -->)?10/05/1980`))
    expect(html).toMatch(/ui3-orders-compact[^>]*>Khoa mẫu/)
    expectMatchingColumns(html, ['ui3-orders-wide'])
    expect(html).not.toMatch(/<td[^>]*\btruncate\b/)
  })
  it('không có dấu hỏi thay chữ hoặc ký hiệu trong chuỗi hiển thị UI3', () => {
    const files = ['features/orders/OrdersTable.tsx', 'features/order-detail/UnifiedOrderLinesTable.tsx', 'features/order-detail/OrderLineExpandedPanel.tsx', 'features/order-detail/LabsTabContent.tsx', 'features/order-detail/DetailSections.tsx', 'features/findings/PassedList.tsx']
    for (const file of files) {
      const source = readFileSync(new URL(`../${file}`, import.meta.url), 'utf8')
      const strings = source.match(/'(?:\\.|[^'\\\r\n])*'|"(?:\\.|[^"\\\r\n])*"|`(?:\\.|[^`\\])*`/g) ?? []
      for (const value of strings) {
        expect(value.slice(1, -1), file).not.toMatch(/^\?$| \? |[A-Za-z]\?[a-z]/)
      }
    }
  })
})
