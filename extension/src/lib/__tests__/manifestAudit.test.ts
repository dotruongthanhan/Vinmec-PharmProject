import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const EXT_ROOT = resolve(__dirname, '../../..')
const PNG_SIG = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])

describe('MV3 Manifest & Build Security Audit', () => {
  it('kiểm tra manifest.json tuân thủ nghiêm ngặt MV3 Side Panel', () => {
    const manifestPath = resolve(EXT_ROOT, 'public/manifest.json')
    const manifest = JSON.parse(readFileSync(manifestPath, 'utf-8')) as Record<string, unknown>

    expect(manifest.manifest_version).toBe(3)
    expect(manifest.side_panel).toEqual({ default_path: 'sidepanel/index.html' })

    const action = manifest.action as Record<string, unknown>
    expect(action.default_popup).toBeUndefined()

    const perms = manifest.permissions as string[]
    expect(perms).toContain('sidePanel')
    expect(perms).toContain('tabs')
    expect(perms).toContain('scripting')
    expect(perms).toContain('storage')

    const icons = manifest.icons as Record<string, string>
    for (const [sizeStr, relPath] of Object.entries(icons)) {
      const size = Number.parseInt(sizeStr, 10)
      const absIcon = resolve(EXT_ROOT, 'public', relPath)
      expect(existsSync(absIcon)).toBe(true)
      const buf = readFileSync(absIcon)
      expect(buf.subarray(0, 8).equals(PNG_SIG)).toBe(true)
      const width = buf.readUInt32BE(16)
      const height = buf.readUInt32BE(20)
      expect(width).toBe(size)
      expect(height).toBe(size)
    }
  })

  it('kiểm tra gói dist sau build không chứa inline script hoặc eval', () => {
    const distDir = resolve(EXT_ROOT, 'dist')
    if (!existsSync(distDir)) {
      return
    }
    expect(existsSync(resolve(distDir, 'manifest.json'))).toBe(true)
    expect(existsSync(resolve(distDir, 'service-worker.js'))).toBe(true)
    const htmlPath = resolve(distDir, 'sidepanel/index.html')
    expect(existsSync(htmlPath)).toBe(true)
    const html = readFileSync(htmlPath, 'utf-8')
    expect(html).not.toMatch(/<script(?![^>]*\bsrc=)[^>]*>/i)

    const sw = readFileSync(resolve(distDir, 'service-worker.js'), 'utf-8')
    expect(sw).not.toMatch(/\beval\s*\(/)
    expect(sw).toContain('openPanelOnActionClick')
  })
})
