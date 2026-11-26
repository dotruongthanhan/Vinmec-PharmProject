/** Bước 1 trong Side Panel: chọn tab EMR, kiểm chéo bệnh nhân, duyệt schema, cắt ảnh OH & audit PII. */

import {
  AlertOctagon,
  CheckCircle2,
  Eye,
  FileSearch,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import type { ExtensionApiClient } from '../api/extensionClient'
import { OhImageCropper, type CroppedOhImageValue } from '../components/OhImageCropper'
import { sanitizeTabsForUpload, scrubText } from '../lib/deidScrubber'
import { computeSchemaHash } from '../lib/domExtractor'
import { verifySamePatientAcrossTabs } from '../lib/patientGuard'
import {
  classifyLocalBaseline,
  foldVietnamese,
  loadCachedSchema,
  mergeWithPiiFloor,
  saveCachedSchema,
} from '../lib/schemaCache'
import type {
  BrowserTabSummary,
  ClassifiedField,
  DeidAuditSummary,
  EmrSectionPayload,
  ExtensionReviewResponse,
  PatientGuardResult,
  RawTabExtraction,
  SchemaGroup,
} from '../lib/types'

interface Props {
  client: ExtensionApiClient
  onReviewed: (res: ExtensionReviewResponse, restoreMap: Record<string, string>) => void
}

function sendWorkerMessage<T>(msg: unknown): Promise<T> {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(msg, (response) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message))
        return
      }
      if (!response?.ok) {
        reject(new Error(response?.error || 'Lỗi Service Worker'))
        return
      }
      resolve(response as T)
    })
  })
}

export function CapturePanel({ client, onReviewed }: Props) {
  const [tabs, setTabs] = useState<BrowserTabSummary[]>([])
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [ohImage, setOhImage] = useState<CroppedOhImageValue | null>(null)

  const [extractions, setExtractions] = useState<RawTabExtraction[]>([])
  const [patientGuard, setPatientGuard] = useState<PatientGuardResult | null>(null)
  const [pendingSchemaApproval, setPendingSchemaApproval] = useState<{
    schemaHash: string
    fields: ClassifiedField[]
  } | null>(null)
  const [sanitizedSections, setSanitizedSections] = useState<EmrSectionPayload[] | null>(null)
  const [auditSummary, setAuditSummary] = useState<DeidAuditSummary | null>(null)
  const [localRestoreMap, setLocalRestoreMap] = useState<Record<string, string>>({})

  const [showAuditPreview, setShowAuditPreview] = useState(false)
  const [busyStep, setBusyStep] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const refreshTabs = useCallback(async () => {
    setErrorMsg(null)
    try {
      const res = await sendWorkerMessage<{ ok: true; tabs: BrowserTabSummary[] }>({
        type: 'LIST_TABS',
      })
      setTabs(res.tabs)
      const candidates = res.tabs.filter((t) => t.isEmrCandidate).map((t) => t.id)
      setSelectedIds(candidates.length > 0 ? candidates : res.tabs.slice(0, 1).map((t) => t.id))
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Không đọc được danh sách tab.')
    }
  }, [])

  useEffect(() => {
    void refreshTabs()
  }, [refreshTabs])

  const finalizeSanitization = useCallback(
    (tabsData: RawTabExtraction[], approvedFields: ClassifiedField[]) => {
      const { sections, audit, restoreMap } = sanitizeTabsForUpload(tabsData, approvedFields)
      setSanitizedSections(sections)
      setAuditSummary(audit)
      setLocalRestoreMap(restoreMap)
    },
    [],
  )

  /** Đọc DOM đồng thời các tab đã chọn: yêu cầu host permission ĐỒNG BỘ trước khi await. */
  const handleReadTabs = () => {
    setErrorMsg(null)
    const chosenTabs = tabs.filter((t) => selectedIds.includes(t.id))
    if (chosenTabs.length === 0) {
      setErrorMsg('Hãy chọn ít nhất 1 tab EMR đang mở (hoặc dán ảnh bảng y lệnh OH).')
      return
    }
    const origins = Array.from(new Set(chosenTabs.map((t) => `${t.origin}/*`)))

    const proceedExtraction = async () => {
      setBusyStep('Đang đọc DOM các tab và kiểm tra tách PII...')
      try {
        const workerRes = await sendWorkerMessage<{
          ok: true
          extractions: RawTabExtraction[]
          errors: Array<{ tabId: number; reason: string }>
        }>({
          type: 'EXTRACT_TABS',
          tabIds: selectedIds,
        })
        if (workerRes.extractions.length === 0) {
          throw new Error(workerRes.errors[0]?.reason || 'Không đọc được nội dung tab.')
        }
        setExtractions(workerRes.extractions)

        const guard = await verifySamePatientAcrossTabs(workerRes.extractions)
        setPatientGuard(guard)
        if (guard.status === 'MISMATCH_BLOCKED') {
          setSanitizedSections(null)
          setAuditSummary(null)
          setPendingSchemaApproval(null)
          return
        }

        // Giai đoạn 0b: hợp nhất & khử trùng lặp nhãn sạch (loại bỏ tiêu đề cột ngày/giờ hoặc chuỗi chứa PII).
        const dedupMap = new Map<string, (typeof workerRes.extractions)[0]['uniqueFields'][0]>()
        for (const tab of workerRes.extractions) {
          for (const field of tab.uniqueFields) {
            const label = field.ten_nhan.trim().slice(0, 80)
            if (!label || scrubText(label).thay_the.length > 0) continue
            const key = foldVietnamese(label)
            if (!dedupMap.has(key)) {
              dedupMap.set(key, {
                ten_nhan: label,
                kieu_dom: field.kieu_dom.slice(0, 40),
                ngu_canh_muc: field.ngu_canh_muc ? field.ngu_canh_muc.slice(0, 120) : null,
              })
            }
          }
        }
        const allLabels = Array.from(dedupMap.values())
        const combinedHash = computeSchemaHash(
          workerRes.extractions[0].origin,
          allLabels.map((f) => f.ten_nhan),
        )

        if (allLabels.length === 0) {
          finalizeSanitization(workerRes.extractions, [])
          setPendingSchemaApproval(null)
          return
        }

        const cached = await loadCachedSchema(combinedHash)
        if (cached) {
          const merged = mergeWithPiiFloor(allLabels, cached.fields)
          finalizeSanitization(workerRes.extractions, merged)
          setPendingSchemaApproval(null)
          return
        }

        // Chưa có trong bộ đệm -> gọi Gemini 3.5 Flash Lite phân loại CHỈ TÊN NHÃN.
        let classified: ClassifiedField[]
        try {
          const remote = await client.classifySchema(
            combinedHash,
            allLabels.slice(0, 120),
            workerRes.extractions[0].origin,
          )
          classified = mergeWithPiiFloor(allLabels, remote.fields)
        } catch {
          classified = classifyLocalBaseline(allLabels)
        }
        setPendingSchemaApproval({ schemaHash: combinedHash, fields: classified })
        finalizeSanitization(workerRes.extractions, classified)
      } catch (err) {
        setErrorMsg(err instanceof Error ? err.message : 'Lỗi khi trích xuất tab.')
      } finally {
        setBusyStep(null)
      }
    }

    if (typeof chrome !== 'undefined' && chrome.permissions?.request) {
      // QUY TẮC MV3: gọi request() đồng bộ trong sự kiện click, KHÔNG await trước nó!
      chrome.permissions.request({ origins }, (granted) => {
        if (!granted) {
          setErrorMsg('Trình duyệt chưa được cấp quyền đọc các tab đã chọn.')
          return
        }
        void proceedExtraction()
      })
    } else {
      void proceedExtraction()
    }
  }

  const updateSchemaFieldGroup = (idx: number, nextGroup: SchemaGroup) => {
    if (!pendingSchemaApproval) return
    const updated = pendingSchemaApproval.fields.map((item, i) =>
      i === idx ? { ...item, nhom: nextGroup } : item,
    )
    setPendingSchemaApproval({ ...pendingSchemaApproval, fields: updated })
    finalizeSanitization(extractions, updated)
  }

  const approveSchemaTemplate = async () => {
    if (!pendingSchemaApproval) return
    await saveCachedSchema(pendingSchemaApproval.schemaHash, pendingSchemaApproval.fields)
    setPendingSchemaApproval(null)
  }

  const handleRunReview = async () => {
    setErrorMsg(null)
    if (patientGuard?.status === 'MISMATCH_BLOCKED') {
      setErrorMsg('Đang bị chặn vì các tab thuộc hai người bệnh khác nhau.')
      return
    }
    if (ohImage && !ohImage.confirmedNoPii) {
      setErrorMsg('Vui lòng tích xác nhận ảnh OH đã cắt bỏ thông tin hành chính.')
      return
    }

    const sectionsToSend =
      sanitizedSections && sanitizedSections.length > 0
        ? sanitizedSections
        : [
            {
              tieu_de: 'Y lệnh từ ảnh chụp OH',
              loai_muc: 'meds_notes' as const,
              noi_dung: 'Người bệnh gửi kèm ảnh chụp bảng y lệnh OH chờ duyệt.',
            },
          ]

    setBusyStep('Đang chạy 4 luồng Gemini song song + 14 công thức & 14 luật...')
    try {
      const payload: {
        schema_hash?: string
        tab_count: number
        source_domains: string[]
        sections: EmrSectionPayload[]
      } = {
        schema_hash: extractions[0]?.schemaHash,
        tab_count: Math.max(1, extractions.length),
        source_domains: Array.from(new Set(extractions.map((e) => e.origin))),
        sections: sectionsToSend,
      }
      const res = await client.extractAndReview(
        payload,
        ohImage ? { blob: ohImage.blob, confirmedNoPii: ohImage.confirmedNoPii } : null,
      )
      onReviewed(res, localRestoreMap)
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Lỗi khi thẩm định y lệnh.')
    } finally {
      setBusyStep(null)
    }
  }

  const canSubmit =
    !busyStep &&
    patientGuard?.status !== 'MISMATCH_BLOCKED' &&
    !pendingSchemaApproval &&
    (Boolean(sanitizedSections?.length) || Boolean(ohImage)) &&
    (!ohImage || ohImage.confirmedNoPii)

  return (
    <div className="space-y-3">
      {/* 1. Chọn tab EMR đang mở */}
      <section className="rounded-lg border border-slate-200 bg-white p-3">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-xs font-semibold text-slate-800">1. Chọn tab bệnh án (EMR)</h2>
          <button
            type="button"
            onClick={() => void refreshTabs()}
            className="inline-flex items-center gap-1 text-[11px] font-medium text-teal-700 hover:underline"
          >
            <RefreshCw className="h-3 w-3" /> Làm mới tab
          </button>
        </div>

        <div className="max-h-40 space-y-1.5 overflow-y-auto pr-1">
          {tabs.length === 0 ? (
            <p className="text-[11px] text-slate-500">Không tìm thấy tab web nào đang mở.</p>
          ) : (
            tabs.map((tab) => {
              const checked = selectedIds.includes(tab.id)
              return (
                <label
                  key={tab.id}
                  className={`flex cursor-pointer items-start gap-2 rounded border p-2 text-xs ${
                    checked ? 'border-teal-300 bg-teal-50/40' : 'border-slate-200 bg-white'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(e) => {
                      setSelectedIds((prev) =>
                        e.target.checked ? [...prev, tab.id] : prev.filter((id) => id !== tab.id),
                      )
                    }}
                    className="mt-0.5 rounded border-slate-300 text-teal-600 focus:ring-teal-500"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <span className="truncate font-medium text-slate-800">{tab.title}</span>
                      {tab.isEmrCandidate && (
                        <span className="shrink-0 rounded bg-teal-100 px-1.5 py-0.5 text-[10px] font-semibold text-teal-800">
                          EMR
                        </span>
                      )}
                    </div>
                    <p className="truncate text-[10px] text-slate-500">{tab.origin}</p>
                  </div>
                </label>
              )
            })
          )}
        </div>

        <button
          type="button"
          onClick={handleReadTabs}
          disabled={Boolean(busyStep) || selectedIds.length === 0}
          className="mt-2 inline-flex w-full items-center justify-center gap-1.5 rounded-md bg-slate-800 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-900 disabled:opacity-50"
        >
          <FileSearch className="h-3.5 w-3.5" />
          Đọc & Tách PII từ {selectedIds.length} tab đã chọn
        </button>
      </section>

      {/* Cảnh báo khớp / trộn lẫn bệnh nhân giữa nhiều tab */}
      {patientGuard && (
        <div
          className={`flex items-start gap-2 rounded-lg border p-2.5 text-xs ${
            patientGuard.status === 'MISMATCH_BLOCKED'
              ? 'border-rose-300 bg-rose-50 text-rose-800'
              : 'border-emerald-200 bg-emerald-50 text-emerald-800'
          }`}
        >
          {patientGuard.status === 'MISMATCH_BLOCKED' ? (
            <AlertOctagon className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
          ) : (
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
          )}
          <div>
            <p className="font-semibold">
              {patientGuard.status === 'MISMATCH_BLOCKED'
                ? 'Chặn trộn lẫn người bệnh'
                : 'Kiểm tra đồng nhất người bệnh'}
            </p>
            <p className="text-[11px]">{patientGuard.message}</p>
          </div>
        </div>
      )}

      {/* Bảng xác nhận mẫu nhãn PII lần đầu */}
      {pendingSchemaApproval && (
        <section className="space-y-2 rounded-lg border border-amber-300 bg-amber-50/70 p-3">
          <div className="flex items-start justify-between gap-2">
            <div>
              <h3 className="text-xs font-semibold text-amber-900">
                Xác nhận mẫu nhãn trường EMR (chỉ 1 lần / biểu mẫu)
              </h3>
              <p className="text-[11px] text-amber-800">
                Gemini 3.5 Flash Lite đã phân loại tên nhãn (không gửi giá trị bệnh nhân). Hãy rà
                nhanh trước khi lưu vào bộ đệm.
              </p>
            </div>
          </div>

          <div className="max-h-44 space-y-1 overflow-y-auto rounded border border-amber-200 bg-white p-2">
            {pendingSchemaApproval.fields.map((field, idx) => (
              <div
                key={`${field.ten_nhan}-${idx}`}
                className="flex items-center justify-between gap-2 border-b border-slate-100 py-1 text-[11px] last:border-b-0"
              >
                <span className="truncate font-medium text-slate-800">{field.ten_nhan}</span>
                <select
                  value={field.nhom}
                  onChange={(e) => updateSchemaFieldGroup(idx, e.target.value as SchemaGroup)}
                  className="rounded border border-slate-300 px-1.5 py-0.5 text-[11px]"
                >
                  <option value="pii_xoa">Xoá (PII)</option>
                  <option value="nghi_ngo_pii">Xoá (Nghi ngờ)</option>
                  <option value="lam_sang_giu">Giữ (Lâm sàng)</option>
                </select>
              </div>
            ))}
          </div>

          <button
            type="button"
            onClick={() => void approveSchemaTemplate()}
            className="w-full rounded bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-700"
          >
            Chấp nhận & Lưu mẫu nhãn
          </button>
        </section>
      )}

      {/* Báo cáo De-ID thu gọn (Audit Inspector) */}
      {auditSummary && (
        <section className="rounded-lg border border-slate-200 bg-white p-2.5">
          <div className="flex items-center justify-between text-xs">
            <span className="inline-flex items-center gap-1.5 font-medium text-slate-700">
              <ShieldCheck className="h-4 w-4 text-teal-600" />
              Đã che PII tại trình duyệt ({auditSummary.droppedFields.length} trường bị cắt,{' '}
              {auditSummary.dateAnchorCount} mốc ngày tương đối,{' '}
              {auditSummary.knownValueRedactions} lượt lặp)
            </span>
            <button
              type="button"
              onClick={() => setShowAuditPreview((v) => !v)}
              className="inline-flex items-center gap-1 text-[11px] font-medium text-teal-700 hover:underline"
            >
              <Eye className="h-3 w-3" /> {showAuditPreview ? 'Ẩn' : 'Xem dữ liệu sẽ gửi'}
            </button>
          </div>
          {showAuditPreview && sanitizedSections && (
            <div className="mt-2 max-h-40 space-y-1.5 overflow-y-auto rounded bg-slate-900 p-2 font-mono text-[10px] text-slate-100">
              {sanitizedSections.map((sec, i) => (
                <div key={i} className="border-b border-slate-700 pb-1 last:border-b-0">
                  <div className="font-semibold text-teal-300">
                    [{sec.loai_muc}] {sec.tieu_de}
                  </div>
                  <div className="whitespace-pre-wrap text-slate-200">{sec.noi_dung}</div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* 2. Dán & cắt ảnh bảng y lệnh OH */}
      <OhImageCropper value={ohImage} onChange={setOhImage} />

      {errorMsg && (
        <div className="rounded border border-rose-200 bg-rose-50 p-2 text-xs text-rose-700">
          {errorMsg}
        </div>
      )}

      {busyStep && (
        <div className="rounded border border-teal-200 bg-teal-50 p-2 text-xs font-medium text-teal-800">
          {busyStep}
        </div>
      )}

      <button
        type="button"
        onClick={() => void handleRunReview()}
        disabled={!canSubmit}
        className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-teal-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Sparkles className="h-4 w-4" />
        Thẩm định y lệnh (Zero-Retention)
      </button>
    </div>
  )
}
