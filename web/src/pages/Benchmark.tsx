/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useState } from 'react'
import { api } from '../api'

const LABELS: Record<string, string> = {
  random: 'Random guess',
  salience: 'Blame the most recent drama (the booking)',
  lane_shortcut: 'Guess from the side the goal came from',
  stat_unfitted: 'Statistics engine (untuned)',
  stat_fitted: 'Statistics engine',
  'deterministic (shipped)': 'Statistics only',
  investigator_only: 'Statistics, no sceptic',
  'sceptic_refute (default)': 'Statistics + sceptic',
  sceptic_rescore: 'Statistics + sceptic that re-ranks',
  agents: 'AI agents (Claude Haiku 5.5)',
  llm_only: 'Claude reading the raw match log',
}
const pct = (x: number | undefined) => (x === undefined ? '–' : `${Math.round(x * 100)}%`)

function ScoreTable({ rows, highlight, order }: { rows: Record<string, any>; highlight: string[]; order?: string[] }) {
  const names = order ? order.filter((n) => rows[n]) : Object.keys(rows)
  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="data">
        <thead>
          <tr><th>Who explains the goal</th><th>Right cause first</th><th>In its top 3</th><th>Ignores the booking</th><th>Claims not backed by data</th></tr>
        </thead>
        <tbody>
          {names.map((name) => {
            const s = rows[name]
            return (
              <tr key={name} className={highlight.includes(name) ? 'ours' : ''}>
                <td>{LABELS[name] ?? name}</td>
                <td>{pct(s['recall@1'])}</td>
                <td>{pct(s['recall@3'])}</td>
                <td>{pct(s.decoy_rejection)}</td>
                <td>{name === 'agents' && s.pre_verification_unsupported_rate !== undefined
                  ? `${pct(s.pre_verification_unsupported_rate)} caught, 0% shown` : pct(s.unsupported_claim_rate)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default function Benchmark() {
  const [data, setData] = useState<Record<string, any> | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { api.benchmark().then(setData).catch((e) => setError(e.message)) }, [])

  if (error) return <div className="page"><p className="error" style={{ marginTop: 32 }}>{error}</p></div>
  if (!data) return <div className="page"><p className="faint" style={{ marginTop: 32 }}>Loading results…</p></div>

  const p0 = data.phase0
  const s2 = data.slice2_sceptic
  const cur = data.agents_heldout_v21
  const v1 = data.slice3_agents
  const v1b = data.agents_heldout2

  return (
    <div className="page bench">
      <h1>How accurate is it?</h1>
      <p className="lede">
        Anyone can write a convincing explanation of a goal. The question is whether it's the <em>right</em> one. Our matches are
        simulated, so we plant a hidden cause in each one (a tiring full-back, an outnumbered flank, a defender who is outmatched)
        and measure that it really changed the goals. Then we check the explanation against that answer key, on matches the system
        has never seen.
      </p>

      {cur ? (
        <section>
          <h2>On {cur.n_cases} new matches</h2>
          <ScoreTable rows={cur.variants} highlight={['agents']} order={['agents', 'deterministic (shipped)', 'llm_only']} />
          <p className="callout">
            The AI agents name the real cause first in {pct(cur.variants.agents?.['recall@1'])} of matches; the statistics engine on its own
            manages {pct(cur.variants['deterministic (shipped)']?.['recall@1'])}. Claude reading the raw match log, with no tools and no fact
            checks, gets {pct(cur.variants.llm_only?.['recall@1'])}, and {pct(cur.variants.llm_only?.unsupported_claim_rate)} of its claims
            aren't backed by the data. The tools and checks are what make the AI useful.
          </p>
          <p className="faint" style={{ fontSize: 13, display: "none"}}>
            One run per match ({cur.model}), so expect a few points of variation. About ${cur.variants.agents?.mean_cost_usd} and{' '}
            {cur.variants.agents?.mean_calls} model calls per AI investigation (estimated). Estimated cost of this whole test: ${cur.spent_usd_estimate.toFixed(2)}.
          </p>
        </section>
      ) : p0 && (
        <section>
          <h2>On {p0.truth.labelled + p0.truth.ambiguous} new matches</h2>
          <ScoreTable rows={p0.test_scores} highlight={['stat_fitted']} />
        </section>
      )}

      {p0 && (
        <section>
          <h2>Why the simple stories fail</h2>
          <p className="muted">
            The obvious story, blaming the booking just before the goal, is right in {pct(p0.test_scores.salience['recall@1'])} of matches.
            Guessing from the side the goal came from gets {pct(p0.test_scores.lane_shortcut['recall@1'])}. Finding the real cause means
            looking at when things changed during the match, not just at the goal.
          </p>
          <ScoreTable rows={p0.test_scores} highlight={['stat_fitted']} order={['stat_fitted', 'lane_shortcut', 'salience', 'random']} />
        </section>
      )}

      <section>
        <h2>How the answer key works</h2>
        <div className="cards">
          <div className="panel panel-pad">
            <h2>Planted, then measured</h2>
            <p className="muted" style={{ margin: 0 }}>Each match is re-played {p0?.args?.k ?? 120} times from the moment a hidden cause begins, with and
              without it. A cause counts only if it clearly changed the number of goals.</p>
          </div>
          <div className="panel panel-pad">
            <h2>Never seen by the AI</h2>
            <p className="muted" style={{ margin: 0 }}>The agents only see the match events everyone can see. The answer key is stored separately, and tests
              fail if any hidden detail leaks into the events.</p>
          </div>
          <div className="panel panel-pad">
            <h2>Honest limits</h2>
            <p className="muted" style={{ margin: 0 }}>This is a simulation, not real football. Real club and player names are used for familiarity; the
              events, goals and explanations are invented.</p>
          </div>
        </div>
      </section>

      <details className="panel panel-pad" style={{ marginTop: 40 }}>
        <summary><strong>For data scientists: gates, ablations and history</strong></summary>
        {p0 && (
          <>
            <h3>Pre-registered gates</h3>
            <div className="gates">
              {Object.entries(p0.gates).map(([g, v]: [string, any]) => (
                <div className="gate" key={g}>
                  <span className={`chip ${v.pass ? 'upheld' : 'refuted'}`}>{v.pass ? 'Pass' : 'Fail'}</span>
                  <span className="mono" style={{ fontSize: 13 }}>{g.replace(/_/g, ' ')}</span>
                  <span className="detail muted">{Array.isArray(v.detail) ? (v.detail.length ? v.detail.join('; ') : 'no hidden terms in the event stream') : v.detail}</span>
                </div>
              ))}
            </div>
            <p className="callout" style={{ marginTop: 12 }}>The failed gate is reported, not hidden: the statistics engine still can't tell a defender
              who tired late from one outmatched all game.</p>
          </>
        )}
        {s2?.fresh_test && (
          <>
            <h3>Does the rule-based sceptic change the answer?</h3>
            <ScoreTable rows={s2.fresh_test} highlight={['sceptic_refute (default)']} />
          </>
        )}
        {(v1 || v1b) && (
          <>
            <h3>Earlier engine (fictional clubs)</h3>
            <p className="muted">Before switching to real squads, the first AI agents trailed the statistics engine on outnumbered flanks; an
              overload detector and citation pruning closed the gap. Those runs used a different engine, so they are not comparable with the table above.</p>
            {v1 && <ScoreTable rows={v1.variants} highlight={['agents']} />}
            {v1b && <ScoreTable rows={v1b.variants} highlight={['agents']} />}
          </>
        )}
      </details>
    </div>
  )
}
