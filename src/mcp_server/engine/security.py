"""Digests and signatures, byte-compatible with the gateway firmware (access.cpp)."""

from __future__ import annotations

import hashlib
import hmac


def pin_digest(txn: str, pin: str) -> str:
    """What the gateway sends as ``pinDigest``: SHA-256("<txn>:<pin>"), lowercase hex."""
    return hashlib.sha256(f"{txn}:{pin}".encode()).hexdigest()


def acl_pin_digest(uid: str, pin: str) -> str:
    """What the gateway's cached ACL stores for offline checks: SHA-256("<uid>:<pin>")."""
    return hashlib.sha256(f"{uid}:{pin}".encode()).hexdigest()


def sign_decision(key: str, txn: str, effect: str) -> str:
    """HMAC-SHA256 over "<txn>|<effect>". The firmware uses the key's ASCII bytes as-is."""
    message = f"{txn}|{effect}".encode()
    return hmac.new(key.encode(), message, hashlib.sha256).hexdigest()


def verify_decision(key: str, txn: str, effect: str, signature: str) -> bool:
    return hmac.compare_digest(sign_decision(key, txn, effect), signature.lower())


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())
