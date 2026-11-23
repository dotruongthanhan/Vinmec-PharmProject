import { useEffect, useId, useRef, useState } from 'react'
import type { KeyboardEvent, ReactNode, RefObject } from 'react'
import { apiClient } from '@/api/index'
import type { GoiYThuoc, KetQuaGoiYThuoc } from '@/api/types'
import { cn } from '@/lib/cn'
import {
  SUGGEST_CACHE_MAX_KEYS,
  SUGGEST_KIND_LABELS,
  comboboxInitialActiveIndex,
  formatIngredientSummary,
  resolveComboboxKeyDown,
  setBoundedCache,
  splitHighlightSegments,
} from '@/lib/lookup'

export interface DrugNameComboboxProps {
  value: string
  onValueChange: (value: string) => void
  onSelect: (item: GoiYThuoc) => void
  onEnterFreeText?: () => void
  onKeyDown?: (event: KeyboardEvent<HTMLInputElement>) => void
  onBlur?: () => void
  placeholder?: string
  id?: string
  disabled?: boolean
  ariaLabel?: string
  ariaDescribedBy?: string
  type?: 'text' | 'search'
  className?: string
  inputClassName?: string
  leadingIcon?: ReactNode
  inputRef?: RefObject<HTMLInputElement | null>
  fetchSuggest?: (q: string, options?: { signal?: AbortSignal }) => Promise<KetQuaGoiYThuoc>
  initialResult?: KetQuaGoiYThuoc | null
}

/** Ô gõ tên thuốc kèm danh sách gợi ý theo mẫu combobox WAI-ARIA 1.2. */
export function DrugNameCombobox({
  value,
  onValueChange,
  onSelect,
  onEnterFreeText,
  onKeyDown,
  onBlur,
  placeholder,
  id,
  disabled = false,
  ariaLabel,
  ariaDescribedBy,
  type = 'text',
  className,
  inputClassName,
  leadingIcon,
  inputRef,
  fetchSuggest = (q, options) => apiClient.suggestDrugs(q, options),
  initialResult = null,
}: DrugNameComboboxProps) {
  const generatedId = useId()
  const inputId = id ?? `${generatedId}-input`
  const listboxId = `${generatedId}-listbox`

  const [result, setResult] = useState<KetQuaGoiYThuoc | null>(() => initialResult)
  // Truy vấn ứng với `result`: khác giá trị đang gõ nghĩa là danh sách đã cũ.
  const [resultQuery, setResultQuery] = useState<string | null>(() =>
    initialResult ? value.trim() : null,
  )
  const [open, setOpen] = useState<boolean>(() => Boolean(initialResult))
  const [activeIndex, setActiveIndex] = useState<number>(() =>
    initialResult ? comboboxInitialActiveIndex(initialResult.ket_qua) : -1,
  )

  const cacheRef = useRef<Map<string, KetQuaGoiYThuoc>>(new Map())
  const controllerRef = useRef<AbortController | null>(null)
  const fetchSuggestRef = useRef(fetchSuggest)
  const skipValueRef = useRef<string | null>(initialResult ? value.trim() : null)
  // Chỉ gợi ý sau khi người dùng tự gõ: vào trang với `?q=` sẵn thì không tự mở danh sách.
  const userEditedRef = useRef<boolean>(false)
  // Enter bấm khi gợi ý cho đúng chuỗi đó chưa về: chờ kết quả rồi mới quyết định.
  const pendingEnterRef = useRef<string | null>(null)
  const onSelectRef = useRef(onSelect)
  const onEnterFreeTextRef = useRef(onEnterFreeText)

  useEffect(() => {
    fetchSuggestRef.current = fetchSuggest
    onSelectRef.current = onSelect
    onEnterFreeTextRef.current = onEnterFreeText
  }, [fetchSuggest, onSelect, onEnterFreeText])

  /** Có kết quả cho chuỗi đang chờ Enter: chọn mục khớp chính xác/tiền tố, không thì giữ chữ tự do. */
  const resolvePendingEnter = (query: string, res: KetQuaGoiYThuoc | null) => {
    if (pendingEnterRef.current !== query) return false
    pendingEnterRef.current = null
    const index = res ? comboboxInitialActiveIndex(res.ket_qua) : -1
    setOpen(false)
    setActiveIndex(-1)
    if (res && index >= 0) {
      const item = res.ket_qua[index]
      skipValueRef.current = item.gia_tri_gui.trim()
      onSelectRef.current(item)
    } else {
      onEnterFreeTextRef.current?.()
    }
    return true
  }

  useEffect(() => {
    const trimmed = value.trim()
    if (pendingEnterRef.current !== null && pendingEnterRef.current !== trimmed) {
      pendingEnterRef.current = null
    }
    if (skipValueRef.current !== null && trimmed === skipValueRef.current) {
      skipValueRef.current = null
      return
    }
    skipValueRef.current = null

    if (disabled || trimmed.length < 2 || !userEditedRef.current) {
      controllerRef.current?.abort()
      setOpen(false)
      setResult(null)
      setResultQuery(null)
      setActiveIndex(-1)
      return
    }

    const cached = cacheRef.current.get(trimmed)
    if (cached) {
      controllerRef.current?.abort()
      setResult(cached)
      setResultQuery(trimmed)
      setOpen(true)
      setActiveIndex(comboboxInitialActiveIndex(cached.ket_qua))
      return
    }

    const timer = setTimeout(() => {
      controllerRef.current?.abort()
      const controller = new AbortController()
      controllerRef.current = controller
      void fetchSuggestRef.current(trimmed, { signal: controller.signal })
        .then((res) => {
          if (controller.signal.aborted) return
          setBoundedCache(cacheRef.current, trimmed, res, SUGGEST_CACHE_MAX_KEYS)
          setResult(res)
          setResultQuery(trimmed)
          if (resolvePendingEnter(trimmed, res)) return
          setOpen(true)
          setActiveIndex(comboboxInitialActiveIndex(res.ket_qua))
        })
        .catch((err: unknown) => {
          if (controller.signal.aborted) return
          if (
            (err instanceof DOMException && err.name === 'AbortError') ||
            (err instanceof Error && err.name === 'AbortError')
          ) {
            return
          }
          // Lỗi mạng → đóng danh sách lặng lẽ; ô nhập vẫn dùng được bình thường.
          setOpen(false)
          setResult(null)
          setResultQuery(null)
          setActiveIndex(-1)
          resolvePendingEnter(trimmed, null)
        })
    }, 150)

    return () => {
      clearTimeout(timer)
      controllerRef.current?.abort()
    }
  }, [value, disabled])

  const trimmedValue = value.trim()
  const resultIsFresh = resultQuery !== null && resultQuery === trimmedValue
  // Danh sách của chuỗi cũ không được dùng để chọn bằng bàn phím.
  const items = resultIsFresh ? (result?.ket_qua ?? []) : []
  const hasExactOrPrefix = items.some(
    (item) => item.khop === 'chinh_xac' || item.khop === 'tien_to',
  )
  const showCorrectionBanner =
    open && items.length > 0 && !hasExactOrPrefix && Boolean(result?.goi_y_sua)
  const activeOptionId =
    open && activeIndex >= 0 && activeIndex < items.length
      ? `${listboxId}-option-${activeIndex}`
      : undefined

  const closeList = () => {
    setOpen(false)
    setActiveIndex(-1)
  }

  const handleSelectItem = (item: GoiYThuoc) => {
    skipValueRef.current = item.gia_tri_gui.trim()
    closeList()
    onSelect(item)
  }

  const handleInputKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    // Gõ nhanh rồi Enter khi gợi ý cho đúng chuỗi này chưa về: chờ kết quả thay vì thêm chữ tự do.
    if (
      event.key === 'Enter' &&
      !disabled &&
      userEditedRef.current &&
      trimmedValue.length >= 2 &&
      !resultIsFresh
    ) {
      event.preventDefault()
      pendingEnterRef.current = trimmedValue
      return
    }
    const decision = resolveComboboxKeyDown({
      key: event.key,
      open,
      items,
      activeIndex,
    })
    if (decision.type === 'move') {
      event.preventDefault()
      setActiveIndex(decision.nextIndex)
      return
    }
    if (decision.type === 'select') {
      event.preventDefault()
      handleSelectItem(decision.item)
      return
    }
    if (decision.type === 'close') {
      if (decision.preventDefault) event.preventDefault()
      closeList()
      return
    }
    if (decision.type === 'free_text') {
      if (onEnterFreeText) {
        event.preventDefault()
        closeList()
        onEnterFreeText()
        return
      }
      closeList()
    }
    onKeyDown?.(event)
  }

  return (
    <div className={cn('relative', className)}>
      {leadingIcon}
      <input
        id={inputId}
        ref={inputRef}
        type={type}
        value={value}
        disabled={disabled}
        autoComplete="off"
        role="combobox"
        aria-expanded={open}
        aria-controls={listboxId}
        aria-autocomplete="list"
        aria-haspopup="listbox"
        aria-activedescendant={activeOptionId}
        aria-label={ariaLabel}
        aria-describedby={ariaDescribedBy}
        placeholder={placeholder}
        onChange={(event) => {
          userEditedRef.current = true
          onValueChange(event.target.value)
        }}
        onKeyDown={handleInputKeyDown}
        onBlur={() => {
          closeList()
          onBlur?.()
        }}
        className={inputClassName}
      />

      {open && result && resultIsFresh ? (
        <div
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) event.preventDefault()
          }}
          className="absolute top-full left-0 z-30 mt-1 w-full min-w-[280px] overflow-hidden rounded-md border border-line bg-surface shadow-md"
        >
          {showCorrectionBanner && result.goi_y_sua && items[0] ? (
            <button
              type="button"
              onMouseDown={(event) => {
                event.preventDefault()
                handleSelectItem(items[0])
              }}
              className="flex w-full cursor-pointer items-center gap-1 border-b border-line bg-surface-muted px-3 py-2 text-left text-xs text-fg-muted hover:bg-surface-hover"
            >
              <span>Có phải ý bạn là</span>
              <strong className="font-semibold text-fg">{result.goi_y_sua}</strong>
              <span>?</span>
            </button>
          ) : null}

          <ul id={listboxId} role="listbox" className="max-h-72 overflow-y-auto py-1">
            {items.length === 0 ? (
              <li role="presentation" className="px-3 py-2 text-sm text-fg-subtle">
                Không tìm thấy trong danh mục
              </li>
            ) : (
              items.map((item, index) => {
                const optionId = `${listboxId}-option-${index}`
                const isActive = index === activeIndex
                const segments = splitHighlightSegments(item.nhan, value)
                const ingredients = formatIngredientSummary(item)
                return (
                  <li
                    key={`${item.loai}-${item.gia_tri_gui}-${index}`}
                    id={optionId}
                    role="option"
                    aria-selected={isActive}
                    onMouseDown={(event) => {
                      event.preventDefault()
                      handleSelectItem(item)
                    }}
                    onMouseEnter={() => setActiveIndex(index)}
                    className={cn(
                      'flex min-h-8 cursor-pointer items-baseline justify-between gap-2 px-3 py-1.5 text-sm transition-colors duration-120',
                      isActive ? 'bg-primary-soft text-fg' : 'text-fg hover:bg-surface-hover',
                    )}
                  >
                    <span className="min-w-0 flex-1">
                      <span className="break-words">
                        {segments.map((seg, segIndex) =>
                          seg.match ? (
                            <strong key={segIndex} className="font-semibold text-fg">
                              {seg.text}
                            </strong>
                          ) : (
                            <span key={segIndex}>{seg.text}</span>
                          ),
                        )}
                      </span>
                      {ingredients ? (
                        <span className="ml-1.5 text-xs text-fg-subtle">→ {ingredients}</span>
                      ) : null}
                    </span>
                    <span className="shrink-0 rounded-sm border border-line bg-surface-muted px-1.5 py-0.5 text-2xs font-medium text-fg-muted">
                      {SUGGEST_KIND_LABELS[item.loai]}
                    </span>
                  </li>
                )
              })
            )}
          </ul>
        </div>
      ) : null}
    </div>
  )
}
