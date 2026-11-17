import { ApiClient } from './client.ts'
import type { ReviewApiClient } from './client.ts'
import { MockClient } from './mock.ts'

export { ApiClient, ApiError } from './client.ts'
export type { FetchLike, ReviewApiClient } from './client.ts'
export { MockClient } from './mock.ts'
export type { MockClientOptions } from './mock.ts'
export type * from './types.ts'

export function createApiClient(useMock: boolean): ReviewApiClient {
  return useMock ? new MockClient() : new ApiClient('/api')
}

export const apiClient: ReviewApiClient = createApiClient(import.meta.env.VITE_USE_MOCK === '1')
