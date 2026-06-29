"""Content-addressed storage and bounded model projections for large tool results."""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from src.core.events import ToolCall
from src.tools.base import ToolResult


@dataclass(frozen=True)
class ArtifactReference:
    """Stable reference to an immutable content-addressed artifact."""

    id: str
    size_bytes: int
    media_type: str


class ArtifactStore:
    """Store immutable blobs by SHA-256 without duplicating identical content."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.blob_root = self.root / "blobs"
        self.blob_root.mkdir(parents=True, exist_ok=True)

    def put_text(self, content: str, media_type: str = "text/plain") -> ArtifactReference:
        return self.put_bytes(content.encode("utf-8"), media_type=media_type)

    def put_bytes(
        self,
        content: bytes,
        media_type: str = "application/octet-stream",
    ) -> ArtifactReference:
        digest = hashlib.sha256(content).hexdigest()
        target = self._path_for_digest(digest)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            descriptor, temporary_name = tempfile.mkstemp(dir=target.parent, prefix=".artifact-")
            temporary_path = Path(temporary_name)
            try:
                with os.fdopen(descriptor, "wb") as temporary:
                    temporary.write(content)
                    temporary.flush()
                    os.fsync(temporary.fileno())
                os.replace(temporary_name, target)
            finally:
                if temporary_path.exists():
                    temporary_path.unlink()
        return ArtifactReference(id=digest, size_bytes=len(content), media_type=media_type)

    def read_bytes(self, artifact_id: str) -> bytes:
        return self._path_for_id(artifact_id).read_bytes()

    def read_text(self, artifact_id: str) -> str:
        return self.read_bytes(artifact_id).decode("utf-8")

    def path_for(self, artifact_id: str) -> Path:
        """Return the validated blob path for diagnostics and exports."""
        return self._path_for_id(artifact_id)

    def _path_for_id(self, artifact_id: str) -> Path:
        if len(artifact_id) != 64 or any(
            character not in "0123456789abcdef" for character in artifact_id
        ):
            raise ValueError(f"Invalid artifact ID: {artifact_id}")
        path = self._path_for_digest(artifact_id)
        if not path.is_file():
            raise FileNotFoundError(f"Unknown artifact: {artifact_id}")
        return path

    def _path_for_digest(self, digest: str) -> Path:
        return self.blob_root / digest[:2] / digest[2:]


class ArtifactBackedResultProcessor:
    """Externalize oversized tool payloads and return a bounded model result."""

    def __init__(self, store: ArtifactStore, max_model_characters: int = 16_000) -> None:
        if max_model_characters < 512:
            raise ValueError("max_model_characters must be at least 512")
        self.store = store
        self.max_model_characters = max_model_characters

    def __call__(self, tool_call: ToolCall, result: ToolResult) -> ToolResult:
        serialized = result.to_model_text()
        if len(serialized) <= self.max_model_characters:
            return result

        reference = self.store.put_text(serialized, media_type="application/json")
        marker = f"\n...[full {tool_call.name} result: artifact:{reference.id}]"
        bounded = replace(
            result,
            content=marker,
            data={"original_size_bytes": reference.size_bytes},
            model_content=marker,
            include_data_in_model=False,
            artifact_ref=reference.id,
            truncated=True,
        )
        remaining = self.max_model_characters - len(bounded.to_model_text())
        prefix = result.content[: max(0, remaining // 2)]
        bounded = replace(bounded, content=prefix + marker, model_content=prefix + marker)
        while len(bounded.to_model_text()) > self.max_model_characters and prefix:
            overflow = len(bounded.to_model_text()) - self.max_model_characters
            prefix = prefix[: max(0, len(prefix) - overflow)]
            bounded = replace(bounded, content=prefix + marker, model_content=prefix + marker)
        return bounded
