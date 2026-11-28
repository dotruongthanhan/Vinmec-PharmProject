import React, { useMemo, useState } from 'react'
import { flushSync } from 'react-dom'
import { ExpandButton } from './expand-button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from './dialog.tsx'
import type { TrichDanTraLoi } from '../../api/types.ts'
import { formatClinicalText } from '../../lib/displayFormat.ts'

export interface ClinicalMarkdownProps {
  text: string
  citations?: readonly TrichDanTraLoi[]
  onCitationClick?: (citation: TrichDanTraLoi, target: HTMLButtonElement) => void
  className?: string
}

/** Chip phong cách Ảnh 2: viền bo góc, nền tối nhẹ, chữ màu xanh cyan/primary nổi bật */
export function ClinicalEntityChip({
  children,
  className = '',
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <code
      className={`inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded border border-line bg-surface-muted font-mono text-xs font-semibold text-primary tracking-tight select-all ${className}`}
    >
      {children}
    </code>
  )
}

/** Chuyển đổi công thức toán học / LaTeX cơ bản sang React nodes an toàn (thuần React JSX) */
export function SafeMathFormula({
  rawMath,
  display = false,
}: {
  rawMath: string
  display?: boolean
}) {
  // Chuẩn hoá ký hiệu toán học phổ biến
  let processed = rawMath
    .replace(/\\le(?:q)?\b/g, '≤')
    .replace(/\\ge(?:q)?\b/g, '≥')
    .replace(/\\times\b/g, '×')
    .replace(/\\pm\b/g, '±')
    .replace(/\\approx\b/g, '≈')
    .replace(/\\neq\b/g, '≠')
    .replace(/\\mu\b/g, 'µ')
    .replace(/\\cdot\b/g, '·')
    .replace(/\\infty\b/g, '∞')
    .replace(/\\text\{([^}]+)\}/g, '$1')

  // Phân tích phân số \frac{A}{B}
  const fracRegex = /\\frac\{([^{}]+)\}\{([^{}]+)\}/g
  const parts: React.ReactNode[] = []
  let lastIdx = 0
  let match: RegExpExecArray | null = fracRegex.exec(processed)

  while (match !== null) {
    if (match.index > lastIdx) {
      parts.push(processed.slice(lastIdx, match.index))
    }
    const num = match[1]
    const den = match[2]
    parts.push(
      <span
        key={`frac-${match.index}`}
        className="inline-flex flex-col items-center justify-center align-middle mx-1 text-2xs leading-tight"
      >
        <span className="border-b border-current px-0.5">{num}</span>
        <span className="px-0.5">{den}</span>
      </span>,
    )
    lastIdx = match.index + match[0].length
    match = fracRegex.exec(processed)
  }

  if (lastIdx < processed.length) {
    parts.push(processed.slice(lastIdx))
  }

  // Phân tích số mũ ^2 hoặc ^{abc} và chỉ số chân _2 hoặc _{abc}
  const formatExponentsAndSubscripts = (nodeList: React.ReactNode[]): React.ReactNode[] => {
    const result: React.ReactNode[] = []
    nodeList.forEach((node, nodeIdx) => {
      if (typeof node !== 'string') {
        result.push(node)
        return
      }
      const expSubRegex = /(\^\{[^}]+\}|\^[0-9a-zA-Z]+|_\{[^}]+\}|_[0-9a-zA-Z]+)/g
      let subLast = 0
      let subMatch: RegExpExecArray | null = expSubRegex.exec(node)
      while (subMatch !== null) {
        if (subMatch.index > subLast) {
          result.push(node.slice(subLast, subMatch.index))
        }
        const raw = subMatch[0]
        if (raw.startsWith('^')) {
          const val = raw.startsWith('^{') ? raw.slice(2, -1) : raw.slice(1)
          result.push(<sup key={`sup-${nodeIdx}-${subMatch.index}`}>{val}</sup>)
        } else {
          const val = raw.startsWith('_{') ? raw.slice(2, -1) : raw.slice(1)
          result.push(<sub key={`sub-${nodeIdx}-${subMatch.index}`}>{val}</sub>)
        }
        subLast = subMatch.index + raw.length
        subMatch = expSubRegex.exec(node)
      }
      if (subLast < node.length) {
        result.push(node.slice(subLast))
      }
    })
    return result
  }

  const renderedFormula = formatExponentsAndSubscripts(parts)

  if (display) {
    return (
      <div className="my-2 p-2 rounded border border-line bg-surface-muted text-center font-mono text-xs font-semibold text-primary overflow-x-auto select-all">
        {renderedFormula}
      </div>
    )
  }

  return (
    <span className="inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded border border-line bg-surface-muted font-mono text-xs font-semibold text-primary select-all">
      {renderedFormula}
    </span>
  )
}

/** Tokenizer nội dòng: trích dẫn, mã chip, toán LaTeX, in đậm, in nghiêng */
function renderInlineTokens(
  rawText: string,
  citationsMap: Map<number, TrichDanTraLoi>,
  onCitationClick?: (citation: TrichDanTraLoi, target: HTMLButtonElement) => void,
  keyPrefix = 't',
): React.ReactNode[] {
  if (!rawText) return []

  // Token regex nhận diện:
  // 1. Math display $$...$$ hoặc math inline $...$
  // 2. Inline code `...`
  // 3. Trích dẫn [n]
  // 4. In đậm **...** hoặc in nghiêng *...*
  // 5. Thực thể lâm sàng / hệ thống: DEMO-xx, YL-xx, NB-xx, T-THUOC-xx, DT-xx, TL-xx
  // 6. Chỉ số lâm sàng: CrCl = 16,0 mL/min, eGFR = ..., BMI = ...
  // 7. Mức độ cảnh báo: nghiem_trong/can_xem, can_luu_y/can_xem, v.v.
  // 8. API endpoints và commands: /api/..., uv run ...
  const TOKEN_REGEX =
    /(\$\$[\s\S]+?\$\$|\$(?!\$)[\s\S]+?\$|`[^`]+`|\[\d+\]|\*\*[^*]+?\*\*|\*[^*]+?\*|\b(?:DEMO-\d+|YL-[A-Z0-9-]+|NB-[A-Z0-9-]+|T-[A-Z0-9-]+|DT-[A-Z0-9-]+|TL-[A-Z0-9-]+)\b|\b(?:CrCl|eGFR|BMI|BSA)\s*=\s*\d+(?:[.,]\d+)?\s*(?:mL\/min|mL\/phút|kg\/m[²2]|m[²2])?\b|\b(?:nghiem_trong|can_luu_y|thieu_du_lieu|dat)(?:\/(?:can_xem|ngoai_hdsd))?\b|\/api\/[a-zA-Z0-9_/-]+|\b(?:uv|npm|python)\s+run\s+[a-zA-Z0-9_.: -]+)/g

  const nodes: React.ReactNode[] = []
  let lastIndex = 0
  let match: RegExpExecArray | null = TOKEN_REGEX.exec(rawText)

  while (match !== null) {
    if (match.index > lastIndex) {
      const plainChunk = rawText.slice(lastIndex, match.index)
      nodes.push(
        <span key={`${keyPrefix}-p-${lastIndex}`}>
          {formatClinicalText(plainChunk)}
        </span>,
      )
    }

    const token = match[0]
    const idx = match.index

    if (token.startsWith('$$') && token.endsWith('$$')) {
      const mathContent = token.slice(2, -2).trim()
      nodes.push(
        <SafeMathFormula key={`${keyPrefix}-m-${idx}`} rawMath={mathContent} display />,
      )
    } else if (token.startsWith('$') && token.endsWith('$')) {
      const mathContent = token.slice(1, -1).trim()
      nodes.push(
        <SafeMathFormula key={`${keyPrefix}-m-${idx}`} rawMath={mathContent} />,
      )
    } else if (token.startsWith('`') && token.endsWith('`')) {
      const codeContent = token.slice(1, -1)
      nodes.push(
        <ClinicalEntityChip key={`${keyPrefix}-c-${idx}`}>
          {codeContent}
        </ClinicalEntityChip>,
      )
    } else if (/^\[\d+\]$/.test(token)) {
      const num = Number(token.slice(1, -1))
      const citation = citationsMap.get(num)
      nodes.push(
        <button
          key={`${keyPrefix}-cit-${idx}`}
          type="button"
          onClick={(e) => {
            const activeCitation: TrichDanTraLoi = citation ?? {
              so: num,
              loai_ma: 'du_lieu',
              nhan: `Nguồn tham chiếu [${num}]`,
              ban_ghi_id: null,
            }
            onCitationClick?.(activeCitation, e.currentTarget)
          }}
          title={citation ? citation.nhan : `Trích dẫn ${token}`}
          aria-label={`Mở trích dẫn ${token}: ${citation ? citation.nhan : 'Xem căn cứ'}`}
          className="mx-0.5 inline-flex cursor-pointer items-center rounded-sm border border-primary-line bg-primary-soft px-1.5 py-0.5 font-mono text-2xs font-semibold text-primary tabular-nums hover:bg-primary hover:text-on-primary transition-colors duration-120"
        >
          {token}
        </button>,
      )
    } else if (token.startsWith('**') && token.endsWith('**')) {
      const innerText = token.slice(2, -2)
      nodes.push(
        <strong key={`${keyPrefix}-b-${idx}`} className="font-semibold text-fg">
          {renderInlineTokens(innerText, citationsMap, onCitationClick, `${keyPrefix}-b-${idx}`)}
        </strong>,
      )
    } else if (token.startsWith('*') && token.endsWith('*')) {
      const innerText = token.slice(1, -1)
      nodes.push(
        <em key={`${keyPrefix}-i-${idx}`} className="italic text-fg">
          {renderInlineTokens(innerText, citationsMap, onCitationClick, `${keyPrefix}-i-${idx}`)}
        </em>,
      )
    } else {
      // Thực thể lâm sàng / mã lệnh / chỉ số -> render dạng chip xanh ảnh 2
      nodes.push(
        <ClinicalEntityChip key={`${keyPrefix}-chip-${idx}`}>
          {formatClinicalText(token)}
        </ClinicalEntityChip>,
      )
    }

    lastIndex = idx + token.length
    match = TOKEN_REGEX.exec(rawText)
  }

  if (lastIndex < rawText.length) {
    const trailingChunk = rawText.slice(lastIndex)
    nodes.push(
      <span key={`${keyPrefix}-p-${lastIndex}`}>
        {formatClinicalText(trailingChunk)}
      </span>,
    )
  }

  return nodes
}

interface BlockItem {
  type: 'paragraph' | 'ordered-list' | 'unordered-list' | 'heading' | 'code-block' | 'quote' | 'table'
  table?: { headers: string[]; align: ('left' | 'center' | 'right')[]; rows: string[][]; total: number; title: string; truncated: boolean }
  items?: { prefix?: string; content: string }[]
  content?: string
  level?: number
}

/** Phân tích các khối văn bản (Paragraphs, Lists, Headings, Code blocks) */
function splitTableRow(line: string): string[] {
  const cells: string[] = []
  let cell = ''
  const value = line.trim().replace(/^\|/, '').replace(/(?<!\\)\|$/, '')
  for (let i = 0; i < value.length; i++) {
    if (value[i] === '\\' && value[i + 1] === '|') { cell += '|'; i++ }
    else if (value[i] === '|') { cells.push(cell.trim()); cell = '' }
    else cell += value[i]
  }
  cells.push(cell.trim())
  return cells
}

function limitCell(cell: string): string {
  return cell.length > 1000 ? `${cell.slice(0, 1000)}…` : cell
}

function parseBlocks(rawText: string): BlockItem[] {
  const lines = rawText.split('\n')
  const blocks: BlockItem[] = []

  let currentHeading = ''
  let currentList: { type: 'ordered-list' | 'unordered-list'; items: { prefix?: string; content: string }[] } | null = null

  const flushList = () => {
    if (currentList) {
      blocks.push(currentList)
      currentList = null
    }
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const trimmed = line.trim()

    if (!trimmed) {
      flushList()
      continue
    }

    if (trimmed.startsWith('|') && i + 1 < lines.length && lines[i + 1].trim().startsWith('|')) {
      const headers = splitTableRow(trimmed)
      const separators = splitTableRow(lines[i + 1])
      if (headers.length === separators.length && separators.every((cell) => /^:?-{3,}:?$/.test(cell))) {
        flushList()
        const count = Math.min(headers.length, 20)
        const align = separators.slice(0, count).map((cell): 'left' | 'center' | 'right' =>
          cell.startsWith(':') && cell.endsWith(':') ? 'center' : cell.endsWith(':') ? 'right' : 'left',
        )
        const rows: string[][] = []
        let total = 0
        let longCell = headers.some((cell) => cell.length > 1000)
        i += 2
        while (i < lines.length && lines[i].trim().startsWith('|')) {
          total++
          if (rows.length < 200) {
            const cells = splitTableRow(lines[i])
            longCell ||= cells.some((cell) => cell.length > 1000)
            rows.push(Array.from({ length: count }, (_, index) => limitCell(cells[index] ?? '')))
          }
          i++
        }
        i--
        let previousLine = i - total - 2
        while (previousLine >= 0 && !lines[previousLine].trim()) previousLine--
        const boldTitle = /^\*\*(.+?)\*\*$/.exec(lines[previousLine]?.trim() ?? '')
        blocks.push({ type: 'table', table: { headers: headers.slice(0, count).map(limitCell), align, rows, total, title: currentHeading || boldTitle?.[1] || 'Bảng', truncated: headers.length > 20 || total > 200 || longCell } })
        continue
      }
    }

    // Danh sách có thứ tự: 1) hoặc 1.
    const orderedMatch = /^(\d+[.)])\s+(.*)$/.exec(trimmed)
    if (orderedMatch) {
      if (!currentList || currentList.type !== 'ordered-list') {
        flushList()
        currentList = { type: 'ordered-list', items: [] }
      }
      currentList.items.push({
        prefix: orderedMatch[1],
        content: orderedMatch[2],
      })
      continue
    }

    // Danh sách gạch đầu dòng: •, -, *
    const unorderedMatch = /^([•\-*])\s+(.*)$/.exec(trimmed)
    if (unorderedMatch) {
      if (!currentList || currentList.type !== 'unordered-list') {
        flushList()
        currentList = { type: 'unordered-list', items: [] }
      }
      currentList.items.push({
        prefix: unorderedMatch[1],
        content: unorderedMatch[2],
      })
      continue
    }

    // Khối tiêu đề ### hoặc ##
    const headingMatch = /^(#{1,3})\s+(.*)$/.exec(trimmed)
    if (headingMatch) {
      flushList()
      currentHeading = headingMatch[2]
      blocks.push({
        type: 'heading',
        level: headingMatch[1].length,
        content: headingMatch[2],
      })
      continue
    }

    // Trích dẫn >
    const quoteMatch = /^>\s+(.*)$/.exec(trimmed)
    if (quoteMatch) {
      flushList()
      blocks.push({
        type: 'quote',
        content: quoteMatch[1],
      })
      continue
    }

    // Dòng văn bản bình thường (đoạn văn)
    flushList()
    blocks.push({
      type: 'paragraph',
      content: trimmed,
    })
  }

  flushList()
  return blocks
}

function MarkdownTable({ table, citationsMap, onCitationClick }: {
  table: NonNullable<BlockItem['table']>
  citationsMap: Map<number, TrichDanTraLoi>
  onCitationClick?: ClinicalMarkdownProps['onCitationClick']
}) {
  const [open, setOpen] = useState(false)
  function handleCitation(citation: TrichDanTraLoi, target: HTMLButtonElement) {
    flushSync(() => setOpen(false))
    onCitationClick?.(citation, target)
  }
  const renderTable = (expanded: boolean) => (
    <div className={expanded ? 'min-h-0 min-w-0 max-w-full flex-1 overflow-auto' : 'max-h-80 max-w-full overflow-x-auto overflow-y-auto'}>
      <table className="w-full min-w-full border-collapse text-sm">
        <thead className="sticky top-0 z-10 bg-surface-muted"><tr>
          {table.headers.map((cell, index) => <th scope="col" key={index} style={{ textAlign: table.align[index] }} className={`min-w-[8rem] break-words border border-line px-3 py-2 font-semibold ${expanded ? '' : 'max-w-[28rem]'}`}>{renderInlineTokens(cell, citationsMap, expanded ? handleCitation : onCitationClick)}</th>)}
        </tr></thead>
        <tbody>{table.rows.map((row, rowIndex) => <tr key={rowIndex} className="even:bg-surface-muted/50">
          {row.map((cell, index) => <td key={index} style={{ textAlign: table.align[index] }} className={`min-w-[8rem] break-words border border-line px-3 py-2 ${expanded ? '' : 'max-w-[28rem]'}`}>{renderInlineTokens(cell, citationsMap, expanded ? handleCitation : onCitationClick)}</td>)}
        </tr>)}</tbody>
      </table>
      {table.truncated ? <p className="p-2 text-xs text-fg-muted">Bảng đã rút gọn: hiện {table.rows.length}/{table.total} dòng</p> : null}
    </div>
  )
  return <div className="min-w-0 max-w-full rounded-md border border-line">
    <Dialog open={open} onOpenChange={setOpen}>
      <div className="flex justify-end border-b border-line p-1">
        <DialogTrigger asChild><ExpandButton label="Mở rộng bảng" /></DialogTrigger>
      </div>
      {renderTable(false)}
      <DialogContent variant="fullscreen" aria-describedby={undefined}>
        <DialogHeader><DialogTitle>{table.title}</DialogTitle></DialogHeader>
        {renderTable(true)}
      </DialogContent>
    </Dialog>
  </div>
}

/**
 * Component hiển thị câu trả lời lâm sàng phong phú (Clinical Markdown):
 * - Hỗ trợ Markdown: ngắt dòng, danh sách gạch đầu dòng, danh sách thứ tự, in đậm, in nghiêng.
 * - Hỗ trợ LaTeX toán học an toàn thuần React JSX nodes.
 * - Nhấn mạnh tự động các mã ca, mã y lệnh, mã thuốc, chỉ số lâm sàng thành chip chữ xanh bo góc như ảnh 2.
 * - Giữ nguyên nút bấm tương tác xem trích dẫn căn cứ [1], [2].
 */
export function ClinicalMarkdown({
  text,
  citations = [],
  onCitationClick,
  className = '',
}: ClinicalMarkdownProps) {
  const citationsMap = useMemo(() => {
    const map = new Map<number, TrichDanTraLoi>()
    for (const c of citations) {
      map.set(c.so, c)
    }
    return map
  }, [citations])

  const blocks = useMemo(() => parseBlocks(text), [text])

  if (!text) return null

  return (
    <div className={`flex min-w-0 max-w-full flex-col gap-2.5 leading-relaxed text-fg break-words ${className}`}>
      {blocks.map((block, bIdx) => {
        if (block.type === 'table' && block.table) return <MarkdownTable key={`b-${bIdx}`} table={block.table} citationsMap={citationsMap} onCitationClick={onCitationClick} />
        if (block.type === 'paragraph' && block.content) {
          return (
            <p key={`b-${bIdx}`} className="text-sm leading-relaxed text-fg m-0">
              {renderInlineTokens(block.content, citationsMap, onCitationClick, `b-${bIdx}`)}
            </p>
          )
        }

        if (block.type === 'ordered-list' && block.items) {
          return (
            <ol key={`b-${bIdx}`} className="flex flex-col gap-2 my-1 pl-0 list-none">
              {block.items.map((item, itemIdx) => (
                <li key={`ol-${bIdx}-${itemIdx}`} className="flex items-start gap-2 text-sm leading-relaxed text-fg">
                  <span className="shrink-0 font-mono text-xs font-semibold text-primary pt-0.5 select-none">
                    {item.prefix}
                  </span>
                  <div className="min-w-0 flex-1">
                    {renderInlineTokens(item.content, citationsMap, onCitationClick, `ol-${bIdx}-${itemIdx}`)}
                  </div>
                </li>
              ))}
            </ol>
          )
        }

        if (block.type === 'unordered-list' && block.items) {
          return (
            <ul key={`b-${bIdx}`} className="flex flex-col gap-1.5 my-1 pl-0 list-none">
              {block.items.map((item, itemIdx) => (
                <li key={`ul-${bIdx}-${itemIdx}`} className="flex items-start gap-2 text-sm leading-relaxed text-fg">
                  <span className="shrink-0 text-primary pt-0.5 text-xs font-bold leading-none select-none">
                    •
                  </span>
                  <div className="min-w-0 flex-1">
                    {renderInlineTokens(item.content, citationsMap, onCitationClick, `ul-${bIdx}-${itemIdx}`)}
                  </div>
                </li>
              ))}
            </ul>
          )
        }

        if (block.type === 'heading' && block.content) {
          const Tag = block.level === 1 ? 'h3' : block.level === 2 ? 'h4' : 'h5'
          return (
            <Tag key={`b-${bIdx}`} className="font-semibold text-sm text-fg mt-2 mb-0.5">
              {renderInlineTokens(block.content, citationsMap, onCitationClick, `b-${bIdx}`)}
            </Tag>
          )
        }

        if (block.type === 'quote' && block.content) {
          return (
            <blockquote
              key={`b-${bIdx}`}
              className="border-l-2 border-primary/50 pl-3 my-1 text-xs text-fg-muted italic"
            >
              {renderInlineTokens(block.content, citationsMap, onCitationClick, `b-${bIdx}`)}
            </blockquote>
          )
        }

        return null
      })}
    </div>
  )
}
