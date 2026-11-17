import { Sparkles } from 'lucide-react'

export interface AiNoteProps {
  dienGiaiAi: string | null
  deXuatAi: string | null
}

/** Khối diễn giải và đề xuất đã kiểm chứng của AI trên thẻ nhận định của luật. */
export function AiNote({ dienGiaiAi, deXuatAi }: AiNoteProps) {
  const hasDienGiai = typeof dienGiaiAi === 'string' && dienGiaiAi.trim() !== ''
  const hasDeXuat = typeof deXuatAi === 'string' && deXuatAi.trim() !== ''

  if (!hasDienGiai && !hasDeXuat) {
    return null
  }

  return (
    <div className="flex flex-col gap-2 rounded-sm border border-ai-line bg-ai-bg p-3">
      <div className="flex items-center gap-1.5">
        <Sparkles className="size-3.5 shrink-0 text-ai-fg" strokeWidth={1.75} aria-hidden="true" />
        <span className="text-xs font-semibold text-ai-fg">AI · đã kiểm chứng</span>
      </div>

      {hasDienGiai ? (
        <div className="flex items-baseline gap-3">
          <span className="w-[72px] shrink-0 text-xs font-medium text-fg-subtle">
            Diễn giải
          </span>
          <p className="min-w-0 flex-1 text-sm text-fg whitespace-pre-wrap">{dienGiaiAi}</p>
        </div>
      ) : null}

      {hasDeXuat ? (
        <div className="flex items-baseline gap-3">
          <span className="w-[72px] shrink-0 text-xs font-medium text-fg-subtle">
            Đề xuất
          </span>
          <p className="min-w-0 flex-1 text-sm text-fg whitespace-pre-wrap">{deXuatAi}</p>
        </div>
      ) : null}
    </div>
  )
}
