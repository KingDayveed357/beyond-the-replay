"""Feedback: validation, spam and rate limits, privacy of emails, and both storage backends."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from server import app as app_module
from server.feedback import FeedbackService, FileStore, TableStore, make_store

GOOD = {"rating": 4, "role": "judge", "improve": "Explain xG the first time it appears.", "liked": "The reveal",
        "email": "judge@example.com", "page": "/match/m300080"}


class FakeTable:
    """Stands in for azure.data.tables.TableClient."""

    def __init__(self):
        self.rows = []

    def create_entity(self, entity):
        assert entity["PartitionKey"] and entity["RowKey"]
        self.rows.append(dict(entity))

    def list_entities(self):
        return sorted(self.rows, key=lambda e: (e["PartitionKey"], e["RowKey"]))


class FeedbackApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        service = FeedbackService(FileStore(Path(self.tmp.name) / "feedback.jsonl"), per_hour=3)
        self.patch = mock.patch.object(app_module, "feedback", service)
        self.patch.start()
        self.client = TestClient(app_module.app)

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_feedback_is_stored_and_summarised_without_emails(self):
        self.assertEqual(self.client.post("/api/feedback", json=GOOD).status_code, 201)
        self.client.post("/api/feedback", json=GOOD | {"rating": 2, "role": "fan", "email": ""})
        s = self.client.get("/api/feedback/summary").json()
        self.assertEqual(s["count"], 2)
        self.assertEqual(s["average_rating"], 3.0)
        self.assertEqual(s["by_role"]["judge"]["count"], 1)
        self.assertEqual(s["ratings"]["2"], 1)
        self.assertEqual(s["latest"][0]["role"], "fan")  # newest first
        self.assertNotIn("judge@example.com", str(s))

    def test_bad_input_is_explained(self):
        for bad in ({"rating": 6}, {"role": "manager"}, {"improve": "x"}, {"email": "not-an-email"}):
            res = self.client.post("/api/feedback", json=GOOD | bad)
            self.assertEqual(res.status_code, 422, bad)

    def test_spam_trap_and_rate_limit(self):
        res = self.client.post("/api/feedback", json=GOOD | {"website": "http://spam"}).json()
        self.assertFalse(res["stored"])
        for _ in range(3):
            self.assertEqual(self.client.post("/api/feedback", json=GOOD).status_code, 201)
        res = self.client.post("/api/feedback", json=GOOD)
        self.assertEqual(res.status_code, 429)
        self.assertEqual(res.json()["detail"]["code"], "slow_down")
        self.assertEqual(self.client.get("/api/feedback/summary").json()["count"], 3)


class StoreTests(unittest.TestCase):
    def test_azure_table_round_trip(self):
        store = TableStore("", client=FakeTable())
        ticks = iter([1_800_000_000.0, 1_800_000_060.0])
        service = FeedbackService(store, clock=lambda: next(ticks))
        for rating in (5, 3):
            service.submit(app_module.FeedbackIn(**GOOD | {"rating": rating}), "1.2.3.4")
        rows = store.table.rows
        self.assertTrue(all(r["PartitionKey"] == rows[0]["created"][:7] for r in rows))
        self.assertLess(rows[1]["RowKey"], rows[0]["RowKey"])  # newer rows sort first in the table
        s = service.summary()
        self.assertEqual((s["count"], s["average_rating"], s["storage"]), (2, 4.0, "azure-table"))

    def test_misconfigured_storage_falls_back_to_a_file(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict("os.environ", {"BTR_FEEDBACK_CONNECTION": "not a connection string"}):
            self.assertEqual(make_store(Path(tmp)).kind, "file")

    def test_no_connection_string_means_a_file(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict("os.environ", {"BTR_FEEDBACK_CONNECTION": ""}):
            self.assertEqual(make_store(Path(tmp)).kind, "file")


if __name__ == "__main__":
    unittest.main()
