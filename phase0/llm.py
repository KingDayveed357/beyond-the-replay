"""LLM-only baseline: the raw event log in, ranked causes out. No tools, no sceptic, no verifier
in the loop (claims are verified afterwards only to measure how many were unsupported).

Uses the same provider layer and model as the agents, so the comparison isolates the workflow.
"""
from __future__ import annotations

from investigation.board import Board
from investigation.llm.agents import run_agent
from investigation.llm.provider import Provider
from investigation.llm.tools import INVESTIGATOR_TOOLS

from .investigators import Hypothesis, MatchView, candidate_keys
from .observe import Case

SYSTEM = """You are a football analyst. You receive the complete event log of a synthetic match and one goal to explain. Rank up to three most likely underlying causes of that goal from the candidate list, strongest first, citing event ids from the log as evidence.

Kinds: FATIGUE = a conceding full-back declined during the match; STATIC = a conceding full-back was outmatched all game; OVERLOAD = the scoring team flooded a flank with an extra midfielder from some minute; STYLE = the scoring team simply favours a flank; FOUL = the booking before the goal changed the game. onset_minute is required for FATIGUE and OVERLOAD and null otherwise. Call submit_hypotheses exactly once."""


def build_prompt(case: Case) -> str:
    v = MatchView(case)
    lines = ["ROSTER (id,team,role,name)"]
    lines += [f"{p},{r['team']},{r['role']},{r['name']}" for p, r in case.roster.items()]
    lines.append("EVENTS (id,minute,team,player,type,outcome,lane_for_acting_team,opponent,receiver,possession)")
    for e in case.events:
        lines.append(",".join(str(x) for x in (
            e["id"], round(e["t"] / 60, 1), e["team"], e["player_id"], e["type"], e["outcome"],
            v.lane.get(e["id"], ""), e["opponent_id"] or "", e["receiver_id"] or "", e["possession_id"] or "")))
    lines.append(f"GOAL TO EXPLAIN: {case.incident_id}, scored by {v.A} at minute {round(v.t_inc / 60, 1)}")
    lines.append("CANDIDATES (kind(target)): " + "; ".join(f"{k}({t})" for k, t in candidate_keys(v)))
    return "\n".join(lines)


def investigate(case: Case, provider: Provider) -> list:
    board = Board(case.case_id, case.incident_id, "llm_only")
    submitted, _ = run_agent(provider, name="llm-only analyst", system=SYSTEM, user=build_prompt(case),
                             tools=[INVESTIGATOR_TOOLS[-1]], handlers={}, submit="submit_hypotheses",
                             max_tokens=8000, effort="medium", board=board)
    out = []
    for i, h in enumerate((submitted.get("hypotheses") or [])[:3]):
        onset = h.get("onset_minute")
        out.append(Hypothesis(str(h.get("kind", "")).upper(), str(h.get("target", "")), 3.0 - i,
                              (int(onset) - 1) * 60 if isinstance(onset, int) else None,
                              [str(c) for c in h.get("cited_event_ids", [])][:8], str(h.get("reasoning", ""))[:300]))
    return out
