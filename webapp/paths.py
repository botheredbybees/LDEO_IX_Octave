from pathlib import Path, PurePosixPath


class PathOutsideMountError(Exception):
    pass


def resolve_within(mount_root: Path, relative: str) -> Path:
    if relative in ("", "."):
        candidate_parts: tuple = ()
    else:
        rel = PurePosixPath(relative.replace("\\", "/"))
        if rel.is_absolute() or ".." in rel.parts:
            raise PathOutsideMountError(f"{relative!r} is not a safe relative path")
        candidate_parts = rel.parts

    root = mount_root.resolve()
    candidate = root.joinpath(*candidate_parts).resolve()

    try:
        candidate.relative_to(root)
    except ValueError:
        raise PathOutsideMountError(f"{relative!r} escapes mount root {root}")

    return candidate
