import { Children, isValidElement } from 'react'
import type { ReactElement, ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MOCK_CASES } from '../api/mockData'
import { WorkspacePage } from '../app/WorkspacePage'
import type { AppShellProps } from '../app/AppShell'
import { TooltipProvider } from '../components/ui/tooltip'
import { MedicalRecordsList } from '../features/medical-records/MedicalRecordsList'
import type { MedicalRecordsListProps } from '../features/medical-records/MedicalRecordsList'
import { SidebarNav } from '../features/sidebar/SidebarNav'
import type { SidebarNavProps } from '../features/sidebar/SidebarNav'

const captured = vi.hoisted(() => ({
  shell: null as AppShellProps | null,
  navigate: vi.fn(),
  retry: vi.fn(),
}))

vi.mock('react-router-dom', async (original) => ({
  ...await original<typeof import('react-router-dom')>(),
  useNavigate: () => captured.navigate,
}))
vi.mock('../features/auth/useAuth', () => ({
  useAuth: () => ({ userEmail: null, isDemoMode: true, vaiTro: null, signOut: vi.fn() }),
}))
vi.mock('../state/useCases', async () => ({
  useCases: () => ({
    data: MOCK_CASES, loading: false, error: null, reload: captured.retry, markAllResponded: vi.fn(),
  }),
}))
vi.mock('../app/AppShell', () => ({
  AppShell: (props: AppShellProps) => {
    captured.shell = props
    return <>{props.sidebarSlot}{props.children}</>
  },
}))
vi.mock('../features/settings/SettingsDialog', () => ({ SettingsDialog: () => null }))
vi.mock('../features/findings/EvidenceDialog', () => ({ EvidenceDialog: () => null }))

type TreeProps = {
  children?: ReactNode
  onClick?: (event: { stopPropagation: () => void }) => void
  'aria-label'?: string
  to?: string
}

function elements(node: ReactNode): ReactElement<TreeProps>[] {
  return Children.toArray(node).flatMap((child) => isValidElement<TreeProps>(child)
    ? [child, ...elements(child.props.children)] : [])
}

function renderRoute(path: string, state?: object): string {
  return renderToStaticMarkup(
    <TooltipProvider>
      <MemoryRouter initialEntries={[{ pathname: path.split('?')[0], search: path.split('?')[1], state }]}>
        <Routes>
          <Route path="/app" element={<WorkspacePage />} />
          <Route path="/app/ho-so" element={<WorkspacePage />} />
          <Route path="/app/y-lenh/:caId" element={<WorkspacePage />} />
        </Routes>
      </MemoryRouter>
    </TooltipProvider>,
  )
}

function listProps(overrides: Partial<MedicalRecordsListProps> = {}): MedicalRecordsListProps {
  return {
    cases: MOCK_CASES.cases, loading: false, error: null, searchQuery: '',
    onRetry: captured.retry, onOpenRecord: vi.fn(), ...overrides,
  }
}

beforeEach(() => { captured.shell = null; vi.clearAllMocks() })

describe('điều hướng hồ sơ trong bàn làm việc', () => {
  it.each([
    ['/app', 'Y lệnh'],
    ['/app/y-lenh/DEMO-02', 'Y lệnh'],
    ['/app/y-lenh/DEMO-02?tab=ho_so_benh_an', 'Y lệnh'],
    ['/app/ho-so', 'Hồ sơ bệnh án'],
    ['/app/ho-so/', 'Hồ sơ bệnh án'],
  ])('route %s chọn đúng mục %s', (path, selected) => {
    const html = renderRoute(path)
    const links = [...html.matchAll(/<a\b[^>]*>/g)].map((match) => match[0])
    for (const label of ['Y lệnh', 'Hồ sơ bệnh án']) {
      const link = links.find((tag) => tag.includes(`aria-label="${label}"`))
      expect(link).toBeDefined()
      expect(link?.includes('aria-current="page"')).toBe(label === selected)
    }
  })

  it('mục Hồ sơ bệnh án có đích /app/ho-so và gọi đóng drawer khi chọn', () => {
    const html = renderRoute('/app')
    expect(html).toMatch(/<a[^>]*aria-label="Hồ sơ bệnh án"[^>]*href="\/app\/ho-so"/)
    const props = (captured.shell!.sidebarDrawerSlot as ReactElement<SidebarNavProps>).props
    const closeDrawer = vi.fn()
    // Dựng SidebarNav trong React để giữ nguyên hook và lấy callback của liên kết.
    let tree: ReactNode
    function Probe() {
      tree = SidebarNav({ ...props, onNavigate: closeDrawer })
      return tree
    }
    renderToStaticMarkup(<TooltipProvider><MemoryRouter><Probe /></MemoryRouter></TooltipProvider>)
    const link = elements(tree).find((item) => item.props.to === '/app/ho-so')
    link!.props.onClick!({ stopPropagation() {} })
    expect(closeDrawer).toHaveBeenCalledOnce()
  })

  it.each([
    { collapsed: true, inDrawer: false },
    { collapsed: true, inDrawer: true },
  ])('giữ hai mục khi collapsed=$collapsed, inDrawer=$inDrawer', (options) => {
    renderRoute('/app/ho-so')
    const props = (captured.shell!.sidebarSlot as ReactElement<SidebarNavProps>).props
    const html = renderToStaticMarkup(
      <TooltipProvider><MemoryRouter><SidebarNav {...props} {...options} /></MemoryRouter></TooltipProvider>,
    )
    expect(html).toContain('aria-label="Y lệnh"')
    expect(html).toContain('aria-label="Hồ sơ bệnh án" aria-current="page"')
    expect(html.includes('>Hồ sơ bệnh án</span>')).toBe(options.inDrawer)
    if (!options.inDrawer) expect(html).toContain('data-state="closed"')
  })

  it('bấm dòng và nút bàn phím mở đúng tab hồ sơ, mã ca được mã hoá', () => {
    renderRoute('/app/ho-so')
    const props = (captured.shell!.children as ReactElement<MedicalRecordsListProps>).props
    const caId = 'CA GIA/LAP'
    const tree = MedicalRecordsList({ ...props, cases: [{ ...MOCK_CASES.cases[0], ca_id: caId }] })
    const row = elements(tree).find((item) => item.type === 'tr' && item.props.onClick)
    row!.props.onClick!({ stopPropagation() {} })
    expect(captured.navigate).toHaveBeenCalledExactlyOnceWith('/app/y-lenh/CA%20GIA%2FLAP?tab=ho_so_benh_an', { state: { fromRecords: true } })
    captured.navigate.mockClear()
    const stopPropagation = vi.fn()
    const button = elements(tree).find((item) => item.type === 'button')
    button!.props.onClick!({ stopPropagation })
    expect(stopPropagation).toHaveBeenCalledOnce()
    expect(captured.navigate).toHaveBeenCalledExactlyOnceWith('/app/y-lenh/CA%20GIA%2FLAP?tab=ho_so_benh_an', { state: { fromRecords: true } })
  })

  it('chi tiết mở từ danh sách hồ sơ giữ mục Hồ sơ bệnh án sáng', () => {
    const html = renderRoute('/app/y-lenh/DEMO-02?tab=y_lenh', { fromRecords: true })
    expect(html).toContain('aria-label="Hồ sơ bệnh án" aria-current="page"')
    expect(html).not.toContain('aria-label="Y lệnh" aria-current="page"')
  })
})

describe('bảng hồ sơ dùng dữ liệu danh sách ca hiện có', () => {
  it('hiện bảy cột, sáu ca và đánh dấu dữ liệu thiếu', () => {
    const html = renderToStaticMarkup(<MedicalRecordsList {...listProps()} />)
    expect(html.match(/scope="col"/g)).toHaveLength(7)
    expect(html).toContain('Y lệnh (lần cuối)')
    expect(html.match(/<td\b/g)).toHaveLength(MOCK_CASES.cases.length * 7)
    expect(html).toContain('NB-DEMO-02')
    expect(html).toContain('Nữ, 75 tuổi')
    expect(html).toContain('Hô hấp')
    expect(html.match(/>Chưa ghi nhận<\/td>/g)).toHaveLength(MOCK_CASES.cases.length * 4)
    expect(html).not.toContain('05:50')
    expect(html).not.toContain('Meropenem')
  })

  it('không suy diễn dữ liệu khi thiếu tóm tắt người bệnh và khoa', () => {
    const row = { ...MOCK_CASES.cases[0], nguoi_benh_tom_tat: null, khoa: '' }
    const html = renderToStaticMarkup(<MedicalRecordsList {...listProps({ cases: [row] })} />)
    expect(html).not.toContain('NB-DEMO-02')
    expect(html).toContain('aria-label="Mở hồ sơ DEMO-02"')
    expect(html.match(/>—</g)).toHaveLength(2)
    expect(html.match(/>Chưa ghi nhận</g)).toHaveLength(5)
  })

  it('hiện họ tên, ngày sinh, chẩn đoán và vào viện khi API cung cấp', () => {
    const row = { ...MOCK_CASES.cases[0], ho_ten: 'Nguyễn Thị 62', ngay_sinh: '1951-11-10',
      chan_doan_chinh: 'Viêm phổi', vao_vien: '2026-11-10T05:50:00+07:00', so_y_lenh: 3 }
    const html = renderToStaticMarkup(<MedicalRecordsList {...listProps({ cases: [row] })} />)
    for (const value of ['NGUYỄN THỊ 62', '10/11/1951', 'Viêm phổi', '05:50', '>3</td>']) {
      expect(html).toContain(value)
    }
  })

  it('tìm kiếm không dấu theo dữ liệu sẵn có và báo không khớp', () => {
    const html = renderToStaticMarkup(<MedicalRecordsList {...listProps({ searchQuery: 'nu 75' })} />)
    expect(html).toContain('NB-DEMO-02')
    expect(html).not.toContain('NB-DEMO-06')
    const empty = renderToStaticMarkup(<MedicalRecordsList {...listProps({ searchQuery: 'khong khop' })} />)
    expect(empty).toContain('Không tìm thấy hồ sơ phù hợp')
  })

  it('dùng trạng thái tải, rỗng và lỗi có thử lại', () => {
    expect(renderToStaticMarkup(<MedicalRecordsList {...listProps({ loading: true })} />)).toContain('aria-busy="true"')
    expect(renderToStaticMarkup(<MedicalRecordsList {...listProps({ cases: [] })} />)).toContain('Chưa có hồ sơ bệnh án')
    const props = listProps({ error: 'Lỗi giả lập' })
    const html = renderToStaticMarkup(<MedicalRecordsList {...props} />)
    expect(html).toContain('role="alert"')
    expect(html).toContain('Lỗi giả lập')
    expect(html).toContain('Thử lại')
    const errorView = elements(MedicalRecordsList(props)).find((item) => item.type !== 'section' && 'onRetry' in item.props)
    ;(errorView as ReactElement<{ onRetry: () => void }>).props.onRetry()
    expect(captured.retry).toHaveBeenCalledOnce()
  })
})
