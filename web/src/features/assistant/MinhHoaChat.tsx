import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import type { KhoiMinhHoa } from '@/api/types'

const KhungMinhHoa = lazy(() => import('@/features/minh-hoa/KhungMinhHoa').then((m) => ({ default: m.KhungMinhHoa })))

export function MinhHoaChat({ khoi, cu }: { khoi: KhoiMinhHoa; cu: boolean }) {
  const [mo, setMo] = useState(false)
  const [thay, setThay] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (typeof IntersectionObserver === 'undefined') {
      const timer = window.setTimeout(() => setThay(true), 0)
      return () => window.clearTimeout(timer)
    }
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) setThay(true)
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])
  const title = typeof khoi.dac_ta?.tieu_de === 'string' ? khoi.dac_ta.tieu_de : 'Hình minh hoạ'
  return (
    <div ref={ref} className="min-w-0 w-full">
      {cu && !mo ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-line bg-surface p-3">
          <span className="text-sm font-semibold text-fg">{title}</span>
          <button type="button" className="min-h-8 rounded-sm border border-line-strong px-3 text-sm text-primary" onClick={() => setMo(true)}>Mở hình</button>
        </div>
      ) : thay ? (
        <Suspense fallback={<div className="h-80 rounded-md border border-line" aria-label="Đang tải hình minh hoạ" />}>
          <KhungMinhHoa dacTa={khoi.dac_ta} boDuLieu={khoi.bo_du_lieu} congThucHienThi={khoi.dac_ta?.cong_thuc && khoi.cong_thuc_hien_thi ? { [khoi.dac_ta.cong_thuc]: khoi.cong_thuc_hien_thi } : undefined} />
        </Suspense>
      ) : <div className="h-80 rounded-md border border-line" aria-label="Hình minh hoạ chưa hiển thị" />}
    </div>
  )
}
