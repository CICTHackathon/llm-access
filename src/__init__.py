"""Multi-agent policy decision point for the Smart Gateway access-control system."""

import os

__version__ = "0.1.0"

# On Vercel only /tmp is writable, but CrewAI creates its data directory under
# ~/.local/share when it is imported. Point the XDG directories at /tmp before any
# CrewAI import; MCP server subprocesses inherit these through the environment.
if os.environ.get("VERCEL"):
    for _var, _sub in (("XDG_DATA_HOME", "share"), ("XDG_CACHE_HOME", "cache"),
                       ("XDG_CONFIG_HOME", "config")):
        os.environ.setdefault(_var, f"/tmp/xdg/{_sub}")
