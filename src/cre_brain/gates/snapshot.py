"""Host-only immutable artifact bytes bound to an authenticated digest."""

from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True, slots=True)
class ArtifactSnapshot:
    data: bytes
    sha256: str

    def __post_init__(self) -> None:
        if type(self.data) is not bytes or sha256(self.data).hexdigest() != self.sha256:
            raise ValueError("Artifact snapshot must match its authenticated digest")
