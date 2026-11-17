/// <reference types="node" />
import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { contrastRatio } from '../lib/contrast'
const theme = readFileSync(new URL('../styles/theme.css', import.meta.url), 'utf8')

const semantics = ['danger', 'warning', 'missing', 'offlabel', 'success', 'ai', 'neutral']
const parseColors = (source: string): Record<string, string> => Object.fromEntries(
  [...source.matchAll(/--color-([\w-]+):\s*(#[\da-f]{6})\s*;/gi)].map((m) => [m[1], m[2]]),
)
const light = parseColors(theme.split(':root[data-theme="dark"]')[0])
const dark = parseColors(theme.split(':root[data-theme="dark"]')[1] ?? '')

describe('tỉ lệ tương phản WCAG', () => {
  it('đen trên trắng = 21, hai màu giống nhau = 1', () => {
    expect(contrastRatio('#000000', '#ffffff')).toBe(21)
    expect(contrastRatio('#1a2b3c', '#1a2b3c')).toBe(1)
  })
  it('tính đúng cặp đã biết, không phụ thuộc thứ tự', () => {
    expect(contrastRatio('#777777', '#ffffff')).toBeCloseTo(4.478089, 5)
    expect(contrastRatio('#ffffff', '#777777')).toBeCloseTo(4.478089, 5)
  })
})

for (const [mode, colors] of [['light', light], ['dark', dark]] as const) {
  describe(`biến màu ${mode}`, () => {
    it('định nghĩa lại toàn bộ biến màu ở chế độ tối', () => {
      expect(Object.keys(dark).sort()).toEqual(Object.keys(light).sort())
    })
    for (const foreground of ['fg', 'fg-muted', 'fg-subtle']) {
      for (const background of ['canvas', 'surface', 'paper']) {
        it(`${foreground} trên ${background} ≥ 4,5`, () => {
          expect(contrastRatio(colors[foreground], colors[background])).toBeGreaterThanOrEqual(4.5)
        })
      }
    }
    for (const meaning of semantics) {
      it(`${meaning}-fg trên ${meaning}-bg ≥ 4,5`, () => {
        expect(contrastRatio(colors[`${meaning}-fg`], colors[`${meaning}-bg`])).toBeGreaterThanOrEqual(4.5)
      })
    }
    it('chữ nút chính trên cả nền thường và nền hover ≥ 4,5', () => {
      for (const background of ['primary', 'primary-hover']) {
        expect(contrastRatio(colors['on-primary'], colors[background])).toBeGreaterThanOrEqual(4.5)
      }
    })
    it('chữ trên nút mềm và liên kết thanh bên khi hover ≥ 4,5', () => {
      expect(contrastRatio(colors.primary, colors['primary-soft'])).toBeGreaterThanOrEqual(4.5)
      expect(contrastRatio(colors['primary-line'], colors.ink)).toBeGreaterThanOrEqual(4.5)
    })
    it('vòng tiêu điểm trên mọi nền kề nó ≥ 3', () => {
      for (const background of ['canvas', 'surface', 'surface-muted', 'surface-raised', 'paper', 'ink', 'ink-soft']) {
        expect(contrastRatio(colors.focus, colors[background]), background).toBeGreaterThanOrEqual(3)
      }
    })
  })
}
