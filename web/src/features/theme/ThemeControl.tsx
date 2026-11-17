import { Moon, Sun } from 'lucide-react'
import { IconButton } from '@/components/ui/icon-button'
import { useTheme } from './useTheme'

/** Một nút duy nhất: đang sáng hiện mặt trời, bấm sang tối thì đổi thành mặt trăng, và ngược lại. */
export function ThemeControl({ className }: { className?: string }) {
  const { theme, setPreference } = useTheme()
  const isDark = theme === 'dark'
  const Icon = isDark ? Moon : Sun
  return (
    <IconButton
      aria-label={isDark ? 'Đang ở chế độ tối, bấm để chuyển sang sáng' : 'Đang ở chế độ sáng, bấm để chuyển sang tối'}
      tooltip={isDark ? 'Chế độ tối' : 'Chế độ sáng'}
      tooltipSide="bottom"
      onClick={() => setPreference(isDark ? 'light' : 'dark')}
      icon={<Icon className="size-4" strokeWidth={1.75} />}
      className={className}
    />
  )
}
