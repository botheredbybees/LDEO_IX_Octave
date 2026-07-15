% EXAMPLE set_cast_params.m -- one real GO-SHIP cast (P16N station 3), for
% reference only. Copy this into your own working directory as
% `set_cast_params.m`, rename to your cast, and edit every field.
%
% A real cruise's set_cast_params.m normally has a `switch stn ... end` with
% one case per station; this example only ever processes cast 003, so it is
% unconditional. Values below were taken from the source cruise's recorded
% p-struct (LDEO's own archived processing run for this cast) wherever the
% field is a true *input* (not something loadrdi/loadctd/etc. compute and
% record back) -- so this file also serves as a worked reference for which
% fields are inputs vs. derived outputs.
%
% Expects cwd to contain `data/raw/...` and `data/CTD/2Hz/...` as referenced
% below -- adjust the paths to match your own working directory layout.

cruise_id = 'P16N';
p.cruise_id = cruise_id;

f.ladcpdo = 'data/raw/003DL000.000';
f.ladcpup = 'data/raw/003UL000.000';
p.ladcp_station = 3;
p.ladcp_cast = 1;
p.name = '003';

% CTD/nav time series -- a CTD .cnv time series decimated to 2 Hz. Field
% layout matches the recorded p-struct exactly (ctd_fields_per_line etc.).
%
% All of these are read off the `f` struct (loadctd.m/loadnav.m's own
% setdefv() calls default them on f, e.g. loadctd.m:40-52) -- NOT `p`,
% despite the recorded 003.nc attributes flattening f/p/ps together.
f.ctd = 'data/CTD/2Hz/003.2Hz';
f.nav = 'data/CTD/2Hz/003.2Hz';
f.ctd_header_lines = 0;
f.ctd_fields_per_line = 11;
f.ctd_time_field = 1;
f.ctd_pressure_field = 2;
f.ctd_temperature_field = 3;
f.ctd_salinity_field = 4;
f.ctd_badvals = -999;
f.ctd_time_base = 0;
f.nav_header_lines = 0;
f.nav_fields_per_line = 11;
f.nav_time_field = 1;
f.nav_lat_field = 10;
f.nav_lon_field = 11;
% BUG in the in-tree loadnav.m (IX_14beta): its own setdefv() call (line 72)
% defaults nav_time_base onto `p`, but the switch that consumes it (line 137)
% reads `f.nav_time_base` -- so with only p.nav_time_base set, loadnav.m
% dies with "structure has no member 'nav_time_base'". loadctd.m's changelog
% (line 85) shows the identical ctd_time_base bug WAS fixed on 2014-03-21;
% the fix was apparently never ported to loadnav.m. Worked around here by
% setting both, rather than patching the copied .m file.
f.nav_time_base = 0;
p.nav_time_base = 0;
p.nav_error = 30;

% Recorded magnetic deviation (GEN_Magnetic_deviation_deg) -- hardcoded
% here rather than relying on magdev.m.
p.drot = 12.318441;
p.lat = -15.498335;
p.lon = -150.19699;

% ctd_time_base/nav_time_base=0 means "elapsed seconds since p.time_start"
% (see loadctd.m/loadnav.m case 0) -- p.time_start/time_end must match the
% reference your decimated CTD file's field 1 is relative to (its own first
% and last scan). This also happens to match the raw .cnv's own header
% ("System UpLoad Time = Apr 11 2015 17:36:23").
p.time_start = [2015 4 11 17 36 23.312975];
p.time_end   = [2015 4 11 21 9 42.220459];

% No SADCP file in this example. Leaving f.sadcp unset makes loadsadcp.m
% skip cleanly (existf(f,'sadcp')==0).

p.btrk_mode = 3;
p.btrk_used = 1;

f.checkpoints = 'checkpoints/003';
f.res = 'V7/003';
% Checkpoint after every step so a crashed run (e.g. while whack-a-moling
% plotting stubs) can resume via process_cast(stn, N, 0) instead of
% re-running loadrdi.m (~4 min) from scratch every time.
p.checkpoints = 1:16;
