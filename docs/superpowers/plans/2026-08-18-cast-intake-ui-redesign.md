# Cast-Intake UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Task 1 is an exception — it requires live interaction with the human partner (presenting mockups, waiting for approval) and must run inline in the orchestrating session, not dispatched to a fresh subagent.**

**Goal:** Redesign `webapp/`'s cast-intake form — visual system, layout, column-name-aware CTD/Nav field mapping, unsaved-state indicator, modal file-browser/preview — per `docs/superpowers/specs/2026-08-18-cast-intake-ui-redesign-design.md`.

**Architecture:** FastAPI + Jinja2 + hand-written vanilla CSS/JS, no Node/build toolchain (unchanged). Backend gains two small pure-logic additions (`column_names` sniffing, `suggest_roles`) each independently pytest-covered. Frontend gets a CSS token layer (hand-ported from the Nuyina Design "Nocturne" theme) plus template/JS changes layered on top of it.

**Tech Stack:** Python 3.10+, FastAPI, Jinja2, pytest, vanilla JS/CSS, Google Fonts (`Inter`, `<link>` tag — no bundler).

## Global Constraints

- No Node/build toolchain — every frontend change is hand-written CSS/JS/Jinja2, no bundler, no framework (spec Non-goals).
- No change to `ldeo_ix/` or the Docker image (spec Non-goals).
- `template_gen.py` does not change — both the select-driven and manual-entry field-mapping paths write the same numeric value into the same named form field (spec §2).
- The existing `sniff_and_preview` header/data-split heuristic (first all-numeric line ends the header) is extended, not replaced (spec Non-goals).
- Pure-logic modules (`delimited_parser.py`, `field_role_suggest.py`) get pytest coverage; UI/route wiring is verified manually against the running app in a browser, per this repo's existing convention (`CLAUDE.md`) — there is no JS test runner in this repo.
- Run tests with: `cd /home/peter_sha/sourcecode/Nuyina/LDEO_IX_Octave && /tmp/ldeo_venv/bin/python -m pytest webapp/tests -v` (venv already has `fastapi==0.115.*`/`starlette` etc. installed per `webapp/requirements.txt`, minus `ctdam` which isn't needed for these tests). If `/tmp/ldeo_venv` doesn't exist in a fresh environment, recreate it: `python3.10 -m venv /tmp/ldeo_venv && /tmp/ldeo_venv/bin/pip install -q -r <(grep -v '^ctdam' webapp/requirements.txt)`.
- Run the live app for manual verification with:
  ```bash
  mkdir -p /tmp/ldeo_scratch/{data,ladcp,ctd,sadcp,nav}
  cd /home/peter_sha/sourcecode/Nuyina/LDEO_IX_Octave
  LDEO_DATA_DIR=/tmp/ldeo_scratch/data LDEO_LADCP_DIR=/tmp/ldeo_scratch/ladcp \
  LDEO_CTD_DIR=/tmp/ldeo_scratch/ctd LDEO_SADCP_DIR=/tmp/ldeo_scratch/sadcp \
  LDEO_NAV_DIR=/tmp/ldeo_scratch/nav \
  /tmp/ldeo_venv/bin/python -m uvicorn webapp.main:app --port 8124 --host 127.0.0.1
  ```

---

### Task 1: Claude Design mockups and visual-direction sign-off

**Files:**
- Create: `webapp/static/style.css` (token layer only — full rewrite of the current 16-line file)

**Interfaces:**
- Produces: the CSS custom-property tokens every later CSS task consumes by name: `--color-bg`, `--color-surface`, `--color-surface-2`, `--color-border`, `--color-text`, `--color-text-muted`, `--color-accent`, `--color-accent-hover`, `--color-danger`, `--color-warning`, `--font-body`, `--radius-sm`, `--radius-md`, `--radius-lg`, `--space-2` through `--space-8`. Also produces the base `.btn`/`.btn-secondary`/`.btn-danger` button classes later tasks apply to their own markup.

This task is exploratory/approval-gated, not a fixed-code step — run it inline, not dispatched.

- [ ] **Step 1: Build 2-3 mockup screens in the existing Claude Design project**

  Project ID `199bd28b-6ed0-42a5-acbf-6c8fe0afabde` ("RSV Nuyina Science Data Pipeline") already has the Nocturne design system attached (`_ds/nocturne-0e5f890e-9f2a-486f-8d4b-8b6a4fa424eb/`). Use `mcp__claude-design__write_files` to add 2-3 new `.dc.html` files (e.g. `LDEO Cast Intake - Cast List.dc.html`, `LDEO Cast Intake - Cast Editor.dc.html`) showing, with placeholder data:
  - The cast list as cards (name/station/lat/lon, Edit/Clone/Remove as a button row).
  - The cast editor's CTD fieldset, specifically the new field-mapping selects (`Time field`, `Pressure field`, etc.) populated with realistic `"3: CTDPRS"`-style options, plus the "Enter index manually" toggle in both states.
  - The Save-cast area showing the unsaved/saved-state chip.

  Reuse the real Nocturne token values already confirmed in `_ds/nocturne-.../styles.css`: `--color-bg: #161826` (page background use `#12131f`, matching the data-flow diagram's outer wrapper, with `#161826`/`#1b1d2e` as panel/surface tones), `--color-text: #e9e9ed`, `--color-accent: #9184d9`, neutral ramp `--color-neutral-100..900` (`#f3f5fe` .. `#292b31`), accent ramp `--color-accent-100..900`, `--font-body`/`--font-heading: "Inter"`, `--radius-sm/md/lg: 4px/8px/14px`.

- [ ] **Step 2: Present mockups to the user for review**

  Give the user the `open_url` from `mcp__claude-design__render_preview` for each mockup file (never the `serve_url` — that's for your own browser tooling only). Ask explicitly whether the direction is approved, and note any requested adjustments (color, spacing, wording).

- [ ] **Step 3: Iterate until approved**

  Apply any requested changes via `write_files` and re-present. Repeat until the user confirms.

- [ ] **Step 4: Write the finalized token layer to `webapp/static/style.css`**

  Replace the entire current file with the token layer + base rules, using the values confirmed in Step 2/3 (adjust the exact hex values below if the user asked for changes during review):

  ```css
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  :root {
    --color-bg: #12131f;
    --color-surface: #1b1d2e;
    --color-surface-2: #161826;
    --color-border: #3f424d;
    --color-text: #e9e9ed;
    --color-text-muted: #9397ab;
    --color-accent: #9184d9;
    --color-accent-hover: #b5abfc;
    --color-accent-text: #12131f;
    --color-danger: #f28b82;
    --color-warning: #f5c76d;

    --font-body: "Inter", system-ui, sans-serif;

    --radius-sm: 4px;
    --radius-md: 8px;
    --radius-lg: 14px;

    --space-2: 6px;
    --space-3: 10px;
    --space-4: 14px;
    --space-6: 20px;
    --space-8: 28px;
  }

  * { box-sizing: border-box; }

  body {
    background: var(--color-bg);
    color: var(--color-text);
    font-family: var(--font-body);
    margin: 0;
    padding: var(--space-8);
  }

  header h1 {
    font-weight: 600;
    margin: 0 0 var(--space-6) 0;
  }

  h2 { font-weight: 600; margin: var(--space-6) 0 var(--space-3) 0; }
  h3 { font-weight: 600; margin: 0 0 var(--space-3) 0; }

  a { color: var(--color-accent); }

  label {
    display: block;
    font-size: 0.85rem;
    color: var(--color-text-muted);
    margin-bottom: var(--space-2);
  }

  input, select, textarea {
    background: var(--color-surface-2);
    color: var(--color-text);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    padding: var(--space-2) var(--space-3);
    font-family: inherit;
    font-size: 0.95rem;
  }

  input:focus, select:focus, textarea:focus {
    outline: none;
    border-color: var(--color-accent);
  }

  .btn {
    font-family: inherit;
    font-size: 0.9rem;
    padding: var(--space-2) var(--space-4);
    border-radius: var(--radius-sm);
    border: 1px solid transparent;
    cursor: pointer;
  }

  .btn-primary {
    background: var(--color-accent);
    color: var(--color-accent-text);
    font-weight: 600;
  }
  .btn-primary:hover { background: var(--color-accent-hover); }

  .btn-secondary {
    background: transparent;
    color: var(--color-text);
    border-color: var(--color-border);
  }
  .btn-secondary:hover { border-color: var(--color-accent); }

  .btn-danger {
    background: transparent;
    color: var(--color-danger);
    border-color: var(--color-border);
  }
  .btn-danger:hover { border-color: var(--color-danger); }

  .error { color: var(--color-danger); }
  .warning { color: var(--color-warning); }
  ```

- [ ] **Step 5: Commit**

  ```bash
  cd /home/peter_sha/sourcecode/Nuyina/LDEO_IX_Octave
  git add webapp/static/style.css
  git commit -m "feat: add Nocturne-derived CSS token layer for cast-intake UI"
  ```

---

### Task 2: Backend — extract column names in `delimited_parser.py`

**Files:**
- Modify: `webapp/delimited_parser.py`
- Test: `webapp/tests/test_delimited_parser.py`

**Interfaces:**
- Produces: `DelimitedPreview.column_names: list[str] | None` — the real header-line tokens when a matching-length, non-comment header line exists, else `None`. Consumed by Task 4 (`main.py`'s `/api/preview` route).

- [ ] **Step 1: Write the failing tests**

  Add to `webapp/tests/test_delimited_parser.py`:

  ```python
  def test_extracts_column_names_from_last_matching_length_header_line(tmp_path):
      f = tmp_path / "cast.all"
      f.write_text(
          " START POSITION   : 67 00.08 S 039 59.81 E\n"
          "CTDPRS     CTDTMP    CTDCOND     CTDSAL    CTDOXY     FLUORO        PAR      TRANS   NPTS\n"
          "   DBAR     ITS-90      mS/cm     PSS-78    umol/l\n"
          "    2.0    -9.0000  -9.000000    -9.0000     -9.00     -9.000     -9.000     -9.000      0\n"
          "    4.0     0.1258  27.718977    33.1138    355.47      1.382      0.002     -0.001     22\n"
      )

      preview = delimited_parser.sniff_and_preview(f)

      assert preview.column_names == [
          "CTDPRS", "CTDTMP", "CTDCOND", "CTDSAL", "CTDOXY",
          "FLUORO", "PAR", "TRANS", "NPTS",
      ]


  def test_ignores_comment_marked_header_lines_for_column_names(tmp_path):
      f = tmp_path / "with_header.txt"
      f.write_text(
          "% CTD decimated series\n"
          "% generated 2015-04-11\n"
          "1.0 2.0 3.0\n"
          "4.0 5.0 6.0\n"
      )

      preview = delimited_parser.sniff_and_preview(f)

      assert preview.column_names is None
      # existing behavior must be unaffected
      assert preview.header_lines == 2
      assert preview.fields_per_line == 3


  def test_column_names_is_none_for_headerless_files(tmp_path):
      f = tmp_path / "003.2Hz"
      f.write_text(
          "1523980583.0 5.234 12.10 34.90 0 0 0 0 0 -15.498335 -150.196990\n"
          "1523980584.0 5.240 12.11 34.91 0 0 0 0 0 -15.498336 -150.196991\n"
      )

      preview = delimited_parser.sniff_and_preview(f)

      assert preview.column_names is None
  ```

- [ ] **Step 2: Run tests to verify they fail**

  Run: `/tmp/ldeo_venv/bin/python -m pytest webapp/tests/test_delimited_parser.py -v`
  Expected: the three new tests FAIL with `AttributeError: 'DelimitedPreview' object has no attribute 'column_names'`.

- [ ] **Step 3: Implement `column_names` extraction**

  Replace the full contents of `webapp/delimited_parser.py` with:

  ```python
  from dataclasses import dataclass
  from pathlib import Path


  @dataclass
  class DelimitedPreview:
      header_lines: int
      fields_per_line: int
      preview_rows: list
      column_names: list | None = None


  def sniff_and_preview(file_path: Path, max_rows: int = 10) -> DelimitedPreview:
      with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
          lines = [line.rstrip("\n") for line in fh if line.strip() != ""]

      header_lines = 0
      header_line_texts = []
      for line in lines:
          tokens = line.strip().split()
          if tokens and all(_is_number(tok) for tok in tokens):
              break
          header_lines += 1
          header_line_texts.append(line)

      data_lines = lines[header_lines:]
      fields_per_line = len(data_lines[0].split()) if data_lines else 0
      preview_rows = [line.split() for line in data_lines[:max_rows]]

      # The real column-name row, when one exists, is the header line whose
      # token count matches the data row width -- skipping comment-marked
      # lines (`%`/`#`), which can coincidentally match by token count (see
      # test_ignores_comment_marked_header_lines_for_column_names). Real
      # files can have an earlier metadata line that also coincidentally
      # matches (e.g. a lat/lon line with as many tokens as the data), so
      # this takes the LAST match, not the first -- confirmed against a
      # real BROKE-West .all file where an earlier "START POSITION" line
      # has the same token count as the true CTDPRS/CTDTMP/... header.
      column_names = None
      if fields_per_line:
          for header_line in header_line_texts:
              stripped = header_line.strip()
              if stripped.startswith("%") or stripped.startswith("#"):
                  continue
              tokens = stripped.split()
              if len(tokens) == fields_per_line:
                  column_names = tokens

      return DelimitedPreview(
          header_lines=header_lines,
          fields_per_line=fields_per_line,
          preview_rows=preview_rows,
          column_names=column_names,
      )


  def _is_number(token: str) -> bool:
      try:
          float(token)
          return True
      except ValueError:
          return False
  ```

- [ ] **Step 4: Run tests to verify they pass**

  Run: `/tmp/ldeo_venv/bin/python -m pytest webapp/tests/test_delimited_parser.py -v`
  Expected: all tests PASS (the 3 new ones plus the 4 pre-existing ones — confirms this is a pure addition).

- [ ] **Step 5: Commit**

  ```bash
  git add webapp/delimited_parser.py webapp/tests/test_delimited_parser.py
  git commit -m "feat: extract real column names from CTD/Nav file headers when present"
  ```

---

### Task 3: Backend — `field_role_suggest.py` role auto-suggest

**Files:**
- Create: `webapp/field_role_suggest.py`
- Test: `webapp/tests/test_field_role_suggest.py`

**Interfaces:**
- Consumes: nothing from other tasks (pure function of `list[str] | None`).
- Produces: `suggest_roles(column_names: list[str] | None) -> dict[str, int]` — maps role name (`"pressure"`, `"temperature"`, `"salinity"`, `"time"`, `"lat"`, `"lon"`) to a 1-based column index. Consumed by Task 4.

- [ ] **Step 1: Write the failing tests**

  Create `webapp/tests/test_field_role_suggest.py`:

  ```python
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
  ```

- [ ] **Step 2: Run tests to verify they fail**

  Run: `/tmp/ldeo_venv/bin/python -m pytest webapp/tests/test_field_role_suggest.py -v`
  Expected: FAIL with `ModuleNotFoundError: No module named 'webapp.field_role_suggest'`.

- [ ] **Step 3: Implement `field_role_suggest.py`**

  ```python
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
  ```

- [ ] **Step 4: Run tests to verify they pass**

  Run: `/tmp/ldeo_venv/bin/python -m pytest webapp/tests/test_field_role_suggest.py -v`
  Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add webapp/field_role_suggest.py webapp/tests/test_field_role_suggest.py
  git commit -m "feat: add regex-based CTD/Nav field-role auto-suggest"
  ```

---

### Task 4: Backend — wire `column_names`/`suggested_roles` into `/api/preview`

**Files:**
- Modify: `webapp/main.py:56-75` (the `preview_file` route)
- Test: `webapp/tests/test_main_browse_route.py`

**Interfaces:**
- Consumes: `delimited_parser.DelimitedPreview.column_names` (Task 2), `field_role_suggest.suggest_roles` (Task 3).
- Produces: `/api/preview/{mount}` response gains `"column_names": list[str] | None` and `"suggested_roles": dict[str, int]` keys. Consumed by Task 6 (frontend field-mapping selects).

- [ ] **Step 1: Write the failing test**

  Add to `webapp/tests/test_main_browse_route.py`:

  ```python
  def test_preview_endpoint_returns_column_names_and_suggested_roles(tmp_path, monkeypatch):
      (tmp_path / "cast1.all").write_text(
          "CTDPRS     CTDTMP    CTDSAL\n"
          "    2.0    -9.0000    -9.0000\n"
          "    4.0     0.1258    33.1138\n"
      )
      monkeypatch.setitem(config.MOUNTS, "ctd", tmp_path)

      client = TestClient(main.app)
      response = client.get("/api/preview/ctd", params={"path": "cast1.all"})

      assert response.status_code == 200
      body = response.json()
      assert body["column_names"] == ["CTDPRS", "CTDTMP", "CTDSAL"]
      assert body["suggested_roles"] == {"pressure": 1, "temperature": 2, "salinity": 3}


  def test_preview_endpoint_returns_null_column_names_for_headerless_file(tmp_path, monkeypatch):
      (tmp_path / "cast1.cnv").write_text("1.0 2.0 3.0\n4.0 5.0 6.0\n")
      monkeypatch.setitem(config.MOUNTS, "ctd", tmp_path)

      client = TestClient(main.app)
      response = client.get("/api/preview/ctd", params={"path": "cast1.cnv"})

      assert response.status_code == 200
      body = response.json()
      assert body["column_names"] is None
      assert body["suggested_roles"] == {}
  ```

- [ ] **Step 2: Run tests to verify they fail**

  Run: `/tmp/ldeo_venv/bin/python -m pytest webapp/tests/test_main_browse_route.py -v`
  Expected: the 2 new tests FAIL with a `KeyError`/`assert None == [...]`-style failure (the response has no `column_names`/`suggested_roles` keys yet).

- [ ] **Step 3: Wire the fields into the route**

  In `webapp/main.py:9`, the import line currently reads:

  ```python
  from webapp import api, config, delimited_parser, file_browser, ladcp_scan, paths, quick_convert
  ```

  Change it to:

  ```python
  from webapp import api, config, delimited_parser, field_role_suggest, file_browser, ladcp_scan, paths, quick_convert
  ```

  Then replace the `preview_file` route body (currently `webapp/main.py:56-75`):

  ```python
  @app.get("/api/preview/{mount}")
  def preview_file(mount: str, path: str):
      mount_root = config.MOUNTS.get(mount)
      if mount_root is None or not mount_root.is_dir():
          raise HTTPException(status_code=404, detail=f"mount {mount!r} not available")

      try:
          resolved = paths.resolve_within(mount_root, path)
      except paths.PathOutsideMountError:
          raise HTTPException(status_code=400, detail="path is outside the allowed directory")

      if not resolved.is_file():
          raise HTTPException(status_code=404, detail=f"{path!r} is not a file")

      preview = delimited_parser.sniff_and_preview(resolved)
      return {
          "header_lines": preview.header_lines,
          "fields_per_line": preview.fields_per_line,
          "preview_rows": preview.preview_rows,
          "column_names": preview.column_names,
          "suggested_roles": field_role_suggest.suggest_roles(preview.column_names),
      }
  ```

- [ ] **Step 4: Run tests to verify they pass**

  Run: `/tmp/ldeo_venv/bin/python -m pytest webapp/tests -v`
  Expected: all tests PASS (full suite, to confirm nothing else broke).

- [ ] **Step 5: Commit**

  ```bash
  git add webapp/main.py webapp/tests/test_main_browse_route.py
  git commit -m "feat: expose column_names/suggested_roles from the preview API"
  ```

---

### Task 5: Frontend — layout restructure (cards, grids, fieldset styling)

**Files:**
- Modify: `webapp/templates/base.html`
- Modify: `webapp/templates/index.html`
- Modify: `webapp/static/app.js:12-53` (cast list rendering), `:274`, `:278`, `:285`, `:289`, `:313`, `:336` (call sites)
- Modify: `webapp/static/style.css` (append to the token layer from Task 1)

**Interfaces:**
- Consumes: CSS tokens from Task 1 (`--color-*`, `--radius-*`, `--space-*`, `.btn`/`.btn-secondary`/`.btn-danger`).
- Produces: `refreshCastList()` (renamed from `refreshCastTable()`) — later tasks that need to refresh the cast list call this name. `.field-map` container class structure that Task 6 attaches selects/toggles into (see Task 6's own markup — this task only needs to leave the four fieldsets' existing `<label>`/`<input>` pairs in place, wrapped for grid layout).

- [ ] **Step 1: Update `base.html`'s header markup**

  Replace `webapp/templates/base.html` in full:

  ```html
  <!doctype html>
  <html lang="en">
  <head>
    <meta charset="utf-8">
    <title>{% block title %}LDEO_IX Cruise/Cast Intake{% endblock %}</title>
    <link rel="stylesheet" href="/static/style.css">
  </head>
  <body>
    <header>
      <div class="eyebrow">LDEO_IX Octave</div>
      <h1>Cruise/Cast Intake</h1>
    </header>
    <main>{% block content %}{% endblock %}</main>
    {% block scripts %}{% endblock %}
  </body>
  </html>
  ```

- [ ] **Step 2: Add layout CSS to `style.css`**

  Append to `webapp/static/style.css` (after Task 1's token layer):

  ```css
  .eyebrow {
    font-size: 0.75rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    margin-bottom: var(--space-2);
  }

  .card {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--space-6);
    margin-bottom: var(--space-6);
  }

  .card > legend, .card > h2, .card > h3 {
    padding: 0 var(--space-2);
  }

  .field-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: var(--space-4);
  }

  .field-grid label { margin-top: var(--space-3); }

  .cast-cards {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
  }

  .cast-card {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--space-3) var(--space-4);
  }

  .cast-card-summary { display: flex; flex-direction: column; gap: var(--space-2); }
  .cast-card-name { font-weight: 600; }
  .cast-card-meta { color: var(--color-text-muted); font-size: 0.85rem; }
  .cast-card-actions { display: flex; gap: var(--space-2); }
  ```

- [ ] **Step 3: Rewrite `index.html`'s structure**

  Replace `webapp/templates/index.html` in full:

  ```html
  {% extends "base.html" %}
  {% block content %}
  <section id="cruise-header" class="card">
    <label for="cruise-id">Cruise ID</label>
    <input id="cruise-id" type="text">
  </section>

  <section id="cast-list">
    <h2>Casts</h2>
    <div id="cast-cards" class="cast-cards"></div>
    <button type="button" id="add-cast" class="btn btn-secondary">Add cast</button>
  </section>

  <section id="cast-editor" hidden>
    <h2>Edit cast</h2>
    <form id="cast-form">
      <fieldset class="card">
        <legend>Raw LADCP files</legend>
        <select id="ladcp-suggestions"></select>
        <button type="button" id="apply-ladcp-suggestion" class="btn btn-secondary">Use selected pair</button>
        <div class="field-grid">
          <label>Name <input name="cast_name"></label>
          <label>Station <input name="ladcp_station" type="number"></label>
          <label>Cast <input name="ladcp_cast" type="number"></label>
        </div>
        <label>Down file
          <input name="ladcpdo" id="ladcpdo-path">
          <button type="button" id="browse-ladcpdo" class="btn btn-secondary">Browse</button>
        </label>
        <div class="file-browser" id="ladcpdo-browser" hidden></div>
        <label>Up file
          <input name="ladcpup" id="ladcpup-path">
          <button type="button" id="browse-ladcpup" class="btn btn-secondary">Browse</button>
        </label>
        <div class="file-browser" id="ladcpup-browser" hidden></div>
      </fieldset>

      <fieldset class="card">
        <legend>CTD</legend>
        <label>File
          <input name="ctd" id="ctd-path">
          <button type="button" id="browse-ctd" class="btn btn-secondary">Browse</button>
        </label>
        <div class="file-browser" id="ctd-browser" hidden></div>
        <div id="ctd-quickconvert-warning" class="warning" hidden>
          ⚠ This CTD file was generated by Quick-convert — unvalidated,
          not Sea-Bird-equivalent, not for publication-grade science. See
          the README for details.
        </div>

        <details>
          <summary>Quick-convert raw hex (unvalidated, emergency use only)</summary>
          <label>Raw .hex file
            <input name="quickconvert_hex" id="quickconvert-hex-path">
            <button type="button" id="browse-quickconvert-hex" class="btn btn-secondary">Browse</button>
          </label>
          <div class="file-browser" id="quickconvert-hex-browser" hidden></div>
          <label>.XMLCON file
            <input name="quickconvert_xmlcon" id="quickconvert-xmlcon-path">
            <button type="button" id="browse-quickconvert-xmlcon" class="btn btn-secondary">Browse</button>
          </label>
          <div class="file-browser" id="quickconvert-xmlcon-browser" hidden></div>
          <button type="button" id="run-quickconvert" class="btn btn-secondary">Quick-convert (unvalidated, emergency use only)</button>
          <div id="quickconvert-result"></div>
        </details>
        <button type="button" id="preview-ctd" class="btn btn-secondary">Preview / map columns</button>
        <div id="ctd-preview"></div>
        <div class="field-grid">
          <label>Header lines <input name="ctd_header_lines" type="number"></label>
          <label>Fields per line <input name="ctd_fields_per_line" type="number"></label>
          <div class="field-map" data-role-field="ctd_time_field">
            <label for="ctd_time_field">Time field</label>
            <div class="field-map-control">
              <select class="field-map-select" hidden></select>
              <input name="ctd_time_field" id="ctd_time_field" type="number" class="field-map-manual">
              <button type="button" class="field-map-toggle btn btn-secondary">Choose from detected columns</button>
            </div>
          </div>
          <div class="field-map" data-role-field="ctd_pressure_field">
            <label for="ctd_pressure_field">Pressure field</label>
            <div class="field-map-control">
              <select class="field-map-select" hidden></select>
              <input name="ctd_pressure_field" id="ctd_pressure_field" type="number" class="field-map-manual">
              <button type="button" class="field-map-toggle btn btn-secondary">Choose from detected columns</button>
            </div>
          </div>
          <div class="field-map" data-role-field="ctd_temperature_field">
            <label for="ctd_temperature_field">Temperature field</label>
            <div class="field-map-control">
              <select class="field-map-select" hidden></select>
              <input name="ctd_temperature_field" id="ctd_temperature_field" type="number" class="field-map-manual">
              <button type="button" class="field-map-toggle btn btn-secondary">Choose from detected columns</button>
            </div>
          </div>
          <div class="field-map" data-role-field="ctd_salinity_field">
            <label for="ctd_salinity_field">Salinity field</label>
            <div class="field-map-control">
              <select class="field-map-select" hidden></select>
              <input name="ctd_salinity_field" id="ctd_salinity_field" type="number" class="field-map-manual">
              <button type="button" class="field-map-toggle btn btn-secondary">Choose from detected columns</button>
            </div>
          </div>
          <label>Bad value <input name="ctd_badvals" type="number"></label>
        </div>
      </fieldset>

      <fieldset class="card">
        <legend>Nav</legend>
        <label>File
          <input name="nav" id="nav-path">
          <button type="button" id="browse-nav" class="btn btn-secondary">Browse</button>
        </label>
        <div class="file-browser" id="nav-browser" hidden></div>
        <button type="button" id="preview-nav" class="btn btn-secondary">Preview / map columns</button>
        <div id="nav-preview"></div>
        <div class="field-grid">
          <label>Header lines <input name="nav_header_lines" type="number"></label>
          <label>Fields per line <input name="nav_fields_per_line" type="number"></label>
          <div class="field-map" data-role-field="nav_time_field">
            <label for="nav_time_field">Time field</label>
            <div class="field-map-control">
              <select class="field-map-select" hidden></select>
              <input name="nav_time_field" id="nav_time_field" type="number" class="field-map-manual">
              <button type="button" class="field-map-toggle btn btn-secondary">Choose from detected columns</button>
            </div>
          </div>
          <div class="field-map" data-role-field="nav_lat_field">
            <label for="nav_lat_field">Lat field</label>
            <div class="field-map-control">
              <select class="field-map-select" hidden></select>
              <input name="nav_lat_field" id="nav_lat_field" type="number" class="field-map-manual">
              <button type="button" class="field-map-toggle btn btn-secondary">Choose from detected columns</button>
            </div>
          </div>
          <div class="field-map" data-role-field="nav_lon_field">
            <label for="nav_lon_field">Lon field</label>
            <div class="field-map-control">
              <select class="field-map-select" hidden></select>
              <input name="nav_lon_field" id="nav_lon_field" type="number" class="field-map-manual">
              <button type="button" class="field-map-toggle btn btn-secondary">Choose from detected columns</button>
            </div>
          </div>
        </div>
      </fieldset>

      <fieldset class="card">
        <legend>Position / time / bottom-tracking</legend>
        <div class="field-grid">
          <label>Lat <input name="lat" type="number" step="any"></label>
          <label>Lon <input name="lon" type="number" step="any"></label>
          <label>Magnetic deviation (drot) <input name="drot" type="number" step="any"></label>
          <label>Time start (Y M D h m s) <input name="time_start_raw" placeholder="2015 4 11 17 36 23.0"></label>
          <label>Time end (Y M D h m s) <input name="time_end_raw" placeholder="2015 4 11 21 9 42.0"></label>
          <label>Bottom-track mode <input name="btrk_mode" type="number"></label>
          <label>Bottom-track used <input name="btrk_used" type="number"></label>
        </div>
      </fieldset>

      <div id="save-row">
        <button type="submit" class="btn btn-primary">Save cast</button>
        <span id="save-state" class="save-state"></span>
      </div>
    </form>
  </section>

  <section id="generate-section">
    <button type="button" id="generate" class="btn btn-primary">Generate set_cast_params.m</button>
    <pre id="generate-result"></pre>
  </section>
  {% endblock %}
  {% block scripts %}<script src="/static/app.js"></script>{% endblock %}
  ```

  Note: the `<select id="ladcp-suggestions">` and file-mapping `.field-map-select` elements deliberately keep no `name` attribute — they're presentation-only controls that write into the real named inputs (`ladcp_station` etc., `ctd_time_field` etc.), same pattern the code already used before this change (`apply-ladcp-suggestion`'s click handler, unchanged by this task).

- [ ] **Step 4: Rename `refreshCastTable` to `refreshCastList` and switch to card rendering**

  In `webapp/static/app.js`, replace lines 12-53 (the full `refreshCastTable` function body) with:

  ```javascript
  async function refreshCastList() {
    const session = await api("/api/session");
    document.getElementById("cruise-id").value = session.cruise_id || "";
    const container = document.getElementById("cast-cards");
    container.innerHTML = "";
    for (const cast of session.casts) {
      const card = document.createElement("div");
      card.className = "cast-card";

      const summary = document.createElement("div");
      summary.className = "cast-card-summary";
      const name = document.createElement("span");
      name.className = "cast-card-name";
      name.textContent = cast.cast_name || "(unnamed cast)";
      const meta = document.createElement("span");
      meta.className = "cast-card-meta";
      const station = cast.ladcp_station ?? "?";
      const lat = cast.lat ?? "?";
      const lon = cast.lon ?? "?";
      meta.textContent = `Station ${station} · ${lat}, ${lon}`;
      summary.appendChild(name);
      summary.appendChild(meta);

      const actions = document.createElement("div");
      actions.className = "cast-card-actions";
      const editButton = document.createElement("button");
      editButton.type = "button";
      editButton.className = "btn btn-secondary";
      editButton.textContent = "Edit";
      editButton.dataset.edit = cast.id;
      const cloneButton = document.createElement("button");
      cloneButton.type = "button";
      cloneButton.className = "btn btn-secondary";
      cloneButton.textContent = "Clone";
      cloneButton.dataset.clone = cast.id;
      const removeButton = document.createElement("button");
      removeButton.type = "button";
      removeButton.className = "btn btn-danger";
      removeButton.textContent = "Remove";
      removeButton.dataset.remove = cast.id;
      actions.appendChild(editButton);
      actions.appendChild(cloneButton);
      actions.appendChild(removeButton);

      card.appendChild(summary);
      card.appendChild(actions);
      container.appendChild(card);
    }
  }
  ```

- [ ] **Step 5: Update the remaining `refreshCastTable`/`#cast-table` references**

  In `webapp/static/app.js`:
  - Line 274 (inside the `#add-cast` click handler): change `await refreshCastTable();` to `await refreshCastList();`.
  - Line 278: change `document.querySelector("#cast-table tbody").parentElement.addEventListener(...)` to `document.getElementById("cast-cards").addEventListener(...)` (same handler body — `event.target.dataset.edit/clone/remove` still works unchanged, since the buttons still carry those `dataset` attributes).
  - Lines 285 and 289 (inside that same handler, clone/remove branches): change both `await refreshCastTable();` to `await refreshCastList();`.
  - Line 313 (end of the form submit handler): change `await refreshCastTable();` to `await refreshCastList();`.
  - Line 336 (final unconditional call at end of file): change `refreshCastTable();` to `refreshCastList();`.

- [ ] **Step 6: Manual verification**

  Start the app (Global Constraints command) and in a browser:
  - Confirm the page loads with the dark theme, no console errors.
  - Click "Add cast" — confirm a card appears in the cast list after saving.
  - Confirm Edit/Clone/Remove buttons on a card work as before.
  - Confirm the CTD/Nav/Position fieldsets render as a multi-column grid, not one input per line.

  Take a screenshot for the record (Playwright, full-page, as done for the baseline).

- [ ] **Step 7: Commit**

  ```bash
  git add webapp/templates/base.html webapp/templates/index.html webapp/static/app.js webapp/static/style.css
  git commit -m "feat: restructure cast-intake layout into cards and grids"
  ```

---

### Task 6: Frontend — column-name-aware CTD/Nav field mapping

**Files:**
- Modify: `webapp/static/app.js` (the `renderPreview` function and its two call sites)
- Modify: `webapp/static/style.css` (append `.field-map` styles)

**Interfaces:**
- Consumes: `/api/preview/{mount}` response's `column_names`/`suggested_roles` (Task 4); the `.field-map[data-role-field="..."]` markup from Task 5.
- Produces: `populateFieldMapSelect(inputName, columnNames, suggestedIndex)` and `setFieldMapMode(inputName, mode)` — no other task needs to call these, but they must exist under these exact names since this task's own `renderPreview` and the toggle-button click handler both call them.

- [ ] **Step 1: Add field-map CSS**

  Append to `webapp/static/style.css`:

  ```css
  .field-map-control {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .field-map-control select,
  .field-map-control input {
    width: 100%;
  }

  .field-map-toggle {
    align-self: flex-start;
    font-size: 0.8rem;
    padding: var(--space-2) var(--space-3);
  }

  .field-map-toggle:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  ```

- [ ] **Step 2: Replace `renderPreview` and add the field-map helpers**

  In `webapp/static/app.js`, find the current `renderPreview` function (the one that builds a `<table>` with a per-column role-`<select>` in each `<th>`) and replace it, along with adding the new helper functions right after it:

  ```javascript
  async function renderPreview(mount, pathInputId, targetDivId, roleFields, fieldPrefix) {
    const path = document.getElementById(pathInputId).value;
    if (!path) return;
    const preview = await api(`/api/preview/${mount}?path=${encodeURIComponent(path)}`);
    const div = document.getElementById(targetDivId);
    const form = document.getElementById("cast-form");
    form.elements.namedItem(`${fieldPrefix}_header_lines`).value = preview.header_lines;
    form.elements.namedItem(`${fieldPrefix}_fields_per_line`).value = preview.fields_per_line;

    const table = document.createElement("table");
    const headerRow = document.createElement("tr");
    const columnNames = preview.column_names;
    for (let col = 0; col < preview.fields_per_line; col++) {
      const th = document.createElement("th");
      th.textContent = columnNames ? columnNames[col] : `col ${col + 1}`;
      headerRow.appendChild(th);
    }
    table.appendChild(headerRow);

    for (const row of preview.preview_rows) {
      const tr = document.createElement("tr");
      for (const v of row) {
        const td = document.createElement("td");
        td.textContent = v;
        tr.appendChild(td);
      }
      table.appendChild(tr);
    }

    div.innerHTML = "";
    div.appendChild(table);

    for (const role of roleFields) {
      const inputName = `${fieldPrefix}_${role}_field`;
      if (columnNames) {
        const suggestedIndex = preview.suggested_roles[role] ?? null;
        populateFieldMapSelect(inputName, columnNames, suggestedIndex);
      } else {
        setFieldMapMode(inputName, "manual");
      }
    }
  }

  function fieldMapContainer(inputName) {
    return document.querySelector(`.field-map[data-role-field="${inputName}"]`);
  }

  function setFieldMapMode(inputName, mode) {
    const container = fieldMapContainer(inputName);
    if (!container) return;
    const select = container.querySelector(".field-map-select");
    const manual = container.querySelector(".field-map-manual");
    const toggle = container.querySelector(".field-map-toggle");
    if (mode === "select" && select.options.length > 1) {
      select.hidden = false;
      manual.hidden = true;
      toggle.textContent = "Enter index manually";
      toggle.disabled = false;
      container.dataset.mode = "select";
    } else {
      select.hidden = true;
      manual.hidden = false;
      toggle.textContent = "Choose from detected columns";
      toggle.disabled = select.options.length <= 1;
      container.dataset.mode = "manual";
    }
  }

  function populateFieldMapSelect(inputName, columnNames, suggestedIndex) {
    const container = fieldMapContainer(inputName);
    if (!container) return;
    const select = container.querySelector(".field-map-select");
    const manual = container.querySelector(".field-map-manual");

    select.innerHTML = "";
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = "-";
    select.appendChild(blank);
    columnNames.forEach((name, idx) => {
      const col = idx + 1;
      const option = document.createElement("option");
      option.value = String(col);
      option.textContent = `${col}: ${name}`;
      select.appendChild(option);
    });

    select.onchange = () => {
      manual.value = select.value;
    };

    if (manual.value) {
      // An explicit value already exists (typed manually, or loaded from
      // a saved cast) -- reflect it in the select rather than silently
      // overriding it with the auto-suggestion.
      select.value = manual.value;
    } else if (suggestedIndex != null) {
      select.value = String(suggestedIndex);
      manual.value = String(suggestedIndex);
    }

    setFieldMapMode(inputName, "select");
  }

  document.querySelectorAll(".field-map-toggle").forEach((toggle) => {
    toggle.addEventListener("click", () => {
      const container = toggle.closest(".field-map");
      const inputName = container.dataset.roleField;
      const nextMode = container.dataset.mode === "select" ? "manual" : "select";
      setFieldMapMode(inputName, nextMode);
    });
  });
  ```

  This replaces the entire previous `renderPreview` function; do not keep the old per-column `<select>`-in-`<th>` logic (`select.dataset.col`, the `div.querySelectorAll("select[data-col]")` block) — it's the redundant mechanism the design spec calls out for removal.

- [ ] **Step 3: Coerce select values to numbers in the submit handler**

  In `webapp/static/app.js`'s form submit handler (around the existing `document.getElementById("cast-form").addEventListener("submit", ...)`), find this line:

  ```javascript
      payload[element.name] = element.type === "number" ? Number(element.value) : element.value;
  ```

  Replace it with:

  ```javascript
      const isNumericSelect = element.tagName === "SELECT" && element.value !== "" && !Number.isNaN(Number(element.value));
      payload[element.name] = (element.type === "number" || isNumericSelect) ? Number(element.value) : element.value;
  ```

  This isn't strictly required for correctness (FastAPI/Pydantic already coerces numeric strings to `int` for `Optional[int]` fields), but keeps the client payload's types honest rather than relying on implicit server-side coercion, and doesn't affect any other named `<select>` in this form (there are none — `ladcp-suggestions` has no `name` attribute).

- [ ] **Step 4: Manual verification**

  With the app running (Global Constraints command):
  - Create a test file with a real header at `/tmp/ldeo_scratch/ctd/test.all` containing the BROKE-West-style header (`CTDPRS CTDTMP CTDCOND CTDSAL CTDOXY` + a couple of numeric rows).
  - In the browser: Add a cast, set the CTD file path to `test.all`, click "Preview / map columns". Confirm: the preview table shows real column names as headers; the Time/Pressure/Temperature/Salinity field-map controls show selects populated with `"N: NAME"` options; Pressure and Temperature and Salinity are pre-selected per the auto-suggest; Time (no match in this header) is left blank.
  - Click "Enter index manually" on one field — confirm it swaps to a number input showing the same value, editable.
  - Create a second test file with no header (plain numeric rows) at `/tmp/ldeo_scratch/ctd/headerless.dat`, preview it, confirm the field-map controls fall back to manual number inputs with no select shown.
  - Save the cast, confirm no errors, re-open it (Edit), confirm the previously-set field values are preserved (as plain numbers, since column_names isn't persisted).

- [ ] **Step 5: Commit**

  ```bash
  git add webapp/static/app.js webapp/static/style.css
  git commit -m "feat: replace blind CTD/Nav field-index entry with column-name-aware selects"
  ```

---

### Task 7: Frontend — unsaved/saved-state indicator

**Files:**
- Modify: `webapp/static/app.js`
- Modify: `webapp/static/style.css`

**Interfaces:**
- Consumes: `#cast-form` (already exists), `#save-state` span (added in Task 5's `index.html` rewrite).
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Add save-state CSS**

  Append to `webapp/static/style.css`:

  ```css
  #save-row {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-top: var(--space-4);
  }

  .save-state {
    font-size: 0.85rem;
    color: var(--color-text-muted);
  }
  .save-state.unsaved { color: var(--color-warning); }
  .save-state.saved { color: var(--color-accent); }
  ```

- [ ] **Step 2: Track saved-state in `openEditor` and the submit handler**

  In `webapp/static/app.js`, add a `lastSavedSnapshot` field to the existing `state` object (line 1):

  ```javascript
  const state = { editingCastId: null, lastSavedSnapshot: null };
  ```

  Add these two helper functions (place them near `openEditor`):

  ```javascript
  function serializeCastForm() {
    const form = document.getElementById("cast-form");
    const values = {};
    for (const element of form.elements) {
      if (!element.name) continue;
      values[element.name] = element.value;
    }
    return JSON.stringify(values);
  }

  function setSaveState(text, className) {
    const el = document.getElementById("save-state");
    el.textContent = text;
    el.className = `save-state ${className}`;
  }

  function updateSaveStateFromForm() {
    if (state.lastSavedSnapshot === null) return;
    const current = serializeCastForm();
    if (current === state.lastSavedSnapshot) {
      setSaveState("Saved", "saved");
    } else {
      setSaveState("Unsaved changes", "unsaved");
    }
  }
  ```

  At the end of `openEditor` (after `await loadLadcpSuggestions();`), add:

  ```javascript
    state.lastSavedSnapshot = serializeCastForm();
    setSaveState("Saved", "saved");
  ```

  In the `#cast-form` submit handler, after the successful `await api(...)` call and before `document.getElementById("cast-editor").hidden = true;`, add:

  ```javascript
    state.lastSavedSnapshot = serializeCastForm();
    setSaveState("Saved", "saved");
  ```

  Add a form-wide input listener near the other top-level `document.getElementById(...).addEventListener(...)` calls:

  ```javascript
  document.getElementById("cast-form").addEventListener("input", updateSaveStateFromForm);
  ```

- [ ] **Step 3: Manual verification**

  With the app running: Add a cast, confirm "Saved" shows once the editor opens. Type into any field — confirm the chip switches to "Unsaved changes". Click "Save cast" — confirm it switches back to "Saved".

- [ ] **Step 4: Commit**

  ```bash
  git add webapp/static/app.js webapp/static/style.css
  git commit -m "feat: add unsaved/saved-state indicator to the cast editor"
  ```

---

### Task 8: Frontend — file-browser/preview panels as modals

**Files:**
- Modify: `webapp/templates/index.html` (add a shared modal shell)
- Modify: `webapp/static/app.js` (`renderBrowserPanel`, `initBrowser`, and the `preview-ctd`/`preview-nav` click handlers)
- Modify: `webapp/static/style.css`

**Interfaces:**
- Consumes: nothing new from earlier tasks beyond the CSS tokens.
- Produces: `openModal(titleText, contentBuilderFn)` / `closeModal()` — a single shared overlay other future panels could reuse, though nothing later in this plan needs to call them beyond this task's own rewiring.

- [ ] **Step 1: Add the shared modal shell to `index.html`**

  In `webapp/templates/index.html`, add this markup just before `{% endblock %}` (i.e. as the last thing inside the `content` block, after the `#generate-section`):

  ```html
  <div id="modal-overlay" class="modal-overlay" hidden>
    <div class="modal" role="dialog" aria-modal="true">
      <div class="modal-header">
        <span id="modal-title"></span>
        <button type="button" id="modal-close" class="btn btn-secondary">Close</button>
      </div>
      <div id="modal-body" class="modal-body"></div>
    </div>
  </div>
  ```

  Remove the now-redundant inline `<div class="file-browser" id="..." hidden></div>` elements added in Task 5 for `ladcpdo-browser`, `ladcpup-browser`, `ctd-browser`, `nav-browser`, `quickconvert-hex-browser`, `quickconvert-xmlcon-browser` — these panels move into the shared modal in this task, so the six placeholder `<div class="file-browser" ...>` elements are deleted from the template. Also remove the inline `<div id="ctd-preview"></div>` and `<div id="nav-preview"></div>` — the preview table moves into the modal too.

- [ ] **Step 2: Add modal CSS**

  Append to `webapp/static/style.css`:

  ```css
  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
  }

  .modal {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    width: min(720px, 90vw);
    max-height: 80vh;
    display: flex;
    flex-direction: column;
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-4) var(--space-6);
    border-bottom: 1px solid var(--color-border);
    font-weight: 600;
  }

  .modal-body {
    padding: var(--space-6);
    overflow-y: auto;
  }

  .browser-path { font-family: monospace; font-size: 0.85rem; margin-bottom: var(--space-2); color: var(--color-text-muted); }
  .browser-entry { cursor: pointer; padding: var(--space-2) var(--space-3); border-radius: var(--radius-sm); }
  .browser-entry:hover { background: var(--color-surface-2); }
  .browser-entry.is-dir { font-weight: 600; }
  .browser-error { color: var(--color-danger); }
  ```

- [ ] **Step 3: Add the shared `openModal`/`closeModal` helpers**

  In `webapp/static/app.js`, add near the top (after the `api` function):

  ```javascript
  function openModal(titleText, buildContent) {
    document.getElementById("modal-title").textContent = titleText;
    const body = document.getElementById("modal-body");
    body.innerHTML = "";
    buildContent(body);
    document.getElementById("modal-overlay").hidden = false;
  }

  function closeModal() {
    document.getElementById("modal-overlay").hidden = true;
    document.getElementById("modal-body").innerHTML = "";
  }

  document.getElementById("modal-close").addEventListener("click", closeModal);
  document.getElementById("modal-overlay").addEventListener("click", (event) => {
    if (event.target.id === "modal-overlay") closeModal();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !document.getElementById("modal-overlay").hidden) closeModal();
  });
  ```

- [ ] **Step 4: Rewrite `renderBrowserPanel`/`initBrowser` to render into the modal**

  Replace the existing `renderBrowserPanel` and `initBrowser` functions in `webapp/static/app.js` with:

  ```javascript
  async function renderBrowserPanel(container, mount, targetInputId, relativePath) {
    container.dataset.currentPath = relativePath;
    container.innerHTML = "";

    const pathLine = document.createElement("div");
    pathLine.className = "browser-path";
    pathLine.textContent = `${mount}:/${relativePath}`;
    container.appendChild(pathLine);

    let data;
    try {
      data = await api(`/api/browse/${mount}?path=${encodeURIComponent(relativePath)}`);
    } catch (e) {
      const err = document.createElement("div");
      err.className = "browser-error";
      err.textContent = (e.body && e.body.detail) || `could not browse ${mount}`;
      container.appendChild(err);
      return;
    }

    if (relativePath) {
      const up = document.createElement("div");
      up.className = "browser-entry is-dir";
      up.textContent = ".. (up)";
      up.addEventListener("click", () => {
        const parent = relativePath.split("/").slice(0, -1).join("/");
        renderBrowserPanel(container, mount, targetInputId, parent);
      });
      container.appendChild(up);
    }

    for (const entry of data.entries) {
      const row = document.createElement("div");
      row.className = entry.is_dir ? "browser-entry is-dir" : "browser-entry";
      row.textContent = entry.is_dir ? `${entry.name}/` : entry.name;
      row.addEventListener("click", () => {
        if (entry.is_dir) {
          renderBrowserPanel(container, mount, targetInputId, entry.relative_path);
        } else {
          document.getElementById(targetInputId).value = entry.relative_path;
          if (targetInputId === "ctd-path") updateQuickConvertWarning();
          closeModal();
        }
      });
      container.appendChild(row);
    }
  }

  function initBrowser(buttonId, mount, targetInputId) {
    document.getElementById(buttonId).addEventListener("click", () => {
      openModal(`Browse ${mount}`, (body) => {
        renderBrowserPanel(body, mount, targetInputId, "");
      });
    });
  }
  ```

  Update the six `initBrowser(...)` call sites (previously 4-argument calls) to drop the now-removed panel-id argument:

  ```javascript
  initBrowser("browse-ctd", "ctd", "ctd-path");
  initBrowser("browse-nav", "nav", "nav-path");
  initBrowser("browse-ladcpdo", "ladcp", "ladcpdo-path");
  initBrowser("browse-ladcpup", "ladcp", "ladcpup-path");
  initBrowser("browse-quickconvert-hex", "ctd", "quickconvert-hex-path");
  initBrowser("browse-quickconvert-xmlcon", "ctd", "quickconvert-xmlcon-path");
  ```

- [ ] **Step 5: Move the CTD/Nav preview table into the modal**

  In `renderPreview` (added in Task 6), change the signature and how `div`/`targetDivId` is used — replace the `targetDivId` parameter with opening a modal instead:

  ```javascript
  async function renderPreview(mount, pathInputId, modalTitle, roleFields, fieldPrefix) {
    const path = document.getElementById(pathInputId).value;
    if (!path) return;
    const preview = await api(`/api/preview/${mount}?path=${encodeURIComponent(path)}`);
    const form = document.getElementById("cast-form");
    form.elements.namedItem(`${fieldPrefix}_header_lines`).value = preview.header_lines;
    form.elements.namedItem(`${fieldPrefix}_fields_per_line`).value = preview.fields_per_line;

    openModal(modalTitle, (body) => {
      const table = document.createElement("table");
      const headerRow = document.createElement("tr");
      const columnNames = preview.column_names;
      for (let col = 0; col < preview.fields_per_line; col++) {
        const th = document.createElement("th");
        th.textContent = columnNames ? columnNames[col] : `col ${col + 1}`;
        headerRow.appendChild(th);
      }
      table.appendChild(headerRow);
      for (const row of preview.preview_rows) {
        const tr = document.createElement("tr");
        for (const v of row) {
          const td = document.createElement("td");
          td.textContent = v;
          tr.appendChild(td);
        }
        table.appendChild(tr);
      }
      body.appendChild(table);
    });

    for (const role of roleFields) {
      const inputName = `${fieldPrefix}_${role}_field`;
      if (preview.column_names) {
        const suggestedIndex = preview.suggested_roles[role] ?? null;
        populateFieldMapSelect(inputName, preview.column_names, suggestedIndex);
      } else {
        setFieldMapMode(inputName, "manual");
      }
    }
  }
  ```

  Update the two call sites:

  ```javascript
  document.getElementById("preview-ctd").addEventListener("click", () => {
    const ctdPath = document.getElementById("ctd-path").value;
    const mount = ctdPath.endsWith(QUICKCONVERT_SUFFIX) ? "data" : "ctd";
    renderPreview(mount, "ctd-path", "CTD column preview", ["time", "pressure", "temperature", "salinity"], "ctd");
  });
  document.getElementById("preview-nav").addEventListener("click", () => {
    renderPreview("nav", "nav-path", "Nav column preview", ["time", "lat", "lon"], "nav");
  });
  ```

- [ ] **Step 6: Manual verification**

  With the app running: open each Browse button (LADCP down/up, CTD, Nav, Quick-convert hex/XMLCON) — confirm each opens the modal with a dimmed backdrop, lists directory entries, and clicking a file both fills the input and closes the modal. Confirm clicking the backdrop and pressing Escape both close the modal. Run "Preview / map columns" for CTD and Nav — confirm the preview table now renders inside the modal (not inline), and the field-map selects populate exactly as in Task 6's verification.

- [ ] **Step 7: Commit**

  ```bash
  git add webapp/templates/index.html webapp/static/app.js webapp/static/style.css
  git commit -m "feat: present file-browser and CTD/Nav preview as a shared modal"
  ```

---

### Task 9: Full regression pass, screenshots, and README note

**Files:**
- Modify: `README.md` (only if the Usage section's UI description is now stale)

**Interfaces:**
- Consumes: the fully assembled app from Tasks 1-8.
- Produces: nothing — this is the final verification/documentation task.

- [ ] **Step 1: Run the full backend test suite**

  Run: `/tmp/ldeo_venv/bin/python -m pytest webapp/tests -v`
  Expected: all tests PASS (this repo has no JS test runner — frontend correctness for this task is the manual pass below).

- [ ] **Step 2: Full manual click-through**

  With the app running (Global Constraints command), in a browser. If `/tmp/ldeo_scratch/ctd/test.all` and `/tmp/ldeo_scratch/ctd/headerless.dat` don't already exist (e.g. a fresh environment, or Task 6's scratch files weren't preserved), recreate them first:

  ```bash
  cat > /tmp/ldeo_scratch/ctd/test.all <<'EOF'
  CTDPRS     CTDTMP    CTDCOND     CTDSAL    CTDOXY
     2.0    -9.0000  -9.000000    -9.0000     -9.00
     4.0     0.1258  27.718977    33.1138    355.47
  EOF
  cat > /tmp/ldeo_scratch/ctd/headerless.dat <<'EOF'
  1523980583.0 5.234 12.10 34.90 0 0 0 0 0 -15.498335 -150.196990
  1523980584.0 5.240 12.11 34.91 0 0 0 0 0 -15.498336 -150.196991
  EOF
  ```

  - Load the index page, confirm dark theme, no console errors, cast cards render.
  - Add a cast, fill in CTD/Nav files with real headers (`test.all`/`headerless.dat`), confirm field-mapping selects and manual fallback both work.
  - Confirm the unsaved/saved-state chip updates correctly through an edit → save cycle.
  - Open every Browse modal and the CTD/Nav preview modal; confirm Esc and backdrop-click close each.
  - Save the cast, click "Generate set_cast_params.m", confirm the generated output still appears (unchanged backend behavior).
  - Clone and Remove a cast from its card, confirm the list updates.

  Take full-page screenshots of the cast list and an open cast editor (Playwright), for comparison against the Task-0 baseline screenshots taken during design.

- [ ] **Step 3: Update README if needed**

  Read `README.md`'s Usage section. If it describes the old plain-table cast list or the old inline file-browser/preview panels, update the relevant paragraph(s) to match the new card-list + modal behavior. If it's already generic enough (doesn't describe specific UI mechanics), no change is needed — don't add UI description that wasn't there before.

- [ ] **Step 4: Commit (only if README changed)**

  ```bash
  git add README.md
  git commit -m "docs: update README for the redesigned cast-intake UI"
  ```
