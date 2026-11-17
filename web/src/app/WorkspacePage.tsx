import { Search, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { apiClient } from '@/api/index'
import type { NhanDinh, PhanHoiDaGhi } from '@/api/types'
import { AppShell } from '@/app/AppShell'
import { AssistantPanel } from '@/features/assistant/AssistantPanel'
import type { FocusedFindingContext } from '@/features/assistant/AssistantPanel'
import { useAuth } from '@/features/auth/useAuth'
import { EvidenceDialog } from '@/features/findings/EvidenceDialog'
import { OrderDetailView } from '@/features/order-detail/OrderDetailView'
import { OrdersTable } from '@/features/orders/OrdersTable'
import { SidebarNav } from '@/features/sidebar/SidebarNav'
import { DetailSkeleton, ErrorState } from '@/features/states/StateViews'
import { mergeFindingsFeedback, selectFindingsSource } from '@/lib/aiReview'
import { extractOrderCode } from '@/lib/displayFormat'
import { extractShortDrugName } from '@/lib/orderDetail'
import {
  countOrderGroups,
  filterOrders,
  getOrderFilterTitle,
  sortOrders,
} from '@/lib/orders'
import type {
  OrderSelectionFilter,
  OrderSortDirection,
  OrderSortField,
} from '@/lib/orders'
import {
  loadUiPrefs,
  saveAssistantWidth,
  saveChatCollapsed,
  saveQueueCollapsed,
} from '@/lib/prefs'
import { sortAttentionFindings } from '@/lib/presentation'
import type { EvidenceTarget } from '@/lib/uiTypes'
import { useAiReview } from '@/state/useAiReview'
import { useCaseDetail } from '@/state/useCaseDetail'
import { useCases } from '@/state/useCases'
import { useChat } from '@/state/useChat'
import { useFeedback } from '@/state/useFeedback'

interface DialogState {
  target: EvidenceTarget | null
  triggerEl: HTMLElement | null
}

/** Bàn làm việc ba cột cho tuyến /app (danh sách y lệnh) và /app/y-lenh/:caId (chi tiết y lệnh). */
export function WorkspacePage() {
  const { caId: routeCaId } = useParams<{ caId?: string }>()
  const navigate = useNavigate()
  const { userEmail, isDemoMode, signOut } = useAuth()

  const activeCaseId = routeCaId ?? null
  const isListRoute = activeCaseId === null

  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(
    () => loadUiPrefs().queueCollapsed,
  )
  const [assistantCollapsed, setAssistantCollapsed] = useState<boolean>(
    () => loadUiPrefs().chatCollapsed,
  )
  const [assistantWidth, setAssistantWidth] = useState<number>(
    () => loadUiPrefs().assistantWidth,
  )
  const [drawerSidebarOpen, setDrawerSidebarOpen] = useState<boolean>(false)
  const [drawerAssistantOpen, setDrawerAssistantOpen] = useState<boolean>(false)

  const [activeFilter, setActiveFilter] = useState<OrderSelectionFilter>({
    type: 'group',
    group: 'tat_ca',
  })
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [sortField, setSortField] = useState<OrderSortField>('ket_qua')
  const [sortDirection, setSortDirection] = useState<OrderSortDirection>('desc')
  const [focusedFinding, setFocusedFinding] = useState<FocusedFindingContext | null>(null)
  const [dialogState, setDialogState] = useState<DialogState>({
    target: null,
    triggerEl: null,
  })
  const [sessionFeedback, setSessionFeedback] = useState<
    Record<string, Record<string, PhanHoiDaGhi>>
  >({})

  const [prevActiveCaseId, setPrevActiveCaseId] = useState<string | null>(activeCaseId)
  if (prevActiveCaseId !== activeCaseId) {
    setPrevActiveCaseId(activeCaseId)
    setFocusedFinding(null)
  }

  const searchInputRef = useRef<HTMLInputElement | null>(null)

  const {
    data: casesData,
    loading: casesLoading,
    error: casesError,
    reload: reloadCases,
    markAllResponded,
  } = useCases(apiClient)

  const {
    detail,
    loading: detailLoading,
    error: detailError,
    retry: retryDetail,
    applyFeedbackToCase,
  } = useCaseDetail(apiClient, activeCaseId)

  const ai = useAiReview(
    detail?.ca_id ?? null,
    Boolean(detail?.che_do.co_llm),
    apiClient,
  )

  const handleFeedbackSuccess = useCallback(
    (caId: string, nhanDinhId: string, recorded: PhanHoiDaGhi) => {
      const nextCaseFeedback = {
        ...(sessionFeedback[caId] ?? {}),
        [nhanDinhId]: recorded,
      }
      setSessionFeedback((prev) => ({
        ...prev,
        [caId]: {
          ...(prev[caId] ?? {}),
          [nhanDinhId]: recorded,
        },
      }))
      const ruleAllDone = applyFeedbackToCase(caId, nhanDinhId, recorded)
      let allDone = ruleAllDone
      if (detail?.ca_id === caId && ai.trangThai === 'xong' && ai.ketQua?.nhan_dinh) {
        const merged = mergeFindingsFeedback(ai.ketQua.nhan_dinh, nextCaseFeedback, [
          detail.nhan_dinh,
        ])
        allDone =
          merged.can_chu_y.length > 0 &&
          merged.can_chu_y.every((item) => item.phan_hoi !== null)
      }
      markAllResponded(caId, allDone)
    },
    [applyFeedbackToCase, markAllResponded, detail, ai.trangThai, ai.ketQua, sessionFeedback],
  )

  const feedback = useFeedback(apiClient, handleFeedbackSuccess)
  const chat = useChat(apiClient, activeCaseId)

  const allCases = useMemo(() => casesData?.cases ?? [], [casesData])
  const counts = useMemo(() => countOrderGroups(allCases), [allCases])

  const filteredOrders = useMemo(
    () => filterOrders(allCases, activeFilter, searchQuery),
    [allCases, activeFilter, searchQuery],
  )
  const sortedOrders = useMemo(
    () => sortOrders(filteredOrders, sortField, sortDirection),
    [filteredOrders, sortField, sortDirection],
  )

  const recentCases = useMemo(() => {
    const map = new Map(allCases.map((c) => [c.ca_id, c]))
    return chat.askedCaseIds
      .map((id) => map.get(id))
      .filter((item): item is NonNullable<typeof item> => item !== undefined)
  }, [allCases, chat.askedCaseIds])

  const displayedFindings = useMemo(() => {
    if (!detail) {
      return null
    }
    const raw = selectFindingsSource(detail.nhan_dinh, ai.trangThai, ai.ketQua)
    const fallbackSources =
      raw === detail.nhan_dinh
        ? ai.ketQua?.nhan_dinh
          ? [ai.ketQua.nhan_dinh]
          : []
        : [detail.nhan_dinh]
    return mergeFindingsFeedback(raw, sessionFeedback[detail.ca_id] ?? {}, fallbackSources)
  }, [detail, ai.trangThai, ai.ketQua, sessionFeedback])

  const attentionFindings = useMemo(
    () => (displayedFindings ? sortAttentionFindings(displayedFindings.can_chu_y) : []),
    [displayedFindings],
  )

  const navigationOrderList = useMemo(() => {
    if (sortedOrders.some((c) => c.ca_id === activeCaseId)) {
      return sortedOrders
    }
    return allCases
  }, [sortedOrders, allCases, activeCaseId])

  const currentIdx = activeCaseId
    ? navigationOrderList.findIndex((c) => c.ca_id === activeCaseId)
    : -1
  const canPrev = currentIdx > 0
  const canNext = currentIdx !== -1 && currentIdx < navigationOrderList.length - 1

  const handleFocusSearch = useCallback(() => {
    setDrawerSidebarOpen(false)
    if (!isListRoute) {
      navigate('/app')
    }
    requestAnimationFrame(() => {
      searchInputRef.current?.focus()
      searchInputRef.current?.select()
    })
  }, [isListRoute, navigate])

  useEffect(() => {
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        handleFocusSearch()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [handleFocusSearch])

  const handleToggleSidebar = useCallback(() => {
    setSidebarCollapsed((prev) => {
      const next = !prev
      saveQueueCollapsed(next)
      return next
    })
  }, [])

  const handleToggleAssistant = useCallback(() => {
    setAssistantCollapsed((prev) => {
      const next = !prev
      saveChatCollapsed(next)
      return next
    })
  }, [])

  const handleAssistantWidthChange = useCallback((nextWidth: number) => {
    setAssistantWidth(nextWidth)
    saveAssistantWidth(nextWidth)
  }, [])

  const handleSelectFilter = useCallback(
    (nextFilter: OrderSelectionFilter) => {
      setActiveFilter(nextFilter)
      setDrawerSidebarOpen(false)
      if (!isListRoute) {
        navigate('/app')
      }
    },
    [isListRoute, navigate],
  )

  const handleOpenCase = useCallback(
    (caId: string) => {
      setDrawerSidebarOpen(false)
      navigate(`/app/y-lenh/${encodeURIComponent(caId)}`)
    },
    [navigate],
  )

  const handleToggleSort = useCallback(
    (field: OrderSortField) => {
      if (sortField === field) {
        setSortDirection((prev) => (prev === 'desc' ? 'asc' : 'desc'))
      } else {
        setSortField(field)
        setSortDirection('desc')
      }
    },
    [sortField],
  )

  const handleResetFilters = useCallback(() => {
    setActiveFilter({ type: 'group', group: 'tat_ca' })
    setSearchQuery('')
  }, [])

  const handleOpenEvidence = useCallback(
    (target: EvidenceTarget, trigger: HTMLButtonElement) => {
      setDialogState({ target, triggerEl: trigger })
    },
    [],
  )

  const handleCloseEvidence = useCallback(() => {
    setDialogState({ target: null, triggerEl: null })
  }, [])

  const handleAskAboutFinding = useCallback((finding: NhanDinh) => {
    const shortDrug = finding.thuoc ? extractShortDrugName(finding.thuoc) : ''
    const label = shortDrug ? `${shortDrug} · ${finding.yeu_to}` : finding.yeu_to
    setFocusedFinding({
      nhanDinhId: finding.nhan_dinh_id,
      label,
    })
    setAssistantCollapsed(false)
    saveChatCollapsed(false)
    if (typeof window !== 'undefined' && window.innerWidth < 1180) {
      setDrawerAssistantOpen(true)
    }
  }, [])

  const handleSignOut = useCallback(() => {
    void signOut().then(() => {
      navigate('/dang-nhap', { replace: true })
    })
  }, [signOut, navigate])

  const activeOrderCode = activeCaseId
    ? detail && detail.ca_id === activeCaseId
      ? extractOrderCode(detail.chi_tiet.y_lenh.thong_tin_text, detail.ca_id)
      : activeCaseId
    : null

  const activeMode = detail?.che_do ?? casesData?.che_do ?? null

  const sidebarCommonProps = {
    counts,
    activeFilter,
    isListRoute,
    activeCaseId,
    recentCases,
    userEmail,
    isDemoMode,
    onSelectFilter: handleSelectFilter,
    onOpenCase: handleOpenCase,
    onFocusSearch: handleFocusSearch,
    onToggleCollapse: handleToggleSidebar,
    onSignOut: handleSignOut,
  }

  return (
    <>
      <AppShell
        cheDo={activeMode}
        activeOrderCode={activeOrderCode}
        searchQuery={searchQuery}
        searchInputRef={searchInputRef}
        isDemoMode={isDemoMode}
        sidebarCollapsed={sidebarCollapsed}
        assistantCollapsed={assistantCollapsed}
        assistantWidth={assistantWidth}
        drawerSidebarOpen={drawerSidebarOpen}
        drawerAssistantOpen={drawerAssistantOpen}
        onDrawerSidebarChange={setDrawerSidebarOpen}
        onDrawerAssistantChange={setDrawerAssistantOpen}
        onToggleSidebar={handleToggleSidebar}
        onToggleAssistant={handleToggleAssistant}
        onAssistantWidthChange={handleAssistantWidthChange}
        onSearchChange={setSearchQuery}
        onSearchFocusOrSubmit={() => {
          if (!isListRoute) {
            navigate('/app')
          }
        }}
        sidebarSlot={<SidebarNav {...sidebarCommonProps} collapsed={sidebarCollapsed} />}
        sidebarDrawerSlot={
          <SidebarNav {...sidebarCommonProps} collapsed={false} inDrawer />
        }
        assistantSlot={
          <AssistantPanel
            client={apiClient}
            detail={detail && detail.ca_id === activeCaseId ? detail : null}
            attentionFindings={attentionFindings}
            messages={activeCaseId ? chat.getMessages(activeCaseId) : []}
            sending={activeCaseId ? chat.isSending(activeCaseId) : false}
            lastStatus={activeCaseId ? chat.getLastStatus(activeCaseId) : null}
            focusedFinding={focusedFinding}
            onClearFocusedFinding={() => setFocusedFinding(null)}
            onSend={chat.sendQuestion}
            onStop={chat.stopQuestion}
            onRetryLast={chat.retryLastQuestion}
            onClear={chat.clearChat}
            onClose={() => {
              if (drawerAssistantOpen) {
                setDrawerAssistantOpen(false)
              } else {
                handleToggleAssistant()
              }
            }}
            onOpenEvidence={handleOpenEvidence}
          />
        }
      >
        {isListRoute ? (
          <div className="mx-auto w-full max-w-[1040px] px-2 py-5 sm:px-4 flex flex-col gap-3">
            {/* Ô tìm kiếm cho màn hình hẹp (< 640px) khi ô trên thanh công cụ ẩn */}
            <div className="list-search relative flex items-center">
              <Search
                className="pointer-events-none absolute left-2.5 size-3.5 text-fg-subtle"
                strokeWidth={1.75}
                aria-hidden="true"
              />
              <input
                type="search"
                value={searchQuery}
                aria-label="Tìm kiếm y lệnh trên điện thoại"
                placeholder="Tìm y lệnh, thuốc, khoa…"
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-9 w-full rounded-sm border border-line-strong bg-surface pl-8 pr-8 text-sm text-fg placeholder:text-fg-subtle"
              />
              {searchQuery ? (
                <button
                  type="button"
                  aria-label="Xoá tìm kiếm"
                  onClick={() => setSearchQuery('')}
                  className="absolute right-2 inline-flex size-5 items-center justify-center rounded-sm text-fg-subtle"
                >
                  <X className="size-3.5" strokeWidth={1.75} aria-hidden="true" />
                </button>
              ) : null}
            </div>

            <OrdersTable
              filterTitle={getOrderFilterTitle(activeFilter)}
              orders={sortedOrders}
              totalCount={allCases.length}
              loiNap={casesData?.loi_nap ?? []}
              loading={casesLoading}
              error={casesError}
              searchQuery={searchQuery}
              sortField={sortField}
              sortDirection={sortDirection}
              onToggleSort={handleToggleSort}
              onOpenOrder={handleOpenCase}
              onResetFilters={handleResetFilters}
              onRetry={reloadCases}
            />
          </div>
        ) : detail && detail.ca_id === activeCaseId ? (
          <OrderDetailView
            detail={detail}
            aiTrangThai={ai.trangThai}
            aiKetQua={ai.ketQua}
            aiThoiGianMs={ai.thoiGianMs}
            aiCanhBao={ai.canhBao}
            sessionFeedbackForCase={sessionFeedback[detail.ca_id] ?? {}}
            canPrev={canPrev}
            canNext={canNext}
            onBackToList={() => navigate('/app')}
            onPrevOrder={() => {
              if (canPrev) {
                handleOpenCase(navigationOrderList[currentIdx - 1].ca_id)
              }
            }}
            onNextOrder={() => {
              if (canNext) {
                handleOpenCase(navigationOrderList[currentIdx + 1].ca_id)
              }
            }}
            onRerunAi={ai.chayLai}
            isFeedbackSubmitting={feedback.isSubmitting}
            getFeedbackError={feedback.getError}
            onSubmitFeedback={feedback.submitFeedback}
            onClearFeedbackError={feedback.clearError}
            onOpenEvidence={handleOpenEvidence}
            onAskAboutFinding={handleAskAboutFinding}
          />
        ) : detailLoading ? (
          <div className="mx-auto w-full max-w-[960px] px-5 py-5">
            <DetailSkeleton />
          </div>
        ) : detailError ? (
          <div className="mx-auto w-full max-w-[960px] px-5 py-5">
            <ErrorState
              title={`Không tải được y lệnh ${activeCaseId}`}
              message={detailError}
              onRetry={retryDetail}
            />
          </div>
        ) : null}
      </AppShell>

      <EvidenceDialog
        target={dialogState.target}
        client={apiClient}
        returnFocusEl={dialogState.triggerEl}
        onClose={handleCloseEvidence}
      />
    </>
  )
}
