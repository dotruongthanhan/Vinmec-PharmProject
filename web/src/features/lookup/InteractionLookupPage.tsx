import { ArrowLeftRight, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { apiClient } from '@/api/index'
import type { KetQuaTraTuongTac, PhanGiaiTen } from '@/api/types'
import { LookupWorkspace } from '@/app/LookupWorkspace'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty-state'
import { InlineAlert } from '@/components/ui/inline-alert'
import { InteractionMatrix } from '@/features/order-detail/InteractionMatrix'
import { ErrorState } from '@/features/states/StateViews'
import {
  MAX_INTERACTION_DRUGS,
  MIN_INTERACTION_DRUGS,
  addDrugName,
  splitDrugNames,
} from '@/lib/lookup'

const EMPTY_TABLE = { cot: [], dong: [] }
const EMPTY_FINDINGS = { can_chu_y: [], dat: [], yeu_to_chua_kiem: [] }

const RESOLUTION_NOTE: Record<PhanGiaiTen['trang_thai'], string | null> = {
  da_phan_giai: null,
  mot_phan: 'chỉ nhận diện được một phần',
  khong_nhan_dien: 'không nhận diện được tên thuốc',
  khong_ap_dung: 'không áp dụng',
}

/** Cảnh báo cho các tên chưa phân giải đầy đủ, hiện bên cạnh ma trận. */
export function ResolutionWarnings({ items }: { items: readonly PhanGiaiTen[] }) {
  const problems = items.filter((item) => item.trang_thai !== 'da_phan_giai')
  if (problems.length === 0) return null
  return (
    <InlineAlert tone="missing" role="status" title="Có tên thuốc chưa nhận diện đầy đủ">
      <ul className="mt-1 flex list-disc flex-col gap-0.5 pl-4">
        {problems.map((item) => (
          <li key={item.chi_tiet_y_lenh_id}>
            <span className="font-medium">{item.ten_nhap}</span>: {RESOLUTION_NOTE[item.trang_thai]}
            {item.ly_do ? ` (${item.ly_do})` : ''}. Các ô liên quan là Thiếu dữ liệu, không có nghĩa là không có tương tác.
          </li>
        ))}
      </ul>
    </InlineAlert>
  )
}

export interface InteractionLookupResultProps {
  result: KetQuaTraTuongTac
}

/** Kết quả tra tay: cảnh báo tên lạ + ma trận dùng chung với trang ca (chi tiết cặp mở sẵn). */
export function InteractionLookupResult({ result }: InteractionLookupResultProps) {
  return (
    <div className="flex flex-col gap-3">
      <ResolutionWarnings items={result.phan_giai} />
      <InteractionMatrix
        choDuyet={EMPTY_TABLE}
        dangDung={null}
        nhanDinh={EMPTY_FINDINGS}
        maTranTuongTac={result.ma_tran}
        onOpenFinding={() => {}}
        manual
        pairDetails={result.chi_tiet}
        detailsOpen
      />
    </div>
  )
}

export interface DrugChipInputProps {
  names: readonly string[]
  onChange: (names: string[]) => void
  onSubmit: () => void
  disabled?: boolean
}

/** Ô nhập dạng thẻ: Enter hoặc dấu phẩy để thêm, Backspace khi ô trống để bỏ thẻ cuối. */
export function DrugChipInput({ names, onChange, onSubmit, disabled = false }: DrugChipInputProps) {
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)

  const commit = (raw: string): boolean => {
    let next = [...names]
    for (const part of splitDrugNames(raw)) {
      const result = addDrugName(next, part)
      if (result.error) {
        setError(result.error)
        onChange(next)
        return false
      }
      next = result.list
    }
    setError(null)
    onChange(next)
    return true
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      event.preventDefault()
      if (draft.trim() === '') {
        if (names.length >= MIN_INTERACTION_DRUGS) onSubmit()
        return
      }
      if (commit(draft)) setDraft('')
    } else if (event.key === ',' || event.key === ';') {
      event.preventDefault()
      if (commit(draft)) setDraft('')
    } else if (event.key === 'Backspace' && draft === '' && names.length > 0) {
      onChange(names.slice(0, -1))
    }
  }

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor="tra-tuong-tac-input" className="text-sm font-medium text-fg">
        Thuốc cần kiểm tra ({names.length}/{MAX_INTERACTION_DRUGS})
      </label>
      <div
        className="flex min-h-10 flex-wrap items-center gap-1.5 rounded-sm border border-line-strong bg-surface px-2 py-1.5 focus-within:border-primary"
        onClick={() => inputRef.current?.focus()}
      >
        {names.map((name) => (
          <span key={name} className="inline-flex items-center gap-1 rounded-full border border-line-strong bg-surface-muted py-0.5 pl-2.5 pr-1 text-sm text-fg">
            {name}
            <button
              type="button"
              aria-label={`Bỏ ${name}`}
              disabled={disabled}
              onClick={(event) => {
                event.stopPropagation()
                onChange(names.filter((item) => item !== name))
              }}
              className="inline-flex size-5 cursor-pointer items-center justify-center rounded-full text-fg-muted hover:bg-surface-hover hover:text-fg focus-visible:outline-2 focus-visible:outline-primary"
            >
              <X className="size-3" strokeWidth={1.75} aria-hidden="true" />
            </button>
          </span>
        ))}
        <input
          id="tra-tuong-tac-input"
          ref={inputRef}
          value={draft}
          disabled={disabled}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={() => {
            if (draft.trim() !== '' && commit(draft)) setDraft('')
          }}
          placeholder={names.length === 0 ? 'Gõ tên thuốc rồi nhấn Enter, ví dụ: Amiodaron 200 mg' : 'Thêm thuốc…'}
          aria-describedby="tra-tuong-tac-help"
          className="min-w-40 flex-1 bg-transparent py-0.5 text-sm text-fg placeholder:text-fg-subtle"
        />
      </div>
      <p id="tra-tuong-tac-help" className="text-xs text-fg-subtle">
        Nhập từ {MIN_INTERACTION_DRUGS} đến {MAX_INTERACTION_DRUGS} thuốc, tên tự do (có thể kèm hàm lượng). Enter để thêm thuốc; Enter khi ô trống để kiểm tra.
      </p>
      {error ? <p role="alert" className="text-xs text-danger-fg">{error}</p> : null}
    </div>
  )
}

/** Trang Tra tương tác `/app/tuong-tac`. */
export default function InteractionLookupPage() {
  const [names, setNames] = useState<string[]>([])
  const [result, setResult] = useState<{ names: string[]; data: KetQuaTraTuongTac } | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const controllerRef = useRef<AbortController | null>(null)

  useEffect(() => () => controllerRef.current?.abort(), [])

  const canCheck = names.length >= MIN_INTERACTION_DRUGS && names.length <= MAX_INTERACTION_DRUGS && !loading

  const check = async () => {
    if (!canCheck) return
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    const requested = [...names]
    setLoading(true)
    setError(null)
    try {
      const data = await apiClient.checkInteractions({ thuoc: requested }, { signal: controller.signal })
      if (controller.signal.aborted) return
      setResult({ names: requested, data })
    } catch (err: unknown) {
      if (controller.signal.aborted) return
      setError(err instanceof Error && err.message ? err.message : 'Không kiểm tra được tương tác.')
    } finally {
      if (!controller.signal.aborted) setLoading(false)
    }
  }

  const stale = result !== null && (result.names.length !== names.length || result.names.some((item, i) => item !== names[i]))

  return (
    <LookupWorkspace section="tuong_tac" breadcrumbLabel="Tra tương tác" backTo="/app/tuong-tac">
      <div className="flex flex-col gap-4">
        <h1 className="text-lg font-semibold tracking-tight text-fg">Tra tương tác thuốc</h1>
        <DrugChipInput names={names} onChange={setNames} onSubmit={() => void check()} disabled={loading} />
        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={() => void check()} disabled={!canCheck} loading={loading}>
            Kiểm tra
          </Button>
          {names.length > 0 ? (
            <Button variant="ghost" onClick={() => { setNames([]); setResult(null); setError(null) }} disabled={loading}>
              Xoá hết
            </Button>
          ) : null}
        </div>

        {error ? <ErrorState title="Không kiểm tra được tương tác" message={error} onRetry={() => void check()} /> : null}
        {stale && !error ? (
          <InlineAlert tone="neutral" role="status">
            Danh sách thuốc đã thay đổi. Bấm Kiểm tra để cập nhật kết quả.
          </InlineAlert>
        ) : null}
        {result ? (
          <InteractionLookupResult result={result.data} />
        ) : !loading && !error ? (
          <EmptyState
            role="status"
            icon={ArrowLeftRight}
            title="Chưa có kết quả"
            description="Nhập ít nhất hai thuốc rồi bấm Kiểm tra để xem ma trận tương tác."
          />
        ) : null}
      </div>
    </LookupWorkspace>
  )
}
