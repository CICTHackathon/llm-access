"""Multi-agent policy decision point for the Smart Gateway access-control system."""

import os
import tempfile
from pathlib import Path

__version__ = "0.1.0"


def _ensure_writable_data_home() -> None:
    """CrewAI creates its data directory under ``~/.local/share`` when it is imported.

    Serverless hosts such as Vercel have a read-only home directory, so the import
    crashes. When that directory cannot be created, point the XDG directories at the
    temp directory instead. MCP server subprocesses inherit them via the environment.
    """
    if os.name != "posix" or os.environ.get("XDG_DATA_HOME"):
        return
    try:
        (Path.home() / ".local" / "share").mkdir(parents=True, exist_ok=True)
    except OSError:
        base = Path(tempfile.gettempdir()) / "xdg"
        for var, sub in (("XDG_DATA_HOME", "share"), ("XDG_CACHE_HOME", "cache"),
                         ("XDG_CONFIG_HOME", "config")):
            os.environ.setdefault(var, str(base / sub))


_ensure_writable_data_home()
