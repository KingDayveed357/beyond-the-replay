"""Half-time and full-time recaps, grounded in the match timeline.

facts() distils the timeline into a small, checkable fact sheet. template_recap() writes a recap
from it deterministically. claude_recap() asks Claude to write it for a fan or an analyst; the
result must pass check_recap() (every player name, minute and percentage must appear in the fact
sheet) or the labelled template is used instead.
"""
from __future__ import annotations

import json
import re

PHASES = {"ht": 45, "ft": 95}
MINUTE_RE = re.compile(r"\b(\d{1,3})(?:'|’| min|(?:st|nd|rd|th)[- ]minute)")
MINUTE_WORD_RE = re.compile(r"(?:minuto|minute|الدقيقة)\s+(\d{1,3})|\b(\d{1,3})(?:e|ème|º|°)\s+minute", re.IGNORECASE)
PERCENT_RE = re.compile(r"\b(\d{1,3})\s?%")
SCORE_RE = re.compile(r"(?<![\d.])\d{1,2}-\d{1,2}(?![\d.])")
LEAD_RE = re.compile(r"\b(trail|trails|trailing|lead|leads|leading)\b", re.IGNORECASE)


def facts(match: dict, timeline: dict, phase: str) -> dict:
    upto = PHASES[phase]
    names = {match["home"]: match["home_name"], match["away"]: match["away_name"]}
    states = [s for s in timeline["states"] if s["minute"] <= upto]
    final = states[-1]
    moments = [m for m in timeline["moments"] if m["minute"] <= upto]
    roster = match["roster"]
    pname = lambda pid: roster.get(pid, {}).get("name") if pid else None
    goals = [{"minute": m["minute"], "team": names[m["team"]], "scorer": pname(m["player_id"]),
              "assist": pname(m.get("assist_id")), "xg": m.get("xg"), "score_after": m["score"]}
             for m in moments if m["type"] == "goal"]
    chances = [{"minute": m["minute"], "team": names[m["team"]], "player": pname(m["player_id"]), "xg": m["xg"]}
               for m in moments if m["type"] == "big_chance"]
    swings = [{"minute": m["minute"], "team": names[m["team"]]} for m in moments if m["type"] == "momentum"]
    cards = [{"minute": m["minute"], "team": names[m["team"]], "player": pname(m["player_id"])}
             for m in moments if m["type"] == "card"]
    team_stats = {names[t]: {k: v[k] for k in ("goals", "shots", "on_target", "xg", "possession", "pass_accuracy",
                                                 "field_tilt", "control")}
                  for t, v in final["teams"].items()}
    standouts = sorted(timeline["players"].values(),
                       key=lambda p: -(3 * p["goals"] + 2 * p["assists"] + p["xg"] + p["duels_won"] / 10))[:4]
    return {
        "phase": "half-time" if phase == "ht" else "full-time", "minute": final["minute"],
        "home": names[match["home"]], "away": names[match["away"]],
        "score": f"{final['teams'][match['home']]['goals']}-{final['teams'][match['away']]['goals']}",
        "venue": match.get("metadata", {}).get("venue"), "goals": goals, "big_chances": chances,
        "momentum_swings": swings, "cards": cards, "team_stats": team_stats,
        "chaos_now": final["chaos"], "tempo_passes_per_min": final["tempo_passes_per_min"],
        "standout_players": [{"name": p["name"], "team": names[p["team"]], "goals": p["goals"], "assists": p["assists"],
                              "xg": p["xg"], "pass_accuracy": p["pass_accuracy"], "duels_won": p["duels_won"]}
                             for p in standouts],
        "simulated": True,
    }


def template_recap(f: dict) -> dict:
    h, a = f["home"], f["away"]
    hs, as_ = f["team_stats"][h], f["team_stats"][a]
    hg, ag = (int(x) for x in f["score"].split("-"))
    lead = f"{h} lead {a} {f['score']}" if hg > ag else f"{a} lead {h} {ag}-{hg}" if ag > hg else f"{h} and {a} are level at {f['score']}"
    if f["phase"] == "full-time":
        lead = (f"{h} beat {a} {f['score']}" if hg > ag else f"{a} won {ag}-{hg} at {f['venue'] or h}" if ag > hg
                else f"{h} and {a} drew {f['score']}")
    goal_bits = [f"{g['scorer']} ({g['minute']}')" for g in f["goals"]]
    para1 = f"{lead}." + (f" Goals: {', '.join(goal_bits)}." if goal_bits else " No goals yet.")
    better = h if hs["control"] >= as_["control"] else a
    para2 = (f"{better} controlled more of the game: {hs['possession']}% possession for {h} against {as_['possession']}% for {a}, "
             f"and {hs['shots']} shots to {as_['shots']}.")
    star = f["standout_players"][0] if f["standout_players"] else None
    para3 = f"Standout: {star['name']} ({star['team']})." if star else ""
    return {"headline": lead, "paragraphs": [p for p in (para1, para2, para3) if p], "source": "template"}


def check_recap(recap: dict, f: dict, roster_names: set) -> list:
    """Problems with a recap: names, minutes or percentages that the fact sheet does not contain."""
    blob = json.dumps(f, ensure_ascii=False)
    allowed_minutes = {str(x) for x in re.findall(r'"minute": (\d+)', blob)}
    allowed_pct = {str(v) for t in f["team_stats"].values() for k, v in t.items() if k in ("possession", "pass_accuracy", "field_tilt")}
    allowed_pct |= {str(p["pass_accuracy"]) for p in f["standout_players"] if p["pass_accuracy"] is not None}
    fact_names = {n for n in roster_names if n in blob}
    allowed_scores = {f["score"], "0-0"} | {g["score_after"] for g in f["goals"]}
    allowed_scores |= {"-".join(reversed(s.split("-"))) for s in allowed_scores}
    level = f["score"].split("-")[0] == f["score"].split("-")[1]
    problems = []
    for text in [recap.get("headline", "")] + list(recap.get("paragraphs", [])):
        for sc in SCORE_RE.findall(text):
            if sc not in allowed_scores:
                problems.append(f"scoreline {sc} is not in the facts")
        if level and LEAD_RE.search(text):
            problems.append(f"says a side leads or trails, but the score is level at {f['score']}")
        found = MINUTE_RE.findall(text) + [a or b for a, b in MINUTE_WORD_RE.findall(text)]
        for m in found:
            if m not in allowed_minutes:
                problems.append(f"minute {m}' is not in the facts")
        for m in PERCENT_RE.findall(text):
            if m not in allowed_pct:
                problems.append(f"{m}% is not in the facts")
        for n in roster_names - fact_names:
            if n in text:
                problems.append(f"{n} is not in the facts")
    # Names written in another script (for example transliterated into Arabic) would slip past the name
    # check, so every goal scorer must appear exactly as spelled in the facts.
    full = " ".join([recap.get("headline", "")] + list(recap.get("paragraphs", [])))
    for g in f["goals"]:
        if g["scorer"] and g["scorer"] not in full:
            problems.append(f"goal scorer {g['scorer']} is not named as spelled in the facts")
    return problems


RECAP_TOOL = {"name": "submit_recap", "description": "Submit the recap. Call exactly once.", "strict": True,
              "input_schema": {"type": "object", "additionalProperties": False, "required": ["headline", "paragraphs"],
                               "properties": {"headline": {"type": "string"},
                                              "paragraphs": {"type": "array", "items": {"type": "string"}}}}}

VOICES = {
    "fan": "Write for a casual fan: vivid, warm, no jargon, short sentences. Headline under 12 words; 2-3 short paragraphs.",
    "analyst": "Write for a data-hungry analyst: precise, tactical, quote the key numbers (xG, possession, field tilt, control). "
               "Headline under 14 words; 3 short paragraphs.",
}


def claude_recap(provider, f: dict, voice: str, language: str, roster_names: set) -> dict:
    from investigation.board import Board
    from investigation.llm.agents import run_agent
    from investigation.llm.provider import ProviderError

    system = ("You write the official match recap for a broadcast and streaming app. This is a simulated match with real "
              "Premier League squads. Use only the facts you are given: every player name, minute and number must come from "
              f"them. Never compute new percentages. {VOICES[voice]} Write in {language}, using Western digits (0-9) "
              "and keeping every player and club name exactly as given. Call submit_recap exactly once.")
    feedback = ""
    for attempt in range(2):
        try:
            out, _ = run_agent(provider, name="recap writer", system=system, user=json.dumps(f, ensure_ascii=False) + feedback,
                               tools=[RECAP_TOOL], handlers={}, submit="submit_recap", max_tokens=6000, effort="low",
                               board=Board("recap", "recap", "agents"))
        except ProviderError as exc:
            if exc.code != "bad_output":
                raise
            continue
        recap = {"headline": str(out.get("headline", ""))[:160], "paragraphs": [str(p)[:900] for p in out.get("paragraphs", [])][:4]}
        problems = check_recap(recap, f, roster_names)
        if not problems and recap["headline"] and recap["paragraphs"]:
            return recap | {"source": "claude", "model": provider.model}
        feedback = "\n\nYour previous draft failed these checks; fix them: " + "; ".join(problems[:6])
    return template_recap(f) | {"note": "Claude's draft failed the fact check, so this is the template version."}
