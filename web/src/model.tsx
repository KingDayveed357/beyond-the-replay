import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, type Byok } from './api'
import type { ProviderStatus } from './types'

interface ModelState {
  status: ProviderStatus | null
  byok: Byok | null
  setByok: (b: Byok | null) => void
  settingsOpen: boolean
  openSettings: (open: boolean) => void
}

const Ctx = createContext<ModelState | null>(null)

/** BYOK lives only in this component's memory: no localStorage, no cookies, gone on reload. */
export function ModelProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<ProviderStatus | null>(null)
  const [byok, setByok] = useState<Byok | null>(null)
  const [settingsOpen, openSettings] = useState(false)
  useEffect(() => { api.provider().then(setStatus).catch(() => setStatus(null)) }, [])
  return <Ctx.Provider value={{ status, byok, setByok, settingsOpen, openSettings }}>{children}</Ctx.Provider>
}

export function useModel(): ModelState {
  const v = useContext(Ctx)
  if (!v) throw new Error('useModel outside ModelProvider')
  return v
}

export const maskKey = (key: string) => (key.length > 12 ? `${key.slice(0, 7)}…${key.slice(-4)}` : '••••')

export function modelLabel(status: ProviderStatus | null, id: string | undefined) {
  return status?.models.find((m) => m.id === id)?.label ?? id ?? 'Claude'
}
