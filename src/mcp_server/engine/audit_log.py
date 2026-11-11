"""Append-only, hash-chained log of every access decision the PDP has issued.

Each line carries the hash of the previous one, so removing or editing a record
breaks the chain from that point on, and :meth:`DecisionLog.verify` reports where.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections import deque
from pathlib import Path
from typing import Any

from src.mcp_server.engine.domain.access import Decision

GENESIS = "0" * 64


def _digest(prev: str, body: dict[str, Any]) -> str:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256((prev + canonical).encode()).hexdigest()


class DecisionLog:
    def __init__(self, path: Path, memory: int = 2000) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._recent: deque[dict[str, Any]] = deque(maxlen=memory)
        self._txns: set[str] = set()
        self._last_hash = GENESIS
        self._load()

    def append(self, decision: Decision) -> dict[str, Any]:
        body = decision.model_dump(mode="json")
        body["epoch"] = int(decision.decided_at.timestamp())
        with self._lock:
            record = {**body, "prev_hash": self._last_hash}
            record["hash"] = _digest(self._last_hash, body)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, separators=(",", ":")) + "\n")
            self._remember(record)
            return record

    def seen_txn(self, txn: str) -> bool:
        with self._lock:
            return txn in self._txns

    def recent(self, *, limit: int = 50, door: str | None = None, uid: str | None = None,
               subject: str | None = None) -> list[dict[str, Any]]:
        """Newest first, filtered on any of door / uid / subject."""
        with self._lock:
            rows = list(self._recent)
        rows.reverse()
        out = []
        for row in rows:
            if door and row.get("door") != door:
                continue
            if uid and row.get("uid") != uid:
                continue
            if subject and row.get("subject_id") != subject:
                continue
            out.append(row)
            if len(out) >= limit:
                break
        return out

    def get(self, decision_id: str) -> dict[str, Any] | None:
        with self._lock:
            return next((r for r in self._recent if r.get("decision_id") == decision_id), None)

    def verify(self) -> dict[str, Any]:
        """Walk the whole file and check every link of the chain."""
        prev, count = GENESIS, 0
        if not self.path.exists():
            return {"ok": True, "records": 0}
        with self.path.open(encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                record = json.loads(line)
                stored_hash, stored_prev = record.pop("hash"), record.pop("prev_hash")
                if stored_prev != prev or _digest(prev, record) != stored_hash:
                    return {"ok": False, "records": count, "broken_at_line": lineno,
                            "decision_id": record.get("decision_id")}
                prev, count = stored_hash, count + 1
        return {"ok": True, "records": count, "head": prev}

    def _remember(self, record: dict[str, Any]) -> None:
        self._recent.append(record)
        self._txns.add(record["txn"])
        self._last_hash = record["hash"]

    def _load(self) -> None:
        if not self.path.exists():
            return
        with self.path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    self._remember(json.loads(line))
