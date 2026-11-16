import {
  ArrowDown,
  CircleHelp,
  FileQuestion,
  OctagonAlert,
  TriangleAlert,
} from 'lucide-react'
import type { DiUngMa, DinhDanhCa } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/cn'
import { parseLeadingSymbolLabel, parseTrendValue } from '@/lib/displayFormat'
import { iconOfAllergy, toneOfAllergy } from '@/lib/severity'
import type { LucideIcon } from 'lucide-react'

const ALLERGY_ICONS: Record<DiUngMa, LucideIcon> = {
  co_di_ung: iconOfAllergy('co_di_ung'),
  khong_di_ung_da_hoi: iconOfAllergy('khong_di_ung_da_hoi'),
  chua_co_thong_tin: iconOfAllergy('chua_co_thong_tin'),
}

export interface CaseHeaderProps {
  dinhDanh: DinhDanhCa
}

/** Thành phần A: Dải định danh ca bệnh dính trên cùng vùng nội dung khi cuộn. */
export function CaseHeader({ dinhDanh }: CaseHeaderProps) {
  const { dem } = dinhDanh
  const parsedCrcl = parseTrendValue(dinhDanh.crcl)
  const allergyTone = toneOfAllergy(dinhDanh.di_ung_ma)
  const AllergyIcon = ALLERGY_ICONS[dinhDanh.di_ung_ma] ?? ALLERGY_ICONS.chua_co_thong_tin
  const allergyText = parseLeadingSymbolLabel(dinhDanh.di_ung_text).text

  const allergyVariant = dinhDanh.di_ung_ma === 'khong_di_ung_da_hoi' ? 'outline' : 'soft'
  const allergyClassName =
    dinhDanh.di_ung_ma === 'co_di_ung'
      ? 'font-semibold'
      : dinhDanh.di_ung_ma === 'chua_co_thong_tin'
        ? 'uppercase font-semibold tracking-[0.02em] border-dashed'
        : 'font-normal'

  return (
    <section
      className="sticky top-0 z-20 shrink-0 min-h-[56px] bg-surface border-b border-line px-5 py-2 flex items-center justify-between gap-x-3 gap-y-1.5 flex-wrap"
      aria-label="Định danh ca bệnh"
    >
      <div className="flex items-center gap-2.5 flex-wrap min-w-0">
        <span className="text-md font-semibold text-fg">{dinhDanh.ca_id}</span>
        <span className="text-fg-disabled" aria-hidden="true">
          ·
        </span>
        <span className="text-sm text-fg-muted">{dinhDanh.gioi_tuoi}</span>
        <span className="text-fg-disabled" aria-hidden="true">
          ·
        </span>
        <span className="text-sm text-fg-muted tabular-nums">{dinhDanh.can_nang}</span>
        <span className="text-fg-disabled" aria-hidden="true">
          ·
        </span>
        <span className="text-sm text-fg-muted">{dinhDanh.khoa_loai}</span>

        <span
          className={cn(
            'inline-flex items-center gap-1.5 rounded-sm border px-2 py-0.5 text-xs',
            dinhDanh.crcl_bat_thuong
              ? 'bg-danger-bg border-danger-line text-danger-fg'
              : 'bg-surface-muted border-line text-fg',
          )}
        >
          <span
            className={cn(
              'text-2xs uppercase tracking-[0.04em] font-medium',
              dinhDanh.crcl_bat_thuong ? 'text-danger-fg' : 'text-fg-subtle',
            )}
          >
            CrCl
          </span>
          <span className="tabular-nums font-semibold">{parsedCrcl.text}</span>
          {dinhDanh.crcl_bat_thuong ? (
            <>
              <ArrowDown className="size-3.5 shrink-0" strokeWidth={1.75} aria-hidden="true" />
              <span className="sr-only">bất thường</span>
            </>
          ) : null}
        </span>

        <Badge
          tone={allergyTone}
          variant={allergyVariant}
          icon={<AllergyIcon className="size-3.5" strokeWidth={1.75} />}
          className={cn('whitespace-normal text-left', allergyClassName)}
        >
          {allergyText}
        </Badge>
      </div>

      <div
        className="flex items-center gap-1.5 flex-wrap tabular-nums"
        aria-label="Số lượng nhận định theo mức"
      >
        <Badge
          tone={dem.nghiem_trong > 0 ? 'danger' : 'neutral'}
          variant={dem.nghiem_trong > 0 ? 'soft' : 'outline'}
          icon={<OctagonAlert className="size-3.5" strokeWidth={1.75} />}
          className={cn('tabular-nums', dem.nghiem_trong === 0 && 'text-fg-subtle border-line')}
        >
          {dem.nghiem_trong} nghiêm trọng
        </Badge>
        <Badge
          tone={dem.can_luu_y > 0 ? 'warning' : 'neutral'}
          variant={dem.can_luu_y > 0 ? 'soft' : 'outline'}
          icon={<TriangleAlert className="size-3.5" strokeWidth={1.75} />}
          className={cn('tabular-nums', dem.can_luu_y === 0 && 'text-fg-subtle border-line')}
        >
          {dem.can_luu_y} cần lưu ý
        </Badge>
        <Badge
          tone={dem.thieu_du_lieu > 0 ? 'missing' : 'neutral'}
          variant={dem.thieu_du_lieu > 0 ? 'soft' : 'outline'}
          icon={<CircleHelp className="size-3.5" strokeWidth={1.75} />}
          className={cn('tabular-nums', dem.thieu_du_lieu === 0 && 'text-fg-subtle border-line')}
        >
          {dem.thieu_du_lieu} thiếu dữ liệu
        </Badge>
        {dem.ngoai_hdsd > 0 ? (
          <Badge
            tone="offlabel"
            variant="soft"
            icon={<FileQuestion className="size-3.5" strokeWidth={1.75} />}
            className="tabular-nums"
          >
            {dem.ngoai_hdsd} ngoài HDSD
          </Badge>
        ) : null}
      </div>
    </section>
  )
}
