const state = { editingCastId: null };

async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw { status: response.status, body };
  }
  return response.status === 204 ? null : response.json();
}

async function refreshCastTable() {
  const session = await api("/api/session");
  document.getElementById("cruise-id").value = session.cruise_id || "";
  const tbody = document.querySelector("#cast-table tbody");
  tbody.innerHTML = "";
  for (const cast of session.casts) {
    const row = document.createElement("tr");

    const nameCell = document.createElement("td");
    nameCell.textContent = cast.cast_name || "";
    row.appendChild(nameCell);

    const stationCell = document.createElement("td");
    stationCell.textContent = cast.ladcp_station ?? "";
    row.appendChild(stationCell);

    const latCell = document.createElement("td");
    latCell.textContent = cast.lat ?? "";
    row.appendChild(latCell);

    const lonCell = document.createElement("td");
    lonCell.textContent = cast.lon ?? "";
    row.appendChild(lonCell);

    const actionsCell = document.createElement("td");
    const editButton = document.createElement("button");
    editButton.textContent = "Edit";
    editButton.dataset.edit = cast.id;
    const cloneButton = document.createElement("button");
    cloneButton.textContent = "Clone";
    cloneButton.dataset.clone = cast.id;
    const removeButton = document.createElement("button");
    removeButton.textContent = "Remove";
    removeButton.dataset.remove = cast.id;
    actionsCell.appendChild(editButton);
    actionsCell.appendChild(cloneButton);
    actionsCell.appendChild(removeButton);
    row.appendChild(actionsCell);

    tbody.appendChild(row);
  }
}

async function openEditor(castId) {
  const session = await api("/api/session");
  const cast = session.casts.find((c) => c.id === castId) || {};
  state.editingCastId = castId || null;
  const form = document.getElementById("cast-form");
  form.reset();
  for (const [key, value] of Object.entries(cast)) {
    const field = form.elements.namedItem(key);
    if (field) field.value = value ?? "";
  }
  if (cast.time_start) form.elements.namedItem("time_start_raw").value = cast.time_start.join(" ");
  if (cast.time_end) form.elements.namedItem("time_end_raw").value = cast.time_end.join(" ");
  document.getElementById("cast-editor").hidden = false;
  await loadLadcpSuggestions();
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
});

async function renderPreview(mount, pathInputId, targetDivId, roleFields) {
  const path = document.getElementById(pathInputId).value;
  if (!path) return;
  const preview = await api(`/api/preview/${mount}?path=${encodeURIComponent(path)}`);
  const div = document.getElementById(targetDivId);
  const form = document.getElementById("cast-form");
  form.elements.namedItem(`${mount === "ctd" ? "ctd" : "nav"}_header_lines`).value = preview.header_lines;
  form.elements.namedItem(`${mount === "ctd" ? "ctd" : "nav"}_fields_per_line`).value = preview.fields_per_line;

  const table = document.createElement("table");

  const headerRow = document.createElement("tr");
  for (let col = 0; col < preview.fields_per_line; col++) {
    const th = document.createElement("th");
    const select = document.createElement("select");
    select.dataset.col = col;
    const blankOption = document.createElement("option");
    blankOption.value = "";
    blankOption.textContent = "-";
    select.appendChild(blankOption);
    for (const role of roleFields) {
      const option = document.createElement("option");
      option.value = role;
      option.textContent = role;
      select.appendChild(option);
    }
    th.appendChild(select);
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

  div.querySelectorAll("select[data-col]").forEach((select) => {
    select.addEventListener("change", () => {
      const col = parseInt(select.dataset.col, 10) + 1;
      const role = select.value;
      if (!role) return;
      const fieldName = `${mount === "ctd" ? "ctd" : "nav"}_${role}_field`;
      const field = form.elements.namedItem(fieldName);
      if (field) field.value = col;
    });
  });
}

async function renderBrowserPanel(panelId, mount, targetInputId, relativePath) {
  const panel = document.getElementById(panelId);
  panel.dataset.currentPath = relativePath;
  panel.innerHTML = "";

  const pathLine = document.createElement("div");
  pathLine.className = "browser-path";
  pathLine.textContent = `${mount}:/${relativePath}`;
  panel.appendChild(pathLine);

  let data;
  try {
    data = await api(`/api/browse/${mount}?path=${encodeURIComponent(relativePath)}`);
  } catch (e) {
    const err = document.createElement("div");
    err.className = "browser-error";
    err.textContent = (e.body && e.body.detail) || `could not browse ${mount}`;
    panel.appendChild(err);
    return;
  }

  if (relativePath) {
    const up = document.createElement("div");
    up.className = "browser-entry is-dir";
    up.textContent = ".. (up)";
    up.addEventListener("click", () => {
      const parent = relativePath.split("/").slice(0, -1).join("/");
      renderBrowserPanel(panelId, mount, targetInputId, parent);
    });
    panel.appendChild(up);
  }

  for (const entry of data.entries) {
    const row = document.createElement("div");
    row.className = entry.is_dir ? "browser-entry is-dir" : "browser-entry";
    row.textContent = entry.is_dir ? `${entry.name}/` : entry.name;
    row.addEventListener("click", () => {
      if (entry.is_dir) {
        renderBrowserPanel(panelId, mount, targetInputId, entry.relative_path);
      } else {
        document.getElementById(targetInputId).value = entry.relative_path;
        panel.hidden = true;
      }
    });
    panel.appendChild(row);
  }
}

function initBrowser(buttonId, mount, targetInputId, panelId) {
  document.getElementById(buttonId).addEventListener("click", () => {
    const panel = document.getElementById(panelId);
    if (!panel.hidden) {
      panel.hidden = true;
      return;
    }
    panel.hidden = false;
    renderBrowserPanel(panelId, mount, targetInputId, panel.dataset.currentPath || "");
  });
}

initBrowser("browse-ctd", "ctd", "ctd-path", "ctd-browser");
initBrowser("browse-nav", "nav", "nav-path", "nav-browser");
initBrowser("browse-ladcpdo", "ladcp", "ladcpdo-path", "ladcpdo-browser");
initBrowser("browse-ladcpup", "ladcp", "ladcpup-path", "ladcpup-browser");

document.getElementById("preview-ctd").addEventListener("click", () => {
  renderPreview("ctd", "ctd-path", "ctd-preview", ["time", "pressure", "temperature", "salinity"]);
});
document.getElementById("preview-nav").addEventListener("click", () => {
  renderPreview("nav", "nav-path", "nav-preview", ["time", "lat", "lon"]);
});

document.getElementById("add-cast").addEventListener("click", async () => {
  const created = await api("/api/session/casts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  await refreshCastTable();
  await openEditor(created.id);
});

document.querySelector("#cast-table tbody").parentElement.addEventListener("click", async (event) => {
  const editId = event.target.dataset.edit;
  const cloneId = event.target.dataset.clone;
  const removeId = event.target.dataset.remove;
  if (editId) await openEditor(editId);
  if (cloneId) {
    await api(`/api/session/casts/${cloneId}/clone`, { method: "POST" });
    await refreshCastTable();
  }
  if (removeId) {
    await api(`/api/session/casts/${removeId}`, { method: "DELETE" });
    await refreshCastTable();
  }
});

document.getElementById("cast-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.target;
  const payload = {};
  for (const element of form.elements) {
    if (!element.name || element.name.endsWith("_raw")) continue;
    if (element.value === "") continue;
    payload[element.name] = element.type === "number" ? Number(element.value) : element.value;
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
  document.getElementById("cast-editor").hidden = true;
  await refreshCastTable();
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

refreshCastTable();
