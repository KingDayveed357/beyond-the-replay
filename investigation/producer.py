"""The producer turns verified findings into a short explanation for a fan or an analyst.

It may only rephrase what is on the board. `check_grounded` enforces that: every beat must
point at a verified, non-refuted claim, and every player name and minute in the text must come
from that claim's evidence. An LLM producer will be held to the same check.
"""
from __future__ import annotations

import re

from phase0.engine import OVERLOAD_RUNNER, pid
from phase0.investigators import MatchView

from .board import Board, Claim
from .language import club, flank, minute, player, player_long

MINUTE_RE = re.compile(r"\b(\d{1,3})'")
COUNT_RE = re.compile(r"\b\d+ of \d+\b|\b\d+/\d+\b|\b\d+%")


def _counts(text: str) -> set:
    return set(COUNT_RE.findall(text))


def statement(c: Claim, v: MatchView, roster: dict) -> str:
    on = minute(c.onset) if c.onset is not None else None
    if c.kind == "FATIGUE":
        return f"{player_long(roster, c.target)}, faded: more one-on-ones lost from around {on}."
    if c.kind == "STATIC":
        return f"{player_long(roster, c.target)}, was outmatched all game."
    if c.kind == "OVERLOAD":
        runner = player(roster, pid(v.A, OVERLOAD_RUNNER[c.target]))
        return f"{club(v.A)} overloaded their {c.target} flank from around {on}, pulling {runner} across."
    if c.kind == "STYLE":
        return f"{club(v.A)} simply favour their {c.target} flank."
    foul = v.by_id[c.target]
    return f"The booking of {player(roster, foul['player_id'])} at {minute(foul['t'])} swung the game."


def supporting_test(c: Claim):
    """The last upheld deterministic test is the positive one (e.g. "did the decline happen?")."""
    return next((ch for ch in reversed(c.challenges) if ch.source == "test" and ch.verdict == "upheld" and ch.evidence), None)


def confidence(ranked: list) -> str:
    if not ranked:
        return "none"
    s1 = ranked[0].score
    s2 = ranked[1].score if len(ranked) > 1 else 0.0
    ratio = s1 / s2 if s2 > 0 else float("inf")
    level = "strong" if ratio >= 2.0 else "likely" if ratio >= 1.3 else "uncertain"
    if ranked[0].status == "weakened" and level == "strong":
        level = "likely"
    return level


def produce(board: Board, v: MatchView, roster: dict) -> dict:
    eligible = [c for c in board.ranked() if c.verified and c.status != "refuted"]
    if not eligible:
        return {"confidence": "none", "headline": "No explanation survived verification.", "beats": [], "ruled_out": []}
    top = eligible[0]
    level = confidence(eligible)
    foul = next((c for c in board.claims if c.kind == "FOUL"), None)
    scorer = player(roster, v.incident["player_id"])

    prefix = "It wasn't the booking. " if foul is not None and foul.status == "refuted" else ""
    headline = {
        "FATIGUE": f"{prefix}{player(roster, top.target)} ran out of legs.",
        "STATIC": f"{prefix}{player(roster, top.target)} was targeted all game.",
        "OVERLOAD": f"{prefix}{club(v.A)} outnumbered the {top.target} flank.",
        "STYLE": f"{prefix}{club(v.A)} kept going down the {top.target}.",
        "FOUL": "The booking changed the game.",
    }[top.kind]

    # The last upheld test is the positive one (e.g. "did the decline happen?"), not a ruled-out alternative.
    support = supporting_test(top)
    beats = [{"label": "Cause", "claim_id": top.id, "evidence": top.cited[:6],
              "fan": statement(top, v, roster), "analyst": statement(top, v, roster)}]
    if support is not None:
        beats.append({"label": "Evidence", "claim_id": top.id, "evidence": support.evidence,
                      "fan": support.finding.split(": ", 1)[-1], "analyst": f"{support.question} {support.finding}"})
    build_up = [e["id"] for e in v.build_up]
    lane = v.final_lane
    beats.append({"label": "The moment", "claim_id": top.id, "evidence": build_up,
                  "fan": f"At {minute(v.t_inc)}, {scorer} finished a move that came down {flank(v.A, lane)}.",
                  "analyst": f"Goal at {minute(v.t_inc)} by {scorer}: {len(build_up)}-action move, final ball from the {lane}."})

    ruled_out = []
    for c in board.ranked():
        if c is top or not c.challenges or c.status == "upheld":
            continue
        decisive = next((ch for ch in c.challenges if ch.verdict == c.status and ch.source == "test"),
                        next(ch for ch in c.challenges if ch.verdict == c.status))
        ruled_out.append({"claim_id": c.id, "status": c.status, "statement": statement(c, v, roster),
                          "reason": decisive.finding, "evidence": decisive.evidence})
    return {"confidence": level, "headline": headline, "beats": beats, "ruled_out": ruled_out[:3]}


def check_grounded(explanation: dict, board: Board, v: MatchView, roster: dict) -> list:
    """Return a list of grounding violations (empty means every statement is backed by evidence)."""
    problems = []
    claims = {c.id: c for c in board.claims}
    allowed_players = {v.incident["player_id"]}
    allowed_minutes = {minute(v.t_inc)}
    for beat in explanation.get("beats", []):
        c = claims.get(beat.get("claim_id"))
        if c is None or not c.verified or c.status == "refuted":
            problems.append(f"beat {beat.get('label')!r} is not backed by a verified claim")
            continue
        allowed_players.add(c.target)
        if c.onset is not None:
            allowed_minutes.add(minute(c.onset))
        if c.kind == "OVERLOAD":
            allowed_players.add(pid(v.A, OVERLOAD_RUNNER[c.target]))
        for eid in list(beat.get("evidence", [])) + list(c.cited):
            e = v.by_id.get(eid)
            if e is None:
                problems.append(f"beat {beat.get('label')!r} cites unknown event {eid}")
                continue
            allowed_players.update(p for p in (e["player_id"], e["opponent_id"], e["receiver_id"]) if p)
            allowed_minutes.add(minute(e["t"]))
        for ch in c.challenges:
            if ch.source != "test":  # model-written judgements are not evidence
                continue
            allowed_players.update(p for p in roster if roster[p]["name"] in ch.finding)
            allowed_minutes.update(f"{m}'" for m in MINUTE_RE.findall(ch.finding))
    for r in explanation.get("ruled_out", []):  # deterministic statements and test findings about rejected causes
        text = f"{r.get('statement', '')} {r.get('reason', '')}"
        allowed_players.update(p for p in roster if roster[p]["name"] in text)
        allowed_minutes.update(f"{m}'" for m in MINUTE_RE.findall(text))
    allowed_counts = {n for c in claims.values() for ch in c.challenges if ch.source == "test" for n in _counts(ch.finding)}
    allowed_names = {roster[p]["name"] for p in allowed_players if p in roster}
    texts = [explanation.get("headline", "")] + [b[k] for b in explanation.get("beats", []) for k in ("fan", "analyst")]
    for text in texts:
        for p, info in roster.items():
            if info["name"] in text and info["name"] not in allowed_names:
                problems.append(f"names {info['name']} without evidence: {text!r}")
        for m in MINUTE_RE.findall(text):
            if f"{m}'" not in allowed_minutes:
                problems.append(f"mentions minute {m}' without evidence: {text!r}")
        for n in _counts(text) - allowed_counts:
            problems.append(f"quotes '{n}' which no test reported: {text!r}")
    return problems
