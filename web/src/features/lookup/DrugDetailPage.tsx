import { ChevronRight, ExternalLink } from 'lucide-react'
import { useId, useState } from 'react'
import type { ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import { apiClient } from '@/api/index'
import type { ChiTietThuoc, QuyTacDong } from '@/api/types'
import { LookupWorkspace } from '@/app/LookupWorkspace'
import { Badge } from '@/components/ui/badge'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorState } from '@/features/states/StateViews'
import { cn } from '@/lib/cn'
import { approvalLabel, fdaSectionLabel, ruleGroupLabel } from '@/lib/lookup'
import { useLoad } from '@/state/useLoad'

export function ApprovalBadge({ trangThai }: { trangThai: string | null | undefined }) {
  const label = approvalLabel(trangThai)
  if (!label) return null
  return <Badge tone={label.tone} variant="soft">{label.text}</Badge>
}

export interface FoldSectionProps {
  title: string
  meta?: string
  trangThai?: string | null
  defaultOpen?: boolean
  disabled?: boolean
  children: ReactNode
}

/** Mục gập/mở: tiêu đề là nút có `aria-expanded`; nội dung luôn nằm trong DOM với `hidden`. */
export function FoldSection({ title, meta, trangThai, defaultOpen = false, disabled = false, children }: FoldSectionProps) {
  const [open, setOpen] = useState(defaultOpen)
  const panelId = useId()
  const expanded = open && !disabled
  return (
    <section className="rounded-md border border-line bg-surface">
      <button
        type="button"
        aria-expanded={expanded}
        aria-controls={panelId}
        disabled={disabled}
        onClick={() => setOpen(!open)}
        className="flex w-full cursor-pointer items-center gap-2 rounded-md px-4 py-3 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-default disabled:opacity-60"
      >
        <ChevronRight
          className={cn('size-4 shrink-0 text-fg-muted transition-transform duration-120', expanded && 'rotate-90')}
          strokeWidth={1.75}
          aria-hidden="true"
        />
        <span className="min-w-0 flex-1 text-sm font-semibold text-fg">{title}</span>
        <ApprovalBadge trangThai={trangThai} />
        {meta ? <span className="shrink-0 text-xs text-fg-subtle tabular-nums">{meta}</span> : null}
      </button>
      <div id={panelId} hidden={!expanded} className="border-t border-line px-4 py-3">
        {children}
      </div>
    </section>
  )
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return JSON.stringify(value)
}

function RuleRow({ rule }: { rule: QuyTacDong }) {
  const { trich_nguyen_van: quote, ...rest } = rule.du_lieu
  const entries = Object.entries(rest).filter(([key]) => key !== 'trang_thai')
  return (
    <li className="flex flex-col gap-1.5 rounded-sm border border-line px-3 py-2">
      <div className="flex flex-wrap items-center gap-2 text-xs text-fg-subtle">
        <span className="font-mono">{rule.bang_luat} · {rule.phan}</span>
        {rule.phien_ban ? <span>phiên bản {rule.phien_ban}</span> : null}
        <ApprovalBadge trangThai={rule.trang_thai} />
      </div>
      {entries.length > 0 ? (
        <dl className="grid grid-cols-[minmax(110px,max-content)_1fr] gap-x-3 gap-y-0.5 text-sm">
          {entries.map(([key, value]) => (
            <div key={key} className="contents">
              <dt className="text-fg-subtle">{key.replaceAll('_', ' ')}</dt>
              <dd className="break-words text-fg">{formatValue(value)}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {typeof quote === 'string' && quote ? (
        <blockquote lang="en" className="border-l-2 border-line-strong pl-3 text-sm whitespace-pre-wrap text-fg-muted">
          {quote}
        </blockquote>
      ) : null}
    </li>
  )
}

export interface DrugDetailViewProps {
  detail: ChiTietThuoc
}

/** Chi tiết một hoạt chất: định danh, nhãn FDA theo mục, quy tắc thẩm định, chế phẩm, tương tác DDInter. */
export function DrugDetailView({ detail }: DrugDetailViewProps) {
  const { dinh_danh: id, che_pham: chePham, nhan_fda: fda, quy_tac: quyTac, tuong_tac_tom_tat: tuongTac } = detail
  const rulesByGroup = new Map<string, QuyTacDong[]>()
  for (const rule of quyTac) {
    rulesByGroup.set(rule.nhom, [...(rulesByGroup.get(rule.nhom) ?? []), rule])
  }
  const totalCap = tuongTac.so_cap.major + tuongTac.so_cap.moderate + tuongTac.so_cap.minor + tuongTac.so_cap.unknown

  return (
    <div className="flex flex-col gap-3">
      <section aria-label="Định danh thuốc" className="rounded-md border border-line bg-surface px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-lg font-semibold tracking-tight text-fg">{id.ten_inn}</h1>
          {id.ten_viet ? <span className="text-sm text-fg-muted">{id.ten_viet}</span> : null}
          <ApprovalBadge trangThai={id.trang_thai} />
        </div>
        <dl className="mt-2 grid grid-cols-[max-content_1fr] gap-x-4 gap-y-0.5 text-sm">
          <dt className="text-fg-subtle">Mã ATC</dt>
          <dd className="font-mono text-xs text-fg">{id.ma_atc.length > 0 ? id.ma_atc.join(', ') : '—'}</dd>
          <dt className="text-fg-subtle">RxCUI</dt>
          <dd className="font-mono text-xs text-fg">{id.rxcui ?? '—'}</dd>
          <dt className="text-fg-subtle">DDInter</dt>
          <dd className="font-mono text-xs text-fg">{id.ddinter_id ?? '—'}</dd>
          <dt className="text-fg-subtle">Loại</dt>
          <dd className="text-fg">{id.loai}</dd>
          <dt className="text-fg-subtle">Nguồn</dt>
          <dd className="text-fg">{id.nguon}</dd>
        </dl>
        <p className="mt-2 text-2xs text-fg-subtle">Kết quả tham khảo. Dược sĩ kiểm chứng và quyết định.</p>
      </section>

      <h2 className="mt-2 text-sm font-semibold text-fg-muted">Nhãn FDA ({fda.tong_doan} đoạn)</h2>
      {fda.nhom.map((group) => (
        <FoldSection
          key={group.muc}
          title={fdaSectionLabel(group.muc)}
          meta={group.doan.length > 0 ? `${group.doan.length} đoạn` : 'Không có đoạn'}
          trangThai={fda.trang_thai}
          disabled={group.doan.length === 0}
        >
          <ul className="flex flex-col gap-3">
            {group.doan.map((part) => (
              <li key={part.doan_trich_id} className="flex flex-col gap-1">
                <p className="text-xs font-semibold text-fg-subtle">{part.duong_dan_muc}</p>
                <p lang="en" className="text-sm leading-relaxed whitespace-pre-wrap text-fg">{part.noi_dung_goc}</p>
                <p className="flex flex-wrap items-center gap-x-2 text-2xs text-fg-subtle">
                  <span>
                    {part.nguon}
                    {part.phien_ban_nguon ? ` · ${part.phien_ban_nguon}` : ''}
                    {part.set_id ? ` · set ${part.set_id}` : ''}
                  </span>
                  {part.url_goc ? (
                    <a
                      href={part.url_goc}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-primary underline"
                    >
                      DailyMed <ExternalLink className="size-3" strokeWidth={1.75} aria-hidden="true" />
                    </a>
                  ) : null}
                </p>
              </li>
            ))}
          </ul>
        </FoldSection>
      ))}

      <h2 className="mt-2 text-sm font-semibold text-fg-muted">Quy tắc thẩm định</h2>
      {rulesByGroup.size === 0 ? (
        <p className="rounded-md border border-line bg-surface px-4 py-3 text-sm text-fg-muted">
          Chưa có quy tắc thẩm định nào cho hoạt chất này. Điều đó không có nghĩa là thuốc không cần kiểm tra.
        </p>
      ) : (
        [...rulesByGroup.entries()].map(([group, rules]) => (
          <FoldSection key={group} title={ruleGroupLabel(group)} meta={`${rules.length} quy tắc`}>
            <ul className="flex flex-col gap-2">
              {rules.map((rule, index) => <RuleRow key={`${rule.bang_luat}-${index}`} rule={rule} />)}
            </ul>
          </FoldSection>
        ))
      )}

      <h2 className="mt-2 text-sm font-semibold text-fg-muted">Chế phẩm và tương tác</h2>
      <FoldSection title="Chế phẩm (Cục Quản lý Dược)" meta={`${chePham.tong} chế phẩm`} trangThai={chePham.trang_thai} disabled={chePham.danh_sach.length === 0}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] border-collapse text-left text-sm">
            <thead className="text-2xs font-medium uppercase tracking-wide text-fg-subtle">
              <tr className="h-8 border-b border-line">
                <th scope="col">Tên thuốc</th>
                <th scope="col">Số đăng ký</th>
                <th scope="col">Dạng bào chế</th>
                <th scope="col" className="text-right">Hàm lượng</th>
              </tr>
            </thead>
            <tbody>
              {chePham.danh_sach.map((item, index) => (
                <tr key={`${item.so_dang_ky ?? item.ten_thuoc}-${index}`} className="h-9 border-b border-line last:border-b-0">
                  <th scope="row" className="pr-3 text-left font-medium">{item.ten_thuoc}</th>
                  <td className="pr-3 font-mono text-xs text-fg-muted">{item.so_dang_ky ?? '—'}</td>
                  <td className="pr-3 text-fg-muted">{item.dang_bao_che ?? '—'}</td>
                  <td className="text-right tabular-nums">
                    {item.ham_luong !== null ? `${item.ham_luong}${item.don_vi ? ` ${item.don_vi}` : ''}` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {chePham.tong > chePham.danh_sach.length ? (
          <p className="mt-2 text-xs text-fg-subtle">Hiển thị {chePham.danh_sach.length} / {chePham.tong} chế phẩm. Nguồn: {chePham.nguon}.</p>
        ) : (
          <p className="mt-2 text-xs text-fg-subtle">Nguồn: {chePham.nguon}.</p>
        )}
      </FoldSection>

      <FoldSection title="Tóm tắt tương tác (DDInter)" meta={tuongTac.co_du_lieu ? `${totalCap} cặp` : 'Không có dữ liệu'} trangThai={tuongTac.trang_thai}>
        {tuongTac.co_du_lieu ? (
          <div className="flex flex-col gap-3">
            <ul className="flex flex-wrap gap-2 text-xs">
              <li><Badge tone="danger" variant="soft">Major {tuongTac.so_cap.major}</Badge></li>
              <li><Badge tone="warning" variant="soft">Moderate {tuongTac.so_cap.moderate}</Badge></li>
              <li><Badge tone="neutral" variant="soft">Minor {tuongTac.so_cap.minor}</Badge></li>
              <li><Badge tone="missing" variant="soft">Unknown {tuongTac.so_cap.unknown}</Badge></li>
            </ul>
            {tuongTac.major.length > 0 ? (
              <ul className="flex flex-col divide-y divide-line rounded-sm border border-line">
                {tuongTac.major.map((pair) => (
                  <li key={pair.ddinter_id} className="px-3 py-2 text-sm">
                    <span className="font-medium text-fg">{pair.ten_thuoc_khac}</span>
                    {pair.co_che.length > 0 ? <span className="text-fg-muted"> · {pair.co_che.join(', ')}</span> : null}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : (
          <p className="text-sm text-fg-muted">Nguồn chưa có dữ liệu tương tác cho hoạt chất này.</p>
        )}
        <p className="mt-2 text-xs text-fg-subtle">{tuongTac.nguon}. {tuongTac.ghi_chu}</p>
      </FoldSection>
    </div>
  )
}

/** Trang chi tiết thuốc `/app/thuoc/:hoat_chat_id`. */
export default function DrugDetailPage() {
  const { hoat_chat_id: hoatChatId = '' } = useParams<{ hoat_chat_id: string }>()
  const state = useLoad<ChiTietThuoc>(
    (signal) => apiClient.getDrug(hoatChatId, { signal }),
    hoatChatId,
    'Không tải được chi tiết thuốc.',
  )
  return (
    <LookupWorkspace section="thuoc" breadcrumbLabel="Tra cứu thuốc" backTo="/app/thuoc" activeItem={state.data?.dinh_danh.ten_inn ?? hoatChatId}>
      {state.loading && !state.data ? (
        <div className="flex flex-col gap-3" aria-busy="true" aria-label="Đang tải chi tiết thuốc">
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : state.status === 404 ? (
        <EmptyState role="status" title="Không tìm thấy hoạt chất" description={`Không có hoạt chất “${hoatChatId}” trong dữ liệu tra cứu.`} />
      ) : state.error ? (
        <ErrorState title="Không tải được chi tiết thuốc" message={state.error} onRetry={state.reload} />
      ) : state.data ? (
        <DrugDetailView detail={state.data} />
      ) : null}
    </LookupWorkspace>
  )
}
