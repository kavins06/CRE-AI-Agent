"""Host-only immutable artifact pair bound to authenticated digests."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CompanionSnapshot:
    path: Path
    data: bytes
    sha256: str

    def __post_init__(self) -> None:
        if type(self.data) is not bytes or sha256(self.data).hexdigest() != self.sha256:
            raise ValueError("Companion snapshot must match its authenticated digest")


@dataclass(frozen=True, slots=True)
class ArtifactSnapshot:
    data: bytes
    sha256: str
    companions: tuple[CompanionSnapshot, ...] = ()

    def __post_init__(self) -> None:
        if type(self.data) is not bytes or sha256(self.data).hexdigest() != self.sha256:
            raise ValueError("Artifact snapshot must match its authenticated digest")
        if type(self.companions) is not tuple or len(self.companions) > 4:
            raise ValueError("Snapshot companions must be a bounded immutable tuple")
        if len({c.path for c in self.companions}) != len(self.companions):
            raise ValueError("Snapshot companions must have unique paths")
        for companion in self.companions:
            CompanionSnapshot(companion.path, companion.data, companion.sha256)
