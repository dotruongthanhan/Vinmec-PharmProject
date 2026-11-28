import { SectionHeading } from './DetailSections'
import { InteractionMatrix } from './InteractionMatrix'
import type { InteractionMatrixProps } from './InteractionMatrix'

export interface InteractionSectionProps extends InteractionMatrixProps {
  /** Trạng thái mở của riêng lưới ma trận; mặc định đóng. */
  open: boolean
  onOpenChange: (open: boolean) => void
}

/**
 * Yếu tố 4 · Tương tác thuốc: mục luôn hiện (danh sách thuốc, thẻ chi tiết từng cặp);
 * chú giải luôn hiện; chỉ lưới ma trận thu gọn sau một nút chevron riêng.
 */
export function InteractionSection({ open, onOpenChange, ...matrixProps }: InteractionSectionProps) {
  return (
    <div className="flex flex-col gap-2.5">
      <SectionHeading title="Yếu tố 4 · Tương tác thuốc" aside="Đối chiếu từng cặp thuốc" />
      <InteractionMatrix {...matrixProps} matrixToggle={{ open, onOpenChange }} />
    </div>
  )
}
