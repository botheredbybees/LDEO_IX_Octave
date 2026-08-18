import re

# Order matters: for a given column, the first pattern in this dict that
# matches wins that column's role. Case-insensitive substring search
# against the real column name text (e.g. "CTDPRS" contains "PRS").
_ROLE_PATTERNS: dict[str, "re.Pattern[str]"] = {
    "pressure": re.compile(r"PRS|PRES", re.IGNORECASE),
    "temperature": re.compile(r"TMP|TEMP", re.IGNORECASE),
    "salinity": re.compile(r"SAL", re.IGNORECASE),
    "time": re.compile(r"TIME|DATE", re.IGNORECASE),
    "lat": re.compile(r"LAT", re.IGNORECASE),
    "lon": re.compile(r"LON", re.IGNORECASE),
}


def suggest_roles(column_names: list | None) -> dict:
    """Guess which column plays which role, by name pattern.

    Returns {role: 1-based column index} for every role a column name
    matched. A role is only suggested once -- the first column (in
    file order) whose name matches that role's pattern wins it. A role
    with no matching column is simply absent from the result, and the
    caller (the CTD/Nav field-mapping UI) leaves that field for the
    user to set manually.
    """
    if not column_names:
        return {}

    suggestions: dict[str, int] = {}
    for index, name in enumerate(column_names, start=1):
        for role, pattern in _ROLE_PATTERNS.items():
            if role in suggestions:
                continue
            if pattern.search(name):
                suggestions[role] = index
                break
    return suggestions
