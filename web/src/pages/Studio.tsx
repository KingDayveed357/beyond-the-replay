import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { MomentFeed, OverlayLayer, ScoreBug, StorylinesPanel } from '../components/LivePanels'
import Pitch from '../components/Pitch'
import { describeEvent, minute } from '../format'
import { usePrefs } from '../prefs'
import type { Cue, Match, MinuteState, Moment, Narrative, Storyline, Timeline } from '../types'
import { momentSound, play } from '../sound'

type Enriched = Timeline['events'][number]
interface Sheet { home: string; away: string; home_name: string; away_name: string; roster: Match['roster']; metadata: Match['metadata'] }
interface Ack { accepted: number; rejected: number; stage_ms: Record<string, number>; summary: { events: number; minute: number; stats: { rejected: number; batches: number } } }

const STAGES: { id: string; label: string; note: string }[] = [
  { id: 'ingest', label: 'Ingest', note: 'schema, roster, pitch and clock checks' },
  { id: 'interpret', label: 'Interpret', note: 'states, xG, pass difficulty, players' },
  { id: 'explain', label: 'Explain', note: 'key moments and why they matter' },
  { id: 'render', label: 'Render', note: 'overlay cues for graphics engines' },
  { id: 'narrate', label: 'Narrate', note: 'storylines, milestones, story so far' },
  { id: 'publish', label: 'Publish', note: 'only what is new, per viewer language' },
]
const ATTACK = new Set(['pass', 'carry', 'dribble', 'cross', 'shot'])

const SNIPPETS = {
  powershell: `$H = "$ORIGIN"
$json = "application/json; charset=utf-8"
$sample = Invoke-RestMethod "$H/api/feeds/sample"
$sheet = [Text.Encoding]::UTF8.GetBytes(($sample.sheet | ConvertTo-Json -Depth 10))
$feed = Invoke-RestMethod -Method Post "$H/api/feeds" -ContentType $json -Body $sheet
$auth = @{ Authorization = "Bearer $($feed.write_token)" }
$batch = [Text.Encoding]::UTF8.GetBytes((@{ events = @($sample.events[0..99]); final = $false } | ConvertTo-Json -Depth 10))
Invoke-RestMethod -Method Post "$H$($feed.events_url)" -Headers $auth -ContentType $json -Body $batch
Start-Process "$H/studio/$($feed.feed_id)"`,
  curl: `H=$ORIGIN
curl -s $H/api/feeds/sample > match.json        # or your own { "sheet": …, "events": [ … ] }
FEED=$(python -c "import json; print(json.dumps(json.load(open('match.json'))['sheet']))" | curl -s -X POST $H/api/feeds -H "Content-Type: application/json" -d @-)
ID=$(echo "$FEED" | python -c "import json,sys; print(json.load(sys.stdin)['feed_id'])")
TOKEN=$(echo "$FEED" | python -c "import json,sys; print(json.load(sys.stdin)['write_token'])")
python -c "import json; print(json.dumps({'events': json.load(open('match.json'))['events'][:100]}))" \\
  | curl -s -X POST $H/api/feeds/$ID/events -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d @-
echo "Watch: $H/studio/$ID"`,
  python: `# streams a brand-new match, one batch per second, like a live data provider
python scripts/feed_simulator.py $ORIGIN --speed 30`,
}

/** Live Studio: a data provider pushes synthetic events in; the Agent Framework pipeline turns each batch into
 * match intelligence, and every output appears here as it is published. */
export default function Studio() {
  const { id } = useParams()
  const nav = useNavigate()
  const { prefs } = usePrefs()
  const lang = prefs.lang
  const dir = lang === 'ar' ? 'rtl' : 'ltr'
  const [sheet, setSheet] = useState<Sheet | null>(null)
  const [events, setEvents] = useState<Enriched[]>([])
  const [states, setStates] = useState<MinuteState[]>([])
  const [moments, setMoments] = useState<Moment[]>([])
  const [cues, setCues] = useState<Cue[]>([])
  const [narrative, setNarrative] = useState<Narrative>({ storylines: [], milestones: [], summaries: [] })
  const [acks, setAcks] = useState<Ack[]>([])
  const [finished, setFinished] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [speed, setSpeed] = useState(30)
  const [reconnect, setReconnect] = useState(0)
  const [shell, setShell] = useState<keyof typeof SNIPPETS>('powershell')
  const log = useRef<HTMLOListElement>(null)

  useEffect(() => {
    if (!id) return
    setFinished(false)
    const es = new EventSource(api.feedLiveUrl(id, lang))
    const data = (ev: Event) => JSON.parse((ev as MessageEvent).data)
    es.addEventListener('snapshot', (ev) => {
      const d = data(ev)
      setSheet(d.sheet)
      setEvents(d.timeline.events)
      setStates(d.timeline.states)
      setMoments(d.timeline.moments)
      setCues(d.timeline.cues)
      setNarrative(d.narrative ?? { storylines: [], milestones: [], summaries: [] })
      setFinished(d.summary.finished)
    })
    es.addEventListener('event', (ev) => { const e = data(ev); setEvents((x) => [...x, e]) })
    es.addEventListener('state', (ev) => { const s = data(ev); setStates((x) => [...x.filter((y) => y.minute < s.minute), s]) })
    es.addEventListener('moment', (ev) => { const m = data(ev); setMoments((x) => [...x, m]); const s = momentSound(m.type); if (s) play(s) })
    es.addEventListener('cue', (ev) => { const c = data(ev); setCues((x) => [...x.slice(-30), c]) })
    es.addEventListener('storyline', (ev) => {
      const s: Storyline = data(ev)
      if (s.beats.length === 1) play('storyline')
      setNarrative((n) => ({ ...n, storylines: [...n.storylines.filter((x) => x.id !== s.id), s] }))
    })
    es.addEventListener('milestone', (ev) => { const m = data(ev); play('milestone'); setNarrative((n) => ({ ...n, milestones: [...n.milestones, m] })) })
    es.addEventListener('summary', (ev) => { const m = data(ev); setNarrative((n) => ({ ...n, summaries: [...n.summaries, m] })) })
    es.addEventListener('ingest', (ev) => { const a = data(ev); setAcks((x) => [...x.slice(-59), a]) })
    es.addEventListener('phase', () => { play('full_time'); setFinished(true); es.close() })
    let retry: ReturnType<typeof setTimeout> | undefined
    es.onerror = () => { es.close(); retry = setTimeout(() => setReconnect((n) => n + 1), 1500) }
    return () => { es.close(); if (retry) clearTimeout(retry) }
  }, [id, lang, reconnect])

  useEffect(() => { log.current?.scrollTo({ top: 0 }) }, [events.length])

  const kickOff = async () => {
    setBusy('Starting a new synthetic match…'); setError(null)
    try {
      play('kickoff')
      const r = await api.demoFeed(speed)
      reset()
      nav(`/studio/${r.feed_id}`)
    } catch (e) { setError((e as Error).message) } finally { setBusy(null) }
  }

  const upload = async (file: File) => {
    setBusy('Uploading through the public ingestion API…'); setError(null)
    try {
      const body = JSON.parse(await file.text())
      const created = await api.createFeed(body.sheet ?? body)
      reset()
      nav(`/studio/${created.feed_id}`)
      const evs: unknown[] = body.events ?? []
      for (let i = 0; i < evs.length; i += 120) {
        await api.pushEvents(created.events_url, created.write_token, evs.slice(i, i + 120), i + 120 >= evs.length)
        await new Promise((r) => setTimeout(r, 350))
      }
    } catch (e) { setError((e as Error).message) } finally { setBusy(null) }
  }

  const reset = () => {
    setSheet(null); setEvents([]); setStates([]); setMoments([]); setCues([]); setAcks([]); setFinished(false)
    setNarrative({ storylines: [], milestones: [], summaries: [] })
  }

  const match: Match | null = useMemo(() => sheet && ({
    id: id ?? '', role: 'showcase', ...sheet, score: {}, incident_id: '', incident_minute: 0, incident_team: sheet.home,
    booking_id: null, booking_minute: null, goals: [], synthetic: true, events: [],
  } as unknown as Match), [sheet, id])

  const clock = events.length ? events[events.length - 1].t : 0
  const state = states.length ? states[states.length - 1] : null
  const last = [...events].reverse().find((e) => ATTACK.has(e.type)) ?? null
  const path = last ? events.filter((e) => e.possession_id === last.possession_id && e.team === last.team && ATTACK.has(e.type)).slice(-10) : []
  const liveCues = cues.filter((c) => c.t_in <= clock && c.t_out > clock)
  const lastAck = acks[acks.length - 1]
  const totalRejected = lastAck?.summary.stats.rejected ?? 0
  const rate = acks.length > 1 ? Math.round(acks.slice(-10).reduce((s, a) => s + a.accepted, 0) / Math.min(acks.length, 10)) : 0

  return (
    <div className="page studio">
      <header className="studio-head">
        <div>
          <p className="eyebrow"><span className="eyebrow-live" aria-hidden />Live Studio · for producers and developers</p>
          <h1>Events in. Intelligence out.</h1>
          <p className="muted">Behind the scenes of the fan experience. A data provider pushes synthetic events as they happen; every batch
            runs through a Microsoft Agent Framework pipeline, and only what is new is published to each viewer, in their language.
            Fans: <Link to="/">start here instead</Link>.</p>
        </div>
        <div className="studio-actions">
          <div className="toggle" role="group" aria-label="Provider speed">
            {[10, 30, 60].map((s) => <button key={s} aria-pressed={speed === s} onClick={() => setSpeed(s)}>{s}×</button>)}
          </div>
          <button className="btn" onClick={kickOff} disabled={!!busy}>Kick off a new synthetic match</button>
          <label className="btn ghost file-btn">
            Upload a match feed (JSON)
            <input type="file" accept="application/json,.json" onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
          </label>
        </div>
        {busy && <p className="faint">{busy}</p>}
        {error && <p className="error">{error}</p>}
      </header>

      <section className="pipeline" aria-label="Match pipeline">
        {STAGES.map((s, i) => (
          <div key={s.id} className={`stage-node${lastAck ? ' on' : ''}`}>
            <span className="mono stage-i">{String(i + 1).padStart(2, '0')}</span>
            <strong>{s.label}</strong>
            <span className="stage-note">{s.note}</span>
            <span className="mono stage-ms">{lastAck?.stage_ms[s.id] !== undefined ? `${lastAck.stage_ms[s.id]} ms` : '—'}</span>
          </div>
        ))}
        <div className="pipeline-foot mono">
          <span>{events.length} events accepted</span><span>{totalRejected} rejected</span>
          <span>{rate} events / batch</span><span>{acks.length ? `${acks[acks.length - 1].summary.stats.batches} batches` : 'no batches yet'}</span>
          <span>Microsoft Agent Framework · fan-out to render and narrate</span>
        </div>
      </section>

      {!id ? (
        <section className="studio-empty">
          <div className="panel panel-pad">
            <h2>Bring your own provider</h2>
            <p className="muted">Three calls: open a feed with a match sheet, push events in clock order with its write token, watch it here.
              Bad events come back with a reason; good ones flow through the pipeline. Nothing here calls an AI model, so test freely.</p>
            <div className="toggle" role="group" aria-label="Example language" style={{ marginBottom: 8 }}>
              {(['powershell', 'curl', 'python'] as const).map((k) => <button key={k} aria-pressed={shell === k} onClick={() => setShell(k)}>{k === 'powershell' ? 'PowerShell' : k === 'curl' ? 'curl' : 'Python'}</button>)}
            </div>
            <pre className="code">{SNIPPETS[shell].replaceAll('$ORIGIN', window.location.origin)}</pre>
            <p className="faint" style={{ fontSize: 13 }}>
              <a href="/docs" target="_blank" rel="noreferrer">Interactive API reference</a> · <a href="/api/schema" target="_blank" rel="noreferrer">JSON Schema</a> ·
              {' '}<a href="/api/feeds/sample" target="_blank" rel="noreferrer">Sample match file</a> 
            </p>
          </div>
        </section>
      ) : !match ? <p className="faint">Connecting to the feed…</p> : (
        <div className="studio-grid">
          <div className="stage-col">
            <ScoreBug match={match} state={state} clock={clock} phase={finished ? 'full_time' : clock >= 45 * 60 ? 'second_half' : 'first_half'} club={prefs.club} />
            <div className="pitch-wrap">
              <Pitch match={match} path={path} scoringTeam={last?.team ?? match.home} animate={false} />
              <OverlayLayer match={match} cues={liveCues} dir={dir} follow={null} />
              <div className="pitch-caption">
                <span>{last ? <><strong>{minute(last.t)}</strong> {describeEvent(match, last)}</> : 'Waiting for the first event…'}</span>
                <span className="faint mono" style={{ fontSize: 12 }}>{finished ? 'Full-time' : 'Live'}</span>
              </div>
            </div>
            <section className="panel panel-pad">
              <h2>Incoming events</h2>
              <ol className="event-log mono" ref={log}>
                {[...events].slice(-14).reverse().map((e) => (
                  <li key={e.id}><span>{minute(e.t)}</span><span>{e.type}</span><span>{describeEvent(match, e)}</span></li>
                ))}
              </ol>
            </section>
          </div>
          <div className="inv">
            <StorylinesPanel match={match} narrative={narrative} clock={clock + 1} lang={lang} dir={dir} club={prefs.club} follow={null} />
            <MomentFeed match={match} moments={moments} lang={lang} dir={dir} club={prefs.club} follow={null} onlyFollow={false} onOnlyFollow={() => {}} />
            <p className="faint" style={{ fontSize: 13 }}>
              Feed <code>{id}</code> · <a href={`/api/feeds/${id}?lang=${lang}`} target="_blank" rel="noreferrer">Snapshot (JSON)</a> · <Link to="/studio">New feed</Link>
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
