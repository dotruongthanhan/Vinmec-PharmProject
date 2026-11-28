import { isValidElement } from 'react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import doanCases from './fixtures/doan.json'
import type { BoDuLieu } from '../nguPhap'

const hooks = vi.hoisted(() => {
  let values: unknown[] = []
  let index = 0
  return {
    reset: () => { values = []; index = 0 },
    next: () => { index = 0 },
    useState: (initial: unknown) => {
      const slot = index++
      if (!(slot in values)) values[slot] = typeof initial === 'function' ? initial() : initial
      return [values[slot], (value: unknown) => {
        values[slot] = typeof value === 'function' ? value(values[slot]) : value
      }]
    },
    useMemo: (fn: () => unknown) => fn(),
    useRef: (value: unknown) => ({ current: value }),
    useEffect: () => {},
    useDeferredValue: (value: unknown) => value,
  }
})

vi.mock('react', async (original) => ({
  ...(await original<typeof import('react')>()),
  ...hooks,
}))

import { BangDuLieuGoc, KhungMinhHoa } from '../KhungMinhHoa'

function findElement(node: ReactNode, predicate: (element: React.ReactElement<any>) => boolean): React.ReactElement<any> | undefined {
  if (Array.isArray(node)) {
    for (const child of node) {
      const found = findElement(child, predicate)
      if (found) return found
    }
    return undefined
  }
  if (!isValidElement(node)) return undefined
  if (predicate(node)) return node
  return findElement((node.props as { children?: ReactNode }).children, predicate)
}

function countTables(node: ReactNode): number {
  if (Array.isArray(node)) return node.reduce((count, child) => count + countTables(child), 0)
  if (!isValidElement(node)) return 0
  return Number(node.type === BangDuLieuGoc) + countTables((node.props as { children?: ReactNode }).children)
}

describe('khung dòng thời gian', () => {
  it('chuyển từ hình đoạn sang bảng với cùng bộ dữ liệu', () => {
    hooks.reset()
    const example = doanCases[0]
    const data = [example.bo_du_lieu as unknown as BoDuLieu]
    const render = () => {
      hooks.next()
      return KhungMinhHoa({ dacTa: example.dac_ta, boDuLieu: data })
    }
    const first = render()
    const button = findElement(first, (el) => el.props['aria-label'] === 'Xem dạng bảng')
    expect(button).toBeDefined()
    expect(countTables(first)).toBe(1)
    button!.props.onClick()
    const second = render()
    expect(findElement(second, (el) => el.props['aria-label'] === 'Ẩn bảng')).toBeDefined()
    expect(countTables(second)).toBe(2)
    const table = findElement(second, (el) => el.type === BangDuLieuGoc)
    expect(table?.props.boDuLieu).toEqual(data)
    expect(table?.props.boDuLieu[0].dong[0].bat_dau).toBe('2026-11-01T08:00:00+07:00')
  })
})
