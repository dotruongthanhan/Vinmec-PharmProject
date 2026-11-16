import type { ComponentPropsWithRef } from 'react'
import { cn } from '@/lib/cn'

export interface DataTableProps extends ComponentPropsWithRef<'table'> {
  wrapperClassName?: string
}

/** Bảng dữ liệu lâm sàng có vùng cuộn ngang dọc và đầu cột dính. */
export function DataTable({
  ref,
  className,
  wrapperClassName,
  ...props
}: DataTableProps) {
  return (
    <div
      className={cn(
        'relative w-full overflow-auto rounded-md border border-line bg-surface',
        wrapperClassName,
      )}
    >
      <table
        ref={ref}
        className={cn('w-full border-collapse text-sm', className)}
        {...props}
      />
    </div>
  )
}

export type DataTableHeaderProps = ComponentPropsWithRef<'thead'>

/** Nhóm đầu bảng dính cố định khi cuộn dọc. */
export function DataTableHeader({
  ref,
  className,
  ...props
}: DataTableHeaderProps) {
  return (
    <thead
      ref={ref}
      className={cn('sticky top-0 z-10 bg-surface-muted', className)}
      {...props}
    />
  )
}

export type DataTableBodyProps = ComponentPropsWithRef<'tbody'>

/** Phần thân chứa các dòng dữ liệu của bảng. */
export function DataTableBody({
  ref,
  className,
  ...props
}: DataTableBodyProps) {
  return <tbody ref={ref} className={cn('bg-surface', className)} {...props} />
}

export interface DataTableRowProps extends ComponentPropsWithRef<'tr'> {
  tone?: 'danger' | 'primary'
}

/** Dòng dữ liệu bảng, không kẻ sọc, hỗ trợ nhấn tông khi bất thường hoặc đang chọn. */
export function DataTableRow({
  ref,
  className,
  tone,
  ...props
}: DataTableRowProps) {
  return (
    <tr
      ref={ref}
      className={cn(
        'h-9 border-b border-line transition-colors duration-120 last:border-b-0 hover:bg-surface-hover',
        tone === 'danger' && 'bg-danger-bg/60 hover:bg-danger-bg',
        tone === 'primary' && 'bg-primary-soft/70 hover:bg-primary-soft',
        className,
      )}
      {...props}
    />
  )
}

export interface DataTableHeadProps extends ComponentPropsWithRef<'th'> {
  align?: 'left' | 'right'
}

/** Ô tiêu đề cột hỗ trợ canh trái hoặc phải cho cột số. */
export function DataTableHead({
  ref,
  className,
  align = 'left',
  scope,
  ...props
}: DataTableHeadProps) {
  return (
    <th
      ref={ref}
      scope={scope ?? 'col'}
      className={cn(
        'sticky top-0 z-10 border-b border-line bg-surface-muted px-3 py-2 text-left text-2xs font-medium uppercase tracking-[0.04em] text-fg-subtle whitespace-nowrap',
        align === 'right' && 'text-right',
        className,
      )}
      {...props}
    />
  )
}

export interface DataTableCellProps extends ComponentPropsWithRef<'td'> {
  align?: 'left' | 'right'
}

/** Ô nội dung bảng hỗ trợ canh phải và chữ số đều cột khi cần. */
export function DataTableCell({
  ref,
  className,
  align = 'left',
  ...props
}: DataTableCellProps) {
  return (
    <td
      ref={ref}
      className={cn(
        'px-3 py-2 align-top text-fg',
        align === 'right' ? 'text-right tabular-nums' : 'text-left',
        className,
      )}
      {...props}
    />
  )
}
