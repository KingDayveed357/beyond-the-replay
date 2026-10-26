import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { LiveStats, MetricFocus, MomentFeed, MomentumChart, OverlayLayer, PersonaliseBar, PlayerCard, RecapCard, ScoreBug, StorylinesPanel } from '../components/LivePanels'
import Pitch from '../components/Pitch'
import { describeEvent, minute } from '../format'
import { usePrefs } from '../prefs'
import type { Cue, Match, MatchEvent, MinuteState, Moment, Recap, Timeline } from '../types'
import { tr } from '../ui'
import { momentSound, play } from '../sound'

const SPEEDS = [10, 30, 60, 120]
const ATTACK = new Set(['pass', 'carry', 'dribble', 'cross', 'shot'])
type Enriched = Timeline['events'][number]

export default function MatchCentre() {
  const { id = '' } = useParams()
  const { prefs, set } = usePrefs()
  const lang = prefs.lang
  const [match, setMatch] = useState<Match | null>(null)
  const [timeline, setTimeline] = useState<(Timeline & { dir: 'ltr' | 'rtl' }) | null>(null)
  const [events, setEvents] = useState<Enriched[]>([])
  const [series, setSeries] = useState<MinuteState[]>([])
  const [moments, setMoments] = useState<Moment[]>([])
  const [cues, setCues] = useState<Cue[]>([])
  const [clock, setClock] = useState(0)
  const [phase, setPhase] = useState('first_half')
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(30)
  const [follow, setFollow] = useState<string | null>(null)
  const [onlyFollow, setOnlyFollow] = useState(false)
  const [recap, setRecap] = useState<Recap | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reconnect, setReconnect] = useState(0)
  const source = useRef<EventSource | null>(null)
  const clockRef = useRef(0)
  clockRef.current = clock

  useEffect(() => { api.match(id).then(setMatch).catch((e) => setError(e.message)) }, [id])

  /** Rebuild everything up to `t` from the timeline (used for seeking and language changes). */
  const seek = useCallback((tl: Timeline, t: number, resume: boolean) => {
    source.current?.close()
    setEvents(tl.events.filter((e) => e.t < t))
    setSeries(tl.states.filter((s) => s.minute * 60 <= t))
    setMoments(tl.moments.filter((m) => m.t < t))
    setCues(tl.cues.filter((c) => c.t_out > t && c.t_in < t))
    setClock(t)
    setPhase(t >= 45 * 60 ? 'second_half' : 'first_half')
    setPlaying(resume)
  }, [])

  // Load (or reload in another language) and restore the current clock.
  useEffect(() => {
    let alive = true
    const wasPlaying = playing
    api.timeline(id, lang).then((tl) => { if (!alive) return; setTimeline(tl); seek(tl, clockRef.current, wasPlaying) }).catch((e) => setError(e.message))
    return () => { alive = false }
  }, [id, lang]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!playing || !match) return
    const es = new EventSource(api.liveUrl(match.id, speed, clockRef.current, lang))
    source.current = es
    const data = (ev: Event) => JSON.parse((ev as MessageEvent).data)
    es.addEventListener('event', (ev) => { const d = data(ev); setEvents((x) => [...x, d.event]); setClock(d.t) })
    es.addEventListener('state', (ev) => { const d = data(ev); setSeries((x) => [...x.filter((s) => s.minute < d.state.minute), d.state]) })
    es.addEventListener('moment', (ev) => {
      const d = data(ev)
      setMoments((x) => [...x, d.moment])
      const s = momentSound(d.moment.type)
      if (s) play(s)
    })
    es.addEventListener('beat', (ev) => { const d = data(ev); if (d.beat.index === 0) play('storyline') })
    es.addEventListener('milestone', () => play('milestone'))
    es.addEventListener('cue', (ev) => { const d = data(ev); setCues((x) => [...x.filter((c) => c.t_out > d.t), d.cue]) })
    es.addEventListener('phase', (ev) => {
      const d = data(ev)
      setPhase(d.phase.phase)
      if (d.phase.phase === 'half_time') play('half_time')
      if (d.phase.phase === 'full_time') { play('full_time'); setPlaying(false); es.close() }
    })
    // Hosting proxies end long responses; reopen the feed from the current minute instead of stopping.
    let retry: ReturnType<typeof setTimeout> | undefined
    es.onerror = () => { es.close(); retry = setTimeout(() => setReconnect((n) => n + 1), 1500) }
    return () => { es.close(); if (retry) clearTimeout(retry) }
  }, [playing, speed, match, lang, reconnect])

  const recapPhase: 'ht' | 'ft' | null = phase === 'full_time' ? 'ft' : clock >= 45 * 60 && clock < 50 * 60 ? 'ht' : null
  useEffect(() => {
    if (!match || !recapPhase) return
    setRecap(null)
    api.recap(match.id, recapPhase, prefs.analyst ? 'analyst' : 'fan', lang).then(setRecap).catch(() => setRecap(null))
  }, [match, recapPhase, prefs.analyst, lang])

  const state = series.length ? series[series.length - 1] : null
  const activeCues = cues.filter((c) => c.t_in <= clock && c.t_out > clock)
  const last = useMemo(() => [...events].reverse().find((e) => ATTACK.has(e.type)) ?? null, [events])
  const path = useMemo(() => {
    if (!last) return []
    return events.filter((e) => e.possession_id === last.possession_id && e.team === last.team && ATTACK.has(e.type)).slice(-10)
  }, [events, last])
  const followed: MatchEvent[] = useMemo(
    () => (follow ? events.filter((e) => e.player_id === follow && clock - e.t <= 300) : []), [events, follow, clock])

  if (error) return <div className="page"><p className="error" style={{ marginTop: 32 }}>{error}</p></div>
  if (!match || !timeline) return <div className="page"><p className="faint" style={{ marginTop: 32 }}>…</p></div>
  const md = match.metadata
  const dir = timeline.dir

  return (
    <div className="page live">
      <div className="live-top">
        <ScoreBug match={match} state={state} clock={clock} phase={phase} club={prefs.club} />
        <div className="live-meta muted">
          {md?.competition} {md?.season} · MW {md?.matchweek} · {md?.venue} · {md?.referee}
          <span className="tag synthetic" style={{ marginInlineStart: 10 }}>{tr(lang, 'simulated')}</span>
        </div>
      </div>

      <PersonaliseBar match={match} lang={lang} club={prefs.club} follow={follow} metric={prefs.metric}
        onLang={(l) => set({ lang: l })} onClub={(c) => set({ club: c })} onFollow={setFollow} onMetric={(m) => set({ metric: m })} />

      <div className="live-controls">
        <button className="btn" onClick={() => {
          if (!playing && (clock === 0 || phase === 'full_time')) play('kickoff')
          if (playing) setPlaying(false)
          else if (phase === 'full_time') seek(timeline, 0, true)
          else setPlaying(true)
        }}>
          {playing ? tr(lang, 'pause') : phase === 'full_time' ? tr(lang, 'again') : clock > 0 ? tr(lang, 'resume') : tr(lang, 'kickoff')}
        </button>
        <div className="toggle" role="group" aria-label="Replay speed">
          {SPEEDS.map((s) => <button key={s} aria-pressed={speed === s} onClick={() => setSpeed(s)}>{s}×</button>)}
        </div>
        <label className="scrub">
          <span className="sr-only">Jump to minute</span>
          <input type="range" min={0} max={94} value={Math.floor(clock / 60)} onChange={(e) => seek(timeline, Number(e.target.value) * 60, false)} />
        </label>
        <div className="toggle" role="group" aria-label="View">
          <button aria-pressed={!prefs.analyst} onClick={() => set({ analyst: false })}>{tr(lang, 'fan')}</button>
          <button aria-pressed={prefs.analyst} onClick={() => set({ analyst: true })}>{tr(lang, 'analyst')}</button>
        </div>
      </div>

      <div className="live-grid">
        <div className="stage-col">
          <div className="pitch-wrap">
            <Pitch match={match} path={path} evidence={followed} scoringTeam={last?.team ?? match.home} animate={false} />
            <OverlayLayer match={match} cues={activeCues} dir={dir} follow={follow} />
            <div className="pitch-caption">
              <span>{last ? <><strong>{minute(last.t)}</strong> {describeEvent(match, last)}</> : '—'}</span>
              <span className="faint mono" style={{ fontSize: 12 }}>{events.length} events</span>
            </div>
          </div>
          <MomentumChart match={match} series={series} lang={lang} />
        </div>
        <div className="inv">
          {recapPhase && <RecapCard recap={recap} phase={recapPhase} analyst={prefs.analyst} onAnalyst={(v) => set({ analyst: v })} lang={lang} dir={dir} />}
          {prefs.metric && <MetricFocus match={match} series={series} metric={prefs.metric} lang={lang} />}
          {follow && <PlayerCard match={match} pid={follow} events={events} moments={moments} lang={lang} />}
          <StorylinesPanel match={match} narrative={timeline.narrative} clock={clock} lang={lang} dir={dir} club={prefs.club} follow={follow} />
          <LiveStats match={match} state={state} analyst={prefs.analyst} lang={lang} club={prefs.club} />
          <MomentFeed match={match} moments={moments} investigateId={match.incident_id} lang={lang} dir={dir} club={prefs.club}
            follow={follow} onlyFollow={onlyFollow} onOnlyFollow={setOnlyFollow} />
          <p className="faint" style={{ fontSize: 13 }}>
            <Link to={`/pack/${match.id}`}>Studio pack</Link> · <Link to={`/match/${match.id}`}>{tr(lang, 'why_goal')}</Link> · <a href={`/api/matches/${match.id}/overlays?lang=${lang}`} target="_blank" rel="noreferrer">Overlay feed (JSON)</a>
            {' · '}<a href={`/api/matches/${match.id}/overlays?lang=${lang}&format=vtt`} target="_blank" rel="noreferrer">WebVTT</a>
          </p>
        </div>
      </div>
    </div>
  )
}
