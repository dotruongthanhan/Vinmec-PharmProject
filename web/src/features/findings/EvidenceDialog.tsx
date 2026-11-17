import { ExternalLink, ShieldCheck } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { ReviewApiClient } from '@/api/client'
import type { BanGhi, DoanNguon } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  DataTable,
  DataTableBody,
  DataTableCell,
  DataTableHead,
  DataTableHeader,
  DataTableRow,
} from '@/components/ui/data-table'
import {
  Dialog,
  DialogBody,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { InlineAlert } from '@/components/ui/inline-alert'
import { RecordId } from '@/components/ui/record-id'
import { Skeleton } from '@/components/ui/skeleton'
import { getSafeHttpsUrl, splitHighlightSegments } from '@/lib/aiReview'
import { formatClinicalText } from '@/lib/displayFormat'
import type { EvidenceTarget } from '@/lib/uiTypes'

export interface EvidenceDialogProps {
  target: EvidenceTarget | null
  client: ReviewApiClient
  returnFocusEl: HTMLElement | null
  onClose: () => void
}

type AsyncDialogResult =
  | { key: string; kind: 'record'; data: BanGhi; error: null }
  | { key: string; kind: 'source'; data: DoanNguon; error: null }
  | { key: string; kind: 'error'; data: null; error: string }

function buildFetchKey(target: EvidenceTarget | null, reloadTick: number): string | null {
  if (!target) {
    return null
  }
  if (target.kind === 'record') {
    return `record::${target.caId}::${target.banGhiId}::${reloadTick}`
  }
  if (target.kind === 'source') {
    return `source::${target.caId}::${target.doanTrichId}::${reloadTick}`
  }
  return null
}

function getDialogSubtitle(target: EvidenceTarget | null): string {
  switch (target?.kind) {
    case 'record':
      return 'Chi tiết bản ghi từ hồ sơ người bệnh'
    case 'source':
      return 'Đoạn trích nguyên văn từ tài liệu tham khảo'
    case 'metric':
      return 'Đầu vào, kết quả và nguồn công thức tính'
    case 'document':
      return 'Thông tin tài liệu tham chiếu'
    default:
      return ''
  }
}

/** Hộp thoại Radix xem căn cứ dữ liệu ca, phép tính chỉ số, tài liệu hoặc đoạn nguồn AI. */
export function EvidenceDialog({
  target,
  client,
  returnFocusEl,
  onClose,
}: EvidenceDialogProps) {
  const [asyncResult, setAsyncResult] = useState<AsyncDialogResult | null>(null)
  const [reloadTick, setReloadTick] = useState<number>(0)
  const lastReturnFocusElRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (returnFocusEl) {
      lastReturnFocusElRef.current = returnFocusEl
    }
  }, [returnFocusEl])

  const activeKey = buildFetchKey(target, reloadTick)

  useEffect(() => {
    if (!target || !activeKey || (target.kind !== 'record' && target.kind !== 'source')) {
      return
    }

    let cancelled = false

    if (target.kind === 'record') {
      client
        .getRecord(target.caId, target.banGhiId)
        .then((res) => {
          if (!cancelled) {
            setAsyncResult({ key: activeKey, kind: 'record', data: res, error: null })
          }
        })
        .catch((err: unknown) => {
          if (!cancelled) {
            const message =
              err instanceof Error && err.message ? err.message : 'Không tải được bản ghi căn cứ.'
            setAsyncResult({ key: activeKey, kind: 'error', data: null, error: message })
          }
        })
    } else {
      client
        .getSource(target.caId, target.doanTrichId)
        .then((res) => {
          if (!cancelled) {
            setAsyncResult({ key: activeKey, kind: 'source', data: res, error: null })
          }
        })
        .catch((err: unknown) => {
          if (!cancelled) {
            const message =
              err instanceof Error && err.message
                ? err.message
                : 'Không tải được đoạn nguồn tài liệu.'
            setAsyncResult({ key: activeKey, kind: 'error', data: null, error: message })
          }
        })
    }

    return () => {
      cancelled = true
    }
  }, [client, target, activeKey])

  const matchingResult =
    activeKey !== null && asyncResult?.key === activeKey ? asyncResult : null
  const loading = activeKey !== null && matchingResult === null
  const error = matchingResult?.kind === 'error' ? matchingResult.error : null
  const record = matchingResult?.kind === 'record' ? matchingResult.data : null
  const source = matchingResult?.kind === 'source' ? matchingResult.data : null

  const safeSourceUrl = source ? getSafeHttpsUrl(source.url_goc) : null
  const subtitle = getDialogSubtitle(target)

  return (
    <Dialog
      open={target !== null}
      onOpenChange={(open) => {
        if (!open) {
          setAsyncResult(null)
          onClose()
        }
      }}
    >
      <DialogContent
        variant={target?.kind === 'source' ? 'source' : 'record'}
        tabIndex={-1}
        onOpenAutoFocus={(e) => {
          e.preventDefault()
          if (e.currentTarget instanceof HTMLElement) {
            e.currentTarget.focus()
          }
        }}
        onCloseAutoFocus={(e) => {
          const el = returnFocusEl ?? lastReturnFocusElRef.current
          lastReturnFocusElRef.current = null
          if (el && el.isConnected) {
            e.preventDefault()
            el.focus()
          }
        }}
      >
        <DialogHeader>
          <DialogTitle>Căn cứ thẩm định</DialogTitle>
          <DialogDescription>{subtitle}</DialogDescription>
        </DialogHeader>

        <DialogBody className="flex flex-col gap-4">
          {target?.kind === 'record' ? (
            <>
              {loading ? (
                <div className="flex flex-col gap-3" role="status" aria-label="Đang tải bản ghi">
                  <Skeleton className="h-5 w-2/3" />
                  <Skeleton className="h-4 w-1/3" />
                  <Skeleton className="h-36 w-full" />
                </div>
              ) : null}

              {!loading && error ? (
                <InlineAlert
                  tone="danger"
                  role="alert"
                  title="Không tải được bản ghi căn cứ"
                  action={
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => setReloadTick((n) => n + 1)}
                    >
                      Thử lại
                    </Button>
                  }
                >
                  <p>{error}</p>
                  <p className="mt-1 text-xs text-fg-muted">{target.titleHint}</p>
                </InlineAlert>
              ) : null}

              {!loading && !error && record ? (
                <>
                  <div className="flex flex-col gap-0.5">
                    <h3 className="text-md font-semibold text-fg">{record.tieu_de}</h3>
                    <p className="text-xs text-fg-muted">Loại bản ghi: {record.loai}</p>
                  </div>

                  <DataTable>
                    <DataTableBody>
                      {record.dong.map(([label, value], idx) => (
                        <DataTableRow key={`${label}-${idx}`}>
                          <DataTableCell className="w-[38%] font-medium text-fg-muted">
                            {label}
                          </DataTableCell>
                          <DataTableCell className="whitespace-pre-wrap tabular-nums">
                            {formatClinicalText(value)}
                          </DataTableCell>
                        </DataTableRow>
                      ))}
                    </DataTableBody>
                  </DataTable>
                </>
              ) : null}
            </>
          ) : null}

          {target?.kind === 'source' ? (
            <>
              {loading ? (
                <div className="flex flex-col gap-3" role="status" aria-label="Đang tải đoạn nguồn">
                  <Skeleton className="h-5 w-2/3" />
                  <Skeleton className="h-4 w-1/2" />
                  <Skeleton className="h-24 w-full" />
                  <Skeleton className="h-32 w-full" />
                </div>
              ) : null}

              {!loading && error ? (
                <InlineAlert
                  tone="danger"
                  role="alert"
                  title="Không tải được đoạn nguồn tài liệu"
                  action={
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => setReloadTick((n) => n + 1)}
                    >
                      Thử lại
                    </Button>
                  }
                >
                  <p>{error}</p>
                  <p className="mt-1 text-xs text-fg-muted">{target.nhan}</p>
                </InlineAlert>
              ) : null}

              {!loading && !error && source ? (
                <>
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <h3 className="text-md font-semibold text-fg">{source.nguon_nhan}</h3>
                      <p className="mt-0.5 text-xs text-fg-muted">{source.duong_dan_muc}</p>
                    </div>
                    <Badge
                      tone={source.tang_tin_cay === 1 ? 'success' : 'neutral'}
                      variant="soft"
                      className="shrink-0 tabular-nums"
                      icon={<ShieldCheck className="size-3.5" strokeWidth={1.75} />}
                    >
                      Tầng {source.tang_tin_cay}
                    </Badge>
                  </div>

                  <DataTable>
                    <DataTableBody>
                      <DataTableRow>
                        <DataTableCell className="w-[36%] font-medium text-fg-muted">
                          Tầng tin cậy
                        </DataTableCell>
                        <DataTableCell className="tabular-nums">
                          Tầng {source.tang_tin_cay}
                        </DataTableCell>
                      </DataTableRow>
                      <DataTableRow>
                        <DataTableCell className="w-[36%] font-medium text-fg-muted">
                          Phiên bản
                        </DataTableCell>
                        <DataTableCell>{source.phien_ban}</DataTableCell>
                      </DataTableRow>
                      {safeSourceUrl ? (
                        <DataTableRow>
                          <DataTableCell className="w-[36%] font-medium text-fg-muted">
                            Trang gốc
                          </DataTableCell>
                          <DataTableCell>
                            <a
                              href={safeSourceUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1.5 font-medium text-primary underline underline-offset-2 hover:text-primary-hover"
                            >
                              <span>Mở trang gốc</span>
                              <ExternalLink
                                className="size-3.5 shrink-0"
                                strokeWidth={1.75}
                                aria-hidden="true"
                              />
                            </a>
                          </DataTableCell>
                        </DataTableRow>
                      ) : null}
                    </DataTableBody>
                  </DataTable>

                  <div className="flex flex-col gap-1.5">
                    <div className="text-xs font-medium text-fg-muted">
                      Nguyên văn đoạn nguồn
                    </div>
                    <div className="rounded-md border border-line bg-surface-muted/50 p-3.5 text-sm leading-relaxed text-fg whitespace-pre-wrap">
                      {splitHighlightSegments(source.noi_dung, target.trichNguyenVan).map(
                        (seg, idx) =>
                          seg.highlighted ? (
                            <mark
                              key={`seg-${idx}`}
                              className="rounded-sm bg-warning-bg px-0.5 font-semibold text-fg"
                            >
                              {seg.text}
                            </mark>
                          ) : (
                            <span key={`seg-${idx}`}>{seg.text}</span>
                          ),
                      )}
                    </div>
                  </div>
                </>
              ) : null}
            </>
          ) : null}

          {target?.kind === 'metric' ? (
            <>
              <div className="flex flex-col gap-0.5">
                <h3 className="text-md font-semibold text-fg">{target.metric.nhan}</h3>
                <p className="text-sm text-fg-muted tabular-nums">
                  Kết quả:{' '}
                  <span className="font-semibold text-fg">{target.metric.gia_tri_text}</span>{' '}
                  {target.metric.don_vi}
                </p>
              </div>

              {target.metric.thieu.length > 0 ? (
                <InlineAlert tone="missing">
                  Thiếu đầu vào: {target.metric.thieu.join(', ')}
                </InlineAlert>
              ) : null}

              <div className="flex flex-col gap-1.5">
                <div className="text-xs font-medium text-fg-muted">Đầu vào sử dụng</div>
                {target.metric.dau_vao.length > 0 ? (
                  <DataTable>
                    <DataTableHeader>
                      <tr>
                        <DataTableHead>Đầu vào</DataTableHead>
                        <DataTableHead align="right">Giá trị</DataTableHead>
                        <DataTableHead>Thời điểm / Mã</DataTableHead>
                      </tr>
                    </DataTableHeader>
                    <DataTableBody>
                      {target.metric.dau_vao.map((inp, idx) => (
                        <DataTableRow key={`${inp.nhan}-${idx}`}>
                          <DataTableCell className="font-medium text-fg-muted">
                            {inp.nhan}
                          </DataTableCell>
                          <DataTableCell align="right" className="font-medium">
                            {formatClinicalText(`${inp.gia_tri_text} ${inp.don_vi}`.trim())}
                          </DataTableCell>
                          <DataTableCell className="text-xs text-fg-subtle tabular-nums">
                            <div className="flex flex-wrap items-center gap-1.5">
                              {inp.thoi_diem_text ? (
                                <span>{formatClinicalText(inp.thoi_diem_text)}</span>
                              ) : null}
                              {inp.ban_ghi_id ? <RecordId id={inp.ban_ghi_id} /> : null}
                              {!inp.thoi_diem_text && !inp.ban_ghi_id ? <span>—</span> : null}
                            </div>
                          </DataTableCell>
                        </DataTableRow>
                      ))}
                    </DataTableBody>
                  </DataTable>
                ) : (
                  <p className="text-xs text-fg-subtle">Không có đầu vào hợp lệ.</p>
                )}
              </div>

              {target.metric.ghi_chu.length > 0 ? (
                <div className="flex flex-col gap-1">
                  <div className="text-xs font-medium text-fg-muted">Ghi chú</div>
                  <ul className="flex list-disc flex-col gap-1 pl-4 text-sm text-fg">
                    {target.metric.ghi_chu.map((note, idx) => (
                      <li key={`dlg-note-${idx}`} className="whitespace-pre-wrap">
                        {formatClinicalText(note)}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <div className="flex flex-col gap-1 border-t border-line pt-3">
                <div className="text-xs font-medium text-fg-muted">
                  Trích dẫn bài báo / tài liệu
                </div>
                <p className="text-xs text-fg-subtle">{target.metric.tham_khao}</p>
                {target.titleHint ? (
                  <p className="text-xs text-fg-muted">Mô tả căn cứ: {target.titleHint}</p>
                ) : null}
              </div>
            </>
          ) : null}

          {target?.kind === 'document' ? (
            <div className="flex flex-col gap-3">
              <h3 className="text-md font-semibold text-fg">Căn cứ tài liệu</h3>
              <p className="text-sm leading-relaxed text-fg whitespace-pre-wrap">{target.moTa}</p>
              <InlineAlert tone="neutral">
                <span className="whitespace-pre-wrap">
                  {target.ghiChu ?? 'Nguyên văn đoạn nguồn sẽ có khi nối kho tri thức.'}
                </span>
              </InlineAlert>
            </div>
          ) : null}
        </DialogBody>

        <DialogFooter>
          <DialogClose asChild>
            <Button variant="secondary" size="md">
              Đóng
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
