import { ArrowLeft, SlidersHorizontal } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ThemeControl } from '@/features/theme/ThemeControl'
import { KhungMinhHoa } from './KhungMinhHoa'
import type { DacTaMinhHoa, TepMauMinhHoa } from './nguPhap'
import meropenemJson from './mau/lieu-meropenem-crcl.json'
import tuongTacJson from './mau/ma-tran-tuong-tac.json'
import thongKeJson from './mau/thong-ke-thang.json'

const MAU_MEROPENEM = meropenemJson as unknown as TepMauMinhHoa
const MAU_TUONG_TAC = tuongTacJson as unknown as TepMauMinhHoa
const MAU_THONG_KE = thongKeJson as unknown as TepMauMinhHoa

function layDanhSachDacTa(tep: TepMauMinhHoa): readonly DacTaMinhHoa[] {
  return Array.isArray(tep.dac_ta) ? tep.dac_ta : [tep.dac_ta as DacTaMinhHoa]
}

/** Trang mẫu minh hoạ tương tác theo ngữ pháp `mh-0` (chỉ hiển thị ở chế độ dev). */
export default function MauMinhHoaPage() {
  const dacTaThongKe = layDanhSachDacTa(MAU_THONG_KE)

  return (
    <div className="min-h-screen bg-canvas text-fg">
      <header className="sticky top-0 z-20 border-b border-line bg-surface">
        <div className="mx-auto flex w-full max-w-[1040px] flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div className="flex min-w-0 items-center gap-2.5">
            <SlidersHorizontal className="size-4 shrink-0 text-primary" strokeWidth={1.75} aria-hidden="true" />
            <h1 className="truncate text-md font-semibold text-fg">
              Mẫu minh hoạ tương tác (ngữ pháp mh-0)
            </h1>
            <Badge tone="ai" variant="soft">
              Chỉ chế độ dev
            </Badge>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            <Button variant="secondary" size="md" asChild className="min-h-8">
              <Link to="/app">
                <ArrowLeft className="size-3.5" strokeWidth={1.75} aria-hidden="true" />
                <span>Về bàn làm việc</span>
              </Link>
            </Button>
            <ThemeControl className="size-8 min-h-8 min-w-8" />
          </div>
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-[1040px] flex-col gap-6 px-4 py-6">
        <p className="text-sm leading-relaxed text-fg-muted">
          Tất cả các hình bên dưới đều được dựng từ cùng một bộ vẽ đọc đặc tả JSON theo ngữ pháp{' '}
          <code className="rounded-sm border border-line bg-surface-muted px-1.5 py-0.5 font-mono text-xs text-fg">
            mh-0
          </code>{' '}
          và bộ dữ liệu tính sẵn từ máy chủ. Không có công thức y khoa nào viết trên trình duyệt.
        </p>

        {/* Mẫu 1: Liều meropenem theo CrCl (DEMO-02) */}
        <KhungMinhHoa
          dacTa={MAU_MEROPENEM.dac_ta}
          boDuLieu={MAU_MEROPENEM.bo_du_lieu}
          congThucHienThi={MAU_MEROPENEM.cong_thuc_hien_thi}
          giaLap={Boolean(MAU_MEROPENEM.gia_lap)}
        />

        {/* Mẫu 2: Ma trận tương tác thuốc */}
        <KhungMinhHoa
          dacTa={MAU_TUONG_TAC.dac_ta}
          boDuLieu={MAU_TUONG_TAC.bo_du_lieu}
          giaLap={Boolean(MAU_TUONG_TAC.gia_lap)}
        />

        {/* Mẫu 3: Thống kê tháng giả lập (2 đặc tả dùng chung bộ dữ liệu) */}
        <div className="flex flex-col gap-4">
          {dacTaThongKe.map((dacTa, idx) => (
            <KhungMinhHoa
              key={`thong-ke-${idx}`}
              dacTa={dacTa}
              boDuLieu={MAU_THONG_KE.bo_du_lieu}
              giaLap={Boolean(MAU_THONG_KE.gia_lap)}
            />
          ))}
        </div>
      </main>
    </div>
  )
}
