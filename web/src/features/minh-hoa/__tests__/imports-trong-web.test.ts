import { readdirSync, readFileSync } from 'node:fs'
import { dirname, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, it } from 'vitest'

it('không nhập tệp ngoài web', () => {
  const web = fileURLToPath(new URL('../../../../', import.meta.url))
  const src = resolve(web, 'src')
  const violations: string[] = []
  function scan(dir: string): void {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const file = resolve(dir, entry.name)
      if (entry.isDirectory()) scan(file)
      else if (/\.[cm]?[jt]sx?$/.test(entry.name)) {
        const source = readFileSync(file, 'utf8')
        const imports = source.matchAll(/\b(?:import|export)\s+(?:[^'";]*?\s+from\s+)?['"](\.[^'"]+)['"]|\b(?:import|require)\s*\(\s*['"](\.[^'"]+)['"]/g)
        for (const match of imports) {
          const specifier = match[1] ?? match[2]
          const target = relative(web, resolve(dirname(file), specifier))
          if (target === '..' || target.startsWith(`..${sep}`)) violations.push(`${relative(src, file)}: ${specifier}`)
        }
      }
    }
  }
  scan(src)
  expect(violations).toEqual([])
})
