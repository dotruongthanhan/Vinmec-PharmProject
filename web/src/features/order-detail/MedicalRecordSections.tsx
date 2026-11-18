import { ChevronDown, ClipboardList } from 'lucide-react'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import type { ChiTietCa, MedicalOrder } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { RadioGroup, RadioPillItem } from '@/components/ui/radio-group'
import { administrativeDate } from '@/lib/displayFormat'
import { groupEncounters, orderSelectionParams } from '@/lib/medicalRecord'
import { InfoRows, OrderLinesTable, SectionHeading } from './DetailSections'

const ROLES: Record<string, string> = {
  bac_si_dieu_tri: 'Bác sĩ điều trị', bac_si_truc: 'Bác sĩ trực', hoi_chan: 'Hội chẩn',
}
const STATUS: Record<string, { label: string; tone: 'warning' | 'success' | 'neutral' }> = {
  cho_duyet: { label: 'Chờ duyệt', tone: 'warning' },
  da_duyet: { label: 'Đã duyệt', tone: 'success' },
  dang_thuc_hien: { label: 'Đang thực hiện', tone: 'success' },
  ngung: { label: 'Đã ngừng', tone: 'neutral' },
  hoan_tat: { label: 'Hoàn tất', tone: 'neutral' },
}
const TYPES: Record<string, string> = {
  thuong_quy: 'Thường quy', cap_cuu: 'Cấp cứu', khi_can: 'Khi cần', hoi_chan: 'Hội chẩn',
}
const FLOWS: Record<string, string> = { truc_tiep: 'Trực tiếp', hau_kiem: 'Hậu kiểm' }
const missing = 'Chưa ghi nhận'

function OrderStatus({ status }: { status?: string | null }) {
  const value = STATUS[status ?? ''] ?? { label: status ?? missing, tone: 'neutral' }
  return <Badge tone={value.tone} variant="soft">{value.label}</Badge>
}

function encounterLabel(detail: ChiTietCa, id: string, index: number | null): string {
  const start = detail.lich_su_vao_vien?.find((entry) => entry.dot_dieu_tri_id === id)?.thoi_diem_bat_dau
    ?? (detail.quan_ly_nguoi_benh?.dot_dieu_tri_id === id ? detail.quan_ly_nguoi_benh.thoi_diem_bat_dau : null)
  const date = start ? administrativeDate(start).match(/\d{2}\/\d{2}\/\d{4}/)?.[0] : null
  return `Lần vào viện ${index ?? 'chưa ghi nhận'}${date ? ` · ${date}` : ''}`
}

/** Radio trong Popover dùng bàn phím và thứ tự nhóm theo lần vào viện. */
export function OrderChoices({ orders, selectedId, detail, onSelect }: {
  orders: readonly MedicalOrder[]; selectedId?: string; detail: ChiTietCa; onSelect: (id: string) => void
}) {
  return <RadioGroup value={selectedId} onValueChange={onSelect} aria-label="Chọn y lệnh">
    {groupEncounters(orders).map((group) => <div key={group.id} role="group"
      aria-label={encounterLabel(detail, group.id, group.thuTu)} className="flex flex-col gap-2">
      <p className="text-xs font-medium text-fg-subtle">{encounterLabel(detail, group.id, group.thuTu)}</p>
      {group.items.map((order) => <RadioPillItem key={order.y_lenh_id} value={order.y_lenh_id}
        aria-label={`${order.y_lenh_id} · ${STATUS[order.trang_thai ?? '']?.label ?? missing}`}
        className="h-auto w-full flex-col items-start gap-1 rounded-md px-3 py-2 text-left">
        <span className="flex w-full items-center justify-between gap-2">
          <span className="font-mono">{order.y_lenh_id}</span><OrderStatus status={order.trang_thai} />
        </span>
        <span className="text-xs text-fg-subtle">{administrativeDate(order.thoi_diem_ke)}</span>
        <span className="text-xs">{order.dong.slice(0, 2).map((row) => row['Thuốc']).join(' · ') || 'Không có dòng thuốc'}</span>
      </RadioPillItem>)}
    </div>)}
  </RadioGroup>
}

export function OrderSelector({ orders, selected, detail, onSelect }: {
  orders: readonly MedicalOrder[]; selected?: MedicalOrder; detail: ChiTietCa; onSelect: (id: string) => void
}) {
  const [open, setOpen] = useState(false)
  return <section className="flex flex-col gap-2.5" aria-label="Bộ chọn y lệnh">
    <SectionHeading title="Chọn y lệnh" aside={`${orders.length} y lệnh`} />
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild><Button variant="secondary" className="justify-between" aria-label="Chọn y lệnh">
        <span className="flex flex-wrap items-center gap-2"><span className="font-mono">{selected?.y_lenh_id ?? 'Chưa có y lệnh'}</span>
          {selected ? <OrderStatus status={selected.trang_thai} /> : null}</span>
        <ChevronDown className="size-4 shrink-0" aria-hidden="true" />
      </Button></PopoverTrigger>
      <PopoverContent align="start" className="max-h-96 overflow-y-auto" aria-label="Danh sách y lệnh">
        <OrderChoices orders={orders} selectedId={selected?.y_lenh_id} detail={detail}
          onSelect={(id) => { onSelect(id); setOpen(false) }} />
      </PopoverContent>
    </Popover>
  </section>
}

/** Metadata bổ sung áp dụng cho cả trọng tâm và y lệnh lịch sử. */
export function OrderExtraInfo({ order }: { order: MedicalOrder }) {
  return <InfoRows items={[
        { label: 'Trạng thái', value: <OrderStatus status={order.trang_thai} /> },
        { label: 'Loại y lệnh', value: TYPES[order.loai ?? ''] ?? missing },
        { label: 'Người kê', value: ROLES[order.vai_tro_nguoi_ke ?? ''] ?? missing },
        ...(order.ly_do_ngung ? [{ label: 'Lý do ngừng', value: order.ly_do_ngung, wide: true }] : []),
        ...(order.thoi_diem_ngung ? [{ label: 'Thời điểm ngừng', value: administrativeDate(order.thoi_diem_ngung) }] : []),
        ...(order.thay_the_y_lenh_id ? [{ label: 'Y lệnh thay thế', value: order.thay_the_y_lenh_id }] : []),
  ]} />
}

/** Y lệnh lịch sử chỉ hiển thị, không chuyển dòng thuốc sang thẩm định AI. */
export function SelectedOrderDetails({ order }: { order: MedicalOrder }) {
  return <>
    <section aria-label="Thông tin y lệnh" className="flex flex-col gap-2.5">
      <SectionHeading title="Thông tin y lệnh" />
      <InfoRows items={[
        { label: 'Mã y lệnh', value: order.y_lenh_id },
        { label: 'Khoa kê đơn', value: order.khoa_ke_don ?? missing },
        { label: 'Luồng duyệt', value: FLOWS[order.luong_duyet ?? ''] ?? missing },
        { label: 'Thời điểm kê', value: administrativeDate(order.thoi_diem_ke) },
      ]} />
      <OrderExtraInfo order={order} />
    </section>
    <section aria-label="Dòng thuốc y lệnh đang xem" className="flex flex-col gap-2.5">
      <SectionHeading title="Chi tiết y lệnh" aside={`${order.dong.length} dòng thuốc`} />
      <OrderLinesTable table={order} selectedDrug={null} />
    </section>
  </>
}

/** Thẻ phiếu theo ngày và liên kết nội bộ sang đúng y lệnh. */
export function TreatmentSheets({ detail }: { detail: ChiTietCa }) {
  const [params] = useSearchParams()
  const sheets = detail.phieu_dieu_tri ?? []
  if (!sheets.length) return <EmptyState icon={ClipboardList} title="Chưa có phiếu điều trị"
    description="Hồ sơ ngoại trú hoặc ca bệnh này chưa có bản ghi phiếu điều trị." />
  return <div className="flex flex-col gap-6">{groupEncounters(sheets).map((group) => <section key={group.id}
    aria-label={encounterLabel(detail, group.id, group.thuTu)} className="flex flex-col gap-3">
    <SectionHeading title={encounterLabel(detail, group.id, group.thuTu)} aside={`${group.items.length} phiếu`} />
    {group.items.map((sheet) => <Card key={sheet.phieu_dieu_tri_id} className="flex flex-col gap-4 p-4">
      <h4 className="font-medium text-fg">Ngày điều trị {sheet.ngay_dieu_tri} · {administrativeDate(sheet.thoi_diem_lap)}</h4>
      <p className="text-xs text-fg-subtle">{ROLES[sheet.vai_tro_nguoi_lap] ?? sheet.vai_tro_nguoi_lap}</p>
      {[['Diễn biến', sheet.dien_bien], ['Đánh giá', sheet.danh_gia], ['Hướng xử trí', sheet.huong_xu_tri]].map(([label, value]) =>
        <div key={label}><h5 className="text-sm font-medium text-fg">{label}</h5><p className="whitespace-pre-line text-sm text-fg-muted">{value}</p></div>)}
      <InfoRows items={[
        { label: 'Chế độ chăm sóc', value: sheet.che_do_cham_soc ?? missing },
        { label: 'Chế độ ăn', value: sheet.che_do_an },
        { label: 'Dặn dò', value: sheet.dan_do ?? missing, wide: true },
      ]} />
      <div><h5 className="text-sm font-medium text-fg">Theo dõi</h5>
        <ul className="list-disc pl-5 text-sm text-fg-muted">{sheet.theo_doi.map((item, index) => <li key={index}>{item}</li>)}</ul></div>
      <nav aria-label={`Y lệnh trong ngày ${sheet.ngay_dieu_tri}`} className="flex flex-wrap gap-3">
        {sheet.y_lenh_trong_ngay.map((id) => <Link key={id} className="text-xs text-primary underline underline-offset-2"
          to={{ search: `?${orderSelectionParams(params, id)}` }}>{id}</Link>)}
      </nav>
    </Card>)}
  </section>)}</div>
}
