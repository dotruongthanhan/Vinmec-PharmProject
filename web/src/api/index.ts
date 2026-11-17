import { ApiClient } from './client.ts'
import type { ReviewApiClient } from './client.ts'
import { MockClient } from './mock.ts'
import { defaultAuthClient } from '@/features/auth/authClient'
import { notifyAuthEvent } from '@/features/auth/authEvents'
import { isActiveDemoMode } from '@/lib/demoSession'

export { ApiClient, ApiError } from './client.ts'
export type { AuthHooks, FetchLike, ReviewApiClient } from './client.ts'
export { MockClient } from './mock.ts'
export type { MockClientOptions } from './mock.ts'
export type * from './types.ts'

export function createApiClient(useMock: boolean): ReviewApiClient {
  return useMock ? new MockClient() : new ApiClient('/api', undefined, {
    getAccessToken: () => isActiveDemoMode() ? Promise.resolve(null) : defaultAuthClient.getAccessToken(),
    refreshSession: () => isActiveDemoMode() ? Promise.resolve(null) : defaultAuthClient.refreshSession(),
    onUnauthorized: () => notifyAuthEvent('unauthorized'),
    onForbidden: () => { void notifyAuthEvent('forbidden') },
  })
}

export const apiClient: ReviewApiClient = createApiClient(import.meta.env.VITE_USE_MOCK === '1')
