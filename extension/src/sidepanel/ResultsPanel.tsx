/**
 * Bước 2 trong Side Panel: hiển thị kết quả thẩm định tức thì (14 công thức + 14 luật),
 * sửa nhanh sinh hiệu/xét nghiệm, theo dõi AI nền (deepseek-flash) và nút Xoá phiên.
 */

import {
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  MessageSquareText,
  RefreshCcw,
  Trash2,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { sanitizeHttpsUrl, type ExtensionApiClient } from '../api/extensionClient'
import { restoreLocalLabels } from '../lib/deidScrubber'
import type {
  DoanNguon,
  ExtensionReviewResponse,
  KetQuaAI,
  NhanDinh,
} from '../lib/types'

interface Props {
  client: ExtensionApiClient
  review: ExtensionReviewResponse
  restoreMap?: Record<string, string>
  onUpdated: (next: ExtensionReviewResponse) => void
  onOpenChat: (findingId?: string) => void
  onPurged: () => void
}

export function ResultsPanel({
  client,
  review,
  restoreMap = {},
  onUpdated,
  onOpenChat,
  onPurged,
}: Props) {
  const { chi_tiet: detail } = review
  const [aiResult, setAiResult] = useState<KetQuaAI | null>(null)
  const [showOriginalDates, setShowOriginalDates] = useState(false)
  const [editWeight, setEditWeight] = useState<string>('')
  const [editCreat, setEditCreat] = useState<string>('')
  const [recalcBusy, setRecalcBusy] = useState(false)
  const [openFindingId, setOpenFindingId] = useState<string | null>(null)
  const [sourceModal, setSourceModal] = useState<DoanNguon | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const formatClinicalText = (raw: string) =>
    showOriginalDates ? restoreLocalLabels(raw, restoreMap) : raw
  const hasDateMap = Object.keys(restoreMap).length > 0

  // Tự động kích hoạt & poll tác vụ AI Giai đoạn 3 (deepseek-flash).
  useEffect(() => {
    let active = true
    let timer: ReturnType<typeof setTimeout> | null = null

    const startAndPoll = async () => {
      try {
        const started = await client.startAi(review.session_id)
        if (!active) return
        setAiResult(started)
        if (started.trang_thai === 'dang_chay') {
          const poll = async () => {
            if (!active) return
            try {
              const latest = await client.getAi(review.session_id)
              if (!active) return
              setAiResult(latest)
              if (latest.trang_thai === 'dang_chay') {
                timer = setTimeout(() => void poll(), 1200)
              }
            } catch {
              // Dừng poll nếu phiên đã bị xoá hoặc hết hạn.
            }
          }
          timer = setTimeout(() => void poll(), 1000)
        }
      } catch {
        // Nếu server tắt LLM, giao diện vẫn hiển thị trọn vẹn kết quả luật tất định.
      }
    }

    void startAndPoll()
    return () => {
      active = false
      if (timer) clearTimeout(timer)
    }
  }, [client, review.session_id])

  const handleQuickRecalc = async () => {
    setErrorMsg(null)
    setRecalcBusy(true)
    try {
      const weightVal = editWeight.trim() ? Number.parseFloat(editWeight) : undefined
      const creatVal = editCreat.trim() ? Number.parseFloat(editCreat) : undefined
      const next = await client.recalc(review.session_id, {
        can_nang_kg: Number.isFinite(weightVal) ? weightVal : undefined,
        xet_nghiem: Number.isFinite(creatVal)
          ? [{ ma_xet_nghiem: 'creatinin', gia_tri_so: creatVal!, don_vi: 'umol/L' }]
          : undefined,
      })
      onUpdated(next)
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Không tính lại được.')
    } finally {
      setRecalcBusy(false)
    }
  }

  const handleDeleteSession = async () => {
    try {
      await client.deleteSession(review.session_id)
    } catch {
      // Kể cả khi server hết hạn vẫn dọn trạng thái trình duyệt.
    }
    if (typeof chrome !== 'undefined' && chrome.runtime?.sendMessage) {
      chrome.runtime.sendMessage({ type: 'CLEAR_SESSION_STATE' })
    }
    onPurged()
  }

  const openSource = async (chunkId: string) => {
    try {
      const src = await client.getSource(review.session_id, chunkId)
      setSourceModal(src)
    } catch {
      setErrorMsg('Không mở được đoạn nguồn trích dẫn.')
    }
  }

  const aiAttention = aiResult?.trang_thai === 'xong' && aiResult.nhan_dinh
    ? aiResult.nhan_dinh.can_chu_y
    : detail.nhan_dinh.can_chu_y

  const renderFindingCard = (item: NhanDinh) => {
    const isExpanded = openFindingId === item.nhan_dinh_id
    const sevBadge =
      item.muc_do_ma === 'nghiem_trong'
        ? 'bg-rose-100 text-rose-800 border-rose-200'
        : item.muc_do_ma === 'can_luu_y'
          ? 'bg-amber-100 text-amber-800 border-amber-200'
          : 'bg-slate-100 text-slate-700 border-slate-200'

    return (
      <div
        key={item.nhan_dinh_id}
        className="rounded-lg border border-slate-200 bg-white p-2.5 shadow-xs"
      >
        <button
          type="button"
          onClick={() => setOpenFindingId(isExpanded ? null : item.nhan_dinh_id)}
          className="flex w-full items-start justify-between gap-2 text-left"
        >
          <div className="min-w-0 flex-1 space-y-1">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold ${sevBadge}`}>
                {item.muc_do_nhan || item.ket_luan_nhan}
              </span>
              <span className="text-[10px] font-medium text-slate-500">{item.yeu_to}</span>
            </div>
            <p className="text-xs font-semibold text-slate-900">{item.thuoc || 'Toàn y lệnh'}</p>
            <p className="text-xs text-slate-700">{formatClinicalText(item.nhan_xet)}</p>
          </div>
          {isExpanded ? (
            <ChevronUp className="h-4 w-4 shrink-0 text-slate-400" />
          ) : (
            <ChevronDown className="h-4 w-4 shrink-0 text-slate-400" />
          )}
        </button>

        {isExpanded && (
          <div className="mt-2 space-y-2 border-t border-slate-100 pt-2 text-[11px]">
            {item.dien_giai_ai && (
              <div className="rounded bg-teal-50 p-2 text-teal-900">
                <p className="font-semibold">Diễn giải (DeepSeek Flash):</p>
                <p>{formatClinicalText(item.dien_giai_ai)}</p>
              </div>
            )}
            {item.de_xuat_ai && (
              <div className="rounded bg-blue-50 p-2 text-blue-900">
                <p className="font-semibold">Đề xuất cân nhắc:</p>
                <p>{formatClinicalText(item.de_xuat_ai)}</p>
              </div>
            )}
            {item.can_cu.length > 0 && (
              <div>
                <p className="font-semibold text-slate-700">Căn cứ:</p>
                <ul className="list-disc space-y-0.5 pl-4 text-slate-600">
                  {item.can_cu.map((c) => (
                    <li key={c.so}>{c.mo_ta}</li>
                  ))}
                </ul>
              </div>
            )}
            {item.trich_dan && item.trich_dan.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {item.trich_dan.map((cit) => (
                  <button
                    key={cit.so}
                    type="button"
                    onClick={() => void openSource(cit.doan_trich_id)}
                    className="rounded bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-teal-700 hover:bg-teal-50"
                  >
                    [{cit.so}] {cit.nhan}
                  </button>
                ))}
              </div>
            )}
            <button
              type="button"
              onClick={() => onOpenChat(item.nhan_dinh_id)}
              className="inline-flex items-center gap-1 text-[11px] font-medium text-teal-700 hover:underline"
            >
              <MessageSquareText className="h-3 w-3" /> Hỏi đáp về nhận định này
            </button>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* Banner cảnh báo PII nếu ảnh OH còn dính chữ hành chính */}
      {review.canh_bao_pii_anh.length > 0 && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 p-2.5 text-xs text-amber-900">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
          <div>
            <p className="font-semibold">Cảnh báo mềm: Phát hiện vùng nghi chứa PII trên ảnh OH</p>
            <p className="text-[11px]">
              Hạng mục nhận diện: <strong>{review.canh_bao_pii_anh.join(', ')}</strong>. Lần sau bạn
              nên kéo khung cắt xuống thấp hơn để che thanh hành chính.
            </p>
          </div>
        </div>
      )}

      {/* Thẻ tóm tắt bệnh nhân (không định danh) & CrCl */}
      <section className="rounded-lg border border-slate-200 bg-white p-3">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-teal-700">
              Phiên tạm RAM · {review.thoi_gian_ms} ms
            </p>
            <h2 className="text-sm font-bold text-slate-900">
              {detail.dinh_danh.gioi_tuoi} · {detail.dinh_danh.can_nang}
            </h2>
            <p className="text-[11px] text-slate-600">{detail.dinh_danh.khoa_loai}</p>
          </div>
          <div
            className={`rounded-md px-2 py-1 text-right text-xs font-semibold ${
              detail.dinh_danh.crcl_bat_thuong
                ? 'bg-rose-50 text-rose-700 ring-1 ring-rose-200'
                : 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200'
            }`}
          >
            <div>CrCl: {detail.dinh_danh.crcl}</div>
            <div className="text-[10px] font-normal">{detail.dinh_danh.di_ung_text}</div>
          </div>
        </div>

        {/* Sửa nhanh thông số để chạy lại Stage 2 (<50ms) */}
        <div className="mt-2.5 grid grid-cols-3 gap-1.5 border-t border-slate-100 pt-2">
          <input
            type="number"
            step="0.5"
            placeholder="Cân nặng (kg)"
            value={editWeight}
            onChange={(e) => setEditWeight(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1 text-[11px]"
          />
          <input
            type="number"
            step="1"
            placeholder="Creatinin (µmol/L)"
            value={editCreat}
            onChange={(e) => setEditCreat(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1 text-[11px]"
          />
          <button
            type="button"
            disabled={recalcBusy}
            onClick={() => void handleQuickRecalc()}
            className="inline-flex items-center justify-center gap-1 rounded bg-slate-800 px-2 py-1 text-[11px] font-medium text-white hover:bg-slate-900 disabled:opacity-50"
          >
            <RefreshCcw className="h-3 w-3" /> Tính lại
          </button>
        </div>

        {hasDateMap && (
          <div className="mt-2 border-t border-slate-100 pt-2">
            <label className="flex cursor-pointer items-center justify-between text-[11px] text-slate-600">
              <span>Hiện mốc ngày gốc (chỉ lưu trong RAM trình duyệt)</span>
              <input
                type="checkbox"
                checked={showOriginalDates}
                onChange={(e) => setShowOriginalDates(e.target.checked)}
                className="rounded border-slate-300 text-teal-600 focus:ring-teal-500"
              />
            </label>
            {showOriginalDates && (
              <div className="mt-1.5 flex flex-wrap gap-1">
                {Object.entries(restoreMap).map(([rel, orig]) => (
                  <span
                    key={rel}
                    className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-700"
                  >
                    {rel} = {orig}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </section>

      {/* Thanh tiến trình Giai đoạn 3 (deepseek-flash) */}
      {aiResult && (
        <section className="rounded-lg border border-slate-200 bg-white p-2.5 text-xs">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-slate-800">
              Diễn giải AI ({aiResult.mo_hinh || 'deepseek-flash'})
            </span>
            <span className="text-[11px] font-medium text-teal-700">
              {aiResult.trang_thai === 'dang_chay'
                ? 'Đang đối chiếu nhãn FDA...'
                : aiResult.trang_thai === 'xong'
                  ? `Hoàn tất (${Math.round(aiResult.thoi_gian_ms ?? 0)} ms)`
                  : aiResult.trang_thai === 'tat'
                    ? 'Chỉ dùng bộ luật tất định'
                    : 'AI gặp lỗi — giữ nguyên kết quả luật'}
            </span>
          </div>
          {aiResult.cac_buoc.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {aiResult.cac_buoc.map((step) => (
                <span
                  key={step.ma}
                  className={`rounded px-1.5 py-0.5 text-[10px] ${
                    step.trang_thai === 'xong'
                      ? 'bg-emerald-100 text-emerald-800'
                      : step.trang_thai === 'dang_chay'
                        ? 'bg-amber-100 text-amber-800'
                        : 'bg-slate-100 text-slate-600'
                  }`}
                >
                  {step.ten}
                </span>
              ))}
            </div>
          )}
        </section>
      )}

      {errorMsg && (
        <div className="rounded border border-rose-200 bg-rose-50 p-2 text-xs text-rose-700">
          {errorMsg}
        </div>
      )}

      {/* Danh sách nhận định cần chú ý (7 yếu tố) */}
      <section className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold text-slate-800">
            Cần chú ý ({aiAttention.length}) · Đạt ({detail.nhan_dinh.dat.length})
          </h3>
          <span className="text-[10px] text-slate-500">
            Đã chạy {detail.nhan_dinh.so_luat_da_chay} luật
          </span>
        </div>

        {aiAttention.length === 0 ? (
          <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-800">
            <CheckCircle className="h-4 w-4 shrink-0 text-emerald-600" />
            <span>Không phát hiện cảnh báo bất thường trên y lệnh này.</span>
          </div>
        ) : (
          <div className="space-y-2">{aiAttention.map(renderFindingCard)}</div>
        )}
      </section>

      {/* Modal xem trích dẫn nguồn công khai (link https an toàn) */}
      {sourceModal && (
        <div className="rounded-lg border border-teal-300 bg-white p-3 shadow-md">
          <div className="mb-1 flex items-center justify-between">
            <span className="text-xs font-semibold text-teal-800">
              {sourceModal.nguon_nhan} · {sourceModal.duong_dan_muc}
            </span>
            <button
              type="button"
              onClick={() => setSourceModal(null)}
              className="text-[11px] font-medium text-slate-500 hover:text-slate-900"
            >
              Đóng
            </button>
          </div>
          <p className="max-h-36 overflow-y-auto whitespace-pre-wrap text-[11px] text-slate-700">
            {sourceModal.noi_dung}
          </p>
          {sanitizeHttpsUrl(sourceModal.url_goc) && (
            <a
              href={sanitizeHttpsUrl(sourceModal.url_goc)!}
              target="_blank"
              rel="noreferrer noopener"
              className="mt-1.5 inline-flex items-center gap-1 text-[11px] font-medium text-teal-700 hover:underline"
            >
              Xem nguồn gốc DailyMed <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
      )}

      {/* Thanh hành động đáy: Hỏi đáp AI + Xoá sạch phiên RAM */}
      <div className="grid grid-cols-2 gap-2 pt-1">
        <button
          type="button"
          onClick={() => onOpenChat()}
          className="inline-flex items-center justify-center gap-1.5 rounded-md border border-teal-600 bg-white px-3 py-2 text-xs font-semibold text-teal-700 hover:bg-teal-50"
        >
          <MessageSquareText className="h-3.5 w-3.5" /> Hỏi đáp ca bệnh
        </button>
        <button
          type="button"
          onClick={() => void handleDeleteSession()}
          className="inline-flex items-center justify-center gap-1.5 rounded-md border border-rose-300 bg-rose-50 px-3 py-2 text-xs font-semibold text-rose-700 hover:bg-rose-100"
        >
          <Trash2 className="h-3.5 w-3.5" /> Xoá phiên / Ca mới
        </button>
      </div>
    </div>
  )
}
