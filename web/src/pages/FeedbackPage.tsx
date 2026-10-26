import { useEffect, useState } from 'react'
import { api, type FeedbackSummary } from '../api'

const ROLE_LABEL: Record<string, string> = { fan: 'Fans', analyst: 'Analysts', judge: 'Judges', developer: 'Developers', other: 'Others' }

/** What people think: public counts, ratings by role and the latest comments (never emails). */
export default function FeedbackPage() {
  const [data, setData] = useState<FeedbackSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { api.feedbackSummary().then(setData).catch((e) => setError(e.message)) }, [])

  if (error) return <div className="page"><p className="error" style={{ marginTop: 32 }}>{error}</p></div>
  if (!data) return <div className="page"><p className="faint" style={{ marginTop: 32 }}>Loading feedback…</p></div>
  const max = Math.max(1, ...Object.values(data.ratings))

  return (
    <div className="page feedback-page">
      <header className="pack-head" style={{ gridTemplateColumns: '1fr' }}>
        <div>
          <p className="eyebrow"><span className="eyebrow-live" aria-hidden />Feedback</p>
          <h1>What people think</h1>
          <p className="muted">Every note from fans, analysts, judges and developers, unedited. Use the Feedback button on any page to add yours.</p>
        </div>
      </header>
      {data.count === 0 ? <p className="muted">No feedback yet. Be the first: press <strong>Feedback</strong> at the bottom right.</p> : (
        <>
          <div className="fb-stats">
            <div className="stat-card"><span className="mono">Responses</span><b>{data.count}</b></div>
            <div className="stat-card"><span className="mono">Average rating</span><b>{data.average_rating?.toFixed(1)}<em> / 5</em></b></div>
            <div className="stat-card fb-dist">
              <span className="mono">Ratings</span>
              {[5, 4, 3, 2, 1].map((r) => (
                <div key={r} className="fb-bar"><span>{r}★</span><i style={{ width: `${(data.ratings[String(r)] / max) * 100}%` }} /><em>{data.ratings[String(r)]}</em></div>
              ))}
            </div>
          </div>
          <div className="fb-roles-grid">
            {Object.entries(data.by_role).filter(([, v]) => v.count).map(([role, v]) => (
              <span key={role} className="tag">{ROLE_LABEL[role]}: {v.count} · {v.average_rating?.toFixed(1)}★</span>
            ))}
          </div>
          <h2 className="section-kicker">Latest notes</h2>
          <ol className="fb-list">
            {data.latest.map((n, i) => (
              <li key={i} className="panel panel-pad">
                <div className="fb-meta mono">
                  <span>{'★'.repeat(n.rating)}<span className="faint">{'★'.repeat(5 - n.rating)}</span></span>
                  <span>{ROLE_LABEL[n.role]?.replace(/s$/, '') ?? n.role}</span>
                  {n.page && <span className="faint">{n.page}</span>}
                  <span className="faint">{n.created.slice(0, 16).replace('T', ' ')} UTC</span>
                </div>
                <p><strong>Improve:</strong> {n.improve}</p>
                {n.liked && <p className="muted"><strong>Worked:</strong> {n.liked}</p>}
              </li>
            ))}
          </ol>
        </>
      )}
      <p className="faint" style={{ fontSize: 12.5 }}>Stored in {data.storage === 'azure-table' ? 'Azure Table Storage' : 'a local file (development)'}. Emails are never shown.</p>
    </div>
  )
}
