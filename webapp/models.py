import uuid
from typing import Optional

from pydantic import BaseModel, Field


class CastEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    cast_name: str = ""

    ladcp_station: Optional[int] = None
    ladcp_cast: Optional[int] = None
    ladcpdo: str = ""
    ladcpup: str = ""

    ctd: str = ""
    ctd_header_lines: Optional[int] = None
    ctd_fields_per_line: Optional[int] = None
    ctd_time_field: Optional[int] = None
    ctd_pressure_field: Optional[int] = None
    ctd_temperature_field: Optional[int] = None
    ctd_salinity_field: Optional[int] = None
    ctd_badvals: float = -9e99
    ctd_time_base: int = 0

    nav: str = ""
    nav_header_lines: Optional[int] = None
    nav_fields_per_line: Optional[int] = None
    nav_time_field: Optional[int] = None
    nav_lat_field: Optional[int] = None
    nav_lon_field: Optional[int] = None
    nav_time_base: int = 0
    nav_error: float = 30

    sadcp: str = ""

    drot: Optional[float] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    time_start: Optional[list] = None
    time_end: Optional[list] = None

    btrk_mode: int = 3
    btrk_used: int = 1

    checkpoints_file: str = ""
    res_file: str = ""
    checkpoints_steps: str = "1:16"


class CruiseSession(BaseModel):
    cruise_id: str = ""
    casts: list[CastEntry] = Field(default_factory=list)
