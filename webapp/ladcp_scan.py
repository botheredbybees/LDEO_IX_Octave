import re
from dataclasses import dataclass
from pathlib import Path

_FILENAME_RE = re.compile(r"^(?P<station>\d+)(?P<dir>[DU])L\d+\.\d+$", re.IGNORECASE)


@dataclass
class LadcpCastFiles:
    station: str
    down: str = None
    up: str = None


def scan_ladcp_directory(mount_root: Path) -> list:
    by_station: dict = {}
    for entry in sorted(mount_root.iterdir()):
        if not entry.is_file():
            continue
        match = _FILENAME_RE.match(entry.name)
        if not match:
            continue
        station = match.group("station")
        direction = match.group("dir").upper()
        slot = by_station.setdefault(station, {"down": None, "up": None})
        if direction == "D":
            slot["down"] = entry.name
        else:
            slot["up"] = entry.name

    return [
        LadcpCastFiles(station=station, down=files["down"], up=files["up"])
        for station, files in sorted(by_station.items())
    ]
