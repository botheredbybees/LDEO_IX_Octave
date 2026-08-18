from dataclasses import dataclass, field

from webapp import config, paths, quick_convert
from webapp.models import CruiseSession

REQUIRED_FIELDS = [
    "ladcpdo", "ladcpup", "ladcp_station", "ladcp_cast",
    "lat", "lon", "time_start", "time_end",
]

_NUMERIC_FIELDS_WHERE_ZERO_IS_VALID = {"ladcp_station", "ladcp_cast", "lat", "lon"}

_FILE_FIELDS = [
    ("ladcp", "ladcpdo"),
    ("ladcp", "ladcpup"),
    ("ctd", "ctd"),
    ("nav", "nav"),
    ("sadcp", "sadcp"),
]


@dataclass
class ValidationResult:
    errors: dict = field(default_factory=dict)
    warnings: dict = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        return not any(self.errors.values())


def validate_session(session: CruiseSession) -> ValidationResult:
    result = ValidationResult()

    for cast in session.casts:
        cast_errors = []
        for field_name in REQUIRED_FIELDS:
            value = getattr(cast, field_name)
            if field_name in _NUMERIC_FIELDS_WHERE_ZERO_IS_VALID:
                missing = value is None
            else:
                missing = not value
            if missing:
                cast_errors.append(f"{field_name} is required")
        if cast_errors:
            result.errors[cast.id] = cast_errors

        cast_warnings = []
        for mount_name, field_name in _FILE_FIELDS:
            relative = getattr(cast, field_name)
            if not relative:
                continue
            if field_name == "ctd" and relative.endswith(quick_convert.QUICKCONVERT_SUFFIX):
                mount_root = config.MOUNTS.get("data")
            else:
                mount_root = config.MOUNTS.get(mount_name)
            if mount_root is None:
                cast_warnings.append(f"{relative} not found under {mount_name} mount")
                continue
            try:
                resolved = paths.resolve_within(mount_root, relative)
            except paths.PathOutsideMountError:
                cast_warnings.append(f"{relative} not found under {mount_name} mount")
                continue
            if not resolved.is_file():
                cast_warnings.append(f"{relative} not found under {mount_name} mount")
        if cast_warnings:
            result.warnings[cast.id] = cast_warnings

    return result
