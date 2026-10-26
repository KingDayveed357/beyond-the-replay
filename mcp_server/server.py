"""MCP server: Beyond the Replay's match intelligence as tools for any MCP client
(GitHub Copilot agent mode in VS Code, Claude, or another agent).

All tools are read-only and work on the same simulated matches and pipeline as the web app.
They never expose the hidden answer key and never spend model credits: "why_goal" runs the
statistics-only investigation.

Run (stdio):  python -m mcp_server
"""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from analytics.i18n import LANGUAGES
from investigation.workflow import investigate
from server.app import case_for, index, match, public, timeline_in

mcp = MCPServer(
    name="beyond-the-replay",
    title="Beyond the Replay match intelligence",
    instructions=("Simulated football matches (fictional clubs and players, invented events). Use list_matches first, then "
                  "match_state, key_moments, player_summary, why_goal or overlay_track. Minutes are 1-95."),
    version="1.0",
)


def _summary(m: dict) -> dict:
    return {"match_id": m["id"], "fixture": f"{m['home_name']} {m['score'][m['home']]}-{m['score'][m['away']]} {m['away_name']}",
            "venue": m.get("metadata", {}).get("venue"), "featured_goal_minute": m["incident_minute"], "simulated": True}


@mcp.tool(description="List the available simulated matches with final score, venue and the featured goal.")
def list_matches() -> list:
    return [_summary(public(m, m["id"])) for m in index()]


@mcp.tool(description="Score and team stats (possession, shots, xG, pass accuracy, territory, pressing, control) at a given minute.")
def match_state(match_id: str, minute: int = 90) -> dict:
    states = timeline_in(match_id, "en")["states"]
    s = states[min(max(minute, 1), len(states)) - 1]
    m = public(match(match_id), match_id)
    names = {m["home"]: m["home_name"], m["away"]: m["away_name"]}
    return {"minute": s["minute"], "teams": {names[t]: v for t, v in s["teams"].items()},
            "momentum_favours": names[m["home"]] if s["momentum"] > 0 else names[m["away"]],
            "chaos_0_to_100": s["chaos"], "tempo_passes_per_min": s["tempo_passes_per_min"]}


@mcp.tool(description="Key moments (goals, big chances, bookings, momentum swings, standout passes) up to a minute, "
                      "each with why it matters. lang: en, es, fr, pt or ar.")
def key_moments(match_id: str, up_to_minute: int = 95, lang: str = "en") -> list:
    if lang not in LANGUAGES:
        raise ValueError(f"lang must be one of {', '.join(LANGUAGES)}")
    return [{"minute": x["minute"], "type": x["type"], "headline": x["headline"], "why": x["why"]}
            for x in timeline_in(match_id, lang)["moments"] if x["minute"] <= up_to_minute]


@mcp.tool(description="One player's match: touches, passing, average pass difficulty, duels, defending, shots, xG, "
                      "goals, assists, top speed, distance carried.")
def player_summary(match_id: str, player_name: str) -> dict:
    players = timeline_in(match_id, "en")["players"]
    hits = [p for p in players.values() if player_name.lower() in p["name"].lower()]
    if not hits:
        raise ValueError(f"no player matching {player_name!r}; try a surname")
    return hits[0]


@mcp.tool(description="Why the featured goal happened: candidate causes, what was ruled out and why, and the evidence. "
                      "Uses the statistics-only investigation (no AI model, no cost).")
def why_goal(match_id: str) -> dict:
    m = match(match_id)
    out = public(investigate(case_for(match_id, m["incident_id"])), match_id)
    return {"goal_minute": m["incident_minute"], "headline": out["explanation"]["headline"],
            "confidence": out["explanation"]["confidence"],
            "explanation": [b["analyst"] for b in out["explanation"]["beats"]],
            "ruled_out": [{"claim": r["statement"], "reason": r["reason"]} for r in out["explanation"]["ruled_out"]]}


@mcp.tool(description="Timed overlay cues (goal graphics, lower thirds, player name tags with speed or distance) "
                      "between two minutes, ready for a graphics engine. lang: en, es, fr, pt or ar.")
def overlay_track(match_id: str, from_minute: int = 1, to_minute: int = 95, lang: str = "en") -> list:
    if lang not in LANGUAGES:
        raise ValueError(f"lang must be one of {', '.join(LANGUAGES)}")
    lo, hi = (from_minute - 1) * 60, to_minute * 60
    return [c for c in timeline_in(match_id, lang)["cues"] if lo <= c["t_in"] < hi]


def main():
    mcp.run("stdio")
