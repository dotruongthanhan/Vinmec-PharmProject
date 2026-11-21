import { ApiClient } from './client.ts'
import type { ReviewApiClient } from './client.ts'
import { defaultAuthClient } from '@/features/auth/authClient'
import { notifyAuthEvent } from '@/features/auth/authEvents'
import { isActiveDemoMode } from '@/lib/demoSession'

export { ApiClient, ApiError } from './client.ts'
export type { AuthHooks, FetchLike, ReviewApiClient } from './client.ts'
export type { MockClientOptions } from './mock.ts'
export type * from './types.ts'

function createHttpApiClient(): ReviewApiClient {
  return new ApiClient('/api', undefined, {
    getAccessToken: () => isActiveDemoMode() ? Promise.resolve(null) : defaultAuthClient.getAccessToken(),
    refreshSession: () => isActiveDemoMode() ? Promise.resolve(null) : defaultAuthClient.refreshSession(),
    onUnauthorized: () => notifyAuthEvent('unauthorized'),
    onForbidden: () => { void notifyAuthEvent('forbidden') },
  })
}

/**
 * Tạo máy khách API; chỉ nạp động `./mock.ts` khi `useMock` là `true` để không đóng gói dữ liệu giả vào production.
 */
export async function createApiClient(useMock: boolean): Promise<ReviewApiClient> {
  if (!useMock) {
    return createHttpApiClient()
  }
  const { MockClient } = await import('./mock.ts')
  return new MockClient()
}

function createLazyMockClient(): ReviewApiClient {
  let pending: Promise<ReviewApiClient> | null = null
  let loaded: ReviewApiClient | null = null
  const load = (): Promise<ReviewApiClient> => {
    if (!pending) {
      pending = (async () => {
        try {
          const client = await createApiClient(true)
          loaded = client
          return client
        } catch (error) {
          pending = null
          throw error
        }
      })()
    }
    return pending
  }
  return {
    abortAll: () => {
      loaded?.abortAll?.()
    },
    signOut: async (token) => {
      const client = await load()
      await client.signOut?.(token)
    },
    getMe: async () => (await load()).getMe(),
    getHealth: async () => (await load()).getHealth(),
    getCases: async (options) => (await load()).getCases(options),
    getCase: async (caId, options) => (await load()).getCase(caId, options),
    getRecord: async (caId, banGhiId) => (await load()).getRecord(caId, banGhiId),
    sendFeedback: async (caId, payload) => (await load()).sendFeedback(caId, payload),
    ask: async (caId, payload, options) => (await load()).ask(caId, payload, options),
    getAskProgress: async (caId, init) => (await load()).getAskProgress(caId, init),
    startAi: async (caId, chayLai) => (await load()).startAi(caId, chayLai),
    getAi: async (caId) => (await load()).getAi(caId),
    getSource: async (caId, doanTrichId) => (await load()).getSource(caId, doanTrichId),
    searchDrugs: async (params, options) => (await load()).searchDrugs(params, options),
    getDrug: async (hoatChatId, options) => (await load()).getDrug(hoatChatId, options),
    checkInteractions: async (payload, options) => (await load()).checkInteractions(payload, options),
    getFormulas: async (options) => (await load()).getFormulas(options),
    calculateFormula: async (ma, payload, options) => (await load()).calculateFormula(ma, payload, options),
  }
}

export const apiClient: ReviewApiClient = import.meta.env.VITE_USE_MOCK === '1'
  ? createLazyMockClient()
  : createHttpApiClient()
