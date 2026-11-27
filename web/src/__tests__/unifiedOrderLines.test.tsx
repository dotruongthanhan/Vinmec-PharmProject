import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { MOCK_CASE_DETAILS } from '../api/mockData'
import type { ChiTietCa, MedicalOrder, NhanDinh } from '../api/types'
import { TooltipProvider } from '../components/ui/tooltip'
import { OrderDetailView } from '../features/order-detail/OrderDetailView'
import { UnifiedOrderLinesTable } from '../features/order-detail/UnifiedOrderLinesTable'
import {
  flattenOrderLines,
  lineHighlightSeverity,
  normalizeLineStatus,
  partitionFindingsByLine,
} from '../lib/unifiedOrderLines'

describe('normalizeLineStatus & flattenOrderLines', () => {
  it('chuẩn hoá đúng 5 nhãn trạng thái dòng thuốc', () => {
    expect(normalizeLineStatus('pending', 'cho_duyet').label).toBe('Chờ duyệt')
    expect(normalizeLineStatus('active', 'dang_thuc_hien').label).toBe('Đang dùng')
    expect(
      normalizeLineStatus('active', 'da_duyet', '2099-01-01T08:00:00+07:00', 0).label,
    ).toBe('Đang chờ')
    expect(normalizeLineStatus('completed', 'hoan_tat').label).toBe('Dùng xong')
    expect(normalizeLineStatus('discontinued', 'ngung').label).toBe('Đã hủy')
  })

  it('chia nhận định đa thuốc vào cả 2 dòng và giữ nhận định chung toàn hồ sơ', () => {
    const base = MOCK_CASE_DETAILS['DEMO-02']
    const orderA: MedicalOrder = {
      y_lenh_id: 'YL-1',
      dot_dieu_tri_id: 'DT-1',
      thoi_diem_ke: '2026-11-10T08:00:00+07:00',
      trang_thai: 'cho_duyet',
      loai: 'thuong_quy',
      vai_tro_nguoi_ke: 'bac_si_dieu_tri',
      khoa_ke_don: 'Tim mạch',
      luong_duyet: 'truc_tiep',
      la_trong_tam: true,
      cot: ['Thuốc', 'Liều', 'Tần suất', 'Đường dùng', 'Lịch dùng'],
      dong: [
        {
          Thuốc: 'Amiodarone 200 mg',
          Liều: '200 mg',
          'Tần suất': '2 lần/ngày',
          'Đường dùng': 'Uống',
          'Lịch dùng': '10/11/2026 08:00 (200 mg)',
        },
        {
          Thuốc: 'Digoxin 0.25 mg',
          Liều: '0,25 mg',
          'Tần suất': '1 lần/ngày',
          'Đường dùng': 'Uống',
          'Lịch dùng': '10/11/2026 08:00 (0,25 mg)',
        },
      ],
      dong_meta: [
        {
          chi_tiet_y_lenh_id: 'CT-AMIO',
          trang_thai_dong: 'pending',
          bat_dau: '2026-11-10T08:00:00+07:00',
          ket_thuc: '2026-11-15T08:00:00+07:00',
        },
        {
          chi_tiet_y_lenh_id: 'CT-DIGO',
          trang_thai_dong: 'active',
          bat_dau: '2026-11-01T08:00:00+07:00',
          ket_thuc: null,
        },
      ],
    }

    const detail: ChiTietCa = { ...base, danh_sach_y_lenh: [orderA] }
    const lines = flattenOrderLines(detail)
    expect(lines).toHaveLength(2)

    const interactionFinding: NhanDinh = {
      ...base.nhan_dinh.can_chu_y[0],
      nhan_dinh_id: 'nd-ddi',
      thuoc: 'Amiodarone + Digoxin',
      yeu_to: '4. Tương tác thuốc',
      muc_do_ma: 'nghiem_trong',
      chi_tiet_y_lenh_id: ['CT-AMIO', 'CT-DIGO'],
    }
    const caseWideFinding: NhanDinh = {
      ...base.nhan_dinh.can_chu_y[0],
      nhan_dinh_id: 'nd-allergy-missing',
      thuoc: '',
      yeu_to: '1. Dị ứng, quá mẫn',
      ket_luan_ma: 'khong_du_du_lieu',
      muc_do_ma: null,
      chi_tiet_y_lenh_id: [],
    }

    const part = partitionFindingsByLine(lines, [interactionFinding, caseWideFinding], [])
    expect(part.byLineKey[lines[0].key].attention.map((f) => f.nhan_dinh_id)).toEqual(['nd-ddi'])
    expect(part.byLineKey[lines[1].key].attention.map((f) => f.nhan_dinh_id)).toEqual(['nd-ddi'])
    expect(part.caseWideAttention.map((f) => f.nhan_dinh_id)).toEqual(['nd-allergy-missing'])
    expect(lineHighlightSeverity(part.byLineKey[lines[0].key].attention)).toBe('nghiem_trong')
  })
})

describe('UnifiedOrderLinesTable UI & single-expand accordion', () => {
  it('hiển thị đúng 9 cột (không STT, không Kết quả thẩm định), tô màu cả dòng sáng và chỉ mở tối đa 1 dòng', () => {
    const base = MOCK_CASE_DETAILS['DEMO-02']
    const detail: ChiTietCa = {
      ...base,
      danh_sach_y_lenh: [
        {
          y_lenh_id: 'YL-1',
          dot_dieu_tri_id: 'DT-1',
          thoi_diem_ke: '2026-11-10T05:50:00+07:00',
          trang_thai: 'cho_duyet',
          loai: 'thuong_quy',
          vai_tro_nguoi_ke: 'bac_si_dieu_tri',
          khoa_ke_don: 'Hô hấp',
          luong_duyet: 'truc_tiep',
          la_trong_tam: true,
          cot: ['Thuốc', 'Liều', 'Tần suất', 'Đường dùng', 'Lịch dùng'],
          dong: [
            {
              Thuốc: 'Meropenem 1 g',
              Liều: '1,0 g',
              'Tần suất': '3 lần/ngày',
              'Đường dùng': 'truyền tĩnh mạch',
              'Lịch dùng': '10/11/2026 06:00 (1,0 g)',
            },
            {
              Thuốc: 'Paracetamol 500 mg',
              Liều: '500 mg',
              'Tần suất': 'Khi sốt',
              'Đường dùng': 'uống',
              'Lịch dùng': '—',
            },
          ],
          dong_meta: [
            {
              chi_tiet_y_lenh_id: 'CT-1',
              trang_thai_dong: 'pending',
              bat_dau: '2026-11-10T06:00:00+07:00',
              ket_thuc: '2026-11-10T22:00:00+07:00',
            },
            {
              chi_tiet_y_lenh_id: 'CT-2',
              trang_thai_dong: 'discontinued',
              bat_dau: '2026-11-08T08:00:00+07:00',
              ket_thuc: '2026-11-09T08:00:00+07:00',
            },
          ],
        },
      ],
    }

    const lines = flattenOrderLines(detail)
    const meroFinding: NhanDinh = {
      ...base.nhan_dinh.can_chu_y[0],
      chi_tiet_y_lenh_id: ['CT-1'],
    }
    const part = partitionFindingsByLine(lines, [meroFinding], [])

    const html = renderToStaticMarkup(
      <TooltipProvider>
        <MemoryRouter>
          <UnifiedOrderLinesTable
            caId={detail.ca_id}
            lines={lines}
            partitioned={part}
            expandedLineKey={lines[0].key}
            onToggleLine={vi.fn()}
            chiSo={detail.chi_so}
            nhomLyDo={detail.nhom_ly_do}
            feedbackDrafts={{}}
            onFeedbackDraftChange={vi.fn()}
            isFeedbackSubmitting={() => false}
            getFeedbackError={() => null}
            onSubmitFeedback={async () => true}
            onClearFeedbackError={vi.fn()}
            onOpenEvidence={vi.fn()}
            onAskAboutFinding={vi.fn()}
          />
        </MemoryRouter>
      </TooltipProvider>,
    )

    // Đủ 9 cột yêu cầu, bỏ STT và Kết quả thẩm định
    for (const col of [
      'Mã y lệnh',
      'Tên thuốc',
      'Liều',
      'Tần suất',
      'Đường dùng',
      'Ngày kê',
      'Trạng thái',
      'Bắt đầu, kết thúc',
      'Lịch dùng',
    ]) {
      expect(html).toContain(col)
    }
    expect(html).not.toContain('>STT<')
    expect(html).not.toContain('>Kết quả thẩm định<')

    // Dòng nghiêm trọng tô bg-danger-bg chữ text-fg, chỉ có đúng 1 hàng aria-expanded="true"
    expect(html).toContain('bg-danger-bg/85')
    expect((html.match(/<tr[^>]*aria-expanded="true"/g) ?? []).length).toBe(1)
    expect((html.match(/<tr[^>]*aria-expanded="false"/g) ?? []).length).toBe(1)

    // Ngăn mở rộng có đủ Thuốc dùng, Trạng thái, Khoa kê, Luồng, Loại y lệnh, Người kê và nhận định thuốc
    expect(html).toContain('Thuốc dùng')
    expect(html).toContain('Khoa kê')
    expect(html).toContain('Trực tiếp')
    expect(html).toContain('Thường quy')
    expect(html).toContain('Bác sĩ điều trị')
    expect(html).toContain('Nhận định thuốc')
  })

  it('OrderDetailView mặc định mở tab Y lệnh, đặt Nhận định chung & Ma trận tương tác ở đầu tab và ẩn khối Thông tin y lệnh / Chọn y lệnh', () => {
    const demo03 = MOCK_CASE_DETAILS['DEMO-03']
    const detailWithGeneral: ChiTietCa = {
      ...demo03,
      nhan_dinh: {
        ...demo03.nhan_dinh,
        can_chu_y: [
          ...demo03.nhan_dinh.can_chu_y,
          {
            ...demo03.nhan_dinh.can_chu_y[0],
            nhan_dinh_id: 'nhan_dinh_chung_ho_so|DEMO-03',
            thuoc: '',
            chi_tiet_y_lenh_id: [],
            nhan_xet: 'Hồ sơ chưa có thông tin dị ứng toàn bệnh án.',
          },
        ],
      },
    }
    const html = renderToStaticMarkup(
      <TooltipProvider>
        <MemoryRouter initialEntries={['/app/y-lenh/DEMO-03']}>
          <OrderDetailView
            detail={detailWithGeneral}
            aiTrangThai="tat"
            aiKetQua={null}
            aiThoiGianMs={null}
            aiCanhBao={[]}
            sessionFeedbackForCase={{}}
            onRerunAi={vi.fn()}
            isFeedbackSubmitting={() => false}
            getFeedbackError={() => null}
            onSubmitFeedback={async () => true}
            onClearFeedbackError={vi.fn()}
            onOpenEvidence={vi.fn()}
            onAskAboutFinding={vi.fn()}
          />
        </MemoryRouter>
      </TooltipProvider>,
    )

    // 6 tab (bỏ Phiếu điều trị, giữ Thẩm định)
    expect(html).not.toContain('Phiếu điều trị (')
    expect(html).toContain('<span>Thẩm định</span>')
    expect(html).not.toContain('Chọn y lệnh')
    expect(html).not.toContain('Thông tin y lệnh')

    // Nhận định chung toàn hồ sơ + Ma trận tương tác nằm trước bảng Chi tiết y lệnh
    const generalIdx = html.indexOf('Nhận định chung toàn hồ sơ')
    const matrixIdx = html.indexOf('Yếu tố 4 · Tương tác thuốc')
    const tableIdx = html.indexOf('Chi tiết y lệnh')
    expect(generalIdx).toBeGreaterThan(-1)
    expect(matrixIdx).toBeGreaterThan(generalIdx)
    expect(tableIdx).toBeGreaterThan(matrixIdx)
  })
})
