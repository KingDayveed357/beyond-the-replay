import json
import unittest

from fastapi.testclient import TestClient

from analytics.live import build_timeline
from analytics.models import PassModel, xg
from analytics.recap import check_recap, facts, template_recap
from server.app import app, index, match, timeline


class TimelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mid = index()[0]["id"]
        cls.m = match(cls.mid)
        cls.tl = timeline(cls.mid)

    def test_final_state_matches_the_events(self):
        goals = [e for e in self.m["events"] if e["type"] == "shot" and e["outcome"] == "goal"]
        final = self.tl["states"][-1]["teams"]
        for team in (self.m["home"], self.m["away"]):
            self.assertEqual(final[team]["goals"], sum(1 for g in goals if g["team"] == team))
            self.assertEqual(final[team]["shots"], sum(1 for e in self.m["events"] if e["type"] == "shot" and e["team"] == team))
        self.assertAlmostEqual(sum(t["possession"] for t in final.values()), 100, delta=1)

    def test_states_are_one_per_minute_and_monotonic(self):
        minutes = [s["minute"] for s in self.tl["states"]]
        self.assertEqual(minutes, list(range(1, len(minutes) + 1)))
        goals = [sum(t["goals"] for t in s["teams"].values()) for s in self.tl["states"]]
        self.assertEqual(goals, sorted(goals))

    def test_every_goal_is_a_moment_with_a_scorer(self):
        goal_moments = [m for m in self.tl["moments"] if m["type"] == "goal"]
        goals = [e for e in self.m["events"] if e["type"] == "shot" and e["outcome"] == "goal"]
        self.assertEqual(len(goal_moments), len(goals))
        self.assertTrue(all(m["player_id"] in self.m["roster"] for m in goal_moments))

    def test_enriched_values_are_in_range_and_cues_are_ordered(self):
        for e in self.tl["events"]:
            if "pass_difficulty" in e:
                self.assertTrue(0 <= e["pass_difficulty"] <= 100)
            if "xg" in e:
                self.assertTrue(0 < e["xg"] < 1)
        t_in = [c["t_in"] for c in self.tl["cues"]]
        self.assertEqual(t_in, sorted(t_in))

    def test_xg_falls_with_distance(self):
        self.assertGreater(xg(100, 34, True), xg(88, 34, True))
        self.assertGreater(xg(88, 34, True), xg(80, 34, True))
        self.assertLess(xg(100, 34, True, header=True), xg(100, 34, True))

    def test_pass_model_rates_long_switches_harder(self):
        model = PassModel.load()
        short = {"team": "A", "x": 40, "y": 34, "end_x": 50, "end_y": 36, "under_pressure": False}
        long_switch = {"team": "A", "x": 40, "y": 10, "end_x": 75, "end_y": 60, "under_pressure": True}
        self.assertGreater(model.difficulty(long_switch, "A"), model.difficulty(short, "A"))


class RecapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mid = index()[0]["id"]
        cls.m = match(cls.mid)
        cls.f = facts(cls.m, timeline(cls.mid), "ft")
        cls.names = {p["name"] for p in cls.m["roster"].values()}

    def test_template_passes_its_own_check(self):
        self.assertEqual(check_recap(template_recap(self.f), self.f, self.names), [])

    def test_invented_details_are_caught(self):
        outsider = next(n for n in self.names if n not in json.dumps(self.f, ensure_ascii=False))
        bad = {"headline": "A 9-9 classic", "paragraphs": [f"{outsider} scored at 3'.", "They had 99% possession."]}
        problems = " ".join(check_recap(bad, self.f, self.names))
        for fragment in ("scoreline 9-9", outsider, "minute 3'", "99%"):
            self.assertIn(fragment, problems)

    def test_lead_language_is_rejected_when_level(self):
        level = dict(self.f, score="1-1", goals=[])
        self.assertTrue(check_recap({"headline": "Hosts lead at the break", "paragraphs": []}, level, self.names))


class LiveStreamTests(unittest.TestCase):
    def test_stream_delivers_events_in_time_order(self):
        client = TestClient(app)
        mid = index()[0]["id"]
        times, kinds = [], set()
        with client.stream("GET", f"/api/matches/{mid}/live?speed=240") as res:
            self.assertEqual(res.headers["content-type"].split(";")[0], "text/event-stream")
            for line in res.iter_lines():
                if line.startswith("event: "):
                    kinds.add(line[7:])
                if line.startswith("data: "):
                    times.append(json.loads(line[6:])["t"])
                if len(times) >= 40:
                    break
        self.assertEqual(times, sorted(times))
        self.assertIn("event", kinds)



class OrdinalMinuteTests(RecapTests):
    def test_ordinal_minutes_are_checked(self):
        bad = {"headline": "Late drama", "paragraphs": ["The winner came in the 3rd minute."]}
        self.assertTrue(any("minute 3'" in p for p in check_recap(bad, self.f, self.names)))



class LocalisationTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.mid = index()[0]["id"]

    def test_every_language_renders_every_moment_and_cue(self):
        from analytics.i18n import LANGUAGES
        names = {p["name"] for p in self.client.get(f"/api/matches/{self.mid}").json()["roster"].values()}
        for lang in LANGUAGES:
            tl = self.client.get(f"/api/matches/{self.mid}/timeline?lang={lang}").json()
            self.assertEqual(tl["dir"], "rtl" if lang == "ar" else "ltr")
            for m in tl["moments"]:
                self.assertTrue(m["headline"] and m["why"], (lang, m))
                self.assertNotIn("{", m["headline"] + m["why"])
            goals = [m for m in tl["moments"] if m["type"] == "goal"]
            self.assertTrue(all(any(n in m["headline"] for n in names) for m in goals), lang)
            self.assertTrue(all(c["text"] and "{" not in c["text"] for c in tl["cues"]))

    def test_unknown_language_is_rejected(self):
        self.assertEqual(self.client.get(f"/api/matches/{self.mid}/timeline?lang=xx").status_code, 400)

    def test_overlay_track_is_versioned_and_ordered(self):
        track = self.client.get(f"/api/matches/{self.mid}/overlays?lang=es").json()
        self.assertEqual(track["version"], "1.0")
        self.assertTrue(track["cues"])
        self.assertEqual([c["t_in"] for c in track["cues"]], sorted(c["t_in"] for c in track["cues"]))
        self.assertTrue(all(c["t_out"] > c["t_in"] for c in track["cues"]))

    def test_webvtt_track_is_well_formed(self):
        res = self.client.get(f"/api/matches/{self.mid}/overlays?lang=fr&format=vtt")
        self.assertTrue(res.headers["content-type"].startswith("text/vtt"))
        lines = res.text.splitlines()
        self.assertEqual(lines[0], "WEBVTT")
        timings = [l for l in lines if "-->" in l]
        self.assertTrue(timings)
        self.assertRegex(timings[0], r"^\d\d:\d\d:\d\d\.\d{3} --> \d\d:\d\d:\d\d\.\d{3}$")


if __name__ == "__main__":
    unittest.main()
