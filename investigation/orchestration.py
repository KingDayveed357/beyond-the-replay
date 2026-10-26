"""The goal investigation as a Microsoft Agent Framework workflow.

    intake -> investigator -> sceptic -> verifier -> producer -> publish
                         \\______(sceptic off)______/

Each role is an Agent Framework executor. They hand one job down the graph and share an evidence board
(the job's `board`) plus workflow state (`ctx.set_state`), so every role sees exactly what the previous one
concluded. In "agents" mode the investigator, sceptic and producer are Claude tool-use agents; in
"deterministic" mode the same roles are statistics and rules. The verifier is always code.

Failure recovery: when a Claude agent times out, is rate-limited or returns malformed output, the workflow
does not fail. The deterministic version of that role takes over, the board records the hand-over, and the
result lists it under `orchestration.recovered`. Errors only the user can fix (a rejected key, an unsupported
model) still surface.
"""
from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass, field

from agent_framework import Case as Route, Default, Executor, WorkflowBuilder, WorkflowContext, handler

from phase0.investigators import Hypothesis, MatchView, StatInvestigator, _involves, verify
from phase0.observe import Case

from .board import Board, Claim
from .producer import check_grounded, produce, statement
from .sceptic import review
from .workflow import DEFAULT_WEIGHTS

FRAMEWORK = "Microsoft Agent Framework"


@dataclass
class Job:
    case: Case
    mode: str                       # "agents" | "deterministic"
    provider: object = None         # investigation.llm.provider.Provider in agents mode
    use_sceptic: bool = True
    sceptic_mode: str = "refute"
    weights: dict | None = None
    started: float = field(default_factory=time.perf_counter)
    view: MatchView | None = None
    tools: object = None
    board: Board | None = None
    explanation: dict | None = None
    extra: dict = field(default_factory=dict)
    path: list = field(default_factory=list)
    recovered: list = field(default_factory=list)

    def __deepcopy__(self, memo):
        """The framework snapshots each executor's input for its event log. A job carries live resources (the model
        client, its HTTP pool) that cannot be copied, so the snapshot is a reference: one job flows down the graph."""
        return self


def _recoverable(exc: Exception) -> bool:
    from .llm.provider import ProviderError
    return isinstance(exc, ProviderError) and (exc.retryable or exc.code == "bad_output")


def _recover(job: Job, role: str, exc) -> None:
    job.recovered.append({"role": role, "code": exc.code, "message": exc.message})
    job.board.log(role, "recovered", f"Claude {role} failed ({exc.code}); the statistics {role} took over")


class Intake(Executor):
    @handler
    async def start(self, job: Job, ctx: WorkflowContext[Job]) -> None:
        job.path.append(self.id)
        job.view = MatchView(job.case)
        job.board = Board(job.case.case_id, job.case.incident_id, job.mode)
        if job.mode == "agents":
            from .llm.tools import MatchTools
            job.tools = MatchTools(job.view, job.case.roster)
        ctx.set_state("case", {"match": job.case.case_id, "incident": job.case.incident_id, "mode": job.mode})
        await ctx.send_message(job)


class Investigator(Executor):
    @handler
    async def propose(self, job: Job, ctx: WorkflowContext[Job]) -> None:
        job.path.append(self.id)
        if job.mode == "agents":
            try:
                await asyncio.to_thread(self._claude, job)
            except Exception as exc:
                if not _recoverable(exc):
                    raise
                _recover(job, "investigator", exc)
                job.board.claims = []
                self._statistics(job, recovered=True)
        else:
            self._statistics(job)
        ctx.set_state("claims", [c.id for c in job.board.claims])
        await ctx.send_message(job)

    @staticmethod
    def _statistics(job: Job, recovered: bool = False) -> None:
        v, case = job.view, job.case
        hypotheses = StatInvestigator(job.weights or DEFAULT_WEIGHTS).investigate(case)
        for i, h in enumerate(hypotheses, 1):
            c = Claim(f"c{i}", h.kind, h.target, h.onset, "", list(h.cited),
                      "investigator (statistics, recovered)" if recovered else "investigator", h.score, h.score)
            c.statement = statement(c, v, case.roster)
            job.board.claims.append(c)
        job.board.log("investigator", "propose", f"{len(hypotheses)} candidate explanations from change-point and base-rate tests")

    @staticmethod
    def _claude(job: Job) -> None:
        from .language import club, minute
        from .llm.agents import INVESTIGATOR_SYSTEM, _claims_from, run_agent
        from .llm.tools import INVESTIGATOR_TOOLS
        v, tools, board, case = job.view, job.tools, job.board, job.case
        handlers = {"match_brief": tools.match_brief, "goal_build_up": tools.goal_build_up,
                    "statistical_screen": tools.statistical_screen, "duel_record": tools.duel_record,
                    "defender_decline": tools.defender_decline, "flank_profile": tools.flank_profile,
                    "flank_change": tools.flank_change}
        submitted, calls = run_agent(job.provider, name="investigator", system=INVESTIGATOR_SYSTEM,
                                     user=f"Investigate {club(v.A)}'s goal at {minute(v.t_inc)} (event {v.incident['id']}).",
                                     tools=INVESTIGATOR_TOOLS, handlers=handlers, submit="submit_hypotheses",
                                     max_tokens=8000, effort="medium", board=board)
        board.claims, job.extra["citations_dropped"] = _claims_from(submitted, tools, v, case.roster)
        if v.last_foul and not any(c.kind == "FOUL" for c in board.claims):
            c = Claim(f"c{len(board.claims) + 1}", "FOUL", v.last_foul["id"], None, "", [v.last_foul["id"]],
                      "code (the obvious story)", 0.5, 0.5)
            c.statement = statement(c, v, case.roster)
            board.claims.append(c)
        job.extra["investigator_tool_calls"] = len(calls)
        board.log("investigator", "propose", f"Claude proposed {len(board.claims)} causes after {len(calls)} tool calls")


class Sceptic(Executor):
    @handler
    async def challenge(self, job: Job, ctx: WorkflowContext[Job]) -> None:
        job.path.append(self.id)
        if job.mode == "agents":
            from .llm.agents import _sceptic
            try:
                job.extra["sceptic_notes"] = await asyncio.to_thread(_sceptic, job.provider, job.board, job.tools,
                                                                     job.view, job.case.roster)
            except Exception as exc:
                if not _recoverable(exc):
                    raise
                _recover(job, "sceptic", exc)
                review(job.board, job.view, job.case.roster, mode="refute")
                job.extra["sceptic_notes"] = ["rule-based sceptic stood in"]
        else:
            review(job.board, job.view, job.case.roster, mode=job.sceptic_mode)
        ctx.set_state("verdicts", {c.id: c.status for c in job.board.claims})
        await ctx.send_message(job)


class Verifier(Executor):
    """Code, never a model: every claim must be backed by the events it cites."""

    @handler
    async def check(self, job: Job, ctx: WorkflowContext[Job]) -> None:
        job.path.append(self.id)
        v, pruned = job.view, 0
        for c in job.board.claims:
            if job.mode == "agents":  # keep only citations that involve the claim
                h = Hypothesis(c.kind, c.target, c.score, c.onset, c.cited)
                relevant = [x for x in c.cited if x in v.by_id and _involves(h, v.by_id[x], v)]
                pruned += len(c.cited) - len(relevant)
                c.cited = relevant
            ok, _, notes = verify(Hypothesis(c.kind, c.target, c.score, c.onset, c.cited), v)
            c.verified, c.verification_notes = ok, notes
        rejected = sum(1 for c in job.board.claims if not c.verified)
        job.extra["citations_pruned"], job.extra["unverified_claims"] = pruned, rejected
        job.board.log("verifier", "check", f"{len(job.board.claims) - rejected} claims verified against events, {rejected} rejected"
                      + (f", {pruned} irrelevant citations removed" if pruned else ""))
        ctx.set_state("verified", [c.id for c in job.board.claims if c.verified])
        await ctx.send_message(job)


class Producer(Executor):
    @handler
    async def write(self, job: Job, ctx: WorkflowContext[Job]) -> None:
        job.path.append(self.id)
        v, board, roster = job.view, job.board, job.case.roster
        if job.mode == "agents":
            from .llm.agents import _producer
            try:
                job.explanation, source, problems = await asyncio.to_thread(_producer, job.provider, board, v, roster)
            except Exception as exc:
                if not _recoverable(exc):
                    raise
                _recover(job, "producer", exc)
                job.explanation, source, problems = produce(board, v, roster), "template", [exc.message]
            job.extra["producer_source"], job.extra["producer_problems"] = source, problems
            board.log("producer", "write", f"{job.explanation['confidence']} explanation written by "
                      + ("Claude" if source == "claude" else "the template (Claude's draft failed grounding)"))
        else:
            explanation = produce(board, v, roster)
            problems = check_grounded(explanation, board, v, roster)
            if problems:  # never ship an ungrounded explanation
                board.log("producer", "blocked", "; ".join(problems[:3]))
                explanation = {"confidence": "none", "headline": "Explanation withheld: it failed the grounding check.",
                               "beats": [], "ruled_out": [], "problems": problems}
            else:
                board.log("producer", "write", f"{explanation['confidence']} explanation from {len(explanation['beats'])} grounded beats")
            job.explanation = explanation
        await ctx.send_message(job)


class Publish(Executor):
    @handler
    async def publish(self, job: Job, ctx: WorkflowContext[None, dict]) -> None:
        job.path.append(self.id)
        board = job.board
        out = board.to_dict()
        out["explanation"] = job.explanation
        out["ranking"] = [list(c.key) for c in board.ranked() if c.verified]
        out["elapsed_ms"] = round((time.perf_counter() - job.started) * 1000, 2 if job.mode != "agents" else 1)
        if job.mode == "agents":
            from .llm.provider import SUPPORTED_MODELS
            p, x = job.provider, job.extra
            out.update({
                "sceptic": "claude", "model": p.model, "model_label": SUPPORTED_MODELS[p.model]["label"], "key_source": p.source,
                "usage": p.usage.to_dict(), "producer_source": x.get("producer_source", "template"),
                "audit": {"citations_dropped": x.get("citations_dropped", 0), "citations_pruned": x.get("citations_pruned", 0),
                          "unverified_claims": x.get("unverified_claims", 0), "sceptic_notes": x.get("sceptic_notes", []),
                          "producer_problems": x.get("producer_problems", [])[:5],
                          "investigator_tool_calls": x.get("investigator_tool_calls", 0)},
            })
        else:
            out["sceptic"] = job.sceptic_mode if job.use_sceptic else "off"
        out["orchestration"] = {"framework": FRAMEWORK, "workflow": "goal-investigation", "path": job.path,
                                "recovered": job.recovered}
        await ctx.yield_output(out)


def build_workflow():
    intake, inv, sceptic, verifier = Intake("intake"), Investigator("investigator"), Sceptic("sceptic"), Verifier("verifier")
    producer, publish = Producer("producer"), Publish("publish")
    return (WorkflowBuilder(start_executor=intake, name="goal-investigation",
                            description="Investigator, sceptic, code verifier and producer over one evidence board")
            .add_edge(intake, inv)
            .add_switch_case_edge_group(inv, [Route(condition=lambda job: job.use_sceptic, target=sceptic), Default(target=verifier)])
            .add_edge(sceptic, verifier)
            .add_edge(verifier, producer)
            .add_edge(producer, publish)
            .build())


def describe() -> dict:
    """The graph, for the UI and docs."""
    return {"framework": FRAMEWORK, "workflow": "goal-investigation",
            "executors": [
                {"id": "intake", "role": "Builds the match view and the shared evidence board"},
                {"id": "investigator", "role": "Proposes causes with tools (Claude, or change-point statistics)"},
                {"id": "sceptic", "role": "Tries to break every claim; the booking is always tested"},
                {"id": "verifier", "role": "Code: each claim must be backed by the events it cites"},
                {"id": "producer", "role": "Writes the explanation; ungrounded text is rejected"},
                {"id": "publish", "role": "Assembles the result, audit trail and recovery notes"}],
            "edges": [["intake", "investigator"], ["investigator", "sceptic", "sceptic on"],
                      ["investigator", "verifier", "sceptic off"], ["sceptic", "verifier"], ["verifier", "producer"],
                      ["producer", "publish"]],
            "recovery": "A failed Claude role hands over to its deterministic counterpart; the result records it."}


def _run_sync(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    box = {}  # called from inside an event loop: run on a private loop in a helper thread

    def target():
        try:
            box["r"] = asyncio.run(coro)
        except BaseException as exc:  # noqa: BLE001 - re-raised in the caller's thread
            box["e"] = exc
    t = threading.Thread(target=target)
    t.start()
    t.join()
    if "e" in box:
        raise box["e"]
    return box["r"]


def run(case: Case, mode: str, provider=None, *, use_sceptic: bool = True, sceptic_mode: str = "refute",
        weights: dict | None = None) -> dict:
    job = Job(case, mode, provider, use_sceptic if mode != "agents" else True, sceptic_mode, weights)
    try:
        result = _run_sync(build_workflow().run(job))
    except Exception as exc:  # surface the role's own error (e.g. a rejected key), not the framework's wrapper
        cause = exc
        while cause.__cause__ is not None and not _is_provider_error(cause):
            cause = cause.__cause__
        raise cause from None if cause is not exc else exc
    outputs = result.get_outputs()
    if not outputs:
        raise RuntimeError(f"investigation workflow ended without a result: {result.get_final_state()}")
    return outputs[0]


def _is_provider_error(exc) -> bool:
    from .llm.provider import ProviderError
    return isinstance(exc, ProviderError)
