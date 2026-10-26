import type { Claim, Match, MatchEvent } from './types'

export const ROLE_NAMES: Record<string, string> = {
  GK: 'goalkeeper', RB: 'right-back', LB: 'left-back', CB1: 'centre-back', CB2: 'centre-back',
  DM: 'defensive midfielder', CMR: 'right-sided midfielder', CML: 'left-sided midfielder',
  RW: 'right winger', ST: 'striker', LW: 'left winger',
}

export const KIND_LABEL: Record<Claim['kind'], string> = {
  FATIGUE: 'Defender tired',
  STATIC: 'Outmatched all game',
  OVERLOAD: 'Outnumbered on a flank',
  STYLE: 'Favourite flank',
  FOUL: 'The booking',
}

export const STATUS_LABEL: Record<string, string> = {
  proposed: 'Unchallenged',
  upheld: 'Holds up',
  weakened: 'Doubtful',
  refuted: 'Ruled out',
}

export const minute = (t: number) => `${Math.floor(t / 60) + 1}'`

export const ordinal = (n: number) => {
  const suffix = n % 100 >= 11 && n % 100 <= 13 ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' } as Record<number, string>)[n % 10] ?? 'th'
  return `${n}${suffix}`
}

export const clubName = (m: Match, team: string) => (team === m.home ? m.home_name : m.away_name)

export const playerName = (m: Match, id: string | null) => (id && m.roster[id] ? m.roster[id].name : id ?? '')

export const playerLong = (m: Match, id: string) =>
  m.roster[id] ? `${m.roster[id].name}, ${clubName(m, m.roster[id].team)} ${ROLE_NAMES[m.roster[id].role]}` : id

export const eventIndex = (m: Match) => new Map(m.events.map((e) => [e.id, e]))

const VERB: Record<MatchEvent['type'], (e: MatchEvent, m: Match) => string> = {
  pass: (e, m) => (e.outcome === 'success' ? `passes to ${playerName(m, e.receiver_id)}` : `pass cut out by ${playerName(m, e.opponent_id)}`),
  carry: (e) => (e.outcome === 'success' ? 'carries forward' : 'loses the ball'),
  dribble: (e, m) => (e.outcome === 'success' ? `beats ${playerName(m, e.opponent_id)}` : `stopped by ${playerName(m, e.opponent_id)}`),
  cross: (e, m) => (e.outcome === 'success' ? `crosses to ${playerName(m, e.receiver_id)}` : 'cross cleared'),
  shot: (e) => (e.outcome === 'goal' ? 'scores' : e.outcome === 'saved' ? 'shot saved' : 'shot off target'),
  foul: (e, m) => `fouls ${playerName(m, e.opponent_id)}`,
  card: () => 'is booked',
  tackle: (e, m) => `tackles ${playerName(m, e.opponent_id)}`,
  interception: (e, m) => `intercepts ${playerName(m, e.opponent_id)}'s pass`,
  clearance: () => 'clears the cross',
}

export const describeEvent = (m: Match, e: MatchEvent) => `${playerName(m, e.player_id)} ${VERB[e.type](e, m)}`
