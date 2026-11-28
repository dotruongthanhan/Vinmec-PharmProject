import { Pill, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { apiClient } from '@/api/index'
import type { DanhSachThuoc, KetQuaThuoc } from '@/api/types'
import { LookupWorkspace } from '@/app/LookupWorkspace'
import { Badge } from '@/components/ui/badge'
import { EmptyState } from '@/components/ui/empty-state'
import { InlineAlert } from '@/components/ui/inline-alert'
import { Skeleton } from '@/components/ui/skeleton'
import { DrugNameCombobox } from '@/features/lookup/DrugNameCombobox'
import { TablePagination } from '@/features/orders/TablePagination'
import { ErrorState } from '@/features/states/StateViews'
import { DEFAULT_PAGE_SIZE, parsePageParam, updatePageInSearchParams } from '@/lib/pagination'
import { useLoad } from '@/state/useLoad'

export interface DrugResultsTableProps {
  data: DanhSachThuoc | null
  loading: boolean
  error: string | null
  query: string
  onOpen: (hoatChatId: string) => void
  onPageChange: (page: number) => void
  onRetry: () => void
}

/** Bảng kết quả tra thuốc, phân trang phía máy chủ (30 dòng như bảng Hồ sơ cần duyệt). */
export function DrugResultsTable({ data, loading, error, query, onOpen, onPageChange, onRetry }: DrugResultsTableProps) {
  if (error) {
    return <ErrorState title="Không tải được danh sách thuốc" message={error} onRetry={onRetry} />
  }
  if (loading && !data) {
    return (
      <div className="flex flex-col gap-2" aria-busy="true" aria-label="Đang tải danh sách thuốc">
        {Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="h-11 w-full" />)}
      </div>
    )
  }
  if (!data || data.ket_qua.length === 0) {
    return (
      <div className="rounded-md border border-line bg-surface shadow-xs">
        <EmptyState
          role="status"
          icon={Pill}
          title={query ? `Không tìm thấy thuốc khớp “${query}”` : 'Chưa có thuốc để liệt kê'}
          description={query ? 'Thử tên hoạt chất (INN), tên Việt hoặc tên biệt dược, có hoặc không dấu.' : undefined}
        />
      </div>
    )
  }
  const pageSize = data.so_dong || DEFAULT_PAGE_SIZE
  const totalPages = Math.max(1, Math.ceil(data.tong / pageSize))
  const startIndex = (data.trang - 1) * pageSize + 1
  const endIndex = startIndex + data.ket_qua.length - 1
  return (
    <>
      {data.goi_y_sua ? (
        <InlineAlert tone="neutral" role="status">
          Không có kết quả khớp đúng. Đang hiện kết quả gần đúng cho{' '}
          <strong className="font-semibold text-fg">{data.goi_y_sua}</strong>.
        </InlineAlert>
      ) : null}
      <div
        role="region"
        aria-label="Bảng tra cứu thuốc"
        tabIndex={0}
        aria-busy={loading}
        className="relative w-full overflow-x-auto rounded-md border border-line bg-surface shadow-xs"
      >
        <table className="w-full min-w-[760px] border-collapse text-left text-sm">
          <thead className="bg-surface-muted text-2xs font-medium uppercase tracking-wide text-fg-subtle">
            <tr className="h-9 border-b border-line">
              <th scope="col" className="px-3">Hoạt chất</th>
              <th scope="col" className="px-3">Tên Việt</th>
              <th scope="col" className="px-3">ATC</th>
              <th scope="col" className="px-3 text-right">Chế phẩm</th>
              <th scope="col" className="px-3">Nhãn FDA</th>
              <th scope="col" className="px-3 text-right">Quy tắc</th>
            </tr>
          </thead>
          <tbody>
            {data.ket_qua.map((row: KetQuaThuoc) => (
              <tr key={row.hoat_chat_id} className="h-11 border-b border-line last:border-b-0 hover:bg-surface-hover">
                <th scope="row" className="px-3 text-left font-medium">
                  <button
                    type="button"
                    onClick={() => onOpen(row.hoat_chat_id)}
                    className="cursor-pointer rounded-sm text-left text-primary hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                  >
                    {row.ten_inn}
                  </button>
                </th>
                <td className="px-3 text-fg-muted">{row.ten_viet ?? '—'}</td>
                <td className="px-3 font-mono text-xs text-fg-muted">{row.ma_atc.length > 0 ? row.ma_atc.join(', ') : '—'}</td>
                <td className="px-3 text-right tabular-nums">{row.so_che_pham}</td>
                <td className="px-3">
                  {row.co_nhan_fda ? <Badge tone="success" variant="soft">Có</Badge> : <span className="text-fg-subtle">Không</span>}
                </td>
                <td className="px-3 text-right tabular-nums">{row.so_quy_tac}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <TablePagination
        currentPage={data.trang}
        totalPages={totalPages}
        totalItems={data.tong}
        startIndex={startIndex}
        endIndex={endIndex}
        onPageChange={onPageChange}
      />
    </>
  )
}

/** Trang Tra cứu thuốc: ô tìm (có debounce, ghi vào URL) và bảng phân trang. */
export default function DrugSearchPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const query = searchParams.get('q') ?? ''
  const page = parsePageParam(searchParams.get('trang'))
  const [draft, setDraft] = useState(query)

  useEffect(() => {
    if (draft.trim() === query.trim()) return
    const timer = setTimeout(() => {
      setSearchParams((prev) => {
        const next = updatePageInSearchParams(prev, 1)
        if (draft.trim()) next.set('q', draft.trim())
        else next.delete('q')
        return next
      }, { replace: true })
    }, 300)
    return () => clearTimeout(timer)
  }, [draft, query, setSearchParams])

  const state = useLoad<DanhSachThuoc>(
    (signal) => apiClient.searchDrugs({ q: query, trang: page, soDong: DEFAULT_PAGE_SIZE }, { signal }),
    `${query}|${page}`,
    'Không tải được danh sách thuốc.',
  )

  return (
    <LookupWorkspace section="thuoc" breadcrumbLabel="Tra cứu thuốc" backTo="/app/thuoc">
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <div className="flex flex-wrap items-baseline gap-2.5">
            <h1 className="text-lg font-semibold tracking-tight text-fg">Tra cứu thuốc</h1>
            {state.data ? (
              <span className="font-mono text-xs text-fg-subtle tabular-nums">{state.data.tong} hoạt chất</span>
            ) : null}
          </div>
        </div>
        <DrugNameCombobox
          type="search"
          value={draft}
          ariaLabel="Tìm thuốc theo hoạt chất, tên Việt hoặc biệt dược"
          placeholder="Tìm hoạt chất, tên Việt, biệt dược…"
          onValueChange={setDraft}
          onSelect={(item) => {
            const firstId = item.hoat_chat_ids[0]
            if (firstId) navigate(`/app/thuoc/${encodeURIComponent(firstId)}`)
          }}
          onEnterFreeText={() => {
            const trimmed = draft.trim()
            if (trimmed === query.trim()) return
            setSearchParams((prev) => {
              const next = updatePageInSearchParams(prev, 1)
              if (trimmed) next.set('q', trimmed)
              else next.delete('q')
              return next
            }, { replace: true })
          }}
          className="relative flex w-full max-w-xl items-center"
          leadingIcon={
            <Search
              className="pointer-events-none absolute left-2.5 size-3.5 text-fg-subtle"
              strokeWidth={1.75}
              aria-hidden="true"
            />
          }
          inputClassName="h-9 w-full rounded-sm border border-line-strong bg-surface pl-8 pr-3 text-sm text-fg placeholder:text-fg-subtle focus:border-primary"
        />
        <DrugResultsTable
          data={state.data}
          loading={state.loading}
          error={state.error}
          query={query}
          onOpen={(id) => navigate(`/app/thuoc/${encodeURIComponent(id)}`)}
          onPageChange={(next) => setSearchParams((prev) => updatePageInSearchParams(prev, next))}
          onRetry={state.reload}
        />
      </div>
    </LookupWorkspace>
  )
}
