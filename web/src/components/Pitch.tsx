import { useEffect, useMemo, useRef, useState } from 'react'
import { describeEvent, minute, playerName } from '../format'
import type { Match, MatchEvent } from '../types'
import { useWidth } from '../useWidth'

const W = 105
const H = 68
const sy = (y: number) => H - y // data y grows "up the page" for the home side; SVG grows down

interface Props {
  match: Match
  path: MatchEvent[]          // the move being replayed, in order
  evidence?: MatchEvent[]     // events cited by the selected claim
  focus?: MatchEvent | null
  scoringTeam: string
  animate?: boolean
  label?: boolean | 'scorer'  // true: key moments; 'scorer': only the player who finishes the move
  crop?: boolean              // zoom to the attacking move instead of the whole pitch
  accent?: string             // colour for the scoring side's markers
}

function Markings() {
  const s = { fill: 'none', stroke: 'var(--pitch-line)', strokeWidth: 0.35 }
  const box = (x: number, w: number, y: number, h: number) => <rect x={x} y={y} width={w} height={h} {...s} />
  return (
    <g>
      <rect x={0} y={0} width={W} height={H} {...s} />
      <line x1={W / 2} y1={0} x2={W / 2} y2={H} {...s} />
      <circle cx={W / 2} cy={H / 2} r={9.15} {...s} />
      <circle cx={W / 2} cy={H / 2} r={0.4} fill="var(--pitch-line)" />
      {box(0, 16.5, 13.84, 40.32)}
      {box(W - 16.5, 16.5, 13.84, 40.32)}
      {box(0, 5.5, 24.84, 18.32)}
      {box(W - 5.5, 5.5, 24.84, 18.32)}
      <path d={`M16.5 26.7 A9.15 9.15 0 0 1 16.5 41.3`} {...s} />
      <path d={`M${W - 16.5} 26.7 A9.15 9.15 0 0 0 ${W - 16.5} 41.3`} {...s} />
      <rect x={-1.6} y={30.34} width={1.6} height={7.32} {...s} />
      <rect x={W} y={30.34} width={1.6} height={7.32} {...s} />
      {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((i) => (
        <rect key={i} x={(i - 1) * (W / 9)} y={0} width={W / 9} height={H} fill={i % 2 ? 'rgba(255,255,255,0.012)' : 'transparent'} />
      ))}
    </g>
  )
}

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(() => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false)
  useEffect(() => {
    const mq = window.matchMedia?.('(prefers-reduced-motion: reduce)')
    const on = () => setReduced(mq.matches)
    mq?.addEventListener('change', on)
    return () => mq?.removeEventListener('change', on)
  }, [])
  return reduced
}

/** Points the ball actually travels through: each event's start, then its end where recorded. */
function ballPoints(path: MatchEvent[], fx: (x: number) => number, fy: (y: number) => number): [number, number][] {
  const pts: [number, number][] = []
  for (const e of path) {
    pts.push([fx(e.x), fy(e.y)])
    if (e.end_x !== null && e.end_y !== null && e.outcome !== 'fail') pts.push([fx(e.end_x), fy(e.end_y)])
  }
  return pts
}

function useBall(points: [number, number][], run: boolean, duration = 3600) {
  const [pos, setPos] = useState<[number, number] | null>(null)
  const raf = useRef(0)
  useEffect(() => {
    if (!run || points.length < 2) {
      setPos(points.length ? points[points.length - 1] : null)
      return
    }
    const lengths = points.slice(1).map((p, i) => Math.hypot(p[0] - points[i][0], p[1] - points[i][1]))
    const total = lengths.reduce((a, b) => a + b, 0) || 1
    let start = 0
    const tick = (now: number) => {
      if (!start) start = now
      let d = Math.min((now - start) / duration, 1) * total
      let i = 0
      while (i < lengths.length - 1 && d > lengths[i]) d -= lengths[i++]
      const f = lengths[i] ? Math.min(d / lengths[i], 1) : 1
      setPos([points[i][0] + (points[i + 1][0] - points[i][0]) * f, points[i][1] + (points[i + 1][1] - points[i][1]) * f])
      if (now - start < duration) raf.current = requestAnimationFrame(tick)
    }
    raf.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf.current)
  }, [points, run, duration])
  return pos
}

export default function Pitch({ match, path, evidence = [], focus, scoringTeam, animate = true, label = true, crop = false, accent }: Props) {
  const reduced = usePrefersReducedMotion()
  // The data has the home side attacking towards +x. Like a broadcast, always show the
  // scoring team attacking left to right: a 180-degree view rotation, not a data change.
  const flip = scoringTeam !== match.home
  const fx = (x: number) => (flip ? W - x : x)
  const fy = (y: number) => (flip ? y : sy(y))
  const points = useMemo(() => ballPoints(path, fx, fy), [path, flip]) // eslint-disable-line react-hooks/exhaustive-deps
  const ball = useBall(points, animate && !reduced)
  const solid = (team: string) => team === scoringTeam
  const [ref, px] = useWidth<SVGSVGElement>()
  // Crop: frame the move and the goal it was aimed at, keeping the pitch's proportions readable.
  let view = '-3 -3 111 74'
  if (crop && path.length) {
    const xs = path.flatMap((e) => [fx(e.x), fx(e.end_x ?? e.x)])
    const ys = path.flatMap((e) => [fy(e.y), fy(e.end_y ?? e.y)]).concat([H / 2 - 6, H / 2 + 6])  // keep the goal mouth in frame
    const aspect = 1.6
    const right = W + 3
    let h = Math.max(Math.max(...ys) - Math.min(...ys) + 14, (right - Math.min(...xs) + 8) / aspect, 34)
    h = Math.min(h, 74)
    const w = Math.min(h * aspect, 111)
    const left = Math.max(-3, right - w)
    const y0 = Math.min(Math.max(-3, (Math.min(...ys) + Math.max(...ys)) / 2 - h / 2), 71 - h)
    view = `${left.toFixed(1)} ${y0.toFixed(1)} ${(right - left).toFixed(1)} ${h.toFixed(1)}`
  }
  // Text scale: labels never render smaller than about 10 px, so names stay readable on a phone-sized pitch.
  const k = px ? Math.max(1, (10 * Number(view.split(' ')[2])) / px / 2.1) : 1
  const keyIdx = new Set(label === 'scorer' ? [path.length - 1] : [0, path.length - 1])
  if (label === true) path.forEach((e, i) => e.type === 'dribble' && e.outcome === 'success' && keyIdx.add(i))
  // Place labels latest-first and skip any that would collide with one already placed.
  const placed: { x: number; y: number }[] = []
  const labelAt = new Map<number, { x: number; y: number; anchor: 'start' | 'middle' | 'end' }>()
  for (let i = path.length - 1; i >= 0; i--) {
    if (!keyIdx.has(i)) continue
    const x = fx(path[i].x), y = fy(path[i].y)
    if (placed.some((q) => Math.abs(q.x - x) < 14 * k && Math.abs(q.y - y) < 4.5 * k)) continue
    placed.push({ x, y })
    labelAt.set(i, { x, y: y < 6 * k ? y + 2.5 + 2.1 * k : y - 1.5 - 0.9 * k, anchor: x > W - 12 * k ? 'end' : x < 12 * k ? 'start' : 'middle' })
  }
  const focusText = focus ? `${minute(focus.t)} ${describeEvent(match, focus)}` : ''
  const focusSize = 2.2 * Math.min(k, 1.35)
  const focusHalf = Math.min(focusText.length * focusSize * 0.27, W / 2)  // rough half-width of the line, to keep it on the pitch
  const team = accent ?? 'var(--chalk)'

  const summary = path.map((e) => `${minute(e.t)} ${describeEvent(match, e)}`).join('; ')

  return (
    <svg ref={ref} viewBox={view} role="img" aria-label={`Pitch. ${summary}`} style={{ display: 'block', width: '100%' }}>
      <defs>
        <marker id="arrow" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="4" markerHeight="4" orient="auto">
          <path d="M0 0 L6 3 L0 6 z" fill="var(--chalk)" />
        </marker>
      </defs>
      <rect x={-3} y={-3} width={111} height={74} fill="var(--pitch)" />
      <Markings />

      {evidence.map((e) => (
        <g key={`ev-${e.id}`} opacity={focus && focus.id !== e.id ? 0.55 : 1}>
          <circle cx={fx(e.x)} cy={fy(e.y)} r={1.5} fill="none" stroke="var(--supported)" strokeWidth={0.45} />
          <circle cx={fx(e.x)} cy={fy(e.y)} r={0.45} fill="var(--supported)" />
          <title>{`${e.id} · ${minute(e.t)} · ${describeEvent(match, e)}`}</title>
        </g>
      ))}

      {path.map((e, i) => {
        const x = fx(e.x), y = fy(e.y)
        const hasEnd = e.end_x !== null && e.end_y !== null
        const ex = hasEnd ? fx(e.end_x!) : x, ey = hasEnd ? fy(e.end_y!) : y
        const dashed = e.type === 'carry' || e.type === 'dribble'
        return (
          <g key={e.id}>
            {hasEnd && (
              <line x1={x} y1={y} x2={ex} y2={ey} stroke="var(--chalk)" strokeOpacity={e.type === 'shot' ? 0.9 : 0.55}
                strokeWidth={e.type === 'shot' ? 0.5 : 0.35} strokeDasharray={dashed ? '1 0.8' : undefined}
                markerEnd={e.type === 'pass' || e.type === 'cross' || e.type === 'shot' ? 'url(#arrow)' : undefined} />
            )}
            {e.opponent_id && e.type === 'dribble' && (
              <circle cx={x + (hasEnd ? (ex - x) * 0.35 : 1.5)} cy={y + (hasEnd ? (ey - y) * 0.35 : 0)} r={1.25}
                fill="var(--pitch)" stroke="var(--chalk-2)" strokeWidth={0.4} />
            )}
            <circle cx={x} cy={y} r={1.25} fill={solid(e.team) ? team : 'var(--pitch)'}
              stroke={solid(e.team) && !accent ? 'var(--ink)' : 'var(--chalk)'} strokeWidth={solid(e.team) ? (accent ? 0.4 : 0.25) : 0.4} />
            {label && labelAt.has(i) && (
              <text x={labelAt.get(i)!.x} y={labelAt.get(i)!.y} textAnchor={labelAt.get(i)!.anchor} fontSize={2.1 * k}
                fill="var(--chalk)" fontFamily="var(--sans)" fontWeight={600} paintOrder="stroke" stroke="var(--pitch)" strokeWidth={0.6 * k}>
                {playerName(match, e.player_id)}
              </text>
            )}
          </g>
        )
      })}

      {focus && (
        <g>
          <circle cx={fx(focus.x)} cy={fy(focus.y)} r={2.8} fill="none" stroke="var(--supported)" strokeWidth={0.5} />
          <text x={Math.min(Math.max(fx(focus.x), Math.max(14, focusHalf)), W - Math.max(14, focusHalf))}
            y={fy(focus.y) + (fy(focus.y) > 60 ? -2 - focusSize : 3.4 + focusSize)} textAnchor="middle"
            fontSize={focusSize} fill="var(--chalk)" fontFamily="var(--sans)" paintOrder="stroke" stroke="var(--pitch)" strokeWidth={0.5}>
            {focusText}
          </text>
        </g>
      )}

      {ball && <circle cx={ball[0]} cy={ball[1]} r={0.75} fill="var(--supported)" stroke="var(--ink)" strokeWidth={0.2} />}
    </svg>
  )
}
