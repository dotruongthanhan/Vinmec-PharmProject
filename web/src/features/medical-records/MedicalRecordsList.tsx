import { FileText } from 'lucide-react'
import type { DongHangDoi } from '@/api/types'
import { EmptyState } from '@/components/ui/empty-state'
import { ErrorState, QueueSkeleton } from '@/features/states/StateViews'
import { filterOrders, getOrderPatientCode } from '@/lib/orders'
import { administrativeDate } from '@/lib/displayFormat'

export interface MedicalRecordsListProps {
  cases: readonly DongHangDoi[]
  loading: boolean
  error: string | null
  searchQuery: string
  onRetry: () => void
  onOpenRecord: (caId: string) => void
}

/** Danh sách hồ sơ; hành chính tùy chọn để giữ tương thích bản demo cũ. */
export function MedicalRecordsList({
  cases, loading, error, searchQuery, onRetry, onOpenRecord,
}: MedicalRecordsListProps) {
  const records = filterOrders(cases, { type: 'group', group: 'tat_ca' }, searchQuery)

  return (
    <section className="mx-auto flex w-full max-w-[1200px] flex-col gap-4 px-3 py-5 sm:px-6" aria-labelledby="medical-records-title">
      <h1 id="medical-records-title" className="text-lg font-semibold text-fg">Hồ sơ bệnh án</h1>
      {loading ? <QueueSkeleton /> : error ? (
        <ErrorState title="Không tải được hồ sơ bệnh án" message={error} onRetry={onRetry} />
      ) : records.length === 0 ? (
        <EmptyState
          role="status"
          icon={FileText}
          title={searchQuery.trim() ? 'Không tìm thấy hồ sơ phù hợp' : 'Chưa có hồ sơ bệnh án'}
        />
      ) : (
        <div className="overflow-hidden rounded-md border border-line bg-surface shadow-xs">
          <table className="w-full table-fixed text-left text-sm">
            <caption className="sr-only">Danh sách hồ sơ bệnh án</caption>
            <thead className="sticky top-0 z-10 bg-surface-muted text-2xs font-medium uppercase tracking-wide text-fg-subtle">
              <tr>
                {['Mã BN', 'Người bệnh (giới, tuổi)', 'Ngày sinh', 'Khoa', 'Chẩn đoán chính', 'Thời điểm vào viện', 'Số y lệnh'].map((label) => (
                  <th key={label} scope="col" className={`break-words px-2 py-3 ${label === 'Số y lệnh' ? 'text-right' : ''}`}>{label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {records.map((record) => (
                <tr
                  key={record.ca_id}
                  onClick={() => onOpenRecord(record.ca_id)}
                  className="h-9 cursor-pointer border-t border-line text-fg hover:bg-surface-hover focus-within:bg-surface-hover"
                >
                  <td className="break-words px-2 py-2 font-mono text-xs">
                    <button
                      type="button"
                      aria-label={`Mở hồ sơ ${getOrderPatientCode(record) || record.ca_id}`}
                      onClick={(event) => {
                        event.stopPropagation()
                        onOpenRecord(record.ca_id)
                      }}
                      className="cursor-pointer rounded-sm text-left text-primary underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                    >
                      {getOrderPatientCode(record) || '—'}
                    </button>
                  </td>
                  <td className="break-words px-2 py-2">
                    {record.ho_ten ? <span className="block font-medium">{record.ho_ten.toLocaleUpperCase('vi-VN')}</span> : null}
                    {record.nguoi_benh_tom_tat?.trim() || 'Chưa ghi nhận'}
                  </td>
                  <td className="break-words px-2 py-2 tabular-nums">{administrativeDate(record.ngay_sinh)}</td>
                  <td className="break-words px-2 py-2">{record.khoa.trim() || '—'}</td>
                  <td className="break-words px-2 py-2">{record.chan_doan_chinh || 'Chưa ghi nhận'}</td>
                  <td className="break-words px-2 py-2 tabular-nums">{administrativeDate(record.vao_vien)}</td>
                  <td className="px-2 py-2 text-right tabular-nums">{record.so_y_lenh ?? 'Chưa ghi nhận'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
