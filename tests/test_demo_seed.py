"""The demo seed: real pipeline decisions at past times, on a valid hash chain."""

from __future__ import annotations

import asyncio

from src.demo import seed_demo_decisions
from src.mcp_server.runtime import Runtime


def test_seed_fills_an_empty_log_with_a_valid_chain(runtime: Runtime) -> None:
    count = asyncio.run(seed_demo_decisions(runtime, days=7))

    assert count > 30
    integrity = runtime.decisions.verify()
    assert integrity == {"ok": True, "records": count, "head": integrity["head"]}

    records = runtime.decisions.recent(limit=count)
    effects = {r["effect"] for r in records}
    deny_codes = {r["code"] for r in records if r["effect"] == "deny"}
    assert effects == {"permit", "deny"}
    assert len(deny_codes) >= 3
    assert any(r["agent"] for r in records)
    # Every record went through the pipeline, starting with the validate stage.
    assert all(r["stages"][0]["name"] == "validate" for r in records)
    times = [r["decided_at"] for r in reversed(records)]
    assert times == sorted(times)


def test_seed_never_touches_a_log_with_decisions(runtime: Runtime) -> None:
    assert asyncio.run(seed_demo_decisions(runtime, days=2)) > 0
    before = runtime.decisions.verify()["records"]

    assert asyncio.run(seed_demo_decisions(runtime, days=2)) == 0
    assert runtime.decisions.verify()["records"] == before
