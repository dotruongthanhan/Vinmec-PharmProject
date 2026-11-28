import { useCallback, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { AppShell } from '@/app/AppShell'
import { useAuth } from '@/features/auth/useAuth'
import type { SignOutOptions } from '@/features/auth/useAuth'
import { SettingsDialog } from '@/features/settings/SettingsDialog'
import { SidebarNav } from '@/features/sidebar/SidebarNav'
import type { SidebarSection } from '@/features/sidebar/SidebarNav'
import { loadUiPrefs, saveQueueCollapsed } from '@/lib/prefs'

export interface LookupWorkspaceProps {
  section: Exclude<SidebarSection, 'orders'>
  /** Tên mục ở thanh đường dẫn (ví dụ "Tra cứu thuốc"). */
  breadcrumbLabel: string
  /** Đường dẫn của trang danh sách, dùng cho mũi tên quay lại. */
  backTo: string
  /** Tên mục con đang xem (hoạt chất hay công thức); có thì hiện mũi tên quay lại. */
  activeItem?: string | null
  children: ReactNode
}

/** Khung bàn làm việc cho ba trang tra cứu: thanh bên chung, không có khung trợ lý. */
export function LookupWorkspace({ section, breadcrumbLabel, backTo, activeItem = null, children }: LookupWorkspaceProps) {
  const navigate = useNavigate()
  const { userEmail, isDemoMode, vaiTro, signOut } = useAuth()
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(() => loadUiPrefs().queueCollapsed)
  const [drawerSidebarOpen, setDrawerSidebarOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const searchInputRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key === ',') {
        event.preventDefault()
        setSettingsOpen((prev) => !prev)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  const handleToggleSidebar = useCallback(() => {
    setSidebarCollapsed((prev) => {
      saveQueueCollapsed(!prev)
      return !prev
    })
  }, [])
  const handleOpenSettings = useCallback(() => {
    setDrawerSidebarOpen(false)
    setSettingsOpen(true)
  }, [])
  const handleSignIn = useCallback(() => {
    setDrawerSidebarOpen(false)
    void signOut()
  }, [signOut])
  const handleSignOut = useCallback((options?: SignOutOptions) => {
    void signOut(options)
  }, [signOut])

  const sidebarProps = {
    activeSection: section,
    onNavigate: () => setDrawerSidebarOpen(false),
    userEmail,
    isDemoMode,
    vaiTro,
    onToggleCollapse: handleToggleSidebar,
    onOpenSettings: handleOpenSettings,
    onSignIn: handleSignIn,
    onSignOut: handleSignOut,
  }

  return (
    <>
      <AppShell
        cheDo={null}
        activeOrderCode={activeItem}
        breadcrumbLabel={breadcrumbLabel}
        backTo={backTo}
        assistantAvailable={false}
        searchQuery=""
        searchInputRef={searchInputRef}
        isDemoMode={isDemoMode}
        sidebarCollapsed={sidebarCollapsed}
        assistantCollapsed
        assistantWidth={0}
        drawerSidebarOpen={drawerSidebarOpen}
        drawerAssistantOpen={false}
        onDrawerSidebarChange={setDrawerSidebarOpen}
        onDrawerAssistantChange={() => {}}
        onToggleSidebar={handleToggleSidebar}
        onToggleAssistant={() => {}}
        onAssistantWidthChange={() => {}}
        onSearchChange={() => {}}
        onSearchFocusOrSubmit={() => navigate('/app')}
        sidebarSlot={<SidebarNav {...sidebarProps} collapsed={sidebarCollapsed} />}
        sidebarDrawerSlot={<SidebarNav {...sidebarProps} collapsed={false} inDrawer />}
        assistantSlot={null}
      >
        <div className="mx-auto w-full max-w-[1200px] px-3 py-5 sm:px-6">{children}</div>
      </AppShell>
      <SettingsDialog
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        userEmail={userEmail}
        isDemoMode={isDemoMode}
        cheDo={null}
        sidebarCollapsed={sidebarCollapsed}
        assistantCollapsed
        onToggleSidebarCollapse={handleToggleSidebar}
        onToggleAssistantCollapse={() => {}}
        onSignIn={handleSignIn}
        onSignOut={handleSignOut}
      />
    </>
  )
}
