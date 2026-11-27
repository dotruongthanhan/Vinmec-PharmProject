import { cn } from '@/lib/cn'

export function lopBoCucKhung(chieuRong: number): { dauKhung: string; soHien: string } {
  return {
    dauKhung: cn('min-w-0 flex-1', chieuRong < 480 && 'basis-full'),
    soHien: cn('grid grid-cols-1 gap-2', chieuRong >= 480 && 'sm:grid-cols-2 lg:grid-cols-3'),
  }
}
