import type { TrichDan } from '@/api/types'
import { Button } from '@/components/ui/button'
import type { EvidenceTarget } from '@/lib/uiTypes'

export interface SourceListProps {
  caId: string
  trichDan: readonly TrichDan[]
  onOpenEvidence: (target: EvidenceTarget, trigger: HTMLButtonElement) => void
}

/** Nhóm nguồn tài liệu trích dẫn từ AI đặt bên trong phần Căn cứ. */
export function SourceList({ caId, trichDan, onOpenEvidence }: SourceListProps) {
  if (trichDan.length === 0) {
    return null
  }

  return (
    <div className="flex flex-col gap-2 border-t border-line pt-2.5">
      <div className="text-xs font-semibold text-fg-muted tabular-nums">
        Nguồn tài liệu ({trichDan.length})
      </div>
      <ol className="flex flex-col gap-3">
        {trichDan.map((td) => (
          <li key={`${td.so}-${td.doan_trich_id}`} className="flex flex-col gap-1.5">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <span className="min-w-[200px] flex-1 text-sm font-medium text-fg tabular-nums">
                {td.so}. {td.nhan}
              </span>
              <Button
                variant="ghost"
                size="sm"
                className="shrink-0"
                onClick={(e) =>
                  onOpenEvidence(
                    {
                      kind: 'source',
                      caId,
                      doanTrichId: td.doan_trich_id,
                      nhan: td.nhan,
                      trichNguyenVan: td.trich_nguyen_van,
                    },
                    e.currentTarget,
                  )
                }
              >
                Mở nguồn
              </Button>
            </div>
            <blockquote className="border-l-2 border-line-strong pl-3 text-sm text-fg-muted whitespace-pre-wrap">
              {td.trich_nguyen_van}
            </blockquote>
          </li>
        ))}
      </ol>
    </div>
  )
}
