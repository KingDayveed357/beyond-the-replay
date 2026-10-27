import { describeEvent, minute } from '../format'
import type { Match } from '../types'
import { useWidth } from '../useWidth'

interface Props {
  match: Match
  scoringTeam: string
  incidentId: string
  evidenceIds?: Set<string>
  focusId?: string | null
  onsetMinute?: number | null
  onSelect?: (id: string) => void
}

const END = 92 * 60

export default function Timeline({ match, scoringTeam, incidentId, evidenceIds, focusId, onsetMinute, onSelect }: Props) {
  // 1000 units wide on desktop; on a narrow panel the drawing gets fewer units so labels and marks stay legible.
  const [ref, px] = useWidth<SVGSVGElement>()
  const U = px && px < 640 ? Math.round(px * 1.25) : 1000
  const X = (t: number) => (Math.min(t, END) / END) * U
  const shots = match.events.filter((e) => e.type === 'shot')
  const cards = match.events.filter((e) => e.type === 'card')
  const evidence = evidenceIds ? match.events.filter((e) => evidenceIds.has(e.id)) : []
  const incident = match.events.find((e) => e.id === incidentId)
  const row = (team: string) => (team === scoringTeam ? 22 : 62)

  return (
    <svg ref={ref} viewBox={`0 0 ${U} 86`} role="group" aria-label="Match timeline">
      <line x1={0} y1={42} x2={U} y2={42} stroke="var(--rule)" />
      {[0, 15, 30, 45, 60, 75, 90].map((m) => (
        <g key={m}>
          <line x1={X(m * 60)} y1={38} x2={X(m * 60)} y2={46} stroke="var(--rule)" />
          <text x={X(m * 60) + 3} y={84} fontSize={10} fill="var(--chalk-3)" fontFamily="var(--mono)">{m}'</text>
        </g>
      ))}
      {onsetMinute != null && (
        <g>
          <rect x={X((onsetMinute - 1) * 60)} y={4} width={U - X((onsetMinute - 1) * 60)} height={72} fill="rgba(143,227,176,0.05)" />
          <line x1={X((onsetMinute - 1) * 60)} y1={4} x2={X((onsetMinute - 1) * 60)} y2={76} stroke="var(--supported)" strokeDasharray="3 3" />
          <text x={X((onsetMinute - 1) * 60) + 4} y={12} fontSize={10} fill="var(--supported)" fontFamily="var(--mono)">change {onsetMinute}'</text>
        </g>
      )}
      {incident && <line x1={X(incident.t)} y1={2} x2={X(incident.t)} y2={78} stroke="var(--chalk)" strokeWidth={1.5} />}
      {evidence.map((e) => (
        <circle key={`ev${e.id}`} cx={X(e.t)} cy={42} r={focusId === e.id ? 5 : 3} fill="var(--supported)"
          style={{ cursor: onSelect ? 'pointer' : undefined }} onClick={() => onSelect?.(e.id)}>
          <title>{`${minute(e.t)} ${describeEvent(match, e)}`}</title>
        </circle>
      ))}
      {cards.map((e) => (
        <rect key={e.id} x={X(e.t) - 3} y={row(e.team) - 6} width={6} height={10} rx={1} fill="none" stroke="var(--chalk-2)"
          style={{ cursor: onSelect ? 'pointer' : undefined }} onClick={() => onSelect?.(e.id)}>
          <title>{`${minute(e.t)} ${describeEvent(match, e)}`}</title>
        </rect>
      ))}
      {shots.map((e) => {
        const goal = e.outcome === 'goal'
        const solid = e.team === scoringTeam
        return (
          <circle key={e.id} cx={X(e.t)} cy={row(e.team)} r={goal ? 6 : 2.4}
            fill={solid ? 'var(--chalk)' : 'var(--ink-2)'} stroke="var(--chalk)" strokeWidth={solid ? 0 : 1.2}
            opacity={goal ? 1 : 0.5} style={{ cursor: onSelect ? 'pointer' : undefined }} onClick={() => onSelect?.(e.id)}>
            <title>{`${minute(e.t)} ${describeEvent(match, e)}`}</title>
          </circle>
        )
      })}
    </svg>
  )
}
