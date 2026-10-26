"""Beyond the Replay as an A2A agent: other agents (a broadcaster's production assistant, a club's content bot)
can ask it about any match over the Agent2Agent protocol.

The agent is a Microsoft Agent Framework agent served through agent_framework_a2a.A2AExecutor. It answers from
checked data only and never spends model credits: saved AI investigations, the statistics-only investigation
workflow, storylines and the studio pack. Agent card: /a2a/.well-known/agent-card.json; JSON-RPC: /a2a/.
"""
from __future__ import annotations

import os
import re

from agent_framework import AgentResponse, AgentResponseUpdate, BaseAgent, Content, Message

HELP = ("Ask me about a simulated match. Try: 'list matches', 'why was the goal scored in m300080?', "
        "'storylines in m300121', or 'presenter script for m300080'.")


class MatchAnalystAgent(BaseAgent):
    """Routes a plain-language request to the right checked source and answers in text."""

    def __init__(self, answer):
        super().__init__(name="beyond-the-replay", description="Explainable match intelligence for simulated football matches")
        self._answer = answer  # (text) -> str, provided by the app so this module has no import cycle

    async def run(self, messages=None, *, stream=False, session=None, function_invocation_kwargs=None, client_kwargs=None, **_):
        text = _last_text(messages)
        reply = self._answer(text)
        if stream:
            async def updates():
                yield AgentResponseUpdate(contents=[Content.from_text(reply)], role="assistant", agent_id=self.id)
            return updates()
        return AgentResponse(messages=[Message("assistant", [reply])], agent_id=self.id)


def _last_text(messages) -> str:
    if messages is None:
        return ""
    if isinstance(messages, str):
        return messages
    items = messages if isinstance(messages, (list, tuple)) else [messages]
    for m in reversed(items):
        if isinstance(m, str):
            return m
        text = getattr(m, "text", None)
        if text:
            return text
    return ""


def answer(text: str, *, index, public, match, investigate_saved, investigate_stats, narrative_en, pack_en) -> str:
    q = text.lower()
    ids = {m["id"] for m in index()}
    mid = next((x for x in re.findall(r"m\d{6}", q) if x in ids), None)
    if not mid:  # allow club names ("why did Highcross score?")
        for m in index():
            pm = public(m, m["id"])
            if pm["home_name"].lower() in q or pm["away_name"].lower() in q:
                mid = m["id"]
                break
    if "list" in q or "matches" in q and not mid:
        rows = [public(m, m["id"]) for m in index()]
        return "Matches (simulated):\n" + "\n".join(
            f"- {r['id']}: {r['home_name']} {r['score'][r['home']]}-{r['score'][r['away']]} {r['away_name']} "
            f"(featured goal {r['incident_minute']}')" for r in rows)
    if not mid:
        return HELP
    m = public(match(mid), mid)
    fixture = f"{m['home_name']} {m['score'][m['home']]}-{m['score'][m['away']]} {m['away_name']}"
    if any(w in q for w in ("story", "storyline", "building", "narrative")):
        nar = narrative_en(mid)
        lines = [f"{s['title']} ({s['status']}): {s['beats'][-1]['text']}" for s in nar["storylines"][:5]]
        return f"Storylines in {fixture}:\n- " + "\n- ".join(lines) + (f"\n{nar['summaries'][-1]['text']}" if nar["summaries"] else "")
    if any(w in q for w in ("script", "presenter", "recap", "pack", "autocue")):
        pack = pack_en(mid)
        return f"60-second presenter script for {fixture}:\n" + "\n".join(f"[{x['cue']}] {x['text']}" for x in pack["presenter"]["60s"]["lines"])
    saved = investigate_saved(mid)
    out = saved or investigate_stats(mid)
    source = f"AI agents ({out.get('model_label', 'Claude')}), every claim checked by code" if saved else "statistics-only investigation"
    ex = out["explanation"]
    beats = "\n".join(f"- {b['label']}: {b['analyst']}" for b in ex["beats"])
    ruled = "\n".join(f"- Ruled out: {r['statement']} ({r['reason']})" for r in ex["ruled_out"][:3])
    return (f"{fixture}, goal at {m['incident_minute']}'.\n{ex['headline']} (confidence: {ex['confidence']}; source: {source})\n"
            f"{beats}\n{ruled}\nSimulated match; names are fictional.")


def a2a_routes(agent: BaseAgent):
    """Starlette routes for the agent card and JSON-RPC endpoint (mounted at /a2a)."""
    from a2a.server.request_handlers import DefaultRequestHandler
    from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
    from a2a.server.tasks import InMemoryTaskStore
    from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
    from agent_framework_a2a import A2AExecutor

    base = os.environ.get("BTR_PUBLIC_URL", "http://localhost:8000").rstrip("/")
    card = AgentCard(
        name="Beyond the Replay match analyst",
        description="Explainable match intelligence for simulated football: why goals happened (checked AI investigations), "
                    "storylines, and broadcast-ready presenter scripts. Never spends model credits.",
        version="1.0.0", default_input_modes=["text"], default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=False),
        supported_interfaces=[AgentInterface(url=f"{base}/a2a/", protocol_binding="JSONRPC", protocol_version="1.0")],
        skills=[
            AgentSkill(id="why-goal", name="Why a goal happened", description="The checked cause of a match's decisive goal, and what was ruled out.",
                       tags=["football", "explainability"], examples=["Why was the goal scored in m300080?"]),
            AgentSkill(id="storylines", name="Storylines", description="What built up over the match: control spells, flank targeting, tiring defenders.",
                       tags=["football", "narrative"], examples=["storylines in m300121"]),
            AgentSkill(id="presenter-script", name="Presenter script", description="A 60-second autocue script with graphics cues.",
                       tags=["broadcast"], examples=["presenter script for m300080"]),
        ],
    )
    handler = DefaultRequestHandler(agent_executor=A2AExecutor(agent), task_store=InMemoryTaskStore(), agent_card=card)
    return [*create_agent_card_routes(card), *create_jsonrpc_routes(handler, "/")]
