import { fileURLToPath, URL } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { loadEnv } from 'vite'
import { defineConfig } from 'vitest/config'

/**
 * Khi chạy `npm run dev`, nếu web chưa khai VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY,
 * lấy SUPABASE_URL và SUPABASE_ANON_KEY (khóa công khai) từ `.env` gốc của kho.
 * Chỉ hai khóa này, không bao giờ đưa SUPABASE_SERVICE_ROLE_KEY hay khóa bí mật khác ra trình duyệt.
 * Khi build (Vercel), không chạm vào: dùng biến VITE_* đã cấu hình trên Vercel.
 */
function devSupabaseDefines(mode: string, command: string): Record<string, string> {
  if (command !== 'serve') {
    return {}
  }
  const own = loadEnv(mode, process.cwd(), 'VITE_')
  const root = loadEnv(mode, fileURLToPath(new URL('..', import.meta.url)), '')
  const defines: Record<string, string> = {}
  if (!own.VITE_SUPABASE_URL && root.SUPABASE_URL) {
    defines['import.meta.env.VITE_SUPABASE_URL'] = JSON.stringify(root.SUPABASE_URL)
  }
  if (!own.VITE_SUPABASE_ANON_KEY && root.SUPABASE_ANON_KEY) {
    defines['import.meta.env.VITE_SUPABASE_ANON_KEY'] = JSON.stringify(root.SUPABASE_ANON_KEY)
  }
  return defines
}

export default defineConfig(({ mode, command }) => ({
  plugins: [react(), tailwindcss()],
  define: devSupabaseDefines(mode, command),
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'node',
  },
}))
