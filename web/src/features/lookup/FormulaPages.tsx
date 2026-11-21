import { Calculator, ExternalLink } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { apiClient } from '@/api/index'
import type { CongThucMuc, DanhMucCongThuc, DauVaoCongThuc, KetQuaCongThuc } from '@/api/types'
import { LookupWorkspace } from '@/app/LookupWorkspace'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty-state'
import { InlineAlert } from '@/components/ui/inline-alert'
import { Skeleton } from '@/components/ui/skeleton'
import { ApprovalBadge } from '@/features/lookup/DrugDetailPage'
import { ErrorState } from '@/features/states/StateViews'
import {
  buildFormulaBody,
  formatFormulaResult,
  formulaChoiceLabel,
  formulaInputLabel,
  groupFormulas,
  hasUnitSelect,
  initialFormulaValues,
} from '@/lib/lookup'
import type { FormulaFormValues } from '@/lib/lookup'
import { useLoad } from '@/state/useLoad'

export const REFERENCE_NOTICE = 'Kết quả tham khảo, dược sĩ kiểm chứng'

const UNIT_DISPLAY: Record<string, string> = { tuoi: 'tuổi', 'lan/phut': 'lần/phút', umol: 'µmol', 'umol/L': 'µmol/L' }

function unitText(unit: string): string {
  return UNIT_DISPLAY[unit] ?? unit
}

export interface FormulaListViewProps {
  list: readonly CongThucMuc[]
}

/** Danh mục công thức theo nhóm (cơ thể, thận, gan, tim mạch, điện giải). */
export function FormulaListView({ list }: FormulaListViewProps) {
  const groups = groupFormulas(list)
  if (groups.length === 0) {
    return <EmptyState role="status" icon={Calculator} title="Chưa có công thức nào" />
  }
  return (
    <div className="flex flex-col gap-5">
      {groups.map((group) => (
        <section key={group.id} aria-labelledby={`nhom-${group.id}`} className="flex flex-col gap-2">
          <h2 id={`nhom-${group.id}`} className="text-sm font-semibold text-fg-muted">{group.label}</h2>
          <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {group.items.map((item) => (
              <li key={item.ma}>
                <Link
                  to={`/app/cong-thuc/${encodeURIComponent(item.ma)}`}
                  className="flex h-full flex-col gap-1 rounded-md border border-line bg-surface px-4 py-3 transition-colors duration-120 hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                >
                  <span className="text-sm font-semibold text-fg">{item.ten}</span>
                  <span className="text-xs text-fg-subtle">
                    {item.dau_vao.length} đầu vào · kết quả {item.dau_ra.don_vi.map(unitText).join(' / ') || '—'}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}

/** Trang danh sách công thức `/app/cong-thuc`. */
export function FormulaListPage() {
  const state = useLoad<DanhMucCongThuc>((signal) => apiClient.getFormulas({ signal }), 'danh-muc', 'Không tải được danh mục công thức.')
  return (
    <LookupWorkspace section="cong_thuc" breadcrumbLabel="Tính toán" backTo="/app/cong-thuc">
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-lg font-semibold tracking-tight text-fg">Tính toán công thức lâm sàng</h1>
          <p className="text-sm text-fg-muted">{REFERENCE_NOTICE}.</p>
        </div>
        {state.error ? (
          <ErrorState title="Không tải được danh mục công thức" message={state.error} onRetry={state.reload} />
        ) : state.loading && !state.data ? (
          <div className="flex flex-col gap-2" aria-busy="true" aria-label="Đang tải danh mục công thức">
            {Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-16 w-full" />)}
          </div>
        ) : state.data ? (
          <FormulaListView list={state.data.cong_thuc} />
        ) : null}
      </div>
    </LookupWorkspace>
  )
}

const FIELD_CLASS =
  'h-9 rounded-sm border border-line-strong bg-surface px-2.5 text-sm text-fg placeholder:text-fg-subtle focus:border-primary'

function FormulaField({
  input,
  values,
  onChange,
}: {
  input: DauVaoCongThuc
  values: FormulaFormValues
  onChange: (name: string, value: string) => void
}) {
  const id = `cong-thuc-${input.ten}`
  const label = input.nhan || formulaInputLabel(input.ten)
  if (input.kieu === 'lua_chon') {
    return (
      <div className="flex flex-col gap-1">
        <label htmlFor={id} className="text-sm font-medium text-fg">
          {label}{input.bat_buoc ? <span aria-hidden="true" className="text-danger-fg"> *</span> : null}
        </label>
        <select id={id} value={values[input.ten] ?? ''} onChange={(event) => onChange(input.ten, event.target.value)} className={FIELD_CLASS}>
          <option value="">Chọn…</option>
          {input.lua_chon.map((choice) => (
            <option key={choice} value={choice}>{input.nhan_lua_chon?.[choice] || formulaChoiceLabel(choice)}</option>
          ))}
        </select>
      </div>
    )
  }
  const unitField = input.truong_don_vi
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium text-fg">
        {label}{input.bat_buoc ? <span aria-hidden="true" className="text-danger-fg"> *</span> : null}
      </label>
      <div className="flex items-center gap-2">
        <input
          id={id}
          inputMode="decimal"
          autoComplete="off"
          value={values[input.ten] ?? ''}
          onChange={(event) => onChange(input.ten, event.target.value)}
          className={`${FIELD_CLASS} min-w-0 flex-1`}
        />
        {hasUnitSelect(input) && unitField !== null && input.don_vi.length > 1 ? (
          <select
            aria-label={`Đơn vị ${label.toLowerCase()}`}
            value={values[unitField] ?? input.don_vi[0]}
            onChange={(event) => onChange(unitField, event.target.value)}
            className={`${FIELD_CLASS} w-28`}
          >
            {input.don_vi.map((unit) => <option key={unit} value={unit}>{unitText(unit)}</option>)}
          </select>
        ) : input.don_vi.length > 0 ? (
          <span className="w-28 text-sm text-fg-muted">{unitText(input.don_vi[0])}</span>
        ) : null}
      </div>
    </div>
  )
}

export interface FormulaResultViewProps {
  result: KetQuaCongThuc
  spec?: CongThucMuc
}

/** Khối kết quả: số lớn + đơn vị, ghi chú, đầu vào đã dùng, đầu vào thiếu và tham khảo. */
export function FormulaResultView({ result, spec }: FormulaResultViewProps) {
  const missing = result.thieu_dau_vao
  const inputByName = new Map((spec?.dau_vao ?? []).map((item) => [item.ten, item]))
  const labelFor = (ten: string) => inputByName.get(ten)?.nhan || formulaInputLabel(ten)
  const formatUsedValue = (ten: string, giaTri: number | string) => {
    const inputSpec = inputByName.get(ten)
    if (typeof giaTri === 'string' && inputSpec?.kieu === 'lua_chon') {
      return inputSpec.nhan_lua_chon?.[giaTri] || formulaChoiceLabel(giaTri)
    }
    return String(giaTri)
  }
  return (
    <section aria-label="Kết quả tính" className="flex flex-col gap-3 rounded-md border border-line bg-surface px-4 py-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-semibold text-fg-muted">Kết quả</h2>
        <ApprovalBadge trangThai={result.trang_thai} />
      </div>
      {result.ket_qua !== null ? (
        <p className="flex flex-wrap items-baseline gap-2" role="status">
          <span className="text-4xl font-semibold tracking-tight text-fg tabular-nums">{formatFormulaResult(result.ket_qua)}</span>
          <span className="text-base text-fg-muted">{unitText(result.don_vi)}</span>
        </p>
      ) : null}
      {missing.length > 0 ? (
        <InlineAlert tone="missing" role="status" title="Thiếu đầu vào, chưa tính được">
          Còn thiếu: {missing.map(labelFor).join(', ')}.
        </InlineAlert>
      ) : null}
      {result.ghi_chu.length > 0 ? (
        <ul className="flex list-disc flex-col gap-1 pl-4 text-sm text-fg-muted">
          {result.ghi_chu.map((note, index) => <li key={index}>{note}</li>)}
        </ul>
      ) : null}
      {result.dau_vao_da_dung.length > 0 ? (
        <p className="text-xs text-fg-subtle">
          Đầu vào đã dùng: {result.dau_vao_da_dung.map((item) => `${labelFor(item.ten)} ${formatUsedValue(item.ten, item.gia_tri)} ${unitText(item.don_vi)}`.trim()).join(' · ')}
        </p>
      ) : null}
      <p className="text-xs text-fg-subtle">
        {result.cong_thuc} · phiên bản {result.phien_ban}
        {result.tham_khao ? ` · ${result.tham_khao}` : ''}
      </p>
      <p className="text-xs font-medium text-fg-muted">{REFERENCE_NOTICE}.</p>
    </section>
  )
}

export interface FormulaFormProps {
  spec: CongThucMuc
  onSubmit: (body: Record<string, string | number | null>) => void
  loading: boolean
}

/** Biểu mẫu sinh từ `dau_vao` của đặc tả. */
export function FormulaForm({ spec, onSubmit, loading }: FormulaFormProps) {
  const [values, setValues] = useState<FormulaFormValues>(() => initialFormulaValues(spec))
  const submit = (event: FormEvent) => {
    event.preventDefault()
    onSubmit(buildFormulaBody(spec, values))
  }
  return (
    <form onSubmit={submit} className="flex flex-col gap-3 rounded-md border border-line bg-surface px-4 py-4" aria-label={`Biểu mẫu ${spec.ten}`}>
      {spec.dau_vao.map((input) => (
        <FormulaField key={input.ten} input={input} values={values} onChange={(name, value) => setValues((prev) => ({ ...prev, [name]: value }))} />
      ))}
      <div>
        <Button type="submit" loading={loading} disabled={loading}>Tính</Button>
      </div>
    </form>
  )
}

/** Trang một công thức `/app/cong-thuc/:ma`. */
export function FormulaPage() {
  const { ma = '' } = useParams<{ ma: string }>()
  const catalog = useLoad<DanhMucCongThuc>((signal) => apiClient.getFormulas({ signal }), 'danh-muc', 'Không tải được danh mục công thức.')
  const spec = catalog.data?.cong_thuc.find((item) => item.ma === ma) ?? null
  const [result, setResult] = useState<{ ma: string; data: KetQuaCongThuc } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const controllerRef = useRef<AbortController | null>(null)

  useEffect(() => {
    controllerRef.current?.abort()
    return () => controllerRef.current?.abort()
  }, [ma])

  const calculate = async (body: Record<string, string | number | null>) => {
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    setLoading(true)
    setError(null)
    try {
      const data = await apiClient.calculateFormula(ma, { dau_vao: body }, { signal: controller.signal })
      if (controller.signal.aborted) return
      setResult({ ma, data })
    } catch (err: unknown) {
      if (controller.signal.aborted) return
      setResult(null)
      setError(err instanceof Error && err.message ? err.message : 'Không tính được công thức.')
    } finally {
      if (!controller.signal.aborted) setLoading(false)
    }
  }

  return (
    <LookupWorkspace section="cong_thuc" breadcrumbLabel="Tính toán" backTo="/app/cong-thuc" activeItem={spec?.ma ?? ma}>
      {catalog.error ? (
        <ErrorState title="Không tải được danh mục công thức" message={catalog.error} onRetry={catalog.reload} />
      ) : catalog.loading && !catalog.data ? (
        <div className="flex flex-col gap-3" aria-busy="true" aria-label="Đang tải công thức">
          <Skeleton className="h-10 w-1/2" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : !spec ? (
        <EmptyState role="status" icon={Calculator} title="Không tìm thấy công thức" description={`Không có công thức “${ma}”.`} />
      ) : (
        <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-lg font-semibold tracking-tight text-fg">{spec.ten}</h1>
              <ApprovalBadge trangThai={spec.trang_thai} />
            </div>
            <p className="text-sm font-medium text-fg-muted">{REFERENCE_NOTICE}.</p>
          </div>
          <FormulaForm key={spec.ma} spec={spec} onSubmit={(body) => void calculate(body)} loading={loading} />
          {error ? <ErrorState title="Không tính được" message={error} /> : null}
          {result && result.ma === spec.ma ? <FormulaResultView result={result.data} spec={spec} /> : null}
          {spec.tham_khao_goc.length > 0 || spec.tham_chieu_mdcalc ? (
            <section aria-label="Tham khảo" className="flex flex-col gap-1 text-xs text-fg-subtle">
              <h2 className="text-sm font-semibold text-fg-muted">Tham khảo</h2>
              <ul className="flex list-disc flex-col gap-0.5 pl-4">
                {spec.tham_khao_goc.map((ref, index) => <li key={index}>{ref}</li>)}
              </ul>
              {spec.tham_chieu_mdcalc ? (
                <a
                  href={spec.tham_chieu_mdcalc}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex w-fit items-center gap-1 text-primary underline"
                >
                  Đối chiếu trên MDCalc <ExternalLink className="size-3" strokeWidth={1.75} aria-hidden="true" />
                </a>
              ) : null}
            </section>
          ) : null}
        </div>
      )}
    </LookupWorkspace>
  )
}
