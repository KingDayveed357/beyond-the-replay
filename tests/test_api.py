import json
import unittest

from fastapi.testclient import TestClient

from server.app import app, index

client = TestClient(app)


class ApiTests(unittest.TestCase):
    def test_lists_synthetic_matches(self):
        matches = client.get("/api/matches").json()
        self.assertGreaterEqual(len(matches), 1)
        self.assertTrue(all(m["synthetic"] for m in matches))

    def test_match_events_expose_no_hidden_state(self):
        m = client.get(f"/api/matches/{index()[0]['id']}").json()
        blob = json.dumps(m["events"]).lower()
        for term in ("fatigue", "overload", "rating", "magnitude", "decoy"):
            self.assertNotIn(term, blob)
        self.assertNotIn("truth", m)

    def test_investigation_returns_verified_ranking_and_trace(self):
        m = index()[0]
        out = client.post(f"/api/matches/{m['id']}/incidents/{m['incident_id']}/investigations?mode=deterministic").json()
        self.assertTrue(out["ranking"])
        self.assertEqual(out["mode"], "deterministic")
        self.assertIn("producer", [s["agent"] for s in out["trace"]])

    def test_truth_is_separate_and_marked(self):
        m = index()[0]
        truth = client.get(f"/api/matches/{m['id']}/incidents/{m['incident_id']}/truth").json()
        self.assertTrue(truth["evaluation_only"])

    def test_unknown_ids_are_404(self):
        self.assertEqual(client.get("/api/matches/nope").status_code, 404)
        m = index()[0]
        self.assertEqual(client.post(f"/api/matches/{m['id']}/incidents/e99999/investigations?mode=deterministic").status_code, 404)


if __name__ == "__main__":
    unittest.main()
