/** Ngăn hỏi đáp Agentic Q&A theo phiên RAM tạm thời (deepseek-flash + trích dẫn nguồn mở). */

import { ArrowLeft, Send } from 'lucide-react'
import { useState } from 'react'
import type { ExtensionApiClient } from '../api/extensionClient'
import type { BuocAI, TraLoi } from '../lib/types'

interface Props {
  client: ExtensionApiClient
  sessionId: string
  suggestedQuestions: string[]
  initialFindingId?: string
  onBack: () => void
}

interface ChatTurn {
  role: 'user' | 'assistant'
  text: string
  reply?: TraLoi
}

export function ChatDrawer({
  client,
  sessionId,
  suggestedQuestions,
  initialFindingId,
  onBack,
}: Props) {
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [input, setInput] = useState('')
  const [steps, setSteps] = useState<BuocAI[]>([])
  const [busy, setBusy] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const sendQuestion = async (questionText: string) => {
    const cleaned = questionText.trim()
    if (!cleaned || busy) return
    setErrorMsg(null)
    setBusy(true)
    setTurns((prev) => [...prev, { role: 'user', text: cleaned }])
    setInput('')

    let active = true
    const pollProgress = async () => {
      while (active) {
        try {
          const p = await client.getAskProgress(sessionId)
          if (!active) break
          setSteps(p.cac_buoc)
        } catch {
          // Bỏ qua lỗi poll thoáng qua.
        }
        await new Promise((r) => setTimeout(r, 800))
      }
    }
    void pollProgress()

    try {
      const reply = await client.ask(sessionId, cleaned, initialFindingId)
      setTurns((prev) => [...prev, { role: 'assistant', text: reply.noi_dung, reply }])
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Không thể gửi câu hỏi.')
    } finally {
      active = false
      setBusy(false)
    }
  }

  return (
    <div className="flex h-full flex-col space-y-3">
      <div className="flex items-center justify-between border-b border-slate-200 pb-2">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-1 text-xs font-medium text-teal-700 hover:underline"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Quay lại bảng nhận định
        </button>
        <span className="text-[10px] text-slate-500">Agentic Q&A (Zero-Retention)</span>
      </div>

      {turns.length === 0 && suggestedQuestions.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[11px] font-medium text-slate-600">Câu hỏi gợi ý:</p>
          <div className="flex flex-wrap gap-1.5">
            {suggestedQuestions.slice(0, 4).map((q, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => void sendQuestion(q)}
                className="rounded-md border border-teal-200 bg-teal-50 px-2 py-1 text-left text-[11px] text-teal-900 hover:bg-teal-100"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="flex-1 space-y-2 overflow-y-auto pr-1">
        {turns.map((turn, idx) => (
          <div
            key={idx}
            className={`rounded-lg p-2.5 text-xs ${
              turn.role === 'user'
                ? 'ml-6 bg-teal-600 text-white'
                : 'mr-4 border border-slate-200 bg-white text-slate-800'
            }`}
          >
            <p className="whitespace-pre-wrap">{turn.text}</p>
            {turn.reply && turn.reply.cong_cu_da_goi.length > 0 && (
              <div className="mt-1.5 flex flex-wrap gap-1">
                {turn.reply.cong_cu_da_goi.map((tool) => (
                  <span
                    key={tool}
                    className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600"
                  >
                    Công cụ: {tool}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}

        {busy && (
          <div className="rounded border border-amber-200 bg-amber-50 p-2 text-[11px] text-amber-800">
            Đang tổng hợp bằng chứng...{' '}
            {steps.length > 0 ? steps.map((s) => s.ten).join(' -> ') : ''}
          </div>
        )}
      </div>

      {errorMsg && (
        <div className="rounded border border-rose-200 bg-rose-50 p-2 text-xs text-rose-700">
          {errorMsg}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault()
          void sendQuestion(input)
        }}
        className="flex items-center gap-1.5 border-t border-slate-200 pt-2"
      >
        <input
          type="text"
          maxLength={1000}
          placeholder="Đặt câu hỏi lâm sàng về ca này..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className="flex-1 rounded-md border border-slate-300 px-2.5 py-1.5 text-xs focus:border-teal-500 focus:outline-none"
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="inline-flex items-center justify-center rounded-md bg-teal-600 p-2 text-white hover:bg-teal-700 disabled:opacity-50"
        >
          <Send className="h-3.5 w-3.5" />
        </button>
      </form>
    </div>
  )
}
