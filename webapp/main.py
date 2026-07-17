from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from webapp import api, config, delimited_parser, file_browser, ladcp_scan, paths

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="LDEO_IX Cruise/Cast Intake")

app.include_router(api.router, prefix="/api")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


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


@app.get("/api/ladcp/scan")
def scan_ladcp():
    mount_root = config.MOUNTS.get("ladcp")
    if mount_root is None or not mount_root.is_dir():
        raise HTTPException(status_code=404, detail="ladcp mount not available")

    results = ladcp_scan.scan_ladcp_directory(mount_root)
    return {
        "casts": [
            {"station": r.station, "down": r.down, "up": r.up} for r in results
        ]
    }
