import { useEffect, useState } from 'react'
import { Link, NavLink, Route, Routes } from 'react-router-dom'
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
  useEffect(() => { api.identity().then((i) => setNames(i.label)).catch(() => {}) }, [])
  return (
    <PrefsProvider>
    <ModelProvider>
      <header className="topbar">
        <Link to="/" className="wordmark">Beyond <em>the</em> Replay</Link>
         <span className="tag synthetic" style={{display: "none"}}>Simulated matches · {names}</span>
        <nav>
          <NavLink to="/" end>Matches</NavLink>
          <NavLink to="/studio"><span className="nav-full">Live Studio</span><span className="nav-short">Studio</span></NavLink>
          <NavLink to="/benchmark"><span className="nav-full">How accurate is it?</span><span className="nav-short">Accuracy</span></NavLink>
          <SoundButton />
          <ModelButton />
        </nav>
      </header>
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
