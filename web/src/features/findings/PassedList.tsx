import { CircleCheck } from 'lucide-react'
import type { NhanDinh } from '@/api/types'
import { Card } from '@/components/ui/card'
import {
  Collapsible,
  CollapsibleChevron,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
  DataTable,
  DataTableBody,
  DataTableCell,
  DataTableHead,
  DataTableHeader,
  DataTableRow,
} from '@/components/ui/data-table'
import { parseLeadingSymbolLabel } from '@/lib/displayFormat'

export interface PassedListProps {
  passed: readonly NhanDinh[]
}

/** Khối các mục đạt đóng sẵn, bấm mở dạng bảng gọn để dược sĩ biết hệ thống đã kiểm gì. */
export function PassedList({ passed }: PassedListProps) {
  return (
    <Card>
      <Collapsible defaultOpen={false}>
        <CollapsibleTrigger className="flex w-full cursor-pointer items-center gap-2 px-4 py-3 text-left text-sm font-medium text-fg transition-colors duration-120 hover:bg-surface-hover">
          <CollapsibleChevron />
          <CircleCheck
            className="size-4 shrink-0 text-success-fg"
            strokeWidth={1.75}
            aria-hidden="true"
          />
          <span className="tabular-nums">Các mục đạt ({passed.length})</span>
        </CollapsibleTrigger>

        <CollapsibleContent className="border-t border-line p-4">
          {passed.length > 0 ? (
            <DataTable>
              <DataTableHeader>
                <tr>
                  <DataTableHead>Thuốc</DataTableHead>
                  <DataTableHead>Yếu tố</DataTableHead>
                  <DataTableHead>Nhận xét</DataTableHead>
                  <DataTableHead>Kết luận</DataTableHead>
                  <DataTableHead>Nguồn</DataTableHead>
                </tr>
              </DataTableHeader>
              <DataTableBody>
                {passed.map((item) => {
                  const ketLuanClean = parseLeadingSymbolLabel(item.ket_luan_nhan).text
                  return (
                    <DataTableRow key={item.nhan_dinh_id}>
                      <DataTableCell className="font-medium">
                        {item.thuoc || 'Toàn đơn'}
                      </DataTableCell>
                      <DataTableCell className="text-fg-muted">{item.yeu_to}</DataTableCell>
                      <DataTableCell className="whitespace-pre-wrap">{item.nhan_xet}</DataTableCell>
                      <DataTableCell className="whitespace-nowrap">
                        <span className="inline-flex items-center gap-1.5 font-medium text-success-fg">
                          <CircleCheck
                            className="size-3.5 shrink-0 text-success-fg"
                            strokeWidth={1.75}
                            aria-hidden="true"
                          />
                          <span>{ketLuanClean}</span>
                        </span>
                      </DataTableCell>
                      <DataTableCell className="whitespace-nowrap text-fg-muted">
                        {item.nguon_goc_nhan}
                      </DataTableCell>
                    </DataTableRow>
                  )
                })}
              </DataTableBody>
            </DataTable>
          ) : (
            <p className="text-xs text-fg-subtle">Không có mục đạt.</p>
          )}
        </CollapsibleContent>
      </Collapsible>
    </Card>
  )
}
