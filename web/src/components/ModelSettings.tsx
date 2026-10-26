import { useEffect, useRef, useState } from 'react'
import { ApiError, api } from '../api'
import { maskKey, modelLabel, useModel } from '../model'

export function ModelButton() {
  const { status, byok, openSettings } = useModel()
  const name = byok ? modelLabel(status, byok.model) : status?.server_key_configured ? modelLabel(status, status.default_model) : 'Statistics only'
  const key = byok ? ' · your key' : status?.server_key_configured ? ' · demo key' : ''
  return (
    <button type="button" className="model-btn" onClick={() => openSettings(true)} aria-haspopup="dialog" aria-label={`Model: ${name}${key}`}>
      <i className="dot" style={{ background: byok || status?.server_key_configured ? 'var(--supported)' : 'var(--chalk-3)' }} />
      <span className="model-name">{name}</span><span className="model-short">Model</span>{key && <span className="model-key">{key}</span>}
    </button>
  )
}

export default function ModelSettings() {
  const { status, byok, setByok, settingsOpen, openSettings } = useModel()
  const [key, setKey] = useState('')
  const [model, setModel] = useState(byok?.model ?? status?.default_model ?? 'claude-haiku-5-5')
  const [test, setTest] = useState<{ ok: boolean; text: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const dialog = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!settingsOpen) { setKey(''); setTest(null); return }
    dialog.current?.querySelector<HTMLElement>('input, select, button')?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && openSettings(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [settingsOpen, openSettings])

  if (!settingsOpen) return null

  const runTest = async () => {
    setBusy(true); setTest(null)
    try {
      const r = await api.testKey({ key: key.trim(), model })
      setTest({ ok: true, text: `Connected. ${r.display_name} is available to this key.` })
    } catch (e) {
      setTest({ ok: false, text: e instanceof ApiError ? e.message : 'Test failed.' })
    } finally { setBusy(false) }
  }

  return (
    <div className="drawer-backdrop" onClick={() => openSettings(false)}>
      <div className="drawer" role="dialog" aria-modal="true" aria-labelledby="model-title" ref={dialog} onClick={(e) => e.stopPropagation()}>
        <div className="drawer-head">
          <h2 id="model-title">Model</h2>
          <button className="evidence-chip" onClick={() => openSettings(false)} aria-label="Close settings">Close</button>
        </div>

        <section className="drawer-section">
          <h3>Default</h3>
          {status?.server_key_configured ? (
            <p className="muted">
              {modelLabel(status, status.default_model)} through Anthropic, paid for by this demo. Results are cached, so repeat visits
              are instant and free. Shared budget left (estimate): <span className="mono">${status.budget.remaining_usd_estimate.toFixed(2)}</span>.
            </p>
          ) : (
            <p className="muted">No model key is configured on this server. The deterministic investigation still works, or add your own key.</p>
          )}
        </section>

        <section className="drawer-section">
          <h3>Use your own key <span className="faint">(optional)</span></h3>
          {byok ? (
            <>
              <p className="muted">Using your key <span className="mono">{maskKey(byok.key)}</span> with {modelLabel(status, byok.model)}.</p>
              <button className="btn ghost" onClick={() => { setByok(null); setTest(null) }}>Forget my key</button>
            </>
          ) : (
            <form onSubmit={(e) => { e.preventDefault(); if (key.trim()) { setByok({ key: key.trim(), model }); openSettings(false) } }}>
              <label className="field">
                <span>Provider</span>
                <select disabled value="anthropic"><option value="anthropic">Anthropic</option></select>
              </label>
              <label className="field">
                <span>API key</span>
                <input type="password" autoComplete="off" spellCheck={false} value={key} onChange={(e) => setKey(e.target.value)}
                  placeholder="sk-ant-…" aria-describedby="key-note" />
              </label>
              <label className="field">
                <span>Model</span>
                <select value={model} onChange={(e) => setModel(e.target.value)}>
                  {status?.models.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
                </select>
              </label>
              <div className="row" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
                <button type="button" className="btn ghost" disabled={!key.trim() || busy} onClick={runTest}>{busy ? 'Testing…' : 'Test connection'}</button>
                <button type="submit" className="btn" disabled={!key.trim()}>Use this key</button>
              </div>
              {test && <p className={test.ok ? 'ok-note' : 'error'} style={{ marginTop: 12 }}>{test.text}</p>}
            </form>
          )}
          <p id="key-note" className="faint" style={{ fontSize: 13, marginTop: 14 }}>
            Your key stays in this tab's memory. It is sent to this app's server with each run, used for that run only, and never stored,
            logged or cached. Reloading the page forgets it. Usage is billed to your Anthropic account. Test connection makes a free
            model lookup, not a generation.
          </p>
        </section>
      </div>
    </div>
  )
}
