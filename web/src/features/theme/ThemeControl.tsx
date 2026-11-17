import { Monitor, Moon, Sun } from 'lucide-react'
import { IconButton } from '@/components/ui/icon-button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { SegmentedControl, SegmentedControlItem } from '@/components/ui/segmented-control'
import { cn } from '@/lib/cn'
import { parseThemePreference } from '@/lib/theme'
import { useTheme } from './useTheme'

/** Ba lựa chọn màu; thanh bên thu gọn dùng nút biểu tượng có chú giải. */
export function ThemeControl({ collapsed = false, inSidebar = false }: { collapsed?: boolean; inSidebar?: boolean }) {
  const { preference, setPreference } = useTheme()
  const options = (
    <SegmentedControl value={preference} onValueChange={(value) => setPreference(parseThemePreference(value))}
      aria-label="Chế độ sáng tối"
      className={cn(inSidebar && !collapsed && 'border-ink-line bg-ink-soft')}>
      {(['light', 'dark', 'system'] as const).map((option, index) => (
        <SegmentedControlItem key={option} value={option}
          className={cn('min-h-7 px-2', inSidebar && !collapsed && 'text-ink-muted hover:text-ink-fg data-[state=on]:bg-ink data-[state=on]:text-ink-fg')}>
          {['Sáng', 'Tối', 'Theo hệ thống'][index]}
        </SegmentedControlItem>
      ))}
    </SegmentedControl>
  )
  if (!collapsed) return options
  const Icon = preference === 'system' ? Monitor : preference === 'dark' ? Moon : Sun
  return (
    <Popover>
      <PopoverTrigger asChild>
        <IconButton aria-label="Chọn chế độ sáng tối" icon={<Icon className="size-4" strokeWidth={1.75} />}
          className="self-center text-ink-muted hover:bg-ink-soft hover:text-ink-fg" />
      </PopoverTrigger>
      <PopoverContent side="right" className="w-auto p-2">{options}</PopoverContent>
    </Popover>
  )
}
