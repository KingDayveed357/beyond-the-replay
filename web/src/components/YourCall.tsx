import { KIND_LABEL, clubName, playerName } from '../format'
import type { Claim, Match } from '../types'
import { play } from '../sound'

export type Call = Claim['kind'] | 'skip'

const OPTIONS: { kind: Claim['kind']; text: string }[] = [
  { kind: 'FOUL', text: 'The booking just before' },
  { kind: 'FATIGUE', text: 'A defender tiring' },
  { kind: 'OVERLOAD', text: 'Outnumbered on one flank' },
  { kind: 'STATIC', text: 'A defender outmatched all game' },
]

const CALLS = 'btr.calls.v1'
const RECORD = 'btr.record.v1'

/** Per-viewer conveniences: kept in this browser only and never required for the page to work. */
function read<T>(key: string, fallback: T): T {
  try { return { ...fallback, ...JSON.parse(localStorage.getItem(key) ?? '{}') } } catch { return fallback }
}
function write(key: string, value: unknown) {
  try { localStorage.setItem(key, JSON.stringify(value)) } catch { /* private mode: keep in memory only */ }
}

export const savedCall = (matchId: string): Call | null => read<Record<string, Call>>(CALLS, {})[matchId] ?? null
export const saveCall = (matchId: string, call: Call) => write(CALLS, { ...read<Record<string, Call>>(CALLS, {}), [matchId]: call })
export const clearCall = (matchId: string) => {
  const all = read<Record<string, Call>>(CALLS, {})
  delete all[matchId]
  write(CALLS, all)
}
export const callLabel = (kind: string) => KIND_LABEL[kind as Claim['kind']] ?? kind

/** Your record against the answer key, across matches: { matchId: you were right }. */
export function record(matchId?: string, right?: boolean) {
  const all = read<Record<string, boolean>>(RECORD, {})
  if (matchId !== undefined && right !== undefined) write(RECORD, { ...all, [matchId]: right })
  const now = matchId !== undefined && right !== undefined ? { ...all, [matchId]: right } : all
  const values = Object.values(now)
  return { right: values.filter(Boolean).length, played: values.length }
}

export default function YourCall({ match, onCall }: { match: Match; onCall: (c: Call) => void }) {
  const booking = match.events.find((e) => e.id === match.booking_id)
  return (
    <section className="panel panel-pad your-call">
      <p className="eyebrow"><span className="eyebrow-live" aria-hidden />Your call first</p>
      <h2 className="your-call-q">What decided {clubName(match, match.incident_team)}'s goal at {match.incident_minute}'?</h2>
      <p className="muted" style={{ margin: '0 0 14px' }}>
        {booking ? <>{playerName(match, booking.player_id)} was booked at {match.booking_minute}', a minute before. </> : null}
        Watch the move on the pitch, make your call, then see what the AI finds and what really happened.
      </p>
      <div className="call-options">
        {OPTIONS.map((o) => (
          <button key={o.kind} className="call-option" onClick={() => { play('tap'); onCall(o.kind) }}>{o.text}</button>
        ))}
      </div>
      <button className="call-skip" onClick={() => onCall('skip')}>Skip, just show me</button>
    </section>
  )
}
