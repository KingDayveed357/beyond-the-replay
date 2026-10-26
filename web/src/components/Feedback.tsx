import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { api } from '../api'
import { play } from '../sound'

const ROLES = [['fan', 'Fan'], ['analyst', 'Analyst'], ['judge', 'Judge'], ['developer', 'Developer'], ['other', 'Other']] as const
const FACES = ['Poor', 'Meh', 'OK', 'Good', 'Excellent']

/** A floating "Feedback" button on every page, opening a short form. */
export default function Feedback() {
  const [open, setOpen] = useState(false)
  const { pathname } = useLocation()
  return (
    <>
      <button type="button" className="fb-fab" onClick={() => setOpen(true)} aria-haspopup="dialog">Feedback</button>
      {open && <FeedbackDialog page={pathname} onClose={() => setOpen(false)} />}
    </>
  )
}

function FeedbackDialog({ page, onClose }: { page: string; onClose: () => void }) {
  const [rating, setRating] = useState(0)
  const [role, setRole] = useState('')
  const [improve, setImprove] = useState('')
  const [liked, setLiked] = useState('')
  const [email, setEmail] = useState('')
  const [website, setWebsite] = useState('')
  const [state, setState] = useState<'idle' | 'sending' | 'sent'>('idle')
  const [error, setError] = useState<string | null>(null)
  const dialog = useRef<HTMLDivElement>(null)

  useEffect(() => {
    dialog.current?.querySelector<HTMLElement>('button, input, textarea')?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const ready = rating > 0 && role && improve.trim().length >= 3
  const send = async () => {
    setState('sending'); setError(null)
    try {
      await api.sendFeedback({ rating, role, improve, liked, email, page, website })
      setState('sent'); play('right')
    } catch (e) {
      setError((e as Error).message); setState('idle')
    }
  }

  return (
    <div className="drawer-backdrop fb-backdrop" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="fb-dialog" role="dialog" aria-modal="true" aria-labelledby="fb-title" ref={dialog}>
        <div className="drawer-head">
          <h2 id="fb-title">Be brutally honest</h2>
          <button className="copy-btn" onClick={onClose} aria-label="Close">Close</button>
        </div>
        {state === 'sent' ? (
          <div className="fb-thanks">
            <p className="big">Thank you. We read every note.</p>
            <p className="muted">See what everyone is saying on the <Link to="/feedback" onClick={onClose}>feedback page</Link>.</p>
          </div>
        ) : (
          <>
            <p className="muted" style={{ marginTop: 0 }}>Two minutes. What works, what doesn't, and the one thing we should fix first.</p>
            <fieldset className="fb-field">
              <legend>How good is Beyond the Replay?</legend>
              <div className="fb-stars" role="radiogroup">
                {FACES.map((label, i) => (
                  <button key={label} type="button" role="radio" aria-checked={rating === i + 1} className={rating > i ? 'on' : ''}
                    onClick={() => setRating(i + 1)} title={label}>
                    <span aria-hidden>★</span><span className="sr-only">{i + 1}: {label}</span>
                  </button>
                ))}
                <span className="faint">{rating ? FACES[rating - 1] : ''}</span>
              </div>
            </fieldset>
            <fieldset className="fb-field">
              <legend>I'm a…</legend>
              <div className="toggle fb-roles">
                {ROLES.map(([v, label]) => <button key={v} type="button" aria-pressed={role === v} onClick={() => setRole(v)}>{label}</button>)}
              </div>
            </fieldset>
            <label className="field"><span>The one thing we should improve</span>
              <textarea rows={3} maxLength={1500} value={improve} onChange={(e) => setImprove(e.target.value)}
                placeholder="Confusing words, missing features, anything that felt slow or wrong…" />
            </label>
            <label className="field"><span>What worked for you <em className="faint">(optional)</em></span>
              <textarea rows={2} maxLength={1000} value={liked} onChange={(e) => setLiked(e.target.value)} />
            </label>
            <label className="field"><span>Email, if you'd like a reply <em className="faint">(optional, never shown)</em></span>
              <input type="email" maxLength={200} value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
            <label className="fb-trap" aria-hidden>Website<input tabIndex={-1} autoComplete="off" value={website} onChange={(e) => setWebsite(e.target.value)} /></label>
            {error && <p className="error">{error}</p>}
            <button className="btn" disabled={!ready || state === 'sending'} onClick={send}>
              {state === 'sending' ? 'Sending…' : 'Send feedback'}
            </button>
            {!ready && <p className="faint" style={{ fontSize: 12.5, margin: '8px 0 0' }}>Pick a rating, who you are, and tell us one thing to improve.</p>}
          </>
        )}
      </div>
    </div>
  )
}
