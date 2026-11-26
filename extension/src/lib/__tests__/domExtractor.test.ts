import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { sanitizeTabsForUpload } from '../deidScrubber'
import { extractFromDocument, type DomDocumentLike, type DomElementLike } from '../domExtractor'
import { classifyLocalBaseline } from '../schemaCache'

/** Bộ phân tích HTML gọn nhẹ thuần Node để kiểm thử DOM Extractor không cần jsdom. */
interface ParsedNode extends DomElementLike {
  parent: ParsedNode | null
  attrs: Record<string, string>
  nodeList: ParsedNode[]
}

function parseTinyHtml(html: string): DomDocumentLike {
  const tokens = html.match(/<\/?[a-zA-Z0-9-]+(?:\s+[^>]*)?>|[^<]+/g) ?? []
  const findClosest = (startNode: ParsedNode, selector: string): ParsedNode | null => {
    let cur: ParsedNode | null = startNode
    while (cur) {
      if (matchesSingle(cur, selector)) return cur
      cur = cur.parent
    }
    return null
  }

  const root: ParsedNode = {
    tagName: 'BODY',
    id: '',
    attrs: {},
    textContent: '',
    parent: null,
    nodeList: [],
    getAttribute(name: string) {
      return root.attrs[name] ?? null
    },
    querySelectorAll(selector: string) {
      return matchSelector(root, selector)
    },
    closest(selector: string) {
      return findClosest(root, selector)
    },
  }

  let current = root
  const voidTags = new Set(['meta', 'br', 'hr', 'img', 'input', 'link'])

  for (const tok of tokens) {
    if (tok.startsWith('</')) {
      const tag = tok.slice(2, -1).trim().toUpperCase()
      let walker: ParsedNode | null = current
      while (walker && walker.tagName !== tag && walker !== root) {
        walker = walker.parent
      }
      if (walker && walker.parent) {
        current = walker.parent
      }
    } else if (tok.startsWith('<')) {
      const m = /^<([a-zA-Z0-9-]+)([\s\S]*?)\/?>$/.exec(tok)
      if (!m) continue
      const tag = m[1].toUpperCase()
      const attrRaw = m[2]
      const attrs: Record<string, string> = {}
      const attrRe = /([a-zA-Z0-9-:]+)\s*=\s*"([^"]*)"/g
      let am: RegExpExecArray | null
      while ((am = attrRe.exec(attrRaw)) !== null) {
        attrs[am[1]] = am[2]
      }
      const el: ParsedNode = {
        tagName: tag,
        id: attrs.id ?? '',
        attrs,
        textContent: '',
        parent: current,
        nodeList: [],
        getAttribute(name: string) {
          return el.attrs[name] ?? null
        },
        querySelectorAll(selector: string) {
          return matchSelector(el, selector)
        },
        closest(selector: string) {
          return findClosest(el, selector)
        },
      }
      if (current.nodeList.length > 0) {
        current.nodeList[current.nodeList.length - 1].nextElementSibling = el
      }
      current.nodeList.push(el)
      if (!voidTags.has(m[1].toLowerCase()) && !tok.endsWith('/>')) {
        current = el
      }
    } else {
      const addText = (node: ParsedNode | null) => {
        if (!node) return
        node.textContent = (node.textContent ?? '') + tok
        addText(node.parent)
      }
      addText(current)
    }
  }

  function matchesSingle(node: ParsedNode, selectorGroup: string): boolean {
    return selectorGroup.split(',').some((raw) => {
      const s = raw.trim()
      if (!s) return false
      if (s === '[id^="finding-"]') return (node.id ?? '').startsWith('finding-')
      if (s === '[data-testid="ai-review-drawer"]') {
        return node.attrs['data-testid'] === 'ai-review-drawer'
      }
      if (s === '[data-cdss-ignore="true"]') return node.attrs['data-cdss-ignore'] === 'true'
      if (s === '[aria-label="Bốn chỉ số lâm sàng"]') {
        return node.attrs['aria-label'] === 'Bốn chỉ số lâm sàng'
      }
      if (s === 'section[aria-label]') {
        return node.tagName === 'SECTION' && typeof node.attrs['aria-label'] === 'string'
      }
      const parts = s.split(/\s+/)
      const targetTag = parts[parts.length - 1].toUpperCase()
      return node.tagName === targetTag
    })
  }

  function matchSelector(scope: ParsedNode, selector: string): ParsedNode[] {
    const out: ParsedNode[] = []
    const walk = (n: ParsedNode) => {
      for (const child of n.nodeList) {
        if (matchesSingle(child, selector)) out.push(child)
        walk(child)
      }
    }
    walk(scope)
    return out
  }

  return {
    title: 'Hồ sơ giả lập DEMO-02',
    location: {
      href: 'http://localhost:5173/app/y-lenh/DEMO-02',
      origin: 'http://localhost:5173',
    },
    body: root,
    querySelectorAll(selector: string) {
      return matchSelector(root, selector)
    },
  }
}

describe('domExtractor trên HTML giống web hiện tại', () => {
  it('đọc được cả <details> đóng và loại trừ hoàn toàn <aside> / Thẩm định có sẵn', () => {
    const fixturePath = resolve(
      __dirname,
      '../../../../tests/extension_api/fixtures/emr_demo02_sanitized.html',
    )
    const html = readFileSync(fixturePath, 'utf-8')
    const doc = parseTinyHtml(html)
    const result = extractFromDocument(doc, { tabId: 42 })

    const labels = result.uniqueFields.map((f) => f.ten_nhan)
    expect(labels).toContain('Họ và tên')
    expect(labels).toContain('Cân nặng')
    expect(labels).toContain('Chẩn đoán chính')

    const joinedSections = result.sections.map((s) => `${s.title}: ${s.text}`).join('\n')
    expect(joinedSections).toContain('Creatinin máu | 212 | umol/L')
    expect(joinedSections).toContain('BS Nguyễn Văn An')
    // Bắt buộc không đọc khung Thẩm định / AI Drawer sẵn có trên màn hình.
    expect(joinedSections).not.toContain('Không được lấy sẵn nhận định này')
  })

  it('đọc thẻ bệnh nhân ở cột bên trái nhưng vẫn chặn <nav>, Chỉ số tính sẵn và Khung trợ lý AI', () => {
    const sidebarHtml = `
      <body>
        <aside aria-label="Thanh bên điều hướng">
          <nav>
            <a href="/app">Hồ sơ cần duyệt</a>
            <a href="/thuoc">Tra cứu thuốc</a>
          </nav>
          <div>
            <div>
              <h2>NGUYỄN THỊ 42</h2>
              <p>Nữ · 78 tuổi</p>
            </div>
            <dl>
              <div><dt>Mã hồ sơ</dt><dd>HS-042</dd></div>
              <div><dt>Ngày sinh</dt><dd>02/12/1947</dd></div>
              <div><dt>Cân nặng</dt><dd>56 kg</dd></div>
              <div><dt>Chiều cao</dt><dd>158 cm</dd></div>
            </dl>
            <div>
              <span>BHYT</span>
              <div><span>GD4010000000042</span><span>hạn 31/12/2030</span></div>
            </div>
            <div>
              <span>Dị ứng</span>
              <div>Đã hỏi, không ghi nhận dị ứng</div>
            </div>
            <div>
              <span>Chẩn đoán</span>
              <ul>
                <li>Rung nhĩ (I48)</li>
                <li>Tăng huyết áp (I10)</li>
              </ul>
            </div>
            <div>
              <span>Chỉ số</span>
              <div aria-label="Bốn chỉ số lâm sàng">
                <dl><dt>BMI</dt><dd>22,4 kg/m2</dd></dl>
              </div>
            </div>
          </div>
        </aside>
        <aside aria-label="Khung trợ lý AI">
          <dl><dt>Nhận định AI</dt><dd>Không được đọc khung trợ lý AI</dd></dl>
        </aside>
      </body>
    `
    const doc = parseTinyHtml(sidebarHtml)
    const extracted = extractFromDocument(doc, { tabId: 7 })

    const byLabel = new Map(extracted.fieldPairs.map((p) => [p.label, p.value]))
    expect(byLabel.get('Họ tên')).toBe('NGUYỄN THỊ 42')
    expect(byLabel.get('Giới tính / Tuổi')).toBe('Nữ · 78 tuổi')
    expect(byLabel.get('Mã hồ sơ')).toBe('HS-042')
    expect(byLabel.get('Ngày sinh')).toBe('02/12/1947')
    expect(byLabel.get('Cân nặng')).toBe('56 kg')
    expect(byLabel.get('Chiều cao')).toBe('158 cm')
    expect(byLabel.get('BHYT')).toContain('GD4010000000042')
    expect(byLabel.get('Dị ứng')).toBe('Đã hỏi, không ghi nhận dị ứng')
    expect(byLabel.get('Chẩn đoán')).toContain('Rung nhĩ (I48)')

    // Phải loại bỏ khối Chỉ số tính sẵn và Khung trợ lý AI bên phải.
    expect(byLabel.has('BMI')).toBe(false)
    expect(byLabel.has('Nhận định AI')).toBe(false)

    // Đưa qua lớp De-ID: cắt Họ tên, Mã hồ sơ, Ngày sinh (chuyển tuổi), BHYT; giữ lại dữ liệu lâm sàng.
    const classified = classifyLocalBaseline(extracted.uniqueFields)
    const { sections } = sanitizeTabsForUpload([extracted], classified, new Date(2026, 10, 26))
    const textOut = sections.map((s) => s.noi_dung).join('\n')
    expect(textOut).not.toContain('NGUYỄN THỊ 42')
    expect(textOut).not.toContain('HS-042')
    expect(textOut).not.toContain('GD4010000000042')
    expect(textOut).not.toContain('02/12/1947')
    expect(textOut).toContain('Cân nặng: 56 kg')
    expect(textOut).toContain('Chiều cao: 158 cm')
    expect(textOut).toContain('Dị ứng: Đã hỏi, không ghi nhận dị ứng')
    expect(textOut).toContain('Chẩn đoán: Rung nhĩ (I48)')
  })

  it('không đưa tiêu đề cột ngày giờ (vd. 26/09/2026 08:00) vào danh sách nhãn classify-schema', () => {
    const labHtml = `
      <body>
        <section aria-label="Kết quả xét nghiệm">
          <table>
            <thead>
              <tr>
                <th>STT</th>
                <th>Chỉ số xét nghiệm</th>
                <th>26/09/2026 08:00</th>
                <th>Đánh giá</th>
              </tr>
            </thead>
            <tbody>
              <tr><td>1</td><td>INR</td><td>2,4</td><td>Trong tham chiếu</td></tr>
            </tbody>
          </table>
        </section>
      </body>
    `
    const extracted = extractFromDocument(parseTinyHtml(labHtml), { tabId: 9 })
    const labelNames = extracted.uniqueFields.map((f) => f.ten_nhan)
    expect(labelNames).toContain('Chỉ số xét nghiệm')
    expect(labelNames).not.toContain('26/09/2026 08:00')
    expect(extracted.sections[0]?.text).toContain('INR | 2,4')
  })
})
