import { useCallback, useMemo, useRef, useState } from 'react'
import type { PhanHoiDaGhi } from '@/api/types'
import { apiClient } from '@/api/index'
import { AppShell } from '@/app/AppShell'
import { ChatPanel } from '@/features/assistant/ChatPanel'
import { CaseHeader } from '@/features/case-header/CaseHeader'
import { DetailTabs } from '@/features/detail/DetailTabs'
import { EvidenceDialog } from '@/features/findings/EvidenceDialog'
import { FindingsSection } from '@/features/findings/FindingsSection'
import { QueuePanel } from '@/features/queue/QueuePanel'
import {
  DetailSkeleton,
  EmptyDetailState,
  EmptyQueueState,
  ErrorState,
} from '@/features/states/StateViews'
import { SummarySection } from '@/features/summary/SummarySection'
import {
  countAiSummary,
  mergeFindingsFeedback,
  selectFindingsSource,
} from '@/lib/aiReview'
import { loadUiPrefs, saveChatCollapsed, saveQueueCollapsed } from '@/lib/prefs'
import { sortAttentionFindings } from '@/lib/presentation'
import { filterQueue } from '@/lib/queue'
import type { DetailTabId, EvidenceTarget } from '@/lib/uiTypes'
import { useAiReview } from '@/state/useAiReview'
import { useCaseDetail } from '@/state/useCaseDetail'
import { useCases } from '@/state/useCases'
import { useChat } from '@/state/useChat'
import { useFeedback } from '@/state/useFeedback'

interface DialogState {
  target: EvidenceTarget | null
  triggerEl: HTMLElement | null
}

/** Ứng dụng thẩm định y lệnh cho dược sĩ lâm sàng. */
export function App() {
  const [queueCollapsed, setQueueCollapsed] = useState<boolean>(
    () => loadUiPrefs().queueCollapsed,
  )
  const [chatCollapsed, setChatCollapsed] = useState<boolean>(
    () => loadUiPrefs().chatCollapsed,
  )
  const [activeTab, setActiveTab] = useState<DetailTabId>('y_lenh')
  const [dialogState, setDialogState] = useState<DialogState>({
    target: null,
    triggerEl: null,
  })
  const [sessionFeedback, setSessionFeedback] = useState<
    Record<string, Record<string, PhanHoiDaGhi>>
  >({})

  const findingsRef = useRef<HTMLElement | null>(null)
  const detailTabsRef = useRef<HTMLElement | null>(null)

  const {
    data: casesData,
    loading: casesLoading,
    error: casesError,
    selectedCaseId,
    filter,
    selectCase,
    setFilter,
    reload: reloadCases,
    markAllResponded,
  } = useCases(apiClient)

  const {
    detail,
    loading: detailLoading,
    error: detailError,
    retry: retryDetail,
    applyFeedbackToCase,
  } = useCaseDetail(apiClient, selectedCaseId)

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
  const chat = useChat(apiClient)

  const allCases = useMemo(() => casesData?.cases ?? [], [casesData])
  const filteredCases = useMemo(
    () => filterQueue(allCases, filter),
    [allCases, filter],
  )

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
  const passedFindings = displayedFindings?.dat ?? []
  const aiSummary = useMemo(() => countAiSummary(ai.ketQua), [ai.ketQua])

  const activeMode = detail?.che_do ?? casesData?.che_do ?? null

  const handleToggleQueue = useCallback(() => {
    setQueueCollapsed((prev) => {
      const next = !prev
      saveQueueCollapsed(next)
      return next
    })
  }, [])

  const handleToggleChat = useCallback(() => {
    setChatCollapsed((prev) => {
      const next = !prev
      saveChatCollapsed(next)
      return next
    })
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

  const handleViewAllNotes = useCallback(() => {
    setActiveTab('dien_bien')
    detailTabsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])

  const handleJumpToFindings = useCallback(() => {
    findingsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])

  return (
    <>
      <AppShell
        cheDo={activeMode}
        queueCollapsed={queueCollapsed}
        onToggleQueue={handleToggleQueue}
        chatCollapsed={chatCollapsed}
        onToggleChat={handleToggleChat}
        hasCase={Boolean(detail)}
        thoiGianMs={detail?.thoi_gian_ms ?? null}
        queueSlot={
          <QueuePanel
            allCases={allCases}
            filteredCases={filteredCases}
            loiNap={casesData?.loi_nap ?? []}
            loading={casesLoading}
            error={casesError}
            selectedCaseId={selectedCaseId}
            filter={filter}
            collapsed={queueCollapsed}
            onSelectCase={selectCase}
            onFilterChange={setFilter}
            onToggleCollapse={handleToggleQueue}
            onRetry={reloadCases}
          />
        }
        queueDrawerSlot={
          <QueuePanel
            allCases={allCases}
            filteredCases={filteredCases}
            loiNap={casesData?.loi_nap ?? []}
            loading={casesLoading}
            error={casesError}
            selectedCaseId={selectedCaseId}
            filter={filter}
            collapsed={false}
            inDrawer
            onSelectCase={selectCase}
            onFilterChange={setFilter}
            onToggleCollapse={handleToggleQueue}
            onRetry={reloadCases}
          />
        }
        headerSlot={detail ? <CaseHeader dinhDanh={detail.dinh_danh} /> : null}
        renderChat={(onCloseChat) =>
          detail ? (
            <ChatPanel
              key={detail.ca_id}
              caId={detail.ca_id}
              cauHoiGoiY={detail.cau_hoi_goi_y}
              messages={chat.getMessages(detail.ca_id)}
              sending={chat.isSending(detail.ca_id)}
              hoiThemEnabled={Boolean(detail.che_do.hoi_them)}
              chiSo={detail.chi_so}
              onClose={onCloseChat}
              onSend={chat.sendQuestion}
              onClear={chat.clearChat}
              onOpenEvidence={handleOpenEvidence}
            />
          ) : null
        }
      >
        {detail ? (
          <>
            <SummarySection
              caId={detail.ca_id}
              tomTat={detail.tom_tat}
              chiSo={detail.chi_so}
              crclBatThuong={detail.dinh_danh.crcl_bat_thuong}
              onViewAllNotes={handleViewAllNotes}
              onOpenEvidence={handleOpenEvidence}
            />

            <FindingsSection
              caId={detail.ca_id}
              attentionFindings={attentionFindings}
              passedFindings={passedFindings}
              yeuToChuaKiem={detail.nhan_dinh.yeu_to_chua_kiem}
              soLuatDaChay={detail.nhan_dinh.so_luat_da_chay}
              chiSo={detail.chi_so}
              nhomLyDo={detail.nhom_ly_do}
              aiTrangThai={ai.trangThai}
              aiThoiGianMs={ai.thoiGianMs}
              aiCoDienGiai={aiSummary.coDienGiai}
              aiDoAiThem={aiSummary.doAiThem}
              aiCanhBao={ai.canhBao}
              onRerunAi={ai.chayLai}
              isFeedbackSubmitting={feedback.isSubmitting}
              getFeedbackError={feedback.getError}
              onSubmitFeedback={feedback.submitFeedback}
              onClearFeedbackError={feedback.clearError}
              onOpenEvidence={handleOpenEvidence}
              sectionRef={findingsRef}
            />

            <DetailTabs
              chiTiet={detail.chi_tiet}
              activeTab={activeTab}
              onTabChange={setActiveTab}
              sectionRef={detailTabsRef}
              onJumpToFindings={handleJumpToFindings}
            />
          </>
        ) : casesLoading ? (
          <DetailSkeleton />
        ) : casesError ? (
          <ErrorState
            title="Không tải được danh sách ca"
            message={casesError}
            onRetry={reloadCases}
          />
        ) : allCases.length === 0 ? (
          <EmptyQueueState />
        ) : detailLoading && selectedCaseId ? (
          <DetailSkeleton />
        ) : detailError ? (
          <ErrorState
            title={`Không tải được ca ${selectedCaseId ?? ''}`}
            message={detailError}
            onRetry={retryDetail}
          />
        ) : (
          <EmptyDetailState />
        )}
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

export default App
