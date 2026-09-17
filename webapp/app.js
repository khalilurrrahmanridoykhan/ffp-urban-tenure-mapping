const COLORS = { secure: "#2ea043", moderate: "#d4a72c", at_risk: "#e8730a", contested: "#cc2277" };

let map, geoLayer, parcelIndex = {};

async function loadJSON(path) {
  const res = await fetch(path);
  return res.json();
}

function styleFor(feature) {
  const cls = feature.properties.security_class;
  return { color: "#1f2328", weight: feature.properties.disputed ? 2 : 0.7, fillColor: COLORS[cls] || "#999", fillOpacity: 0.55 };
}

function highlightFeature(layer) {
  layer.setStyle({ weight: 3, color: "#0969da" });
  layer.bringToFront();
}

function resetFeature(layer) {
  geoLayer.resetStyle(layer);
}

function showDetail(props) {
  const panel = document.getElementById("detail-panel");
  const content = document.getElementById("detail-content");
  const cls = props.security_class;
  const claimsHtml = props.claims.map(c => `
    <div class="claim">
      <div class="field"><span>Claimant</span><span>${c.claimant_name}</span></div>
      <div class="field"><span>Household size</span><span>${c.household_size}</span></div>
      <div class="field"><span>Tenure type</span><span>${c.tenure_type}</span></div>
      <div class="field"><span>Status</span><span>${c.str_status}</span></div>
      <div class="field"><span>Evidence</span><span>${c.documented_by ? "photo on file" : "none"}</span></div>
    </div>`).join("");

  content.innerHTML = `
    <h3>${props.spatial_unit_id}</h3>
    <span class="badge" style="background:${COLORS[cls]}">${cls}</span>
    <div class="field" style="margin-top:10px"><span>Tenure summary</span><span>${props.tenure_type_summary}</span></div>
    <div class="field"><span>Boundary conflict</span><span>${props.boundary_conflict ? "yes" : "no"}</span></div>
    <div class="field"><span>Claims on file</span><span>${props.claims.length}</span></div>
    ${claimsHtml}
  `;
  panel.classList.remove("hidden");
}

function onEachFeature(feature, layer) {
  layer.on({
    mouseover: () => highlightFeature(layer),
    mouseout: () => resetFeature(layer),
    click: () => showDetail(feature.properties),
  });
  parcelIndex[feature.properties.spatial_unit_id] = layer;
}

function renderStats(features) {
  const counts = {};
  features.forEach(f => { counts[f.properties.security_class] = (counts[f.properties.security_class] || 0) + 1; });
  const el = document.getElementById("stats");
  el.innerHTML = Object.entries(counts).map(([k, v]) => `<div><span>${k}</span><span>${v}</span></div>`).join("")
    + `<div><span><b>Total</b></span><span><b>${features.length}</b></span></div>`;
}

function severityClass(sev) {
  return sev === "high" ? "sev-high" : sev === "medium" ? "sev-medium" : "sev-low";
}

function renderQueue(queue) {
  document.getElementById("queue-count").textContent = queue.length;

  const categories = [...new Set(queue.map(q => q.category))];
  const catSelect = document.getElementById("filter-category");
  categories.forEach(c => catSelect.insertAdjacentHTML("beforeend", `<option value="${c}">${c}</option>`));

  const severities = [...new Set(queue.map(q => q.severity))];
  const sevSelect = document.getElementById("filter-severity");
  severities.forEach(s => sevSelect.insertAdjacentHTML("beforeend", `<option value="${s}">${s}</option>`));

  function draw() {
    const catFilter = catSelect.value;
    const sevFilter = document.getElementById("filter-severity").value;
    const list = document.getElementById("queue-list");
    const filtered = queue.filter(q => (!catFilter || q.category === catFilter) && (!sevFilter || q.severity === sevFilter));
    list.innerHTML = filtered.map(q => `
      <div class="queue-item" data-ids="${q.spatial_unit_ids || ""}">
        <span class="sev ${severityClass(q.severity)}">${q.severity}</span>
        <span class="cat">${q.category.replace(/_/g, " ")}</span>
        <p>${q.description}</p>
      </div>`).join("") || "<p class='hint'>No findings match this filter.</p>";

    list.querySelectorAll(".queue-item").forEach(el => {
      el.addEventListener("click", () => {
        const ids = el.dataset.ids.split(";").filter(Boolean);
        focusParcels(ids);
      });
    });
  }

  catSelect.addEventListener("change", draw);
  document.getElementById("filter-severity").addEventListener("change", draw);
  draw();
}

function focusParcels(ids) {
  if (!ids.length) return;
  const bounds = [];
  ids.forEach(id => {
    const layer = parcelIndex[id];
    if (!layer) return;
    highlightFeature(layer);
    bounds.push(layer.getBounds());
    setTimeout(() => resetFeature(layer), 2500);
  });
  if (bounds.length) {
    let b = bounds[0];
    bounds.slice(1).forEach(x => { b = b.extend(x); });
    map.fitBounds(b, { padding: [80, 80], maxZoom: 3 });
  }
  if (ids.length === 1 && parcelIndex[ids[0]]) {
    showDetail(parcelIndex[ids[0]].feature.properties);
  }
}

function setupTabs() {
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    });
  });
  document.getElementById("detail-close").addEventListener("click", () => {
    document.getElementById("detail-panel").classList.add("hidden");
  });
}

async function main() {
  setupTabs();

  const meta = await loadJSON("data/meta.json");
  const bounds = [[0, 0], [meta.height, meta.width]];

  map = L.map("map", { crs: L.CRS.Simple, minZoom: -2, maxZoom: 4 });
  L.imageOverlay("data/imagery.jpg", bounds).addTo(map);
  map.fitBounds(bounds);

  const security = await loadJSON("data/tenure_security.geojson");
  geoLayer = L.geoJSON(security, { style: styleFor, onEachFeature }).addTo(map);
  renderStats(security.features);

  const queue = await loadJSON("data/adjudication_queue.json");
  renderQueue(queue);
}

main();
