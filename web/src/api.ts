import type { Investigation, Match, MatchSummary, ProviderStatus, Recap, Timeline, Truth } from './types'

export class ApiError extends Error {
  code: string
  retryable: boolean
  status: number
  constructor(message: string, code = 'error', retryable = false, status = 0) {
    super(message)
    this.code = code
    this.retryable = retryable
    this.status = status
  }
}

/** A user's own key. Held only in React memory; sent per request as a header, never stored. */
export interface Byok {
  key: string
  model: string
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`/api${path}`, init)
  } catch {
    throw new ApiError('Could not reach the server.', 'network', true)
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const d = body.detail
    if (d && typeof d === 'object') throw new ApiError(d.message, d.code, d.retryable, res.status)
    throw new ApiError(typeof d === 'string' ? d : `${res.status} ${res.statusText}`, 'error', res.status >= 500, res.status)
  }
  return res.json() as Promise<T>
}

const byokHeaders = (byok: Byok | null): Record<string, string> =>
  byok ? { 'X-BYOK-Key': byok.key, 'X-BYOK-Model': byok.model } : {}

export const api = {
  matches: () => call<MatchSummary[]>('/matches'),
  match: (id: string) => call<Match>(`/matches/${id}`),
  investigate: (id: string, incident: string, opts: { mode: 'agents' | 'deterministic'; fresh?: boolean; byok?: Byok | null }) =>
    call<Investigation>(`/matches/${id}/incidents/${incident}/investigations?mode=${opts.mode}&fresh=${!!opts.fresh}`, {
      method: 'POST',
      headers: opts.mode === 'agents' ? byokHeaders(opts.byok ?? null) : {},
    }),
  truth: (id: string, incident: string) => call<Truth>(`/matches/${id}/incidents/${incident}/truth`),
  provider: () => call<ProviderStatus>('/provider'),
  timeline: (id: string, lang = 'en') => call<Timeline & { dir: 'ltr' | 'rtl' }>(`/matches/${id}/timeline?lang=${lang}`),
  recap: (id: string, phase: 'ht' | 'ft', voice: 'fan' | 'analyst', lang = 'en') =>
    call<Recap>(`/matches/${id}/recap?phase=${phase}&voice=${voice}&lang=${lang}`),
  liveUrl: (id: string, speed: number, start: number, lang = 'en') => `/api/matches/${id}/live?speed=${speed}&start=${start}&lang=${lang}`,
  testKey: (byok: Byok) =>
    call<{ ok: boolean; model: string; display_name: string }>('/provider/test', { method: 'POST', headers: byokHeaders(byok) }),
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  feedLiveUrl: (id: string, lang = 'en') => `/api/feeds/${id}/live?lang=${lang}`,
  demoFeed: (speed: number) => call<{ feed_id: string }>(`/feeds/demo?speed=${speed}`, { method: 'POST' }),
  createFeed: (sheet: unknown) => call<{ feed_id: string; write_token: string; events_url: string }>('/feeds', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(sheet) }),
  pushEvents: (url: string, token: string, events: unknown[], final: boolean) =>
    call<{ accepted: number; rejected_count: number }>(url.replace(/^\/api/, ''), {
      method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ events, final }) }),
  identity: () => call<{ mode: 'fictional' | 'real'; label: string; note: string }>('/identity'),
  benchmark: () => call<Record<string, any>>('/benchmark'),
}
