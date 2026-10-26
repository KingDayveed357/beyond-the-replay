"""The A2A endpoint: agent card, JSON-RPC message handling, and answers built only from checked data."""
import unittest

from fastapi.testclient import TestClient

from server.app import app, index
from server.identity import identity


def ask(client, text):
    body = {"jsonrpc": "2.0", "id": "1", "method": "SendMessage",
            "params": {"message": {"messageId": "m1", "role": "ROLE_USER", "parts": [{"text": text}]}}}
    res = client.post("/a2a/", json=body, headers={"A2A-Version": "1.0"})
    assert res.status_code == 200, res.text
    task = res.json()["result"]["task"]
    assert task["status"]["state"] == "TASK_STATE_COMPLETED", task["status"]
    return task["history"][-1]["parts"][0]["text"]


class A2ATests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_agent_card_lists_skills(self):
        card = self.client.get("/a2a/.well-known/agent-card.json").json()
        self.assertEqual({s["id"] for s in card["skills"]}, {"why-goal", "storylines", "presenter-script"})

    def test_answers_why_a_goal_happened_without_real_names(self):
        hero = next(m for m in index() if m["role"] == "hero")
        text = ask(self.client, f"Why was the goal scored in {hero['id']}?")
        self.assertIn("confidence", text)
        self.assertEqual(identity().leaks(text), [])

    def test_lists_matches_and_falls_back_to_help(self):
        self.assertIn("Matches (simulated)", ask(self.client, "list matches"))
        self.assertIn("Ask me about", ask(self.client, "hello"))

    def test_storylines_and_scripts(self):
        mid = index()[0]["id"]
        self.assertIn("Storylines", ask(self.client, f"storylines in {mid}"))
        self.assertIn("[", ask(self.client, f"presenter script for {mid}"))


if __name__ == "__main__":
    unittest.main()
