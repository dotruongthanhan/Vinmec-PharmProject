import { motion, useReducedMotion } from 'motion/react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { MOCK_AI_ANNOTATIONS, MOCK_CASE_DETAILS, MOCK_SOURCES } from '@/api/mockData'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { RecordId } from '@/components/ui/record-id'
import { ThemeControl } from '@/features/theme/ThemeControl'
import { formatClinicalText } from '@/lib/displayFormat'
import { HeroAnimation } from './HeroAnimation'

interface TraceStep {
  number: string
  actor: 'code' | 'tài liệu' | 'AI' | 'dược sĩ'
  title: string
  detail: string
  meta?: string
}

const FACTOR_STATUS_ROWS: readonly { index: number; name: string; status: 'đã có luật' | 'chưa có luật' }[] =
  [
    { index: 1, name: 'Dị ứng, quá mẫn', status: 'đã có luật' },
    { index: 2, name: 'Trùng lặp thuốc', status: 'đã có luật' },
    { index: 3, name: 'Chỉ định, liều, đường dùng', status: 'chưa có luật' },
    { index: 4, name: 'Tương tác thuốc', status: 'chưa có luật' },
    { index: 5, name: 'Độc tính', status: 'chưa có luật' },
    { index: 6, name: 'Cơ địa và xét nghiệm', status: 'đã có luật' },
  ]

const PRINCIPLES: readonly string[] = [
  'Dược sĩ là người quyết định cuối cùng; hệ thống chỉ gợi ý đối chiếu và lưu nhận định.',
  'Hệ thống chỉ đọc: không ghi vào hồ sơ bệnh án, không tự gửi hay thay đổi y lệnh.',
  'Toàn bộ hồ sơ ca trong bản thử nghiệm này là dữ liệu giả lập, không chứa thông tin người bệnh thật.',
  'Khi thiếu dữ liệu đầu vào, hệ thống nêu rõ trường còn thiếu và không bao giờ tự đánh dấu đạt.',
]

function RevealSection({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  const prefersReducedMotion = useReducedMotion()

  if (prefersReducedMotion) {
    return <section className={className}>{children}</section>
  }

  return (
    <motion.section
      initial={{ opacity: 0, y: 8 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.15 }}
      transition={{ duration: 0.22, ease: 'easeOut' }}
      className={className}
    >
      {children}
    </motion.section>
  )
}

/** Trang chủ giới thiệu sản phẩm trên nền paper, dẫn tới đăng nhập và bàn làm việc. */
export function LandingPage() {
  const demo02 = MOCK_CASE_DETAILS['DEMO-02']
  const demo02Finding = demo02.nhan_dinh.can_chu_y[0]
  const demo02Ai = MOCK_AI_ANNOTATIONS['DEMO-02']['lieu_than_can_chinh|CT-DEMO02-01']
  const demo02Source = MOCK_SOURCES['DEMO-02']['fda_merrem_iv|renal_01']
  const crclMetric = demo02.chi_so[0]
  const latestAbnormal = demo02.tom_tat.bat_thuong[0]

  const traceSteps: TraceStep[] = [
    {
      number: '01',
      actor: 'code',
      title: 'Dữ liệu ca bệnh',
      detail: `${latestAbnormal.ten}: ${latestAbnormal.gia_tri_text} ${formatClinicalText(latestAbnormal.don_vi)} (${latestAbnormal.so_voi_truoc ?? ''}) lúc ${latestAbnormal.thoi_diem_text}.`,
      meta: 'XN-DEMO02-01',
    },
    {
      number: '02',
      actor: 'code',
      title: 'Công thức tính bằng code',
      detail: `${crclMetric.nhan} = ${crclMetric.gia_tri_text} ${crclMetric.don_vi} (từ tuổi 75,0 và cân nặng thực tế 50,0 kg).`,
      meta: crclMetric.tham_khao,
    },
    {
      number: '03',
      actor: 'code',
      title: 'Bộ luật đối chiếu bảng liều',
      detail: formatClinicalText(demo02Finding.nhan_xet),
      meta: `${demo02Finding.muc_do_nhan ?? ''} · ${demo02Finding.ket_luan_nhan}`,
    },
    {
      number: '04',
      actor: 'tài liệu',
      title: 'Đoạn nguồn trích nguyên văn từ nhãn thuốc',
      detail: `${demo02Source.nguon_nhan} (${demo02Source.duong_dan_muc}): "${demo02Ai.trich_dan[0]?.trich_nguyen_van ?? ''}"`,
    },
    {
      number: '05',
      actor: 'AI',
      title: 'AI viết diễn giải và đề xuất',
      detail: demo02Ai.dien_giai_ai ?? '',
    },
    {
      number: '06',
      actor: 'code',
      title: 'Kiểm chứng trích dẫn và con số',
      detail:
        'Đối chiếu nguyên văn đoạn trích với kho nguồn và xác nhận mọi con số trùng khớp dữ liệu ca hoặc kết quả code trước khi hiển thị.',
    },
    {
      number: '07',
      actor: 'dược sĩ',
      title: 'Dược sĩ kiểm chứng và quyết định',
      detail:
        'Xem căn cứ từng bước, mở đoạn nguồn gốc và ghi nhận phản hồi Đồng ý, Bác bỏ hoặc Cần sửa trên từng nhận định.',
    },
  ]

  return (
    <div className="min-h-screen bg-paper text-fg">
      <header className="border-b border-line bg-paper">
        <div className="mx-auto flex min-h-14 max-w-[1120px] flex-wrap items-center justify-between gap-2 px-6 py-2">
          <span className="text-sm font-semibold tracking-tight text-fg">
            Hỗ trợ thẩm định y lệnh
          </span>
          <ThemeControl />
          <Button asChild variant="secondary" size="md">
            <Link to="/dang-nhap">Đăng nhập</Link>
          </Button>
        </div>
      </header>

      <main className="mx-auto flex max-w-[1120px] flex-col gap-16 px-6 py-12 sm:py-16">
        {/* 1. Mở đầu */}
        <section className="grid grid-cols-1 items-start gap-10 lg:grid-cols-12">
          <div className="flex flex-col gap-5 lg:col-span-6">
            <h1 className="font-serif text-[34px] leading-[42px] sm:text-[40px] sm:leading-[48px] font-normal tracking-tight text-fg">
              Hỗ trợ dược sĩ lâm sàng thẩm định y lệnh với căn cứ truy vết đầy đủ.
            </h1>
            <p className="text-base leading-relaxed text-fg-muted">
              Hệ thống gom bối cảnh hồ sơ bệnh án, tính các chỉ số lâm sàng bằng công thức chuẩn
              và đối chiếu y lệnh qua bộ luật. Mọi nhận định đều kèm trích dẫn từ dữ liệu ca và tài
              liệu thuốc để dược sĩ kiểm chứng.
            </p>
            <div className="pt-1">
              <Button asChild variant="primary" size="lg">
                <Link to="/dang-nhap">Đăng nhập để vào bàn làm việc</Link>
              </Button>
            </div>
          </div>

          <div className="lg:col-span-6">
            <HeroAnimation />
          </div>
        </section>

        {/* 2. Một nhận định đi từ đâu ra */}
        <RevealSection className="border-t border-line pt-12">
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
            <div className="lg:col-span-4 space-y-2">
              <h2 className="font-serif text-[26px] leading-[34px] font-normal text-fg">
                Một nhận định đi từ đâu ra
              </h2>
              <p className="text-sm text-fg-muted leading-relaxed">
                Vết truy thẳng trên ca giả lập DEMO-02: từ chỉ số xét nghiệm trong hồ sơ đến kết
                luận của bộ luật, đoạn nguồn nhãn thuốc và quyết định cuối cùng của dược sĩ.
              </p>
            </div>

            <ol className="lg:col-span-8 flex flex-col">
              {traceSteps.map((step, idx) => {
                const isLast = idx === traceSteps.length - 1
                const actorTone =
                  step.actor === 'AI'
                    ? 'ai'
                    : step.actor === 'dược sĩ'
                      ? 'success'
                      : 'neutral'
                return (
                  <li key={step.number} className="relative pl-10 pb-6 last:pb-0">
                    {!isLast ? (
                      <span
                        aria-hidden="true"
                        className="absolute left-3.5 top-7 bottom-0 w-px bg-line-strong"
                      />
                    ) : null}
                    <span
                      aria-hidden="true"
                      className="absolute left-0 top-0.5 flex size-7 items-center justify-center rounded-full border border-line-strong bg-surface font-mono text-xs font-medium text-fg-muted tabular-nums"
                    >
                      {step.number}
                    </span>

                    <div className="flex flex-col gap-1.5 border-b border-line pb-5 last:border-b-0 last:pb-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-sm font-semibold text-fg">{step.title}</h3>
                        <Badge tone={actorTone} variant="outline" className="font-mono text-2xs">
                          {step.actor}
                        </Badge>
                        {step.meta ? <RecordId id={step.meta} className="max-w-full whitespace-normal break-words" /> : null}
                      </div>
                      <p className="text-sm leading-relaxed text-fg-muted">{step.detail}</p>
                    </div>
                  </li>
                )
              })}
            </ol>
          </div>
        </RevealSection>

        {/* 3. Sáu yếu tố thẩm định */}
        <RevealSection className="border-t border-line pt-12">
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
            <div className="lg:col-span-4 space-y-2">
              <h2 className="font-serif text-[26px] leading-[34px] font-normal text-fg">
                Sáu yếu tố thẩm định
              </h2>
              <p className="text-sm text-fg-muted leading-relaxed">
                Phạm vi kiểm tra bằng luật hiện có của hệ thống. Yếu tố chưa có luật được hiển thị
                rõ trạng thái, không bỏ trống hay báo đạt.
              </p>
            </div>

            <div className="lg:col-span-8">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-line-strong text-left text-2xs uppercase tracking-[0.04em] text-fg-subtle">
                    <th className="py-2.5 pr-4 font-medium w-14">STT</th>
                    <th className="py-2.5 pr-4 font-medium">Yếu tố</th>
                    <th className="py-2.5 text-right font-medium">Trạng thái hiện tại</th>
                  </tr>
                </thead>
                <tbody>
                  {FACTOR_STATUS_ROWS.map((row) => (
                    <tr key={row.index} className="border-b border-line">
                      <td className="py-3 pr-4 font-mono text-xs text-fg-subtle tabular-nums">
                        0{row.index}
                      </td>
                      <td className="py-3 pr-4 font-medium text-fg">{row.name}</td>
                      <td className="py-3 text-right">
                        <Badge
                          tone={row.status === 'đã có luật' ? 'success' : 'neutral'}
                          variant={row.status === 'đã có luật' ? 'soft' : 'outline'}
                        >
                          {row.status}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </RevealSection>

        {/* 4. Giới hạn và nguyên tắc */}
        <RevealSection className="border-t border-line pt-12">
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
            <div className="lg:col-span-4">
              <h2 className="font-serif text-[26px] leading-[34px] font-normal text-fg">
                Giới hạn và nguyên tắc
              </h2>
            </div>

            <ol className="lg:col-span-8 divide-y divide-line border-t border-b border-line">
              {PRINCIPLES.map((text, idx) => (
                <li key={idx} className="flex items-baseline gap-4 py-3.5 text-sm">
                  <span className="font-mono text-xs text-fg-subtle tabular-nums shrink-0">
                    0{idx + 1}
                  </span>
                  <span className="text-fg leading-relaxed">{text}</span>
                </li>
              ))}
            </ol>
          </div>
        </RevealSection>
      </main>

      {/* 5. Chân trang */}
      <footer className="border-t border-line bg-paper">
        <div className="mx-auto max-w-[1120px] px-6 py-6 text-xs text-fg-subtle">
          Bản thử nghiệm học thuật trong chương trình Vinmec AI Exploration Sprint (VinUni ×
          Vinmec), Khoa Dược · Năm 2026.
        </div>
      </footer>
    </div>
  )
}

export default LandingPage
