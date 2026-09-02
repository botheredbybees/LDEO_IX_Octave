# Cruise/Cast Intake — User Guide

This is the day-to-day operating guide for the web form used to build
`set_cast_params.m` — the one file LDEO_IX needs per cast to process LADCP
data. If you're setting up or deploying this Docker image rather than
using an already-running one, see the main README instead (`README.md`
at the repository root); this guide assumes the form is already open in
your browser.

## Before you start: mounted directories

The form reads and writes files under a handful of mount points, each
pointing at a directory on disk (set up by whoever ran `docker run` —
see the README's example):

| Mount | What lives there |
|---|---|
| `data` | Your working directory. `set_cast_params.m` is written here, and Quick-convert's output goes in `data/quick_convert/`. |
| `ladcp` | Raw LADCP down/up files (`.000`-style Workhorse ADCP files). |
| `ctd` | Pre-converted CTD time series files. |
| `nav` | Navigation time series files. |
| `sadcp` | Shipboard ADCP files (optional — not every cruise has these). |

A mount that wasn't set up when the container was started simply won't
offer a Browse button for that file type. If a Browse button is missing
where you expect one, that's the first thing to check with whoever
started the container.

## The cast list

The top of the page has one field, **Cruise ID**, and a list of casts.
Each cast card shows its name, station, and lat/lon (or `?` for anything
not filled in yet) with **Edit**, **Clone**, and **Remove** buttons.

- **Add cast** creates a new, mostly-blank cast and opens it for editing.
- **Clone** copies everything from an existing cast (a good starting point
  for a re-occupied station or a near-identical cast).
- **Remove** deletes a cast from this session — this only affects the
  in-progress session, not any `set_cast_params.m` you've already
  generated.

### Guessed file locations for a new cast

If you already have at least one cast in the list, **Add cast** tries to
guess the new cast's LADCP/CTD/Nav file locations and field mapping from
the previous cast — incrementing the station number in each filename
(e.g. offering `004DL000.000` after `003DL000.000`) and checking that the
guessed file actually exists before offering it. When this happens, you'll
see a banner:

> ⚠ File locations and field mapping were guessed from the previous
> cast — please verify before saving.

Treat every guessed value as a starting point, not a fact — always check
it against the real files before saving. If a guess can't be confirmed
(the file doesn't exist, or its column count doesn't match), that piece is
simply left blank rather than offering something wrong.

## Raw LADCP files

LDEO_IX's naming convention pairs a down cast and an up cast per station:
a filename like `003DL000.000` (station `003`, **D**own) and
`003UL000.000` (station `003`, **U**p). The **Raw LADCP files** section
scans the `ladcp` mount for files matching this pattern and lists every
station it finds in the dropdown — pick one and click **Use selected
pair** to fill in Station, Down file, and Up file (and set Name to match,
if it's still blank) in one step. You can also fill Down/Up file
individually via their own **Browse** buttons if a cast doesn't fit the
paired convention.

**Cast** is which LADCP cast number this is at the station — almost
always `1` unless the station was re-occupied.

## CTD data

**The CTD field expects an already-converted time series, not a raw
`.hex` file.** The standard way to get one is Sea-Bird's own SBE Data
Processing software; see [Quick-convert](#quick-convert-unvalidated)
below if that's genuinely not available.

Click **Browse** to pick a file, then **Preview / map columns** to see
its contents and map which column is which:

- If the file has real Sea-Bird column names (either a genuine `.cnv`
  file's `# name N = shortname: ...` header lines, or an older-style
  header row like `CTDPRS CTDTMP CTDCOND CTDSAL`), the preview shows
  those names and a dropdown per role (Time/Pressure/Temperature/
  Salinity) is pre-filled with its best guess — labeled by column name,
  e.g. "2: CTDTMP".
- If the file has no header at all, the preview instead shows generic
  `col 1`, `col 2`, ... labels, and none of the role dropdowns are
  pre-filled — pick each one manually.
- Every dropdown has an **Enter index manually** fallback if you'd rather
  type a 1-based column number directly (useful for a role the
  auto-suggest didn't recognize, or a genuinely undocumented file).

None of this is locked in until you save — the auto-suggestion is always
a starting point, not a decision made for you.

**Bad value** is the numeric flag used for missing/bad readings in the
file (Sea-Bird's usual default is `-9.99e-29`; older BROKE-West-style
files often use `-9e99` or `-999` — check what your file actually uses).

## Quick-convert (unvalidated)

If a cast's CTD data was never run through Sea-Bird's own processing
software, the **Quick-convert raw hex** section (under the CTD fieldset)
can turn a raw `.hex` + `.XMLCON` pair into a usable file automatically.

**This is a fallback for when nothing else is available, not a
replacement for real Sea-Bird processing.** Its output is not guaranteed
Sea-Bird-equivalent and should never be treated as publication-grade
without independent verification later. Converted files are written to
`data/quick_convert/` and always named
`<original>.UNVALIDATED_QUICKCONVERT.cnv`, so the provenance travels with
the file — if you (or anyone downstream) later find this filename in a
processed dataset, that's the signal to double-check it against a real
conversion.

## Nav data

Works the same way as CTD: **Browse**, then **Preview / map columns** to
map Time, Lat, and Lon fields, with the same auto-suggest / manual-entry
fallback. **Nav error** is the assumed navigation-fix uncertainty in
meters (defaults to 30).

## Position / time / bottom-tracking

- **Lat** / **Lon**: the cast's nominal position (decimal degrees; south
  and west are negative).
- **Magnetic deviation (drot)**: local compass deviation, if known —
  leave blank if not.
- **Time start** / **Time end**: cast start/end time as
  `Y M D h m s` (e.g. `2015 4 11 17 36 23.0`).
- **Bottom-track mode** / **Bottom-track used**: LDEO_IX's own
  bottom-tracking configuration for this cast — see LDEO_IX's own
  `process_cast.m` documentation if you're unsure what these should be
  for your instrument.

## Saving and generating

**Save cast** writes the current cast's edits into this browser session
only — it does not touch `set_cast_params.m` on disk. The chip next to
the button tracks this: **Unsaved changes** while you're editing,
**Saved** once you've saved. Switching to a different cast or reloading
the page without saving will lose in-progress edits to the one you were
on.

**Generate set_cast_params.m** is the step that actually writes the file,
for every cast currently in the session — not just the one you're
editing. It:

1. Checks every cast has all of its required fields (LADCP down/up file,
   station, cast number, lat, lon, and time start/end) — if anything's
   missing, it reports exactly what and where, and writes nothing.
2. If any referenced file (LADCP/CTD/Nav/SADCP) can't actually be found
   under its mount, that's reported as a warning, not an error — the file
   still gets generated, since the mount that's missing it now might be
   different from the one that'll be used when you actually process the
   cast.
3. Backs up any existing `data/set_cast_params.m` (as
   `set_cast_params.m.bak.<timestamp>`) before overwriting it, so a bad
   generate never destroys a previous one.

## Troubleshooting

**"`<field>` is required"** — one of the required fields (LADCP down/up
file, station, cast number, lat, lon, time start, time end) is empty for
one of your casts. Open that cast and fill it in.

**"`<file>` not found under `<mount>` mount"** — a file path in one of
your casts doesn't exist under the directory that was mounted for it.
Common causes: a typo, a guessed path that turned out wrong (see
[Guessed file locations](#guessed-file-locations-for-a-new-cast) above),
or the wrong host directory was mounted when the container was started.

**A Browse button or file preview shows nothing** — check that the
relevant mount (`ladcp`/`ctd`/`nav`/`sadcp`) was actually set up when the
container was started; see [Before you start](#before-you-start-mounted-directories).

**No login screen, and I'm worried about who else can reach this** — by
design, there isn't one. This form is built for a single trusted
operator on a directory they already have access to. If it's reachable
by anyone besides you, treat that as a network configuration problem to
fix (bind to `127.0.0.1`, use an SSH tunnel, or don't publish the port),
not something this tool itself can protect against.

**Anything else** — the repository's `README.md` covers building and
running the image, the direct Octave CLI workflow, and licensing; if
your question is about LDEO_IX's actual processing steps rather than this
intake form, `ldeo_ix/process_cast.m`'s own docstring is the reference.
