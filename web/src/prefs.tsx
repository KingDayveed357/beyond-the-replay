import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { setSoundEnabled } from './sound'

export type Lang = 'en' | 'es' | 'fr' | 'pt' | 'ar'
export type Metric = 'xg' | 'possession' | 'pass_accuracy' | 'control' | 'field_tilt'

export interface Prefs {
  lang: Lang
  club: string | null      // favourite club code, e.g. "LIV"
  analyst: boolean
  metric: Metric | null
  spoilerFree: boolean     // hide results until the viewer watches
  sound: boolean           // synthesised match sounds
}

const KEY = 'btr.prefs.v1'
const DEFAULTS: Prefs = { lang: 'en', club: null, analyst: false, metric: null, spoilerFree: false, sound: true }

/** Viewer preferences are a convenience, so they live in localStorage and never block rendering. */
function load(): Prefs {
  try {
    return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(KEY) ?? '{}') }
  } catch {
    return DEFAULTS
  }
}

const Ctx = createContext<{ prefs: Prefs; set: (p: Partial<Prefs>) => void } | null>(null)

export function PrefsProvider({ children }: { children: ReactNode }) {
  const [prefs, setPrefs] = useState<Prefs>(load)
  useEffect(() => {
    try { localStorage.setItem(KEY, JSON.stringify(prefs)) } catch { /* private mode: keep in memory */ }
    document.documentElement.lang = prefs.lang
    setSoundEnabled(prefs.sound)
  }, [prefs])
  return <Ctx.Provider value={{ prefs, set: (p) => setPrefs((x) => ({ ...x, ...p })) }}>{children}</Ctx.Provider>
}

export function usePrefs() {
  const v = useContext(Ctx)
  if (!v) throw new Error('usePrefs outside PrefsProvider')
  return v
}
