from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from webapp import config, netcdf_reader, paths, session_store
from webapp.models import CastEntry

router = APIRouter()


class CastPatch(BaseModel):
    model_config = {"extra": "allow"}


@router.get("/session")
def get_session():
    return session_store.load_session()


@router.post("/session/casts", status_code=201)
def create_cast(patch: CastPatch):
    session = session_store.load_session()
    data = patch.model_dump(exclude_unset=True)
    cast = CastEntry(**data)

    if not cast.checkpoints_file and cast.cast_name:
        cast.checkpoints_file = f"checkpoints/{cast.cast_name}"
    if not cast.res_file and cast.cast_name:
        cast.res_file = f"V7/{cast.cast_name}"

    session.casts.append(cast)
    session_store.save_session(session)
    return cast


@router.put("/session/casts/{cast_id}")
def update_cast(cast_id: str, patch: CastPatch):
    session = session_store.load_session()
    for i, cast in enumerate(session.casts):
        if cast.id == cast_id:
            updated = cast.model_copy(update=patch.model_dump(exclude_unset=True))
            session.casts[i] = updated
            session_store.save_session(session)
            return updated
    raise HTTPException(status_code=404, detail=f"cast {cast_id!r} not found")


@router.delete("/session/casts/{cast_id}", status_code=204)
def delete_cast(cast_id: str):
    session = session_store.load_session()
    remaining = [c for c in session.casts if c.id != cast_id]
    if len(remaining) == len(session.casts):
        raise HTTPException(status_code=404, detail=f"cast {cast_id!r} not found")
    session.casts = remaining
    session_store.save_session(session)


@router.post("/session/casts/{cast_id}/clone", status_code=201)
def clone_cast(cast_id: str):
    session = session_store.load_session()
    for cast in session.casts:
        if cast.id == cast_id:
            data = cast.model_dump()
            data.pop("id")
            clone = CastEntry(**data)
            session.casts.append(clone)
            session_store.save_session(session)
            return clone
    raise HTTPException(status_code=404, detail=f"cast {cast_id!r} not found")


@router.post("/session/casts/from-netcdf", status_code=201)
def create_cast_from_netcdf(path: str):
    mount_root = config.MOUNTS.get("data")
    try:
        resolved = paths.resolve_within(mount_root, path)
    except paths.PathOutsideMountError:
        raise HTTPException(status_code=400, detail="path is outside the allowed directory")

    try:
        attrs = netcdf_reader.read_global_attributes(resolved)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"{path!r} not found")

    known_fields = set(CastEntry.model_fields.keys())
    prefill = {k: v for k, v in attrs.items() if k in known_fields}

    session = session_store.load_session()
    cast = CastEntry(**prefill)
    session.casts.append(cast)
    session_store.save_session(session)
    return cast
