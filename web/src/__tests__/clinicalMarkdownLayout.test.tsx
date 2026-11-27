import { createElement, type ReactNode } from 'react'
import { renderToStaticMarkup as renderMarkup } from 'react-dom/server'
import { TooltipProvider } from '../components/ui/tooltip'
import { describe, expect, it, vi } from 'vitest'

vi.mock('../components/ui/dialog.tsx', () => {
  const Container = ({ children }: { children?: ReactNode }) => createElement('div', null, children)
  return { Dialog: Container, DialogContent: Container, DialogHeader: Container, DialogTitle: Container, DialogTrigger: Container }
})

import { ClinicalMarkdown } from '../components/ui/ClinicalMarkdown.tsx'

const renderToStaticMarkup = (node: ReactNode) => renderMarkup(createElement(TooltipProvider, null, node))

describe('ClinicalMarkdown table layout', () => {
  it('constrains the table and uses the preceding bold line as dialog title', () => {
    const html = renderToStaticMarkup(createElement(ClinicalMarkdown, {
      text: '**Bang theo nguon**\n\n| A | B |\n| --- | --- |\n| x | y |',
    }))
    expect(html).not.toContain('min-w-max')
    expect(html).toContain('overflow-x-auto')
    expect(html).toContain('max-w-full')
    expect(html).toMatch(/^<div class="[^"]*min-w-0/)
    expect(html).toContain('<div>Bang theo nguon</div>')
  })

  it('prefers a markdown heading and ignores bold text that is not immediately before the table', () => {
    const table = '| A |\n| --- |\n| x |'
    const render = (text: string) => renderToStaticMarkup(createElement(ClinicalMarkdown, { text }))
    expect(render(`## Heading\n**Bold**\n${table}`)).toContain('<div>Heading</div>')
    expect(render(`**Bold**\nOther\n${table}`)).toContain('<div>Bảng</div>')
  })
})
