import {
  ArrowRight,
  ArrowUp,
  BookOpenText,
  Calculator,
  CircleCheck,
  FileSearch,
  MessagesSquare,
  MinusCircle,
  ShieldCheck,
} from 'lucide-react'
import { motion, useReducedMotion } from 'motion/react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { MOCK_AI_ANNOTATIONS, MOCK_CASE_DETAILS, MOCK_SOURCES } from '@/api/mockData'
import { Button } from '@/components/ui/button'
import { AppLogo } from '@/components/AppLogo'
import { ThemeControl } from '@/features/theme/ThemeControl'
import { cn } from '@/lib/cn'
import { formatClinicalText } from '@/lib/displayFormat'
import { HeroCarousel } from './HeroCarousel'
import type { HeroSlide } from './HeroCarousel'

interface TraceStep {
  actor: 'Code' | 'Tài liệu' | 'AI' | 'Dược sĩ'
  title: string
  detail: string
}

const FACTORS: readonly { index: number; name: string; note: string; ready: boolean }[] = [
  { index: 1, name: 'Dị ứng, quá mẫn', note: 'Tiền sử dị ứng và dị ứng chéo cùng nhóm', ready: true },
  { index: 2, name: 'Trùng lặp thuốc', note: 'Trùng hoạt chất giữa các dòng đang hiệu lực', ready: true },
  { index: 3, name: 'Chỉ định, liều, đường dùng', note: 'Đối chiếu kháng sinh với kết quả vi sinh', ready: true },
  { index: 4, name: 'Tương tác thuốc', note: 'Sàng lọc từng cặp thuốc theo DDInter', ready: true },
  { index: 5, name: 'Độc tính', note: 'Độc thận, kéo dài QT, khoảng điều trị hẹp, độc gan', ready: true },
  { index: 6, name: 'Cơ địa và xét nghiệm', note: 'Thận, gan, ngưỡng xét nghiệm, thuốc–bệnh', ready: true },
  { index: 7, name: 'Lịch dùng và yếu tố khác', note: 'Lịch dùng, kháng sinh quản lý, trường bắt buộc', ready: true },
]

const STATS: readonly { value: string; label: string }[] = [
  { value: '7', label: 'yếu tố thẩm định trên một màn hình' },
  { value: '50', label: 'nhãn thuốc FDA trong kho nguồn' },
  { value: '4', label: 'trạng thái kết luận, không có "đạt" khi thiếu dữ liệu' },
  { value: '0', label: 'con số do AI tự tính' },
]

const PRINCIPLES: readonly { title: string; text: string }[] = [
  {
    title: 'Dược sĩ quyết định',
    text: 'Hệ thống gợi ý điểm cần đối chiếu và lưu phản hồi. Không duyệt thay, không gửi tin.',
  },
  {
    title: 'Chỉ đọc',
    text: 'Không ghi vào hồ sơ bệnh án, không thay đổi y lệnh trên bất kỳ hệ thống nào.',
  },
  {
    title: 'Thiếu thì nói thiếu',
    text: 'Khi thiếu dữ liệu đầu vào, hệ thống nêu rõ trường còn thiếu và không bao giờ ghi đạt.',
  },
  {
    title: 'Dữ liệu giả lập',
    text: 'Toàn bộ hồ sơ trong bản thử nghiệm là giả lập, không chứa thông tin người bệnh thật.',
  },
]

function Reveal({ children, className }: { children: ReactNode; className?: string }) {
  const prefersReducedMotion = useReducedMotion()
  if (prefersReducedMotion) {
    return <div className={className}>{children}</div>
  }
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.15 }}
      transition={{ duration: 0.4, ease: 'easeOut' }}
      className={className}
    >
      {children}
    </motion.div>
  )
}

function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <p className="flex items-center gap-2 text-xs font-semibold tracking-[0.14em] text-primary uppercase">
      <span className="h-px w-6 bg-primary" aria-hidden="true" />
      {children}
    </p>
  )
}

function BentoTile({
  icon,
  title,
  text,
  className,
  children,
}: {
  icon: ReactNode
  title: string
  text: string
  className?: string
  children: ReactNode
}) {
  return (
    <div
      className={cn(
        'flex flex-col overflow-hidden rounded-lg border border-line bg-surface transition-colors duration-180 hover:border-line-strong',
        className,
      )}
    >
      <div className="flex flex-1 items-center justify-center border-b border-line bg-surface-muted/50 p-6">
        {children}
      </div>
      <div className="flex flex-col gap-1.5 p-6">
        <div className="flex items-center gap-2 text-fg">
          <span className="text-primary">{icon}</span>
          <h3 className="text-md font-semibold tracking-tight">{title}</h3>
        </div>
        <p className="text-sm leading-relaxed text-fg-muted">{text}</p>
      </div>
    </div>
  )
}

/** Cột chữ chuẩn của mỗi slide trên banner trang chủ. */
function SlideText({
  badge,
  title,
  text,
  secondaryHref,
  secondaryLabel,
  note,
}: {
  badge: string
  title: ReactNode
  text: string
  secondaryHref: string
  secondaryLabel: string
  note: string
}) {
  return (
    <>
      <span className="inline-flex w-fit items-center gap-2 rounded-full border border-ink-line bg-ink/50 px-3 py-1 text-xs font-medium text-ink-fg backdrop-blur-sm">
        <span className="size-1.5 rounded-full bg-success-solid" aria-hidden="true" />
        {badge}
      </span>
      <h1 className="landing-display">{title}</h1>
      <p className="max-w-[540px] text-md leading-relaxed text-ink-fg/85">{text}</p>
      <div className="flex flex-wrap items-center gap-3">
        <Button asChild variant="primary" size="lg">
          <Link to="/dang-nhap">
            Vào bàn làm việc
            <ArrowRight className="size-4" strokeWidth={2} aria-hidden="true" />
          </Link>
        </Button>
        <Button
          asChild
          variant="secondary"
          size="lg"
          className="border-ink-line bg-ink/40 text-ink-fg backdrop-blur-sm hover:bg-ink-soft"
        >
          <a href={secondaryHref}>{secondaryLabel}</a>
        </Button>
      </div>
      <p className="flex items-center gap-2 text-xs text-ink-muted">
        <ShieldCheck className="size-4 text-primary" strokeWidth={1.75} aria-hidden="true" />
        {note}
      </p>
    </>
  )
}

const ACTOR_CLASS: Record<TraceStep['actor'], string> = {
  Code: 'bg-neutral-bg text-neutral-fg',
  'Tài liệu': 'bg-primary-soft text-primary',
  AI: 'bg-ai-bg text-ai-fg',
  'Dược sĩ': 'bg-success-bg text-success-fg',
}

/** Trang chủ giới thiệu sản phẩm, dẫn tới đăng nhập và bàn làm việc. */
export function LandingPage() {
  const demo02 = MOCK_CASE_DETAILS['DEMO-02']
  const finding = demo02.nhan_dinh.can_chu_y[0]
  const ai = MOCK_AI_ANNOTATIONS['DEMO-02']['lieu_than_can_chinh|CT-DEMO02-01']
  const source = MOCK_SOURCES['DEMO-02']['fda_merrem_iv|renal_01']
  const crcl = demo02.chi_so[0]
  const lab = demo02.tom_tat.bat_thuong[0]
  const labValue = `${formatClinicalText(lab.gia_tri_text)} ${formatClinicalText(lab.don_vi)}`

  const traceSteps: TraceStep[] = [
    {
      actor: 'Code',
      title: 'Đọc dữ liệu ca',
      detail: `${lab.ten} ${labValue} (${lab.so_voi_truoc ?? ''}).`,
    },
    {
      actor: 'Code',
      title: 'Tính chỉ số bằng công thức',
      detail: `${crcl.nhan} = ${crcl.gia_tri_text} ${crcl.don_vi}, có trích dẫn bài báo gốc.`,
    },
    {
      actor: 'Code',
      title: 'Bộ luật đối chiếu',
      detail: formatClinicalText(finding.nhan_xet),
    },
    {
      actor: 'Tài liệu',
      title: 'Lấy đoạn nguồn nguyên văn',
      detail: `${source.nguon_nhan}: "${ai.trich_dan[0]?.trich_nguyen_van ?? ''}"`,
    },
    {
      actor: 'AI',
      title: 'AI viết diễn giải',
      detail: ai.dien_giai_ai ?? '',
    },
    {
      actor: 'Code',
      title: 'Kiểm chứng trước khi hiển thị',
      detail:
        'Mọi trích dẫn phải khớp nguyên văn kho nguồn, mọi con số phải khớp dữ liệu ca hoặc kết quả code.',
    },
    {
      actor: 'Dược sĩ',
      title: 'Dược sĩ quyết định',
      detail: 'Mở căn cứ, mở đoạn nguồn, rồi ghi Đồng ý, Bác bỏ hoặc Cần sửa cho từng nhận định.',
    },
  ]

  const heroSlides: HeroSlide[] = [
    {
      id: 'tham-dinh',
      image: { src: '/landing/tham-dinh.jpg', alt: 'Hai dược sĩ làm việc trên máy tính trong hiệu thuốc', flip: false, position: '50% 40%', pushRight: true },
      content: (
        <SlideText
          badge="Bản thử nghiệm học thuật · Bệnh viện X"
          title={
            <>
              Mỗi y lệnh, một bản thẩm định <span className="landing-accent">có căn cứ.</span>
            </>
          }
          text="Hồ sơ bệnh án, xét nghiệm, chỉ số chức năng thận và tài liệu thuốc được gom về một màn hình. Mỗi nhận định đi kèm dữ liệu và đoạn nguồn để dược sĩ lâm sàng kiểm chứng trước khi quyết định."
          secondaryHref="#cach-hoat-dong"
          secondaryLabel="Xem cách hoạt động"
          note="Dữ liệu 100% giả lập. Hệ thống chỉ đọc, dược sĩ là người quyết định."
        />
      ),
          },
    {
      id: 'bay-yeu-to',
      image: { src: '/landing/bay-yeu-to.jpg', alt: 'Nhân viên y tế lấy thuốc tại trạm cấp phát có máy tính', flip: true, position: '50% 50%' },
      content: (
        <SlideText
          badge="Bảy yếu tố thẩm định"
          title={
            <>
              Bảy yếu tố, <span className="landing-accent">một màn hình.</span>
            </>
          }
          text="Dị ứng, trùng lặp, chỉ định và liều, tương tác, độc tính, cơ địa và lịch dùng được rà theo cùng một trình tự cho mọi y lệnh. Yếu tố nào chưa có luật thì ghi rõ là chưa kiểm."
          secondaryHref="#bay-yeu-to"
          secondaryLabel="Xem chi tiết bảy yếu tố"
          note="Không có chữ “đạt” khi thiếu dữ liệu đầu vào."
        />
      ),
          },
    {
      id: 'hoi-dap',
      image: { src: '/landing/hoi-dap.jpg', alt: 'Phòng xét nghiệm với các máy phân tích và nhân viên đang làm việc', flip: false, position: '30% 50%' },
      content: (
        <SlideText
          badge="Trợ lý hỏi đáp theo ca"
          title={
            <>
              Hỏi đáp, <span className="landing-accent">có trích dẫn nguồn.</span>
            </>
          }
          text="Hỏi về hồ sơ, liều dùng hay tài liệu thuốc ngay trên y lệnh đang mở, hoặc hỏi chung trên cả danh sách. Mỗi câu trả lời gắn số trích dẫn mở được dữ liệu ca và đoạn nguồn nguyên văn."
          secondaryHref="#cach-hoat-dong"
          secondaryLabel="Xem cách hoạt động"
          note="Thiếu nguồn thì trợ lý nói rõ thiếu, không tự suy đoán."
        />
      ),
          },
    {
      id: 'nguyen-tac',
      image: { src: '/landing/nguyen-tac.jpg', alt: 'Dược sĩ thao tác trên máy tính xách tay trước tủ thuốc', flip: true, position: '50% 50%' },
      content: (
        <SlideText
          badge="Nguyên tắc vận hành"
          title={
            <>
              Dược sĩ <span className="landing-accent">luôn quyết định.</span>
            </>
          }
          text="Hệ thống chỉ đọc và gợi ý điểm cần đối chiếu. Không duyệt thay, không ghi vào hồ sơ bệnh án, không gửi tin. Mọi con số do code tính, AI không tự tính."
          secondaryHref="#nguyen-tac"
          secondaryLabel="Xem các nguyên tắc"
          note="Toàn bộ hồ sơ trong bản thử nghiệm là dữ liệu giả lập."
        />
      ),
          },
  ]

  return (
    <div className="min-h-screen bg-paper text-fg">
      {/* Thanh trên */}
      <header className="sticky top-0 z-30 border-b border-line/70 bg-paper/85 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-[1200px] items-center justify-between gap-4 px-6">
          <Link to="/" className="flex items-center gap-3" aria-label="Thẩm định y lệnh">
            <AppLogo imageClassName="h-11" />
            <span className="hidden h-7 w-px bg-line-strong sm:block" aria-hidden="true" />
            <span className="hidden flex-col leading-tight sm:flex">
              <span className="text-sm font-bold tracking-tight">Thẩm định y lệnh</span>
              <span className="text-2xs text-fg-subtle">Dược lâm sàng · bản thử nghiệm</span>
            </span>
          </Link>
          <nav aria-label="Mục trang chủ" className="hidden items-center gap-7 text-sm text-fg-muted md:flex">
            <a href="#man-hinh" className="transition-colors hover:text-fg">Một màn hình</a>
            <a href="#cach-hoat-dong" className="transition-colors hover:text-fg">Cách hoạt động</a>
            <a href="#bay-yeu-to" className="transition-colors hover:text-fg">Bảy yếu tố</a>
            <a href="#nguyen-tac" className="transition-colors hover:text-fg">Nguyên tắc</a>
          </nav>
          <div className="flex items-center gap-2">
            <ThemeControl />
            <Button asChild variant="primary" size="md">
              <Link to="/dang-nhap">Đăng nhập</Link>
            </Button>
          </div>
        </div>
      </header>

      <main>
        {/* 1. Mở đầu */}
        <section>
          <HeroCarousel slides={heroSlides} />

          {/* Dải số liệu */}
          <div className="border-y border-line bg-surface/70">
            <dl className="mx-auto grid max-w-[1200px] grid-cols-2 divide-line px-6 lg:grid-cols-4 lg:divide-x">
              {STATS.map((stat) => (
                <div key={stat.label} className="flex flex-col gap-1 py-6 lg:px-8 lg:first:pl-0">
                  <dd className="text-[40px] leading-none font-bold tracking-tight text-fg tabular-nums">
                    {stat.value}
                  </dd>
                  <dt className="max-w-[200px] text-sm leading-snug text-fg-muted">{stat.label}</dt>
                </div>
              ))}
            </dl>
          </div>
        </section>

        {/* 2. Một màn hình */}
        <section id="man-hinh" className="mx-auto max-w-[1200px] scroll-mt-20 px-6 py-20 lg:py-28">
          <Reveal className="flex max-w-[680px] flex-col gap-4">
            <Eyebrow>Một màn hình thay nhiều cửa sổ</Eyebrow>
            <h2 className="landing-h2">
              Thôi chuyển qua lại giữa phần mềm kê đơn, hồ sơ bệnh án, trang tra cứu và bảng tính.
            </h2>
            <p className="text-md leading-relaxed text-fg-muted">
              Khảo sát tại khoa ghi nhận một lần duyệt y lệnh phải qua khoảng 5 đến 6 phần mềm và
              công cụ. Bàn làm việc này đặt mọi thứ cần đối chiếu cạnh nhau.
            </p>
          </Reveal>

          <Reveal className="mt-12 grid grid-cols-1 gap-4 md:grid-cols-6">
            <BentoTile
              className="md:col-span-4"
              icon={<FileSearch className="size-5" strokeWidth={1.75} />}
              title="Bảng xét nghiệm theo thời gian"
              text="Mỗi chỉ số một dòng, mỗi lần lấy mẫu một cột. Giá trị ngoài khoảng tham chiếu nổi lên ngay."
            >
              <table className="w-full max-w-[460px] border-collapse text-sm tabular-nums">
                <thead>
                  <tr className="border-b border-line text-left text-xs text-fg-subtle">
                    <th className="py-2 font-medium">Chỉ số</th>
                    <th className="py-2 font-medium">Tham chiếu</th>
                    <th className="py-2 text-right font-medium">Lần trước</th>
                    <th className="py-2 text-right font-medium">Mới nhất</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td className="py-3 font-medium text-fg">{lab.ten}</td>
                    <td className="py-3 text-fg-muted">44,0 – 80,0</td>
                    <td className="py-3 text-right text-fg-muted">150,0</td>
                    <td className="py-3 text-right">
                      <span className="inline-flex items-center gap-1 rounded-sm bg-danger-bg px-2 py-1 font-semibold text-danger-fg">
                        <ArrowUp className="size-3.5" strokeWidth={2} aria-hidden="true" />
                        {formatClinicalText(lab.gia_tri_text)}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </BentoTile>

            <BentoTile
              className="md:col-span-2"
              icon={<Calculator className="size-5" strokeWidth={1.75} />}
              title="Chỉ số tính bằng code"
              text="CrCl, eGFR, BMI, BSA tính theo công thức gốc. AI không được tự tính."
            >
              <div className="flex flex-col items-center gap-1">
                <span className="text-xs text-fg-subtle">{crcl.nhan}</span>
                <span className="text-[44px] leading-none font-bold tracking-tight text-danger-fg tabular-nums">
                  {crcl.gia_tri_text}
                </span>
                <span className="text-xs text-fg-subtle">{crcl.don_vi}</span>
              </div>
            </BentoTile>

            <BentoTile
              className="md:col-span-2"
              icon={<BookOpenText className="size-5" strokeWidth={1.75} />}
              title="Mở đúng đoạn nguồn"
              text="Từ nhận định bấm một lần là tới đoạn nhãn thuốc được trích, nguyên văn."
            >
              <blockquote className="border-l-2 border-primary pl-3 text-sm leading-relaxed text-fg-muted italic">
                {ai.trich_dan[0]?.trich_nguyen_van ?? ''}
                <footer className="mt-2 text-xs text-fg-subtle not-italic">{source.nguon_nhan}</footer>
              </blockquote>
            </BentoTile>

            <BentoTile
              className="md:col-span-4"
              icon={<MessagesSquare className="size-5" strokeWidth={1.75} />}
              title="Hỏi lại ngay trên ca đang mở"
              text="Trợ lý trả lời trong phạm vi dữ liệu ca và kho nguồn, có trích dẫn. Không có căn cứ thì nói không có."
            >
              <div className="flex w-full max-w-[460px] flex-col gap-2.5 text-sm">
                <p className="ml-auto max-w-[85%] rounded-lg rounded-br-sm bg-primary px-3.5 py-2 text-on-primary">
                  Vì sao cần xem lại liều meropenem ở ca này?
                </p>
                <p className="max-w-[92%] rounded-lg rounded-bl-sm border border-line bg-surface px-3.5 py-2 leading-relaxed text-fg">
                  {formatClinicalText(finding.nhan_xet)}
                  <span className="ml-1.5 inline-flex gap-1 align-middle">
                    <span className="rounded-sm bg-primary-soft px-1.5 text-2xs font-semibold text-primary">1</span>
                    <span className="rounded-sm bg-primary-soft px-1.5 text-2xs font-semibold text-primary">2</span>
                  </span>
                </p>
              </div>
            </BentoTile>
          </Reveal>
        </section>

        {/* 3. Cách hoạt động */}
        <section id="cach-hoat-dong" className="landing-ink scroll-mt-16">
          <div className="mx-auto grid max-w-[1200px] grid-cols-1 gap-12 px-6 py-20 lg:grid-cols-12 lg:py-28">
            <Reveal className="flex flex-col gap-4 lg:sticky lg:top-28 lg:col-span-5 lg:self-start">
              <p className="text-xs font-semibold tracking-[0.14em] text-ink-muted uppercase">
                Cách hoạt động
              </p>
              <h2 className="landing-h2">Một nhận định đi qua bảy bước trước khi tới mắt dược sĩ.</h2>
              <p className="text-md leading-relaxed text-ink-muted">
                Luật và công thức chạy bằng code. AI chỉ đọc văn bản và viết diễn giải, và mọi câu
                nó viết đều bị kiểm lại. Ví dụ bên cạnh lấy từ ca giả lập DEMO-02.
              </p>
            </Reveal>

            <ol className="flex flex-col lg:col-span-7">
              {traceSteps.map((step, idx) => (
                <Reveal key={step.title}>
                  <li className="grid grid-cols-[44px_minmax(0,1fr)] gap-x-4 border-t border-ink-line py-5 last:border-b">
                    <span className="text-[26px] leading-8 font-bold tracking-tight text-ink-muted tabular-nums">
                      {String(idx + 1).padStart(2, '0')}
                    </span>
                    <div className="flex flex-col gap-1.5">
                      <div className="flex flex-wrap items-center gap-2.5">
                        <h3 className="text-md font-semibold">{step.title}</h3>
                        <span
                          className={cn(
                            'rounded-full px-2 py-0.5 text-2xs font-semibold',
                            ACTOR_CLASS[step.actor],
                          )}
                        >
                          {step.actor}
                        </span>
                      </div>
                      <p className="text-sm leading-relaxed text-ink-muted">{step.detail}</p>
                    </div>
                  </li>
                </Reveal>
              ))}
            </ol>
          </div>
        </section>

        {/* 4. Bảy yếu tố */}
        <section id="bay-yeu-to" className="mx-auto max-w-[1200px] scroll-mt-20 px-6 py-20 lg:py-28">
          <Reveal className="flex max-w-[680px] flex-col gap-4">
            <Eyebrow>Phạm vi kiểm tra</Eyebrow>
            <h2 className="landing-h2">Bảy yếu tố thẩm định, nói rõ cái nào đã kiểm.</h2>
            <p className="text-md leading-relaxed text-fg-muted">
              Yếu tố chưa có luật được ghi là chưa kiểm. Hệ thống không để trống và không báo đạt
              cho điều nó chưa xem.
            </p>
          </Reveal>

          <Reveal className="mt-12 grid grid-cols-1 gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-2 lg:grid-cols-4">
            {FACTORS.map((factor) => (
              <div key={factor.index} className="flex flex-col gap-3 bg-surface p-6">
                <div className="flex items-center justify-between">
                  <span className="text-[28px] leading-none font-bold tracking-tight text-fg-disabled tabular-nums">
                    {String(factor.index).padStart(2, '0')}
                  </span>
                  <span
                    className={cn(
                      'inline-flex items-center gap-1 text-xs font-medium',
                      factor.ready ? 'text-success-fg' : 'text-fg-subtle',
                    )}
                  >
                    {factor.ready ? (
                      <CircleCheck className="size-3.5" strokeWidth={1.75} aria-hidden="true" />
                    ) : (
                      <MinusCircle className="size-3.5" strokeWidth={1.75} aria-hidden="true" />
                    )}
                    {factor.ready ? 'Đã có luật' : 'Chưa có luật'}
                  </span>
                </div>
                <h3 className="text-md font-semibold tracking-tight text-fg">{factor.name}</h3>
                <p className="text-sm leading-relaxed text-fg-muted">{factor.note}</p>
              </div>
            ))}
            <div className="flex flex-col justify-between gap-4 bg-primary p-6 text-on-primary">
              <p className="text-md leading-snug font-semibold">
                Kết luận chỉ có bốn trạng thái: đạt, cần xem, không đủ dữ liệu, ngoài hướng dẫn sử
                dụng.
              </p>
              <Link
                to="/dang-nhap"
                className="inline-flex items-center gap-1.5 text-sm font-semibold underline-offset-4 hover:underline"
              >
                Xem trên ca mẫu
                <ArrowRight className="size-4" strokeWidth={2} aria-hidden="true" />
              </Link>
            </div>
          </Reveal>
        </section>

        {/* 5. Nguyên tắc */}
        <section id="nguyen-tac" className="scroll-mt-16 border-t border-line bg-surface">
          <div className="mx-auto grid max-w-[1200px] grid-cols-1 gap-12 px-6 py-20 lg:grid-cols-12 lg:py-28">
            <Reveal className="flex flex-col gap-4 lg:col-span-4">
              <Eyebrow>Giới hạn và nguyên tắc</Eyebrow>
              <h2 className="landing-h2">Công cụ hỗ trợ, không phải người duyệt.</h2>
            </Reveal>
            <Reveal className="grid grid-cols-1 gap-x-10 gap-y-9 sm:grid-cols-2 lg:col-span-8">
              {PRINCIPLES.map((item) => (
                <div key={item.title} className="flex flex-col gap-2 border-t-2 border-fg pt-4">
                  <h3 className="text-lg font-semibold tracking-tight text-fg">{item.title}</h3>
                  <p className="text-sm leading-relaxed text-fg-muted">{item.text}</p>
                </div>
              ))}
            </Reveal>
          </div>
        </section>

        {/* 6. Kêu gọi */}
        <section className="mx-auto max-w-[1200px] px-6 py-20">
          <Reveal className="landing-ink flex flex-col items-start justify-between gap-8 rounded-lg px-8 py-12 lg:flex-row lg:items-center lg:px-14">
            <div className="flex flex-col gap-3">
              <h2 className="landing-h2">Mở một ca mẫu và tự kiểm chứng.</h2>
              <p className="max-w-[520px] text-md text-ink-muted">
                Sáu ca giả lập có sẵn, gồm ca chỉnh liều theo chức năng thận và ca dị ứng chéo.
              </p>
            </div>
            <Button asChild variant="primary" size="lg">
              <Link to="/dang-nhap">
                Vào bàn làm việc
                <ArrowRight className="size-4" strokeWidth={2} aria-hidden="true" />
              </Link>
            </Button>
          </Reveal>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-3 px-6 py-8 text-xs text-fg-subtle">
          <span>
            Bản thử nghiệm học thuật · Bệnh viện X · Khoa Dược ·
            2026
          </span>
          <span>Kết quả tham khảo. Dược sĩ kiểm chứng và quyết định.</span>
        </div>
      </footer>
    </div>
  )
}

export default LandingPage
