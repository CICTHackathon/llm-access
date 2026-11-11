"""The source of truth: inventory, identity directory and policy set, kept as YAML.

Every reader goes through :class:`SourceOfTruth`, which reloads a file when it
changes on disk, so an MCP server and the PDP always see the same version. Writes
go through :meth:`SourceOfTruth.write`, which keeps a timestamped backup.
"""

from __future__ import annotations

import hashlib
import shutil
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, TypeVar
from zoneinfo import ZoneInfo

import yaml
from pydantic import BaseModel

from src.mcp_server.engine.domain.identity import Directory
from src.mcp_server.engine.domain.inventory import Inventory
from src.mcp_server.engine.domain.policy import PolicySet

Document = Literal["inventory", "identities", "policies", "scenarios"]
M = TypeVar("M", bound=BaseModel)

_MODELS: dict[Document, type[BaseModel] | None] = {
    "inventory": Inventory,
    "identities": Directory,
    "policies": PolicySet,
    "scenarios": None,
}


class _Cached:
    __slots__ = ("mtime", "digest", "value")

    def __init__(self, mtime: float, digest: str, value: Any) -> None:
        self.mtime = mtime
        self.digest = digest
        self.value = value


class SourceOfTruth:
    def __init__(self, config_dir: Path, backup_dir: Path | None = None) -> None:
        self.config_dir = Path(config_dir)
        self.backup_dir = Path(backup_dir) if backup_dir else None
        self._cache: dict[Document, _Cached] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ read ---

    def path(self, doc: Document) -> Path:
        return self.config_dir / f"{doc}.yaml"

    def version(self, doc: Document) -> str:
        """Content hash of a document; plans record it to detect stale edits."""
        return self._load(doc).digest

    @property
    def inventory(self) -> Inventory:
        return self._load("inventory").value

    @property
    def directory(self) -> Directory:
        return self._load("identities").value

    @property
    def policies(self) -> PolicySet:
        return self._load("policies").value

    @property
    def scenarios(self) -> list[dict[str, Any]]:
        data = self._load("scenarios").value or {}
        return list(data.get("scenarios", []))

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.inventory.site.timezone)

    def local_time(self, at: datetime | None = None) -> datetime:
        """``at`` (default: now) in the site timezone; naive values are taken as local."""
        if at is None:
            return datetime.now(UTC).astimezone(self.timezone)
        if at.tzinfo is None:
            return at.replace(tzinfo=self.timezone)
        return at.astimezone(self.timezone)

    def overlay(self, **documents: BaseModel) -> SourceOfTruth:
        """A read-only view with some documents replaced, used to judge candidate edits."""
        return _Overlay(self, documents)  # type: ignore[return-value]

    # ----------------------------------------------------------------- write ---

    def write(self, doc: Document, data: dict[str, Any]) -> str:
        """Validate and persist a document, keeping a backup. Returns the new version."""
        model = _MODELS[doc]
        if model is not None:
            model.model_validate(data)
        path = self.path(doc)
        with self._lock:
            if self.backup_dir and path.exists():
                stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
                target = self.backup_dir / doc / f"{stamp}.yaml"
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
            text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
            tmp = path.with_suffix(".yaml.tmp")
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(path)
            self._cache.pop(doc, None)
        return self.version(doc)

    def dump(self, doc: Document) -> dict[str, Any]:
        """A document as plain data, ready to be edited and passed back to :meth:`write`."""
        value = self._load(doc).value
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json", exclude_defaults=False)
        return dict(value or {})

    # -------------------------------------------------------------- internals ---

    def _load(self, doc: Document) -> _Cached:
        path = self.path(doc)
        mtime = path.stat().st_mtime if path.exists() else -1.0
        with self._lock:
            cached = self._cache.get(doc)
            if cached and cached.mtime == mtime:
                return cached
            text = path.read_text(encoding="utf-8") if path.exists() else ""
            data = yaml.safe_load(text) or {}
            model = _MODELS[doc]
            value = model.model_validate(data) if model is not None else data
            entry = _Cached(mtime, hashlib.sha256(text.encode()).hexdigest()[:16], value)
            self._cache[doc] = entry
            return entry


class _Overlay:
    """Delegates to a :class:`SourceOfTruth` except for the documents it overrides."""

    def __init__(self, base: SourceOfTruth, documents: dict[str, BaseModel]) -> None:
        self._base = base
        self._documents = documents

    def __getattr__(self, name: str) -> Any:
        if name in self._documents:
            return self._documents[name]
        return getattr(self._base, name)


def parse_when(value: Any) -> datetime | None:
    """Accept ``None``, a datetime, or an ISO-8601 string (as YAML or an agent may give)."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))
