type AuthEvent = 'unauthorized' | 'forbidden'
type Listener = (event: AuthEvent) => void | Promise<void>
const listeners = new Set<Listener>()

/** Nối lỗi API với ngữ cảnh phiên mà không phụ thuộc bộ định tuyến. */
export async function notifyAuthEvent(event: AuthEvent): Promise<void> {
  await Promise.all(Array.from(listeners, (listener) => listener(event)))
}

export function subscribeAuthEvents(listener: Listener): () => void {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}
