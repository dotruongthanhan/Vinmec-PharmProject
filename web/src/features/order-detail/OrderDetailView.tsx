import { ArrowDown, ArrowUp, ClipboardList, FileText, MinusCircle, Pill, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useSearchParams } from 'react-router-dom'
import type {
  BuocAI,
  ChiTietCa,
  GuiPhanHoi,
  KetQuaAI,
  NhanDinh,
  PhanHoiDaGhi,
  TrangThaiAI,
} from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import {
  DataTable,
  DataTableBody,
  DataTableCell,
  DataTableHead,
  DataTableHeader,
  DataTableRow,
} from '@/components/ui/data-table'
import { EmptyState } from '@/components/ui/empty-state'
import { InlineAlert } from '@/components/ui/inline-alert'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { LabTrendChart } from '@/features/charts/LabTrendChart'
import { AiStatusBar } from '@/features/findings/AiStatusBar'
import { FindingCard } from '@/features/findings/FindingCard'
import { PassedList } from '@/features/findings/PassedList'
import { FactorStatusIcon } from '@/features/sidebar/ReviewFactorNav'
import { countAiSummary } from '@/lib/aiReview'
import { parseInfoPairs } from '@/lib/detailTables'
import {
  extractOrderTimeText,
  formatClinicalText,
  parseLeadingSymbolLabel,
  parseTrendValue,
} from '@/lib/displayFormat'
import {
  factorIndexOf,
  filterFindingsByDrug,
  filterTreatmentSheetNotes,
  parseDetailTabParam,
  parseReviewFactorParam,
  updateReviewFactorParams,
} from '@/lib/orderDetail'
import type { FactorIndex, SixFactorStatus } from '@/lib/orderDetail'
import type { SemanticTone } from '@/lib/severity'
import { EMPTY_FEEDBACK_DRAFT } from '@/lib/uiTypes'
import type { DetailTabId, EvidenceTarget, FeedbackDraft } from '@/lib/uiTypes'
import {
  InfoRows,
  LabPivotTable,
  MetricsTable,
  NotesTable,
  OrderLinesTable,
  SectionHeading,
} from './DetailSections'
import type { InfoItem } from './DetailSections'
import { InteractionSection } from './InteractionSection'
import { AdministrativeSections } from './AdministrativeSections'
import { countMedicalOrders, medicalOrders, orderSelectionParams, selectMedicalOrder } from '@/lib/medicalRecord'
import { OrderExtraInfo, OrderSelector, SelectedOrderDetails, TreatmentSheets } from './MedicalRecordSections'
import { useReviewFindings } from './useReviewFindings'

export type OrderDetailTab = DetailTabId

function factorStatusTone(status: SixFactorStatus, hasSevere: boolean): SemanticTone {
  switch (status) {
    case 'co_van_de':
      return hasSevere ? 'danger' : 'warning'
    case 'thieu_du_lieu':
      return 'missing'
    case 'dat':
      return 'success'
    case 'chua_co_luat':
      return 'neutral'
  }
}

export interface OrderDetailViewProps {
  detail: ChiTietCa
  orderSelectionReady?: boolean
  aiTrangThai: TrangThaiAI
  aiKetQua: KetQuaAI | null
  aiThoiGianMs: number | null
  aiCanhBao: readonly string[]
  aiCacBuoc?: readonly BuocAI[]
  aiDaChayMs?: number | null
  aiThuongLeMs?: number | null
  sessionFeedbackForCase: Readonly<Record<string, PhanHoiDaGhi>>
  onRerunAi: () => void
  isFeedbackSubmitting: (caId: string, id: string) => boolean
  getFeedbackError: (caId: string, id: string) => string | null
  onSubmitFeedback: (caId: string, payload: GuiPhanHoi) => Promise<boolean>
  onClearFeedbackError: (caId: string, id: string) => void
  onOpenEvidence: (target: EvidenceTarget, trigger: HTMLButtonElement) => void
  onAskAboutFinding: (finding: NhanDinh) => void
}

function EmptyBox({
  icon,
  title,
  description,
}: {
  icon: typeof FileText
  title: string
  description: string
}) {
  return (
    <div className="rounded-md border border-line bg-surface">
      <EmptyState icon={icon} title={title} description={description} />
    </div>
  )
}

function primaryDiagnosis(detail: ChiTietCa): string {
  const list = detail.tom_tat.chan_doan
  if (list.length === 0) {
    return 'Chưa ghi nhận'
  }
  return list
    .map((cd) => `${cd.noi_dung}${cd.ma_icd10 ? ` (${cd.ma_icd10})` : ''}`)
    .join('; ')
}

/** Tách họ tên, tuổi, giới, cân nặng, chiều cao thành ô riêng; thiếu thì dùng chuỗi ghép cũ hoặc "Chưa ghi nhận". */
function patientFieldItems(detail: ChiTietCa): InfoItem[] {
  const full = detail.dinh_danh_day_du
  const missing = 'Chưa ghi nhận'
  const gender =
    full?.gioi_tinh === 'nam'
      ? 'Nam'
      : full?.gioi_tinh === 'nu'
        ? 'Nữ'
        : (detail.dinh_danh.gioi_tuoi.match(/(Nam|Nữ)/i)?.[1] ?? missing)
  const age =
    full?.tuoi != null ? `${full.tuoi} tuổi` : (detail.dinh_danh.gioi_tuoi.match(/\d+\s*tuổi/i)?.[0] ?? missing)
  const num = (value: number | null | undefined, unit: string) =>
    value != null ? `${String(value).replace('.', ',')} ${unit}` : missing
  return [
    { label: 'Họ tên', value: full?.ho_ten ? full.ho_ten.toUpperCase() : missing },
    { label: 'Giới tính', value: gender },
    { label: 'Tuổi', value: age },
    { label: 'Cân nặng', value: full ? num(full.can_nang_kg, 'kg') : detail.dinh_danh.can_nang },
    { label: 'Chiều cao', value: num(full?.chieu_cao_cm, 'cm') },
  ]
}

function patientInfoItems(detail: ChiTietCa): InfoItem[] {
  const { dinh_danh, tom_tat } = detail
  return [
    { label: 'Mã ca', value: detail.ca_id },
    ...patientFieldItems(detail),
    { label: 'Khoa, loại hồ sơ', value: dinh_danh.khoa_loai },
    {
      label: 'Vào viện',
      value: tom_tat.vao_vien_text ? formatClinicalText(tom_tat.vao_vien_text) : 'Chưa ghi nhận',
    },
    {
      label: 'Thời gian nằm viện',
      value: tom_tat.nam_vien_text ? formatClinicalText(tom_tat.nam_vien_text) : 'Không áp dụng',
    },
    { label: 'Dị ứng', value: parseLeadingSymbolLabel(dinh_danh.di_ung_text).text },
    { label: 'Chẩn đoán', value: primaryDiagnosis(detail), wide: true },
  ]
}

function MedicalRecordTabContent({
  detail,
  onOpenEvidence,
}: {
  detail: ChiTietCa
  onOpenEvidence: (target: EvidenceTarget, trigger: HTMLButtonElement) => void
}) {
  const { dinh_danh, tom_tat, chi_so } = detail

  const diagnosisSection = (
    <div className="flex flex-col gap-4">
      <InfoRows
        items={[
          { label: 'Chẩn đoán', value: primaryDiagnosis(detail), wide: true },
          {
            label: 'Dị ứng',
            value: parseLeadingSymbolLabel(dinh_danh.di_ung_text).text || 'Chưa ghi nhận',
          },
        ]}
      />
      <div className="flex flex-col gap-1.5">
        <span className="text-xs font-medium text-fg-subtle">Cơ địa đặc biệt</span>
        {tom_tat.co_dia.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {tom_tat.co_dia.map((item) => (
              <Badge key={item} tone="warning" variant="soft">
                {item}
              </Badge>
            ))}
          </div>
        ) : (
          <p className="text-sm text-fg-subtle">Không ghi nhận cơ địa đặc biệt.</p>
        )}
      </div>
    </div>
  )

  return (
    <div className="flex flex-col gap-7">
      <div className="flex flex-col gap-3">
        <AdministrativeSections
          identity={detail.dinh_danh_day_du}
          management={detail.quan_ly_nguoi_benh}
          history={detail.lich_su_vao_vien}
          diagnosisSection={diagnosisSection}
          legacy={
            detail.dinh_danh_day_du
              ? undefined
              : {
                  gioi_tuoi: dinh_danh.gioi_tuoi,
                  can_nang: dinh_danh.can_nang,
                  vao_vien: formatClinicalText(tom_tat.vao_vien_text),
                  nam_vien: tom_tat.nam_vien_text ? formatClinicalText(tom_tat.nam_vien_text) : null,
                  khoa: dinh_danh.khoa_loai,
                }
          }
        />
      </div>

      <section aria-label="Chỉ số lâm sàng" className="flex flex-col gap-2.5">
        <SectionHeading
          title="Chỉ số lâm sàng tính từ hồ sơ"
          aside="Tính bằng công thức, không do AI tính"
        />
        <MetricsTable
          metrics={chi_so}
          crclAbnormal={dinh_danh.crcl_bat_thuong}
          onOpenEvidence={onOpenEvidence}
        />
      </section>

      <section aria-label="Bất thường xét nghiệm" className="flex flex-col gap-2.5">
        <SectionHeading title="Giá trị cận lâm sàng ngoài ngưỡng" />
        {tom_tat.bat_thuong.length > 0 ? (
          <DataTable>
            <DataTableHeader>
              <tr>
                <DataTableHead>Xét nghiệm</DataTableHead>
                <DataTableHead align="right">Giá trị</DataTableHead>
                <DataTableHead>Đơn vị</DataTableHead>
                <DataTableHead>So với lần trước</DataTableHead>
                <DataTableHead>Thời điểm</DataTableHead>
              </tr>
            </DataTableHeader>
            <DataTableBody>
              {tom_tat.bat_thuong.map((bt, idx) => {
                const dir = parseTrendValue(bt.huong).direction
                const Arrow = dir === 'up' ? ArrowUp : dir === 'down' ? ArrowDown : null
                return (
                  <DataTableRow key={`${bt.ten}-${bt.thoi_diem_text}-${idx}`}>
                    <DataTableCell className="font-medium">{bt.ten}</DataTableCell>
                    <DataTableCell align="right" className="font-semibold text-danger-fg">
                      <span className="inline-flex items-center justify-end gap-1">
                        {Arrow ? (
                          <Arrow className="size-3.5" strokeWidth={2} aria-hidden="true" />
                        ) : null}
                        {formatClinicalText(bt.gia_tri_text)}
                      </span>
                    </DataTableCell>
                    <DataTableCell className="text-fg-subtle">
                      {formatClinicalText(bt.don_vi)}
                    </DataTableCell>
                    <DataTableCell className="text-fg-muted">
                      {bt.so_voi_truoc ? formatClinicalText(bt.so_voi_truoc) : '—'}
                    </DataTableCell>
                    <DataTableCell className="whitespace-nowrap tabular-nums">
                      {formatClinicalText(bt.thoi_diem_text)}
                    </DataTableCell>
                  </DataTableRow>
                )
              })}
            </DataTableBody>
          </DataTable>
        ) : (
          <p className="text-sm text-fg-subtle">
            {tom_tat.bat_thuong_ghi_chu
              ? formatClinicalText(tom_tat.bat_thuong_ghi_chu)
              : 'Không ghi nhận chỉ số bất thường.'}
          </p>
        )}
      </section>

      <section aria-label="Diễn biến gần nhất" className="flex flex-col gap-2.5">
        <SectionHeading title="Diễn biến gần nhất" />
        {tom_tat.dien_bien_moi_nhat ? (
          <NotesTable notes={[tom_tat.dien_bien_moi_nhat]} />
        ) : (
          <p className="text-sm text-fg-subtle">Chưa ghi nhận diễn biến mới nhất.</p>
        )}
      </section>
    </div>
  )
}

/** Màn hình chi tiết một y lệnh: thanh 7 thẻ dính trên cùng, nội dung gọn phẳng bên dưới. */
export function OrderDetailView({
  detail,
  orderSelectionReady = true,
  aiTrangThai,
  aiKetQua,
  aiThoiGianMs,
  aiCanhBao,
  aiCacBuoc,
  aiDaChayMs,
  aiThuongLeMs,
  sessionFeedbackForCase,
  onRerunAi,
  isFeedbackSubmitting,
  getFeedbackError,
  onSubmitFeedback,
  onClearFeedbackError,
  onOpenEvidence,
  onAskAboutFinding,
}: OrderDetailViewProps) {
  const [searchParams, setSearchParams] = useSearchParams()
  const { state: locationState } = useLocation()
  const [selectedDrug, setSelectedDrug] = useState<string | null>(null)
  const [passedOpenByScope, setPassedOpenByScope] = useState<Record<string, boolean>>({})
  const [interactionOpen, setInteractionOpen] = useState<boolean>(false)
  const [prevCaId, setPrevCaId] = useState<string>(detail.ca_id)
  const [rejectedOrderId, setRejectedOrderId] = useState<string | null>(null)
  const [feedbackDrafts, setFeedbackDrafts] = useState<Record<string, FeedbackDraft>>({})
  const [pendingScrollTarget, setPendingScrollTarget] = useState<{
    id: string
    factor: FactorIndex | null
  } | null>(null)
  const tabTriggerRefs = useRef<Partial<Record<OrderDetailTab, HTMLButtonElement | null>>>({})
  const requestedOrderId = searchParams.get('yl')
  const orders = useMemo(() => medicalOrders(detail), [detail])
  const selectedOrder = selectMedicalOrder(orders, requestedOrderId)
  const unmatchedOrderId = requestedOrderId !== null && selectedOrder?.y_lenh_id !== requestedOrderId
    ? requestedOrderId : null
  const invalidOrderId = orderSelectionReady ? unmatchedOrderId : null
  const noticeOrderId = invalidOrderId ?? (requestedOrderId === null ? rejectedOrderId : null)

  useEffect(() => {
    if (invalidOrderId === null) return
    setSearchParams((previous) => {
      const next = new URLSearchParams(previous)
      next.delete('yl')
      return next
    }, { replace: true, state: locationState })
  }, [invalidOrderId, locationState, setSearchParams])

  const clearSelectedDrug = () => setSelectedDrug(null)

  const handleSelectOrder = (id: string) => {
    clearSelectedDrug()
    setRejectedOrderId(null)
    setSearchParams((previous) => orderSelectionParams(previous, id), { replace: true, state: locationState })
  }

  if (prevCaId !== detail.ca_id) {
    setPrevCaId(detail.ca_id)
    setSelectedDrug(null)
    setPassedOpenByScope({})
    setRejectedOrderId(invalidOrderId)
    setFeedbackDrafts({})
    setPendingScrollTarget(null)
  } else if (invalidOrderId !== null && invalidOrderId !== rejectedOrderId) {
    setRejectedOrderId(invalidOrderId)
  } else if (invalidOrderId === null && requestedOrderId !== null && rejectedOrderId !== null) {
    setRejectedOrderId(null)
  }

  const activeTab = parseDetailTabParam(searchParams.get('tab'))
  const activeFactor = parseReviewFactorParam(searchParams.get('yt'))

  const updateFeedbackDraft = (id: string, draft: FeedbackDraft) => {
    setFeedbackDrafts((previous) => {
      if (draft.isEditing || draft.pendingAction !== null || draft.reasonGroup || draft.note) {
        return { ...previous, [id]: draft }
      }
      if (!(id in previous)) return previous
      const next = { ...previous }
      delete next[id]
      return next
    })
  }

  const handleTabChange = useCallback(
    (nextTab: string) => {
      const validTab = parseDetailTabParam(nextTab)
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          if (validTab === 'tham_dinh') {
            next.delete('tab')
          } else {
            next.set('tab', validTab)
          }
          return next
        },
        { replace: true, state: locationState },
      )
      requestAnimationFrame(() => {
        tabTriggerRefs.current[validTab]?.scrollIntoView({
          block: 'nearest',
          inline: 'nearest',
        })
      })
    },
    [locationState, setSearchParams],
  )

  const handleSelectReviewFactor = useCallback(
    (target: 'tong_quan' | FactorIndex) => {
      setSearchParams(
        (prev) => updateReviewFactorParams(prev, target),
        { replace: true, state: locationState },
      )
    },
    [locationState, setSearchParams],
  )

  const { allAttention, allPassed, sixFactors } = useReviewFindings({
    detail,
    aiTrangThai,
    aiKetQua,
    sessionFeedbackForCase,
  })

  const currentFactor =
    activeFactor === 'tong_quan'
      ? null
      : (sixFactors.find((factor) => factor.index === activeFactor) ?? null)

  const factorAttention = useMemo(
    () =>
      activeFactor === 'tong_quan'
        ? allAttention
        : allAttention.filter((item) => factorIndexOf(item.yeu_to) === activeFactor),
    [activeFactor, allAttention],
  )
  const factorPassed = useMemo(
    () =>
      activeFactor === 'tong_quan'
        ? allPassed
        : allPassed.filter((item) => factorIndexOf(item.yeu_to) === activeFactor),
    [activeFactor, allPassed],
  )

  const filteredAttention = useMemo(
    () => filterFindingsByDrug(factorAttention, selectedDrug),
    [factorAttention, selectedDrug],
  )
  const filteredPassed = useMemo(
    () => filterFindingsByDrug(factorPassed, selectedDrug),
    [factorPassed, selectedDrug],
  )

  const passedScopeKey = String(activeFactor)
  const defaultPassedOpen = activeFactor !== 'tong_quan' && factorAttention.length === 0
  const passedOpen = passedOpenByScope[passedScopeKey] ?? defaultPassedOpen
  const handlePassedOpenChange = useCallback(
    (nextOpen: boolean) => {
      setPassedOpenByScope((prev) => ({ ...prev, [passedScopeKey]: nextOpen }))
    },
    [passedScopeKey],
  )

  const treatmentSheetNotes = useMemo(
    () => filterTreatmentSheetNotes(detail.chi_tiet.dien_bien),
    [detail.chi_tiet.dien_bien],
  )

  const treatmentSheetCount = detail.phieu_dieu_tri?.length || treatmentSheetNotes.length

  const aiSummary = useMemo(() => countAiSummary(aiKetQua), [aiKetQua])
  const orderTimeText = useMemo(
    () => extractOrderTimeText(detail.chi_tiet.y_lenh.thong_tin_text),
    [detail.chi_tiet.y_lenh.thong_tin_text],
  )

  const handleSelectDrugForReview = useCallback(
    (drugName: string) => {
      setSelectedDrug((prev) =>
        prev && prev.toLowerCase() === drugName.toLowerCase() ? null : drugName,
      )
      setSearchParams(
        (prev) => {
          const next = updateReviewFactorParams(prev, 'tong_quan')
          next.delete('tab')
          return next
        },
        { replace: true, state: locationState },
      )
      requestAnimationFrame(() => {
        tabTriggerRefs.current.tham_dinh?.scrollIntoView({
          block: 'nearest',
          inline: 'nearest',
        })
      })
    },
    [locationState, setSearchParams],
  )

  const orderInfoItems = useMemo<InfoItem[]>(() => {
    const pairs = parseInfoPairs(formatClinicalText(detail.chi_tiet.y_lenh.thong_tin_text))
    const items: InfoItem[] = pairs
      .filter((pair) => pair.label)
      .map((pair) => ({ label: pair.label, value: pair.value }))
    items.push(
      ...patientFieldItems(detail),
      { label: 'Dị ứng', value: parseLeadingSymbolLabel(detail.dinh_danh.di_ung_text).text },
      {
        label: 'Kết quả thẩm định',
        value:
          allAttention.length > 0
            ? `${allAttention.length} mục cần chú ý`
            : 'Không có mục cần chú ý trong các luật đã chạy',
      },
      { label: 'Chẩn đoán', value: primaryDiagnosis(detail), wide: true },
    )
    return items
  }, [detail, allAttention.length])

  const handleOpenFinding = useCallback(
    (findingId: string) => {
      setSelectedDrug(null)
      const inPassed = allPassed.find((item) => item.nhan_dinh_id === findingId)
      const targetFinding =
        allAttention.find((item) => item.nhan_dinh_id === findingId) ?? inPassed ?? null
      const targetFactor = targetFinding ? factorIndexOf(targetFinding.yeu_to) : null

      if (inPassed) {
        const scopeKey =
          activeFactor === 'tong_quan'
            ? 'tong_quan'
            : String(targetFactor ?? activeFactor)
        setPassedOpenByScope((prev) => ({ ...prev, [scopeKey]: true }))
      }

      if (
        targetFactor !== null &&
        activeFactor !== 'tong_quan' &&
        activeFactor !== targetFactor
      ) {
        setSearchParams(
          (prev) => updateReviewFactorParams(prev, targetFactor),
          { replace: true, state: locationState },
        )
        setPendingScrollTarget({ id: findingId, factor: targetFactor })
        return
      }

      setPendingScrollTarget({ id: findingId, factor: null })
    },
    [activeFactor, allAttention, allPassed, locationState, setSearchParams],
  )

  useEffect(() => {
    if (!pendingScrollTarget) {
      return
    }
    if (
      pendingScrollTarget.factor !== null &&
      activeFactor !== 'tong_quan' &&
      activeFactor !== pendingScrollTarget.factor
    ) {
      return
    }
    const targetId = pendingScrollTarget.id
    let cancelled = false
    const raf = requestAnimationFrame(() => {
      if (cancelled) {
        return
      }
      document
        .getElementById(`finding-${targetId}`)
        ?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      setPendingScrollTarget(null)
    })
    return () => {
      cancelled = true
      cancelAnimationFrame(raf)
    }
  }, [pendingScrollTarget, activeFactor, passedOpenByScope])

  const selectedDrugFilterChip = selectedDrug ? (
    <div className="inline-flex items-center gap-1.5 rounded-sm border border-primary-line bg-primary-soft px-2.5 py-1 text-xs text-primary">
      <span>Đang lọc: {selectedDrug}</span>
      <button
        type="button"
        onClick={() => setSelectedDrug(null)}
        aria-label="Bỏ lọc theo thuốc"
        className="inline-flex cursor-pointer items-center gap-0.5 rounded-sm px-1 hover:bg-surface/60"
      >
        <X className="size-3" strokeWidth={1.75} aria-hidden="true" />
        <span>Bỏ lọc</span>
      </button>
    </div>
  ) : null

  const renderFindingCards = (includeOpenFactor: boolean) => (
    <div className="flex flex-col gap-3">
      {filteredAttention.map((finding) => {
        const factorIdx = includeOpenFactor ? factorIndexOf(finding.yeu_to) : null
        return (
          <FindingCard
            key={`${detail.ca_id}::${finding.nhan_dinh_id}`}
            caId={detail.ca_id}
            finding={finding}
            chiSo={detail.chi_so}
            nhomLyDo={detail.nhom_ly_do}
            submitting={isFeedbackSubmitting(detail.ca_id, finding.nhan_dinh_id)}
            feedbackError={getFeedbackError(detail.ca_id, finding.nhan_dinh_id)}
            feedbackDraft={feedbackDrafts[finding.nhan_dinh_id] ?? EMPTY_FEEDBACK_DRAFT}
            onFeedbackDraftChange={(draft) => updateFeedbackDraft(finding.nhan_dinh_id, draft)}
            onSubmitFeedback={onSubmitFeedback}
            onClearFeedbackError={onClearFeedbackError}
            onOpenEvidence={onOpenEvidence}
            onAskAboutFinding={onAskAboutFinding}
            onOpenFactor={
              factorIdx !== null ? () => handleSelectReviewFactor(factorIdx) : undefined
            }
          />
        )
      })}
    </div>
  )

  const hasSevereInFactor = factorAttention.some(
    (item) => item.muc_do_ma === 'nghiem_trong',
  )

  return (
    <Tabs value={activeTab} onValueChange={handleTabChange} className="detail-sticky-host flex flex-col">
      {/* 1. Thanh 7 thẻ dính ở mép trên cùng khi cuộn */}
      <div className="detail-sticky-bar">
        <div className="detail-sticky-inner">
          <div className="mx-auto w-full max-w-[1200px] px-5">
            <TabsList
              aria-label="Các thẻ hồ sơ bệnh án và thẩm định y lệnh"
              className="border-b-0 px-0 gap-3"
            >
              <TabsTrigger
                value="ho_so_benh_an"
                ref={(el) => {
                  tabTriggerRefs.current.ho_so_benh_an = el
                }}
              >
                Hồ sơ bệnh án
              </TabsTrigger>
              <TabsTrigger
                value="y_lenh"
                ref={(el) => {
                  tabTriggerRefs.current.y_lenh = el
                }}
              >
                Y lệnh ({countMedicalOrders(orders, detail.ca_id)})
              </TabsTrigger>
              <TabsTrigger
                value="phieu_dieu_tri"
                ref={(el) => {
                  tabTriggerRefs.current.phieu_dieu_tri = el
                }}
              >
                Phiếu điều trị ({treatmentSheetCount})
              </TabsTrigger>
              <TabsTrigger
                value="xet_nghiem"
                ref={(el) => {
                  tabTriggerRefs.current.xet_nghiem = el
                }}
              >
                Xét nghiệm ({detail.chi_tiet.xet_nghiem.length})
              </TabsTrigger>
              <TabsTrigger
                value="vi_sinh"
                ref={(el) => {
                  tabTriggerRefs.current.vi_sinh = el
                }}
              >
                Vi sinh ({detail.chi_tiet.vi_sinh.length})
              </TabsTrigger>
              <TabsTrigger
                value="dien_bien"
                ref={(el) => {
                  tabTriggerRefs.current.dien_bien = el
                }}
              >
                Diễn biến ({detail.chi_tiet.dien_bien.length})
              </TabsTrigger>
              <TabsTrigger
                value="tham_dinh"
                ref={(el) => {
                  tabTriggerRefs.current.tham_dinh = el
                }}
              >
                <span className="inline-flex items-center gap-1.5">
                  <span>Thẩm định</span>
                  <span className="font-mono text-2xs text-fg-subtle tabular-nums">
                    ({allAttention.length})
                  </span>
                </span>
              </TabsTrigger>
            </TabsList>
          </div>
        </div>
      </div>

      {/* 2. Nội dung từng thẻ đặt thẳng trên canvas rộng thoáng, không lồng khung dư thừa */}
      <div className="mx-auto w-full max-w-[1200px] px-5 py-5 flex flex-col gap-5">
        {!orderSelectionReady && unmatchedOrderId !== null ? (
          <p role="status" className="text-xs text-fg-muted">Đang đối chiếu y lệnh trong liên kết…</p>
        ) : noticeOrderId !== null ? (
          <p role="status" className="text-xs text-fg-muted">
            {noticeOrderId ? `Y lệnh ${noticeOrderId} không có trong danh sách.` : 'Mã y lệnh trong liên kết bị trống.'}
          </p>
        ) : null}
        <TabsContent value="ho_so_benh_an">
          <MedicalRecordTabContent detail={detail} onOpenEvidence={onOpenEvidence} />
        </TabsContent>

        <TabsContent value="y_lenh" className="flex flex-col gap-7">
          <OrderSelector orders={orders} selected={selectedOrder} detail={detail} onSelect={handleSelectOrder} />
          {selectedOrder?.la_trong_tam ? <>
          <section aria-label="Thông tin y lệnh" className="flex flex-col gap-2.5">
            <SectionHeading title="Thông tin y lệnh" />
            <InfoRows items={orderInfoItems} />
            <OrderExtraInfo order={selectedOrder} />
          </section>

          <section aria-label="Y lệnh chờ duyệt" className="flex flex-col gap-2.5">
            <SectionHeading
              title="Chi tiết y lệnh chờ duyệt"
              aside={`${detail.chi_tiet.y_lenh.cho_duyet.dong.length} dòng thuốc`}
            />
            <OrderLinesTable
              table={detail.chi_tiet.y_lenh.cho_duyet}
              selectedDrug={selectedDrug}
              onSelectDrug={handleSelectDrugForReview}
            />
            <p className="text-xs text-fg-subtle">
              Bấm một dòng thuốc để chuyển sang thẻ Thẩm định và lọc nhận định của thuốc đó. Rê chuột
              vào từng giờ trong lịch dùng để xem liều.
            </p>
          </section>

          {detail.chi_tiet.y_lenh.dang_dung ? (
            <section aria-label="Thuốc đang dùng và đã ngừng" className="flex flex-col gap-2.5">
              <SectionHeading
                title="Thuốc đang dùng và đã ngừng"
                aside={`${detail.chi_tiet.y_lenh.dang_dung.dong.length} dòng thuốc`}
              />
              <OrderLinesTable
                table={detail.chi_tiet.y_lenh.dang_dung}
                selectedDrug={selectedDrug}
                onSelectDrug={handleSelectDrugForReview}
              />
            </section>
          ) : null}
          </> : selectedOrder ? <SelectedOrderDetails order={selectedOrder} /> : (
            <EmptyBox icon={Pill} title="Chưa có y lệnh" description="Hồ sơ chưa có y lệnh để hiển thị." />
          )}
        </TabsContent>

        <TabsContent value="phieu_dieu_tri" className="flex flex-col gap-7">
          <section aria-label="Thông tin người bệnh" className="flex flex-col gap-2.5">
            <SectionHeading title="Thông tin điều trị" />
            <InfoRows items={patientInfoItems(detail)} />
          </section>
          <section aria-label="Phiếu điều trị" className="flex flex-col gap-2.5">
            <SectionHeading title="Phiếu điều trị" aside={`${treatmentSheetCount} phiếu`} />
            {detail.phieu_dieu_tri?.length ? <TreatmentSheets detail={detail} onFollowOrder={clearSelectedDrug} /> : treatmentSheetNotes.length > 0 ? (
              <NotesTable notes={treatmentSheetNotes} />
            ) : (
              <EmptyBox
                icon={ClipboardList}
                title="Chưa có phiếu điều trị"
                description="Hồ sơ ngoại trú hoặc ca bệnh này chưa có bản ghi phiếu điều trị."
              />
            )}
          </section>
        </TabsContent>

        <TabsContent value="xet_nghiem" className="flex flex-col gap-7">
          {detail.chi_tiet.xet_nghiem.length > 0 ? (
            <>
              <section aria-label="Bảng xét nghiệm" className="flex flex-col gap-2.5">
                <SectionHeading
                  title="Kết quả xét nghiệm"
                  aside="Ô nền đỏ: ngoài khoảng tham chiếu"
                />
                <LabPivotTable labs={detail.chi_tiet.xet_nghiem} />
              </section>
              <section aria-label="Diễn tiến xét nghiệm" className="flex flex-col gap-2.5">
                <SectionHeading title="Diễn tiến theo thời gian" />
                <LabTrendChart
                  xetNghiem={detail.chi_tiet.xet_nghiem}
                  orderTimeText={orderTimeText}
                />
              </section>
            </>
          ) : (
            <EmptyBox
              icon={FileText}
              title="Chưa có kết quả xét nghiệm"
              description="Ca bệnh này chưa ghi nhận dữ liệu xét nghiệm cận lâm sàng."
            />
          )}
        </TabsContent>

        <TabsContent value="vi_sinh">
          {detail.chi_tiet.vi_sinh.length > 0 ? (
            <div className="flex flex-col gap-3">
              {detail.chi_tiet.vi_sinh.map((vs, idx) => (
                <Card
                  key={`${vs.benh_pham}-${vs.lay_mau_text}-${idx}`}
                  className="flex flex-col gap-3 p-4"
                >
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-fg tabular-nums">
                    <span>
                      <span className="text-fg-subtle">Bệnh phẩm: </span>
                      <span className="font-medium text-fg">{vs.benh_pham}</span>
                    </span>
                    <span>
                      <span className="text-fg-subtle">Lấy mẫu: </span>
                      <span className="font-mono text-xs">
                        {formatClinicalText(vs.lay_mau_text)}
                      </span>
                    </span>
                    <span>
                      <span className="text-fg-subtle">Vi khuẩn: </span>
                      <span className="font-medium text-fg">
                        {vs.vi_khuan || 'Chưa phân lập vi khuẩn'}
                      </span>
                    </span>
                  </div>

                  {vs.khang_sinh_do.length > 0 ? (
                    <DataTable>
                      <DataTableHeader>
                        <tr>
                          <DataTableHead>Hoạt chất</DataTableHead>
                          <DataTableHead>Kết quả</DataTableHead>
                          <DataTableHead align="right">MIC</DataTableHead>
                          <DataTableHead>Đơn hiện tại</DataTableHead>
                        </tr>
                      </DataTableHeader>
                      <DataTableBody>
                        {vs.khang_sinh_do.map((ksd, kIdx) => (
                          <DataTableRow
                            key={`${ksd.hoat_chat}-${kIdx}`}
                            tone={ksd.dang_ke ? 'primary' : undefined}
                          >
                            <DataTableCell
                              className={ksd.dang_ke ? 'font-semibold text-fg' : undefined}
                            >
                              {ksd.hoat_chat}
                            </DataTableCell>
                            <DataTableCell className="font-mono">{ksd.ket_qua}</DataTableCell>
                            <DataTableCell align="right" className="font-mono">
                              {ksd.mic_text}
                            </DataTableCell>
                            <DataTableCell>
                              {ksd.dang_ke ? (
                                <Badge
                                  tone="neutral"
                                  variant="soft"
                                  icon={<Pill className="size-3.5" strokeWidth={1.75} />}
                                >
                                  Đang kê
                                </Badge>
                              ) : null}
                            </DataTableCell>
                          </DataTableRow>
                        ))}
                      </DataTableBody>
                    </DataTable>
                  ) : null}
                </Card>
              ))}
            </div>
          ) : (
            <div className="rounded-md border border-line bg-surface">
              <EmptyState
                icon={FileText}
                title="Chưa có kết quả vi sinh"
                description="Ca bệnh này chưa ghi nhận kết quả nuôi cấy vi sinh."
              />
            </div>
          )}
        </TabsContent>

        <TabsContent value="dien_bien">
          {detail.chi_tiet.dien_bien.length > 0 ? (
            <NotesTable notes={detail.chi_tiet.dien_bien} />
          ) : (
            <EmptyBox
              icon={FileText}
              title="Chưa có ghi nhận diễn biến"
              description="Ca bệnh này chưa có ghi chép diễn biến lâm sàng."
            />
          )}
        </TabsContent>

        <TabsContent value="tham_dinh" className="flex flex-col gap-5">
          {!currentFactor ? (
            <section aria-label="Nhận định thẩm định" className="flex flex-col gap-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-base font-semibold tracking-tight text-fg">Nhận định</h2>
                  <Badge
                    tone={filteredAttention.length > 0 ? 'neutral' : 'success'}
                    variant="soft"
                    className="border-transparent tabular-nums"
                  >
                    {filteredAttention.length} mục cần chú ý
                  </Badge>
                </div>

                {selectedDrugFilterChip}
              </div>

              <AiStatusBar
                trangThai={aiTrangThai}
                thoiGianMs={aiThoiGianMs}
                coDienGiai={aiSummary.coDienGiai}
                doAiThem={aiSummary.doAiThem}
                canhBao={aiCanhBao}
                onRerun={onRerunAi}
                cacBuoc={aiCacBuoc}
                daChayMs={aiDaChayMs}
                thuongLeMs={aiThuongLeMs}
              />

              {Object.entries(feedbackDrafts).filter(([id]) =>
                !allAttention.some((finding) => finding.nhan_dinh_id === id),
              ).map(([id, draft]) => (
                <InlineAlert key={id} tone="neutral" title="Bản nháp phản hồi">
                  <div className="flex flex-col gap-1.5">
                    <p>Nhận định đã thay đổi. Bản nháp của bạn vẫn còn.</p>
                    {draft.reasonGroup ? <p>{draft.reasonGroup}</p> : null}
                    {draft.note ? <p className="whitespace-pre-wrap break-words">{draft.note}</p> : null}
                    <Button variant="ghost" size="sm" className="self-start"
                      onClick={() => updateFeedbackDraft(id, EMPTY_FEEDBACK_DRAFT)}>Xóa bản nháp</Button>
                  </div>
                </InlineAlert>
              ))}

              {filteredAttention.length === 0 ? (
                <InlineAlert tone="success">
                  {selectedDrug
                    ? `Không có nhận định cần chú ý cho ${selectedDrug}.`
                    : `Không có mục cần chú ý trong phạm vi ${detail.nhan_dinh.so_luat_da_chay} luật đã chạy.`}
                </InlineAlert>
              ) : (
                renderFindingCards(true)
              )}

              <PassedList
                key={`passed-${detail.ca_id}-tong_quan`}
                passed={filteredPassed}
                open={passedOpen}
                onOpenChange={handlePassedOpenChange}
              />
            </section>
          ) : (
            <>
              <section
                aria-label={`${currentFactor.index}. ${currentFactor.title}`}
                className="flex flex-col gap-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-base font-semibold tracking-tight text-fg">
                      {currentFactor.index}. {currentFactor.title}
                    </h2>
                    <Badge
                      tone={factorStatusTone(currentFactor.status, hasSevereInFactor)}
                      variant="soft"
                      icon={<FactorStatusIcon status={currentFactor.status} />}
                    >
                      {currentFactor.statusLabel}
                    </Badge>
                    {filteredAttention.length > 0 ? (
                      <Badge
                        tone="neutral"
                        variant="soft"
                        className="border-transparent tabular-nums"
                      >
                        {filteredAttention.length} mục cần chú ý
                      </Badge>
                    ) : null}
                  </div>

                  {selectedDrugFilterChip}
                </div>

                {currentFactor.status === 'chua_co_luat' ? (
                  <EmptyBox
                    icon={MinusCircle}
                    title="Chưa có luật cho yếu tố này"
                    description="Hệ thống chưa có quy tắc kiểm tra tự động cho yếu tố này."
                  />
                ) : (
                  <>
                    {filteredAttention.length === 0 ? (
                      <InlineAlert tone="success">
                        {selectedDrug
                          ? `Không có nhận định cần chú ý cho ${selectedDrug} ở yếu tố ${currentFactor.index} (${currentFactor.title}).`
                          : `Không có mục cần chú ý ở yếu tố ${currentFactor.index} (${currentFactor.title}) trong phạm vi ${detail.nhan_dinh.so_luat_da_chay} luật đã chạy.`}
                      </InlineAlert>
                    ) : (
                      renderFindingCards(false)
                    )}

                    <PassedList
                      key={`passed-${detail.ca_id}-${currentFactor.index}`}
                      passed={filteredPassed}
                      open={passedOpen}
                      onOpenChange={handlePassedOpenChange}
                    />
                  </>
                )}
              </section>

              {currentFactor.index === 4 ? (
                <section
                  id="interaction-section"
                  aria-label="Tương tác thuốc"
                  className="flex flex-col gap-2.5"
                >
                  <InteractionSection
                    open={interactionOpen}
                    onOpenChange={setInteractionOpen}
                    choDuyet={detail.chi_tiet.y_lenh.cho_duyet}
                    dangDung={detail.chi_tiet.y_lenh.dang_dung}
                    maTranTuongTac={detail.ma_tran_tuong_tac}
                    nhanDinh={{
                      can_chu_y: allAttention,
                      dat: allPassed,
                      yeu_to_chua_kiem: detail.nhan_dinh.yeu_to_chua_kiem,
                    }}
                    onOpenFinding={handleOpenFinding}
                  />
                </section>
              ) : null}
            </>
          )}
        </TabsContent>
      </div>
    </Tabs>
  )
}
