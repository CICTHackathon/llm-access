"""Pure edits to source-of-truth documents.

The verifier applies an edit to a copy to judge it; the deployer applies the same
edit to the live document after checking that the document has not changed since.
Plans therefore store the *edit*, never a full copy of a document that holds PINs.
"""

from __future__ import annotations

import copy
from typing import Any, Literal

from src.mcp_server.engine.domain.identity import normalise_uid

PolicyAction = Literal["add", "replace", "remove"]
CredentialAction = Literal["assign", "revoke"]


class EditError(ValueError):
    pass


def apply_policy_edit(document: dict[str, Any], action: PolicyAction,
                      rule: dict[str, Any] | None = None,
                      rule_id: str | None = None) -> dict[str, Any]:
    doc = copy.deepcopy(document)
    rules: list[dict[str, Any]] = doc.setdefault("rules", [])
    target_id = rule_id or (rule or {}).get("id")
    index = next((i for i, r in enumerate(rules) if r.get("id") == target_id), None)

    if action == "add":
        if not rule:
            raise EditError("add needs a rule")
        if index is not None:
            raise EditError(f"rule {target_id} already exists; use replace")
        rules.append(rule)
    elif action == "replace":
        if not rule or index is None:
            raise EditError(f"replace needs an existing rule id (got {target_id!r})")
        rules[index] = rule
    elif action == "remove":
        if index is None:
            raise EditError(f"no rule {target_id!r} to remove")
        rules.pop(index)
    else:
        raise EditError(f"unknown action {action!r}")
    doc["version"] = int(doc.get("version", 0)) + 1
    return doc


def apply_credential_edit(document: dict[str, Any], action: CredentialAction, uid: str,
                          subject_id: str | None = None) -> dict[str, Any]:
    doc = copy.deepcopy(document)
    creds: list[dict[str, Any]] = doc.setdefault("credentials", [])
    wanted = normalise_uid(uid)
    existing = next((c for c in creds if normalise_uid(str(c.get("uid"))) == wanted), None)

    if action == "assign":
        if not subject_id:
            raise EditError("assign needs a subject_id")
        if not any(s.get("id") == subject_id for s in doc.get("subjects", [])):
            raise EditError(f"unknown subject {subject_id!r}")
        if existing and existing.get("status") == "active" and existing["subject"] != subject_id:
            raise EditError(f"{wanted} is active for {existing['subject']}; revoke it first")
        if existing:
            existing.update(subject=subject_id, status="active")
        else:
            # A new card has no PIN until one is set out of band, so PIN doors deny it.
            creds.append({"uid": wanted, "subject": subject_id, "status": "active"})
    elif action == "revoke":
        if existing is None:
            raise EditError(f"no credential {wanted}")
        existing["status"] = "revoked"
    else:
        raise EditError(f"unknown action {action!r}")
    return doc
