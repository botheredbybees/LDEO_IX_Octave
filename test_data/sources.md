# Test data sources

Real cruise data pulled in to test the webapp's cast-intake form against
raw/near-raw files organized by someone other than LDEO/Thurnherr — every
dataset previously used in the sister `LADCP` project came from the same
processing lineage (A.M. Thurnherr, LDEO), so none of it exercised the
webapp against an independent organization's file conventions.

Bulk data itself is gitignored (`test_data/*`, this file excepted) — same
convention as `LADCP/test_data/sources.md`. Re-fetch by following the
download links below if a fresh checkout needs the files back.

## Both datasets, general notes

- Source: Australian Antarctic Data Centre (`data.aad.gov.au`), voyages of
  the AAD's former icebreaker *Aurora Australis* — genuinely different
  organization, vessel, and era from every existing test dataset.
- License: **CC BY 4.0** (AADC's site-wide default) — free to use with
  attribution, confirmed on each dataset's metadata page.
- Download mechanism: AADC's download form takes an email address, then
  auto-downloads the zip in-browser for datasets under 2GB/10k files (all
  of these qualify) and also emails a one-time link to the same address.
  Downloaded via Playwright (email `peter.shanks@aad.gov.au`) on
  2026-08-16, since the download page is a JS SPA with no direct/scriptable
  endpoint found.
- **Courtesy-ask note, now moot:** both the BROKE-West CTD and au0304
  ADCP/CTD READMEs ask that data users email `mark.rosenberg@utas.edu.au`
  (ACE CRC) with name/institution and intended use. Per Peter (2026-08-16),
  Mark Rosenberg is long retired — that address is unlikely to be
  monitored, so this isn't being chased further. Data use is still fully
  covered by the CC BY 4.0 license regardless.
- **Neither AADC dataset includes raw LADCP binary files** — BROKE-West's
  `LADCP` record ships only the *final processed* output
  (`AU0603_LADCP_processed_allstations.mat`, no raw `.adp`); au0304's
  title mentions LADCP but none actually appears in the archive. Useful
  for CTD/SADCP/nav testing and as a validation target, not for raw-file
  pairing logic. **Resolved by `in2021_v04_investigator/` below**, which
  has genuine raw PD0 files.

## `broke_west_au0603/` — BROKE-West survey, Aurora Australis voyage 3, 2005/06

Southern Ocean, 30–80°E, 120 CTD stations. Three separate AADC records
combined here:

| Subdir | AADC dataset | eds_id | DOI | Size |
|---|---|---|---|---|
| `ladcp/` | `BROKE-West_LADCP` | 2890 | `10.4225/15/59893efaec5f0` | 390 kB (processed output only, see gap above) |
| `sadcp/` | `BROKE-West_ADCP` | 2879 | `10.4225/15/598405ffdd501` | 10.7 MB |
| `ctd/` | `BROKE-West_CTD_au0603` | 4909 | `10.26179/5ceb6d79c35a4` | 37.7 MB |

`ctd/` is real Seabird SBE 704 data — 2-dbar-averaged ASCII (`*.all`
files, one per station, documented header format) plus a combined
`a0603.mat`. `sadcp/` is the ship-mounted ADCP, ASCII (`.cny`) + MATLAB
(`.mat`), full-cruise and "on-station" (<0.35 m/s) subsets. No dedicated
underway/Seapath file was found for this voyage despite the CTD dataset's
abstract mentioning underway sensors — the CTD data itself covers the
"at least Seapath" requirement for this cruise.

## `au0304_kaos/` — Kerguelen Plateau DWBC Experiment ("KAOS"), Aurora Australis voyage 4, 2002/03

South Indian Ocean / Kerguelen Plateau, WOCE I08 transect, 64 CTD
stations. Single AADC record, split into subdirs here:

| Subdir | Contents | Format |
|---|---|---|
| `ctd/` | `a0304.mat` + per-station docs | Seabird CTD, MATLAB |
| `sadcp/` | `au030401.cny`, `a0304dop.mat` (+ "on-station" subset) | ship ADCP, ASCII + MATLAB |
| `navigation/` | `kaos.ora` (31 MB, 1-minute-resolution) | ASCII, "Aurora Australis oracle database" export — GPS/met/bathymetry/SST-SSS, 30+ columns, distinct format from anything else in either repo's test corpus |

Dataset: `au0304`, eds_id 1338, DOI `10.4225/15/58ad0bd50bd58`, 51.85 MB.

## `in2021_v04_investigator/` — RV Investigator voyage IN2021_V04, 2021

A third organization (CSIRO / Marine National Facility) and a third,
current-generation vessel — genuinely different lineage from both AADC
datasets above. Sourced from Peter's local copy
(`/media/peter_sha/PeterShanks_LACIE/in2021_v04/`), not downloaded — one
representative cast's worth of raw files across every instrument stream
needed, not a full-voyage archive:

| Subdir | Contents | Format | Size |
|---|---|---|---|
| `ladcp/` | `Deployment002/{Master,Slave}/Data/*.000` | **Genuine raw RDI Workhorse PD0 binary** (`0x7F 0x7F` header verified) — Master=down-looker (3.4 MB), Slave=up-looker (2.4 MB), plus `Metadata/*.rds`/`.txt` deployment logs | 5.7 MB |
| `ctd/` | `in2021_v04_001.hex` + `.bl`/`.hdr`/`.XMLCON`/config | **Genuine raw Sea-Bird SBE 9 hex** (unprocessed, unlike either AADC CTD dataset) | 11 MB |
| `sadcp/` | `inv2021_180_03711.raw(.log)` | Ocean Surveyor 150 shipboard ADCP raw | 2 MB |
| `navigation/` | `20210705-123512-seapath_01.SEAPA` (196 MB raw), `inv2021_180_14400.sea` (2.4 MB ASCII NMEA subset — `$GPGGA`/`$GPHDT`/`$PSXN`/`$PYRTM`) | **Genuine Kongsberg Seapath log** — this is the actual "Seapath data" originally asked for, not a proxy | 198 MB |
| `navigation/gps_nav/`, `navigation/doppler/` | Same-cast GPS and doppler-log extras, kept alongside Seapath | ASCII/binary | small |

This finally closes the raw-LADCP gap both AADC datasets left open —
`ladcp_scan.py`'s raw-file down/up pairing logic now has a real PD0 pair
to run against.

**Cross-instrument numbering mismatch, worth knowing about (a realistic
test case, not a data error):** the CTD's own plan file calls this cast
`"deployment": 1` (`in2021_v04_001_plan.json`), while the LADCP logging
system calls the same physical cast `Deployment: 2`
(`LADCP/Deployment002/DeploymentInfo.txt`) — different instruments'
logging software numbering the same event differently. Both are dated/
timed to the same cast (Jul 6 2021, ~08:39 UTC cast start). Anything that
tries to auto-pair LADCP/CTD files by deployment number rather than
time/position will get this wrong — exactly the kind of real-world
mismatch a from-scratch intake form needs to handle.

No on-drive README — provenance is Peter's own field copy, not a public
archive; nothing further to cite/link.

## Follow-up

- The AADC courtesy-email item above is closed out (moot, not pursued).
- `in2021_v04_investigator/` only has one cast — if more Investigator
  casts/voyages are wanted later, CSIRO's Data Access Portal
  (`data.csiro.au`) has per-voyage collections tagged with the "LADCP
  (Lowered Acoustic Doppler Current Profiler)" keyword going back to 2016
  (e.g. `IN2023_V04` "Data Products", DOI `10.25919/xv8a-z860`, CC BY
  4.0) — checked one: it ships QC'd LADCP output (not raw `.000`s), same
  gap as AADC. Raw data for that record is separately gated behind an
  "End-of-Voyage (EOV) Archive" request (`data-requests-hf@csiro.au`),
  not a direct download — not pursued further since the local
  `in2021_v04` copy already solved the raw-file gap directly. Revisit
  only if a second/third raw LADCP cast (for cross-voyage diversity) is
  actually needed.
