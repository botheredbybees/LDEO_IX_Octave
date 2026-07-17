import os
from pathlib import Path

MOUNTS: dict[str, Path] = {
    "data": Path(os.environ.get("LDEO_DATA_DIR", "/data")),
    "ladcp": Path(os.environ.get("LDEO_LADCP_DIR", "/ladcp_data")),
    "ctd": Path(os.environ.get("LDEO_CTD_DIR", "/ctd_data")),
    "sadcp": Path(os.environ.get("LDEO_SADCP_DIR", "/sadcp_data")),
    "nav": Path(os.environ.get("LDEO_NAV_DIR", "/navigation_data")),
}

SESSION_FILE_NAME = ".cruise_intake_session.json"


def available_mounts() -> dict[str, Path]:
    return {name: path for name, path in MOUNTS.items() if path.is_dir()}
