"""Match engine (v2).

A deliberately small, seeded, possession-based event generator. It is a scientific
instrument, not a football simulator: it exists so hidden causes can be planted,
removed, and measured.

Three kinds of state are kept apart:
  * MatchConfig - hidden simulation state (ratings, lane preferences, planted factor, decoy)
  * events      - what happened; observe.py decides which fields investigators may see
  * truth.py    - evaluation truth from paired re-runs, never exposed to investigators

Every possession draws from its own RNG stream, keyed by (seed, possession index), so two
runs that differ only in one hidden variable share their randomness (common random numbers).

Identities come from an identity pack: by default the Premier League 2024/25 pack built by
scripts/build_league.py (real clubs and players, simulated matches). Set BTR_IDENTITY=fictional to
use the original fictional clubs instead.
"""
from __future__ import annotations

import json
import math
import os
import random
from dataclasses import dataclass, field
from pathlib import Path

ENGINE_VERSION = "v2.1"  # bump whenever generated matches change; cached match sets are keyed by it
PITCH_X, PITCH_Y = 105.0, 68.0
MATCH_END = 90 * 60

ROLES = ("GK", "RB", "CB1", "CB2", "LB", "DM", "CMR", "CML", "RW", "ST", "LW")
OUTFIELD = ROLES[1:]
LANES = ("left", "center", "right")  # always from the attacking team's point of view
WIDE_LANES = ("left", "right")

# Roles that normally receive the ball in each lane. Public: it follows from the line-up.
LANE_POOL = {
    "left": ("LW", "LB", "CML"),
    "center": ("ST", "DM", "CMR", "CML"),
    "right": ("RW", "RB", "CMR"),
}
# The defending team's players who face each attacking lane.
LANE_DEFENDERS = {"left": ("RB",), "center": ("CB1", "CB2", "DM"), "right": ("LB",)}
FULL_BACK_FOR_LANE = {"left": "RB", "right": "LB"}
# The midfielder an overload pulls across to the flank.
OVERLOAD_RUNNER = {"left": "CMR", "right": "CML"}
LANE_Y = {"left": 56.0, "center": 34.0, "right": 12.0}  # for a team attacking towards +x

FICTIONAL_CLUBS = {
    "NOR": "Northbridge", "ASH": "Ashford", "KIN": "Kingsmere",
    "HAL": "Halden Town", "RED": "Redwater", "CAL": "Calder Vale",
}
LEAGUE_FILE = Path(__file__).resolve().parent.parent / "data" / "league" / "pl_2024_25.json"


def _load_league() -> dict | None:
    if os.environ.get("BTR_IDENTITY", "pl") == "fictional" or not LEAGUE_FILE.exists():
        return None
    return json.loads(LEAGUE_FILE.read_text(encoding="utf-8"))


LEAGUE = _load_league()
CLUBS = {code: c["short"] for code, c in LEAGUE["clubs"].items()} if LEAGUE else FICTIONAL_CLUBS
REFEREES = ("Michael Oliver", "Anthony Taylor", "Simon Hooper", "Chris Kavanagh", "Jarred Gillett", "Craig Pawson",
            "Stuart Attwell", "Robert Jones", "Peter Bankes", "Samuel Barrott", "Darren England", "Tony Harrington")
KICKOFFS = ("Sat 12:30", "Sat 15:00", "Sat 15:00", "Sat 17:30", "Sun 14:00", "Sun 16:30", "Mon 20:00")

SURNAMES = (
    "Okafor", "Lindqvist", "Marlowe", "Adeyemi", "Kerrigan", "Valdés", "Thorne", "Mbeki",
    "Castell", "Oyelaran", "Hartigan", "Novak", "Ferreira", "Quist", "Abara", "Delacroix",
    "Whitlock", "Sørensen", "Iheanacho", "Pellegrini", "Rowntree", "Koenig", "Achterberg",
    "Balogun", "Strand", "Moreau", "Ekwueme", "Haldane", "Fontaine", "Rask", "Nwosu", "Calloway",
    "Brandt", "Osei", "Lennox", "Vidal", "Kowalczyk", "Ashby", "Duarte", "Hollis", "Ogbu",
    "Renshaw", "Ilori", "Vance", "Sauer", "Achebe", "Morrow", "Takács", "Eze", "Garnier",
)

# Mechanism strengths. Phase 0 tunes these on development seeds only.
BASE_SUCCESS = {"pass": 0.89, "carry": 0.92, "dribble": 0.50, "cross": 0.30}
EDGE_WEIGHT = 1.0
FATIGUE_DROP = 0.28
FATIGUE_RAMP = 600
OVERLOAD_PASS_BONUS = 0.30
OVERLOAD_LANE_WEIGHT = 0.8
OVERLOAD_RUNNER_SHARE = 0.25
ROAM_CHANCE = 0.06
FOUL_RATE = 0.015
CARD_RATE = 0.15
PRESSURE_PENALTY = 0.06   # success-probability cost of acting under pressure
PASS_DISTANCE_PENALTY = 0.006  # per metre beyond 12 m
SWITCH_PENALTY = 0.06          # switching the ball to another lane


@dataclass(frozen=True)
class Factor:
    kind: str        # "fatigue": a defending full-back tires | "overload": attackers flood a flank
    team: str        # the team the factor acts on
    target: str      # fatigue: player id | overload: lane
    onset: int       # seconds
    magnitude: float


@dataclass(frozen=True)
class Decoy:
    after: int       # inserted at the first restart by the beneficiary after this time
    fouler: str
    victim: str


@dataclass(frozen=True)
class MatchConfig:
    seed: int
    home: str
    away: str
    ratings: dict = field(hash=False)
    lane_weights: dict = field(hash=False)
    beneficiary: str
    factor: Factor
    weak_player: str | None = None   # a defender who is weaker all match (confound)
    weak_delta: float = 0.0
    decoy: Decoy | None = None


@dataclass
class MatchResult:
    events: list
    goals: list            # (t, team, event_id)
    decoy_ids: list        # hidden: which events the decoy inserted


def pid(team: str, role: str) -> str:
    return f"{team}-{role}"


def team_of(player_id: str) -> str:
    return player_id.split("-", 1)[0]


def role_of(player_id: str) -> str:
    return player_id.split("-", 1)[1]


def mix(*parts: int) -> int:
    """Stable 64-bit hash of integers (FNV-1a style); Python's hash() is salted per process."""
    h = 1469598103934665603
    for part in parts:
        h ^= part & 0xFFFFFFFFFFFFFFFF
        h = (h * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return h


def to_xy(attacks_right: bool, p: float, lane: str, jitter: float = 0.0) -> tuple:
    x = p * PITCH_X
    y = LANE_Y[lane] + jitter
    if not attacks_right:
        x, y = PITCH_X - x, PITCH_Y - y
    return (round(min(max(x, 0.5), PITCH_X - 0.5), 1), round(min(max(y, 0.5), PITCH_Y - 0.5), 1))


def lane_of(y: float, attacks_right: bool) -> str:
    yy = y if attacks_right else PITCH_Y - y
    if yy >= PITCH_Y * 2 / 3:
        return "left"
    if yy < PITCH_Y / 3:
        return "right"
    return "center"


def xg(p: float, lane: str, header: bool) -> float:
    dist = math.hypot((1.0 - p) * PITCH_X, 0.0 if lane == "center" else 14.0)
    q = 0.42 * math.exp(-0.12 * dist)
    return q * 0.55 if header else q


def style_lane(cfg: MatchConfig) -> str:
    w = cfg.lane_weights[cfg.beneficiary]
    return max(w, key=w.get)


def style_bias(cfg: MatchConfig) -> float:
    return max(cfg.lane_weights[cfg.beneficiary].values()) - 1.0


def _weighted(rng: random.Random, weights: dict) -> str:
    total = sum(weights.values())
    r = rng.random() * total
    key = None
    for key, w in weights.items():
        r -= w
        if r <= 0:
            return key
    return key


def _choose_action(rng: random.Random, p: float, lane: str) -> str:
    r = rng.random()
    if lane == "center":
        if p >= 0.86:
            return "shot" if r < 0.65 else "dribble" if r < 0.82 else "pass"
        if p >= 0.70 and r < 0.10:
            return "shot"
        return "pass" if r < 0.68 else "carry" if r < 0.88 else "dribble"
    if p >= 0.78:
        return "cross" if r < 0.45 else "dribble" if r < 0.72 else "pass"
    return "pass" if r < 0.52 else "carry" if r < 0.70 else "dribble"


class _Sim:
    def __init__(self, cfg: MatchConfig, noise_seed, split, neutralize):
        self.cfg = cfg
        self.noise_seed = noise_seed
        self.split = split
        self.neutralize = frozenset(neutralize)
        self.events: list = []
        self.goals: list = []
        self.decoy_ids: list = []
        self.memory = {cfg.home: dict.fromkeys(LANES, 0.0), cfg.away: dict.fromkeys(LANES, 0.0)}
        self.decoy_done = cfg.decoy is None

    def other(self, team):
        return self.cfg.away if team == self.cfg.home else self.cfg.home

    def off(self, name, t):
        """True when hidden variable `name` is switched off at time t (intervention)."""
        return name in self.neutralize and (self.split is None or t >= self.split)

    def rng_for(self, idx, t):
        if self.noise_seed is not None and self.split is not None and t >= self.split:
            return random.Random(mix(self.noise_seed, idx, 2))
        return random.Random(mix(self.cfg.seed, idx, 1))

    def rating(self, player, t):
        cfg = self.cfg
        r = cfg.ratings[player]
        if player == cfg.weak_player and not self.off("static", t):
            r -= cfg.weak_delta
        f = cfg.factor
        if f.kind == "fatigue" and f.target == player and t >= f.onset and not self.off("factor", t):
            r -= FATIGUE_DROP * f.magnitude * min(1.0, (t - f.onset) / FATIGUE_RAMP)
        return r

    def overload(self, team, lane, t):
        f = self.cfg.factor
        return (f.kind == "overload" and f.team == team and f.target == lane
                and t >= f.onset and not self.off("factor", t))

    def lane_weights(self, team, t):
        cfg = self.cfg
        if team == cfg.beneficiary and self.off("style", t):
            w = dict.fromkeys(LANES, 1.0)
        else:
            w = dict(cfg.lane_weights[team])
        f = cfg.factor
        if f.kind == "overload" and self.overload(team, f.target, t):
            w[f.target] += OVERLOAD_LANE_WEIGHT * f.magnitude
        mem = self.memory[team]
        return {lane: w[lane] * (1.0 + 0.25 * min(mem[lane], 3.0)) for lane in LANES}

    def pick(self, team, lane, t, rng, exclude=None):
        player = None
        for _ in range(4):
            # Fixed number of draws per attempt keeps paired runs aligned.
            u_run, u_roam, u_pick = rng.random(), rng.random(), rng.random()
            if lane in OVERLOAD_RUNNER and self.overload(team, lane, t) and u_run < OVERLOAD_RUNNER_SHARE:
                role = OVERLOAD_RUNNER[lane]
            elif u_roam < ROAM_CHANCE:
                role = OUTFIELD[int(u_pick * len(OUTFIELD))]
            else:
                pool = LANE_POOL[lane]
                role = pool[int(u_pick * len(pool))]
            player = pid(team, role)
            if player != exclude:
                return player
        return player

    def emit(self, t, team, player, etype, outcome, xy, end_xy=None, opponent=None, receiver=None, possession=None,
             pressure=False, speed=None):
        e = {
            "id": f"e{len(self.events):05d}", "t": round(t, 1), "team": team, "player_id": player,
            "type": etype, "outcome": outcome, "x": xy[0], "y": xy[1],
            "end_x": end_xy[0] if end_xy else None, "end_y": end_xy[1] if end_xy else None,
            "opponent_id": opponent, "receiver_id": receiver, "possession_id": possession,
            "under_pressure": bool(pressure), "speed_kmh": round(speed, 1) if speed is not None else None,
        }
        self.events.append(e)
        return e

    def advance(self, team, p_old, p_new, lane):
        if p_old < 0.70 <= p_new:
            self.memory[team][lane] += 1.0

    def shot(self, t, team, opp, shooter, p, lane, right, u, poss, header):
        q = xg(p, lane, header)
        q = min(max(q + 0.4 * (self.rating(shooter, t) - self.rating(pid(opp, "GK"), t)), 0.01), 0.9)
        xy = to_xy(right, p, lane, (u - 0.5) * 10.0)
        goal_xy = (PITCH_X, PITCH_Y / 2) if right else (0.0, PITCH_Y / 2)
        if u < q:
            outcome = "goal"
        elif u < q + (1.0 - q) * 0.45:
            outcome = "saved"
        else:
            outcome = "off_target"
        # Shot speed: struck shots roughly 60-120 km/h, faster from range; headers 35-65 km/h.
        frac = (u * 7.31) % 1.0
        speed = 35 + 30 * frac if header else 60 + 45 * frac + 15 * (1 - p)
        e = self.emit(t, team, shooter, "shot", outcome, xy, goal_xy, opponent=pid(opp, "GK"), possession=poss,
                      speed=speed)
        if outcome == "goal":
            self.goals.append((e["t"], team, e["id"]))
        return outcome, t, p

    def insert_decoy(self, t, p):
        """A cynical foul and booking just before a restart. It changes nothing downstream:
        no RNG is consumed and the clock does not move, so its causal effect is exactly zero."""
        d = self.cfg.decoy
        team = team_of(d.fouler)
        xy = to_xy(self.cfg.beneficiary == self.cfg.home, max(p, 0.45), "center")
        foul = self.emit(t + 0.5, team, d.fouler, "foul", "committed", xy, opponent=d.victim)
        card = self.emit(t + 1.0, team, d.fouler, "card", "yellow", xy)
        self.decoy_ids = [foul["id"], card["id"]]
        self.decoy_done = True

    def possession(self, idx, team, p, t, restart_gap):
        cfg = self.cfg
        rng = self.rng_for(idx, t)
        opp = self.other(team)
        right = team == cfg.home
        mem = self.memory[team]
        for lane in LANES:
            mem[lane] *= 0.85
        t += restart_gap + rng.uniform(3.0, 12.0)
        weights = self.lane_weights(team, t)
        lane = _weighted(rng, weights)
        carrier = self.pick(team, lane, t, rng)
        poss = f"p{idx:04d}"
        for _ in range(16):
            t += rng.uniform(2.5, 6.0)
            if t >= MATCH_END:
                return "end", t, p
            action = _choose_action(rng, p, lane)
            defenders = LANE_DEFENDERS[lane]
            defender = pid(opp, defenders[int(rng.random() * len(defenders))])
            jitter = rng.uniform(-7.0, 7.0)
            xy = to_xy(right, p, lane, jitter)
            u_foul, u_card, u_act, u_gain = rng.random(), rng.random(), rng.random(), rng.random()
            u_press, u_speed = rng.random(), rng.random()
            pressed = u_press < 0.18 + 0.42 * p
            if action != "shot" and u_foul < FOUL_RATE:
                self.emit(t, opp, defender, "foul", "committed", xy, opponent=carrier, possession=poss)
                if u_card < CARD_RATE:
                    self.emit(t + 1.0, opp, defender, "card", "yellow", xy, possession=poss)
                t += 15.0 + 15.0 * u_gain
                continue
            if action == "shot":
                return self.shot(t, team, opp, carrier, p, lane, right, u_act, poss, header=False)
            att = self.rating(carrier, t)
            d = self.rating(defender, t)
            prob = BASE_SUCCESS[action] + EDGE_WEIGHT * (att - d) - 0.15 * max(0.0, p - 0.5) / 0.5
            if pressed:
                prob -= PRESSURE_PENALTY
            if action in ("pass", "cross") and self.overload(team, lane, t):
                prob += OVERLOAD_PASS_BONUS * cfg.factor.magnitude
            prob = min(max(prob, 0.05), 0.97)
            ok = u_act < prob

            if action == "cross":
                box = ("ST", "ST", "RW" if lane == "left" else "LW")
                target = pid(team, box[int(u_gain * 3)])
                end_xy = to_xy(right, 0.94, "center", jitter * 0.5)
                self.emit(t, team, carrier, "cross", "success" if ok else "fail", xy, end_xy,
                          opponent=None if ok else defender, receiver=target if ok else None, possession=poss,
                          pressure=pressed, speed=55 + 30 * u_speed)
                if not ok:
                    self.emit(t + 0.3, opp, defender, "clearance", "won", end_xy, opponent=carrier, possession=poss)
                    return "turnover", t, 0.9
                return self.shot(t + 1.0, team, opp, target, 0.94, "center", right, rng.random(), poss, header=True)

            if action == "pass":
                new_lane = lane
                if rng.random() < 0.22:
                    new_lane = _weighted(rng, {k: w for k, w in weights.items() if k != lane})
                receiver = self.pick(team, new_lane, t, rng, exclude=carrier)
                gain = 0.06 + 0.10 * u_gain
                end_xy = to_xy(right, min(p + gain, 0.97), new_lane, rng.uniform(-7.0, 7.0))
                dist = math.hypot(end_xy[0] - xy[0], end_xy[1] - xy[1])
                # Longer passes and switches of play fail more often, as in real football.
                hard = PASS_DISTANCE_PENALTY * max(dist - 12.0, 0.0) + (SWITCH_PENALTY if new_lane != lane else 0.0)
                ok = u_act < min(max(prob - hard, 0.05), 0.97)
                self.emit(t, team, carrier, "pass", "success" if ok else "fail", xy, end_xy,
                          opponent=None if ok else defender, receiver=receiver if ok else None, possession=poss,
                          pressure=pressed, speed=28 + 1.2 * dist + 12 * u_speed)
                if not ok:
                    mid = (round((xy[0] + end_xy[0]) / 2, 1), round((xy[1] + end_xy[1]) / 2, 1))
                    self.emit(t + 0.3, opp, defender, "interception", "won", mid, opponent=carrier, possession=poss)
                    return "turnover", t, p
                self.advance(team, p, p + gain, new_lane)
                p, lane, carrier = min(p + gain, 0.97), new_lane, receiver
                continue

            gain = (0.04 + 0.05 * u_gain) if action == "carry" else (0.06 + 0.06 * u_gain)
            end_xy = to_xy(right, min(p + gain, 0.97), lane, jitter) if ok else None
            opponent = defender if (action == "dribble" or not ok) else None
            # Running speed of the ball carrier: carries 14-27 km/h, dribbles 17-34 km/h.
            run = (14 + 13 * u_speed) if action == "carry" else (17 + 17 * u_speed)
            self.emit(t, team, carrier, action, "success" if ok else "fail", xy, end_xy,
                      opponent=opponent, possession=poss, pressure=pressed, speed=run)
            if not ok:
                self.emit(t + 0.2, opp, defender, "tackle", "won", xy, opponent=carrier, possession=poss)
                return "turnover", t, p
            self.advance(team, p, p + gain, lane)
            p = min(p + gain, 0.97)
        return "turnover", t, p

    def run(self) -> MatchResult:
        cfg = self.cfg
        team, p, t, idx, gap = cfg.home, 0.5, 0.0, 0, 0.0
        while t < MATCH_END:
            if not self.decoy_done and team == cfg.beneficiary and t >= cfg.decoy.after:
                self.insert_decoy(t, p)
            outcome, t, p_end = self.possession(idx, team, p, t, gap)
            idx += 1
            if outcome == "end":
                break
            team = self.other(team)
            if outcome == "goal":
                p, gap = 0.5, 45.0
            elif outcome in ("saved", "off_target"):
                p, gap = 0.08, 8.0
            else:
                p, gap = min(max(1.0 - p_end, 0.05), 0.6), 0.0
        return MatchResult(self.events, self.goals, self.decoy_ids)


def simulate(cfg: MatchConfig, noise_seed: int | None = None, split: int | None = None,
             neutralize=()) -> MatchResult:
    """Run one match.

    noise_seed/split: possessions starting at or after `split` draw from `noise_seed` streams
    instead of the match seed, so many paired futures can branch from one shared history.
    neutralize: hidden variables ("factor", "static", "style") switched off from `split` on.
    """
    return _Sim(cfg, noise_seed, split, neutralize).run()


def make_config(seed: int) -> MatchConfig:
    rng = random.Random(mix(seed, 424242))
    home, away = rng.sample(sorted(CLUBS), 2)
    if LEAGUE:
        # Real ability from the 2024/25 pack, plus a little form on the day.
        ratings = {pid(t, r): round(LEAGUE["clubs"][t]["xi"][r]["rating"] + rng.uniform(-0.02, 0.02), 3)
                   for t in (home, away) for r in ROLES}
    else:
        ratings = {pid(t, r): round(rng.uniform(0.45, 0.65), 3) for t in (home, away) for r in ROLES}
    beneficiary = rng.choice([home, away])
    victim = away if beneficiary == home else home

    lane_weights = {}
    for team in (home, away):
        w = dict.fromkeys(LANES, 1.0)
        w[rng.choice(WIDE_LANES)] += rng.uniform(0.0, 0.8)
        lane_weights[team] = w

    kind = rng.choice(["fatigue", "overload"])
    side = rng.choice(WIDE_LANES)  # the beneficiary's attacking lane where the factor bites
    onset = rng.randint(55, 70) * 60
    magnitude = round(rng.uniform(0.6, 1.4), 3)
    if kind == "fatigue":
        factor = Factor("fatigue", victim, pid(victim, FULL_BACK_FOR_LANE[side]), onset, magnitude)
    else:
        factor = Factor("overload", beneficiary, side, onset, magnitude)

    weak_player, weak_delta = None, 0.0
    if rng.random() < 0.6:
        weak_player = pid(victim, rng.choice(["RB", "LB"]))
        weak_delta = round(rng.uniform(0.06, 0.16), 3)

    decoy = Decoy(
        after=onset + rng.randint(3, 15) * 60,
        fouler=pid(victim, rng.choice(["CB1", "CB2", "DM"])),
        victim=pid(beneficiary, rng.choice(["ST", "LW", "RW"])),
    )
    return MatchConfig(seed, home, away, ratings, lane_weights, beneficiary, factor,
                       weak_player, weak_delta, decoy)


def roster(cfg: MatchConfig) -> dict:
    """Public line-up information: team, role and name for every player."""
    out = {}
    if LEAGUE:
        for team in (cfg.home, cfg.away):
            for role in ROLES:
                p = LEAGUE["clubs"][team]["xi"][role]
                out[pid(team, role)] = {"team": team, "role": role, "name": p["name"], "nationality": p["nationality"]}
        return out
    rng = random.Random(mix(cfg.seed, 777))
    names = rng.sample(SURNAMES, len(ROLES) * 2)
    for i, (team, role) in enumerate((t, r) for t in (cfg.home, cfg.away) for r in ROLES):
        out[pid(team, role)] = {"team": team, "role": role, "name": names[i]}
    return out


def metadata(cfg: MatchConfig) -> dict:
    """Public match metadata: competition, venue, kick-off, referee, attendance."""
    rng = random.Random(mix(cfg.seed, 991))
    meta = {"competition": "Premier League" if LEAGUE else "Synthetic League", "season": LEAGUE["season"] if LEAGUE else None,
            "matchweek": rng.randint(1, 38), "kickoff": rng.choice(KICKOFFS), "referee": rng.choice(REFEREES),
            "formation": {cfg.home: "4-3-3", cfg.away: "4-3-3"}, "simulated": True}
    if LEAGUE:
        home = LEAGUE["clubs"][cfg.home]
        meta |= {"venue": home["stadium"], "attendance": int(home["capacity"] * rng.uniform(0.93, 0.995)),
                 "colours": {t: LEAGUE["clubs"][t]["colours"] for t in (cfg.home, cfg.away)},
                 "club_names": {t: LEAGUE["clubs"][t]["name"] for t in (cfg.home, cfg.away)}}
    return meta
