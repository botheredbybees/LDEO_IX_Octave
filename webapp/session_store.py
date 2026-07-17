from pathlib import Path

from webapp import config
from webapp.models import CruiseSession


def session_path() -> Path:
    return config.MOUNTS["data"] / config.SESSION_FILE_NAME


def load_session() -> CruiseSession:
    path = session_path()
    if not path.is_file():
        return CruiseSession()
    return CruiseSession.model_validate_json(path.read_text(encoding="utf-8"))


def save_session(session: CruiseSession) -> None:
    path = session_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(session.model_dump_json(indent=2), encoding="utf-8")
