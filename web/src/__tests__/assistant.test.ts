import { describe, expect, it } from 'vitest'
import { MOCK_CASE_DETAILS } from '../api/mockData.ts'
import {
  buildSuggestedQuestions,
  getAssistantInputState,
  shouldAcceptAssistantReply,
} from '../lib/assistant.ts'
import { parseCitationsInText } from '../lib/presentation.ts'

describe('tách dấu trích dẫn [n] trong câu trả lời', () => {
  it('tách "a [1] b [2]." thành đúng 5 phần', () => {
    const segments = parseCitationsInText('a [1] b [2].', [
      { so: 1, loai_ma: 'du_lieu', nhan: 'Creatinin', ban_ghi_id: 'XN-1' },
      { so: 2, loai_ma: 'tai_lieu', nhan: 'Nhãn FDA', ban_ghi_id: null },
    ])
    expect(segments).toHaveLength(5)
    expect(segments[0]).toEqual({ kind: 'text', value: 'a ' })
    expect(segments[1]).toMatchObject({ kind: 'citation', label: '[1]' })
    expect(segments[2]).toEqual({ kind: 'text', value: ' b ' })
    expect(segments[3]).toMatchObject({ kind: 'citation', label: '[2]' })
    expect(segments[4]).toEqual({ kind: 'text', value: '.' })
  })

  it('giữ nguyên dấu [n] không có trong trich_dan thành chữ và chuỗi không ngoặc thành 1 phần', () => {
    const unmatched = parseCitationsInText('Xem [1] và [9].', [
      { so: 1, loai_ma: 'du_lieu', nhan: 'Creatinin', ban_ghi_id: 'XN-1' },
    ])
    expect(unmatched).toHaveLength(3)
    expect(unmatched[2]).toEqual({ kind: 'text', value: ' và [9].' })

    const plain = parseCitationsInText('Không có dấu ngoặc.', [
      { so: 1, loai_ma: 'du_lieu', nhan: 'Creatinin', ban_ghi_id: 'XN-1' },
    ])
    expect(plain).toEqual([{ kind: 'text', value: 'Không có dấu ngoặc.' }])
  })
})

describe('hàm thuần điều khiển trạng thái Trợ lý AI', () => {
  it('bỏ qua câu trả lời về muộn của ca cũ hoặc yêu cầu đã huỷ', () => {
    expect(
      shouldAcceptAssistantReply({
        requestCaseId: 'DEMO-02',
        activeCaseId: 'DEMO-06',
        requestSeq: 1,
        latestSeqForCase: 1,
        aborted: false,
      }),
    ).toBe(false)

    expect(
      shouldAcceptAssistantReply({
        requestCaseId: 'DEMO-02',
        activeCaseId: null,
        requestSeq: 1,
        latestSeqForCase: 1,
        aborted: false,
      }),
    ).toBe(false)

    expect(
      shouldAcceptAssistantReply({
        requestCaseId: 'DEMO-02',
        activeCaseId: 'DEMO-02',
        requestSeq: 1,
        latestSeqForCase: 2,
        aborted: false,
      }),
    ).toBe(false)

    expect(
      shouldAcceptAssistantReply({
        requestCaseId: 'DEMO-02',
        activeCaseId: 'DEMO-02',
        requestSeq: 2,
        latestSeqForCase: 2,
        aborted: true,
      }),
    ).toBe(false)

    expect(
      shouldAcceptAssistantReply({
        requestCaseId: 'DEMO-02',
        activeCaseId: 'DEMO-02',
        requestSeq: 2,
        latestSeqForCase: 2,
        aborted: false,
      }),
    ).toBe(true)
  })

  it('khoá ô nhập khi chưa mở ca hoặc khi máy chủ trả chua_san_sang', () => {
    const noCase = getAssistantInputState({
      hasCase: false,
      hoiThemEnabled: true,
      lastStatus: null,
      sending: false,
      draft: 'test',
    })
    expect(noCase.inputLocked).toBe(true)
    expect(noCase.lockMessage).toBe('Mở một y lệnh để hỏi về ca đó.')
    expect(noCase.canSend).toBe(false)

    const notReady = getAssistantInputState({
      hasCase: true,
      hoiThemEnabled: true,
      lastStatus: 'chua_san_sang',
      sending: false,
      draft: 'test',
    })
    expect(notReady.inputLocked).toBe(true)
    expect(notReady.lockMessage).toBe('Máy chủ chưa bật trợ lý.')
    expect(notReady.canSend).toBe(false)

    const nearLimit = getAssistantInputState({
      hasCase: true,
      hoiThemEnabled: true,
      lastStatus: 'ok',
      sending: false,
      draft: 'a'.repeat(920),
    })
    expect(nearLimit.inputLocked).toBe(false)
    expect(nearLimit.showCharCounter).toBe(true)
    expect(nearLimit.remainingChars).toBe(80)
    expect(nearLimit.canSend).toBe(true)
  })

  it('sinh tối đa 3 câu hỏi gợi ý từ dữ liệu ca và nhận định cần xem', () => {
    const detail = MOCK_CASE_DETAILS['DEMO-02']
    const suggestions = buildSuggestedQuestions(detail, detail.nhan_dinh.can_chu_y)
    expect(suggestions).toHaveLength(3)
    expect(suggestions[0]).toContain('Meropenem 1 g')
  })
})
