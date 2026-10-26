import { useState } from 'react'
import { KIND_LABEL, STATUS_LABEL, describeEvent, minute } from '../format'
import type { Claim, Investigation, Match } from '../types'

const STAGES: { agent: 'investigator' | 'sceptic' | 'verifier' | 'producer'; title: string; idle: string }[] = [
  { agent: 'investigator', title: 'Looks for causes', idle: 'The detective: suggests what could explain the goal' },
  { agent: 'sceptic', title: 'Pushes back', idle: "The devil's advocate: tries to knock each idea down" },
  { agent: 'verifier', title: 'Checks the facts', idle: 'The fact-checker (plain code, no AI): every claim must match the events' },
  { agent: 'producer', title: 'Writes it up', idle: 'The writer: only what survived makes it to screen' },
]

interface Props {
  match: Match
  inv: Investigation | null
  stage: number                 // how many stages are revealed (0-4)
  error: string | null
  selectedClaim: Claim | null
  focusId: string | null
  onEvidence: (ids: string[], focus: string, claim: Claim) => void
  onSelectClaim: (c: Claim) => void
}

function EvidenceChips({ ids, match, focusId, onPick }: { ids: string[]; match: Match; focusId: string | null; onPick: (id: string) => void }) {
  const byId = new Map(match.events.map((e) => [e.id, e]))
  return (
    <div className="evidence-row">
      {ids.slice(0, 8).map((id) => {
        const e = byId.get(id)
        return (
          <button key={id} type="button" className={`evidence-chip${focusId === id ? ' active' : ''}`} onClick={() => onPick(id)}
            aria-label={`event ${id}${e ? `, minute ${Math.floor(e.t / 60) + 1}` : ''}`}>
            {e ? `${minute(e.t)} ${describeEvent(match, e)}` : id}
          </button>
        )
      })}
    </div>
  )
}

export default function InvestigationPanel({ match, inv, stage, error, selectedClaim, focusId, onEvidence, onSelectClaim }: Props) {
  const [voice, setVoice] = useState<'fan' | 'analyst'>('fan')
  const claims = inv ? new Map(inv.claims.map((c) => [c.id, c])) : new Map()
  const done = inv !== null && stage >= 4
  const top = inv?.claims.find((c) => c.verified && c.status !== 'refuted') ?? null
  const maxScore = inv ? Math.max(...inv.claims.map((c) => c.score), 0.001) : 1

  return (
    <div className="inv" aria-live="polite">
      <div className="stages">
        {STAGES.map((s, i) => {
          const steps = inv?.trace.filter((t) => t.agent === s.agent) ?? []
          const state = !inv ? (i === 0 && !error ? 'active' : '') : i < stage ? 'done' : i === stage ? 'active' : ''
          const summary = [...steps].reverse().find((t) => t.action !== 'tools') ?? steps[0]
          const text = inv && i < stage ? summary?.detail ?? s.idle : s.idle
          return (
            <div key={s.agent} className={`stage ${state}`}>
              <div className="name">{s.title}</div>
              <div className="what">{s.agent === 'sceptic' && inv && i < stage ? `${steps.filter((t) => t.action === 'challenge').length} explanations tested` : text}</div>
            </div>
          )
        })}
      </div>

      {done && inv && (
        <>
          <section className="panel panel-pad verdict">
            <h2>What really decided it</h2>
            <h2 className="headline">{inv.explanation.headline}</h2>
            <div className="row">
              <span className={`chip ${inv.explanation.confidence === 'strong' ? 'upheld' : inv.explanation.confidence === 'none' ? 'refuted' : 'weakened'}`}>
                {({ strong: 'Very likely', likely: 'Likely', uncertain: 'Unclear', none: 'No answer' } as Record<string, string>)[inv.explanation.confidence]}
              </span>
              <span className="chip neutral">{inv.mode === 'agents' ? `AI agents · ${inv.model_label}` : 'Statistics only'}</span>
              <span className="faint mono" style={{ fontSize: 12 }}>
                {inv.cached ? 'saved result' : `computed in ${inv.elapsed_ms >= 1000 ? `${(inv.elapsed_ms / 1000).toFixed(1)} s` : `${inv.elapsed_ms.toFixed(1)} ms`}`}
              </span>
            </div>
            <p className="mode-note">
              {inv.mode === 'agents' ? (
                <>
                  Two Claude agents dug through the match data on their own ({inv.key_source === 'byok' ? 'your key' : 'demo key'}), then a
                  fact-checker (plain code, no AI) checked every claim against the events and tested the booking.{' '}
                  {inv.producer_source === 'template'
                    ? "This wording comes from our template, because Claude's draft didn't pass the fact check."
                    : 'Claude wrote this summary, and it passed the fact check.'}
                </>
              ) : (
                'Statistics only: no AI involved. The same steps run on numbers and fixed rules.'
              )}
            </p>
          </section>

          {inv.explanation.beats.length > 0 && (
            <section className="panel panel-pad">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <h2 style={{ margin: 0 }}>Why it happened</h2>
                <div className="toggle" role="group" aria-label="Explanation style">
                  <button aria-pressed={voice === 'fan'} onClick={() => setVoice('fan')}>Fan</button>
                  <button aria-pressed={voice === 'analyst'} onClick={() => setVoice('analyst')}>Analyst</button>
                </div>
              </div>
              <div className="beats">
                {inv.explanation.beats.map((b) => (
                  <div className="beat" key={b.label}>
                    <div className="label">{b.label}</div>
                    <div>
                      <p>{b[voice]}</p>
                      <EvidenceChips ids={b.evidence} match={match} focusId={focusId}
                        onPick={(id) => onEvidence(b.evidence, id, claims.get(b.claim_id))} />
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {inv.explanation.ruled_out.length > 0 && (
            <section className="panel panel-pad">
              <h2>What it wasn't</h2>
              <div className="ruled">
                {inv.explanation.ruled_out.map((r) => (
                  <div key={r.claim_id} className={`ruled-item ${r.status}`}>
                    <span className={`chip ${r.status}`}>{STATUS_LABEL[r.status]}</span>
                    <div className="stmt" style={{ marginTop: 6 }}>{r.statement}</div>
                    <div className="why">{r.reason}</div>
                    {r.evidence.length > 0 && (
                      <EvidenceChips ids={r.evidence} match={match} focusId={focusId}
                        onPick={(id) => onEvidence(r.evidence, id, claims.get(r.claim_id))} />
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          <details className="panel panel-pad claims">
            <summary><h2 style={{ margin: 0 }}>Every explanation considered ({inv.claims.length})</h2></summary>
            {inv.claims.map((c) => (
              <div className="claim" key={c.id}>
                <div className="claim-head">
                  <button type="button" className="claim-kind" onClick={() => onSelectClaim(c)}
                    style={{ background: 'none', border: 0, padding: 0, cursor: 'pointer', textDecoration: selectedClaim?.id === c.id ? 'underline' : 'none' }}>
                    {KIND_LABEL[c.kind]}
                  </button>
                  <span className={`chip ${c.status}`}>{STATUS_LABEL[c.status]}</span>
                  {!c.verified && <span className="chip refuted">Not backed by the data</span>}
                  <span className="score-bar" aria-label={`score ${c.score.toFixed(2)}`}><i style={{ width: `${(c.score / maxScore) * 100}%` }} /></span>
                  <span className="mono faint" style={{ fontSize: 12 }}>{c.score.toFixed(2)}</span>
                </div>
                <p className="claim-stmt">{c.statement}</p>
                {c.reasoning && <p className="claim-stmt"><span className="claude-tag">Investigator · Claude</span> {c.reasoning}</p>}
                {c.challenges.length > 0 && (
                  <ul className="qa">
                    {c.challenges.map((ch, i) => (
                      <li key={i}>
                        <span className={`chip ${ch.verdict}`} style={{ alignSelf: 'start' }}>{ch.verdict === 'upheld' ? 'holds up' : ch.verdict === 'weakened' ? 'doubtful' : 'ruled out'}</span>
                        <span>
                          {ch.source === 'llm' && <span className="claude-tag">Sceptic · Claude</span>}{' '}
                          <span className="q">{ch.question}</span> <span className="a">{ch.finding}</span>
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
                {!c.verified && c.verification_notes.length > 0 && (
                  <p className="claim-stmt faint">Fact check: {c.verification_notes.join('; ')}</p>
                )}
              </div>
            ))}
          </details>
          {top === null && <div className="error">No explanation survived verification.</div>}
        </>
      )}
    </div>
  )
}
