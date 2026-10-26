"""Broadcast-safe identity: no real club, stadium, player, manager or referee name leaves the API by default."""
import unittest

from fastapi.testclient import TestClient

from analytics.i18n import LANGUAGES
from server.app import app, index, match
from server.identity import Identity, identity


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.assertTrue(identity().fictional, "fictional names must be the default")

    def assert_clean(self, path, mid=None):
        res = self.client.get(path) if "investigations" not in path else self.client.post(path)
        self.assertEqual(res.status_code, 200, path)
        body = res.json() if "format=vtt" not in path else res.text
        leaks = identity().leaks(body, match(mid)["roster"] if mid else None)
        self.assertEqual(leaks, [], path)

    def test_every_public_output_is_free_of_real_names(self):
        self.assert_clean("/api/matches")
        self.assert_clean("/api/benchmark")
        for m in index():
            mid, inc = m["id"], m["incident_id"]
            self.assert_clean(f"/api/matches/{mid}", mid)
            self.assert_clean(f"/api/matches/{mid}/overlays", mid)
            self.assert_clean(f"/api/matches/{mid}/overlays?format=vtt", mid)
            self.assert_clean(f"/api/matches/{mid}/incidents/{inc}/saved-investigation", mid)
            self.assert_clean(f"/api/matches/{mid}/incidents/{inc}/investigations?mode=deterministic", mid)
            self.assert_clean(f"/api/matches/{mid}/incidents/{inc}/truth", mid)
            for lang in LANGUAGES:
                self.assert_clean(f"/api/matches/{mid}/timeline?lang={lang}", mid)
                for phase in ("ht", "ft"):
                    for voice in ("fan", "analyst"):
                        self.assert_clean(f"/api/matches/{mid}/recap?phase={phase}&voice={voice}&lang={lang}", mid)

    def test_names_are_stable_and_unique(self):
        a, b = Identity("fictional"), Identity("fictional")
        self.assertEqual(a.fake_players, b.fake_players)
        surnames = [n.split()[-1] for n in a.fake_players.values()]
        self.assertEqual(len(surnames), len(set(surnames)))
        self.assertFalse(set(a.fake_players.values()) & set(a.players.values()))

    def test_ids_round_trip(self):
        i = Identity("fictional")
        self.assertEqual(i.unskin_id(i.skin("BOU-RB")), "BOU-RB")
        self.assertEqual(i.unskin_name(i.fake_players["LEI-ST"]), i.players["LEI-ST"])

    def test_real_mode_is_untouched(self):
        m = match(index()[0]["id"])
        self.assertEqual(Identity("real").skin(m, m["roster"]), m)


if __name__ == "__main__":
    unittest.main()
