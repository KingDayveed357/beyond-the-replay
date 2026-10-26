import copy
import unittest

from investigation.board import Board, Claim
from investigation.producer import check_grounded, produce
from investigation.workflow import investigate
from phase0.investigators import MatchView
from tests.test_phase0 import first_case


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, _, cls.case = first_case(100011)
        cls.out = investigate(cls.case)
        cls.view = MatchView(cls.case)

    def test_every_stage_leaves_a_trace(self):
        agents = [s["agent"] for s in self.out["trace"]]
        for agent in ("investigator", "sceptic", "verifier", "producer"):
            self.assertIn(agent, agents)

    def test_booking_is_challenged_and_refuted_when_play_reset(self):
        foul = next(c for c in self.out["claims"] if c["kind"] == "FOUL")
        self.assertEqual(foul["status"], "refuted")
        self.assertNotEqual(self.out["ranking"][0][0], "FOUL")

    def test_explanation_only_uses_verified_claims(self):
        claims = {c["id"]: c for c in self.out["claims"]}
        for beat in self.out["explanation"]["beats"]:
            self.assertTrue(claims[beat["claim_id"]]["verified"])
            self.assertNotEqual(claims[beat["claim_id"]]["status"], "refuted")

    def test_ranking_excludes_unverified_claims(self):
        unverified = {tuple(c["key"]) for c in self.out["claims"] if not c["verified"]}
        self.assertFalse(unverified & {tuple(k) for k in self.out["ranking"]})

    def test_sceptic_off_matches_investigator_ranking(self):
        off = investigate(self.case, use_sceptic=False)
        self.assertEqual(off["sceptic"], "off")
        self.assertTrue(all(not c["challenges"] for c in off["claims"]))


class GroundingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, _, cls.case = first_case(100011)
        cls.view = MatchView(cls.case)

    def board_with(self, verified=True, status="upheld"):
        board = Board(self.case.case_id, self.case.incident_id, "test")
        cited = [e["id"] for e in self.view.build_up]
        board.claims.append(Claim("c1", "STYLE", self.view.final_lane if self.view.final_lane != "center" else "left",
                                  None, "", cited, "test", 1.0, 1.0, status=status, verified=verified))
        return board

    def test_producer_output_is_grounded(self):
        board = self.board_with()
        explanation = produce(board, self.view, self.case.roster)
        self.assertEqual(check_grounded(explanation, board, self.view, self.case.roster), [])

    def test_invented_player_is_caught(self):
        board = self.board_with()
        explanation = copy.deepcopy(produce(board, self.view, self.case.roster))
        outsider = next(p for p, r in self.case.roster.items() if r["role"] == "GK" and r["team"] == self.view.A)
        explanation["beats"][0]["fan"] += f" {self.case.roster[outsider]['name']} also froze."
        problems = check_grounded(explanation, board, self.view, self.case.roster)
        self.assertTrue(any("without evidence" in p for p in problems))

    def test_invented_minute_is_caught(self):
        board = self.board_with()
        explanation = copy.deepcopy(produce(board, self.view, self.case.roster))
        explanation["headline"] += " It all started at 3'."
        self.assertTrue(any("minute 3'" in p for p in check_grounded(explanation, board, self.view, self.case.roster)))

    def test_unverified_or_refuted_claims_cannot_back_a_beat(self):
        for kwargs in ({"verified": False}, {"status": "refuted"}):
            board = self.board_with(**kwargs)
            fake = {"headline": "x", "beats": [{"label": "Cause", "claim_id": "c1", "evidence": [], "fan": "", "analyst": ""}]}
            self.assertTrue(check_grounded(fake, board, self.view, self.case.roster))
            self.assertEqual(produce(board, self.view, self.case.roster)["confidence"], "none")



class NumberGroundingTests(GroundingTests):
    def test_invented_count_is_caught(self):
        board = self.board_with()
        explanation = copy.deepcopy(produce(board, self.view, self.case.roster))
        explanation["beats"][0]["fan"] += " The defender lost 9 of 10 duels."
        self.assertTrue(any("9 of 10" in p for p in check_grounded(explanation, board, self.view, self.case.roster)))


if __name__ == "__main__":
    unittest.main()
