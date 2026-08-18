from webapp.field_role_suggest import suggest_roles


def test_suggests_ctd_roles_from_broke_west_style_header():
    column_names = [
        "CTDPRS", "CTDTMP", "CTDCOND", "CTDSAL", "CTDOXY",
        "FLUORO", "PAR", "TRANS", "NPTS",
    ]

    suggestions = suggest_roles(column_names)

    assert suggestions == {"pressure": 1, "temperature": 2, "salinity": 4}


def test_suggests_nav_roles_from_plain_header():
    column_names = ["time", "lat", "lon"]

    suggestions = suggest_roles(column_names)

    assert suggestions == {"time": 1, "lat": 2, "lon": 3}


def test_first_matching_column_wins_for_each_role():
    column_names = ["TIME1", "TIME2", "PRS"]

    suggestions = suggest_roles(column_names)

    assert suggestions["time"] == 1
    assert suggestions["pressure"] == 3


def test_returns_empty_dict_for_no_column_names():
    assert suggest_roles(None) == {}
    assert suggest_roles([]) == {}


def test_no_suggestion_for_unmatched_roles():
    # CTDCOND matches no tracked role -- conductivity isn't one of the
    # roles this form maps -- and nothing here looks like a date/lat/lon.
    suggestions = suggest_roles(["CTDCOND"])
    assert suggestions == {}
