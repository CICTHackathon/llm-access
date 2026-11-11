"""Digests and signatures must match the firmware byte for byte."""

from src.mcp_server.engine.domain.access import gateway_reason
from src.mcp_server.engine.security import (
    acl_pin_digest,
    pin_digest,
    sign_decision,
    verify_decision,
)

TXN = "0123456789abcdef"


def test_pin_digest_is_salted_with_the_transaction() -> None:
    assert pin_digest(TXN, "1234") == (
        "c9f29cbedcc0104cfa8a7755f2bebdb620997d0cb56ddd228f30318c001f4b4a")


def test_acl_digest_is_salted_with_the_uid() -> None:
    assert acl_pin_digest("0xa1b2c3d4", "1234") == (
        "98cfe16fc1b600cd3b2f93c3da7f797e749a9e0a0eef04bb48fdca19d1e850e0")


def test_decision_signature_covers_txn_and_effect() -> None:
    sig = sign_decision("bench-key", TXN, "permit")
    assert sig == "34f5c1f686052540c94f514cd2a68f631fefb18ce645f0e3562e47452a0fb273"
    assert verify_decision("bench-key", TXN, "permit", sig.upper())
    assert not verify_decision("bench-key", TXN, "deny", sig)


def test_reason_is_safe_for_the_firmware_parser() -> None:
    reason = gateway_reason('deny, "quoted" {brace} and far too long for the buffer')
    assert len(reason) <= 23
    assert not set(reason) & set(',"{}')
