const state = { editingCastId: null, lastSavedSnapshot: null };

async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw { status: response.status, body };
  }
  return response.status === 204 ? null : response.json();
}

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

async function openEditor(castId) {
  const session = await api("/api/session");
  const cast = session.casts.find((c) => c.id === castId) || {};
  state.editingCastId = castId || null;
  const form = document.getElementById("cast-form");
  form.reset();
  document.querySelectorAll(".field-map").forEach((container) => {
    // A value about to be applied below (or left blank) is either a deliberate
    // saved-cast value or nothing at all -- never a fresh auto-suggestion for
    // this cast, so any leftover flag from a previously-edited cast must not
    // survive into this one (see populateFieldMapSelect).
    container.dataset.autoSuggested = "false";
  });
  for (const [key, value] of Object.entries(cast)) {
    const field = form.elements.namedItem(key);
    if (field) field.value = value ?? "";
  }
  if (cast.time_start) form.elements.namedItem("time_start_raw").value = cast.time_start.join(" ");
  if (cast.time_end) form.elements.namedItem("time_end_raw").value = cast.time_end.join(" ");
  updateQuickConvertWarning();
  document.getElementById("cast-editor").hidden = false;
  await loadLadcpSuggestions();
  state.lastSavedSnapshot = serializeCastForm();
  setSaveState("Saved", "saved");
}

async function loadLadcpSuggestions() {
  let data;
  try {
    data = await api("/api/ladcp/scan");
  } catch (e) {
    return;
  }
  const select = document.getElementById("ladcp-suggestions");
  select.innerHTML = "";
  for (const cast of data.casts) {
    const option = document.createElement("option");
    option.value = JSON.stringify(cast);
    option.textContent = `station ${cast.station}: ${cast.down || "?"} / ${cast.up || "?"}`;
    select.appendChild(option);
  }
}

document.getElementById("apply-ladcp-suggestion").addEventListener("click", () => {
  const select = document.getElementById("ladcp-suggestions");
  if (!select.value) return;
  const chosen = JSON.parse(select.value);
  const form = document.getElementById("cast-form");
  form.elements.namedItem("ladcp_station").value = parseInt(chosen.station, 10);
  form.elements.namedItem("ladcpdo").value = chosen.down || "";
  form.elements.namedItem("ladcpup").value = chosen.up || "";
  form.elements.namedItem("cast_name").value = chosen.station;
  updateSaveStateFromForm();
});

async function renderPreview(mount, pathInputId, modalTitle, roleFields, fieldPrefix) {
  const path = document.getElementById(pathInputId).value;
  if (!path) return;
  const preview = await api(`/api/preview/${mount}?path=${encodeURIComponent(path)}`);
  const form = document.getElementById("cast-form");
  form.elements.namedItem(`${fieldPrefix}_header_lines`).value = preview.header_lines;
  form.elements.namedItem(`${fieldPrefix}_fields_per_line`).value = preview.fields_per_line;

  const columnNames = preview.column_names;

  openModal(modalTitle, (body) => {
    const table = document.createElement("table");
    const headerRow = document.createElement("tr");
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
    // Clear out any options left over from a previous preview of a different
    // file before deciding this preview's mode -- otherwise a headerless file
    // previewed right after a named-header one inherits the old file's
    // options and its toggle button stays wrongly clickable (setFieldMapMode
    // gauges "anything to choose from" purely off select.options.length).
    clearFieldMapSelect(inputName);
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

function clearFieldMapSelect(inputName) {
  const container = fieldMapContainer(inputName);
  if (!container) return;
  container.querySelector(".field-map-select").innerHTML = "";
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
    container.dataset.autoSuggested = "false";
    updateSaveStateFromForm();
  };

  // manual.value being non-empty is not by itself proof of a deliberate
  // choice -- it might just be this same role field's own auto-suggestion
  // from an earlier preview of a different file in this session. Only
  // preserve it when it was NOT auto-suggested (i.e. the user typed it,
  // picked it from a select, or it came from a loaded saved cast); a
  // leftover auto-suggested value is safe, and correct, to overwrite with
  // this preview's fresh suggestion (or clear, if this file has none).
  const hadAutoSuggestedValue = container.dataset.autoSuggested === "true";
  if (manual.value && !hadAutoSuggestedValue) {
    select.value = manual.value;
  } else if (suggestedIndex != null) {
    select.value = String(suggestedIndex);
    manual.value = String(suggestedIndex);
    container.dataset.autoSuggested = "true";
    updateSaveStateFromForm();
  } else {
    select.value = "";
    manual.value = "";
    container.dataset.autoSuggested = "false";
    updateSaveStateFromForm();
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

document.querySelectorAll(".field-map-manual").forEach((manual) => {
  manual.addEventListener("input", () => {
    // A direct edit is always deliberate -- never let a later preview's
    // auto-suggest silently overwrite it (see populateFieldMapSelect).
    const container = manual.closest(".field-map");
    if (container) container.dataset.autoSuggested = "false";
  });
});

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
        updateSaveStateFromForm();
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

initBrowser("browse-ctd", "ctd", "ctd-path");
initBrowser("browse-nav", "nav", "nav-path");
initBrowser("browse-ladcpdo", "ladcp", "ladcpdo-path");
initBrowser("browse-ladcpup", "ladcp", "ladcpup-path");

initBrowser("browse-quickconvert-hex", "ctd", "quickconvert-hex-path");
initBrowser("browse-quickconvert-xmlcon", "ctd", "quickconvert-xmlcon-path");

const QUICKCONVERT_SUFFIX = ".UNVALIDATED_QUICKCONVERT.cnv";

function updateQuickConvertWarning() {
  const value = document.getElementById("ctd-path").value;
  document.getElementById("ctd-quickconvert-warning").hidden = !value.endsWith(QUICKCONVERT_SUFFIX);
}

document.getElementById("ctd-path").addEventListener("input", updateQuickConvertWarning);

document.getElementById("cast-form").addEventListener("input", updateSaveStateFromForm);

document.getElementById("run-quickconvert").addEventListener("click", async () => {
  const hexPath = document.getElementById("quickconvert-hex-path").value;
  const xmlconPath = document.getElementById("quickconvert-xmlcon-path").value;
  const result = document.getElementById("quickconvert-result");
  if (!hexPath || !xmlconPath) {
    result.textContent = "Pick both a .hex file and its .XMLCON file first.";
    result.className = "error";
    return;
  }
  try {
    const body = await api("/api/quick-convert/ctd", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ hex_path: hexPath, xmlcon_path: xmlconPath }),
    });
    document.getElementById("ctd-path").value = body.ctd_path;
    updateQuickConvertWarning();
    result.textContent = `Converted. CTD file set to ${body.ctd_path} — remember, this is unvalidated.`;
    result.className = "warning";
  } catch (e) {
    result.textContent = (e.body && e.body.detail) || "Quick-convert failed.";
    result.className = "error";
  }
});

document.getElementById("preview-ctd").addEventListener("click", () => {
  const ctdPath = document.getElementById("ctd-path").value;
  const mount = ctdPath.endsWith(QUICKCONVERT_SUFFIX) ? "data" : "ctd";
  renderPreview(mount, "ctd-path", "CTD column preview", ["time", "pressure", "temperature", "salinity"], "ctd");
});
document.getElementById("preview-nav").addEventListener("click", () => {
  renderPreview("nav", "nav-path", "Nav column preview", ["time", "lat", "lon"], "nav");
});

document.getElementById("add-cast").addEventListener("click", async () => {
  const created = await api("/api/session/casts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  await refreshCastList();
  await openEditor(created.id);
});

document.getElementById("cast-cards").addEventListener("click", async (event) => {
  const editId = event.target.dataset.edit;
  const cloneId = event.target.dataset.clone;
  const removeId = event.target.dataset.remove;
  if (editId) await openEditor(editId);
  if (cloneId) {
    await api(`/api/session/casts/${cloneId}/clone`, { method: "POST" });
    await refreshCastList();
  }
  if (removeId) {
    await api(`/api/session/casts/${removeId}`, { method: "DELETE" });
    await refreshCastList();
  }
});

document.getElementById("cast-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.target;
  const payload = {};
  for (const element of form.elements) {
    if (!element.name || element.name.endsWith("_raw")) continue;
    if (element.value === "") continue;
    const isNumericSelect = element.tagName === "SELECT" && element.value !== "" && !Number.isNaN(Number(element.value));
    payload[element.name] = (element.type === "number" || isNumericSelect) ? Number(element.value) : element.value;
  }
  const startRaw = form.elements.namedItem("time_start_raw").value;
  const endRaw = form.elements.namedItem("time_end_raw").value;
  if (startRaw) payload.time_start = startRaw.trim().split(/\s+/).map(Number);
  if (endRaw) payload.time_end = endRaw.trim().split(/\s+/).map(Number);

  await api(`/api/session/casts/${state.editingCastId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  state.lastSavedSnapshot = serializeCastForm();
  setSaveState("Saved", "saved");
  document.getElementById("cast-editor").hidden = true;
  await refreshCastList();
});

document.getElementById("cruise-id").addEventListener("change", async (event) => {
  await api("/api/session", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cruise_id: event.target.value }),
  });
});

document.getElementById("generate").addEventListener("click", async () => {
  const result = document.getElementById("generate-result");
  try {
    const body = await api("/api/generate", { method: "POST" });
    result.textContent = `Written to ${body.written_to}`;
    result.className = "";
  } catch (e) {
    result.textContent = JSON.stringify(e.body, null, 2);
    result.className = "error";
  }
});

refreshCastList();
