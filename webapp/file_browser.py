from dataclasses import dataclass
from pathlib import Path

from webapp import paths


@dataclass
class DirEntry:
    name: str
    is_dir: bool
    relative_path: str


def list_directory(mount_root: Path, relative: str = "") -> list[DirEntry]:
    target = paths.resolve_within(mount_root, relative)
    if not target.is_dir():
        raise NotADirectoryError(f"{target} is not a directory")

    prefix = relative.strip("/")
    entries = []
    for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        rel = f"{prefix}/{child.name}" if prefix else child.name
        entries.append(DirEntry(name=child.name, is_dir=child.is_dir(), relative_path=rel))
    return entries
