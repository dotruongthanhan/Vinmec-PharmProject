import { describe, expect, it } from 'vitest'

const sources = import.meta.glob<string>('../**/*.{ts,tsx,css}', {
  query: '?raw', import: 'default', eager: true,
})

describe('chuỗi tiếng Việt trong mã nguồn', () => {
  it('giữ mọi chuỗi viết cứng ở dạng NFC, kể cả dữ liệu giả lập', () => {
    for (const [path, source] of Object.entries(sources)) {
      expect(source, path).toBe(source.normalize('NFC'))
    }
  })
})
