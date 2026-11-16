import { describe, expect, it } from 'vitest'

const sourceFiles = import.meta.glob<string>('../**/*.{ts,tsx}', {
  query: '?raw',
  import: 'default',
  eager: true,
})

const FORBIDDEN_PATTERNS: readonly { label: string; token: string }[] = [
  { label: 'dangerouslySetInnerHTML', token: ['dangerously', 'SetInnerHTML'].join('') },
  { label: 'innerHTML', token: ['inner', 'HTML'].join('') },
  { label: 'eval(', token: ['ev', 'al('].join('') },
  { label: 'new Function', token: ['new ', 'Function'].join('') },
  { label: 'sessionStorage', token: ['session', 'Storage'].join('') },
]

const LOCAL_STORAGE_TOKEN = ['local', 'Storage'].join('')

describe('kiểm tra tĩnh an toàn hiển thị và lưu trữ', () => {
  it('đọc được các tệp nguồn trong src/', () => {
    expect(Object.keys(sourceFiles).length).toBeGreaterThan(10)
  })

  it('không tệp nào dùng mã thực thi động hoặc chèn HTML trực tiếp', () => {
    for (const [filePath, content] of Object.entries(sourceFiles)) {
      for (const pattern of FORBIDDEN_PATTERNS) {
        expect(content, `${filePath} chứa ${pattern.label}`).not.toContain(pattern.token)
      }
    }
  })

  it('chỉ duy nhất lib/prefs.ts được phép dùng localStorage', () => {
    const filesUsingLocalStorage = Object.entries(sourceFiles)
      .filter(([, content]) => content.includes(LOCAL_STORAGE_TOKEN))
      .map(([filePath]) => filePath)

    expect(filesUsingLocalStorage).toHaveLength(1)
    expect(filesUsingLocalStorage[0]).toMatch(/lib[/\\]prefs\.ts$/)
  })

  it('không tệp nào chứa liên kết mạng ngoài http/https', () => {
    const httpPrefix = ['ht', 'tp://'].join('')
    const httpsPrefix = ['ht', 'tps://'].join('')
    for (const [filePath, content] of Object.entries(sourceFiles)) {
      expect(content, `${filePath} chứa URL ngoài`).not.toContain(httpPrefix)
      expect(content, `${filePath} chứa URL ngoài`).not.toContain(httpsPrefix)
    }
  })
})
