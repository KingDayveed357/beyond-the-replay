import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError, api } from '../api'
import InvestigationPanel from '../components/InvestigationPanel'
import Pitch from '../components/Pitch'
import Timeline from '../components/Timeline'
import TruthReveal from '../components/TruthReveal'
import YourCall, { type Call, callLabel, clearCall, saveCall, savedCall } from '../components/YourCall'
import { KIND_LABEL, clubName, describeEvent, minute } from '../format'
import { useModel } from '../model'
import type { Claim, Investigation, Match } from '../types'

const STAGE_MS = 450
const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false

export default function Workspace() {
  const { id = '' } = useParams()
  const [match, setMatch] = useState<Match | null>(null)
  const [inv, setInv] = useState<Investigation | null>(null)
  const [stage, setStage] = useState(0)
  const [error, setError] = useState<ApiError | null>(null)
  const [mode, setMode] = useState<'agents' | 'deterministic'>('agents')
  const [running, setRunning] = useState(false)
  const [waited, setWaited] = useState(0)
  const { byok, openSettings, status } = useModel()
  const [claim, setClaim] = useState<Claim | null>(null)
  const [evidenceIds, setEvidenceIds] = useState<string[]>([])
  const [focusId, setFocusId] = useState<string | null>(null)
  const [replayKey, setReplayKey] = useState(0)
  const [call, setCall] = useState<Call | null>(() => savedCall(id))

  useEffect(() => {
    setMatch(null); setInv(null); setStage(0); setError(null); setClaim(null); setEvidenceIds([]); setFocusId(null)
    setCall(savedCall(id))
    api.match(id).then(setMatch).catch((e) => setError(e))
  }, [id])

  useEffect(() => {
    if (!running) return
    setWaited(0)
    const t = setInterval(() => setWaited((w) => w + 1), 1000)
    return () => clearInterval(t)
  }, [running])

  const run = useCallback(async (m: Match, runMode: 'agents' | 'deterministic', fresh = false) => {
    setInv(null); setStage(0); setError(null); setRunning(true); setMode(runMode)
    try {
      const out = await api.investigate(m.id, m.incident_id, { mode: runMode, fresh, byok })
      setInv(out)
      const first = out.claims.find((c) => c.verified && c.status !== 'refuted') ?? null
      setClaim(first)
      setEvidenceIds(first?.cited ?? [])
      if (reducedMotion()) { setStage(4); return }
      for (let i = 1; i <= 4; i++) setTimeout(() => setStage(i), i * STAGE_MS)
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError((e as Error).message))
    } finally {
      setRunning(false)
    }
  }, [byok])

  // Agents by default, once the viewer has made (or skipped) their call: a saved result returns instantly.
  useEffect(() => {
    if (!match || status === undefined || call === null || inv || running) return
    run(match, 'agents', !!byok)
  }, [match, call]) // eslint-disable-line react-hooks/exhaustive-deps

  const makeCall = (c: Call) => { saveCall(id, c); setCall(c) }

  const byId = useMemo(() => new Map(match?.events.map((e) => [e.id, e]) ?? []), [match])
  const path = useMemo(() => {
    if (!match) return []
    const goal = byId.get(match.incident_id)!
    return match.events.filter((e) => e.possession_id === goal.possession_id && e.team === goal.team && e.t <= goal.t)
  }, [match, byId])

  if (error && !match) return <div className="page"><p className="error" style={{ marginTop: 32 }}>{error.message}</p></div>
  if (!match) return <div className="page"><p className="faint" style={{ marginTop: 32 }}>Loading match…</p></div>

  const done = inv !== null && stage >= 4
  const evidence = done ? evidenceIds.map((x) => byId.get(x)).filter((e): e is NonNullable<typeof e> => !!e) : []
  const focus = focusId ? byId.get(focusId) ?? null : null
  const scoring = match.incident_team
  const conceding = scoring === match.home ? match.away : match.home

  const pickEvidence = (ids: string[], f: string, c?: Claim) => {
    setEvidenceIds(ids); setFocusId(f); if (c) setClaim(c)
  }

  return (
    <div className="page">
      <header className="match-head">
        <h1>{match.home_name} <span className="score">{match.score[match.home]}–{match.score[match.away]}</span> {match.away_name}</h1>
        <span className="tag synthetic">Simulated match</span>
        {match.metadata?.venue && (
          <span className="muted" style={{ fontSize: 14 }}>
            {match.metadata.venue} · {match.metadata.kickoff} · Referee {match.metadata.referee}
            {match.metadata.attendance ? ` · ${match.metadata.attendance.toLocaleString()} (simulated)` : ''}
          </span>
        )}
        <span className="spacer" />
        <span className="muted">Investigating {clubName(match, scoring)}'s goal at <span className="mono">{match.incident_minute}'</span></span>
      </header>

      <div className="workspace">
        <div className="stage-col">
          <div className="pitch-wrap">
            <Pitch key={replayKey} match={match} path={path} evidence={evidence} focus={focus} scoringTeam={scoring} />
            <div className="pitch-caption">
              <span>
                {focus ? <><strong>{minute(focus.t)}</strong> {describeEvent(match, focus)}</>
                  : evidence.length && claim ? <><strong>{KIND_LABEL[claim.kind]}</strong>: {evidence.length} cited events in green, plus the goal move</>
                  : <><strong>The goal move</strong>: {path.length} events, {clubName(match, scoring)} attacking</>}
              </span>
              <span className="legend">
                <span><i className="dot" style={{ background: 'var(--chalk)' }} />{clubName(match, scoring)}</span>
                <span><i className="dot" style={{ border: '1.5px solid var(--chalk)' }} />{clubName(match, conceding)}</span>
                <button className="evidence-chip" onClick={() => { setFocusId(null); setReplayKey((k) => k + 1) }}>Replay</button>
              </span>
            </div>
          </div>
          <div className="panel timeline">
            <Timeline match={match} scoringTeam={scoring} incidentId={match.incident_id}
              evidenceIds={new Set(evidence.map((e) => e.id))} focusId={focusId}
              onsetMinute={done && claim?.onset != null ? Math.floor(claim.onset / 60) + 1 : null}
              onSelect={(eid) => setFocusId(eid)} />
          </div>
        </div>

        <div className="inv">
          {call === null && <YourCall match={match} onCall={makeCall} />}
          {call !== null && <>
          <div className="run-bar">
            <div className="toggle" role="group" aria-label="Who investigates">
              <button aria-pressed={mode === 'agents'} disabled={running} onClick={() => run(match, 'agents')}>AI agents</button>
              <button aria-pressed={mode === 'deterministic'} disabled={running} onClick={() => run(match, 'deterministic')}>Statistics only</button>
            </div>
            {inv?.mode === 'agents' && !running && (
              <span className="run-meta">
                {inv.cached ? <>Saved result from {inv.created_at?.slice(0, 16).replace('T', ' ')} UTC · </>
                  : <>{inv.usage?.calls} model calls · {((inv.usage?.input_tokens ?? 0) + (inv.usage?.output_tokens ?? 0)).toLocaleString()} tokens · ≈${inv.usage?.cost_usd_estimate.toFixed(4)} est. · </>}
                <button onClick={() => run(match, 'agents', true)}>Run fresh</button>
              </span>
            )}
          </div>

          {running && (
            <div className="waiting" role="status">
              {mode === 'agents'
                ? <>Claude agents are investigating with {byok ? 'your key' : 'the demo key'}… {waited}s. A fresh run usually takes 30 to 60 seconds:
                    the detective and the devil's advocate each dig through the match data.</>
                : 'Running the statistics-only investigation…'}
            </div>
          )}

          {error && !running && (
            <div className="error" role="alert">
              <strong>{mode === 'agents' ? 'The Claude agents could not run.' : 'The investigation could not run.'}</strong> {error.message}
              {' '}Nothing is shown in its place.
              <div className="error-actions">
                {error.retryable && <button className="btn ghost" onClick={() => run(match, mode, true)}>Try again</button>}
                {mode === 'agents' && <button className="btn ghost" onClick={() => run(match, 'deterministic')}>Use the statistics-only version instead</button>}
                {mode === 'agents' && !byok && <button className="btn ghost" onClick={() => openSettings(true)}>Use your own key</button>}
              </div>
            </div>
          )}

          <InvestigationPanel match={match} inv={inv} stage={stage} error={error && !running ? error.message : null}
            selectedClaim={claim} focusId={focusId} onEvidence={pickEvidence}
            onSelectClaim={(c) => { setClaim(c); setEvidenceIds(c.cited); setFocusId(null) }} />
          {done && inv && call !== 'skip' && (
            <div className="call-vs">
              <span>You said <strong>{callLabel(call)}</strong></span>
              <span>The AI says <strong>{inv.ranking[0] ? callLabel(inv.ranking[0][0]) : 'no clear cause'}</strong></span>
              <button className="call-skip" onClick={() => { clearCall(id); setCall(null); setInv(null); setStage(0) }}>Change my call</button>
            </div>
          )}
          {done && inv && <TruthReveal key={inv.id} match={match} inv={inv} call={call === 'skip' ? null : call} />}
          {done && (
            <p className="faint" style={{ fontSize: 13 }}>
              Every mark on the pitch is a generated event. <Link to="/benchmark">How often is the AI right?</Link>
            </p>
          )}
          </>}
        </div>
      </div>
    </div>
  )
}
