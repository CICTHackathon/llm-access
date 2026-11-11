"""Subjects and the credentials (RFID cards + PIN) they carry."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SubjectStatus = Literal["active", "suspended", "terminated"]
CredentialStatus = Literal["active", "revoked", "lost"]


def normalise_uid(uid: str) -> str:
    """Canonical card UID as the gateway spells it: ``0x`` + lowercase hex."""
    value = uid.strip().lower()
    return value if value.startswith("0x") else f"0x{value}"


class Subject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str = ""
    roles: list[str] = Field(default_factory=list)
    department: str | None = None
    clearance: int = Field(0, ge=0)
    status: SubjectStatus = "active"
    valid_until: date | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)

    def public_view(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class Credential(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uid: str
    subject: str
    pin: str | None = Field(default=None, repr=False)
    status: CredentialStatus = "active"
    expires: date | None = None

    @field_validator("uid")
    @classmethod
    def _normalise(cls, value: str) -> str:
        return normalise_uid(value)

    def public_view(self) -> dict[str, Any]:
        """Everything except the PIN, which never leaves the PDP."""
        data = self.model_dump(mode="json", exclude={"pin"})
        data["has_pin"] = bool(self.pin)
        return data


class Directory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subjects: list[Subject] = Field(default_factory=list)
    credentials: list[Credential] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_references(self) -> Directory:
        ids = [s.id for s in self.subjects]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate subject id")
        uids = [c.uid for c in self.credentials]
        if len(uids) != len(set(uids)):
            raise ValueError("duplicate credential uid")
        known = set(ids)
        for cred in self.credentials:
            if cred.subject not in known:
                raise ValueError(f"credential {cred.uid}: unknown subject {cred.subject!r}")
        return self

    def subject(self, subject_id: str) -> Subject | None:
        return next((s for s in self.subjects if s.id == subject_id), None)

    def credential(self, uid: str) -> Credential | None:
        wanted = normalise_uid(uid)
        return next((c for c in self.credentials if c.uid == wanted), None)

    def credentials_of(self, subject_id: str) -> list[Credential]:
        return [c for c in self.credentials if c.subject == subject_id]
