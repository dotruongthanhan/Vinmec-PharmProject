import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { ApiClient, ApiError } from '../api/client'
import type { FetchLike } from '../api/client'
import { MockClient } from '../api/mock'
import { MOCK_FORMULAS, buildMockDrugDetail } from '../api/mockLookup'
import type { CongThucMuc, DanhSachThuoc, GoiYThuoc, KetQuaCongThuc, KetQuaGoiYThuoc, KetQuaTraTuongTac } from '../api/types'
import { TooltipProvider } from '../components/ui/tooltip'
import { DrugDetailView } from '../features/lookup/DrugDetailPage'
import { DrugNameCombobox } from '../features/lookup/DrugNameCombobox'
import { DrugResultsTable } from '../features/lookup/DrugSearchPage'
import { FormulaForm, FormulaListView, FormulaResultView } from '../features/lookup/FormulaPages'
import { DrugChipInput, InteractionLookupResult, ResolutionWarnings } from '../features/lookup/InteractionLookupPage'
import { SidebarNav } from '../features/sidebar/SidebarNav'
import {
  addDrugName,
  applyChipSuggestion,
  approvalLabel,
  buildFormulaBody,
  comboboxInitialActiveIndex,
  groupFormulas,
  initialFormulaValues,
  resolveComboboxKeyDown,
  setBoundedCache,
  splitHighlightSegments,
} from '../lib/lookup'

const noop = () => {}
const HTTPS = ['ht', 'tps://'].join('')
const DAILYMED = `${HTTPS}dailymed.nlm.nih.gov/dailymed/`
const DDINTER = `${HTTPS}ddinter.scbdd.com/example/`

function jsonFetch(
  calls: { url: string; init?: RequestInit }[],
  body: unknown,
  status = 200,
): FetchLike {
  return async (input, init) => {
    calls.push({ url: String(input), init })
    return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
  }
}

describe('sidebar có 3 mục tra cứu', () => {
  it.each([{ collapsed: false }, { collapsed: true }])('hiện Tra cứu thuốc, Tra tương tác, Tính toán (%o)', (options) => {
    const html = renderToStaticMarkup(
      <TooltipProvider>
        <MemoryRouter>
          <SidebarNav
            {...options}
            activeSection="thuoc"
            onNavigate={noop}
            userEmail={null}
            isDemoMode
            onToggleCollapse={noop}
            onOpenSettings={noop}
            onSignIn={noop}
            onSignOut={noop}
          />
        </MemoryRouter>
      </TooltipProvider>,
    )
    expect(html).toContain('aria-label="Hồ sơ cần duyệt"')
    expect(html).toMatch(/href="\/app\/thuoc"[^>]*aria-label="Tra cứu thuốc"|aria-label="Tra cứu thuốc"[^>]*href="\/app\/thuoc"/)
    expect(html).toContain('href="/app/tuong-tac"')
    expect(html).toContain('aria-label="Tra tương tác"')
    expect(html).toContain('href="/app/cong-thuc"')
    expect(html).toContain('aria-label="Tính toán"')
    expect(html).toContain('aria-current="page"')
    expect(html).not.toContain('Hồ sơ bệnh án')
  })
})

describe('bảng tra cứu thuốc', () => {
  const data: DanhSachThuoc = {
    tong: 65,
    trang: 2,
    so_dong: 30,
    ket_qua: [
      { hoat_chat_id: 'metformin', ten_inn: 'metformin', ten_viet: 'Metformin', ma_atc: ['A10BA02'], so_che_pham: 281, co_nhan_fda: true, so_quy_tac: 13 },
      { hoat_chat_id: 'zzz', ten_inn: 'zzz-chat', ten_viet: null, ma_atc: [], so_che_pham: 0, co_nhan_fda: false, so_quy_tac: 0 },
    ],
  }
  const props = { loading: false, error: null, query: '', onOpen: noop, onPageChange: noop, onRetry: noop }

  it('hiện cột, dòng và phân trang 30 dòng', () => {
    const html = renderToStaticMarkup(<DrugResultsTable {...props} data={data} />)
    for (const heading of ['Hoạt chất', 'Tên Việt', 'ATC', 'Chế phẩm', 'Nhãn FDA', 'Quy tắc']) {
      expect(html).toContain(heading)
    }
    expect(html).toContain('metformin')
    expect(html).toContain('A10BA02')
    expect(html).toContain('281')
    expect(html).toContain('31–32 / 65')
    expect(html).toContain('aria-label="Trang 3"')
    expect(html).toContain('aria-current="page"')
  })

  it('trạng thái lỗi, tải và rỗng dùng thành phần chung', () => {
    expect(renderToStaticMarkup(<DrugResultsTable {...props} data={null} error="Máy chủ lỗi" />)).toContain('Máy chủ lỗi')
    expect(renderToStaticMarkup(<DrugResultsTable {...props} data={null} loading />)).toContain('aria-busy="true"')
    const empty = renderToStaticMarkup(
      <DrugResultsTable {...props} data={{ tong: 0, trang: 1, so_dong: 30, ket_qua: [] }} query="xyz" />,
    )
    expect(empty).toContain('Không tìm thấy thuốc khớp')
  })

  it('ApiClient.searchDrugs gọi GET /api/thuoc đúng tham số', async () => {
    const calls: { url: string; init?: RequestInit }[] = []
    const client = new ApiClient('/api', jsonFetch(calls, data))
    await client.searchDrugs({ q: 'metformin', trang: 2, soDong: 30 })
    expect(calls[0].url).toBe('/api/thuoc?q=metformin&trang=2&so_dong=30')
  })
})

describe('chi tiết thuốc', () => {
  const base = buildMockDrugDetail('metformin')!
  const detail = {
    ...base,
    nhan_fda: {
      ...base.nhan_fda,
      nhom: base.nhan_fda.nhom.map((group) => ({
        ...group,
        doan: group.doan.map((part) => ({ ...part, url_goc: DAILYMED })),
      })),
    },
  }

  it('các mục gập/mở có aria-expanded=false và nội dung hidden', () => {
    const html = renderToStaticMarkup(<DrugDetailView detail={detail} />)
    expect(html).toContain('Chỉ định')
    expect(html).toContain('Chống chỉ định')
    expect(html).toContain('Quy tắc thẩm định')
    expect(html).toContain('Chế phẩm (Cục Quản lý Dược)')
    expect(html).toContain('Tóm tắt tương tác (DDInter)')
    expect(html).toContain('aria-expanded="false"')
    expect(html).toContain('hidden=""')
    // 12 mục nhãn FDA hiện (mục "Khác" cũng là mục thứ 13): đủ 13 nút nhãn
    expect((html.match(/aria-controls=/g) ?? []).length).toBeGreaterThanOrEqual(13)
  })

  it('giữ nguyên tiếng Anh của nhãn, nguồn và liên kết DailyMed', () => {
    const html = renderToStaticMarkup(<DrugDetailView detail={detail} />)
    expect(html).toContain('Mock label text kept in English for the lookup page.')
    expect(html).toContain('lang="en"')
    expect(html).toContain(`href="${DAILYMED}"`)
    expect(html).toContain('rel="noopener noreferrer"')
    expect(html).toContain('DailyMed')
  })

  it('quy tắc có nhãn trạng thái duyệt lấy từ dữ liệu; null thì không nhãn', () => {
    const html = renderToStaticMarkup(<DrugDetailView detail={detail} />)
    expect(html).toContain('Chờ dược sĩ duyệt')
    expect(approvalLabel(null)).toBeNull()
    expect(approvalLabel('cho_duoc_si_duyet')?.text).toBe('Chờ dược sĩ duyệt')
    expect(approvalLabel('chua_duoc_si_duyet')?.tone).toBe('warning')
  })

  it('mục không có đoạn nhãn bị vô hiệu', () => {
    const html = renderToStaticMarkup(<DrugDetailView detail={detail} />)
    expect(html).toContain('Không có đoạn')
    expect(html).toContain('disabled=""')
  })
})

describe('tra tương tác thủ công', () => {
  const result: KetQuaTraTuongTac = {
    ma_tran: {
      nguon: 'DDInter nguồn kiểm thử',
      ghi_chu: 'Giới hạn sàng lọc kiểm thử',
      thuoc: [
        { chi_tiet_y_lenh_id: 'T1', ten: 'amiodarone', nhom: 'cho_duyet', phan_giai: 'da_phan_giai', hoat_chat: ['amiodarone'], ly_do: null },
        { chi_tiet_y_lenh_id: 'T2', ten: 'digoxin', nhom: 'cho_duyet', phan_giai: 'da_phan_giai', hoat_chat: ['digoxin'], ly_do: null },
        { chi_tiet_y_lenh_id: 'T3', ten: 'Thuốc lạ', nhom: 'cho_duyet', phan_giai: 'khong_nhan_dien', hoat_chat: [], ly_do: 'Không có trong từ điển' },
      ],
      cap: [
        { a: 'T1', b: 'T2', muc: 'nghiem_trong', nhan_dinh_id: null, tom_tat: 'Cặp Major kiểm thử', ly_do: null },
        { a: 'T1', b: 'T3', muc: 'thieu_du_lieu', nhan_dinh_id: null, tom_tat: null, ly_do: 'Tên chưa nhận diện' },
        { a: 'T2', b: 'T3', muc: 'thieu_du_lieu', nhan_dinh_id: null, tom_tat: null, ly_do: 'Tên chưa nhận diện' },
      ],
      thuc_an: [],
    },
    phan_giai: [
      { ten_nhap: 'Amiodaron 200 mg', chi_tiet_y_lenh_id: 'T1', trang_thai: 'da_phan_giai', hoat_chat: ['amiodarone'], ly_do: null },
      { ten_nhap: 'Digoxin 0,25 mg', chi_tiet_y_lenh_id: 'T2', trang_thai: 'da_phan_giai', hoat_chat: ['digoxin'], ly_do: null },
      { ten_nhap: 'Thuốc lạ', chi_tiet_y_lenh_id: 'T3', trang_thai: 'khong_nhan_dien', hoat_chat: [], ly_do: 'Không có trong từ điển' },
    ],
    chi_tiet: [
      {
        a: 'T1', b: 'T2', muc: 'tuong_tac_thuoc', mo_ta: 'Mô tả cặp kiểm thử',
        can_cu: ['Mức: Major', `Nguồn ${DDINTER}`],
        thong_tin_con_thieu: ['Liều dùng của digoxin'],
      },
    ],
  }

  it('POST /api/tuong-tac gửi đúng body {thuoc:[...]}', async () => {
    const calls: { url: string; init?: RequestInit }[] = []
    const client = new ApiClient('/api', jsonFetch(calls, result))
    const out = await client.checkInteractions({ thuoc: ['Amiodaron 200 mg', 'Digoxin 0,25 mg'] })
    expect(calls[0].url).toBe('/api/tuong-tac')
    expect(calls[0].init?.method).toBe('POST')
    expect(JSON.parse(String(calls[0].init?.body))).toEqual({ thuoc: ['Amiodaron 200 mg', 'Digoxin 0,25 mg'] })
    expect(out.chi_tiet).toHaveLength(1)
  })

  it('render bằng đúng thành phần ma trận dùng ở trang ca (chú giải, chi tiết cặp, căn cứ)', () => {
    const html = renderToStaticMarkup(
      <TooltipProvider><InteractionLookupResult result={result} /></TooltipProvider>,
    )
    // Cùng chú giải và nhãn mức với InteractionMatrix của trang ca.
    for (const label of ['Nghiêm trọng', 'Thiếu dữ liệu', 'Chưa kiểm']) {
      expect(html).toContain(label)
    }
    expect(html).toContain('THUỐC ĐÃ NHẬP (3)')
    expect(html).toContain('DDInter nguồn kiểm thử')
    expect(html).toContain('Cặp Major kiểm thử')
    // Thẻ chi tiết cặp mở sẵn với căn cứ nguyên văn và liên kết.
    expect(html).toMatch(/<details open=""[^>]*>/)
    expect(html).toContain('Mô tả cặp kiểm thử')
    expect(html).toContain('Mức: Major')
    expect(html).toContain(`href="${DDINTER}"`)
    expect(html).toContain('Liều dùng của digoxin')
  })

  it('cảnh báo tên không nhận diện bên cạnh ma trận', () => {
    const html = renderToStaticMarkup(
      <TooltipProvider><InteractionLookupResult result={result} /></TooltipProvider>,
    )
    expect(html).toContain('Có tên thuốc chưa nhận diện đầy đủ')
    expect(html).toContain('không nhận diện được tên thuốc')
    expect(renderToStaticMarkup(<ResolutionWarnings items={result.phan_giai.slice(0, 2)} />)).toBe('')
  })

  it('thêm tên thuốc: bỏ dấu để phát hiện trùng, giới hạn 12 thuốc', () => {
    expect(addDrugName(['Amiodaron 200 mg'], 'amiodaron 200 MG').error).toContain('đã có')
    expect(addDrugName([], '  Digoxin   0,25 mg ').list).toEqual(['Digoxin 0,25 mg'])
    expect(addDrugName([], '   ').list).toEqual([])
    const twelve = Array.from({ length: 12 }, (_, i) => `thuốc ${i}`)
    expect(addDrugName(twelve, 'thêm').error).toContain('Tối đa 12')
  })

  it('mock client trả 422 khi ít hơn 2 thuốc', async () => {
    await expect(new MockClient({ delayMs: 0 }).checkInteractions({ thuoc: ['a'] })).rejects.toBeInstanceOf(ApiError)
  })
})

describe('công thức', () => {
  const cg = MOCK_FORMULAS.cong_thuc.find((item) => item.ma === 'cockcroft_gault')!

  it('danh sách gom theo nhóm', () => {
    const groups = groupFormulas(MOCK_FORMULAS.cong_thuc)
    expect(groups.map((g) => g.label)).toEqual(['Cơ thể', 'Thận'])
    const html = renderToStaticMarkup(
      <MemoryRouter><FormulaListView list={MOCK_FORMULAS.cong_thuc} /></MemoryRouter>,
    )
    expect(html).toContain('href="/app/cong-thuc/cockcroft_gault"')
    expect(html).toContain('Cockcroft-Gault')
  })

  it('biểu mẫu sinh từ dau_vao (số, đơn vị, lựa chọn)', () => {
    const html = renderToStaticMarkup(<FormulaForm spec={cg} onSubmit={noop} loading={false} />)
    for (const label of ['Tuổi', 'Giới tính', 'Cân nặng', 'Creatinin huyết thanh']) {
      expect(html).toContain(label)
    }
    expect(html).toContain('mg/dL')
    expect(html).toContain('µmol/L')
    expect(html).toContain('<option value="nu">Nữ</option>')
    expect(html).toContain('Tính')
  })

  it('biểu mẫu hiển thị nhãn và lựa chọn có dấu từ API, giữ nguyên value gửi đi', () => {
    const childPughAndWeightSpec: CongThucMuc = {
      ma: 'child_pugh',
      ten: 'Child-Pugh',
      loai: 'thang_diem',
      dau_vao: [
        {
          ten: 'loai_can_nang',
          nhan: 'Loại cân nặng',
          kieu: 'lua_chon',
          don_vi: [],
          lua_chon: ['thuc_te', 'ly_tuong', 'hieu_chinh'],
          nhan_lua_chon: { thuc_te: 'Thực tế', ly_tuong: 'Lý tưởng', hieu_chinh: 'Hiệu chỉnh' },
          truong_don_vi: null,
          bat_buoc: false,
          mac_dinh: 'thuc_te',
        },
        {
          ten: 'co_truong',
          nhan: 'Cổ trướng',
          kieu: 'lua_chon',
          don_vi: [],
          lua_chon: ['khong', 'nhe', 'vua'],
          nhan_lua_chon: { khong: 'Không', nhe: 'Nhẹ', vua: 'Vừa' },
          truong_don_vi: null,
          bat_buoc: true,
          mac_dinh: null,
        },
        {
          ten: 'nao_gan',
          nhan: 'Bệnh não gan',
          kieu: 'lua_chon',
          don_vi: [],
          lua_chon: ['khong', 'do_1_2', 'do_3_4'],
          nhan_lua_chon: { khong: 'Không', do_1_2: 'Độ 1–2', do_3_4: 'Độ 3–4' },
          truong_don_vi: null,
          bat_buoc: true,
          mac_dinh: null,
        },
      ],
      dau_ra: { don_vi: ['diem'], phan_hang: ['A', 'B', 'C'] },
      tham_khao_goc: [],
      tham_chieu_mdcalc: null,
      trang_thai: 'chua_duoc_si_duyet',
    }
    const html = renderToStaticMarkup(
      <FormulaForm spec={childPughAndWeightSpec} onSubmit={noop} loading={false} />,
    )
    expect(html).toContain('Loại cân nặng')
    expect(html).toContain('<option value="ly_tuong">Lý tưởng</option>')
    expect(html).toContain('<option value="hieu_chinh">Hiệu chỉnh</option>')
    expect(html).toContain('Cổ trướng')
    expect(html).toContain('<option value="nhe">Nhẹ</option>')
    expect(html).toContain('<option value="vua">Vừa</option>')
    expect(html).toContain('Bệnh não gan')
    expect(html).toContain('<option value="do_1_2">Độ 1–2</option>')
    expect(html).toContain('<option value="do_3_4">Độ 3–4</option>')
  })

  it('buildFormulaBody gửi đơn vị ở <ten>_don_vi và bỏ ô trống', () => {
    const values = { ...initialFormulaValues(cg), tuoi: '75', gioi_tinh: 'nu', can_nang_kg: '50', creatinin: '1,2' }
    expect(buildFormulaBody(cg, values)).toEqual({
      tuoi: '75', gioi_tinh: 'nu', can_nang_kg: '50', creatinin: '1,2', creatinin_don_vi: 'mg/dL',
    })
    const partial = buildFormulaBody(cg, { ...initialFormulaValues(cg), tuoi: '75', creatinin: '90', creatinin_don_vi: 'umol/L' })
    expect(partial).toEqual({ tuoi: '75', creatinin: '90', creatinin_don_vi: 'umol/L' })
  })

  it('POST /api/cong-thuc/{ma} gửi {dau_vao}', async () => {
    const calls: { url: string; init?: RequestInit }[] = []
    const reply: KetQuaCongThuc = {
      ma: 'cockcroft_gault', cong_thuc: 'Cockcroft-Gault', phien_ban: '1', ket_qua: 31.97, don_vi: 'mL/min',
      dau_vao_da_dung: [], thieu_dau_vao: [], ghi_chu: [], tham_khao: '', trang_thai: 'chua_duoc_si_duyet',
    }
    const client = new ApiClient('/api', jsonFetch(calls, reply))
    const body = { tuoi: '75', creatinin: '1,2', creatinin_don_vi: 'mg/dL' }
    await client.calculateFormula('cockcroft_gault', { dau_vao: body })
    expect(calls[0].url).toBe('/api/cong-thuc/cockcroft_gault')
    expect(JSON.parse(String(calls[0].init?.body))).toEqual({ dau_vao: body })
  })

  it('hiện kết quả lớn, đơn vị, nhãn tham khảo và nhãn chưa duyệt', () => {
    const html = renderToStaticMarkup(
      <FormulaResultView
        result={{
          ma: 'cockcroft_gault', cong_thuc: 'Cockcroft-Gault', phien_ban: '1', ket_qua: 31.9712, don_vi: 'mL/min',
          dau_vao_da_dung: [{ ten: 'creatinin', gia_tri: 1.2, don_vi: 'mg/dL' }],
          thieu_dau_vao: [], ghi_chu: ['Dùng cân nặng thực tế'], tham_khao: 'Nephron 1976', trang_thai: 'chua_duoc_si_duyet',
        }}
      />,
    )
    expect(html).toContain('31,97')
    expect(html).toContain('mL/min')
    expect(html).toContain('Dùng cân nặng thực tế')
    expect(html).toContain('Kết quả tham khảo, dược sĩ kiểm chứng')
    expect(html).toContain('Chờ dược sĩ duyệt')
  })

  it('thiếu đầu vào: không có số, liệt kê trường thiếu', () => {
    const html = renderToStaticMarkup(
      <FormulaResultView
        result={{
          ma: 'cockcroft_gault', cong_thuc: 'Cockcroft-Gault', phien_ban: '1', ket_qua: null, don_vi: 'mL/min',
          dau_vao_da_dung: [], thieu_dau_vao: ['can_nang_kg', 'creatinin'], ghi_chu: [], tham_khao: '', trang_thai: 'chua_duoc_si_duyet',
        }}
      />,
    )
    expect(html).toContain('Thiếu đầu vào')
    expect(html).toContain('Cân nặng, Creatinin huyết thanh')
    expect(html).not.toContain('text-4xl')
  })

  it('422 giữ thông báo tiếng Việt của máy chủ', async () => {
    const calls: { url: string; init?: RequestInit }[] = []
    const client = new ApiClient(
      '/api',
      jsonFetch(calls, { loi: { ma: 'du_lieu_khong_hop_le', thong_bao: 'Đơn vị creatinin không hợp lệ.' } }, 422),
    )
    await expect(client.calculateFormula('cockcroft_gault', { dau_vao: {} })).rejects.toMatchObject({
      status: 422,
      thong_bao: 'Đơn vị creatinin không hợp lệ.',
    })
  })
})

describe('gợi ý tên thuốc khi gõ', () => {
  const sampleItems: GoiYThuoc[] = [
    {
      nhan: 'Paracetamol',
      loai: 'dong_nghia',
      hoat_chat_ids: ['acetaminophen'],
      ten_hoat_chat: ['acetaminophen'],
      gia_tri_gui: 'Paracetamol',
      khop: 'tien_to',
    },
    {
      nhan: 'Panadol Extra',
      loai: 'biet_duoc',
      hoat_chat_ids: ['acetaminophen', 'caffeine'],
      ten_hoat_chat: ['acetaminophen', 'caffeine'],
      gia_tri_gui: 'Panadol Extra',
      khop: 'tien_to',
    },
  ]

  it('ApiClient.suggestDrugs gọi GET /api/thuoc/goi-y đúng tham số và MockClient lọc theo tiền tố', async () => {
    const calls: { url: string; init?: RequestInit }[] = []
    const payload: KetQuaGoiYThuoc = { ket_qua: sampleItems, goi_y_sua: null }
    const client = new ApiClient('/api', jsonFetch(calls, payload))
    const res = await client.suggestDrugs('parac')
    expect(calls[0].url).toBe('/api/thuoc/goi-y?q=parac')
    expect(res.ket_qua).toHaveLength(2)

    const mock = new MockClient({ delayMs: 0 })
    expect((await mock.suggestDrugs('a')).ket_qua).toEqual([])
    const amiod = await mock.suggestDrugs('amiod')
    expect(amiod.ket_qua[0]?.hoat_chat_ids).toEqual(['amiodarone'])
    expect(amiod.ket_qua[0]?.khop).toBe('tien_to')
  })

  it('DrugNameCombobox đủ thuộc tính ARIA và không chứa HTML thô khi nhan có ký tự <', () => {
    const html = renderToStaticMarkup(
      <DrugNameCombobox
        value="par"
        onValueChange={noop}
        onSelect={noop}
        initialResult={{ ket_qua: sampleItems, goi_y_sua: null }}
      />,
    )
    expect(html).toContain('role="combobox"')
    expect(html).toContain('aria-expanded="true"')
    expect(html).toContain('aria-autocomplete="list"')
    expect(html).toContain('role="listbox"')
    expect(html).toContain('role="option"')
    expect(html).toContain('aria-selected="true"')
    expect(html).toContain('aria-activedescendant="')
    expect(html).toContain('Tên khác')
    expect(html).toContain('Biệt dược')
    expect(html).toContain('→ acetaminophen + caffeine')

    const xssItem: GoiYThuoc = {
      nhan: '<script>alert(1)</script>',
      loai: 'biet_duoc',
      hoat_chat_ids: ['x'],
      ten_hoat_chat: ['x'],
      gia_tri_gui: '<script>alert(1)</script>',
      khop: 'tien_to',
    }
    const xssHtml = renderToStaticMarkup(
      <DrugNameCombobox
        value="<sc"
        onValueChange={noop}
        onSelect={noop}
        initialResult={{ ket_qua: [xssItem], goi_y_sua: null }}
      />,
    )
    expect(xssHtml).not.toContain('<script>')
    expect(xssHtml).toContain('&lt;sc')
    expect(xssHtml).toContain('ript&gt;alert(1)&lt;/script&gt;')
    expect(splitHighlightSegments('<script>alert(1)</script>', '<sc')).toEqual([
      { text: '<sc', match: true },
      { text: 'ript>alert(1)</script>', match: false },
    ])
  })

  it('điều hướng bàn phím: ↓ rồi Enter chọn đúng mục, Esc đóng, chỉ tự sáng khi khớp chính xác/tiền tố', () => {
    let active = comboboxInitialActiveIndex(sampleItems)
    expect(active).toBe(0)
    const down = resolveComboboxKeyDown({ key: 'ArrowDown', open: true, items: sampleItems, activeIndex: active })
    expect(down).toEqual({ type: 'move', nextIndex: 1, preventDefault: true })
    if (down.type === 'move') active = down.nextIndex

    const onSelectCalls: GoiYThuoc[] = []
    const enter = resolveComboboxKeyDown({ key: 'Enter', open: true, items: sampleItems, activeIndex: active })
    expect(enter).toEqual({ type: 'select', item: sampleItems[1], preventDefault: true })
    if (enter.type === 'select') onSelectCalls.push(enter.item)
    expect(onSelectCalls).toEqual([sampleItems[1]])

    expect(resolveComboboxKeyDown({ key: 'Escape', open: true, items: sampleItems, activeIndex: active })).toEqual({
      type: 'close',
      preventDefault: true,
    })

    const fuzzyItems: GoiYThuoc[] = [{ ...sampleItems[0], khop: 'gan_dung' }]
    expect(comboboxInitialActiveIndex(fuzzyItems)).toBe(-1)
    expect(resolveComboboxKeyDown({ key: 'Enter', open: true, items: fuzzyItems, activeIndex: -1 })).toEqual({
      type: 'free_text',
    })
  })

  it('bộ nhớ đệm gợi ý giữ tối đa 100 khoá theo LRU', () => {
    const cache = new Map<string, number>()
    for (let i = 0; i < 105; i += 1) {
      setBoundedCache(cache, `k${i}`, i, 100)
    }
    expect(cache.size).toBe(100)
    expect(cache.has('k0')).toBe(false)
    expect(cache.has('k104')).toBe(true)
  })

  it('DrugChipInput chọn gợi ý thêm thẻ bằng gia_tri_gui, thẻ tự do có viền nét đứt', () => {
    const cordarone: GoiYThuoc = {
      nhan: 'Cordarone',
      loai: 'biet_duoc',
      hoat_chat_ids: ['amiodarone'],
      ten_hoat_chat: ['amiodarone'],
      gia_tri_gui: 'Cordarone 200mg',
      khop: 'tien_to',
    }
    const added = applyChipSuggestion([], {}, cordarone)
    expect(added.error).toBeNull()
    expect(added.list).toEqual(['Cordarone 200mg'])

    const html = renderToStaticMarkup(
      <DrugChipInput
        names={['Cordarone 200mg', 'Thuốc tự do']}
        initialMatched={[cordarone]}
        onChange={noop}
        onSubmit={noop}
      />,
    )
    expect(html).toContain('Cordarone')
    expect(html).toContain('→ amiodarone')
    expect(html).toContain('Thuốc tự do')
    expect(html).toContain('border-dashed')
    expect(html).toContain('title="Chưa đối chiếu danh mục"')
  })

  it('bảng Tra cứu thuốc hiện dòng gần đúng khi có goi_y_sua', () => {
    const data: DanhSachThuoc = {
      tong: 1,
      trang: 1,
      so_dong: 30,
      goi_y_sua: 'Paracetamol',
      ket_qua: [
        {
          hoat_chat_id: 'acetaminophen',
          ten_inn: 'acetaminophen',
          ten_viet: 'Paracetamol',
          ma_atc: ['N02BE01'],
          so_che_pham: 120,
          co_nhan_fda: true,
          so_quy_tac: 4,
        },
      ],
    }
    const html = renderToStaticMarkup(
      <DrugResultsTable
        data={data}
        loading={false}
        error={null}
        query="parecetamo"
        onOpen={noop}
        onPageChange={noop}
        onRetry={noop}
      />,
    )
    expect(html).toContain('Không có kết quả khớp đúng. Đang hiện kết quả gần đúng cho')
    expect(html).toContain('Paracetamol')
  })
})
