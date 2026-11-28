import { MessageSquareText } from 'lucide-react'
import { createElement } from 'react'
import type { ChiSo, GuiPhanHoi, NhanDinh } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { InlineAlert } from '@/components/ui/inline-alert'
import { cn } from '@/lib/cn'
import { formatClinicalText, parseLeadingSymbolLabel } from '@/lib/displayFormat'
import { factorIndexOf } from '@/lib/orderDetail'
import {
  ICON_OF_TONE,
  iconOfOrigin,
  toneOfFinding,
  toneOfOrigin,
} from '@/lib/severity'
import type { SemanticTone } from '@/lib/severity'
import type { EvidenceTarget, FeedbackDraft } from '@/lib/uiTypes'
import { AiNote } from './AiNote'
import { EvidenceList } from './EvidenceList'
import { FeedbackBar } from './FeedbackBar'

export interface FindingCardProps {
  caId: string
  finding: NhanDinh
  chiSo: readonly ChiSo[]
  nhomLyDo: readonly string[]
  submitting: boolean
  feedbackError: string | null
  feedbackDraft: FeedbackDraft
  onFeedbackDraftChange: (draft: FeedbackDraft) => void
  onSubmitFeedback: (caId: string, payload: GuiPhanHoi) => Promise<boolean>
  onClearFeedbackError: (caId: string, nhanDinhId: string) => void
  onOpenEvidence: (target: EvidenceTarget, trigger: HTMLButtonElement) => void
  onAskAboutFinding?: (finding: NhanDinh) => void
  onOpenFactor?: () => void
}

const STRIP_BG_CLASS: Record<SemanticTone, string> = {
  danger: 'bg-danger-solid',
  warning: 'bg-warning-solid',
  missing: 'bg-missing-solid',
  offlabel: 'bg-offlabel-solid',
  success: 'bg-success-solid',
  ai: 'bg-ai-solid',
  neutral: 'bg-neutral-solid',
}

/** Thẻ nhận định phân tầng đọc dọc kèm dải mức độ, nguồn gốc, khối AI, căn cứ và phản hồi. */
export function FindingCard({
  caId,
  finding,
  chiSo,
  nhomLyDo,
  submitting,
  feedbackError,
  feedbackDraft,
  onFeedbackDraftChange,
  onSubmitFeedback,
  onClearFeedbackError,
  onOpenEvidence,
  onAskAboutFinding,
  onOpenFactor,
}: FindingCardProps) {
  const factorIndex = onOpenFactor ? factorIndexOf(finding.yeu_to) : null
  const tone = toneOfFinding({
    ket_luan_ma: finding.ket_luan_ma,
    muc_do_ma: finding.muc_do_ma,
  })
  const ToneIcon = ICON_OF_TONE[tone]

  const originTone = toneOfOrigin(finding.nguon_goc_ma)
  const originIconEl = createElement(iconOfOrigin(finding.nguon_goc_ma), {
    className: 'size-3.5',
    strokeWidth: 1.75,
  })

  const isAiAdded = finding.nguon_goc_ma !== 'luat'
  const isUnverified = finding.nguon_goc_ma === 'ai_chua_kiem_chung'

  const ketLuanClean = parseLeadingSymbolLabel(finding.ket_luan_nhan).text
  const hasSeparateSeverity =
    Boolean(finding.muc_do_nhan) && finding.muc_do_nhan !== finding.ket_luan_nhan
  const badgeLabel = hasSeparateSeverity
    ? parseLeadingSymbolLabel(finding.muc_do_nhan ?? '').text
    : ketLuanClean

  const originLabel =
    finding.nguon_goc_nhan ||
    (finding.nguon_goc_ma === 'ai_da_kiem_chung'
      ? 'AI · đã kiểm chứng'
      : finding.nguon_goc_ma === 'ai_chua_kiem_chung'
        ? 'AI · chưa kiểm chứng'
        : 'Luật')

  const drugLabel = finding.thuoc ? formatClinicalText(finding.thuoc) : 'Toàn đơn'

  return (
    <article
      id={`finding-${finding.nhan_dinh_id}`}
      aria-label={`Nhận định: ${drugLabel} — ${badgeLabel}`}
      className={cn(
        'relative rounded-md border bg-surface',
        isAiAdded ? 'border-dashed border-ai-line' : 'border-line',
      )}
    >
      <span
        className={cn('absolute inset-y-0 left-0 w-[3px] rounded-l-md', STRIP_BG_CLASS[tone])}
        aria-hidden="true"
      />

      <div className="flex flex-wrap items-center justify-between gap-2 px-4 pt-3.5 pb-2 pl-5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge
            tone={tone}
            variant="soft"
            icon={<ToneIcon className="size-3.5" strokeWidth={1.75} />}
          >
            {badgeLabel}
          </Badge>
          {hasSeparateSeverity ? (
            <span className="text-sm font-medium text-fg-muted">{ketLuanClean}</span>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-fg-subtle">{finding.yeu_to}</span>
          <Badge
            tone={originTone}
            variant={isUnverified ? 'outline' : 'soft'}
            className={isUnverified ? 'border-dashed' : undefined}
            icon={originIconEl}
          >
            {originLabel}
          </Badge>
          {onOpenFactor && factorIndex !== null ? (
            <Button variant="ghost" size="sm" onClick={onOpenFactor}>
              Mở mục {factorIndex}
            </Button>
          ) : null}
          {onAskAboutFinding ? (
            <Button
              variant="ghost"
              size="sm"
              iconLeft={<MessageSquareText className="size-3.5" strokeWidth={1.75} />}
              onClick={() => onAskAboutFinding(finding)}
            >
              Hỏi về mục này
            </Button>
          ) : null}
        </div>
      </div>

      <div className="flex flex-col gap-2.5 px-4 pb-3 pl-5">
        <div className="text-sm font-medium text-fg-muted">{drugLabel}</div>

        <p className="text-base font-medium leading-relaxed text-fg whitespace-pre-wrap">
          {formatClinicalText(finding.nhan_xet)}
        </p>

        {finding.thong_tin_con_thieu.length > 0 ? (
          <InlineAlert tone="missing">
            Còn thiếu: {finding.thong_tin_con_thieu.join(', ')} (kiểm tra hồ sơ lâm sàng để bổ sung)
          </InlineAlert>
        ) : null}

        {finding.nguon_goc_ma === 'luat' ? (
          <AiNote
            dienGiaiAi={finding.dien_giai_ai ? formatClinicalText(finding.dien_giai_ai) : null}
            deXuatAi={finding.de_xuat_ai ? formatClinicalText(finding.de_xuat_ai) : null}
          />
        ) : null}

        <EvidenceList
          key={`ev-${caId}-${finding.nhan_dinh_id}`}
          caId={caId}
          canCu={finding.can_cu}
          trichDan={finding.trich_dan}
          chiSo={chiSo}
          defaultExpanded={finding.muc_do_ma === 'nghiem_trong'}
          onOpenEvidence={onOpenEvidence}
        />
      </div>

      <div className="rounded-b-md border-t border-line bg-surface-muted/40 px-4 py-2.5 pl-5">
        <FeedbackBar
          draft={feedbackDraft}
          onDraftChange={onFeedbackDraftChange}
          key={`fb-${caId}-${finding.nhan_dinh_id}`}
          caId={caId}
          finding={finding}
          nhomLyDo={nhomLyDo}
          submitting={submitting}
          error={feedbackError}
          onSubmit={onSubmitFeedback}
          onClearError={onClearFeedbackError}
        />
      </div>
    </article>
  )
}
