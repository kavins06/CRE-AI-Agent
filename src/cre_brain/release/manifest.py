"""Self-contained, content-addressed release boundary."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import PurePosixPath
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from cre_brain.config import Settings

Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


def content_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def checked_relative(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if (
        path.as_posix() != name
        or path.is_absolute()
        or "\\" in name
        or ".." in path.parts
        or not (
            len(path.parts) >= 2
            and path.parts[0] == "brain"
            or len(path.parts) == 2
            and path.parts[0] == "config"
            and path.suffix == ".yaml"
        )
    ):
        raise ValueError("Release file path must be within brain/ or config/*.yaml")
    return path


class Snapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    sha256: Digest
    content_base64: str
    mode: int = Field(ge=0, le=0o777, strict=True)

    def content(self) -> bytes:
        payload = base64.b64decode(self.content_base64, validate=True)
        if hashlib.sha256(payload).hexdigest() != self.sha256:
            raise ValueError("Release file content checksum mismatch")
        return payload


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1] = 1
    release_id: Digest
    files: dict[str, Snapshot]
    settings: Settings
    gates_code_hash: Digest
    codex_cli_version: str | None
    firm_playbook_versions: dict[str, str]

    @field_validator("firm_playbook_versions")
    @classmethod
    def nonempty_versions(cls, value: dict[str, str]) -> dict[str, str]:
        if any(not key.strip() or not version.strip() for key, version in value.items()):
            raise ValueError("Firm playbook IDs/versions must be nonblank references")
        return value

    def validate_integrity(self) -> None:
        if content_hash(self.model_dump(mode="json", exclude={"release_id"})) != self.release_id:
            raise ValueError("Release manifest checksum mismatch")
        for name, snapshot in self.files.items():
            checked_relative(name)
            snapshot.content()
