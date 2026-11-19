import { describe, expect, it } from 'vitest'
import type { BangYLenh, MaTranTuongTac, NhanDinh } from '../api/types.ts'
import {
  buildInteractionMatrix,
  buildLabPivot,
  drugKey,
  groupScheduleByDay,
  parseInfoPairs,
  parseSchedule,
} from '../lib/detailTables.ts'

function finding(partial: Partial<NhanDinh>): NhanDinh {
  return {
    nhan_dinh_id: 'x',
    thuoc: '',
    yeu_to: '4. Tương tác thuốc',
    nhan_xet: '',
    ket_luan_ma: 'can_xem',
    ket_luan_nhan: 'Cần xem',
    muc_do_ma: 'can_luu_y',
    muc_do_nhan: 'Cần lưu ý',
    nguon_goc_ma: 'luat',
    nguon_goc_nhan: 'Luật',
    ma_luat: null,
    chi_tiet_y_lenh_id: [],
    thong_tin_con_thieu: [],
    can_cu: [],
    phan_hoi: null,
    dien_giai_ai: null,
    de_xuat_ai: null,
    trich_dan: [],
    ...partial,
  }
}

const table = (names: string[]): BangYLenh => ({
  cot: ['Thuốc'],
  dong: names.map((name) => ({ Thuốc: name })),
})

describe('bảng chi tiết y lệnh', () => {
  it('tách dòng thông tin y lệnh thành cặp nhãn – giá trị', () => {
    expect(parseInfoPairs('Mã y lệnh: YL-01 · Thời điểm kê: 10/11/2026 05:50')).toEqual([
      { label: 'Mã y lệnh', value: 'YL-01' },
      { label: 'Thời điểm kê', value: '10/11/2026 05:50' },
    ])
  })

  it('tách lịch dùng thành từng mốc và gom theo ngày', () => {
    const doses = parseSchedule('10/11/2026 16:00 (500,0 mg), 11/11/2026 00:00 (500,0 mg)')
    expect(doses).toHaveLength(2)
    expect(doses[0]).toEqual({ date: '10/11/2026', time: '16:00', dose: '500,0 mg' })
    expect(groupScheduleByDay(doses).map((day) => day.doses.length)).toEqual([1, 1])
    expect(parseSchedule('khi cần')).toEqual([])
  })

  it('xoay xét nghiệm: cột theo thời điểm tăng dần, ô ngoài ngưỡng được đánh dấu', () => {
    const pivot = buildLabPivot([
      {
        thoi_diem_text: '10/11/2026 05:30',
        ten: 'Creatinin máu',
        gia_tri_text: '212,0',
        don_vi: 'umol/L',
        khoang_tham_chieu: '44,0 – 80,0',
        ngoai_nguong: true,
        huong: '▲',
      },
      {
        thoi_diem_text: '07/11/2026 05:30',
        ten: 'Creatinin máu',
        gia_tri_text: '150,0',
        don_vi: 'umol/L',
        khoang_tham_chieu: '44,0 – 80,0',
        ngoai_nguong: true,
        huong: '▲',
      },
    ])
    expect(pivot.times).toEqual(['07/11/2026 05:30', '10/11/2026 05:30'])
    expect(pivot.rows).toHaveLength(1)
    expect(pivot.rows[0].cells.map((cell) => cell?.text)).toEqual(['150,0', '212,0'])
    expect(pivot.rows[0].cells[1]?.direction).toBe('up')
  })
})

describe('ma trận tương tác thuốc', () => {
  it('dùng mã dòng của ma trận, giữ các dòng trùng tên và lý do thiếu', () => {
    const matrix: MaTranTuongTac = {
      nguon: 'DDInter 2.0', ghi_chu: 'Sàng lọc',
      thuoc: [
        { chi_tiet_y_lenh_id: 'P1', ten: 'Thuốc A', nhom: 'cho_duyet', phan_giai: 'da_phan_giai', hoat_chat: [], ly_do: null },
        { chi_tiet_y_lenh_id: 'P2', ten: 'Thuốc A', nhom: 'cho_duyet', phan_giai: 'khong_nhan_dien', hoat_chat: [], ly_do: 'Chưa phân giải' },
        { chi_tiet_y_lenh_id: 'A1', ten: 'Thuốc ABC', nhom: 'dang_dung', phan_giai: 'khong_ap_dung', hoat_chat: [], ly_do: null },
      ],
      cap: [
        { a: 'P1', b: 'P2', muc: 'thieu_du_lieu', nhan_dinh_id: 'pair', tom_tat: null, ly_do: 'Chưa phân giải P2' },
        { a: 'P1', b: 'A1', muc: 'khong_ap_dung', nhan_dinh_id: null, tom_tat: null, ly_do: 'Dịch truyền' },
        { a: 'P2', b: 'A1', muc: 'khong_ap_dung', nhan_dinh_id: null, tom_tat: null, ly_do: 'Dịch truyền' },
      ],
      thuc_an: [{ chi_tiet_y_lenh_id: 'P1', hoat_chat: 'alpha', thuc_an: 'Fixture food', muc: 'thong_tin', mo_ta: 'Fixture description', xu_tri: null }],
    }
    const data = buildInteractionMatrix(table(['Tên khác']), null, {
      can_chu_y: [finding({ nhan_dinh_id: 'pair', thuoc: 'Không trùng tên' })],
      dat: [], yeu_to_chua_kiem: ['4. Tương tác thuốc'],
    }, matrix)
    expect(data.drugs.map((row) => row.key)).toEqual(['P1', 'P2', 'A1'])
    expect(data.untested).toBe(false)
    expect(data.pairs.map((row) => row.level)).toEqual(['thieu_du_lieu', 'khong_ap_dung', 'khong_ap_dung'])
    expect(data.pairs[0].finding?.nhan_dinh_id).toBe('pair')
    expect(data.pairs[0].reason).toBe('Chưa phân giải P2')
    expect(data.foods).toEqual(matrix.thuc_an)
    expect(data.source).toBe('DDInter 2.0')
    expect(data.note).toBe('Sàng lọc')
  })

  it('rút tên hoạt chất bỏ hàm lượng', () => {
    expect(drugKey('Metoprolol tartrat 50 mg')).toBe('metoprolol tartrat')
  })

  it('chưa có luật tương tác thì mọi cặp là chưa kiểm, không bao giờ là không phát hiện', () => {
    const data = buildInteractionMatrix(table(['Warfarin 5 mg', 'Amiodaron 200 mg']), null, {
      can_chu_y: [],
      dat: [],
      yeu_to_chua_kiem: ['4. Tương tác thuốc'],
    })
    expect(data.untested).toBe(true)
    expect(data.pairs.map((pair) => pair.level)).toEqual(['chua_kiem'])
  })

  it('gắn nhận định tương tác vào đúng cặp và giữ mức nghiêm trọng', () => {
    const data = buildInteractionMatrix(
      table(['Warfarin 5 mg', 'Amiodaron 200 mg']),
      table(['Paracetamol 500 mg']),
      {
        can_chu_y: [
          finding({
            thuoc: 'Warfarin 5 mg',
            nhan_xet: 'Warfarin và Amiodaron: tăng nguy cơ chảy máu',
            muc_do_ma: 'nghiem_trong',
          }),
        ],
        dat: [],
        yeu_to_chua_kiem: [],
      },
    )
    expect(data.drugs).toHaveLength(3)
    expect(data.pairs).toHaveLength(3)
    expect(data.pairs.find((pair) => pair.a === 0 && pair.b === 1)?.level).toBe('nghiem_trong')
    expect(data.pairs.find((pair) => pair.a === 0 && pair.b === 2)?.level).toBe('khong_phat_hien')
  })
})
