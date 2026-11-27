import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import fixture from '../mau/khoi-that-demo02-da-chinh.json'
import rejectedFixture from '../mau/khoi-that-demo02-vi-pham.json'
import { kiemDacTa } from '../nguPhap'
import type { BoDuLieu, DacTaMinhHoa } from '../nguPhap'
import { dungMoHinh, taoTrangThaiMacDinh } from '../dungMoHinh'
import { lopBoCucKhung } from '../boCucKhung'

const block = fixture[0]
const ds = block.bo_du_lieu as BoDuLieu[]
const spec = block.dac_ta as DacTaMinhHoa

describe('mh-1', () => {
  it('kiểm mọi ví dụ trong kỹ năng minh hoạ', () => {
    const prompt = readFileSync(new URL('../../../../../config/prompts/ky_nang_minh_hoa.v1.md', import.meta.url), 'utf8')
    const examples = [...prompt.matchAll(/```json\s*([\s\S]*?)\s*```/g)].map((match) => JSON.parse(match[1]))
    expect(examples.length).toBeGreaterThanOrEqual(5)
    const columnSets = [
      { 'ds-2': { creatinin: 'dinh_luong', loai_can_nang: 'danh_muc', crcl: 'dinh_luong' }, 'ds-3': { creatinin: 'dinh_luong', loai_can_nang: 'danh_muc', crcl: 'dinh_luong' }, 'ds-4': { bien_ve_tu: 'dinh_luong', bien_ve_den: 'dinh_luong', bao_gom_tu: 'logic', bao_gom_den: 'logic', khuyen_cao: 'danh_muc' } },
      { 'ds-1': { thuoc_a: 'danh_muc', thuoc_b: 'danh_muc', muc_do: 'danh_muc' } },
      { 'ds-1': { thoi_gian: 'thoi_gian', gia_tri: 'dinh_luong' } },
      { 'ds-1': { thoi_diem: 'thoi_gian', gia_tri: 'dinh_luong', creatinin_tang_nhanh: 'logic' }, 'ds-2': { thoi_diem: 'thoi_gian' } },
      { 'ds-1': { bat_dau: 'thoi_gian', ket_thuc: 'thoi_gian', hoat_chat: 'danh_muc', trang_thai_dong: 'danh_muc' }, 'ds-2': { thoi_diem_lay_mau: 'thoi_gian', hoat_chat: 'danh_muc' } },
    ]
    expect(examples).toHaveLength(columnSets.length)
    examples.forEach((example, index) => {
      const datasets = Object.entries(columnSets[index]).map(([ma, columns]) => ({
        ma,
        cot: Object.entries(columns).map(([ten, kieu]) => ({ ten, kieu, don_vi: null })),
        dong: [Object.fromEntries(Object.entries(columns).map(([ten, kieu]) => [ten, kieu === 'dinh_luong' ? 1 : kieu === 'logic' ? true : 'mẫu']))],
      })) as BoDuLieu[]
      expect(kiemDacTa(example, datasets)).toMatchObject({ hopLe: true })
    })
  })

  it('từ chối khối thực chưa chỉnh', () => {
    const raw = rejectedFixture[0]
    const result = kiemDacTa(raw.dac_ta, raw.bo_du_lieu as BoDuLieu[])
    expect(result.hopLe).toBe(false)
    if (!result.hopLe) expect(result.lyDo.some((reason) => reason.startsWith('tron_gia_tri_ca_va_gia_dinh:phu_de'))).toBe(true)
  })

  it.each(['phu_de', 'so_hien'] as const)('kiểm giá trị của ca và giá trị tra ở %s', (field) => {
    const original = rejectedFixture[0].dac_ta
    const interval = structuredClone(original.phu_de[3])
    const selected = { o: { ds: 'ds-2', cot: 'crcl', theo_tham_so: true } }
    const caseValue = { o: { ds: 'ds-3', cot: 'crcl', dong: 0 } }
    const label = (item: object) => field === 'so_hien' ? { ...item, nhan: 'Giá trị' } : item
    const check = (items: object[]) => kiemDacTa({ ...spec, phu_de: [], so_hien: [], [field]: items.map(label) }, ds)
    const mixed = check([caseValue, interval])
    expect(mixed.hopLe).toBe(false)
    if (!mixed.hopLe) expect(mixed.lyDo.some((reason) => reason.startsWith(`tron_gia_tri_ca_va_gia_dinh:${field}`))).toBe(true)
    const missing = check([interval])
    expect(missing.hopLe).toBe(false)
    if (!missing.hopLe) expect(missing.lyDo.some((reason) => reason.startsWith(`thieu_gia_tri_tra:${field}`))).toBe(true)
    expect(check([selected, interval]).hopLe).toBe(true)
    const wrongDataset = check([{ o: { ...selected.o, ds: 'ds-3' } }, interval])
    expect(wrongDataset.hopLe).toBe(false)
    if (!wrongDataset.hopLe) expect(wrongDataset.lyDo.some((reason) => reason.startsWith('thieu_gia_tri_tra:'))).toBe(true)
  })

  it.each([320, 399])('xếp phụ đề và các ô toàn chiều ngang ở %i px', (width) => {
    const classes = lopBoCucKhung(width)
    expect(classes.dauKhung).toContain('basis-full')
    expect(classes.dauKhung).toContain('min-w-0')
    expect(classes.soHien).toContain('grid-cols-1')
    expect(classes.soHien).not.toContain('sm:grid-cols-2')
  })

  it('đánh dấu ngay từng giá trị theo tham số khi thay đổi điều khiển', () => {
    const defaults = taoTrangThaiMacDinh(spec, ds)
    const initial = dungMoHinh(spec, ds, defaults)
    const changed = dungMoHinh(spec, ds, { ...defaults, cr: 121 })
    expect(initial.phuDe).not.toContain('(giả định)')
    expect(changed.phuDe.match(/\(giả định\)/g)).toHaveLength(2)
    expect(changed.soHien.every((item) => item.laGiaDinh)).toBe(true)
    const weightChanged = dungMoHinh(spec, ds, { ...defaults, cn: 'ly_tuong' })
    expect(weightChanged.laGiaDinh).toBe(true)
  })
  it('kiểm và dựng khối thực ở creatinin 212', () => {
    expect(kiemDacTa(spec, ds)).toMatchObject({ hopLe: true })
    const model = dungMoHinh(spec, ds, taoTrangThaiMacDinh(spec, ds))
    expect(model.soHien.some((item) => item.giaTri === 'Một nửa liều khuyến cáo, mỗi 12 giờ')).toBe(true)
  })

  it('tra đúng các biên khoảng', () => {
    const state = taoTrangThaiMacDinh(spec, ds)
    const grid = ds.find((item) => item.ma === 'ds-2')!
    const boundaries = [10, 25, 25.01, 50, 50.01]
    const base = grid.dong.find((row) => row.creatinin === state.cr && row.loai_can_nang === state.cn)!
    const rows = boundaries.map((value) => ({ ...base, crcl: value }))
    const datasets = ds.map((item) => item === grid ? { ...item, dong: rows } : item)
    const tiers = ds.find((item) => item.ma === 'ds-4')!.dong
    const expected = [tiers[1].khuyen_cao, tiers[1].khuyen_cao, tiers[2].khuyen_cao, tiers[2].khuyen_cao, tiers[3].khuyen_cao]
    boundaries.forEach((_, index) => {
      const single = datasets.map((item) => item.ma === 'ds-2' ? { ...item, dong: [rows[index]] } : item)
      const model = dungMoHinh(spec, single, state)
      expect(model.soHien[0].giaTri).toBe(expected[index])
    })
  })

  it('dựng lưới 2.000 dòng trong ngân sách 30 ms theo trung vị', () => {
    const grid = ds.find((item) => item.ma === 'ds-2')!
    const data = ds.map((item) => item === grid ? { ...item, dong: Array.from({ length: 2000 }, (_, i) => grid.dong[i % grid.dong.length]) } : item)
    const state = taoTrangThaiMacDinh(spec, data)
    const times = Array.from({ length: 5 }, () => {
      const start = performance.now()
      dungMoHinh(spec, data, state)
      return performance.now() - start
    }).sort((a, b) => a - b)
    expect(times[2]).toBeLessThan(30)
  })
})
