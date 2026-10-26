import { useState } from 'react'
import { api } from '../api'
import { KIND_LABEL, playerName } from '../format'
import type { Investigation, Match, Truth } from '../types'
import { record } from './YourCall'
import { play } from '../sound'

const keyText = (m: Match, key: [string, string]) => {
  const [kind, target] = key
  const label = KIND_LABEL[kind as keyof typeof KIND_LABEL] ?? kind
  return kind === 'OVERLOAD' || kind === 'STYLE' ? `${label}: ${target} flank` : `${label}: ${playerName(m, target)}`
}

export default function TruthReveal({ match, inv, call = null }: { match: Match; inv: Investigation; call?: string | null }) {
  const [truth, setTruth] = useState<Truth | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (!truth) {
    return (
      <section className="panel panel-pad">
        <h2>The real answer</h2>
        <p className="muted" style={{ margin: '0 0 14px', fontSize: 14.5 }}>
          This match is simulated, so we know what really caused the goal. The AI never sees this. Reveal it to see whether it got it right.
        </p>
        <button className="btn truth" disabled={busy} onClick={async () => {
          setBusy(true)
          try {
            const t = await api.truth(match.id, match.incident_id)
            if (call && t.label) record(match.id, call === t.label[0])
            const top = inv.ranking[0]
            const good = call && t.label ? call === t.label[0] : !!(t.label && top && top[0] === t.label[0] && top[1] === t.label[1])
            play(good ? 'right' : 'wrong')
            setTruth(t)
          } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
        }}>
          {busy ? 'Loading…' : 'Reveal the answer'}
        </button>
        {error && <p className="error" style={{ marginTop: 12 }}>{error}</p>}
      </section>
    )
  }

  const top = inv.ranking[0]
  const matched = truth.label !== null && top && top[0] === truth.label[0] && top[1] === truth.label[1]
  const maxEffect = Math.max(...truth.effects.map((e) => Math.abs(e.mean)), 0.01)
  const youRight = call && truth.label ? call === truth.label[0] : null
  const tally = record()

  return (
    <section className="truth-panel">
      <h2>The real answer</h2>
      {truth.label === null ? (
        <p className="big">No single hidden cause stands out in this match.</p>
      ) : (
        <p className="big">{matched ? 'It got it right.' : 'It got this one wrong.'}</p>
      )}
      {youRight !== null && (
        <p className={`you-result ${youRight ? 'right' : 'wrong'}`}>
          {youRight ? 'And so did you. You called it.' : 'Your call was different this time.'}
          {tally.played > 0 && <span className="mono"> Your record: {tally.right} of {tally.played}</span>}
        </p>
      )}
      <p className="muted" style={{ margin: 0, fontSize: 14.5 }}>
        {truth.label ? <>Measured cause: <strong style={{ color: 'var(--chalk)' }}>{keyText(match, truth.label)}</strong>. </> : null}
        The AI's answer: <strong style={{ color: 'var(--chalk)' }}>{top ? keyText(match, top) : 'none'}</strong>.
      </p>
      <table className="effects">
        <thead>
          <tr><th>Hidden cause</th><th>Goals it was worth</th><th style={{ width: '32%' }} /></tr>
        </thead>
        <tbody>
          {truth.effects.map((e) => (
            <tr key={e.variable}>
              <td>{keyText(match, e.key)}</td>
              <td className="mono">{e.mean >= 0 ? '+' : ''}{e.mean.toFixed(2)} ± {(2 * e.se).toFixed(2)}</td>
              <td><div className="effect-bar" style={{ width: `${(Math.max(e.mean, 0) / maxEffect) * 100}%` }} /></td>
            </tr>
          ))}
          <tr>
            <td>The booking</td>
            <td className="mono">0.00</td>
            <td className="faint" style={{ fontSize: 12 }}>no effect by construction</td>
          </tr>
        </tbody>
      </table>
      <p className="faint" style={{ fontSize: 12.5, marginTop: 12, marginBottom: 0 }}>
        Each effect is the average change in the scoring team's goals after minute {truth.factor_onset_minute - 1}, over {truth.k} paired
        simulations with and without that factor (± two standard errors). It describes this simulation, not real football.
      </p>
    </section>
  )
}
