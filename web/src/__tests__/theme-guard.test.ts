import { expect, it } from 'vitest'

const sources = import.meta.glob<string>('../**/*.{ts,tsx,css,svg}', {
  query: '?raw', import: 'default', eager: true,
})

it('mọi màu giao diện qua biến theme.css, không dùng bảng màu mặc định', () => {
  const palette = /\b(?:bg|text|border|ring|outline|fill|stroke|from|via|to|shadow|accent|caret|divide|decoration|placeholder)-(?:white|black|(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3})\b/
  for (const [path, source] of Object.entries(sources)) {
    if (path.includes('/__tests__/') || /\.test\.tsx?$/.test(path) || path.endsWith('/styles/theme.css')) continue
    expect(source, path).not.toMatch(/#[\da-f]{3,8}\b|\b(?:rgba?|hsla?|oklch|oklab|color)\s*\(/i)
    expect(source, path).not.toMatch(palette)
  }
})
