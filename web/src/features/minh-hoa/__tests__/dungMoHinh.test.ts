import { describe, expect, it } from 'vitest'
import {
  dinhDangGiaTri,
  dungMoHinh,
  taoTrangThaiMacDinh,
} from '../dungMoHinh'
import type { PhanTuCot, PhanTuDai, PhanTuDiem, PhanTuDuong, PhanTuO } from '../dungMoHinh'
import type { BoDuLieu, DacTaMinhHoa, TepMauMinhHoa } from '../nguPhap'
import meropenemJson from '../mau/lieu-meropenem-crcl.json'
import tuongTacJson from '../mau/ma-tran-tuong-tac.json'
import thongKeJson from '../mau/thong-ke-thang.json'

const MAU_MEROPENEM = meropenemJson as unknown as TepMauMinhHoa
const MAU_TUONG_TAC = tuongTacJson as unknown as TepMauMinhHoa
const MAU_THONG_KE = thongKeJson as unknown as TepMauMinhHoa

function thuThapCacSoTrongBoDuLieu(boDuLieu: readonly BoDuLieu[]): Set<string> {
  const tap = new Set<string>()
  const themSoTuChuoi = (text: string) => {
    const matches = text.match(/\d+(?:[.,]\d+)?/g)
    if (!matches) return
    for (const token of matches) {
      tap.add(token)
      tap.add(token.replace(',', '.'))
      tap.add(token.replace('.', ','))
    }
  }
  for (const ds of boDuLieu) {
    for (const row of ds.dong) {
      for (const val of Object.values(row)) {
        if (typeof val === 'number') {
          for (const fmt of [undefined, '0', '0.0', '0.00'] as const) {
            themSoTuChuoi(dinhDangGiaTri(val, fmt))
          }
          themSoTuChuoi(String(val))
        } else if (typeof val === 'string') {
          themSoTuChuoi(val)
        }
      }
    }
  }
  return tap
}

function kiemMoiSoDenTuDuLieu(cacChuoi: readonly string[], boDuLieu: readonly BoDuLieu[]): void {
  const tapHopLe = thuThapCacSoTrongBoDuLieu(boDuLieu)
  for (const chuoi of cacChuoi) {
    const matches = chuoi.match(/\d+(?:[.,]\d+)?/g) ?? []
    for (const token of matches) {
      expect(tapHopLe.has(token), `Số "${token}" trong "${chuoi}" không có trong bộ dữ liệu`).toBe(true)
    }
  }
}

describe('dungMoHinh – meropenem theo CrCl (DEMO-02)', () => {
  const dacTa = MAU_MEROPENEM.dac_ta as DacTaMinhHoa
  const boDuLieu = MAU_MEROPENEM.bo_du_lieu
  const ds2 = boDuLieu.find((d) => d.ma === 'ds-2')!
  const ds3 = boDuLieu.find((d) => d.ma === 'ds-3')!
  const creatininCa = Number(ds3.dong[0].creatinin)

  it('đặt creatinin bằng giá trị của ca thì điểm khớp ds-2, không hiện giả định và so_hien khớp khuyen_cao', () => {
    const macDinh = taoTrangThaiMacDinh(dacTa, boDuLieu)
    expect(macDinh.cr).toBe(creatininCa)
    expect(macDinh.cn).toBe('thuc_te')

    const mh = dungMoHinh(dacTa, boDuLieu, macDinh)
    expect(mh.laGiaDinh).toBe(false)

    const dongKhop = ds2.dong.find(
      (r) => r.creatinin === creatininCa && r.loai_can_nang === 'thuc_te',
    )
    expect(dongKhop).toBeDefined()

    const cacDiem = mh.phanTu.filter((p): p is PhanTuDiem => p.loai === 'diem')
    expect(cacDiem).toHaveLength(1)
    expect(cacDiem[0].giaTriX).toBe(dongKhop!.crcl)
    expect(cacDiem[0].laGiaDinh).toBe(false)
    expect(cacDiem[0].nhan).toBeNull()

    const mucLieu = mh.soHien.find((item) => item.nhan === 'Mức liều')
    expect(mucLieu?.giaTri).toBe(dongKhop!.khuyen_cao)

    kiemMoiSoDenTuDuLieu(
      [
        mh.tieuDe,
        mh.phuDe,
        ...mh.soHien.map((s) => `${s.nhan}: ${s.giaTri}`),
        ...cacDiem.map((d) => d.giaTriChu),
      ],
      boDuLieu,
    )
  })

  it('kéo creatinin tới 120 thì điểm sang mức liều khác đúng theo ds-2 và hiện nhãn giả định', () => {
    const macDinh = taoTrangThaiMacDinh(dacTa, boDuLieu)
    const mhCa = dungMoHinh(dacTa, boDuLieu, macDinh)
    const mh120 = dungMoHinh(dacTa, boDuLieu, { ...macDinh, cr: 120 })

    const dong120 = ds2.dong.find((r) => r.creatinin === 120 && r.loai_can_nang === 'thuc_te')
    expect(dong120).toBeDefined()

    const diem120 = mh120.phanTu.find((p): p is PhanTuDiem => p.loai === 'diem')!
    expect(diem120.giaTriX).toBe(dong120!.crcl)
    expect(diem120.laGiaDinh).toBe(true)
    expect(diem120.nhan).toBe('giả định')
    expect(mh120.laGiaDinh).toBe(true)

    const mucLieuCa = mhCa.soHien.find((item) => item.nhan === 'Mức liều')?.giaTri
    const mucLieu120 = mh120.soHien.find((item) => item.nhan === 'Mức liều')?.giaTri
    expect(mucLieu120).toBe(dong120!.khuyen_cao)
    expect(mucLieu120).not.toBe(mucLieuCa)

    kiemMoiSoDenTuDuLieu(
      [mh120.tieuDe, mh120.phuDe, ...mh120.soHien.map((s) => `${s.nhan}: ${s.giaTri}`)],
      boDuLieu,
    )
  })

  it('đổi loai_can_nang sang ly_tuong và hieu_chinh thì CrCl đổi theo đúng dòng trong ds-2', () => {
    const macDinh = taoTrangThaiMacDinh(dacTa, boDuLieu)
    for (const loai of ['ly_tuong', 'hieu_chinh'] as const) {
      const dong = ds2.dong.find((r) => r.creatinin === creatininCa && r.loai_can_nang === loai)
      expect(dong).toBeDefined()

      const mh = dungMoHinh(dacTa, boDuLieu, { ...macDinh, cn: loai })
      const diem = mh.phanTu.find((p): p is PhanTuDiem => p.loai === 'diem')!
      expect(diem.giaTriX).toBe(dong!.crcl)
      expect(mh.soHien.find((item) => item.nhan === 'Mức liều')?.giaTri).toBe(dong!.khuyen_cao)
    }
  })

  it('mọi dòng ds-2 đều có điểm nằm trong đúng dải có khuyen_cao trùng với dòng đó', () => {
    const macDinh = taoTrangThaiMacDinh(dacTa, boDuLieu)
    const mhGoc = dungMoHinh(dacTa, boDuLieu, macDinh)
    const cacDaiGoc = mhGoc.phanTu.filter((p): p is PhanTuDai => p.loai === 'dai')
    expect(cacDaiGoc.length).toBeGreaterThanOrEqual(4)
    expect(cacDaiGoc.some((d) => d.khoangChu === '26–50')).toBe(true)

    for (const row of ds2.dong) {
      const cr = Number(row.creatinin)
      const cn = String(row.loai_can_nang)
      const mh = dungMoHinh(dacTa, boDuLieu, { ...macDinh, cr, cn })
      const cacDai = mh.phanTu.filter((p): p is PhanTuDai => p.loai === 'dai')
      const diem = mh.phanTu.find((p): p is PhanTuDiem => p.loai === 'diem')
      expect(diem).toBeDefined()

      const daiKhop = cacDai.find((d) => d.nhan === row.khuyen_cao)
      expect(
        daiKhop,
        `Không tìm thấy dải cho khuyến cáo "${String(row.khuyen_cao)}" tại creatinin=${cr}, cn=${cn}`,
      ).toBeDefined()
      expect(
        diem!.cx,
        `Điểm CrCl=${String(row.crcl)} (cx=${diem!.cx}) lệch trái dải "${daiKhop!.khoangChu}" [${daiKhop!.x}, ${daiKhop!.x + daiKhop!.rong}]`,
      ).toBeGreaterThanOrEqual(daiKhop!.x - 0.01)
      expect(
        diem!.cx,
        `Điểm CrCl=${String(row.crcl)} (cx=${diem!.cx}) lệch phải dải "${daiKhop!.khoangChu}" [${daiKhop!.x}, ${daiKhop!.x + daiKhop!.rong}]`,
      ).toBeLessThanOrEqual(daiKhop!.x + daiKhop!.rong + 0.01)
    }
  })
})

describe('dungMoHinh – ma trận tương tác thuốc', () => {
  const dacTa = MAU_TUONG_TAC.dac_ta as DacTaMinhHoa
  const boDuLieu = MAU_TUONG_TAC.bo_du_lieu
  const ds1 = boDuLieu.find((d) => d.ma === 'ds-1')!

  it('sinh đúng số ô bằng số cặp trong ds-1', () => {
    const macDinh = taoTrangThaiMacDinh(dacTa, boDuLieu)
    const mh = dungMoHinh(dacTa, boDuLieu, macDinh)
    const cacO = mh.phanTu.filter((p): p is PhanTuO => p.loai === 'o')
    expect(cacO).toHaveLength(ds1.dong.length)
  })

  it('ô ma trận co giãn theo bề rộng khung trong khoảng 32–72 px và căn giữa khi toàn màn', () => {
    const macDinh = taoTrangThaiMacDinh(dacTa, boDuLieu)
    const mhHep = dungMoHinh(dacTa, boDuLieu, macDinh, { rong: 320 })
    const mhToanMan = dungMoHinh(dacTa, boDuLieu, macDinh, { rong: 960 })

    const oHep = mhHep.phanTu.filter((p): p is PhanTuO => p.loai === 'o')
    const oToanMan = mhToanMan.phanTu.filter((p): p is PhanTuO => p.loai === 'o')
    expect(oHep.length).toBeGreaterThan(0)
    expect(oToanMan.length).toBeGreaterThan(0)

    const kichThuocHep = oHep[0].rong + 4
    const kichThuocToanMan = oToanMan[0].rong + 4
    expect(kichThuocHep).toBeGreaterThanOrEqual(32)
    expect(kichThuocHep).toBeLessThanOrEqual(72)
    expect(kichThuocToanMan).toBeGreaterThanOrEqual(32)
    expect(kichThuocToanMan).toBeLessThanOrEqual(72)
    expect(kichThuocToanMan).toBeGreaterThanOrEqual(kichThuocHep)

    const rongLuoiToanMan = mhToanMan.vungVe.phai - mhToanMan.vungVe.trai
    if (rongLuoiToanMan < 960 - 192) {
      const leTrai = mhToanMan.vungVe.trai
      const lePhai = mhToanMan.rong - mhToanMan.vungVe.phai
      expect(leTrai).toBeGreaterThan(136)
      expect(Math.abs(leTrai - lePhai)).toBeLessThanOrEqual(90)
    }
  })

  it('lọc theo mức độ chỉ giữ lại đúng các cặp thuộc mức độ đó', () => {
    const macDinh = taoTrangThaiMacDinh(dacTa, boDuLieu)
    const cacMucCoThat = [...new Set(ds1.dong.map((row) => String(row.muc_do)))]
    expect(cacMucCoThat.length).toBeGreaterThan(0)

    for (const muc of cacMucCoThat) {
      const kyVong = ds1.dong.filter((row) => row.muc_do === muc)
      const mh = dungMoHinh(dacTa, boDuLieu, { ...macDinh, loc_muc: [muc] })
      const cacO = mh.phanTu.filter((p): p is PhanTuO => p.loai === 'o')
      expect(cacO).toHaveLength(kyVong.length)
      expect(cacO.every((item) => item.mucDo === muc)).toBe(true)
    }
  })
})

describe('dungMoHinh – thống kê tháng giả lập', () => {
  const danhSachDacTa = MAU_THONG_KE.dac_ta as readonly DacTaMinhHoa[]
  const boDuLieu = MAU_THONG_KE.bo_du_lieu

  it('hình đường bật/tắt khoa giữ đúng các khoa đang bật', () => {
    const dacTaDuong = danhSachDacTa[0]
    const macDinh = taoTrangThaiMacDinh(dacTaDuong, boDuLieu)
    const mhDayDu = dungMoHinh(dacTaDuong, boDuLieu, macDinh)
    const duongDayDu = mhDayDu.phanTu.filter((p): p is PhanTuDuong => p.loai === 'duong')
    expect(duongDayDu).toHaveLength(4)

    const mhHaiKhoa = dungMoHinh(dacTaDuong, boDuLieu, {
      ...macDinh,
      chon_khoa: ['Khoa A', 'Khoa C'],
    })
    const duongHaiKhoa = mhHaiKhoa.phanTu.filter((p): p is PhanTuDuong => p.loai === 'duong')
    expect(duongHaiKhoa.map((d) => d.nhom).sort()).toEqual(['Khoa A', 'Khoa C'])
  })

  it('hình cột vẽ đúng tổng theo khoa và trục Y bắt đầu từ 0', () => {
    const dacTaCot = danhSachDacTa[1]
    const macDinh = taoTrangThaiMacDinh(dacTaCot, boDuLieu)
    const mh = dungMoHinh(dacTaCot, boDuLieu, macDinh)
    const cacCot = mh.phanTu.filter((p): p is PhanTuCot => p.loai === 'cot')
    expect(cacCot).toHaveLength(4)
    expect(mh.trucY?.vach[0]?.nhan).toBe('0')
  })
})
