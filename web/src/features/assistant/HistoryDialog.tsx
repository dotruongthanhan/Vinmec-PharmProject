import { ArrowRight, MessagesSquare } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { GLOBAL_CHAT_ID } from '@/state/useChat'
import type { ChatMessage } from '@/state/useChat'

/** Một dòng trong thẻ Lịch sử: hội thoại của một y lệnh hoặc hỏi đáp chung. */
export interface AssistantHistoryEntry {
  chatId: string
  title: string
  /** Người bệnh tóm tắt (giới tính, tuổi). */
  patient: string
  khoa: string
  moTa: string
  thuoc: readonly string[]
  thoiDiemKe: string
  lastAt: string | null
  messages: readonly ChatMessage[]
}

function InfoRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[110px_minmax(0,1fr)] gap-3 py-1.5 text-sm">
      <dt className="text-fg-muted">{label}</dt>
      <dd className="min-w-0 text-fg">{children}</dd>
    </div>
  )
}

/** Hộp thoại chi tiết một hội thoại: thông tin y lệnh và người bệnh, lịch sử trò chuyện, nút mở y lệnh. */
export function HistoryDialog({
  entry,
  onOpenChange,
  onGoTo,
}: {
  entry: AssistantHistoryEntry | null
  onOpenChange: (open: boolean) => void
  onGoTo: (chatId: string) => void
}) {
  const isGlobal = entry?.chatId === GLOBAL_CHAT_ID
  return (
    <Dialog open={entry !== null} onOpenChange={onOpenChange}>
      <DialogContent variant="record" aria-describedby="history-dialog-desc">
        {entry ? (
          <>
            <DialogHeader>
              <DialogTitle className={isGlobal ? undefined : 'font-mono'}>{entry.title}</DialogTitle>
              <DialogDescription id="history-dialog-desc">
                {isGlobal
                  ? 'Hội thoại hỏi đáp chung trên cả danh sách y lệnh.'
                  : 'Thông tin y lệnh, người bệnh và hội thoại với trợ lý.'}
              </DialogDescription>
            </DialogHeader>
            <DialogBody className="flex flex-col gap-5">
              {isGlobal ? null : (
                <section aria-label="Thông tin y lệnh và người bệnh">
                  <h3 className="mb-1 text-sm font-semibold text-fg">Thông tin y lệnh</h3>
                  <dl className="divide-y divide-line rounded-md border border-line px-3">
                    <InfoRow label="Người bệnh">{entry.patient || 'Chưa có'}</InfoRow>
                    <InfoRow label="Khoa">{entry.khoa || 'Chưa có'}</InfoRow>
                    <InfoRow label="Thời điểm kê">{entry.thoiDiemKe || 'Chưa có'}</InfoRow>
                    <InfoRow label="Thuốc">
                      {entry.thuoc.length > 0 ? entry.thuoc.join(', ') : 'Chưa có'}
                    </InfoRow>
                    {entry.moTa ? <InfoRow label="Mô tả">{entry.moTa}</InfoRow> : null}
                  </dl>
                </section>
              )}

              <section aria-label="Lịch sử trò chuyện" className="flex flex-col gap-2">
                <h3 className="flex items-center gap-1.5 text-sm font-semibold text-fg">
                  <MessagesSquare className="size-4 text-fg-subtle" strokeWidth={1.75} aria-hidden="true" />
                  Trò chuyện với trợ lý
                </h3>
                {entry.messages.length === 0 ? (
                  <p className="text-sm text-fg-muted">Chưa có tin nhắn.</p>
                ) : (
                  <ol className="flex flex-col gap-2">
                    {entry.messages.map((msg) =>
                      msg.vai === 'nguoi_dung' ? (
                        <li
                          key={msg.id}
                          className="max-w-[85%] self-end rounded-md border border-line bg-surface-muted px-3 py-2 text-sm text-fg"
                        >
                          <span className="mb-0.5 block text-2xs font-semibold text-fg-subtle">Dược sĩ</span>
                          {msg.noi_dung}
                        </li>
                      ) : (
                        <li
                          key={msg.id}
                          className="max-w-[92%] self-start rounded-md border border-primary-line bg-primary-soft/40 px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap text-fg"
                        >
                          <span className="mb-0.5 block text-2xs font-semibold text-fg-subtle">Trợ lý</span>
                          {msg.tra_loi.noi_dung}
                        </li>
                      ),
                    )}
                  </ol>
                )}
              </section>
            </DialogBody>
            <DialogFooter>
              <Button variant="secondary" onClick={() => onOpenChange(false)}>
                Đóng
              </Button>
              <Button
                variant="primary"
                onClick={() => {
                  onGoTo(entry.chatId)
                  onOpenChange(false)
                }}
              >
                {isGlobal ? 'Mở hỏi đáp chung' : 'Đi đến y lệnh'}
                <ArrowRight className="size-4" strokeWidth={1.75} aria-hidden="true" />
              </Button>
            </DialogFooter>
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
