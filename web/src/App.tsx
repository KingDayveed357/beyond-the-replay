import { useEffect, useState } from 'react'
import { Link, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { api } from './api'
import ModelSettings, { ModelButton } from './components/ModelSettings'
import { ModelProvider } from './model'
import { PrefsProvider, usePrefs } from './prefs'
import { play } from './sound'
import Benchmark from './pages/Benchmark'
import Landing from './pages/Landing'
import Feedback from './components/Feedback'
import FeedbackPage from './pages/FeedbackPage'
import Pack from './pages/Pack'
import Studio from './pages/Studio'
import MatchCentre from './pages/MatchCentre'
import Workspace from './pages/Workspace'

function SoundButton() {
  const { prefs, set } = usePrefs()
  return (
    <button type="button" className="sound-btn" aria-pressed={prefs.sound} title={prefs.sound ? 'Match sounds on' : 'Match sounds off'}
      aria-label={prefs.sound ? 'Turn match sounds off' : 'Turn match sounds on'}
      onClick={() => { const on = !prefs.sound; set({ sound: on }); if (on) setTimeout(() => play('tap'), 30) }}>
      <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 10v4h4l5 4V6L8 10H4z" fill="currentColor" stroke="none" />
        {prefs.sound ? <><path d="M16 9.5a3.5 3.5 0 0 1 0 5" /><path d="M18.5 7a7 7 0 0 1 0 10" /></> : <path d="M16.5 9.5l5 5m0-5l-5 5" />}
      </svg>
    </button>
  )
}

export default function App() {
  const [names, setNames] = useState('Fictional clubs and players')
  // The phone menu remembers the page it was opened on, so moving to another page closes it.
  const { pathname } = useLocation()
  const [menuAt, setMenuAt] = useState<string | null>(null)
  const menu = menuAt === pathname
  const setMenu = (open: boolean | ((m: boolean) => boolean)) =>
    setMenuAt((typeof open === 'function' ? open(menu) : open) ? pathname : null)
  useEffect(() => { api.identity().then((i) => setNames(i.label)).catch(() => {}) }, [])
  useEffect(() => {
    if (!menu) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setMenuAt(null) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [menu])
  return (
    <PrefsProvider>
    <ModelProvider>
      <header className="topbar">
        <Link to="/" className="wordmark">Beyond <em>the</em> Replay</Link>
         <span className="tag synthetic" style={{display: "none"}}>Simulated matches · {names}</span>
        <nav>
          {/* On phones these links fold into the menu button's panel; the sound and model buttons stay in the bar. */}
          <div className="nav-links" id="site-nav" data-open={menu}>
            <NavLink to="/" end>Matches</NavLink>
            <NavLink to="/studio">Live Studio</NavLink>
            <NavLink to="/benchmark">How accurate is it?</NavLink>
          </div>
          <SoundButton />
          <ModelButton />
          <button type="button" className="menu-btn" aria-expanded={menu} aria-controls="site-nav"
            aria-label={menu ? 'Close menu' : 'Open menu'} onClick={() => setMenu((m) => !m)}>
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
              {menu ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
            </svg>
          </button>
        </nav>
      </header>
      {menu && <div className="nav-scrim" onClick={() => setMenu(false)} aria-hidden />}
      <main>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/live/:id" element={<MatchCentre />} />
          <Route path="/match/:id" element={<Workspace />} />
          <Route path="/benchmark" element={<Benchmark />} />
          <Route path="/pack/:id" element={<Pack />} />
          <Route path="/feedback" element={<FeedbackPage />} />
          <Route path="/studio" element={<Studio />} />
          <Route path="/studio/:id" element={<Studio />} />
          <Route path="/feed/:id" element={<Studio />} />
          <Route path="*" element={<div className="page"><p style={{ marginTop: 32 }}>Not found. <Link to="/">Back to the investigation</Link></p></div>} />
        </Routes>
      </main>
      <ModelSettings />
      <Feedback />
    </ModelProvider>
    </PrefsProvider>
  )
}
