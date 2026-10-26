import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import Pitch from '../components/Pitch'
import { ordinal, playerName } from '../format'
import { usePrefs } from '../prefs'
import type { Match, MatchSummary } from '../types'

const ROLE_NOTE: Record<MatchSummary['role'], string> = {
  hero: 'The booking, or the legs?',
  showcase: 'The big one. The AI gets this goal wrong, and says so',
  overload: 'Outnumbered on one flank',
  fatigue: 'Another late collapse',
  miss: 'A case we get wrong',
  ambiguous: 'No single cause stands out',
}

const delay = (ms: number) => ({ animationDelay: `${ms}ms` })

/** Ten minutes around the booking and the goal, drawn as a strip so the question is visible at a glance. */
function QuestionStrip({ match, colour }: { match: Match; colour: string }) {
  const booking = match.events.find((e) => e.id === match.booking_id)
  const goal = match.events.find((e) => e.id === match.incident_id)
  if (!booking || !goal) return null
  const from = Math.max(0, Math.floor(booking.t / 60) - 5) * 60
  const to = from + 10 * 60
  const pct = (t: number) => Math.min(96, Math.max(4, ((t - from) / (to - from)) * 100))
  const gap = Math.max(1, Math.round(goal.t - booking.t))
  const gapLabel = gap < 90 ? `${gap} seconds apart` : `${Math.round(gap / 60)} minutes apart`
  const ticks = Array.from({ length: 11 }, (_, i) => from / 60 + i)
  return (
    <div className="qstrip" role="img"
      aria-label={`Booking at ${match.booking_minute}', goal at ${match.incident_minute}', ${gapLabel}`}>
      <div className="qstrip-track">
        {ticks.map((m, i) => (
          <span key={m} className={`qstrip-tick${i % 5 === 0 ? ' major' : ''}`} style={{ left: `${i * 10}%` }}>
            {i % 5 === 0 && <small>{m}'</small>}
          </span>
        ))}
        <span className="qstrip-span" style={{ left: `${pct(booking.t)}%`, width: `${pct(goal.t) - pct(booking.t)}%` }} />
        <span className="qstrip-mark card" style={{ left: `${pct(booking.t)}%` }}>
          <i aria-hidden />
          <span className="qstrip-label"><b>{match.booking_minute}'</b> <span className="who">{playerName(match, booking.player_id)}</span> booked</span>
        </span>
        <span className="qstrip-mark goal" style={{ left: `${pct(goal.t)}%`, ['--team' as string]: colour }}>
          <i aria-hidden />
          <span className="qstrip-label"><b>{match.incident_minute}'</b> <span className="who">{playerName(match, goal.player_id)}</span> scores</span>
        </span>
      </div>
      <div className="qstrip-foot">
        <span>{gapLabel}</span>
        <span className="qstrip-q">Coincidence, or cause?</span>
      </div>
    </div>
  )
}

export default function Landing() {
  const { prefs, set } = usePrefs()
  const hide = prefs.spoilerFree
  const [matches, setMatches] = useState<MatchSummary[]>([])
  const [hero, setHero] = useState<Match | null>(null)
  const [accuracy, setAccuracy] = useState<{ agents: number; alone: number } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [note, setNote] = useState('Simulated matches: clubs, players and stadiums are fictional; every event is invented.')
  const showcase = matches.find((m) => m.role === 'showcase') ?? null

  useEffect(() => {
    api.matches().then((ms) => {
      setMatches(ms)
      const h = ms.find((m) => m.role === 'hero') ?? ms[0]
      if (h) return api.match(h.id).then(setHero)
    }).catch((e) => setError(e.message))
    api.identity().then((i) => setNote(i.note)).catch(() => {})
    api.benchmark().then((b) => {
      const v = b.agents_heldout_v21?.variants
      if (v?.agents && v?.llm_only) setAccuracy({ agents: v.agents['recall@1'], alone: v.llm_only['recall@1'] })
    }).catch(() => setAccuracy(null))
  }, [])

  const path = useMemo(() => {
    if (!hero) return []
    const goal = hero.events.find((e) => e.id === hero.incident_id)!
    return hero.events.filter((e) => e.possession_id === goal.possession_id && e.team === goal.team && e.t <= goal.t)
  }, [hero])

  const scoringName = hero ? (hero.incident_team === hero.home ? hero.home_name : hero.away_name) : ''
  const colour = hero?.metadata?.colours?.[hero.incident_team]?.[0] ?? 'var(--chalk)'
  const close = !!hero && hero.booking_minute !== null && hero.incident_minute - hero.booking_minute <= 10
  const scorer = hero ? playerName(hero, hero.events.find((e) => e.id === hero.incident_id)?.player_id ?? null) : ''

  return (
    <>
      <section className="hero">
        <div className="hero-glow" aria-hidden />
        <div className="hero-grid">
          <div className="hero-copy">
            {hero ? (
              <>
                <p className="eyebrow rise" style={delay(0)}>
                  <span className="eyebrow-live" aria-hidden />
                  <span>{hero.home_name} {hide ? 'v' : `${hero.score[hero.home]}–${hero.score[hero.away]}`} {hero.away_name}</span>
                  {hero.metadata?.venue && <span className="eyebrow-venue">{hero.metadata.venue}</span>}
                </p>
                <h1 className="hero-title">
                  {close ? (
                    <>
                      <span className="line rise" style={delay(80)}>A booking at {hero.booking_minute}'.</span>
                      <span className="line rise" style={delay(170)}>A goal at {hero.incident_minute}'.</span>
                    </>
                  ) : (
                    <span className="line rise" style={delay(80)}>{scoringName} score at {hero.incident_minute}'.</span>
                  )}
                  <em className="line rise" style={delay(280)}>Was the booking really the cause?</em>
                </h1>
                <p className="hero-lede rise" style={delay(380)}>
                  Follow the match live, then ask why a goal went in. AI agents argue the cause, code checks every
                  claim against the match data, and you see what really decided it.
                </p>
                <div className="hero-actions rise" style={delay(460)}>
                  <Link className="btn btn-lg" to={`/match/${hero.id}`}>
                    <span>Find out what decided the <span className="nowrap">{ordinal(hero.incident_minute)}-minute goal</span></span> <span className="btn-arrow" aria-hidden>→</span>
                  </Link>
                  {showcase && (
                    <Link className="btn btn-lg ghost" to={`/live/${showcase.id}`}>
                      <span className="live-pip" aria-hidden />Watch {showcase.home_name} v {showcase.away_name} live
                    </Link>
                  )}
                </div>
                <ul className="proof rise" style={delay(540)}>
                  <li>
                    <strong>{accuracy ? `${Math.round(accuracy.agents * 100)}%` : '59'}</strong>
                    <span>{accuracy
                      ? <>right first time on unseen matches; {Math.round(accuracy.alone * 100)}% for AI alone</>
                      : <>unseen matches scored against a hidden answer key</>}</span>
                  </li>
                  <li><strong>5</strong><span>languages, including Arabic, right to left</span></li>
                  <li><strong>100%</strong><span>of claims checked by code before you see them</span></li>
                </ul>
              </>
            ) : error ? (
              <p className="error">Could not load the demo match: {error}</p>
            ) : (
              <div className="hero-skeleton" aria-busy="true" aria-label="Loading the match"><span /><span /><span /><span /></div>
            )}
          </div>

          <figure className="hero-stage rise" style={delay(200)} aria-hidden={!hero}>
            {hero && (
              <>
                <figcaption className="hero-stage-head">
                  <span className="hero-stage-team" style={{ ['--team' as string]: colour }}><i aria-hidden />{scoringName}</span>
                  <span className="hero-stage-title">Goal · {hero.incident_minute}' · {scorer}</span>
                </figcaption>
                <div className="hero-stage-pitch">
                  <Pitch match={hero} path={path} scoringTeam={hero.incident_team} label="scorer" crop accent={colour} />
                  <span className="hero-stage-flag">Simulated</span>
                </div>
                {close && <QuestionStrip match={hero} colour={colour} />}
              </>
            )}
          </figure>
        </div>
        <p className="hero-note">{note} No account needed.</p>
      </section>

      <div className="page">
        <div className="section-row">
          <h2 className="section-kicker">More matches</h2>
          <label className="spoiler-toggle">
            <input type="checkbox" checked={hide} onChange={(e) => set({ spoilerFree: e.target.checked })} />
            <span>Spoiler-free</span>
          </label>
        </div>
        <div className="moments">
          {matches.map((m) => (
            <Link key={m.id} className="moment" to={`/live/${m.id}`}>
              <span className="kicker">{m.metadata?.venue ?? `${m.incident_minute}' goal`}</span>
              <span className="score">{m.home_name} {hide ? 'v' : `${m.score[m.home]}–${m.score[m.away]}`} {m.away_name}</span>
              <span className="note">{hide ? 'Result hidden: watch it unfold' : ROLE_NOTE[m.role]}</span>
            </Link>
          ))}
        </div>

        <h2 className="section-kicker">One pipeline, five stages</h2>
        <div className="how five">
          {[
            ['01', 'Ingest', 'Synthetic events arrive as they happen, from our engine or any provider, and each one is validated.', '/studio', 'Live Studio'],
            ['02', 'Interpret', 'Per-minute states: xG, pass difficulty, control and chaos, pressing, momentum, player speed and distance.', `/live/${showcase?.id ?? ''}`, 'Match centre'],
            ['03', 'Explain', 'Key moments say why they matter; storylines track what is building; AI agents investigate decisive goals.', `/match/${hero?.id ?? ''}`, 'Investigation'],
            ['04', 'Render', 'Overlay cues (JSON, WebVTT), lower thirds, presenter scripts, highlight edit lists, social posts and alerts.', `/pack/${hero?.id ?? ''}`, 'Studio Pack'],
            ['05', 'Personalise', 'Five languages, your club, a player to follow, fan or analyst depth, one-number focus, spoiler-free.', `/live/${showcase?.id ?? ''}`, 'Try it'],
          ].map(([n, h, p, to, cta]) => (
            <div key={n}>
              <div className="n">{n}</div>
              <h3>{h}</h3>
              <p>{p}</p>
              <Link className="how-link" to={to}>{cta} →</Link>
            </div>
          ))}
        </div>
        <p className="faint built-on" style={{display: "none"}}>Orchestrated with Microsoft Agent Framework: the investigation (investigator, sceptic, code verifier, producer) and
          the match pipeline are both Agent Framework workflows. Match intelligence is also available to GitHub Copilot and other agents over MCP.</p>
      </div>
    </>
  )
}
