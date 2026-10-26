"""Shared investigation state. Every agent reads and writes the board; nothing else is shared."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field


@dataclass
class Challenge:
    question: str
    finding: str
    verdict: str                     # "upheld" | "weakened" | "refuted"
    evidence: list = field(default_factory=list)
    shifts_to: tuple | None = None   # hypothesis key that this finding supports instead
    source: str = "test"             # "test" (deterministic tool output) | "llm" (model-written judgement)


@dataclass
class Claim:
    id: str
    kind: str
    target: str
    onset: int | None
    statement: str
    cited: list
    proposed_by: str
    raw_score: float
    score: float
    status: str = "proposed"         # proposed -> upheld | weakened | refuted; plus verified flag
    challenges: list = field(default_factory=list)
    verified: bool = False
    verification_notes: list = field(default_factory=list)
    reasoning: str = ""              # the proposing agent's own words (never used as evidence)

    @property
    def key(self) -> tuple:
        return (self.kind, self.target)


@dataclass
class TraceStep:
    agent: str
    action: str
    detail: str
    ms: float


class Board:
    def __init__(self, case_id: str, incident_id: str, mode: str):
        self.case_id = case_id
        self.incident_id = incident_id
        self.mode = mode
        self.claims: list[Claim] = []
        self.trace: list[TraceStep] = []
        self._t0 = time.perf_counter()

    def log(self, agent: str, action: str, detail: str) -> None:
        self.trace.append(TraceStep(agent, action, detail, round((time.perf_counter() - self._t0) * 1000, 2)))

    def claim(self, key: tuple) -> Claim | None:
        return next((c for c in self.claims if c.key == key), None)

    def ranked(self) -> list[Claim]:
        return sorted(self.claims, key=lambda c: -c.score)

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id, "incident_id": self.incident_id, "mode": self.mode,
            "claims": [asdict(c) | {"key": list(c.key)} for c in self.ranked()],
            "trace": [asdict(s) for s in self.trace],
        }
