import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter, Outlet } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { AppRoutes } from '../app/router'
import { TooltipProvider } from '../components/ui/tooltip'
import { SidebarNav } from '../features/sidebar/SidebarNav'

vi.mock('react-router-dom', async (original) => ({
  ...await original<typeof import('react-router-dom')>(),
  Navigate: ({ to, replace }: { to: string; replace?: boolean }) => (
    <i data-redirect={to} data-replace={String(Boolean(replace))} />
  ),
}))
vi.mock('../features/auth/ProtectedRoute', () => ({ ProtectedRoute: () => <Outlet /> }))

function renderSidebar(options: { collapsed: boolean; inDrawer?: boolean }): string {
  return renderToStaticMarkup(
    <TooltipProvider>
      <MemoryRouter>
        <SidebarNav
          {...options}
          activeSection="orders"
          onNavigate={() => {}}
          userEmail={null}
          isDemoMode
          onToggleCollapse={() => {}}
          onOpenSettings={() => {}}
          onSignIn={() => {}}
          onSignOut={() => {}}
        />
      </MemoryRouter>
    </TooltipProvider>,
  )
}

describe('bỏ trang danh sách Hồ sơ bệnh án', () => {
  it.each([
    { collapsed: false },
    { collapsed: true },
    { collapsed: true, inDrawer: true },
  ])('sidebar chỉ còn Hồ sơ cần duyệt (%o)', (options) => {
    const html = renderSidebar(options)
    expect(html).toContain('aria-label="Hồ sơ cần duyệt" aria-current="page"')
    expect(html).not.toContain('Hồ sơ bệnh án')
    expect(html).not.toContain('/app/ho-so')
  })

  it.each(['/app/ho-so', '/app/ho-so/', '/app/ho-so/abc'])('đường dẫn cũ %s chuyển về /app', (path) => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={[path]}><AppRoutes /></MemoryRouter>,
    )
    expect(html).toContain('data-redirect="/app"')
    expect(html).toContain('data-replace="true"')
  })
})
