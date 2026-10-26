"""Claude-powered investigation: Investigator -> Sceptic -> (code) Verifier -> Producer.

The LLM agents choose which tools to call and how to reason; code keeps authority over what
counts as evidence. Citations must come from tool results, the verifier is deterministic, the
booking is always tested, a "refuted" verdict needs a failing test, and the producer's text must
pass the grounding check or it is replaced by the labelled template.
"""
from __future__ import annotations

import json
import time

from phase0.investigators import Hypothesis, MatchView, _involves, verify
from phase0.observe import Case

from ..board import Board, Challenge, Claim
from ..producer import check_grounded, confidence, produce, statement, supporting_test
from ..language import club, minute, player
from .provider import SUPPORTED_MODELS, Provider, ProviderError
from .tools import INVESTIGATOR_TOOLS, PRODUCER_TOOL, SCEPTIC_TOOLS, MatchTools

MAX_TOOL_TURNS = 8        # hard stop on any agent loop
SEVERITY = {"upheld": 0, "weakened": 1, "refuted": 2}

INVESTIGATOR_SYSTEM = """You are the Investigator in a football incident inquiry. A goal was scored in a synthetic match. Propose its most likely underlying causes, using only your tools.

Cause vocabulary (kind -> target):
- FATIGUE (full-back id): a conceding full-back declined during the match: noticeably more one-on-ones lost after some minute.
- STATIC (full-back id): a conceding full-back was outmatched all game, with no clear decline.
- OVERLOAD (lane): from some minute the scoring team flooded a flank with an extra midfielder (the "overload runner") and completed more passes there.
- STYLE (lane): the scoring team simply favoured a flank all game.
- FOUL (event id): the booking shortly before the goal changed the game.

Method: start with match_brief and statistical_screen, then test your leading candidates with targeted tools. A decline needs before/after evidence (defender_decline); an overload needs the runner appearing on that flank after a change (flank_change); a constant mismatch needs a gap with no later decline. The most recent dramatic event is not automatically the cause.

Fatigue and overload can look alike: both put more play down one flank, and both raise pass completion there. When there is a flank story, check both: defender_decline for that flank's full-back and flank_change for that flank. Only flank_change's change_found shows an overload; do not rank OVERLOAD first when change_found is false. When change_found is false and the full-back shows a clear decline, the explanation is fatigue.

Rules: cite only event ids that a tool returned to you, and for FATIGUE and OVERLOAD cite events from after the onset. onset_minute is required for FATIGUE and OVERLOAD and null otherwise. Targets must come from valid_targets. Rank strongest first. Keep each reasoning to one or two sentences. Finish by calling submit_hypotheses exactly once."""

SCEPTIC_SYSTEM = """You are the Sceptic in a football incident inquiry. Try to break each claim before it reaches viewers.

For each claim, call run_standard_tests. If a result is borderline, check the raw evidence with the other tools. Verdicts:
- upheld: the claim survives the tests.
- weakened: it partly survives, or a rival explanation fits the evidence as well.
- refuted: a test or the raw evidence contradicts it.

Refute only when a test or the raw evidence contradicts the claim. Always review the booking claim if there is one. Each rationale is one or two sentences and quotes only numbers a tool returned. Finish by calling submit_reviews exactly once."""

PRODUCER_SYSTEM = """You are the Producer. Write the on-screen explanation of a goal for a broadcast audience, using only the verified findings you are given. Do not add facts: every player name, minute and number you mention must appear in the findings. Quote counts exactly as the findings write them (for example "6 of 7"); do not compute percentages, rates or fractions.

Headline: under 12 words; if the booking was ruled out, say so. Write three beats: "Cause" (the top finding in plain words), "Evidence" (the key numbers from the tests), "The moment" (how the goal itself unfolded). Each beat has a fan version (plain and vivid, at most 25 words) and an analyst version (precise, with numbers, at most 40 words). Call submit_explanation exactly once."""


def run_agent(provider: Provider, *, name: str, system: str, user: str, tools: list, handlers: dict,
              submit: str, max_tokens: int, effort: str, board: Board) -> tuple:
    """Bounded tool-use loop. Returns (submitted input, tool calls made)."""
    messages = [{"role": "user", "content": user}]
    calls, nudged = [], False
    for _ in range(MAX_TOOL_TURNS):
        resp = provider.create(system=system, messages=messages, tools=tools, max_tokens=max_tokens,
                               output_config={"effort": effort})
        if resp.stop_reason == "max_tokens":
            raise ProviderError("bad_output", f"The {name} ran out of output room.", 502, True)
        uses = [b for b in resp.content if b.type == "tool_use"]
        final = next((b for b in uses if b.name == submit), None)
        if final is not None:
            return final.input, calls
        messages.append({"role": "assistant", "content": resp.content})
        if not uses:
            if nudged:
                raise ProviderError("bad_output", f"The {name} finished without submitting a result.", 502, True)
            messages.append({"role": "user", "content": f"Call {submit} now with your conclusions."})
            nudged = True
            continue
        results = []
        for b in uses:
            calls.append({"tool": b.name, "input": b.input})
            try:
                out = handlers[b.name](**b.input)
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": json.dumps(out)})
            except (KeyError, TypeError, ValueError) as exc:
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": f"Error: {exc}", "is_error": True})
        messages.append({"role": "user", "content": results})
        board.log(name, "tools", ", ".join(c["tool"] for c in calls[-len(uses):]))
    raise ProviderError("bad_output", f"The {name} did not finish within {MAX_TOOL_TURNS} steps.", 502, True)


def _claims_from(submitted: dict, tools: MatchTools, v: MatchView, roster: dict) -> tuple:
    hyps = submitted.get("hypotheses") if isinstance(submitted, dict) else None
    if not isinstance(hyps, list) or not hyps:
        raise ProviderError("bad_output", "The investigator returned no hypotheses.", 502, True)
    claims, dropped = [], 0
    for i, h in enumerate(hyps[:4]):
        if not isinstance(h, dict):
            continue
        cited = [str(x) for x in h.get("cited_event_ids", [])]
        allowed = [x for x in cited if x in tools.seen_ids]
        dropped += len(cited) - len(allowed)
        onset = h.get("onset_minute")
        c = Claim(f"c{i + 1}", str(h.get("kind", "")).upper(), str(h.get("target", "")),
                  (int(onset) - 1) * 60 if isinstance(onset, int) else None, "", allowed, "investigator (Claude)",
                  float(4 - i), float(4 - i), reasoning=str(h.get("reasoning", ""))[:400])
        try:
            c.statement = statement(c, v, roster)
        except (KeyError, IndexError, TypeError):
            c.statement = f"{c.kind} {c.target}"
        claims.append(c)
    return claims, dropped


def _sceptic(provider: Provider, board: Board, tools: MatchTools, v: MatchView, roster: dict) -> list:
    claims = {c.id: c for c in board.claims}
    tested: dict[str, list] = {}

    def run_standard_tests(claim_id: str) -> dict:
        c = claims.get(claim_id)
        if c is None:
            raise ValueError(f"unknown claim {claim_id}")
        tested[claim_id] = tools.standard_tests(c)
        return {"claim_id": claim_id, "tests": [{"question": ch.question, "finding": ch.finding, "verdict": ch.verdict,
                                                 "event_ids": tools._ids(ch.evidence)} for ch in tested[claim_id]]}

    listing = "\n".join(f"- {c.id}: {c.kind}({c.target}) — {c.statement} Investigator's reasoning: {c.reasoning or 'n/a'}"
                        for c in board.claims)
    handlers = {"run_standard_tests": run_standard_tests, "duel_record": tools.duel_record,
                "defender_decline": tools.defender_decline, "flank_profile": tools.flank_profile,
                "flank_change": tools.flank_change}
    submitted, calls = run_agent(provider, name="sceptic", system=SCEPTIC_SYSTEM,
                                 user=f"Claims about {club(v.A)}'s goal at {minute(v.t_inc)}:\n{listing}",
                                 tools=SCEPTIC_TOOLS, handlers=handlers, submit="submit_reviews",
                                 max_tokens=6000, effort="medium", board=board)
    reviews = submitted.get("reviews", []) if isinstance(submitted, dict) else []
    notes = []
    for r in reviews:
        c = claims.get(r.get("claim_id")) if isinstance(r, dict) else None
        verdict = r.get("verdict") if isinstance(r, dict) else None
        if c is None or verdict not in SEVERITY:
            continue
        if c.id not in tested:  # a verdict always rests on the deterministic tests
            tested[c.id] = tools.standard_tests(c)
        worst = max((SEVERITY[ch.verdict] for ch in tested[c.id]), default=0)
        if verdict == "refuted" and worst == 0:
            verdict = "weakened"
            notes.append(f"{c.id}: 'refuted' downgraded to 'weakened' because every test held")
        c.challenges = tested[c.id] + [Challenge("Sceptic's judgement", str(r.get("rationale", ""))[:400], verdict, source="llm")]
        c.status = verdict
        board.log("sceptic", "challenge", f"{c.kind}({c.target}): {verdict}")
    for c in board.claims:  # the obvious story is always tested, even if the model skipped it
        if c.kind == "FOUL" and c.status == "proposed":
            c.challenges = tested.get(c.id) or tools.standard_tests(c)
            c.status = max((ch.verdict for ch in c.challenges), key=SEVERITY.get)
            notes.append(f"{c.id}: the sceptic skipped the booking, so code ran its tests")
            board.log("sceptic", "challenge", f"FOUL({c.target}): {c.status} (tested by code)")
    for c in board.claims:
        if c.status == "refuted":
            c.score *= 0.05
    return notes + [f"{len(calls)} tool calls"]


def _producer(provider: Provider, board: Board, v: MatchView, roster: dict) -> tuple:
    template = produce(board, v, roster)
    eligible = [c for c in board.ranked() if c.verified and c.status != "refuted"]
    if not eligible:
        return template, "template", ["no verified claims"]
    top = eligible[0]
    support = supporting_test(top)
    findings = {
        "top_finding": {"statement": top.statement, "kind": top.kind,
                        "tests": [{"question": ch.question, "finding": ch.finding} for ch in top.challenges
                                  if ch.source == "test" and ch.verdict == "upheld"]},
        "ruled_out": [{"statement": r["statement"], "status": r["status"], "reason": r["reason"]} for r in template["ruled_out"]],
        "goal": {"minute": minute(v.t_inc), "scorer": player(roster, v.incident["player_id"]),
                 "scoring_team": club(v.A), "conceding_team": club(v.B),
                 "move": [f"{minute(e['t'])} {player(roster, e['player_id'])} {e['type']} ({v.lane[e['id']]})" for e in v.build_up]},
        "confidence": confidence(eligible),
    }
    evidence = {"Cause": top.cited[:6], "Evidence": support.evidence if support else top.cited[:6],
                "The moment": [e["id"] for e in v.build_up]}
    feedback, problems = "", []
    for attempt in range(2):
        try:
            submitted, _ = run_agent(provider, name="producer", system=PRODUCER_SYSTEM,
                                     user=json.dumps(findings) + feedback, tools=[PRODUCER_TOOL], handlers={},
                                     submit="submit_explanation", max_tokens=6000, effort="low", board=board)
        except ProviderError as exc:
            if exc.code != "bad_output":  # provider outages still surface; a malformed draft falls back
                raise
            problems = [exc.message]
            board.log("producer", "rejected", f"draft {attempt + 1}: {exc.message}")
            continue
        beats = [b for b in submitted.get("beats", []) if isinstance(b, dict) and b.get("label") in evidence]
        explanation = {"confidence": findings["confidence"], "headline": str(submitted.get("headline", ""))[:140],
                       "beats": [{"label": b["label"], "claim_id": top.id, "evidence": evidence[b["label"]],
                                  "fan": str(b.get("fan", ""))[:300], "analyst": str(b.get("analyst", ""))[:400]} for b in beats],
                       "ruled_out": template["ruled_out"]}
        problems = check_grounded(explanation, board, v, roster)
        if not problems and explanation["beats"] and explanation["headline"]:
            return explanation, "claude", []
        feedback = "\n\nYour previous draft failed these checks; fix them: " + "; ".join(problems[:5])
        board.log("producer", "rejected", f"draft {attempt + 1} failed grounding ({len(problems)} problems)")
    return template, "template", problems


def run_agents(case: Case, provider: Provider) -> dict:
    """Claude investigator, sceptic and producer, orchestrated by Microsoft Agent Framework (../orchestration.py)."""
    from ..orchestration import run
    return run(case, "agents", provider)


def _fingerprint() -> str:
    import hashlib
    import inspect

    from .. import producer, sceptic
    blob = json.dumps([INVESTIGATOR_SYSTEM, SCEPTIC_SYSTEM, PRODUCER_SYSTEM, INVESTIGATOR_TOOLS, SCEPTIC_TOOLS,
                       PRODUCER_TOOL, MAX_TOOL_TURNS, inspect.getsource(producer), inspect.getsource(sceptic)],
                      sort_keys=True)
    return hashlib.sha1(blob.encode()).hexdigest()[:10]


# Cached results are reused only while prompts, tools, loop limits, sceptic tests and grounding rules are unchanged.
PROMPT_VERSION = _fingerprint()
