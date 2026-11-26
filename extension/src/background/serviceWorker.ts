/**
 * Manifest V3 Service Worker phi trạng thái (không lưu biến toàn cục).
 * Mở Side Panel khi bấm biểu tượng tiện ích và giữ trạng thái phiên trong chrome.storage.session.
 */

import { injectedTabDomSnapshot } from '../lib/domExtractor'
import type { BrowserTabSummary, RawTabExtraction } from '../lib/types'

const SESSION_STORAGE_KEY = 'cdss_ext_active_session_v1'

function configureSidePanelBehavior(): void {
  if (chrome.sidePanel?.setPanelBehavior) {
    void chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {
      // Bỏ qua trên phiên bản trình duyệt không hỗ trợ cờ này.
    })
  }
}

configureSidePanelBehavior()
chrome.runtime.onInstalled.addListener(() => {
  configureSidePanelBehavior()
})

type WorkerRequest =
  | { type: 'LIST_TABS' }
  | { type: 'EXTRACT_TABS'; tabIds: number[] }
  | { type: 'SAVE_SESSION_STATE'; payload: unknown }
  | { type: 'LOAD_SESSION_STATE' }
  | { type: 'CLEAR_SESSION_STATE' }

function isEmrCandidateUrl(url: string): boolean {
  try {
    const parsed = new URL(url)
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return false
    const path = parsed.pathname.toLowerCase()
    return (
      path.includes('/y-lenh') ||
      path.includes('/ho-so') ||
      path.includes('/emr') ||
      path.includes('/patient') ||
      parsed.hostname === 'localhost' ||
      parsed.hostname === '127.0.0.1'
    )
  } catch {
    return false
  }
}

async function listInspectableTabs(): Promise<BrowserTabSummary[]> {
  const tabs = await chrome.tabs.query({ currentWindow: true })
  const out: BrowserTabSummary[] = []
  for (const tab of tabs) {
    if (typeof tab.id !== 'number' || !tab.url) continue
    if (!tab.url.startsWith('http://') && !tab.url.startsWith('https://')) continue
    let origin = ''
    try {
      origin = new URL(tab.url).origin
    } catch {
      continue
    }
    out.push({
      id: tab.id,
      title: tab.title ?? origin,
      url: tab.url,
      origin,
      isEmrCandidate: isEmrCandidateUrl(tab.url),
      active: Boolean(tab.active),
    })
  }
  return out
}

async function extractSelectedTabs(tabIds: number[]): Promise<{
  extractions: RawTabExtraction[]
  errors: Array<{ tabId: number; reason: string }>
}> {
  const extractions: RawTabExtraction[] = []
  const errors: Array<{ tabId: number; reason: string }> = []

  await Promise.all(
    tabIds.map(async (tabId) => {
      try {
        const results = await chrome.scripting.executeScript({
          target: { tabId },
          func: injectedTabDomSnapshot,
          args: [tabId],
        })
        const first = results[0]?.result as RawTabExtraction | undefined
        if (first) {
          extractions.push(first)
        } else {
          errors.push({ tabId, reason: 'Không đọc được nội dung DOM của tab.' })
        }
      } catch (err) {
        errors.push({
          tabId,
          reason: err instanceof Error ? err.message : 'Chưa được cấp quyền đọc trang này.',
        })
      }
    }),
  )
  return { extractions, errors }
}

chrome.runtime.onMessage.addListener((message: WorkerRequest, _sender, sendResponse) => {
  if (!message || typeof message !== 'object') {
    return false
  }
  if (message.type === 'LIST_TABS') {
    void listInspectableTabs()
      .then((tabs) => sendResponse({ ok: true, tabs }))
      .catch((err) =>
        sendResponse({
          ok: false,
          error: err instanceof Error ? err.message : 'Lỗi đọc danh sách tab',
        }),
      )
    return true
  }
  if (message.type === 'EXTRACT_TABS') {
    void extractSelectedTabs(message.tabIds)
      .then((res) => sendResponse({ ok: true, ...res }))
      .catch((err) =>
        sendResponse({
          ok: false,
          error: err instanceof Error ? err.message : 'Lỗi trích xuất tab',
        }),
      )
    return true
  }
  if (message.type === 'SAVE_SESSION_STATE') {
    void chrome.storage.session
      .set({ [SESSION_STORAGE_KEY]: message.payload })
      .then(() => sendResponse({ ok: true }))
      .catch(() => sendResponse({ ok: false }))
    return true
  }
  if (message.type === 'LOAD_SESSION_STATE') {
    void chrome.storage.session
      .get(SESSION_STORAGE_KEY)
      .then((data) => sendResponse({ ok: true, payload: data[SESSION_STORAGE_KEY] ?? null }))
      .catch(() => sendResponse({ ok: false, payload: null }))
    return true
  }
  if (message.type === 'CLEAR_SESSION_STATE') {
    void chrome.storage.session
      .remove(SESSION_STORAGE_KEY)
      .then(() => sendResponse({ ok: true }))
      .catch(() => sendResponse({ ok: false }))
    return true
  }
  return false
})
