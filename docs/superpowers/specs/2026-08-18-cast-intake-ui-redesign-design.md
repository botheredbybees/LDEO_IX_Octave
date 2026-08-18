# Cast-intake UI redesign — design spec

Status: draft

## Problem

`webapp/`'s cast-intake form (`templates/index.html`, `static/style.css`,
`static/app.js`) is fully functional but has zero visual design — plain
browser-default HTML, one unbroken single-column layout, no visual
hierarchy between primary and secondary actions. Screenshotted baseline:
a ~1400px-wide viewport with a form that never uses more than ~350px of
horizontal space, four stacked fieldsets each a single column of
label+input pairs, and Edit/Clone/Remove buttons crammed into one table
cell.

Beyond the visual gap, one real usability problem: the CTD/Nav field-index
inputs (`ctd_time_field`, `ctd_pressure_field`, etc.) are plain number
boxes the user fills in by guessing a raw column position, with no
indication of what's actually in that column beyond the CTD/Nav preview
panel's raw numeric rows. Real CTD files often carry a genuine header line
(confirmed against a real BROKE-West `.all` file:
`CTDPRS CTDTMP CTDCOND CTDSAL CTDOXY FLUORO PAR TRANS NPTS`) that
`delimited_parser.sniff_and_preview()` currently detects the *position*
of (to know how many lines to skip) but discards the *text* of entirely.
Not universal, though — the native LDEO 2Hz format is genuinely headerless
(one line per sample, no header at all — see
`test_sniffs_zero_header_lines_and_field_count` in
`webapp/tests/test_delimited_parser.py`), so any fix has to degrade
gracefully.

## Goals

1. A real visual design (Nuyina Design system's "Nocturne" dark theme —
   see the RSV Nuyina Science Data Pipeline Claude Design project) ported
   into this repo's plain CSS, no build toolchain.
2. A restructured layout that uses the available horizontal space and
   gives primary/secondary actions distinct visual weight.
3. CTD/Nav field mapping driven by real column names when the source file
   has them, with a graceful manual-entry fallback when it doesn't.
4. Visible unsaved/saved state on the cast editor.
5. File-browser and CTD/Nav preview panels presented as a clear modal
   overlay, not an inline page-pushing expand.

## Non-goals

- No change to `ldeo_ix/` (Octave/MATLAB code) or the Docker image itself.
- No Node/build toolchain — stays FastAPI + Jinja2 + hand-written CSS/JS,
  per this repo's existing constraint (`CLAUDE.md`).
- No new backend framework or client-side framework (React/Vue/etc).
- Not attempting to auto-detect every possible CTD/Nav file dialect's
  header format — reuses the existing `sniff_and_preview` heuristic
  (first all-numeric line marks the end of the header), extended to also
  capture header text, not replacing that heuristic.

## Design

### 1. Column-name-aware field mapping (backend)

`delimited_parser.sniff_and_preview()` gains a `column_names:
list[str] | None` field on `DelimitedPreview`. After the existing
header/data split, scan the header lines (there may be more than one —
e.g. BROKE-West has a names line then a units line) and pick the one
whose `split()` length equals `fields_per_line`; if none matches (or
`header_lines == 0`), `column_names` is `None`. This is a pure addition —
`header_lines`/`fields_per_line`/`preview_rows` behavior is unchanged, so
every existing test in `test_delimited_parser.py` keeps passing unmodified.

`main.py`'s `/api/preview/{mount}` response gains a `"column_names"` key
(the list, or `null`).

### 2. Column-name-aware field mapping (frontend)

The main fieldset's per-role inputs (`ctd_time_field`,
`ctd_pressure_field`, `ctd_temperature_field`, `ctd_salinity_field`, and
the Nav equivalents) change from `<input type="number">` to `<select>`,
populated after a preview has been fetched, with each `<option>` labeled
`"<index>: <column name>"` when `column_names` is available. A lightweight
regex auto-suggest pre-selects the likely role per column on first
render — `PRS|PRES` → pressure, `TMP|TEMP` → temperature, `SAL` →
salinity, `COND` → (no role, left as manual pick — conductivity isn't
one of the tracked roles), `TIME|DATE` → time, `LAT` → lat, `LON` → lon —
matched case-insensitively against each column name; the user can always
override. Each select carries an "Enter index manually" toggle that swaps
it for a plain number input — the fallback path for headerless files
(`column_names is None`) or any file whose real mapping the heuristic
gets wrong. The generated `set_cast_params.m` payload is unaffected: both
paths ultimately write the same numeric index into the same named form
field, `template_gen.py` doesn't change.

The existing preview-table per-column role-select (in `renderPreview`,
`app.js`) is removed — it was a second, redundant mechanism for setting
the same fields. The preview table itself stays (raw sample rows are
still useful to sanity-check a mapping), now with column names as real
`<th>` headers instead of blank/index-only columns.

### 3. Visual system

New CSS custom-property token layer in `static/style.css`, hand-ported
from the Nuyina Design "Nocturne" theme's values (not its JS/bundle) —
dark background (`#12131f`-family), purple accent scale, `Inter` typeface
(Google Fonts `<link>`, same mechanism the data-flow diagram project
uses — no bundler). Buttons get two visual tiers: primary (Save cast,
Generate, filled/accent) and secondary (Browse, Preview, Cancel-style,
outlined/muted). Form inputs, selects, and fieldset cards share one
consistent bordered/rounded treatment instead of raw browser defaults.

### 4. Layout restructure

- **CTD / Nav / Position fieldsets**: CSS grid
  (`grid-template-columns: repeat(auto-fill, minmax(180px, 1fr))`)
  instead of one input per line — cuts vertical scroll roughly in half
  at this viewport width without touching field order or names.
- **Cast list**: card-per-cast instead of a bare `<table>` — name/
  station/lat/lon plus Edit/Clone/Remove as a row of icon buttons per
  card, replacing the cramped multi-button table cell.
- **Cast editor fieldsets**: each becomes a bordered card with a heading
  bar (still semantically a `<fieldset>`/`<legend>`, styled as a card)
  rather than a bare default-rendered fieldset.

### 5. Unsaved/saved-state indicator

A status chip next to "Save cast" — `Unsaved changes` / `Saved` /
`Saving…` — driven by comparing serialized current form values against
the last-saved snapshot on every `input`/`change` event. Pure frontend
state, no new API.

### 6. File-browser / preview panels as modals

`.file-browser` (currently an inline `hidden` `<div>` that un-hides in
place, pushing page content down) and the CTD/Nav preview panels become a
shared modal-overlay component (dimmed backdrop, close button, Esc-to-
close, focus trapped inside while open). One JS helper renders any of the
three (LADCP down/up browse, CTD/Nav browse, CTD/Nav preview) into the
same overlay shell rather than three near-duplicate inline-panel code
paths.

### 7. Claude Design → repo handoff

2–3 key screens (cast list, cast editor showing the new field-mapping
selects, the file-browser/preview modal) get built as static mockups
with placeholder data in the existing "RSV Nuyina Science Data Pipeline"
Claude Design project, for the user to review and pick a direction from.
The chosen direction is then hand-ported into the real
`webapp/templates/*.html` + `webapp/static/style.css` + `webapp/static/app.js`
and wired to the live FastAPI backend — the Claude Design mockup is a
visual reference only, never deployed or linked from the running app.

## Testing

- `delimited_parser.py`'s new `column_names` extraction gets unit tests
  in `test_delimited_parser.py`: a file with a matching-length header
  names line (BROKE-West-shaped fixture), a file with names+units lines
  (only the matching-length one wins), and the existing headerless case
  confirming `column_names is None` and all prior assertions still hold.
- The regex role auto-suggest gets unit tests against a small table of
  real column-name examples (`CTDPRS`, `CTDTMP`, `CTDSAL`, `CTDCOND`,
  a plain `time`/`lat`/`lon` nav header) — pure function, no DOM.
- UI/route wiring (modal behavior, save-state chip, grid layout,
  select-vs-manual-entry toggle) verified manually against the running
  app in a browser per this repo's existing convention (no Playwright/JS
  test runner in this repo) — screenshots taken before/after for the
  record.
