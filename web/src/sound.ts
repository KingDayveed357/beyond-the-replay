/**
 * Match sounds, synthesised live with the Web Audio API: no recordings, no music, nothing copyrighted, so they are
 * safe for the demo video. Each key event has its own signature:
 *
 *   goal          crowd roar swelling over a rising horn chord
 *   big_chance    a short "ooh" from the crowd that falls away
 *   card          two sharp referee whistle blasts
 *   momentum      a low drum swell (a side taking control)
 *   kickoff       one long whistle      half_time  two whistles      full_time  three whistles
 *   storyline     a soft two-note chime (something is building)
 *   milestone     a single bright tick
 *   right / wrong the reveal: a rising arpeggio, or a gentle falling pair
 *
 * Browsers only allow sound after the viewer has interacted with the page, so the context is created lazily.
 */
export type SoundName =
  | 'goal' | 'big_chance' | 'card' | 'momentum' | 'pass' | 'kickoff' | 'half_time' | 'full_time'
  | 'storyline' | 'milestone' | 'right' | 'wrong' | 'tap'

let ctx: AudioContext | null = null
let master: GainNode | null = null
let enabled = true
const lastPlayed: Partial<Record<SoundName, number>> = {}

export function setSoundEnabled(on: boolean) {
  enabled = on
  if (!on && ctx) void ctx.suspend()
  if (on && ctx) void ctx.resume()
}

function audio(): AudioContext | null {
  if (!enabled || typeof window === 'undefined') return null
  const AC = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
  if (!AC) return null
  if (!ctx) {
    ctx = new AC()
    master = ctx.createGain()
    master.gain.value = 0.55
    master.connect(ctx.destination)
  }
  if (ctx.state === 'suspended') void ctx.resume()
  return ctx
}

function noise(a: AudioContext, seconds: number) {
  const buf = a.createBuffer(1, Math.ceil(a.sampleRate * seconds), a.sampleRate)
  const d = buf.getChannelData(0)
  for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1
  const src = a.createBufferSource()
  src.buffer = buf
  return src
}

function env(g: GainNode, t0: number, attack: number, peak: number, hold: number, release: number) {
  g.gain.setValueAtTime(0.0001, t0)
  g.gain.exponentialRampToValueAtTime(peak, t0 + attack)
  g.gain.setValueAtTime(peak, t0 + attack + hold)
  g.gain.exponentialRampToValueAtTime(0.0001, t0 + attack + hold + release)
}

function tone(a: AudioContext, freq: number, t0: number, dur: number, peak: number, type: OscillatorType = 'sine', glideTo?: number) {
  const o = a.createOscillator()
  const g = a.createGain()
  o.type = type
  o.frequency.setValueAtTime(freq, t0)
  if (glideTo) o.frequency.exponentialRampToValueAtTime(glideTo, t0 + dur)
  env(g, t0, Math.min(0.02, dur / 4), peak, dur * 0.4, dur * 0.6)
  o.connect(g).connect(master!)
  o.start(t0)
  o.stop(t0 + dur + 0.05)
}

/** A crowd: band-passed noise whose loudness and brightness follow the shape you give it. */
function crowd(a: AudioContext, t0: number, dur: number, peak: number, centre: number, rise: number) {
  const src = noise(a, dur + 0.1)
  const bp = a.createBiquadFilter()
  bp.type = 'bandpass'
  bp.Q.value = 0.7
  bp.frequency.setValueAtTime(centre * 0.7, t0)
  bp.frequency.exponentialRampToValueAtTime(centre * 1.3, t0 + rise)
  bp.frequency.exponentialRampToValueAtTime(centre * 0.8, t0 + dur)
  const g = a.createGain()
  env(g, t0, rise, peak, dur * 0.25, Math.max(0.2, dur - rise - dur * 0.25))
  src.connect(bp).connect(g).connect(master!)
  src.start(t0)
  src.stop(t0 + dur + 0.1)
}

/** A referee's pea whistle: a high tone warbled by a fast LFO. */
function whistle(a: AudioContext, t0: number, dur: number) {
  const o = a.createOscillator()
  const lfo = a.createOscillator()
  const depth = a.createGain()
  const g = a.createGain()
  o.type = 'sine'
  o.frequency.value = 2900
  lfo.frequency.value = 38
  depth.gain.value = 120
  lfo.connect(depth).connect(o.frequency)
  env(g, t0, 0.015, 0.22, dur - 0.08, 0.06)
  o.connect(g).connect(master!)
  o.start(t0); lfo.start(t0)
  o.stop(t0 + dur + 0.05); lfo.stop(t0 + dur + 0.05)
}

function drum(a: AudioContext, t0: number, peak: number) {
  tone(a, 110, t0, 0.35, peak, 'sine', 48)
  const n = noise(a, 0.12)
  const lp = a.createBiquadFilter()
  lp.type = 'lowpass'
  lp.frequency.value = 600
  const g = a.createGain()
  env(g, t0, 0.005, peak * 0.4, 0.01, 0.1)
  n.connect(lp).connect(g).connect(master!)
  n.start(t0)
}

const QUIET_AFTER_GOAL = new Set<SoundName>(['milestone', 'storyline', 'pass', 'momentum'])
const MIN_GAP_MS: Partial<Record<SoundName, number>> = { pass: 4000, milestone: 1500, storyline: 2500, momentum: 3000 }

export function play(name: SoundName) {
  const now = Date.now()
  if ((lastPlayed[name] ?? 0) + (MIN_GAP_MS[name] ?? 250) > now) return  // never machine-gun the viewer
  if (QUIET_AFTER_GOAL.has(name) && now - (lastPlayed.goal ?? 0) < 3500) return  // let the goal breathe
  lastPlayed[name] = now
  window.dispatchEvent(new CustomEvent('btr:sound', { detail: name }))
  const a = audio()
  if (!a || !master) return
  const t = a.currentTime + 0.02
  switch (name) {
    case 'goal':
      crowd(a, t, 4.2, 0.9, 900, 0.5)
      crowd(a, t + 0.1, 3.8, 0.5, 2200, 0.7)
      ;[261.6, 329.6, 392, 523.3].forEach((f, i) => tone(a, f, t + 0.15 + i * 0.12, 1.4, 0.12, 'sawtooth'))
      break
    case 'big_chance':
      crowd(a, t, 1.6, 0.55, 700, 0.35)
      tone(a, 330, t + 0.05, 0.9, 0.05, 'triangle', 220)
      break
    case 'card':
      whistle(a, t, 0.22)
      whistle(a, t + 0.32, 0.22)
      break
    case 'momentum':
      drum(a, t, 0.5); drum(a, t + 0.28, 0.6); drum(a, t + 0.5, 0.75)
      break
    case 'pass':
      tone(a, 880, t, 0.18, 0.06, 'triangle', 1320)
      break
    case 'kickoff':
      whistle(a, t, 0.9)
      break
    case 'half_time':
      whistle(a, t, 0.35); whistle(a, t + 0.5, 0.7)
      break
    case 'full_time':
      whistle(a, t, 0.35); whistle(a, t + 0.5, 0.35); whistle(a, t + 1.0, 0.9)
      crowd(a, t + 1.1, 2.6, 0.4, 900, 0.4)
      break
    case 'storyline':
      tone(a, 659.3, t, 0.35, 0.08); tone(a, 987.8, t + 0.14, 0.5, 0.07)
      break
    case 'milestone':
      tone(a, 1318.5, t, 0.2, 0.06, 'triangle')
      break
    case 'right':
      ;[523.3, 659.3, 784, 1046.5].forEach((f, i) => tone(a, f, t + i * 0.09, 0.45, 0.1, 'triangle'))
      crowd(a, t + 0.1, 1.8, 0.35, 1200, 0.3)
      break
    case 'wrong':
      tone(a, 392, t, 0.35, 0.09, 'triangle'); tone(a, 311.1, t + 0.22, 0.6, 0.09, 'triangle')
      break
    case 'tap':
      tone(a, 1046.5, t, 0.08, 0.05, 'triangle')
      break
  }
}

/** The sound for a key moment of the match, by moment type. */
export const momentSound = (type: string): SoundName | null =>
  (({ goal: 'goal', big_chance: 'big_chance', card: 'card', momentum: 'momentum', pass: 'pass' }) as Record<string, SoundName>)[type] ?? null
