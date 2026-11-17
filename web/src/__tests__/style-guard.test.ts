import { describe, expect, it } from 'vitest'

const codeFiles = import.meta.glob<string>('../**/*.{ts,tsx}', {
  query: '?raw',
  import: 'default',
  eager: true,
})

const cssFiles = import.meta.glob<string>('../**/*.css', {
  query: '?raw',
  import: 'default',
  eager: true,
})

const HEX_COLOR_PATTERN = /#[0-9a-fA-F]{3,8}\b/
const RGB_OR_HSL_PATTERN = /\b(?:rgba?|hsla?)\s*\(/i
const INLINE_COLOR_STYLE_PATTERN =
  /style=\{\{[^}]*\b(?:color|background|backgroundColor|borderColor|outlineColor|fill|stroke)\b/i

const FORBIDDEN_SYMBOLS: readonly { code: string; char: string }[] = [
  { code: 'U+25B2', char: '\u25B2' },
  { code: 'U+25BC', char: '\u25BC' },
  { code: 'U+26A0', char: '\u26A0' },
  { code: 'U+2713', char: '\u2713' },
  { code: 'U+26D4', char: '\u26D4' },
  { code: 'U+2139', char: '\u2139' },
  { code: 'U+2605', char: '\u2605' },
]

function isCheckedCodeFile(filePath: string): boolean {
  const normalized = filePath.replace(/\\/g, '/')
  if (normalized.includes('/__tests__/')) {
    return false
  }
  if (normalized.endsWith('.test.ts') || normalized.endsWith('.test.tsx')) {
    return false
  }
  if (normalized.endsWith('/api/mockData.ts')) {
    return false
  }
  return true
}

function isApiContractFile(filePath: string): boolean {
  return filePath.replace(/\\/g, '/').endsWith('/api/types.ts')
}

describe('kiểm tra tĩnh hệ thống thiết kế (style guard)', () => {
  const targetCodeEntries = Object.entries(codeFiles).filter(([filePath]) =>
    isCheckedCodeFile(filePath),
  )
  // api/types.ts khai báo hợp đồng kiểu dữ liệu API ('▲' | '▼'), không phải mã nguồn hiển thị UI.
  const uiCodeEntries = targetCodeEntries.filter(([filePath]) => !isApiContractFile(filePath))

  it('đọc được các tệp nguồn giao diện trong src/', () => {
    expect(targetCodeEntries.length).toBeGreaterThan(20)
  })

  it('không có mã màu hex, rgb/rgba, hsl/hsla trong mã nguồn ngoài theme.css và mockData.ts', () => {
    for (const [filePath, content] of targetCodeEntries) {
      expect(content, `${filePath} chứa mã màu hex`).not.toMatch(HEX_COLOR_PATTERN)
      expect(content, `${filePath} chứa rgb()/rgba() hoặc hsl()/hsla()`).not.toMatch(
        RGB_OR_HSL_PATTERN,
      )
    }

    const globalsCss = Object.entries(cssFiles).find(([filePath]) =>
      filePath.replace(/\\/g, '/').endsWith('/styles/globals.css'),
    )
    expect(globalsCss).toBeDefined()
    if (globalsCss) {
      const [cssPath, cssContent] = globalsCss
      expect(cssContent, `${cssPath} chứa mã màu hex`).not.toMatch(HEX_COLOR_PATTERN)
      expect(cssContent, `${cssPath} chứa rgb()/rgba() hoặc hsl()/hsla()`).not.toMatch(
        RGB_OR_HSL_PATTERN,
      )
    }
  })

  it('không có thuộc tính màu nội tuyến style={{ ... }} trong mã nguồn', () => {
    for (const [filePath, content] of targetCodeEntries) {
      expect(content, `${filePath} chứa style={{ ... }} có thuộc tính màu`).not.toMatch(
        INLINE_COLOR_STYLE_PATTERN,
      )
    }
  })

  it('không dùng ký tự mũi tên hay biểu tượng unicode trực tiếp trong mã nguồn giao diện', () => {
    for (const [filePath, content] of uiCodeEntries) {
      for (const symbol of FORBIDDEN_SYMBOLS) {
        expect(content, `${filePath} chứa ký tự ${symbol.code}`).not.toContain(symbol.char)
      }
    }
  })

  it('src/styles/ chỉ còn theme.css và globals.css, không còn file .css thừa nào khác', () => {
    const cssPaths = Object.keys(cssFiles)
      .map((filePath) => filePath.replace(/\\/g, '/'))
      .sort()
    expect(cssPaths).toEqual(['../styles/globals.css', '../styles/theme.css'])
  })
})
