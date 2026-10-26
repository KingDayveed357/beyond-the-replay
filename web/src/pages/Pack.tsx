import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { teamColour } from '../components/LivePanels'
import { usePrefs, type Lang } from '../prefs'
import type { Match } from '../types'
import { LANG_LABEL } from '../ui'

interface Clip { n: number; type: string; minute: number; team: string; in: number; out: number; in_tc: string; out_tc: string; label: string; why: string; for_you: boolean }
interface Line { cue: string; text: string }
interface StudioPack {
  lang: Lang; finished: boolean
  match: { home: string; away: string; home_name: string; away_name: string; score: Record<string, number>; venue: string; minute: number }
  presenter: Record<'30s' | '60s', { lines: Line[]; words: number; seconds: number }>
  highlights: { clips: Clip[]; duration_s: number }
  lower_thirds: { t: number; minute: number; team: string; line1: string; line2: string }[]
  push: { minute: number; title: string; body: string; for_you: boolean }[]
  social: { post: string; thread: string[]; caption: string }
  stat_cards: { title: string; home: string; away: string }[]
  why_it_happened: { headline: string; confidence: string } | null
}

function Copy({ text }: { text: string }) {
  const [done, setDone] = useState(false)
  return (
    <button className="copy-btn" onClick={() => { navigator.clipboard?.writeText(text).then(() => { setDone(true); setTimeout(() => setDone(false), 1400) }).catch(() => {}) }}>
      {done ? 'Copied' : 'Copy'}
    </button>
  )
}

/** Studio Pack: the automated recap bundle for studio, broadcast and streaming teams. */
export default function Pack() {
  const { id = '' } = useParams()
  const { prefs, set } = usePrefs()
  const [match, setMatch] = useState<Match | null>(null)
  const [pack, setPack] = useState<StudioPack | null>(null)
  const [length, setLength] = useState<'30s' | '60s'>('30s')
  const [player, setPlayer] = useState('')
  const [error, setError] = useState<string | null>(null)
  const club = match && prefs.club && [match.home, match.away].includes(prefs.club) ? prefs.club : ''
  const query = `lang=${prefs.lang}${club ? `&club=${club}` : ''}${player ? `&player=${player}` : ''}`
  const base = `/api/matches/${id}/studio-pack`

  useEffect(() => { api.match(id).then(setMatch).catch((e) => setError(e.message)) }, [id])
  useEffect(() => {
    setPack(null)
    fetch(`${base}?${query}`).then((r) => (r.ok ? r.json() : Promise.reject(new Error(`${r.status}`)))).then(setPack).catch((e) => setError(e.message))
  }, [base, query])

  if (error) return <div className="page"><p className="error" style={{ marginTop: 32 }}>{error}</p></div>
  if (!match || !pack) return <div className="page"><p className="faint" style={{ marginTop: 32 }}>Building the studio pack…</p></div>
  const m = pack.match
  const dir = pack.lang === 'ar' ? 'rtl' : 'ltr'
  const script = pack.presenter[length]
  const span = 95 * 60

  return (
    <div className="page pack">
      <header className="pack-head">
        <div>
          <p className="eyebrow"><span className="eyebrow-live" aria-hidden />Studio Pack · automated recap</p>
          <h1>{m.home_name} {m.score[m.home]}–{m.score[m.away]} {m.away_name}</h1>
          <p className="muted">Scripts, highlights, graphics, social and alerts for studio, broadcast and streaming teams. Generated in under a second from
            the checked match data, so every name, minute and number agrees with the feed.</p>
        </div>
        <div className="pack-controls">
          <label className="field inline"><span>Language</span>
            <select value={prefs.lang} onChange={(e) => set({ lang: e.target.value as Lang })}>
              {(Object.keys(LANG_LABEL) as Lang[]).map((l) => <option key={l} value={l}>{LANG_LABEL[l]}</option>)}
            </select>
          </label>
          <label className="field inline"><span>For a club</span>
            <select value={club} onChange={(e) => set({ club: e.target.value || null })}>
              <option value="">Neutral</option>
              <option value={match.home}>{match.home_name}</option>
              <option value={match.away}>{match.away_name}</option>
            </select>
          </label>
          <label className="field inline"><span>Feature a player</span>
            <select value={player} onChange={(e) => setPlayer(e.target.value)}>
              <option value="">None</option>
              {[match.home, match.away].map((t) => (
                <optgroup key={t} label={t === match.home ? match.home_name : match.away_name}>
                  {Object.entries(match.roster).filter(([, p]) => p.team === t).map(([pid, p]) => <option key={pid} value={pid}>{p.name}</option>)}
                </optgroup>
              ))}
            </select>
          </label>
          <div className="pack-downloads">
            <a className="btn ghost" href={`${base}?${query}&format=md`} target="_blank" rel="noreferrer">Rundown (.md)</a>
            <a className="btn ghost" href={`${base}?${query}&format=edl`}>Edit list (.edl)</a>
            <a className="btn ghost" href={`${base}?${query}&format=csv`}>Clips (.csv)</a>
            <a className="btn ghost" href={`${base}?${query}`} target="_blank" rel="noreferrer">JSON</a>
          </div>
        </div>
      </header>

      <div className="pack-grid" dir={dir}>
        <section className="panel panel-pad autocue">
          <div className="pack-section-head">
            <h2>Presenter script</h2>
            <div className="toggle" role="group" aria-label="Script length">
              {(['30s', '60s'] as const).map((k) => <button key={k} aria-pressed={length === k} onClick={() => setLength(k)}>{k}</button>)}
            </div>
            <Copy text={script.lines.map((l) => `[${l.cue}] ${l.text}`).join('\n')} />
          </div>
          <ol className="cue-lines">
            {script.lines.map((l, i) => <li key={i}><span className="cue-chip mono">{l.cue}</span><p>{l.text}</p></li>)}
          </ol>
          <p className="faint mono" style={{ fontSize: 12, margin: 0 }}>{script.words} words · about {script.seconds} s at broadcast pace</p>
        </section>

        <section className="panel panel-pad">
          <div className="pack-section-head">
            <h2>Highlights rundown</h2>
            <span className="faint mono" style={{ fontSize: 12 }}>{pack.highlights.clips.length} clips · {Math.round(pack.highlights.duration_s)} s</span>
          </div>
          <div className="clip-bar" aria-hidden>
            <span className="clip-ht" style={{ left: `${(45 * 60 / span) * 100}%` }} />
            {pack.highlights.clips.map((c) => (
              <i key={c.n} className={c.type} style={{ left: `${(c.in / span) * 100}%`, width: `${Math.max(0.8, ((c.out - c.in) / span) * 100)}%`,
                background: teamColour(match, c.team) }} title={c.label} />
            ))}
          </div>
          <ol className="clip-list">
            {pack.highlights.clips.map((c) => (
              <li key={c.n} className={c.for_you ? 'for-you' : ''}>
                <span className="mono clip-n">{String(c.n).padStart(2, '0')}</span>
                <span className="mono clip-tc">{c.in_tc}<br />{c.out_tc}</span>
                <span><strong>{c.label}</strong>{c.for_you && <em className="for-you-tag"> for you</em>}<br /><span className="faint">{c.why}</span></span>
              </li>
            ))}
          </ol>
        </section>

        <section className="panel panel-pad">
          <div className="pack-section-head"><h2>Social</h2><Copy text={pack.social.post} /></div>
          <div className="social-post">
            <p>{pack.social.post}</p>
            <span className="faint mono" style={{ fontSize: 11.5 }}>{pack.social.post.length}/280</span>
          </div>
          <ol className="thread">{pack.social.thread.map((t, i) => <li key={i}><span className="mono faint">{i + 1}/{pack.social.thread.length}</span> {t}</li>)}</ol>
        </section>

        <section className="panel panel-pad">
          <h2>Push alerts</h2>
          <div className="push-list">
            {pack.push.map((p, i) => (
              <div key={i} className={`push${p.for_you ? ' for-you' : ''}`}>
                <span className="push-app mono">BEYOND THE REPLAY · {p.minute}'</span>
                <strong>{p.title}</strong>
                <span>{p.body}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="panel panel-pad pack-wide">
          <h2>Lower thirds</h2>
          <div className="lt-strip">
            {pack.lower_thirds.map((x, i) => (
              <div key={i} className="lower-third" style={{ borderInlineStartColor: teamColour(match, x.team) }}>
                <strong><span className="mono faint">{x.minute}'</span> {x.line1}</strong><span>{x.line2}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="panel panel-pad pack-wide">
          <h2>Stat cards</h2>
          <div className="stat-cards">
            {pack.stat_cards.map((c) => (
              <div key={c.title} className="stat-card">
                <span className="mono">{c.title}</span>
                <div><b style={{ color: teamColour(match, m.home) }}>{c.home}</b><em>{m.home_name} · {m.away_name}</em><b style={{ color: teamColour(match, m.away) }}>{c.away}</b></div>
              </div>
            ))}
          </div>
          {pack.why_it_happened && (
            <p className="pack-why"><span className="mono">Why it happened (AI, every claim checked)</span>{pack.why_it_happened.headline}</p>
          )}
        </section>
      </div>
      <p className="faint" style={{ fontSize: 13 }}><Link to={`/live/${id}`}>Back to the match centre</Link> · <Link to={`/match/${id}`}>The investigation</Link></p>
    </div>
  )
}
