import { ArrowDown, ArrowUp, Pill, TriangleAlert } from 'lucide-react'
import type { RefObject } from 'react'
import type { BangYLenh, ChiTietCa } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  DataTable,
  DataTableBody,
  DataTableCell,
  DataTableHead,
  DataTableHeader,
  DataTableRow,
} from '@/components/ui/data-table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { parseLeadingSymbolLabel, parseTrendValue } from '@/lib/displayFormat'
import { ICON_OF_TONE } from '@/lib/severity'
import type { DetailTabId } from '@/lib/uiTypes'

export interface DetailTabsProps {
  chiTiet: ChiTietCa['chi_tiet']
  activeTab: DetailTabId
  onTabChange: (tab: DetailTabId) => void
  sectionRef?: RefObject<HTMLElement | null>
  onJumpToFindings?: () => void
}

function OrderTable({
  table,
  onJumpToFindings,
}: {
  table: BangYLenh
  onJumpToFindings?: () => void
}) {
  if (table.dong.length === 0) {
    return <p className="text-sm text-fg-subtle">Không có dòng thuốc.</p>
  }

  return (
    <DataTable>
      <DataTableHeader>
        <tr>
          {table.cot.map((col) => (
            <DataTableHead key={col}>{col}</DataTableHead>
          ))}
        </tr>
      </DataTableHeader>
      <DataTableBody>
        {table.dong.map((row, rowIdx) => {
          const hasFinding = Boolean(row['Nhận định'] && row['Nhận định'].trim() !== '')
          return (
            <DataTableRow
              key={`order-row-${rowIdx}`}
              tone={hasFinding ? 'primary' : undefined}
            >
              {table.cot.map((col) => {
                const cell = row[col] ?? '—'
                if (col === 'Nhận định' && hasFinding) {
                  const parsed = parseLeadingSymbolLabel(cell)
                  const ToneIcon = parsed.tone ? ICON_OF_TONE[parsed.tone] : TriangleAlert
                  if (onJumpToFindings) {
                    return (
                      <DataTableCell key={col}>
                        <Button
                          variant="soft"
                          size="sm"
                          iconLeft={
                            <ToneIcon
                              className={
                                parsed.tone === 'success'
                                  ? 'size-3.5 text-success-fg'
                                  : 'size-3.5 text-warning-fg'
                              }
                              strokeWidth={1.75}
                            />
                          }
                          onClick={onJumpToFindings}
                        >
                          {parsed.text}
                        </Button>
                      </DataTableCell>
                    )
                  }
                  return (
                    <DataTableCell key={col}>
                      <Badge
                        tone={parsed.tone ?? 'warning'}
                        variant="soft"
                        icon={<ToneIcon className="size-3.5" strokeWidth={1.75} />}
                      >
                        {parsed.text}
                      </Badge>
                    </DataTableCell>
                  )
                }

                return (
                  <DataTableCell
                    key={col}
                    className="tabular-nums whitespace-pre-wrap"
                  >
                    {cell}
                  </DataTableCell>
                )
              })}
            </DataTableRow>
          )
        })}
      </DataTableBody>
    </DataTable>
  )
}

/** Thành phần E: 4 thẻ chi tiết hồ sơ (Y lệnh, Xét nghiệm, Vi sinh, Diễn biến). */
export function DetailTabs({
  chiTiet,
  activeTab,
  onTabChange,
  sectionRef,
  onJumpToFindings,
}: DetailTabsProps) {
  return (
    <section ref={sectionRef} aria-label="Chi tiết hồ sơ">
      <Card>
        <Tabs
          value={activeTab}
          onValueChange={(value) => onTabChange(value as DetailTabId)}
        >
          <TabsList aria-label="Các thẻ chi tiết hồ sơ">
            <TabsTrigger value="y_lenh">Y lệnh</TabsTrigger>
            <TabsTrigger value="xet_nghiem">Xét nghiệm</TabsTrigger>
            <TabsTrigger value="vi_sinh">Vi sinh</TabsTrigger>
            <TabsTrigger value="dien_bien">Diễn biến</TabsTrigger>
          </TabsList>

          <TabsContent value="y_lenh" className="p-4">
            <p className="text-xs text-fg-muted tabular-nums mb-3">
              {chiTiet.y_lenh.thong_tin_text}
            </p>
            <OrderTable
              table={chiTiet.y_lenh.cho_duyet}
              onJumpToFindings={onJumpToFindings}
            />

            {chiTiet.y_lenh.dang_dung ? (
              <>
                <h3 className="text-sm font-semibold text-fg mt-5 mb-2">
                  Thuốc đang dùng và đã ngừng
                </h3>
                <OrderTable
                  table={chiTiet.y_lenh.dang_dung}
                  onJumpToFindings={onJumpToFindings}
                />
              </>
            ) : null}
          </TabsContent>

          <TabsContent value="xet_nghiem" className="p-4">
            {chiTiet.xet_nghiem.length > 0 ? (
              <DataTable>
                <DataTableHeader>
                  <tr>
                    <DataTableHead>Thời điểm</DataTableHead>
                    <DataTableHead>Xét nghiệm</DataTableHead>
                    <DataTableHead align="right">Giá trị</DataTableHead>
                    <DataTableHead>Đơn vị</DataTableHead>
                    <DataTableHead>Khoảng tham chiếu</DataTableHead>
                    <DataTableHead>Bất thường</DataTableHead>
                  </tr>
                </DataTableHeader>
                <DataTableBody>
                  {chiTiet.xet_nghiem.map((xn, idx) => {
                    const parsedValue = parseTrendValue(xn.gia_tri_text)
                    const parsedDir = parseTrendValue(xn.huong ?? '')
                    const direction = parsedDir.direction ?? parsedValue.direction
                    const dirIcon =
                      direction === 'up' ? (
                        <ArrowUp className="size-3.5" strokeWidth={1.75} />
                      ) : direction === 'down' ? (
                        <ArrowDown className="size-3.5" strokeWidth={1.75} />
                      ) : undefined

                    return (
                      <DataTableRow
                        key={`${xn.ten}-${xn.thoi_diem_text}-${idx}`}
                        tone={xn.ngoai_nguong ? 'danger' : undefined}
                      >
                        <DataTableCell className="tabular-nums whitespace-nowrap">
                          {xn.thoi_diem_text}
                        </DataTableCell>
                        <DataTableCell>{xn.ten}</DataTableCell>
                        <DataTableCell
                          align="right"
                          className={
                            xn.ngoai_nguong ? 'font-semibold text-danger-fg' : undefined
                          }
                        >
                          {parsedValue.text}
                        </DataTableCell>
                        <DataTableCell className="text-fg-subtle">
                          {xn.don_vi}
                        </DataTableCell>
                        <DataTableCell className="tabular-nums">
                          {xn.khoang_tham_chieu}
                        </DataTableCell>
                        <DataTableCell>
                          {xn.ngoai_nguong ? (
                            <Badge tone="danger" variant="soft" icon={dirIcon}>
                              Ngoài ngưỡng
                              {direction === 'up' ? (
                                <span className="sr-only"> (Tăng)</span>
                              ) : direction === 'down' ? (
                                <span className="sr-only"> (Giảm)</span>
                              ) : null}
                            </Badge>
                          ) : null}
                        </DataTableCell>
                      </DataTableRow>
                    )
                  })}
                </DataTableBody>
              </DataTable>
            ) : (
              <p className="text-sm text-fg-subtle">Chưa có kết quả xét nghiệm.</p>
            )}
          </TabsContent>

          <TabsContent value="vi_sinh" className="p-4">
            {chiTiet.vi_sinh.length > 0 ? (
              <div className="flex flex-col gap-3">
                {chiTiet.vi_sinh.map((vs, idx) => (
                  <Card
                    key={`${vs.benh_pham}-${vs.lay_mau_text}-${idx}`}
                    className="p-3.5 flex flex-col gap-3"
                  >
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-fg tabular-nums">
                      <span>
                        <span className="text-fg-subtle">Bệnh phẩm: </span>
                        <span className="font-medium text-fg">{vs.benh_pham}</span>
                      </span>
                      <span>
                        <span className="text-fg-subtle">Lấy mẫu: </span>
                        <span>{vs.lay_mau_text}</span>
                      </span>
                      <span>
                        <span className="text-fg-subtle">Vi khuẩn: </span>
                        <span className="font-medium text-fg">
                          {vs.vi_khuan || 'Chưa phân lập vi khuẩn'}
                        </span>
                      </span>
                    </div>

                    {vs.khang_sinh_do.length > 0 ? (
                      <DataTable>
                        <DataTableHeader>
                          <tr>
                            <DataTableHead>Hoạt chất</DataTableHead>
                            <DataTableHead>Kết quả</DataTableHead>
                            <DataTableHead align="right">MIC</DataTableHead>
                            <DataTableHead>Đơn hiện tại</DataTableHead>
                          </tr>
                        </DataTableHeader>
                        <DataTableBody>
                          {vs.khang_sinh_do.map((ksd, kIdx) => (
                            <DataTableRow
                              key={`${ksd.hoat_chat}-${kIdx}`}
                              tone={ksd.dang_ke ? 'primary' : undefined}
                            >
                              <DataTableCell
                                className={ksd.dang_ke ? 'font-semibold text-fg' : undefined}
                              >
                                {ksd.hoat_chat}
                              </DataTableCell>
                              <DataTableCell>{ksd.ket_qua}</DataTableCell>
                              <DataTableCell align="right">{ksd.mic_text}</DataTableCell>
                              <DataTableCell>
                                {ksd.dang_ke ? (
                                  <Badge
                                    tone="ai"
                                    variant="soft"
                                    icon={<Pill className="size-3.5" strokeWidth={1.75} />}
                                  >
                                    Đang kê
                                  </Badge>
                                ) : null}
                              </DataTableCell>
                            </DataTableRow>
                          ))}
                        </DataTableBody>
                      </DataTable>
                    ) : null}
                  </Card>
                ))}
              </div>
            ) : (
              <p className="text-sm text-fg-subtle">Chưa có kết quả vi sinh.</p>
            )}
          </TabsContent>

          <TabsContent value="dien_bien" className="p-4">
            {chiTiet.dien_bien.length > 0 ? (
              <div className="flex flex-col gap-3">
                {chiTiet.dien_bien.map((db, idx) => (
                  <div
                    key={`${db.thoi_diem_text}-${idx}`}
                    className="flex flex-col gap-1.5 pb-3 border-b border-line last:border-b-0 last:pb-0"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs text-fg-subtle tabular-nums">
                        {db.thoi_diem_text}
                      </span>
                      <Badge tone="neutral" variant="soft">
                        {db.loai_nhan}
                      </Badge>
                    </div>
                    <p className="whitespace-pre-wrap text-sm text-fg">{db.noi_dung}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-fg-subtle">Chưa có ghi nhận diễn biến.</p>
            )}
          </TabsContent>
        </Tabs>
      </Card>
    </section>
  )
}
