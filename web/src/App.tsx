import { MotionConfig } from 'motion/react'
import { AppRouter } from '@/app/router'
import { Toaster } from '@/components/ui/toaster'
import { TooltipProvider } from '@/components/ui/tooltip'
import { AuthProvider } from '@/features/auth/AuthProvider'
import { ThemeProvider } from '@/features/theme/ThemeProvider'

/** Gốc ứng dụng: cung cấp xác thực, tooltip, thông báo nổi, cấu hình chuyển động và định tuyến. */
export function App() {
  return (
    <MotionConfig reducedMotion="user">
      <ThemeProvider>
        <AuthProvider>
          <TooltipProvider>
            <AppRouter />
            <Toaster />
          </TooltipProvider>
        </AuthProvider>
      </ThemeProvider>
    </MotionConfig>
  )
}

export default App
