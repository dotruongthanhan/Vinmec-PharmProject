/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { buildMockDrugDetail } from '../api/mockLookup'
import { DrugDetailView } from '../features/lookup/DrugDetailPage'
import { safeHttpsUrl } from '../lib/sourceLink'

const HTTP = ['ht', 'tp://'].join('')
const HTTPS = ['ht', 'tps://'].join('')
const DAILYMED_HTTP = `${HTTP}dailymed.nlm.nih.gov/dailymed/`
const DAILYMED_HTTPS = `${HTTPS}dailymed.nlm.nih.gov/dailymed/`

describe('cấu hình CSP và tệp index.html', () => {
  it('index.html không còn script nội tuyến và nạp /theme-init.js đồng bộ trong head', () => {
    const html = readFileSync(new URL('../../index.html', import.meta.url), 'utf8')
    const scripts = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)]

    expect(scripts.length).toBeGreaterThan(0)
    for (const [, attrs, body] of scripts) {
      expect(attrs).toMatch(/\bsrc\s*=\s*["'][^"']+["']/i)
      expect(body.trim()).toBe('')
    }

    const headHtml = /<head>([\s\S]*?)<\/head>/i.exec(html)?.[1] ?? ''
    const themeScriptMatch = /<script\b([^>]*\bsrc=["']\/theme-init\.js["'][^>]*)><\/script>/i.exec(headHtml)
    expect(themeScriptMatch).not.toBeNull()
    expect(themeScriptMatch![1]).not.toMatch(/\b(?:defer|async|type=["']module["'])\b/i)

    const themeInit = readFileSync(new URL('../../public/theme-init.js', import.meta.url), 'utf8')
    expect(themeInit).toContain('pharm_review_ui_theme')
  })

  it('vercel.json hợp lệ JSON, giữ 2 rewrites và có đủ 5 tiêu đề bảo mật', () => {
    const raw = readFileSync(new URL('../../vercel.json', import.meta.url), 'utf8')
    const config = JSON.parse(raw) as {
      rewrites?: Array<{ source: string; destination: string }>
      headers?: Array<{ source: string; headers: Array<{ key: string; value: string }> }>
    }

    expect(config.rewrites).toEqual([
      { source: '/api/:path*', destination: `${HTTPS}vinmec-pharm.duckdns.org/api/:path*` },
      { source: '/(.*)', destination: '/index.html' },
    ])

    const globalHeadersRule = config.headers?.find((item) => item.source === '/(.*)')
    expect(globalHeadersRule).toBeDefined()

    const headerMap = new Map(globalHeadersRule!.headers.map((header) => [header.key, header.value]))
    expect(headerMap.size).toBe(5)
    expect(headerMap.get('X-Frame-Options')).toBe('DENY')
    expect(headerMap.get('X-Content-Type-Options')).toBe('nosniff')
    expect(headerMap.get('Referrer-Policy')).toBe('strict-origin-when-cross-origin')
    expect(headerMap.get('Permissions-Policy')).toBe('camera=(), microphone=(), geolocation=()')

    const csp = headerMap.get('Content-Security-Policy') ?? ''
    expect(csp).toContain("frame-ancestors 'none'")
    expect(csp).toContain("script-src 'self'")
    expect(csp).toContain("object-src 'none'")
    expect(csp).not.toContain("'unsafe-eval'")

    const scriptSrc = csp.split(';').find((directive) => directive.trim().startsWith('script-src')) ?? ''
    expect(scriptSrc).not.toContain("'unsafe-inline'")
  })
})

describe('tách mock khỏi api/index.ts', () => {
  it('không nhập tĩnh hoặc xuất lại MockClient trong src/api/index.ts', () => {
    const apiIndex = readFileSync(new URL('../api/index.ts', import.meta.url), 'utf8')
    expect(apiIndex).not.toMatch(/import\s+(?!type\b)[^;\n]*from\s+['"]\.\/mock(?:\.ts)?['"]/)
    expect(apiIndex).not.toMatch(/export\s+(?!type\b)\{[^}]*\}\s+from\s+['"]\.\/mock(?:\.ts)?['"]/)
    expect(apiIndex).toContain("await import('./mock.ts')")
  })
})

describe('kiểm tra url_goc theo giao thức https:', () => {
  const base = buildMockDrugDetail('metformin')!
  const withUrl = (urlGoc: string) => ({
    ...base,
    nhan_fda: {
      ...base.nhan_fda,
      nhom: base.nhan_fda.nhom.map((group) => ({
        ...group,
        doan: group.doan.map((part) => ({ ...part, url_goc: urlGoc })),
      })),
    },
  })

  it('safeHttpsUrl chỉ chấp nhận https:', () => {
    expect(safeHttpsUrl(`  ${DAILYMED_HTTPS}  `)).toBe(DAILYMED_HTTPS)
    expect(safeHttpsUrl(DAILYMED_HTTP)).toBeNull()
    expect(safeHttpsUrl('javascript:alert(1)')).toBeNull()
    expect(safeHttpsUrl('data:text/html,<script>alert(1)</script>')).toBeNull()
    expect(safeHttpsUrl('')).toBeNull()
    expect(safeHttpsUrl(null)).toBeNull()
    expect(safeHttpsUrl(undefined)).toBeNull()
  })

  it(`javascript:alert(1) và ${HTTP} không thành thẻ <a> mà hiển thị văn bản thuần`, () => {
    for (const unsafeUrl of ['javascript:alert(1)', DAILYMED_HTTP]) {
      const html = renderToStaticMarkup(<DrugDetailView detail={withUrl(unsafeUrl)} />)
      expect(html).not.toContain(unsafeUrl)
      expect(html).not.toMatch(/<a\b[^>]*>DailyMed\b/)
      expect(html).toContain('<span>DailyMed</span>')
    }
  })

  it(`${HTTPS} thành thẻ <a target="_blank" rel="noopener noreferrer">`, () => {
    const html = renderToStaticMarkup(<DrugDetailView detail={withUrl(DAILYMED_HTTPS)} />)
    expect(html).toContain(`href="${DAILYMED_HTTPS}"`)
    expect(html).toMatch(/<a\b[^>]*target="_blank"[^>]*rel="noopener noreferrer"[^>]*>DailyMed\b/)
  })
})
