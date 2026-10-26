import { Link } from 'react-router-dom'
import type { Lang, Metric } from '../prefs'
import type { Cue, Match, MatchEvent, MinuteState, Moment, Narrative, Recap, Storyline } from '../types'
import { LANG_LABEL, tr, type UIKey } from '../ui'

export const teamColour = (m: Match, team: string) => m.metadata?.colours?.[team]?.[0] ?? (team === m.home ? '#EEF0EA' : '#6E7771')
const clubName = (m: Match, team: string) => (team === m.home ? m.home_name : m.away_name)

export function ScoreBug({ match, state, clock, phase, club }: { match: Match; state: MinuteState | null; clock: number; phase: string; club: string | null }) {
  const g = (t: string) => state?.teams[t]?.goals ?? 0
  const label = phase === 'full_time' ? 'FT' : phase === 'half_time' && clock < 46 * 60 ? 'HT' : `${Math.min(Math.floor(clock / 60) + 1, 90)}'`
  const team = (t: string) => (
    <span className={`sb-team${club === t ? ' mine' : ''}`}><i style={{ background: teamColour(match, t) }} />{clubName(match, t)}{club === t ? ' ★' : ''}</span>
  )
  return (
    <div className="scorebug" role="status" aria-label={`${match.home_name} ${g(match.home)}, ${match.away_name} ${g(match.away)}, ${label}`}>
      {team(match.home)}
      <span className="sb-score">{g(match.home)}<em>–</em>{g(match.away)}</span>
      {team(match.away)}
      <span className="sb-clock">{label}</span>
    </div>
  )
}

export function PersonaliseBar({ match, lang, club, follow, metric, onLang, onClub, onFollow, onMetric }: {
  match: Match; lang: Lang; club: string | null; follow: string | null; metric: Metric | null
  onLang: (l: Lang) => void; onClub: (c: string | null) => void; onFollow: (p: string | null) => void; onMetric: (m: Metric | null) => void
}) {
  const squad = (team: string) => Object.entries(match.roster).filter(([, p]) => p.team === team)
  return (
    <div className="personalise">
      <label className="field inline"><span>{tr(lang, 'language')}</span>
        <select value={lang} onChange={(e) => onLang(e.target.value as Lang)}>
          {(Object.keys(LANG_LABEL) as Lang[]).map((l) => <option key={l} value={l}>{LANG_LABEL[l]}</option>)}
        </select>
      </label>
      <label className="field inline"><span>{tr(lang, 'my_club')}</span>
        <select value={club && [match.home, match.away].includes(club) ? club : ''} onChange={(e) => onClub(e.target.value || null)}>
          <option value="">{tr(lang, 'none')}</option>
          <option value={match.home}>{match.home_name}</option>
          <option value={match.away}>{match.away_name}</option>
        </select>
      </label>
      <label className="field inline"><span>{tr(lang, 'follow')}</span>
        <select value={follow ?? ''} onChange={(e) => onFollow(e.target.value || null)}>
          <option value="">{tr(lang, 'none')}</option>
          {[match.home, match.away].map((t) => (
            <optgroup key={t} label={clubName(match, t)}>
              {squad(t).map(([pid, p]) => <option key={pid} value={pid}>{p.name}</option>)}
            </optgroup>
          ))}
        </select>
      </label>
      <label className="field inline"><span>{tr(lang, 'metric')}</span>
        <select value={metric ?? ''} onChange={(e) => onMetric((e.target.value || null) as Metric | null)}>
          <option value="">{tr(lang, 'none')}</option>
          {(['xg', 'possession', 'pass_accuracy', 'control', 'field_tilt'] as Metric[]).map((m) => <option key={m} value={m}>{tr(lang, m)}</option>)}
        </select>
      </label>
    </div>
  )
}

const ROWS: { key: keyof MinuteState['teams'][string]; fmt?: (v: number) => string; lowerIsBetter?: boolean }[] = [
  { key: 'possession', fmt: (v) => `${v}%` },
  { key: 'shots' },
  { key: 'on_target' },
  { key: 'xg', fmt: (v) => v.toFixed(2) },
  { key: 'pass_accuracy', fmt: (v) => `${v}%` },
  { key: 'field_tilt', fmt: (v) => `${v}%` },
  { key: 'ppda', fmt: (v) => v.toFixed(1), lowerIsBetter: true },
  { key: 'control', fmt: (v) => `${v}/100` },
]

export function LiveStats({ match, state, analyst, lang, club }: { match: Match; state: MinuteState | null; analyst: boolean; lang: Lang; club: string | null }) {
  if (!state) return <div className="panel panel-pad faint">{tr(lang, 'stats')}…</div>
  const rows = analyst ? ROWS : ROWS.filter((r) => ['possession', 'shots', 'on_target', 'xg'].includes(r.key))
  const h = state.teams[match.home], a = state.teams[match.away]
  return (
    <section className="panel panel-pad">
      <h2>{tr(lang, 'stats')}</h2>
      <div className="stat-teams">
        <span className={club === match.home ? 'mine' : ''}>{match.home_name}{club === match.home ? ` · ${tr(lang, 'your_team')}` : ''}</span>
        <span className={club === match.away ? 'mine' : ''}>{club === match.away ? `${tr(lang, 'your_team')} · ` : ''}{match.away_name}</span>
      </div>
      <div className="stat-rows">
        {rows.map((r) => {
          const hv = (h[r.key] as number | null) ?? 0, av = (a[r.key] as number | null) ?? 0
          const total = hv + av || 1
          const share = r.lowerIsBetter ? av / total : hv / total
          return (
            <div className="stat-row" key={r.key}>
              <span className="mono">{r.fmt ? r.fmt(hv) : hv}</span>
              <span className="stat-label" title={tr(lang, `tip_${r.key}` as UIKey)}>{tr(lang, r.key as UIKey)}</span>
              <span className="mono">{r.fmt ? r.fmt(av) : av}</span>
              <span className="stat-bar" aria-hidden>
                <i style={{ width: `${share * 100}%`, background: teamColour(match, match.home) }} />
                <i style={{ width: `${(1 - share) * 100}%`, background: teamColour(match, match.away) }} />
              </span>
            </div>
          )
        })}
      </div>
      {analyst ? (
        <details className="stat-help">
          <summary>{tr(lang, 'what_mean')}</summary>
          <dl>{rows.map((r) => <div key={r.key}><dt>{tr(lang, r.key as UIKey)}</dt><dd>{tr(lang, `tip_${r.key}` as UIKey)}</dd></div>)}</dl>
        </details>
      ) : <p className="stat-hint">{tr(lang, 'xg_hint')}</p>}
    </section>
  )
}

/** One number, big, for viewers who only care about a single metric. */
export function MetricFocus({ match, series, metric, lang }: { match: Match; series: MinuteState[]; metric: Metric; lang: Lang }) {
  const last = series[series.length - 1]
  if (!last) return null
  const fmt = (v: number) => (metric === 'xg' ? v.toFixed(2) : `${Math.round(v)}${metric === 'control' ? '' : '%'}`)
  const W = 300, H = 46
  const vals = series.map((s) => [s.teams[match.home][metric] as number, s.teams[match.away][metric] as number])
  const max = Math.max(1, ...vals.flat())
  const line = (i: 0 | 1) => vals.map((v, k) => `${(k / Math.max(vals.length - 1, 1)) * W},${H - (v[i] / max) * (H - 4)}`).join(' ')
  return (
    <section className="panel panel-pad metric-focus">
      <h2>{tr(lang, metric)}</h2>
      <div className="metric-row">
        <span><i className="dot" style={{ background: teamColour(match, match.home) }} /> {match.home_name}<strong>{fmt(last.teams[match.home][metric] as number)}</strong></span>
        <span><i className="dot" style={{ background: teamColour(match, match.away) }} /> {match.away_name}<strong>{fmt(last.teams[match.away][metric] as number)}</strong></span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} aria-hidden>
        <polyline points={line(0)} fill="none" stroke={teamColour(match, match.home)} strokeWidth={2} />
        <polyline points={line(1)} fill="none" stroke={teamColour(match, match.away)} strokeWidth={2} />
      </svg>
    </section>
  )
}

type Enriched = MatchEvent & { xg?: number; pass_difficulty?: number }

/** Live card for the followed player, computed from the events received so far. */
export function PlayerCard({ match, pid, events, moments, lang }: { match: Match; pid: string; events: Enriched[]; moments: Moment[]; lang: Lang }) {
  const p = match.roster[pid]
  const mine = events.filter((e) => e.player_id === pid)
  const passes = mine.filter((e) => e.type === 'pass')
  const done = passes.filter((e) => e.outcome === 'success')
  const duels = events.filter((e) => e.type === 'dribble' && (e.player_id === pid || e.opponent_id === pid))
  const won = duels.filter((e) => (e.player_id === pid) === (e.outcome === 'success')).length
  const speed = Math.max(0, ...mine.filter((e) => e.type === 'carry' || e.type === 'dribble').map((e) => e.speed_kmh ?? 0))
  const carried = mine.filter((e) => (e.type === 'carry' || e.type === 'dribble') && e.outcome === 'success' && e.end_x !== null)
    .reduce((s, e) => s + Math.hypot(e.end_x! - e.x, e.end_y! - e.y), 0)
  const diffs = passes.map((e) => e.pass_difficulty ?? 0)
  const goals = moments.filter((m) => m.type === 'goal' && m.player_id === pid).length
  const assists = moments.filter((m) => m.type === 'goal' && m.assist_id === pid).length
  const xg = mine.reduce((s, e) => s + (e.xg ?? 0), 0)
  const stat = (k: UIKey, v: string) => <div className="pc-stat"><span>{tr(lang, k)}</span><strong className="mono">{v}</strong></div>
  return (
    <section className="panel panel-pad player-card" style={{ borderTop: `3px solid ${teamColour(match, p.team)}` }}>
      <h2>{tr(lang, 'follow')}</h2>
      <div className="pc-name">{p.name} <span className="faint">{clubName(match, p.team)}{goals ? ` · ⚽ ${goals}` : ''}{assists ? ` · 🅰 ${assists}` : ''}</span></div>
      <div className="pc-grid">
        {stat('touches', `${mine.filter((e) => ['pass', 'carry', 'dribble', 'cross', 'shot'].includes(e.type)).length}`)}
        {stat('passes', passes.length ? `${done.length}/${passes.length}` : '–')}
        {stat('difficulty', diffs.length ? `${Math.round(diffs.reduce((a, b) => a + b, 0) / diffs.length)}/100` : '–')}
        {stat('duels', duels.length ? `${won}/${duels.length}` : '–')}
        {stat('defending', `${mine.filter((e) => e.type === 'tackle' || e.type === 'interception').length}`)}
        {stat('xg', xg ? xg.toFixed(2) : '0.00')}
        {stat('top_speed', speed ? `${speed.toFixed(1)} km/h` : '–')}
        {stat('carried', `${Math.round(carried)} m`)}
      </div>
    </section>
  )
}

export function MomentumChart({ match, series, lang }: { match: Match; series: MinuteState[]; lang: Lang }) {
  const W = 900, H = 120, mid = 60
  const max = Math.max(1, ...series.map((s) => Math.abs(s.momentum)))
  const bw = W / 95
  return (
    <section className="panel momentum">
      <div className="momentum-head">
        <h2 style={{ margin: 0 }}>{tr(lang, 'momentum')}</h2>
        <span className="legend">
          <span><i className="dot" style={{ background: teamColour(match, match.home) }} />{clubName(match, match.home)}</span>
          <span><i className="dot" style={{ background: teamColour(match, match.away) }} />{clubName(match, match.away)}</span>
        </span>
      </div>
      <svg viewBox={`0 0 ${W} ${H + 26}`} role="img" aria-label="Momentum by minute: bars above the line favour the home side">
        <line x1={0} y1={mid} x2={W} y2={mid} stroke="var(--rule)" />
        <line x1={45 * bw} y1={4} x2={45 * bw} y2={H - 4} stroke="var(--rule)" strokeDasharray="3 3" />
        {series.map((s) => {
          const h = (Math.abs(s.momentum) / max) * (mid - 6)
          const home = s.momentum >= 0
          return <rect key={s.minute} x={(s.minute - 1) * bw + 1} y={home ? mid - h : mid} width={bw - 2} height={h}
            fill={teamColour(match, home ? match.home : match.away)} opacity={0.85} />
        })}
        {series.map((s) => (
          <rect key={`c${s.minute}`} x={(s.minute - 1) * bw} y={H + 8} width={bw} height={12}
            fill={`rgba(255,111,97,${(s.chaos / 100) * 0.9})`}><title>{`${s.minute}' chaos ${s.chaos}/100, tempo ${s.tempo_passes_per_min} passes/min`}</title></rect>
        ))}
      </svg>
      <p className="faint" style={{ fontSize: 12.5, margin: '2px 0 0' }}>{tr(lang, 'momentum_note')}</p>
    </section>
  )
}

export function MomentFeed({ match, moments, investigateId, lang, dir, club, follow, onlyFollow, onOnlyFollow }: {
  match: Match; moments: Moment[]; investigateId?: string; lang: Lang; dir: 'ltr' | 'rtl'; club: string | null
  follow: string | null; onlyFollow: boolean; onOnlyFollow: (v: boolean) => void
}) {
  const shown = follow && onlyFollow ? moments.filter((m) => m.player_id === follow || m.assist_id === follow) : moments
  return (
    <section className="panel panel-pad">
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
        <h2 style={{ margin: 0 }}>{tr(lang, 'moments')}</h2>
        {follow && (
          <label className="faint" style={{ fontSize: 13, display: 'flex', gap: 6, alignItems: 'center' }}>
            <input type="checkbox" checked={onlyFollow} onChange={(e) => onOnlyFollow(e.target.checked)} /> {tr(lang, 'only_player')}
          </label>
        )}
      </div>
      {!shown.length ? <p className="faint">{tr(lang, 'waiting')}</p> : (
        <ol className="moments-feed" dir={dir}>
          {[...shown].reverse().map((m) => (
            <li key={`${m.t}-${m.type}`} className={`moment-item ${m.type}${club === m.team ? ' mine' : ''}${follow && (m.player_id === follow || m.assist_id === follow) ? ' followed' : ''}`}>
              <span className="mono moment-min">{m.minute}'</span>
              <div>
                <div className="moment-head">
                  <span className="moment-tag" style={{ borderColor: teamColour(match, m.team) }}>{clubName(match, m.team)}</span>
                  <strong>{m.headline}</strong>
                </div>
                <p className="moment-why">{m.why}</p>
                {m.type === 'goal' && m.event_id === investigateId && (
                  <Link className="why-link" to={`/match/${match.id}`}>{tr(lang, 'why_goal')}</Link>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

export function OverlayLayer({ match, cues, dir, follow }: { match: Match; cues: Cue[]; dir: 'ltr' | 'rtl'; follow: string | null }) {
  const rank = (c: Cue) => c.priority + (follow && c.player_id === follow ? 2 : 0)
  const top = [...cues].sort((a, b) => rank(b) - rank(a)).slice(0, 2)
  return (
    <div className="overlay-layer" aria-live="polite" dir={dir}>
      {top.map((c) => (
        <div key={`${c.t_in}-${c.text}`} className={`lower-third ${c.kind}`} style={{ borderInlineStartColor: teamColour(match, c.team) }}>
          <strong>{c.text}</strong>
          {c.subtext && <span>{c.subtext}</span>}
        </div>
      ))}
    </div>
  )
}

export function RecapCard({ recap, phase, analyst, onAnalyst, lang, dir }: {
  recap: Recap | null; phase: 'ht' | 'ft'; analyst: boolean; onAnalyst: (v: boolean) => void; lang: Lang; dir: 'ltr' | 'rtl'
}) {
  return (
    <section className="panel panel-pad recap">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
        <h2 style={{ margin: 0 }}>{tr(lang, phase)}</h2>
        <div className="toggle" role="group">
          <button aria-pressed={!analyst} onClick={() => onAnalyst(false)}>{tr(lang, 'fan')}</button>
          <button aria-pressed={analyst} onClick={() => onAnalyst(true)}>{tr(lang, 'analyst')}</button>
        </div>
      </div>
      {!recap ? <p className="faint">…</p> : (
        <div dir={dir}>
          <h3 className="recap-headline">{recap.headline}</h3>
          {recap.paragraphs.map((p, i) => <p key={i}>{p}</p>)}
          <p className="faint" style={{ fontSize: 12.5, marginBottom: 0 }}>{recap.source === 'claude' ? tr(lang, 'recap_by') : recap.note ?? 'Template recap.'}</p>
        </div>
      )}
    </section>
  )
}

const KIND_MARK: Record<Storyline['kind'], string> = { control: '◆', flank: '⇢', duels: '⚑', discipline: '▮', chase: '↺' }

/** Storylines as they stood at `clock`: only beats already "broadcast" are shown, so replays never spoil. */
export function StorylinesPanel({ match, narrative, clock, lang, dir, club, follow }: {
  match: Match; narrative?: Narrative; clock: number; lang: Lang; dir: 'ltr' | 'rtl'; club: string | null; follow: string | null
}) {
  if (!narrative) return null
  const mine = (s: Storyline) => (follow && s.player_id === follow ? 2 : 0) + (club && s.team === club ? 1 : 0)
  const live = narrative.storylines
    .filter((s) => s.opened_t <= clock)
    .map((s) => ({ ...s, beats: s.beats.filter((b) => b.t <= clock), done: s.closed_t !== undefined && s.closed_t <= clock }))
    .sort((a, b) => mine(b) - mine(a) || Number(a.done) - Number(b.done) || b.beats[b.beats.length - 1].t - a.beats[a.beats.length - 1].t)
    .slice(0, 4)
  const summary = [...narrative.summaries].reverse().find((x) => x.t <= clock)
  const miles = narrative.milestones.filter((m) => m.t <= clock).slice(-3).reverse()
  return (
    <section className="panel panel-pad stories" dir={dir}>
      <h2>{tr(lang, 'storylines')}</h2>
      {summary && (
        <div className="story-sofar">
          <span className="mono">{tr(lang, 'story_so_far')} · {summary.minute}'</span>
          <p>{summary.text}</p>
        </div>
      )}
      {!live.length ? <p className="faint" style={{ margin: 0 }}>{tr(lang, 'no_story')}</p> : (
        <ol className="story-list">
          {live.map((s) => {
            const latest = s.beats[s.beats.length - 1]
            return (
              <li key={s.id} className={`story ${s.kind}${s.done ? ' done' : ''}${mine(s) ? ' mine' : ''}`}
                style={{ borderInlineStartColor: teamColour(match, s.team) }}>
                <div className="story-head">
                  <span className="story-kind" aria-hidden>{KIND_MARK[s.kind]}</span>
                  <strong>{s.title}</strong>
                  <span className={`story-status${s.done ? '' : ' open'}`}>{tr(lang, s.done ? 'resolved' : 'developing')}</span>
                </div>
                <p><span className="mono">{latest.minute}'</span> {latest.text}</p>
                {s.beats.length > 1 && (
                  <span className="story-beats" aria-label={`${s.beats.length} updates`}>
                    {s.beats.map((b) => <i key={b.t} title={`${b.minute}' ${b.text}`} />)}
                  </span>
                )}
              </li>
            )
          })}
        </ol>
      )}
      {miles.length > 0 && (
        <div className="milestones">
          <span className="mono">{tr(lang, 'milestones')}</span>
          {miles.map((m) => <span key={m.key} className="milestone"><b className="mono">{m.minute}'</b> {m.text}</span>)}
        </div>
      )}
    </section>
  )
}
