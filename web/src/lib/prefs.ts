import type { QueueFilter } from './queue.ts'
import { parseThemePreference } from './theme.ts'
import type { ThemePreference } from './theme.ts'

export const ASSISTANT_MIN_WIDTH = 320
export const ASSISTANT_MAX_WIDTH = 560
export const ASSISTANT_DEFAULT_WIDTH = 400

export interface UiPrefs {
  selectedCaseId: string | null
  queueFilter: QueueFilter
  queueCollapsed: boolean
  chatCollapsed: boolean
  assistantWidth: number
}

const PREFIX = 'pharm_review_ui_'
const KEY_SELECTED_CASE = `${PREFIX}selected_case_id`
const KEY_QUEUE_FILTER = `${PREFIX}queue_filter`
const KEY_QUEUE_COLLAPSED = `${PREFIX}queue_collapsed`
const KEY_CHAT_COLLAPSED = `${PREFIX}chat_collapsed`
const KEY_ASSISTANT_WIDTH = `${PREFIX}assistant_width`
const KEY_THEME = `${PREFIX}theme`

function safeGetStorage(): Storage | null {
  try {
    if (typeof window === 'undefined' || typeof window.localStorage === 'undefined') {
      return null
    }
    return window.localStorage
  } catch {
    return null
  }
}

export function loadThemePreference(): ThemePreference {
  try {
    return parseThemePreference(safeGetStorage()?.getItem(KEY_THEME))
  } catch {
    return 'system'
  }
}

export function saveThemePreference(preference: ThemePreference): void {
  try {
    safeGetStorage()?.setItem(KEY_THEME, preference)
  } catch {
    // Vẫn đổi màu trong phiên khi trình duyệt chặn bộ nhớ.
  }
}

function isQueueFilter(value: string | null): value is QueueFilter {
  return value === 'tat_ca' || value === 'can_xem' || value === 'da_phan_hoi_het'
}

export function clampAssistantWidth(raw: number): number {
  if (!Number.isFinite(raw)) {
    return ASSISTANT_DEFAULT_WIDTH
  }
  return Math.min(ASSISTANT_MAX_WIDTH, Math.max(ASSISTANT_MIN_WIDTH, Math.round(raw)))
}

export function loadUiPrefs(): UiPrefs {
  const storage = safeGetStorage()
  if (!storage) {
    return {
      selectedCaseId: null,
      queueFilter: 'tat_ca',
      queueCollapsed: false,
      chatCollapsed: false,
      assistantWidth: ASSISTANT_DEFAULT_WIDTH,
    }
  }
  try {
    const selectedCaseId = storage.getItem(KEY_SELECTED_CASE)
    const rawFilter = storage.getItem(KEY_QUEUE_FILTER)
    const rawQueueCollapsed = storage.getItem(KEY_QUEUE_COLLAPSED)
    const rawChatCollapsed = storage.getItem(KEY_CHAT_COLLAPSED)
    const rawWidth = storage.getItem(KEY_ASSISTANT_WIDTH)
    const parsedWidth = rawWidth ? Number(rawWidth) : ASSISTANT_DEFAULT_WIDTH
    return {
      selectedCaseId: selectedCaseId || null,
      queueFilter: isQueueFilter(rawFilter) ? rawFilter : 'tat_ca',
      queueCollapsed: rawQueueCollapsed === '1',
      chatCollapsed: rawChatCollapsed === '1',
      assistantWidth: clampAssistantWidth(parsedWidth),
    }
  } catch {
    return {
      selectedCaseId: null,
      queueFilter: 'tat_ca',
      queueCollapsed: false,
      chatCollapsed: false,
      assistantWidth: ASSISTANT_DEFAULT_WIDTH,
    }
  }
}

export function saveSelectedCaseId(caId: string | null): void {
  const storage = safeGetStorage()
  if (!storage) {
    return
  }
  try {
    if (caId === null) {
      storage.removeItem(KEY_SELECTED_CASE)
    } else {
      storage.setItem(KEY_SELECTED_CASE, caId)
    }
  } catch {
    // Bỏ qua khi trình duyệt chặn ghi tuỳ chọn giao diện.
  }
}

export function saveQueueFilter(filter: QueueFilter): void {
  const storage = safeGetStorage()
  if (!storage) {
    return
  }
  try {
    storage.setItem(KEY_QUEUE_FILTER, filter)
  } catch {
    // Bỏ qua khi trình duyệt chặn ghi tuỳ chọn giao diện.
  }
}

export function saveQueueCollapsed(collapsed: boolean): void {
  const storage = safeGetStorage()
  if (!storage) {
    return
  }
  try {
    storage.setItem(KEY_QUEUE_COLLAPSED, collapsed ? '1' : '0')
  } catch {
    // Bỏ qua khi trình duyệt chặn ghi tuỳ chọn giao diện.
  }
}

export function saveChatCollapsed(collapsed: boolean): void {
  const storage = safeGetStorage()
  if (!storage) {
    return
  }
  try {
    storage.setItem(KEY_CHAT_COLLAPSED, collapsed ? '1' : '0')
  } catch {
    // Bỏ qua khi trình duyệt chặn ghi tuỳ chọn giao diện.
  }
}

export function saveAssistantWidth(width: number): void {
  const storage = safeGetStorage()
  if (!storage) {
    return
  }
  try {
    storage.setItem(KEY_ASSISTANT_WIDTH, String(clampAssistantWidth(width)))
  } catch {
    // Bỏ qua khi trình duyệt chặn ghi tuỳ chọn giao diện.
  }
}
