import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { MOCK_CASE_DETAILS } from '../api/mockData'
import type { ChiTietCa } from '../api/types'
import { TooltipProvider } from '../components/ui/tooltip'
import { FindingCard } from '../features/findings/FindingCard'
import { OrderDetailView } from '../features/order-detail/OrderDetailView'
import { useReviewFindings } from '../features/order-detail/useReviewFindings'
import { ReviewFactorNav } from '../features/sidebar/ReviewFactorNav'
import { SidebarNav } from '../features/sidebar/SidebarNav'
import type { SidebarReviewNav } from '../features/sidebar/SidebarNav'
import {
  SIX_FACTOR_DEFINITIONS,
  computeSixFactorsStatus,
  countAttentionByFactor,
  hasSevereByFactor,
} from '../lib/orderDetail'
import type { ReviewSectionId } from '../lib/orderDetail'
import { EMPTY_FEEDBACK_DRAFT } from '../lib/uiTypes'

function buildNavProps(
  detail: ChiTietCa,
  selected: ReviewSectionId = 'tong_quan',
): SidebarReviewNav {
  const factors = computeSixFactorsStatus(detail.nhan_dinh)
  const attentionCountByFactor = countAttentionByFactor(detail.nhan_dinh.can_chu_y)
  const severeByFactor = hasSevereByFactor(detail.nhan_dinh.can_chu_y)
  const totalAttention = detail.nhan_dinh.can_chu_y.length
  const hasAnySevere = detail.nhan_dinh.can_chu_y.some(
    (item) => item.muc_do_ma === 'nghiem_trong',
  )
  return {
    selected,
    factors,
    attentionCountByFactor,
    severeByFactor,
    totalAttention,
    hasAnySevere,
    soLuatDaChay: detail.nhan_dinh.so_luat_da_chay,
    onSelect: vi.fn(),
  }
}

function renderOrderView(detail: ChiTietCa, entry: string): string {
  return renderToStaticMarkup(
    <TooltipProvider>
      <MemoryRouter initialEntries={[entry]}>
        <OrderDetailView
          detail={detail}
          aiTrangThai="tat"
          aiKetQua={null}
          aiThoiGianMs={null}
          aiCanhBao={[]}
          sessionFeedbackForCase={{}}
          onRerunAi={vi.fn()}
          isFeedbackSubmitting={() => false}
          getFeedbackError={() => null}
          onSubmitFeedback={async () => true}
          onClearFeedbackError={vi.fn()}
          onOpenEvidence={vi.fn()}
          onAskAboutFinding={vi.fn()}
        />
      </MemoryRouter>
    </TooltipProvider>,
  )
}

describe('ReviewFactorNav 8 mục ở thanh bên', () => {
  it('hiển thị đủ 8 mục đúng thứ tự, aria-current="page", số đếm đúng, mục chua_co_luat không chứa "Đạt", có dòng luật đã chạy', () => {
    const detail = MOCK_CASE_DETAILS['DEMO-02']
    const navProps = buildNavProps(detail, 6)
    const html = renderToStaticMarkup(<ReviewFactorNav {...navProps} />)

    expect(html).toContain('<nav aria-label="Mục thẩm định"')

    const buttons = html.match(/<button\b[\s\S]*?<\/button>/g) ?? []
    expect(buttons).toHaveLength(8)

    const expectedTitles = ['Tổng quan', ...SIX_FACTOR_DEFINITIONS.map((d) => d.title)]
    let cursor = -1
    for (const title of expectedTitles) {
      const idx = html.indexOf(title)
      expect(idx).toBeGreaterThan(cursor)
      cursor = idx
    }

    // Chỉ đúng 1 mục đang chọn có aria-current="page"
    const currentMatches = html.match(/aria-current="page"/g) ?? []
    expect(currentMatches).toHaveLength(1)
    expect(buttons[6]).toContain('aria-current="page"')
    expect(buttons[6]).toContain('bg-ink-soft')

    // Tổng quan và yếu tố 6 có 1 nhận định nghiêm trọng → hiện số 1 và tô nhấn danger
    expect(buttons[0]).toContain('>1<')
    expect(buttons[0]).toContain('danger-')
    expect(buttons[6]).toContain('>1<')
    expect(buttons[6]).toContain('danger-')

    // Yếu tố không có nhận định cần chú ý ẩn số đếm; yếu tố chua_co_luat (3, 4, 5) không chứa chữ "Đạt"
    for (const idx of [3, 4, 5]) {
      expect(buttons[idx]).toContain('Chưa có luật')
      expect(buttons[idx]).not.toContain('Đạt')
      expect(buttons[idx]).not.toContain('đạt')
      expect(buttons[idx]).not.toContain('>0<')
    }

    expect(html).toContain('4 luật đã chạy')
  })

  it('mục chỉ có mức Cần lưu ý (không Nghiêm trọng) dùng màu warning thay vì tô nhấn danger', () => {
    const detail = MOCK_CASE_DETAILS['DEMO-05']
    const navProps = buildNavProps(detail, 'tong_quan')
    const html = renderToStaticMarkup(<ReviewFactorNav {...navProps} />)
    const buttons = html.match(/<button\b[\s\S]*?<\/button>/g) ?? []

    expect(buttons).toHaveLength(8)
    expect(buttons[0]).toContain('>1<')
    expect(buttons[7]).toContain('>1<')
    expect(buttons[0]).not.toContain('danger-')
    expect(buttons[7]).not.toContain('danger-')
    expect(buttons[7]).toContain('warning-')
    expect(html).toContain('3 luật đã chạy')
  })

  it('chế độ thu gọn (56 px) dựng cột 8 nút biểu tượng kèm aria-label và giữ trạng thái chọn', () => {
    const detail = MOCK_CASE_DETAILS['DEMO-02']
    const navProps = buildNavProps(detail, 'tong_quan')
    const html = renderToStaticMarkup(
      <TooltipProvider>
        <ReviewFactorNav {...navProps} collapsed />
      </TooltipProvider>,
    )

    expect(html).toContain('<nav aria-label="Mục thẩm định"')
    const buttons = html.match(/<button\b[\s\S]*?<\/button>/g) ?? []
    expect(buttons).toHaveLength(8)
    expect(buttons[0]).toContain('aria-current="page"')
    expect(buttons[3]).not.toContain('Đạt')
  })
})

describe('SidebarNav chuyển đổi giữa reviewNav và thẻ người bệnh', () => {
  it('có reviewNav → không còn "Thông tin người bệnh", có "Mục thẩm định"; không có reviewNav → thẻ người bệnh như cũ', () => {
    const detail = MOCK_CASE_DETAILS['DEMO-02']
    const reviewNav = buildNavProps(detail, 'tong_quan')

    const withReviewHtml = renderToStaticMarkup(
      <TooltipProvider>
        <MemoryRouter>
          <SidebarNav
            collapsed={false}
            activeSection="orders"
            onNavigate={vi.fn()}
            userEmail={null}
            isDemoMode
            onToggleCollapse={vi.fn()}
            onOpenSettings={vi.fn()}
            onSignIn={vi.fn()}
            onSignOut={vi.fn()}
            patient={detail}
            reviewNav={reviewNav}
          />
        </MemoryRouter>
      </TooltipProvider>,
    )
    expect(withReviewHtml).not.toContain('Thông tin người bệnh')
    expect(withReviewHtml).toContain('aria-label="Mục thẩm định"')
    expect(withReviewHtml).toContain('Cơ địa và xét nghiệm')
    expect(withReviewHtml).toContain('4 luật đã chạy')

    const withReviewCollapsedHtml = renderToStaticMarkup(
      <TooltipProvider>
        <MemoryRouter>
          <SidebarNav
            collapsed
            activeSection="orders"
            onNavigate={vi.fn()}
            userEmail={null}
            isDemoMode
            onToggleCollapse={vi.fn()}
            onOpenSettings={vi.fn()}
            onSignIn={vi.fn()}
            onSignOut={vi.fn()}
            patient={detail}
            reviewNav={reviewNav}
          />
        </MemoryRouter>
      </TooltipProvider>,
    )
    expect(withReviewCollapsedHtml).not.toContain('Thông tin người bệnh')
    expect(withReviewCollapsedHtml).toContain('aria-label="Mục thẩm định"')

    const withReviewDrawerHtml = renderToStaticMarkup(
      <TooltipProvider>
        <MemoryRouter>
          <SidebarNav
            collapsed
            inDrawer
            activeSection="orders"
            onNavigate={vi.fn()}
            userEmail={null}
            isDemoMode
            onToggleCollapse={vi.fn()}
            onOpenSettings={vi.fn()}
            onSignIn={vi.fn()}
            onSignOut={vi.fn()}
            patient={detail}
            reviewNav={reviewNav}
          />
        </MemoryRouter>
      </TooltipProvider>,
    )
    expect(withReviewDrawerHtml).toContain('4 luật đã chạy')
    expect(withReviewDrawerHtml).toContain('Cơ địa và xét nghiệm')

    const withoutReviewHtml = renderToStaticMarkup(
      <TooltipProvider>
        <MemoryRouter>
          <SidebarNav
            collapsed={false}
            activeSection="orders"
            onNavigate={vi.fn()}
            userEmail={null}
            isDemoMode
            onToggleCollapse={vi.fn()}
            onOpenSettings={vi.fn()}
            onSignIn={vi.fn()}
            onSignOut={vi.fn()}
            patient={detail}
          />
        </MemoryRouter>
      </TooltipProvider>,
    )
    expect(withoutReviewHtml).toContain('Thông tin người bệnh')
    expect(withoutReviewHtml).not.toContain('aria-label="Mục thẩm định"')
  })
})

describe('useReviewFindings và OrderDetailView theo ?yt=', () => {
  it('useReviewFindings tính nhất quán số lượng, mức nghiêm trọng và 7 yếu tố', () => {
    const detail = MOCK_CASE_DETAILS['DEMO-02']
    function Probe() {
      const result = useReviewFindings({
        detail,
        aiTrangThai: 'tat',
        aiKetQua: null,
        sessionFeedbackForCase: {},
      })
      return (
        <div>
          {JSON.stringify({
            total: result.totalAttention,
            hasAnySevere: result.hasAnySevere,
            count6: result.attentionCountByFactor[6],
            severe6: result.severeByFactor[6],
            status6: result.sixFactors[5]?.status,
          })}
        </div>
      )
    }
    const html = renderToStaticMarkup(<Probe />)
    expect(html).toContain('&quot;total&quot;:1')
    expect(html).toContain('&quot;hasAnySevere&quot;:true')
    expect(html).toContain('&quot;count6&quot;:1')
    expect(html).toContain('&quot;severe6&quot;:true')
    expect(html).toContain('&quot;status6&quot;:&quot;co_van_de&quot;')
  })

  it('OrderDetailView với ?yt=6 chỉ hiện yếu tố 6, bỏ SixFactorStrip và không hiện Mở mục', () => {
    const detail = MOCK_CASE_DETAILS['DEMO-02']
    const html = renderOrderView(detail, '?yt=6')

    expect(html).toContain('6. Cơ địa và xét nghiệm')
    expect(html).toContain('Meropenem 1 g')
    expect(html).not.toContain('Bảy yếu tố thẩm định')
    expect(html).not.toContain('Mở mục 6')
    expect(html).not.toContain('Yếu tố 4 · Tương tác thuốc')
    expect(html).not.toContain('không có tiền sử dị ứng')
  })

  it('OrderDetailView với ?yt=4 hiện phần tương tác và không chứa "Đạt"; ?yt=3 không chứa "Đạt"', () => {
    const detail = MOCK_CASE_DETAILS['DEMO-02']
    const yt4Html = renderOrderView(detail, '?yt=4')
    expect(yt4Html).toContain('4. Tương tác thuốc')
    expect(yt4Html).toContain('Chưa có luật cho yếu tố này')
    expect(yt4Html).toContain('Yếu tố 4 · Tương tác thuốc')
    expect(yt4Html).not.toContain('Đạt')

    const yt3Html = renderOrderView(detail, '?yt=3')
    expect(yt3Html).toContain('3. Chỉ định, liều, đường dùng')
    expect(yt3Html).toContain('Chưa có luật cho yếu tố này')
    expect(yt3Html).not.toContain('Đạt')
    expect(yt3Html).not.toContain('Các mục đạt')
  })

  it('OrderDetailView với ?yt=1 mở sẵn PassedList khi yếu tố không có mục cần chú ý', () => {
    const detail = MOCK_CASE_DETAILS['DEMO-02']
    const html = renderOrderView(detail, '?yt=1')

    expect(html).toContain('1. Dị ứng, quá mẫn')
    expect(html).toContain('Không có mục cần chú ý ở yếu tố 1 (Dị ứng, quá mẫn)')
    expect(html).toContain('Các mục đạt (1)')
    expect(html).toContain('aria-expanded="true"')
    expect(html).toContain('Người bệnh đã được khai thác: không có tiền sử dị ứng')
    expect(html).not.toContain('Không có hoạt chất trùng lặp')
  })

  it('OrderDetailView với ?yt=abc hoặc ?yt=tong_quan quay về Tổng quan có nút Mở mục N và không có SixFactorStrip', () => {
    const detail = MOCK_CASE_DETAILS['DEMO-02']
    for (const query of ['?yt=abc', '?yt=tong_quan']) {
      const html = renderOrderView(detail, query)
      expect(html).toContain('Nhận định')
      expect(html).toContain('1 mục cần chú ý')
      expect(html).toContain('Mở mục 6')
      expect(html).toContain('Các mục đạt (3)')
      expect(html).not.toContain('Bảy yếu tố thẩm định')
      expect(html).not.toContain('Yếu tố 4 · Tương tác thuốc')
    }
  })

  it('FindingCard chỉ hiện nút "Mở mục N" khi có prop onOpenFactor', () => {
    const detail = MOCK_CASE_DETAILS['DEMO-02']
    const finding = detail.nhan_dinh.can_chu_y[0]
    const baseProps = {
      caId: detail.ca_id,
      finding,
      chiSo: detail.chi_so,
      nhomLyDo: detail.nhom_ly_do,
      submitting: false,
      feedbackError: null,
      feedbackDraft: EMPTY_FEEDBACK_DRAFT,
      onFeedbackDraftChange: vi.fn(),
      onSubmitFeedback: async () => true,
      onClearFeedbackError: vi.fn(),
      onOpenEvidence: vi.fn(),
      onAskAboutFinding: vi.fn(),
    }

    const withoutProp = renderToStaticMarkup(<FindingCard {...baseProps} />)
    expect(withoutProp).not.toContain('Mở mục')

    const withProp = renderToStaticMarkup(<FindingCard {...baseProps} onOpenFactor={vi.fn()} />)
    expect(withProp).toContain('Mở mục 6')
  })
})
