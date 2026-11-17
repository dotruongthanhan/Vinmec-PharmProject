import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Children, isValidElement } from 'react'
import type { ReactElement, ReactNode } from 'react'
import { SidebarNav } from '../features/sidebar/SidebarNav'
import type { SidebarNavProps } from '../features/sidebar/SidebarNav'

// Điều khiển hook khi kiểm tra cây React trong Node, không thay thế SidebarNav.
const state = vi.hoisted(() => ({ open: false }))
vi.mock('react', async (original) => ({
  ...await original<typeof import('react')>(),
  useState: () => [state.open, (open: boolean) => { state.open = open }],
}))

type ElementProps = {
  children?: ReactNode
  role?: string
  'aria-label'?: string
  onClick?: () => void
  onOpenChange?: (open: boolean) => void
  open?: boolean
}

function elements(node: ReactNode): ReactElement<ElementProps>[] {
  return Children.toArray(node).flatMap((child) => {
    if (!isValidElement<ElementProps>(child)) return []
    return [child, ...elements(child.props.children)]
  })
}

function text(node: ReactNode): string {
  return Children.toArray(node).map((child): string => {
    if (typeof child === 'string' || typeof child === 'number') return String(child)
    return isValidElement<ElementProps>(child) ? text(child.props.children) : ''
  }).join('')
}

function render(overrides: Partial<SidebarNavProps> = {}) {
  return SidebarNav({
    counts: { tat_ca: 0, can_xem: 0, thieu_du_lieu: 0, dat: 0, da_phan_hoi: 0, departments: [] },
    activeFilter: { type: 'group', group: 'tat_ca' },
    collapsed: false,
    userEmail: 'tai-khoan@example.invalid',
    isDemoMode: false,
    onSelectFilter: () => {},
    onToggleCollapse: () => {},
    onOpenSettings: () => {},
    onSignIn: () => {},
    onSignOut: () => {},
    ...overrides,
  })
}

function menuItem(tree: ReactNode, label: string) {
  const item = elements(tree).find((element) => element.props.role === 'menuitem' && text(element.props.children) === label)
  expect(item, `Thiếu mục menu ${label}`).toBeDefined()
  return item!
}

beforeEach(() => { state.open = false })

describe('nhãn tài khoản ở thanh bên', () => {
  it.each([
    { vaiTro: 'admin' as const, isDemoMode: false, label: 'Quản trị' },
    { vaiTro: 'duoc_si_ls' as const, isDemoMode: false, label: 'Dược sĩ lâm sàng' },
    { vaiTro: 'admin' as const, isDemoMode: true, label: 'Demo' },
    { vaiTro: null, isDemoMode: false, label: 'Chưa cấp quyền' },
    { vaiTro: undefined, isDemoMode: false, label: 'Chưa cấp quyền' },
  ])('hiện $label cho vai trò $vaiTro khi demo=$isDemoMode', ({ vaiTro, isDemoMode, label }) => {
    const tree = render({ vaiTro, isDemoMode })
    const account = elements(tree).find((element) => element.props['aria-label'] === 'Mở menu tài khoản và cài đặt')
    expect(text(account?.props.children)).toContain(` · ${label}`)
  })

  it('thiếu email dùng Tài khoản ở tên ngắn và nhãn khi thu gọn', () => {
    const expanded = render({ userEmail: null })
    const account = elements(expanded).find((element) => element.props['aria-label'] === 'Mở menu tài khoản và cài đặt')
    expect(text(account?.props.children)).toContain('Tài khoản · Chưa cấp quyền')
    const collapsed = render({ userEmail: null, collapsed: true })
    expect(elements(collapsed).some((element) => element.props['aria-label'] === 'Tài khoản · Tuỳ chọn tài khoản')).toBe(true)
  })
})

describe('phạm vi đăng xuất từ menu tài khoản', () => {
  it.each([
    { label: 'Đăng xuất', scope: 'local' },
    { label: 'Đăng xuất mọi thiết bị', scope: 'global' },
  ] as const)('$label gửi scope=$scope và đóng menu', ({ label, scope }) => {
    const onSignOut = vi.fn()
    const tree = render({ onSignOut })
    const popover = elements(tree).find((element) => element.props.onOpenChange)
    popover?.props.onOpenChange?.(true)
    expect(state.open).toBe(true)
    menuItem(render({ onSignOut }), label).props.onClick?.()
    expect(onSignOut).toHaveBeenCalledExactlyOnceWith({ scope })
    expect(state.open).toBe(false)
  })

  it('demo giữ mục thoát demo và không hiện đăng xuất mọi thiết bị', () => {
    const onSignOut = vi.fn()
    const tree = render({ isDemoMode: true, onSignOut })
    const labels = elements(tree).filter((element) => element.props.role === 'menuitem').map((element) => text(element.props.children))
    expect(labels).toContain('Đăng nhập tài khoản')
    expect(labels).not.toContain('Đăng xuất mọi thiết bị')
    menuItem(tree, 'Thoát chế độ demo').props.onClick?.()
    expect(onSignOut).toHaveBeenCalledExactlyOnceWith()
  })
})
