from fastapi import FastAPI, HTTPException

from webapp import config, delimited_parser, file_browser, paths

app = FastAPI(title="LDEO_IX Cruise/Cast Intake")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/mounts")
def list_mounts():
    return {"mounts": sorted(config.available_mounts().keys())}


@app.get("/api/browse/{mount}")
def browse(mount: str, path: str = ""):
    mount_root = config.MOUNTS.get(mount)
    if mount_root is None or not mount_root.is_dir():
        raise HTTPException(status_code=404, detail=f"mount {mount!r} not available")

    try:
        entries = file_browser.list_directory(mount_root, path)
    except paths.PathOutsideMountError:
        raise HTTPException(status_code=400, detail="path is outside the allowed directory")
    except NotADirectoryError:
        raise HTTPException(status_code=400, detail="path is not a directory")

    return {
        "entries": [
            {"name": e.name, "is_dir": e.is_dir, "relative_path": e.relative_path}
            for e in entries
        ]
    }


@app.get("/api/preview/{mount}")
def preview_file(mount: str, path: str):
    mount_root = config.MOUNTS.get(mount)
    if mount_root is None or not mount_root.is_dir():
        raise HTTPException(status_code=404, detail=f"mount {mount!r} not available")

    try:
        resolved = paths.resolve_within(mount_root, path)
    except paths.PathOutsideMountError:
        raise HTTPException(status_code=400, detail="path is outside the allowed directory")

    if not resolved.is_file():
        raise HTTPException(status_code=404, detail=f"{path!r} is not a file")

    preview = delimited_parser.sniff_and_preview(resolved)
    return {
        "header_lines": preview.header_lines,
        "fields_per_line": preview.fields_per_line,
        "preview_rows": preview.preview_rows,
    }
