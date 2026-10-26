"""Feedback from fans, analysts, judges and developers.

Stored in Azure Table Storage when BTR_FEEDBACK_CONNECTION (a storage account connection string) is set: it
survives container restarts and costs cents. Otherwise it goes to a JSON-lines file under BTR_RUNTIME, which is
fine locally but is lost when a container restarts.

Emails are stored for follow-up but never returned by the API.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

log = logging.getLogger("btr")
ROLES = ("fan", "analyst", "judge", "developer", "other")
TABLE = os.environ.get("BTR_FEEDBACK_TABLE", "feedback")


class FeedbackIn(BaseModel):
    rating: int = Field(ge=1, le=5, description="1 (poor) to 5 (excellent)")
    role: str = Field(description="fan, analyst, judge, developer or other", examples=["fan"])
    improve: str = Field(min_length=3, max_length=1500, description="The one thing we should improve")
    liked: str = Field(default="", max_length=1000, description="What worked (optional)")
    email: str = Field(default="", max_length=200, description="Only if you'd like a reply. Never shown.")
    page: str = Field(default="", max_length=200, description="Where in the app the feedback was given")
    website: str = Field(default="", max_length=200, description="Leave empty (spam trap)")

    @field_validator("role")
    @classmethod
    def known_role(cls, v: str) -> str:
        if v not in ROLES:
            raise ValueError(f"role must be one of {', '.join(ROLES)}")
        return v

    @field_validator("email")
    @classmethod
    def plausible_email(cls, v: str) -> str:
        v = v.strip()
        if v and ("@" not in v or "." not in v.split("@")[-1] or " " in v):
            raise ValueError("that doesn't look like an email address")
        return v

    @field_validator("improve", "liked", "page")
    @classmethod
    def tidy(cls, v: str) -> str:
        return " ".join(v.split())


class FileStore:
    kind = "file"

    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()

    def add(self, row: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock, open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def all(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.lock, open(self.path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]


class TableStore:
    """Azure Table Storage: partition by month, row key sorts newest first."""
    kind = "azure-table"

    def __init__(self, connection_string: str, table: str = TABLE, client=None):
        if client is None:
            from azure.data.tables import TableServiceClient
            client = TableServiceClient.from_connection_string(connection_string).create_table_if_not_exists(table)
        self.table = client

    def add(self, row: dict) -> None:
        entity = {k: v for k, v in row.items() if v not in (None, "")}
        entity["PartitionKey"] = row["created"][:7]
        entity["RowKey"] = f"{10**16 - int(row['ts'] * 1_000_000):016d}-{row['id']}"  # newest first
        self.table.create_entity(entity=entity)

    def all(self) -> list[dict]:
        return [{k: v for k, v in dict(e).items() if k not in ("PartitionKey", "RowKey")}
                for e in self.table.list_entities()]


def make_store(runtime: Path):
    conn = os.environ.get("BTR_FEEDBACK_CONNECTION", "").strip()
    if conn:
        try:
            return TableStore(conn)
        except Exception as exc:  # misconfigured storage must not take the app down
            log.warning("feedback: Azure Table Storage unavailable (%s); using a local file", type(exc).__name__)
    return FileStore(runtime / "feedback.jsonl")


class FeedbackService:
    def __init__(self, store, per_hour: int = 6, clock=time.time):
        self.store = store
        self.per_hour = per_hour
        self.clock = clock  # injectable, so tests never patch the global time module
        self.hits: dict[str, list[float]] = {}

    def allow(self, client: str) -> bool:
        now = self.clock()
        recent = [t for t in self.hits.get(client, []) if now - t < 3600]
        self.hits[client] = recent
        return len(recent) < self.per_hour

    def submit(self, fb: FeedbackIn, client: str) -> dict:
        now = self.clock()
        row = {"id": uuid.uuid4().hex[:12], "ts": now, "created": datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="seconds"),
               "rating": fb.rating, "role": fb.role, "improve": fb.improve, "liked": fb.liked, "email": fb.email, "page": fb.page}
        if fb.website:  # a bot filled the hidden field: pretend it worked, keep nothing
            return {"id": row["id"], "stored": False}
        self.hits.setdefault(client, []).append(now)
        self.store.add(row)
        log.info("feedback %s role=%s rating=%s store=%s", row["id"], fb.role, fb.rating, self.store.kind)
        return {"id": row["id"], "stored": True}

    def summary(self, limit: int = 30) -> dict:
        rows = sorted(self.store.all(), key=lambda r: -float(r.get("ts", 0)))
        ratings = [int(r["rating"]) for r in rows if r.get("rating")]
        by_role = Counter(r.get("role", "other") for r in rows)
        return {
            "count": len(rows),
            "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
            "ratings": {str(k): ratings.count(k) for k in range(1, 6)},
            "by_role": {role: {"count": by_role.get(role, 0),
                               "average_rating": _avg([int(r["rating"]) for r in rows if r.get("role") == role])}
                        for role in ROLES},
            "latest": [{k: r.get(k, "") for k in ("created", "role", "rating", "improve", "liked", "page")} for r in rows[:limit]],
            "storage": self.store.kind,
        }


def _avg(xs: list[int]):
    return round(sum(xs) / len(xs), 2) if xs else None
