import dataclasses
import json
import unittest

from phase0.engine import make_config, pid, roster, simulate, _Sim
from phase0.investigators import Hypothesis, MatchView, StatInvestigator, verify
from phase0.observe import HIDDEN_TERMS, OBSERVABLE_FIELDS, Case, SchemaError, project, validate_events


def first_case(start=1):
    """First seed whose match has a beneficiary goal after the decoy."""
    for seed in range(start, start + 200):
        cfg = make_config(seed)
        res = simulate(cfg)
        if not res.decoy_ids:
            continue
        decoy_t = next(e["t"] for e in res.events if e["id"] == res.decoy_ids[0])
        goal = next((eid for t, team, eid in res.goals if team == cfg.beneficiary and t > decoy_t), None)
        if goal:
            return cfg, res, Case(f"m{seed}", cfg.home, cfg.away, roster(cfg), project(res.events), goal)
    raise AssertionError("no usable seed")


class EngineTests(unittest.TestCase):
    def test_same_seed_same_match(self):
        cfg = make_config(7)
        self.assertEqual(simulate(cfg).events, simulate(cfg).events)

    def test_history_before_onset_is_shared_when_factor_removed(self):
        cfg = make_config(11)
        onset = cfg.factor.onset
        on = [e for e in simulate(cfg).events if e["t"] < onset]
        off = [e for e in simulate(cfg, neutralize={"factor"}).events if e["t"] < onset]
        self.assertEqual(on, off)

    def test_paired_futures_share_history(self):
        cfg = make_config(12)
        split = cfg.factor.onset
        a = [e for e in simulate(cfg, 99, split).events if e["t"] < split]
        b = [e for e in simulate(cfg, 99, split, {"factor"}).events if e["t"] < split]
        self.assertEqual(a, b)

    def test_decoy_has_zero_causal_effect(self):
        for seed in range(1, 15):
            cfg = make_config(seed)
            with_decoy = simulate(cfg)
            without = simulate(dataclasses.replace(cfg, decoy=None))
            stripped = [{k: v for k, v in e.items() if k != "id"}
                        for e in with_decoy.events if e["id"] not in with_decoy.decoy_ids]
            self.assertEqual(stripped, [{k: v for k, v in e.items() if k != "id"} for e in without.events])
            self.assertEqual([g[:2] for g in with_decoy.goals], [g[:2] for g in without.goals])

    def test_fatigue_only_acts_after_onset(self):
        cfg = make_config(3)
        cfg = dataclasses.replace(cfg, factor=dataclasses.replace(cfg.factor, kind="fatigue",
                                  target=pid(cfg.home, "RB"), team=cfg.home))
        sim = _Sim(cfg, None, None, ())
        target, onset = cfg.factor.target, cfg.factor.onset
        base = cfg.ratings[target] - (cfg.weak_delta if cfg.weak_player == target else 0)
        self.assertAlmostEqual(sim.rating(target, onset - 1), base)
        self.assertLess(sim.rating(target, onset + 900), base)
        off = _Sim(cfg, None, None, {"factor"})
        self.assertAlmostEqual(off.rating(target, onset + 900), base)

    def test_realistic_order_of_magnitude(self):
        res = simulate(make_config(5))
        self.assertGreater(len(res.events), 300)
        self.assertLess(len(res.goals), 12)


class ObservationTests(unittest.TestCase):
    def test_observable_stream_has_no_hidden_state(self):
        _, res, case = first_case()
        for e in case.events:
            self.assertEqual(set(e), set(OBSERVABLE_FIELDS))
        blob = json.dumps(case.events).lower()
        for term in HIDDEN_TERMS:
            self.assertNotIn(term, blob)
        validate_events(case.events, case.roster)

    def test_malformed_events_are_rejected(self):
        _, _, case = first_case()
        bad = [dict(e) for e in case.events[:20]]
        bad[3]["player_id"] = "XXX-ST"
        bad[5]["t"] = -10
        del bad[7]["outcome"]
        bad[9]["stamina"] = 0.2
        with self.assertRaises(SchemaError) as ctx:
            validate_events(bad, case.roster)
        msg = str(ctx.exception)
        for fragment in ("unknown player", "out of order", "missing", "unexpected fields"):
            self.assertIn(fragment, msg)


class VerifierTests(unittest.TestCase):
    def setUp(self):
        _, _, self.case = first_case()
        self.view = MatchView(self.case)

    def test_invented_citation_is_rejected(self):
        h = Hypothesis("STYLE", "left", 1.0, cited=["e99999"])
        ok, frac, reasons = verify(h, self.view)
        self.assertFalse(ok)
        self.assertEqual(frac, 0.0)
        self.assertIn("does not exist", reasons[0])

    def test_citation_not_involving_target_is_rejected(self):
        unrelated = next(e["id"] for e in self.case.events if e["type"] == "pass" and e["team"] == self.view.A)
        h = Hypothesis("FATIGUE", self.view.full_back("left"), 1.0, cited=[unrelated])
        self.assertFalse(verify(h, self.view)[0])

    def test_invalid_target_and_missing_evidence(self):
        self.assertFalse(verify(Hypothesis("OVERLOAD", "centre-ish", 1.0, cited=[]), self.view)[0])
        self.assertFalse(verify(Hypothesis("TELEPATHY", "left", 1.0, cited=["e00001"]), self.view)[0])

    def test_stat_investigator_claims_verify(self):
        for h in StatInvestigator().investigate(self.case)[:3]:
            if h.cited:
                ok, frac, reasons = verify(h, self.view)
                self.assertTrue(ok, (h, reasons))


if __name__ == "__main__":
    unittest.main()
