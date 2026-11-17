import { CircleHelp, Keyboard, LogIn, LogOut, ShieldCheck, SlidersHorizontal } from 'lucide-react'
import type { CheDo } from '@/api/types'
import { Badge } from '@/components/ui/badge'
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
import { Kbd } from '@/components/ui/kbd'
import { ThemeControl } from '@/features/theme/ThemeControl'

export interface SettingsDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  userEmail: string | null
  isDemoMode: boolean
  cheDo: CheDo | null
  sidebarCollapsed: boolean
  assistantCollapsed: boolean
  onToggleSidebarCollapse: () => void
  onToggleAssistantCollapse: () => void
  onSignIn: () => void
  onSignOut: () => void
}

/** Hộp thoại Cài đặt (Ctrl+,): giao diện sáng/tối, bố cục cột, thông tin phiên và đăng nhập/đăng xuất. */
export function SettingsDialog({
  open,
  onOpenChange,
  userEmail,
  isDemoMode,
  cheDo,
  sidebarCollapsed,
  assistantCollapsed,
  onToggleSidebarCollapse,
  onToggleAssistantCollapse,
  onSignIn,
  onSignOut,
}: SettingsDialogProps) {
  const isAiEnabled = Boolean(cheDo?.co_llm)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent variant="record" aria-describedby="settings-dialog-desc">
        <DialogHeader>
          <DialogTitle>Cài đặt bàn làm việc</DialogTitle>
          <DialogDescription id="settings-dialog-desc">
            Tuỳ chỉnh giao diện, bố cục làm việc, phím tắt và tài khoản phiên hiện tại.
          </DialogDescription>
        </DialogHeader>

        <DialogBody className="flex flex-col gap-5">
          {/* 1. Giao diện sáng/tối */}
          <section className="flex flex-col gap-2.5">
            <div className="flex items-center justify-between gap-4">
              <div className="min-w-0">
                <h3 className="text-sm font-semibold text-fg">Chế độ hiển thị</h3>
                <p className="text-xs text-fg-subtle">
                  Bấm biểu tượng để chuyển giữa nền sáng (mặt trời) và nền tối (mặt trăng).
                </p>
              </div>
              <ThemeControl />
            </div>
          </section>

          <hr className="border-line" />

          {/* 2. Không gian 3 cột */}
          <section className="flex flex-col gap-2.5">
            <div className="flex items-center gap-1.5 text-sm font-semibold text-fg">
              <SlidersHorizontal className="size-4 text-fg-subtle" strokeWidth={1.75} aria-hidden="true" />
              <span>Bố cục bàn làm việc</span>
            </div>
            <div className="flex flex-col gap-2 rounded-md border border-line bg-surface p-3">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-sm font-medium text-fg">Thanh điều hướng bên trái</div>
                  <div className="text-xs text-fg-subtle">Thu gọn về dải biểu tượng 56 px hoặc mở rộng 248 px.</div>
                </div>
                <Button variant="secondary" size="sm" onClick={onToggleSidebarCollapse}>
                  {sidebarCollapsed ? 'Mở rộng' : 'Thu gọn'}
                </Button>
              </div>
              <hr className="border-line" />
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-sm font-medium text-fg">Khung Trợ lý AI bên phải</div>
                  <div className="text-xs text-fg-subtle">Bật hoặc ẩn khung hỏi đáp và đối chiếu đoạn nguồn.</div>
                </div>
                <Button variant="secondary" size="sm" onClick={onToggleAssistantCollapse}>
                  {assistantCollapsed ? 'Hiển thị' : 'Thu gọn'}
                </Button>
              </div>
            </div>
          </section>

          <hr className="border-line" />

          {/* 3. Tài khoản & Chế độ hệ thống */}
          <section className="flex flex-col gap-2.5">
            <div className="flex items-center gap-1.5 text-sm font-semibold text-fg">
              <ShieldCheck className="size-4 text-fg-subtle" strokeWidth={1.75} aria-hidden="true" />
              <span>Tài khoản và chế độ thẩm định</span>
            </div>
            <div className="flex flex-col gap-3 rounded-md border border-line bg-surface p-3.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="text-xs text-fg-subtle">Phiên hiện tại</div>
                  <div className="truncate text-sm font-medium text-fg">
                    {isDemoMode
                      ? 'Chế độ demo (chưa xác thực tài khoản)'
                      : (userEmail ?? 'Tài khoản dược sĩ')}
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-1.5">
                  <Badge tone="neutral" variant="soft">
                    Dữ liệu giả lập
                  </Badge>
                  <Badge tone={isAiEnabled ? 'ai' : 'neutral'} variant="soft">
                    {isAiEnabled ? 'AI bật' : 'Chỉ bộ luật'}
                  </Badge>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2 border-t border-line pt-3">
                {isDemoMode ? (
                  <>
                    <Button
                      variant="primary"
                      size="sm"
                      iconLeft={<LogIn className="size-3.5" strokeWidth={1.75} />}
                      onClick={() => {
                        onOpenChange(false)
                        onSignIn()
                      }}
                    >
                      Đăng nhập tài khoản
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      iconLeft={<LogOut className="size-3.5" strokeWidth={1.75} />}
                      onClick={() => {
                        onOpenChange(false)
                        onSignOut()
                      }}
                    >
                      Thoát chế độ demo
                    </Button>
                  </>
                ) : (
                  <Button
                    variant="secondary"
                    size="sm"
                    iconLeft={<LogOut className="size-3.5" strokeWidth={1.75} />}
                    onClick={() => {
                      onOpenChange(false)
                      onSignOut()
                    }}
                  >
                    Đăng xuất
                  </Button>
                )}
              </div>
            </div>
          </section>

          <hr className="border-line" />

          {/* 4. Phím tắt và trợ giúp */}
          <section className="flex flex-col gap-2">
            <div className="flex items-center gap-1.5 text-sm font-semibold text-fg">
              <Keyboard className="size-4 text-fg-subtle" strokeWidth={1.75} aria-hidden="true" />
              <span>Phím tắt và lưu ý sử dụng</span>
            </div>
            <div className="flex flex-col gap-1.5 rounded-md border border-line bg-surface p-3 text-xs text-fg-muted">
              <div className="flex items-center justify-between gap-2">
                <span>Tìm kiếm y lệnh, thuốc, khoa</span>
                <Kbd>Ctrl K</Kbd>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span>Mở nhanh Cài đặt</span>
                <Kbd>Ctrl ,</Kbd>
              </div>
              <div className="mt-1 flex items-start gap-1.5 border-t border-line pt-2 text-fg-subtle">
                <CircleHelp className="mt-0.5 size-3.5 shrink-0" strokeWidth={1.75} aria-hidden="true" />
                <span>
                  Kết quả bộ luật và diễn giải AI chỉ hỗ trợ tra cứu; dược sĩ lâm sàng kiểm chứng trước khi quyết định.
                </span>
              </div>
            </div>
          </section>
        </DialogBody>

        <DialogFooter>
          <Button variant="secondary" size="sm" onClick={() => onOpenChange(false)}>
            Đóng
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
