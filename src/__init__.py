"""Multi-agent policy decision point for the Smart Gateway access-control system."""

import os
import tempfile
from pathlib import Path

__version__ = "0.1.0"


def _ensure_writable_data_home() -> None:
    """CrewAI creates its data directory under ``~/.local/share`` when it is imported.

    Serverless hosts such as Vercel have a read-only home directory, so the import
    crashes. When that directory cannot be created, move HOME (some CrewAI modules
    use ``~`` directly) and the XDG directories into the temp directory. MCP server
    subprocesses inherit them via the environment.
    """
    if os.name != "posix":
        return
    try:
        (Path.home() / ".local" / "share").mkdir(parents=True, exist_ok=True)
    except OSError:
        home = Path(tempfile.gettempdir()) / "home"
        home.mkdir(parents=True, exist_ok=True)
        os.environ["HOME"] = str(home)
        for var, sub in (("XDG_DATA_HOME", ".local/share"), ("XDG_CACHE_HOME", ".cache"),
                         ("XDG_CONFIG_HOME", ".config")):
            os.environ[var] = str(home / sub)


_ensure_writable_data_home()
