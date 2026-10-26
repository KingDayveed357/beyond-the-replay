"""LLM agent tests with a scripted fake model. No test here makes a network call."""
import json
import logging
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import mock

import anthropic
import httpx2
from fastapi.testclient import TestClient

from investigation.llm import agents
from investigation.llm.agents import run_agents
from investigation.llm.provider import Ledger, Provider, ProviderError, Usage
from investigation.llm.tools import MatchTools
from phase0.investigators import MatchView
from server import app as app_module
from server.inference import InferencePolicy
from tests.test_phase0 import first_case

FAKE_KEY = "sk-ant-test-0000000000000000000000"


def use(name, inp, i=0):
    return NS(type="tool_use", id=f"tu_{name}_{i}", name=name, input=inp)


def reply(*blocks, stop="tool_use", inp=1000, out=200):
    return NS(content=list(blocks), stop_reason=stop, usage=NS(input_tokens=inp, output_tokens=out, cache_read_input_tokens=0))


class FakeClient:
    """Plays back scripted responses. Each script entry is a response or a function of the request."""

    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        self.messages = NS(create=self._create)
        self.models = NS(retrieve=lambda model: NS(id=model, display_name="Claude Haiku 5.5"))

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        if not self.script:
            raise AssertionError("model called more often than scripted")
        nxt = self.script.pop(0)
        return nxt(kwargs) if callable(nxt) else nxt


def api_error(cls, status, message="error"):
    req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls(message, response=httpx2.Response(status, request=req), body=None)


class Fixture:
    def __init__(self):
        _, _, self.case = first_case(100011)
        self.view = MatchView(self.case)
        screen = MatchTools(self.view, self.case.roster).statistical_screen()
        top = screen["candidates"][0]
        self.top_key = (top["kind"], top["target"])
        self.top_ids = top["event_ids"]
        self.top_onset = top["change_minute"]

    def investigator(self, cited=None, kind=None, target=None):
        return [
            reply(use("match_brief", {}), use("statistical_screen", {}, 1)),
            reply(use("submit_hypotheses", {"hypotheses": [{
                "kind": kind or self.top_key[0], "target": target or self.top_key[1], "onset_minute": self.top_onset,
                "cited_event_ids": cited if cited is not None else self.top_ids, "reasoning": "Clear late decline."}]})),
        ]

    def sceptic(self, reviews, tested=("c1", "c2")):
        return [
            reply(*[use("run_standard_tests", {"claim_id": c}, i) for i, c in enumerate(tested)]),
            reply(use("submit_reviews", {"reviews": reviews})),
        ]

    @staticmethod
    def producer(headline="It wasn't the booking.", fan="The defender faded late on."):
        return reply(use("submit_explanation", {"headline": headline, "beats": [
            {"label": "Cause", "fan": fan, "analyst": fan},
            {"label": "The moment", "fan": "The move finished in the box.", "analyst": "A short move ended in a goal."}]}))


class AgentWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()

    def run_with(self, script):
        client = FakeClient(script)
        provider = Provider(None, "claude-haiku-5-5", "server", client=client)
        return run_agents(self.f.case, provider), client

    def test_full_workflow_produces_verified_grounded_result(self):
        out, client = self.run_with(self.f.investigator() + self.f.sceptic(
            [{"claim_id": "c1", "verdict": "upheld", "rationale": "Tests hold."},
             {"claim_id": "c2", "verdict": "refuted", "rationale": "Play reset."}]) + [self.f.producer()])
        self.assertEqual(tuple(out["ranking"][0]), self.f.top_key)
        foul = next(c for c in out["claims"] if c["kind"] == "FOUL")
        self.assertEqual(foul["status"], "refuted")
        self.assertEqual(out["producer_source"], "claude")
        self.assertEqual(out["usage"]["calls"], 5)
        self.assertEqual(out["mode"], "agents")
        for req in client.requests:  # current API rules: model pinned, no sampling parameters
            self.assertEqual(req["model"], "claude-haiku-5-5")
            self.assertNotIn("temperature", req)

    def test_citations_not_returned_by_tools_are_dropped(self):
        out, _ = self.run_with(self.f.investigator(cited=["e99999", "e00001"]) + self.f.sceptic(
            [{"claim_id": "c1", "verdict": "upheld", "rationale": "x"}]) + [self.f.producer()])
        self.assertGreaterEqual(out["audit"]["citations_dropped"], 1)
        claim = next(c for c in out["claims"] if c["id"] == "c1")
        self.assertNotIn("e99999", claim["cited"])

    def test_refuted_verdict_needs_a_failing_test(self):
        out, _ = self.run_with(self.f.investigator() + self.f.sceptic(
            [{"claim_id": "c1", "verdict": "refuted", "rationale": "I just don't buy it."},
             {"claim_id": "c2", "verdict": "refuted", "rationale": "Play reset."}]) + [self.f.producer()])
        c1 = next(c for c in out["claims"] if c["id"] == "c1")
        tests = [ch for ch in c1["challenges"] if ch["source"] == "test"]
        if all(t["verdict"] == "upheld" for t in tests):
            self.assertEqual(c1["status"], "weakened")
            self.assertTrue(any("downgraded" in n for n in out["audit"]["sceptic_notes"]))

    def test_booking_is_tested_even_if_the_sceptic_skips_it(self):
        out, _ = self.run_with(self.f.investigator() + self.f.sceptic(
            [{"claim_id": "c1", "verdict": "upheld", "rationale": "x"}], tested=("c1",)) + [self.f.producer()])
        foul = next(c for c in out["claims"] if c["kind"] == "FOUL")
        self.assertNotEqual(foul["status"], "proposed")
        self.assertTrue(any("code ran" in n for n in out["audit"]["sceptic_notes"]))

    def test_ungrounded_producer_falls_back_to_labelled_template(self):
        outsider = next(r["name"] for p, r in self.f.case.roster.items() if r["role"] == "GK" and r["team"] == self.f.view.A)
        bad = self.f.producer(fan=f"{outsider} froze at 3'.")
        out, _ = self.run_with(self.f.investigator() + self.f.sceptic(
            [{"claim_id": "c1", "verdict": "upheld", "rationale": "x"},
             {"claim_id": "c2", "verdict": "refuted", "rationale": "y"}]) + [bad, bad])
        self.assertEqual(out["producer_source"], "template")
        self.assertTrue(out["audit"]["producer_problems"])
        self.assertNotIn(outsider, json.dumps(out["explanation"]))

    def test_agent_loop_is_bounded_and_the_workflow_recovers(self):
        endless = [reply(use("match_brief", {}, i)) for i in range(agents.MAX_TOOL_TURNS)]
        out, client = self.run_with(endless + self.f.sceptic([{"claim_id": "c1", "verdict": "upheld", "rationale": "ok"}])
                                    + [self.f.producer()])
        investigator_calls = [r for r in client.requests if r["system"] == agents.INVESTIGATOR_SYSTEM]
        self.assertEqual(len(investigator_calls), agents.MAX_TOOL_TURNS)
        recovered = out["orchestration"]["recovered"]
        self.assertEqual([(r["role"], r["code"]) for r in recovered], [("investigator", "bad_output")])
        self.assertTrue(all(c["proposed_by"] == "investigator (statistics, recovered)" for c in out["claims"]))
        self.assertTrue(out["ranking"])

    def test_workflow_path_and_framework_are_recorded(self):
        out, _ = self.run_with(self.f.investigator() + self.f.sceptic(
            [{"claim_id": "c1", "verdict": "upheld", "rationale": "ok"}]) + [self.f.producer()])
        self.assertEqual(out["orchestration"]["framework"], "Microsoft Agent Framework")
        self.assertEqual(out["orchestration"]["path"], ["intake", "investigator", "sceptic", "verifier", "producer", "publish"])
        self.assertEqual(out["orchestration"]["recovered"], [])

    def test_sceptic_timeout_hands_over_to_the_rule_based_sceptic(self):
        def timeout(_):
            raise anthropic.APITimeoutError(request=httpx2.Request("POST", "https://api.anthropic.com"))
        out, _ = self.run_with(self.f.investigator() + [timeout, self.f.producer()])
        self.assertEqual([r["role"] for r in out["orchestration"]["recovered"]], ["sceptic"])
        self.assertTrue(all(c["status"] != "proposed" for c in out["claims"]))

    def test_jobs_carrying_uncopyable_clients_run(self):
        """Regression: the framework deep-copies executor inputs; a real HTTP client holds locks."""
        import threading
        client = FakeClient(self.f.investigator() + self.f.sceptic([{"claim_id": "c1", "verdict": "upheld", "rationale": "ok"}])
                            + [self.f.producer()])
        client.lock = threading.RLock()
        out = run_agents(self.f.case, Provider(None, "claude-haiku-5-5", "server", client=client))
        self.assertTrue(out["ranking"])

    def test_errors_only_the_user_can_fix_still_surface(self):
        def rejected(_):
            raise api_error(anthropic.AuthenticationError, 401)
        with self.assertRaises(ProviderError) as ctx:
            self.run_with([rejected])
        self.assertEqual(ctx.exception.code, "auth")

    def test_tool_errors_are_returned_to_the_model_not_raised(self):
        script = [reply(use("duel_record", {"defender_id": "NOPE", "from_minute": 1, "to_minute": 90}))] + self.f.investigator()[1:]
        script += self.f.sceptic([{"claim_id": "c1", "verdict": "upheld", "rationale": "x"}]) + [self.f.producer()]
        out, client = self.run_with(script)
        second = client.requests[1]["messages"][-1]["content"][0]
        self.assertTrue(second["is_error"])
        self.assertTrue(out["ranking"])


class ProviderTests(unittest.TestCase):
    def provider_raising(self, exc):
        client = NS(messages=NS(create=mock.Mock(side_effect=exc)), models=NS(retrieve=mock.Mock(side_effect=exc)))
        return Provider(None, "claude-haiku-5-5", "byok", client=client)

    def test_errors_map_to_explicit_codes(self):
        cases = [
            (api_error(anthropic.AuthenticationError, 401), "auth", 401),
            (api_error(anthropic.RateLimitError, 429), "rate_limited", 429),
            (api_error(anthropic.BadRequestError, 400, "Your credit balance is too low to access the API."), "credits", 402),
            (api_error(anthropic.BadRequestError, 400, "messages: bad shape"), "bad_request", 502),
            (api_error(anthropic.InternalServerError, 500), "provider_unavailable", 503),
            (anthropic.APITimeoutError(request=httpx2.Request("POST", "https://api.anthropic.com")), "timeout", 504),
            (anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com")), "connection", 503),
        ]
        for exc, code, status in cases:
            with self.assertRaises(ProviderError) as ctx:
                self.provider_raising(exc).create(max_tokens=10, messages=[])
            self.assertEqual((ctx.exception.code, ctx.exception.status), (code, status))
            with self.assertRaises(ProviderError):
                self.provider_raising(exc).test()

    def test_refusal_is_explicit(self):
        client = FakeClient([reply(NS(type="text", text=""), stop="refusal")])
        with self.assertRaises(ProviderError) as ctx:
            Provider(None, "claude-haiku-5-5", "server", client=client).create(max_tokens=10, messages=[])
        self.assertEqual(ctx.exception.code, "refusal")

    def test_unsupported_model_and_missing_key(self):
        with self.assertRaises(ProviderError) as ctx:
            Provider(FAKE_KEY, "gpt-5", "byok")
        self.assertEqual(ctx.exception.code, "unsupported_model")
        with self.assertRaises(ProviderError) as ctx:
            Provider(None, "claude-haiku-5-5", "server")
        self.assertEqual(ctx.exception.code, "not_configured")

    def test_usage_cost_is_an_estimate_from_list_prices(self):
        u = Usage()
        u.add(NS(input_tokens=1_000_000, output_tokens=1_000_000, cache_read_input_tokens=0), "claude-haiku-5-5")
        self.assertAlmostEqual(u.cost_usd_estimate, 0.60)
        self.assertIn("estimated", u.to_dict()["cost_basis"])


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.tmp = tempfile.TemporaryDirectory()
        self.made = []
        good = lambda: (self.f.investigator() + self.f.sceptic(
            [{"claim_id": "c1", "verdict": "upheld", "rationale": "x"},
             {"claim_id": "c2", "verdict": "refuted", "rationale": "y"}]) + [self.f.producer()])

        def factory(key, model, source):
            self.made.append((source, model, key == FAKE_KEY))
            return Provider(None, model, source, client=FakeClient(good()))

        self.policy = InferencePolicy(Path(self.tmp.name) / "cache", Path(self.tmp.name) / "rt", factory)
        self.env = mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "server-key-placeholder"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def run_policy(self, **kw):
        args = dict(client_id="1.2.3.4", fresh=False, byok_key=None, byok_model=None) | kw
        return self.policy.investigate(self.f.case, **args)

    def test_server_runs_are_cached_and_reused(self):
        first = self.run_policy()
        second = self.run_policy()
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])
        self.assertEqual(len(self.made), 1)
        self.assertGreater(self.policy.ledger.spent_usd, 0)

    def test_budget_cap_blocks_fresh_server_runs(self):
        self.policy.ledger.spent_usd = self.policy.ledger.cap_usd
        with self.assertRaises(ProviderError) as ctx:
            self.run_policy(fresh=True)
        self.assertEqual(ctx.exception.code, "budget_exhausted")

    def test_per_client_fresh_run_limit(self):
        with mock.patch("server.inference.FRESH_RUNS_PER_HOUR", 1):
            self.run_policy(fresh=True)
            with self.assertRaises(ProviderError) as ctx:
                self.run_policy(fresh=True)
            self.assertEqual(ctx.exception.code, "client_limit")

    def test_byok_is_isolated(self):
        out = self.run_policy(byok_key=FAKE_KEY, byok_model="claude-sonnet-5-5")
        self.assertEqual(out["key_source"], "byok")
        self.assertEqual(self.made[-1], ("byok", "claude-sonnet-5-5", True))
        self.assertEqual(self.policy.ledger.spent_usd, 0)  # not charged to the server budget
        self.assertIsNone(self.policy.cached(self.f.case.case_id, self.f.case.incident_id, "claude-sonnet-5-5"))
        self.assertNotIn(FAKE_KEY, json.dumps(out))

    def test_server_key_cannot_be_pointed_at_other_models(self):
        with self.assertRaises(ProviderError) as ctx:
            self.run_policy(byok_model="claude-sonnet-5-5")
        self.assertEqual(ctx.exception.code, "byok_required")

    def test_missing_server_key_is_a_clear_error(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
            with self.assertRaises(ProviderError) as ctx:
                self.run_policy(fresh=True)
        self.assertEqual(ctx.exception.code, "not_configured")


class ApiSecurityTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.client = TestClient(app_module.app)
        self.records = []
        handler = logging.Handler()
        handler.emit = lambda r: self.records.append(handler.format(r))
        handler.addFilter(app_module.RedactKeys())
        logging.getLogger().addHandler(handler)
        self.addCleanup(logging.getLogger().removeHandler, handler)
        script = lambda: (self.f.investigator() + self.f.sceptic(
            [{"claim_id": "c1", "verdict": "upheld", "rationale": "x"}]) + [self.f.producer()])
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        policy = InferencePolicy(Path(tmp.name) / "c", Path(tmp.name) / "r",
                                 lambda key, model, source: Provider(None, model, source, client=FakeClient(script())))
        patcher = mock.patch.object(app_module, "policy", policy)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_provider_status_exposes_no_credentials(self):
        body = self.client.get("/api/provider").text
        self.assertNotIn("sk-ant", body)
        data = json.loads(body)
        self.assertIn("claude-haiku-5-5", [m["id"] for m in data["models"]])
        self.assertIn("server_key_configured", data)

    def test_byok_key_never_appears_in_responses_or_logs(self):
        m = app_module.index()[0]
        case = app_module.case_for(m["id"], m["incident_id"])
        self.f.case, self.f.view = case, MatchView(case)
        screen = MatchTools(self.f.view, case.roster).statistical_screen()["candidates"][0]
        self.f.top_key, self.f.top_ids, self.f.top_onset = (screen["kind"], screen["target"]), screen["event_ids"], screen["change_minute"]
        res = self.client.post(f"/api/matches/{m['id']}/incidents/{m['incident_id']}/investigations?mode=agents",
                               headers={"X-BYOK-Key": FAKE_KEY})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertNotIn(FAKE_KEY, res.text)
        logging.getLogger("btr").info("debug %s", FAKE_KEY)  # even an accidental log line is redacted
        self.assertFalse(any(FAKE_KEY in r for r in self.records))

    def test_provider_errors_become_structured_json(self):
        with mock.patch.object(app_module, "Provider", side_effect=ProviderError("auth", "The API key was rejected.", 401)):
            res = self.client.post("/api/provider/test", headers={"X-BYOK-Key": FAKE_KEY})
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["detail"]["code"], "auth")
        self.assertNotIn(FAKE_KEY, res.text)



class OverloadDetectorTests(unittest.TestCase):
    """flank_change must fire on a planted overload's flank and stay quiet when the cause is fatigue."""

    @staticmethod
    def case_with(kind):
        from phase0.engine import make_config, roster, simulate
        from phase0.observe import Case, project
        for seed in range(1, 300):
            cfg = make_config(seed)
            if cfg.factor.kind != kind:
                continue
            res = simulate(cfg)
            goal = next((eid for t, team, eid in res.goals if team == cfg.beneficiary and t > cfg.factor.onset + 600), None)
            if goal:
                return cfg, Case(f"m{seed}", cfg.home, cfg.away, roster(cfg), project(res.events), goal)
        raise AssertionError(f"no {kind} case")

    def test_fires_on_the_overloaded_flank(self):
        cfg, case = self.case_with("overload")
        out = MatchTools(MatchView(case), case.roster).flank_change(cfg.factor.target)
        self.assertTrue(out["change_found"], out)
        self.assertTrue(out["event_ids"])

    def test_quiet_when_the_cause_is_fatigue(self):
        cfg, case = self.case_with("fatigue")
        tools = MatchTools(MatchView(case), case.roster)
        self.assertFalse(any(tools.flank_change(lane)["change_found"] for lane in ("left", "right")))



class ProducerFailureTests(AgentWorkflowTests):
    def test_malformed_producer_output_falls_back_without_failing_the_run(self):
        truncated = reply(NS(type="text", text="..."), stop="max_tokens")
        out, _ = self.run_with(self.f.investigator() + self.f.sceptic(
            [{"claim_id": "c1", "verdict": "upheld", "rationale": "x"},
             {"claim_id": "c2", "verdict": "refuted", "rationale": "y"}]) + [truncated, truncated])
        self.assertEqual(out["producer_source"], "template")
        self.assertTrue(out["ranking"])



class FoundryAndModelTests(unittest.TestCase):
    def test_foundry_client_uses_deployment_name_and_resource(self):
        env = {"ANTHROPIC_FOUNDRY_RESOURCE": "example-resource", "BTR_FOUNDRY_DEPLOYMENT": "my-haiku"}
        with mock.patch.dict(os.environ, env):
            p = Provider("foundry-key-placeholder", "claude-haiku-5-5", "server", platform="foundry")
        self.assertIsInstance(p.client, anthropic.AnthropicFoundry)
        self.assertEqual(p.api_model, "my-haiku")
        self.assertIn("example-resource.services.ai.azure.com", str(p.client.base_url))

    def test_models_without_effort_do_not_receive_it(self):
        client = FakeClient([reply(NS(type="text", text="ok"), stop="end_turn")])
        Provider(None, "claude-haiku-4-5", "server", client=client).create(max_tokens=10, messages=[], output_config={"effort": "low"})
        self.assertNotIn("output_config", client.requests[0])

    def test_byok_always_uses_the_claude_api(self):
        with mock.patch("investigation.llm.provider.PLATFORM", "foundry"):
            p = Provider(FAKE_KEY, "claude-haiku-5-5", "byok")
        self.assertEqual(p.platform, "anthropic")
        self.assertIsInstance(p.client, anthropic.Anthropic)


class SavedInvestigationEndpointTests(unittest.TestCase):
    def test_saved_result_is_served_without_calling_a_model(self):
        client = TestClient(app_module.app)
        m = app_module.index()[0]
        with mock.patch.object(app_module.policy, "provider_factory", side_effect=AssertionError("must not call a model")):
            res = client.get(f"/api/matches/{m['id']}/incidents/{m['incident_id']}/saved-investigation")
        self.assertIn(res.status_code, (200, 404))
        if res.status_code == 200:
            self.assertTrue(res.json()["cached"])


if __name__ == "__main__":
    unittest.main()
