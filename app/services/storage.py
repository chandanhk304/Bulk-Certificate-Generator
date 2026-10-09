"""File storage for generated certificates, behind a small interface (swap for S3 etc.)."""
from pathlib import Path
from typing import Protocol


class FileStorage(Protocol):
    def save(self, key: str, content: bytes) -> None: ...

    def read(self, key: str) -> bytes: ...


class LocalFileStorage:
    """Stores files on local disk under base_dir; keys are plain file names."""

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, key: str, content: bytes) -> None:
        self._path(key).write_bytes(content)

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()  # raises FileNotFoundError if missing

    def _path(self, key: str) -> Path:
        path = (self.base_dir / key).resolve()
        # Guard against keys like "../../etc/passwd" escaping the storage folder.
        if path.parent != self.base_dir:
            raise ValueError(f"Invalid storage key: {key!r}")
        return path
