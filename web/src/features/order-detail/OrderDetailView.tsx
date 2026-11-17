import { ArrowDown, ArrowUp, Pill, TriangleAlert, X } from 'lucide-react'
import { useCallback, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import type {
  BangYLenh,
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
import { InlineAlert } from '@/components/ui/inline-alert'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { LabTrendChart } from '@/features/charts/LabTrendChart'
import { AiStatusBar } from '@/features/findings/AiStatusBar'
import { FindingCard } from '@/features/findings/FindingCard'
import { PassedList } from '@/features/findings/PassedList'
import { countAiSummary, mergeFindingsFeedback, selectFindingsSource } from '@/lib/aiReview'
import { cn } from '@/lib/cn'
import {
  extractOrderTimeText,
  extractOrderCode,
  formatClinicalText,
  parseLeadingSymbolLabel,
  parseTrendValue,
} from '@/lib/displayFormat'
import {
  computeSixFactorsStatus,
  filterFindingsByDrug,
} from '@/lib/orderDetail'
import type { SixFactorItem } from '@/lib/orderDetail'
import { sortAttentionFindings } from '@/lib/presentation'
import { ICON_OF_TONE } from '@/lib/severity'
import type { EvidenceTarget } from '@/lib/uiTypes'
import { OrderHeaderStrip } from './OrderHeaderStrip'
import { SixFactorStrip } from './SixFactorStrip'

export type OrderDetailTab = 'tham_dinh' | 'xet_nghiem' | 'vi_sinh' | 'dien_bien'

const VALID_TABS = new Set<OrderDetailTab>(['tham_dinh', 'xet_nghiem', 'vi_sinh', 'dien_bien'])

export interface OrderDetailViewProps {
  detail: ChiTietCa
  aiTrangThai: TrangThaiAI
  aiKetQua: KetQuaAI | null
  aiThoiGianMs: number | null
  aiCanhBao: readonly string[]
  sessionFeedbackForCase: Readonly<Record<string, PhanHoiDaGhi>>
  canPrev: boolean
  canNext: boolean
  onBackToList: () => void
  onPrevOrder: () => void
  onNextOrder: () => void
  onRerunAi: () => void
  isFeedbackSubmitting: (caId: string, id: string) => boolean
  getFeedbackError: (caId: string, id: string) => string | null
  onSubmitFeedback: (caId: string, payload: GuiPhanHoi) => Promise<boolean>
  onClearFeedbackError: (caId: string, id: string) => void
  onOpenEvidence: (target: EvidenceTarget, trigger: HTMLButtonElement) => void
  onAskAboutFinding: (finding: NhanDinh) => void
}

function SelectableOrderTable({
  table,
  selectedDrug,
  onToggleDrug,
}: {
  table: BangYLenh
  selectedDrug: string | null
  onToggleDrug?: (drugName: string) => void
}) {
  if (table.dong.length === 0) {
    return <p className="text-sm text-fg-subtle">Không có dòng thuốc.</p>
  }

  return (
    <DataTable>
      <DataTableHeader>
        <tr>
          {table.cot.map((col) => (
            <DataTableHead key={col}>
              {col === 'Nhận định' ? 'Kết quả' : col}
            </DataTableHead>
          ))}
        </tr>
      </DataTableHeader>
      <DataTableBody>
        {table.dong.map((row, rowIdx) => {
          const drugName = row['Thuốc'] ?? ''
          const isSelected = Boolean(
            selectedDrug && drugName && selectedDrug.toLowerCase() === drugName.toLowerCase(),
          )
          const hasFinding = Boolean(row['Nhận định'] && row['Nhận định'].trim() !== '')
          const clickable = Boolean(onToggleDrug && drugName)

          return (
            <DataTableRow
              key={`order-row-${rowIdx}`}
              tone={isSelected ? 'primary' : undefined}
              onClick={clickable && onToggleDrug ? () => onToggleDrug(drugName) : undefined}
              tabIndex={clickable ? 0 : undefined}
              aria-selected={clickable ? isSelected : undefined}
              onKeyDown={
                clickable && onToggleDrug
                  ? (e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        onToggleDrug(drugName)
                      }
                    }
                  : undefined
              }
              className={cn(
                clickable && 'cursor-pointer',
                isSelected && 'ring-1 ring-inset ring-primary-line',
              )}
            >
              {table.cot.map((col) => {
                const cell = row[col] ?? '—'
                if (col === 'Nhận định') {
                  if (!hasFinding) {
                    return (
                      <DataTableCell key={col} className="text-xs text-fg-subtle">
                        Đạt
                      </DataTableCell>
                    )
                  }
                  const parsed = parseLeadingSymbolLabel(cell)
                  const ToneIcon = parsed.tone ? ICON_OF_TONE[parsed.tone] : TriangleAlert
                  return (
                    <DataTableCell key={col}>
                      <Badge
                        tone={parsed.tone ?? 'warning'}
                        variant="soft"
                        icon={<ToneIcon className="size-3.5" strokeWidth={1.75} />}
                      >
                        {parsed.text}
                      </Badge>
                    </DataTableCell>
                  )
                }

                return (
                  <DataTableCell
                    key={col}
                    className={cn(
                      'tabular-nums whitespace-pre-wrap',
                      col === 'Thuốc' && 'font-medium text-fg',
                    )}
                  >
                    {formatClinicalText(cell)}
                  </DataTableCell>
                )
              })}
            </DataTableRow>
          )
        })}
      </DataTableBody>
    </DataTable>
  )
}

/** Màn hình chi tiết một y lệnh: dải người bệnh dính trên, bảng y lệnh đứng trước nhận định, dải 6 yếu tố, biểu đồ xét nghiệm. */
export function OrderDetailView({
  detail,
  aiTrangThai,
  aiKetQua,
  aiThoiGianMs,
  aiCanhBao,
  sessionFeedbackForCase,
  canPrev,
  canNext,
  onBackToList,
  onPrevOrder,
  onNextOrder,
  onRerunAi,
  isFeedbackSubmitting,
  getFeedbackError,
  onSubmitFeedback,
  onClearFeedbackError,
  onOpenEvidence,
  onAskAboutFinding,
}: OrderDetailViewProps) {
  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedDrug, setSelectedDrug] = useState<string | null>(null)
  const [passedOpen, setPassedOpen] = useState<boolean>(false)
  const [prevCaId, setPrevCaId] = useState<string>(detail.ca_id)

  if (prevCaId !== detail.ca_id) {
    setPrevCaId(detail.ca_id)
    setSelectedDrug(null)
    setPassedOpen(false)
  }

  const rawTab = searchParams.get('tab') as OrderDetailTab | null
  const activeTab: OrderDetailTab =
    rawTab && VALID_TABS.has(rawTab) ? rawTab : 'tham_dinh'

  const handleTabChange = useCallback(
    (nextTab: string) => {
      const validTab: OrderDetailTab = VALID_TABS.has(nextTab as OrderDetailTab)
        ? (nextTab as OrderDetailTab)
        : 'tham_dinh'
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
        { replace: true },
      )
    },
    [setSearchParams],
  )

  const displayedFindings = useMemo(() => {
    const raw = selectFindingsSource(detail.nhan_dinh, aiTrangThai, aiKetQua)
    const fallbackSources =
      raw === detail.nhan_dinh
        ? aiKetQua?.nhan_dinh
          ? [aiKetQua.nhan_dinh]
          : []
        : [detail.nhan_dinh]
    return mergeFindingsFeedback(raw, sessionFeedbackForCase, fallbackSources)
  }, [detail, aiTrangThai, aiKetQua, sessionFeedbackForCase])

  const allAttention = useMemo(
    () => sortAttentionFindings(displayedFindings.can_chu_y),
    [displayedFindings],
  )
  const allPassed = displayedFindings.dat

  const filteredAttention = useMemo(
    () => filterFindingsByDrug(allAttention, selectedDrug),
    [allAttention, selectedDrug],
  )
  const filteredPassed = useMemo(
    () => filterFindingsByDrug(allPassed, selectedDrug),
    [allPassed, selectedDrug],
  )

  const sixFactors = useMemo(
    () =>
      computeSixFactorsStatus({
        can_chu_y: allAttention,
        dat: allPassed,
        yeu_to_chua_kiem: detail.nhan_dinh.yeu_to_chua_kiem,
      }),
    [allAttention, allPassed, detail.nhan_dinh.yeu_to_chua_kiem],
  )

  const aiSummary = useMemo(() => countAiSummary(aiKetQua), [aiKetQua])
  const orderTimeText = useMemo(
    () => extractOrderTimeText(detail.chi_tiet.y_lenh.thong_tin_text),
    [detail.chi_tiet.y_lenh.thong_tin_text],
  )

  const handleToggleDrug = useCallback((drugName: string) => {
    setSelectedDrug((prev) =>
      prev && prev.toLowerCase() === drugName.toLowerCase() ? null : drugName,
    )
  }, [])

  const handleSelectFactor = useCallback((factor: SixFactorItem) => {
    if (!factor.firstFindingId) {
      return
    }
    setSelectedDrug(null)
    if (factor.inPassedOnly) {
      setPassedOpen(true)
    }
    requestAnimationFrame(() => {
      const targetEl = document.getElementById(`finding-${factor.firstFindingId}`)
      if (targetEl) {
        targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' })
      } else if (factor.inPassedOnly) {
        document.getElementById('passed-findings-section')?.scrollIntoView({
          behavior: 'smooth',
          block: 'start',
        })
      }
    })
  }, [])

  return (
    <div className="flex flex-col">
      <OrderHeaderStrip
        orderCode={extractOrderCode(detail.chi_tiet.y_lenh.thong_tin_text, detail.ca_id)}
        dinhDanh={detail.dinh_danh}
        tomTat={detail.tom_tat}
        chiSo={detail.chi_so}
        canPrev={canPrev}
        canNext={canNext}
        onBackToList={onBackToList}
        onPrevOrder={onPrevOrder}
        onNextOrder={onNextOrder}
        onOpenEvidence={onOpenEvidence}
      />

      <div className="mx-auto w-full max-w-[960px] px-5 py-4 flex flex-col gap-4">
        <Tabs value={activeTab} onValueChange={handleTabChange}>
          <div className="rounded-md border border-line bg-surface">
            <TabsList aria-label="Các thẻ chi tiết y lệnh" className="flex-wrap gap-x-4 gap-y-0">
              <TabsTrigger value="tham_dinh">Thẩm định</TabsTrigger>
              <TabsTrigger value="xet_nghiem">
                Xét nghiệm ({detail.chi_tiet.xet_nghiem.length})
              </TabsTrigger>
              <TabsTrigger value="vi_sinh">
                Vi sinh ({detail.chi_tiet.vi_sinh.length})
              </TabsTrigger>
              <TabsTrigger value="dien_bien">
                Diễn biến ({detail.chi_tiet.dien_bien.length})
              </TabsTrigger>
            </TabsList>

            <TabsContent value="tham_dinh" className="p-4 flex flex-col gap-5">
              {/* 1. Bảng Y lệnh (đứng trước nhận định) */}
              <section aria-label="Y lệnh trong đơn" className="flex flex-col gap-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h2 className="text-md font-semibold text-fg">Y lệnh</h2>
                  <span className="font-mono text-xs text-fg-subtle tabular-nums">
                    {formatClinicalText(detail.chi_tiet.y_lenh.thong_tin_text)}
                  </span>
                </div>

                <SelectableOrderTable
                  table={detail.chi_tiet.y_lenh.cho_duyet}
                  selectedDrug={selectedDrug}
                  onToggleDrug={handleToggleDrug}
                />

                {selectedDrug ? (
                  <div className="flex items-center gap-2 text-xs text-primary">
                    <span>Đang lọc nhận định theo thuốc: {selectedDrug}</span>
                    <button
                      type="button"
                      onClick={() => setSelectedDrug(null)}
                      className="inline-flex cursor-pointer items-center gap-1 rounded-sm px-1.5 py-0.5 hover:bg-primary-soft"
                    >
                      <X className="size-3" strokeWidth={1.75} aria-hidden="true" />
                      <span>Bỏ lọc</span>
                    </button>
                  </div>
                ) : (
                  <p className="text-xs text-fg-subtle">
                    Bấm một dòng thuốc để lọc nhận định của thuốc đó.
                  </p>
                )}

                {detail.chi_tiet.y_lenh.dang_dung ? (
                  <div className="pt-2 flex flex-col gap-2">
                    <h3 className="text-sm font-semibold text-fg">Thuốc đang dùng và đã ngừng</h3>
                    <SelectableOrderTable
                      table={detail.chi_tiet.y_lenh.dang_dung}
                      selectedDrug={selectedDrug}
                      onToggleDrug={handleToggleDrug}
                    />
                  </div>
                ) : null}
              </section>

              {/* 2. Dải sáu yếu tố */}
              <section aria-label="Tổng quan sáu yếu tố" className="flex flex-col gap-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h2 className="text-md font-semibold text-fg">Sáu yếu tố thẩm định</h2>
                  <span className="text-xs text-fg-subtle tabular-nums">
                    {detail.nhan_dinh.so_luat_da_chay} luật đã chạy
                  </span>
                </div>
                <SixFactorStrip factors={sixFactors} onSelectFactor={handleSelectFactor} />
              </section>

              {/* 3. Dải trạng thái AI + Thẻ nhận định */}
              <div className="flex flex-col gap-3">
                <div className="flex flex-wrap items-center gap-2.5">
                  <h2 className="text-md font-semibold text-fg">Nhận định</h2>
                  <Badge
                    tone={filteredAttention.length > 0 ? 'neutral' : 'success'}
                    variant="soft"
                    className="tabular-nums"
                  >
                    {filteredAttention.length} mục cần chú ý
                  </Badge>
                </div>

                <AiStatusBar
                  trangThai={aiTrangThai}
                  thoiGianMs={aiThoiGianMs}
                  coDienGiai={aiSummary.coDienGiai}
                  doAiThem={aiSummary.doAiThem}
                  canhBao={aiCanhBao}
                  onRerun={onRerunAi}
                />

                {filteredAttention.length === 0 ? (
                  <InlineAlert tone="success">
                    {selectedDrug
                      ? `Không có nhận định cần chú ý cho ${selectedDrug}.`
                      : `Không có mục cần chú ý trong phạm vi ${detail.nhan_dinh.so_luat_da_chay} luật đã chạy.`}
                  </InlineAlert>
                ) : (
                  <div className="flex flex-col gap-3">
                    {filteredAttention.map((finding) => (
                      <FindingCard
                        key={`${detail.ca_id}::${finding.nhan_dinh_id}`}
                        caId={detail.ca_id}
                        finding={finding}
                        chiSo={detail.chi_so}
                        nhomLyDo={detail.nhom_ly_do}
                        submitting={isFeedbackSubmitting(detail.ca_id, finding.nhan_dinh_id)}
                        feedbackError={getFeedbackError(detail.ca_id, finding.nhan_dinh_id)}
                        onSubmitFeedback={onSubmitFeedback}
                        onClearFeedbackError={onClearFeedbackError}
                        onOpenEvidence={onOpenEvidence}
                        onAskAboutFinding={onAskAboutFinding}
                      />
                    ))}
                  </div>
                )}

                {/* 4. Mục đạt thu gọn ở cuối */}
                <PassedList
                  key={`passed-${detail.ca_id}`}
                  passed={filteredPassed}
                  open={passedOpen}
                  onOpenChange={setPassedOpen}
                />
              </div>
            </TabsContent>

            <TabsContent value="xet_nghiem" className="p-4">
              {detail.chi_tiet.xet_nghiem.length > 0 ? (
                <>
                  <LabTrendChart
                    xetNghiem={detail.chi_tiet.xet_nghiem}
                    orderTimeText={orderTimeText}
                  />

                  <DataTable>
                    <DataTableHeader>
                      <tr>
                        <DataTableHead>Thời điểm</DataTableHead>
                        <DataTableHead>Xét nghiệm</DataTableHead>
                        <DataTableHead align="right">Giá trị</DataTableHead>
                        <DataTableHead>Đơn vị</DataTableHead>
                        <DataTableHead>Khoảng tham chiếu</DataTableHead>
                        <DataTableHead>Bất thường</DataTableHead>
                      </tr>
                    </DataTableHeader>
                    <DataTableBody>
                      {detail.chi_tiet.xet_nghiem.map((xn, idx) => {
                        const parsedValue = parseTrendValue(xn.gia_tri_text)
                        const parsedDir = parseTrendValue(xn.huong ?? '')
                        const direction = parsedDir.direction ?? parsedValue.direction
                        const ArrowIcon =
                          direction === 'up'
                            ? ArrowUp
                            : direction === 'down'
                              ? ArrowDown
                              : undefined

                        return (
                          <DataTableRow
                            key={`${xn.ten}-${xn.thoi_diem_text}-${idx}`}
                            tone={xn.ngoai_nguong ? 'danger' : undefined}
                          >
                            <DataTableCell className="font-mono text-xs tabular-nums whitespace-nowrap">
                              {formatClinicalText(xn.thoi_diem_text)}
                            </DataTableCell>
                            <DataTableCell>{xn.ten}</DataTableCell>
                            <DataTableCell
                              align="right"
                              className={cn(
                                'font-mono',
                                xn.ngoai_nguong ? 'font-semibold text-danger-fg' : undefined,
                              )}
                            >
                              {formatClinicalText(parsedValue.text)}
                            </DataTableCell>
                            <DataTableCell className="text-fg-subtle">
                              {formatClinicalText(xn.don_vi)}
                            </DataTableCell>
                            <DataTableCell className="font-mono text-xs tabular-nums">
                              {formatClinicalText(xn.khoang_tham_chieu)}
                            </DataTableCell>
                            <DataTableCell>
                              {xn.ngoai_nguong ? (
                                <Badge
                                  tone="danger"
                                  variant="soft"
                                  icon={
                                    ArrowIcon ? (
                                      <ArrowIcon className="size-3.5" strokeWidth={1.75} />
                                    ) : undefined
                                  }
                                >
                                  Ngoài ngưỡng
                                  {direction === 'up' ? ' (tăng)' : direction === 'down' ? ' (giảm)' : ''}
                                </Badge>
                              ) : null}
                            </DataTableCell>
                          </DataTableRow>
                        )
                      })}
                    </DataTableBody>
                  </DataTable>
                </>
              ) : (
                <p className="text-sm text-fg-subtle">Chưa có kết quả xét nghiệm.</p>
              )}
            </TabsContent>

            <TabsContent value="vi_sinh" className="p-4">
              {detail.chi_tiet.vi_sinh.length > 0 ? (
                <div className="flex flex-col gap-3">
                  {detail.chi_tiet.vi_sinh.map((vs, idx) => (
                    <Card
                      key={`${vs.benh_pham}-${vs.lay_mau_text}-${idx}`}
                      className="p-3.5 flex flex-col gap-3"
                    >
                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-fg tabular-nums">
                        <span>
                          <span className="text-fg-subtle">Bệnh phẩm: </span>
                          <span className="font-medium text-fg">{vs.benh_pham}</span>
                        </span>
                        <span>
                          <span className="text-fg-subtle">Lấy mẫu: </span>
                          <span className="font-mono text-xs">{formatClinicalText(vs.lay_mau_text)}</span>
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
                <p className="text-sm text-fg-subtle">Chưa có kết quả vi sinh.</p>
              )}
            </TabsContent>

            <TabsContent value="dien_bien" className="p-4">
              {detail.chi_tiet.dien_bien.length > 0 ? (
                <div className="flex flex-col gap-3">
                  {detail.chi_tiet.dien_bien.map((db, idx) => (
                    <div
                      key={`${db.thoi_diem_text}-${idx}`}
                      className="flex flex-col gap-1.5 pb-3 border-b border-line last:border-b-0 last:pb-0"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-xs text-fg-subtle tabular-nums">
                          {formatClinicalText(db.thoi_diem_text)}
                        </span>
                        <Badge tone="neutral" variant="soft">
                          {db.loai_nhan}
                        </Badge>
                      </div>
                      <p className="whitespace-pre-wrap text-sm text-fg leading-relaxed">
                        {formatClinicalText(db.noi_dung)}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-fg-subtle">Chưa có ghi nhận diễn biến.</p>
              )}
            </TabsContent>
          </div>
        </Tabs>
      </div>
    </div>
  )
}
