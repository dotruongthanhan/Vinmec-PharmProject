import { CircleCheck, PencilLine, ThumbsDown, ThumbsUp } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { GuiPhanHoi, NhanDinh } from '@/api/types'
import { Button } from '@/components/ui/button'
import { InlineAlert } from '@/components/ui/inline-alert'
import { RadioPillGroup, RadioPillItem } from '@/components/ui/radio-group'
import { toast } from '@/components/ui/toaster'

export interface FeedbackBarProps {
  caId: string
  finding: NhanDinh
  nhomLyDo: readonly string[]
  submitting: boolean
  error: string | null
  onSubmit: (caId: string, payload: GuiPhanHoi) => Promise<boolean>
  onClearError: (caId: string, nhanDinhId: string) => void
}

type PendingAction = 'bac_bo' | 'can_sua' | null

/** Thanh phản hồi trên từng thẻ nhận định: Đồng ý · Bác bỏ · Cần sửa. */
export function FeedbackBar({
  caId,
  finding,
  nhomLyDo,
  submitting,
  error,
  onSubmit,
  onClearError,
}: FeedbackBarProps) {
  const [isEditing, setIsEditing] = useState<boolean>(false)
  const [pendingAction, setPendingAction] = useState<PendingAction>(null)
  const [reasonGroup, setReasonGroup] = useState<string>('')
  const [note, setNote] = useState<string>('')
  const lastToastedErrorRef = useRef<string | null>(null)

  useEffect(() => {
    if (error && error !== lastToastedErrorRef.current) {
      lastToastedErrorRef.current = error
      toast.error('Không ghi được phản hồi', { description: error })
    } else if (!error) {
      lastToastedErrorRef.current = null
    }
  }, [error])

  const recorded = finding.phan_hoi

  const handleAgree = async () => {
    setPendingAction(null)
    const ok = await onSubmit(caId, {
      nhan_dinh_id: finding.nhan_dinh_id,
      phan_hoi: 'dong_y',
      nhom_ly_do: null,
      ly_do: null,
    })
    if (ok) {
      toast.success('Đã ghi nhận phản hồi')
      setIsEditing(false)
      setReasonGroup('')
      setNote('')
    }
  }

  const handleConfirmReason = async () => {
    if (!pendingAction || !reasonGroup) {
      return
    }
    const cleanNote = note.trim()
    const ok = await onSubmit(caId, {
      nhan_dinh_id: finding.nhan_dinh_id,
      phan_hoi: pendingAction,
      nhom_ly_do: reasonGroup,
      ly_do: cleanNote ? cleanNote : null,
    })
    if (ok) {
      toast.success('Đã ghi nhận phản hồi')
      setIsEditing(false)
      setPendingAction(null)
      setReasonGroup('')
      setNote('')
    }
  }

  const handleCancel = () => {
    setPendingAction(null)
    setIsEditing(false)
    setReasonGroup('')
    setNote('')
    onClearError(caId, finding.nhan_dinh_id)
  }

  if (recorded !== null && !isEditing) {
    const details: string[] = []
    if (recorded.nhom_ly_do) {
      details.push(recorded.nhom_ly_do)
    }
    if (recorded.ly_do) {
      details.push(recorded.ly_do)
    }
    const suffix = details.length > 0 ? ` (${details.join(' · ')})` : ''

    return (
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <CircleCheck
            className="size-4 shrink-0 text-success-fg"
            strokeWidth={1.75}
            aria-hidden="true"
          />
          <span className="text-sm font-medium text-fg tabular-nums">
            Đã phản hồi: {recorded.phan_hoi_nhan} · {recorded.thoi_diem_text}
            {suffix}
          </span>
        </div>

        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            setIsEditing(true)
            setPendingAction(null)
            setReasonGroup('')
            setNote('')
            onClearError(caId, finding.nhan_dinh_id)
          }}
        >
          Sửa
        </Button>
      </div>
    )
  }

  const actionLabel = pendingAction === 'bac_bo' ? 'Bác bỏ' : 'Cần sửa'
  const reasonLabelId = `reason-group-${caId}-${finding.nhan_dinh_id}`
  const noteId = `reason-note-${caId}-${finding.nhan_dinh_id}`

  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-fg-muted">Phản hồi:</span>

        <Button
          variant="secondary"
          size="sm"
          loading={submitting && pendingAction === null}
          disabled={submitting}
          iconLeft={<ThumbsUp className="size-3.5" strokeWidth={1.75} />}
          onClick={() => {
            void handleAgree()
          }}
        >
          Đồng ý
        </Button>

        <Button
          variant="secondary"
          size="sm"
          disabled={submitting}
          aria-pressed={pendingAction === 'bac_bo'}
          className={
            pendingAction === 'bac_bo'
              ? 'border-primary-line bg-primary-soft text-primary'
              : undefined
          }
          iconLeft={<ThumbsDown className="size-3.5" strokeWidth={1.75} />}
          onClick={() => {
            setPendingAction('bac_bo')
            onClearError(caId, finding.nhan_dinh_id)
          }}
        >
          Bác bỏ
        </Button>

        <Button
          variant="secondary"
          size="sm"
          disabled={submitting}
          aria-pressed={pendingAction === 'can_sua'}
          className={
            pendingAction === 'can_sua'
              ? 'border-primary-line bg-primary-soft text-primary'
              : undefined
          }
          iconLeft={<PencilLine className="size-3.5" strokeWidth={1.75} />}
          onClick={() => {
            setPendingAction('can_sua')
            onClearError(caId, finding.nhan_dinh_id)
          }}
        >
          Cần sửa
        </Button>

        {isEditing && pendingAction === null ? (
          <Button variant="ghost" size="sm" disabled={submitting} onClick={handleCancel}>
            Huỷ
          </Button>
        ) : null}
      </div>

      {pendingAction !== null ? (
        <div className="flex flex-col gap-2.5 rounded-sm border border-line bg-surface p-3">
          <div className="flex flex-col gap-1.5">
            <span id={reasonLabelId} className="text-xs font-medium text-fg-muted">
              Nhóm lý do cho &ldquo;{actionLabel}&rdquo; (bắt buộc)
            </span>
            <RadioPillGroup
              aria-labelledby={reasonLabelId}
              value={reasonGroup}
              disabled={submitting}
              onValueChange={setReasonGroup}
            >
              {nhomLyDo.map((reason) => (
                <RadioPillItem key={reason} value={reason}>
                  {reason}
                </RadioPillItem>
              ))}
            </RadioPillGroup>
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor={noteId} className="text-xs font-medium text-fg-muted">
              Ghi chú (tuỳ chọn)
            </label>
            <input
              id={noteId}
              type="text"
              className="w-full rounded-sm border border-line-strong bg-surface px-2.5 py-1.5 text-sm text-fg placeholder:text-fg-subtle disabled:opacity-50"
              placeholder="Nhập ghi chú thêm nếu cần…"
              value={note}
              disabled={submitting}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="primary"
              size="sm"
              loading={submitting}
              disabled={!reasonGroup || submitting}
              onClick={() => {
                void handleConfirmReason()
              }}
            >
              Gửi
            </Button>
            <Button variant="ghost" size="sm" disabled={submitting} onClick={handleCancel}>
              Huỷ
            </Button>
          </div>
        </div>
      ) : null}

      {error ? (
        <InlineAlert tone="danger" role="alert">
          Không ghi được phản hồi: {error}
        </InlineAlert>
      ) : null}
    </div>
  )
}
