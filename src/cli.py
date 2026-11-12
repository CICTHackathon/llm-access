"""Command line: ``llm-access <command>`` (or ``python -m src.cli <command>``)."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import secrets
import sys
from typing import Any

import uvicorn

from src.llm.crews import AccessReviewer, run_operations
from src.llm.decision import DecisionService
from src.mcp_server.engine.domain.access import AccessRequest
from src.mcp_server.engine.security import pin_digest
from src.mcp_server.engine.source_of_truth import parse_when
from src.mcp_server.main import main as mcp_main
from src.mcp_server.runtime import get_runtime
from src.mcp_server.servers.auditor import check_compliance
from src.mcp_server.servers.simulator import run_policy_scenarios
from src.settings import get_settings


def _print(data: Any) -> None:
    print(json.dumps(data, indent=2, default=str, ensure_ascii=False))


def cmd_serve(args: argparse.Namespace) -> None:
    settings = get_settings()
    uvicorn.run("src.main:app", host=args.host or settings.host, port=args.port or settings.port)


def cmd_mcp(args: argparse.Namespace) -> None:
    mcp_main([args.server, "--transport", args.transport, "--port", str(args.port)])


def cmd_ops(args: argparse.Namespace) -> None:
    report = run_operations(get_settings(), args.intent, dry_run=not args.live)
    _print(report.model_dump())


def cmd_decide(args: argparse.Namespace) -> None:
    """Build the request a gateway would send for this card and PIN, and decide it."""
    runtime = get_runtime()
    if args.no_agents:
        runtime.settings.agent_review = "off"  # rules only, for this invocation
    reviewer = None
    if runtime.settings.agent_review != "off":
        reviewer = AccessReviewer(runtime.settings)
    txn = secrets.token_hex(8)
    request = AccessRequest(txn=txn, door=args.door, uid=args.uid,
                            pinDigest=pin_digest(txn, args.pin) if args.pin else "")
    service = DecisionService(runtime, reviewer, collect_device_evidence=not args.offline)
    try:
        decision = asyncio.run(service.decide(request, now=parse_when(args.at)))
    finally:
        if reviewer:
            reviewer.close()
    _print(decision.model_dump(mode="json"))


def cmd_scenarios(_: argparse.Namespace) -> None:
    result = run_policy_scenarios()
    _print(result)
    sys.exit(1 if result["failed"] else 0)


def cmd_compliance(args: argparse.Namespace) -> None:
    _print(asyncio.run(check_compliance(args.node)))


def cmd_provision(args: argparse.Namespace) -> None:
    """Wire a gateway to this PDP: URL, door id, timeout and the two shared secrets.

    Secrets never pass through an agent; this operator command is how they reach the node.
    """
    runtime = get_runtime()
    node = runtime.sot.inventory.nodes.get(args.gateway)
    if node is None or node.kind != "gateway":
        raise SystemExit(f"{args.gateway!r} is not a gateway in the inventory")
    changes: dict[str, Any] = {
        "pdpUrl": args.pdp_url,
        "doorId": node.door,
        "pdpTimeoutMs": max(runtime.min_pdp_timeout_ms, 2000),
    }
    for key, which in (("pdpToken", "pdp_token"), ("decisionKey", "decision_key")):
        value = node.secret(which)
        if not value:
            raise SystemExit(f"set {getattr(node, f'{which}_env')} before provisioning")
        changes[key] = value
    if args.dry_run:
        _print({k: ("<secret>" if k in ("pdpToken", "decisionKey") else v)
                for k, v in changes.items()})
        return
    gateway = runtime.fleet.gateway(args.gateway)
    asyncio.run(gateway.set_config(changes))
    _print({"provisioned": args.gateway, "door": node.door, "pdpUrl": args.pdp_url,
            "pdpTimeoutMs": changes["pdpTimeoutMs"]})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="llm-access",
                                     description="Smart Gateway multi-agent PDP.")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("serve", help="run the PDP / operations HTTP API")
    p.add_argument("--host")
    p.add_argument("--port", type=int)
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("mcp", help="run one MCP server")
    p.add_argument("server")
    p.add_argument("--transport", default="stdio", choices=["stdio", "sse", "streamable-http"])
    p.add_argument("--port", type=int, default=8100)
    p.set_defaults(func=cmd_mcp)

    p = sub.add_parser("ops", help="carry out an operator intent with the operations crew")
    p.add_argument("intent")
    p.add_argument("--live", action="store_true", help="touch devices (default: dry run)")
    p.set_defaults(func=cmd_ops)

    p = sub.add_parser("decide", help="decide a card + PIN at a door, as the gateway would ask")
    p.add_argument("--uid", required=True)
    p.add_argument("--door", required=True)
    p.add_argument("--pin", default="")
    p.add_argument("--at", help="local ISO time, default now")
    p.add_argument("--offline", action="store_true", help="do not contact the devices")
    p.add_argument("--no-agents", action="store_true", help="skip the agent review")
    p.set_defaults(func=cmd_decide)

    p = sub.add_parser("scenarios", help="run the policy regression scenarios")
    p.set_defaults(func=cmd_scenarios)

    p = sub.add_parser("compliance", help="check nodes against the security baseline")
    p.add_argument("--node")
    p.set_defaults(func=cmd_compliance)

    p = sub.add_parser("provision", help="point a gateway at this PDP and push its secrets")
    p.add_argument("gateway")
    p.add_argument("--pdp-url", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_provision)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args.func(args)


if __name__ == "__main__":
    main()
