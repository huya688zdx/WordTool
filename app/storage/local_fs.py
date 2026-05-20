import shutil
from pathlib import Path
from typing import Optional
from uuid import uuid4

from app.config.settings import settings


class LocalStorage:
    """Local filesystem storage for documents and generated files."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or settings.STORAGE_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_file(self, source_path: Path, subdir: str = "") -> str:
        """Save a file to storage, return storage key."""
        target_dir = self.base_dir / subdir if subdir else self.base_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        ext = source_path.suffix
        storage_key = f"{subdir}/{uuid4().hex}{ext}" if subdir else f"{uuid4().hex}{ext}"
        target_path = self.base_dir / storage_key

        shutil.copy2(source_path, target_path)
        return storage_key

    def get_path(self, storage_key: str) -> Path:
        """Get absolute path for a storage key."""
        return self.base_dir / storage_key

    def delete_file(self, storage_key: str) -> None:
        """Delete a file from storage."""
        path = self.base_dir / storage_key
        if path.exists():
            path.unlink()


storage = LocalStorage()
