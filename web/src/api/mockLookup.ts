import type {
  ChiTietThuoc,
  CongThucMuc,
  DanhMucCongThuc,
  KetQuaThuoc,
  NhomNhanFda,
} from './types.ts'

/** Dữ liệu giả lập nhỏ cho chế độ mock của ba trang tra cứu (không phải dữ liệu thật). */
export const MOCK_DRUGS: KetQuaThuoc[] = [
  { hoat_chat_id: 'metformin', ten_inn: 'metformin', ten_viet: 'Metformin', ma_atc: ['A10BA02'], so_che_pham: 281, co_nhan_fda: true, so_quy_tac: 13 },
  { hoat_chat_id: 'meropenem', ten_inn: 'meropenem', ten_viet: 'Meropenem', ma_atc: ['J01DH02'], so_che_pham: 131, co_nhan_fda: true, so_quy_tac: 11 },
  { hoat_chat_id: 'amiodarone', ten_inn: 'amiodarone', ten_viet: 'Amiodaron', ma_atc: ['C01BD01'], so_che_pham: 40, co_nhan_fda: true, so_quy_tac: 6 },
]

const FDA_MUC = [
  'chi_dinh', 'chong_chi_dinh', 'lieu', 'lieu_than', 'lieu_gan', 'canh_bao', 'tuong_tac',
  'thai_ky_cho_bu', 'nhi_cao_tuoi', 'tac_dung_phu', 'qua_lieu', 'duoc_ly', 'khac',
]

export function buildMockDrugDetail(id: string): ChiTietThuoc | null {
  const drug = MOCK_DRUGS.find((item) => item.hoat_chat_id === id)
  if (!drug) return null
  const nhom: NhomNhanFda[] = FDA_MUC.map((muc) => ({
    muc,
    doan: muc === 'chi_dinh'
      ? [{
          doan_trich_id: `${id}-fda-1`,
          duong_dan_muc: '1 INDICATIONS AND USAGE',
          noi_dung_goc: 'Mock label text kept in English for the lookup page.',
          url_goc: null,
          tai_lieu_id: `fda-${id}`,
          set_id: null,
          nguon: 'openFDA',
          phien_ban_nguon: null,
          tang_tin_cay: 3,
        }]
      : [],
  }))
  return {
    dinh_danh: {
      hoat_chat_id: id, ten_inn: drug.ten_inn, ten_viet: drug.ten_viet, rxcui: null,
      ma_atc: drug.ma_atc, ddinter_id: null, loai: 'hoat_chat', nguon: 'mock', trang_thai: null,
    },
    che_pham: {
      nguon: 'Cục Quản lý Dược (mock)', trang_thai: null, tong: 1,
      danh_sach: [{ ten_thuoc: `${drug.ten_viet} 500 mg`, so_dang_ky: 'VD-0000-00', dang_bao_che: 'Viên nén', ham_luong: 500, don_vi: 'mg' }],
    },
    nhan_fda: { nguon: 'openFDA (mock)', trang_thai: null, tong_doan: 1, nhom },
    quy_tac: [{
      nhom: 'lieu_than', bang_luat: 'mock', phan: 'quy_tac', phien_ban: null,
      trang_thai: 'cho_duoc_si_duyet', du_lieu: { egfr_duoi: 30, hanh_dong: 'chong_chi_dinh' },
    }],
    tuong_tac_tom_tat: {
      nguon: 'DDInter (mock)', trang_thai: null, ddinter_id: null, co_du_lieu: true,
      so_cap: { major: 1, moderate: 2, minor: 0, unknown: 0 },
      major: [{ ddinter_id: 'DDInter0', ten_thuoc_khac: 'Thuốc mẫu', co_che: ['Distribution'] }],
      ghi_chu: 'Dữ liệu mock.',
    },
  }
}

const MOCK_FORMULA_LIST: CongThucMuc[] = [
  {
    ma: 'bmi', ten: 'Chỉ số khối cơ thể (BMI)', loai: 'cong_thuc_toan',
    dau_vao: [
      { ten: 'can_nang_kg', nhan: 'Cân nặng', kieu: 'so', don_vi: ['kg'], lua_chon: [], nhan_lua_chon: {}, truong_don_vi: null, bat_buoc: true, mac_dinh: null },
      { ten: 'chieu_cao_cm', nhan: 'Chiều cao', kieu: 'so', don_vi: ['cm'], lua_chon: [], nhan_lua_chon: {}, truong_don_vi: null, bat_buoc: true, mac_dinh: null },
    ],
    dau_ra: { don_vi: ['kg/m2'], phan_hang: [] },
    tham_khao_goc: ['WHO. Body mass index (BMI).'],
    tham_chieu_mdcalc: null,
    trang_thai: 'chua_duoc_si_duyet',
  },
  {
    ma: 'cockcroft_gault', ten: 'Độ thanh thải creatinin – Cockcroft-Gault', loai: 'cong_thuc_toan',
    dau_vao: [
      { ten: 'tuoi', nhan: 'Tuổi', kieu: 'so', don_vi: ['tuoi'], lua_chon: [], nhan_lua_chon: {}, truong_don_vi: null, bat_buoc: true, mac_dinh: null },
      { ten: 'gioi_tinh', nhan: 'Giới tính', kieu: 'lua_chon', don_vi: [], lua_chon: ['nam', 'nu'], nhan_lua_chon: { nam: 'Nam', nu: 'Nữ' }, truong_don_vi: null, bat_buoc: true, mac_dinh: null },
      { ten: 'can_nang_kg', nhan: 'Cân nặng', kieu: 'so', don_vi: ['kg'], lua_chon: [], nhan_lua_chon: {}, truong_don_vi: null, bat_buoc: true, mac_dinh: null },
      { ten: 'creatinin', nhan: 'Creatinin huyết thanh', kieu: 'so', don_vi: ['mg/dL', 'umol/L'], lua_chon: [], nhan_lua_chon: {}, truong_don_vi: 'creatinin_don_vi', bat_buoc: true, mac_dinh: null },
    ],
    dau_ra: { don_vi: ['mL/min'], phan_hang: [] },
    tham_khao_goc: ['Cockcroft DW, Gault MH. Nephron 1976;16:31-41.'],
    tham_chieu_mdcalc: null,
    trang_thai: 'chua_duoc_si_duyet',
  },
]

export const MOCK_FORMULAS: DanhMucCongThuc = { cong_thuc: MOCK_FORMULA_LIST }
