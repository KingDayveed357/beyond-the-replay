export type Lane = 'left' | 'center' | 'right'

export interface MatchEvent {
  id: string
  t: number
  team: string
  player_id: string
  type: 'pass' | 'carry' | 'dribble' | 'cross' | 'shot' | 'foul' | 'card' | 'tackle' | 'interception' | 'clearance'
  outcome: string
  x: number
  y: number
  end_x: number | null
  end_y: number | null
  opponent_id: string | null
  receiver_id: string | null
  possession_id: string | null
  under_pressure: boolean
  speed_kmh: number | null
}

export interface Player {
  team: string
  role: string
  name: string
}

export interface Goal {
  id: string
  team: string
  player_id: string
  minute: number
}

export interface MatchSummary {
  id: string
  role: 'hero' | 'showcase' | 'overload' | 'fatigue' | 'miss' | 'ambiguous'
  home: string
  away: string
  home_name: string
  away_name: string
  score: Record<string, number>
  incident_id: string
  incident_minute: number
  incident_team: string
  booking_id: string | null
  booking_minute: number | null
  goals: Goal[]
  synthetic: true
  metadata?: MatchMetadata
}

export interface MatchMetadata {
  competition: string
  season: string | null
  matchweek: number
  kickoff: string
  referee: string
  venue?: string
  attendance?: number
  colours?: Record<string, [string, string]>
  club_names?: Record<string, string>
  simulated: true
}

export interface Match extends MatchSummary {
  roster: Record<string, Player>
  events: MatchEvent[]
}

export type Verdict = 'upheld' | 'weakened' | 'refuted'
export type ClaimStatus = 'proposed' | Verdict

export interface Challenge {
  question: string
  finding: string
  verdict: Verdict
  evidence: string[]
  shifts_to: [string, string] | null
  source: 'test' | 'llm'
}

export interface Claim {
  id: string
  kind: 'FATIGUE' | 'STATIC' | 'OVERLOAD' | 'STYLE' | 'FOUL'
  target: string
  onset: number | null
  statement: string
  cited: string[]
  proposed_by: string
  raw_score: number
  score: number
  status: ClaimStatus
  challenges: Challenge[]
  verified: boolean
  verification_notes: string[]
  reasoning: string
  key: [string, string]
}

export interface Beat {
  label: string
  claim_id: string
  evidence: string[]
  fan: string
  analyst: string
}

export interface Explanation {
  confidence: 'strong' | 'likely' | 'uncertain' | 'none'
  headline: string
  beats: Beat[]
  ruled_out: { claim_id: string; status: Verdict; statement: string; reason: string; evidence: string[] }[]
  problems?: string[]
}

export interface TraceStep {
  agent: 'investigator' | 'sceptic' | 'verifier' | 'producer'
  action: string
  detail: string
  ms: number
}

export interface Investigation {
  id: string
  case_id: string
  incident_id: string
  mode: 'deterministic' | 'agents'
  sceptic: string
  claims: Claim[]
  trace: TraceStep[]
  explanation: Explanation
  ranking: [string, string][]
  elapsed_ms: number
  cached?: boolean
  created_at?: string
  model?: string
  model_label?: string
  key_source?: 'server' | 'byok'
  producer_source?: 'claude' | 'template'
  usage?: { calls: number; input_tokens: number; output_tokens: number; cost_usd_estimate: number; cost_basis: string }
  audit?: { citations_dropped: number; unverified_claims: number; sceptic_notes: string[]; producer_problems: string[] }
}

export interface ProviderStatus {
  server_key_configured: boolean
  default_model: string
  budget: { cap_usd: number; spent_usd_estimate: number; remaining_usd_estimate: number }
  models: { id: string; label: string }[]
  byok: { providers: string[]; storage: string }
}

export interface Effect {
  variable: string
  key: [string, string]
  mean: number
  se: number
}

export interface Truth {
  label: [string, string] | null
  effects: Effect[]
  planted_key: [string, string]
  but_for: boolean
  k: number
  factor_onset_minute: number
  evaluation_only: true
}

export interface TeamState {
  goals: number
  shots: number
  on_target: number
  xg: number
  possession: number
  pass_accuracy: number
  passes: number
  tackles: number
  interceptions: number
  fouls: number
  yellow_cards: number
  field_tilt: number
  pressured_share: number
  ppda: number | null
  control: number
}

export interface MinuteState {
  minute: number
  teams: Record<string, TeamState>
  momentum: number
  tempo_passes_per_min: number
  turnovers_per_min: number
  chaos: number
}

export interface Moment {
  t: number
  minute: number
  type: 'goal' | 'big_chance' | 'card' | 'momentum' | 'pass'
  team: string
  player_id: string | null
  assist_id?: string | null
  importance: number
  event_id?: string
  score?: string
  xg?: number
  headline: string
  why: string
}

export interface Cue {
  t_in: number
  t_out: number
  kind: 'name_tag' | 'speed' | 'lower_third' | 'goal'
  priority: number
  team: string
  player_id?: string | null
  player?: string
  metric?: string
  value?: number
  text: string
  subtext?: string
}

export interface PlayerSummary {
  name: string
  team: string
  role: string
  touches: number
  passes: number
  passes_completed: number
  pass_accuracy: number | null
  avg_pass_difficulty: number | null
  duels_won: number
  duels_lost: number
  tackles: number
  interceptions: number
  shots: number
  xg: number
  goals: number
  assists: number
  top_speed_kmh: number
  carry_m: number
}

export interface Timeline {
  events: (MatchEvent & { xg?: number; pass_difficulty?: number; pass_distance_m?: number })[]
  states: MinuteState[]
  moments: Moment[]
  cues: Cue[]
  players: Record<string, PlayerSummary>
  narrative: Narrative
}

export interface StoryBeat {
  t: number
  minute: number
  text: string
}

export interface Storyline {
  id: string
  kind: 'control' | 'flank' | 'duels' | 'discipline' | 'chase'
  team: string
  player_id: string | null
  opened_t: number
  closed_t?: number
  status: 'open' | 'resolved'
  title: string
  beats: StoryBeat[]
}

export interface Narrative {
  storylines: Storyline[]
  milestones: { key: string; t: number; minute: number; kind: string; text: string }[]
  summaries: { key: string; t: number; minute: number; phase: 'live' | 'ht' | 'ft'; text: string }[]
}

export interface Recap {
  headline: string
  paragraphs: string[]
  source: 'claude' | 'template'
  note?: string
  model?: string
}
