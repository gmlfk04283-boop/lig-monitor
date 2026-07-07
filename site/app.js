const DATA = {
  papers: [],
  graph: { nodes: [], edges: [] },
  reportsIndex: [],
  alerts: { alerts: [] },
};

const THEME_LABELS = {
  new_application: "신규 응용분야 개척",
  device_performance: "소자 성능/다기능 최적화",
  energy_storage: "에너지 저장/변환 소자",
  mechanism_process: "합성 메커니즘/공정 규명",
  review: "종합 리뷰/전망",
};

async function loadJSON(path, fallback) {
  try {
    const res = await fetch(path, { cache: "no-store" });
    if (!res.ok) throw new Error(res.status);
    return await res.json();
  } catch (e) {
    return fallback;
  }
}

async function loadText(path) {
  try {
    const res = await fetch(path, { cache: "no-store" });
    if (!res.ok) throw new Error(res.status);
    return await res.text();
  } catch (e) {
    return null;
  }
}

function setEmpty(id, isEmpty) {
  const el = document.getElementById(id);
  if (el) el.hidden = !isEmpty;
}

function renderStats() {
  const journals = new Set(DATA.papers.map((p) => p.journal));
  const themes = new Set(DATA.papers.map((p) => p.theme).filter(Boolean));
  document.getElementById("stat-papers").textContent = DATA.papers.length;
  document.getElementById("stat-journals").textContent = journals.size;
  document.getElementById("stat-themes").textContent = themes.size || Object.keys(THEME_LABELS).length;

  const generatedAt = DATA.graph.generated_at;
  document.getElementById("last-updated").textContent = generatedAt
    ? `마지막 업데이트: ${new Date(generatedAt).toLocaleString("ko-KR")}`
    : "아직 데이터 없음";
}

function renderGraph() {
  const nodes = DATA.graph.nodes || [];
  const edges = DATA.graph.edges || [];
  setEmpty("graph-empty", nodes.length === 0);
  if (nodes.length === 0) return;

  const svg = d3.select("#graph-svg");
  const width = document.getElementById("graph-panel").clientWidth;
  const height = 420;
  svg.attr("viewBox", [0, 0, width, height]);
  svg.selectAll("*").remove();

  const nodeData = nodes.map((n) => ({ ...n }));
  const edgeData = edges.map((e) => ({ ...e }));

  const simulation = d3
    .forceSimulation(nodeData)
    .force("link", d3.forceLink(edgeData).id((d) => d.id).distance(160).strength(0.3))
    .force("charge", d3.forceManyBody().strength(-260))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force("collide", d3.forceCollide().radius((d) => radiusFor(d) + 24));

  const link = svg
    .append("g")
    .selectAll("path")
    .data(edgeData)
    .join("path")
    .attr("class", "edge")
    .attr("stroke-width", (d) => Math.max(1, Math.min(8, d.weight)));

  const node = svg
    .append("g")
    .selectAll("g")
    .data(nodeData)
    .join("g")
    .attr("class", (d) => (d.type === "journal" ? "journal-node" : "theme-node"))
    .call(drag(simulation))
    .on("click", (event, d) => applyFilter(d));

  node.append("circle").attr("r", (d) => radiusFor(d));

  node
    .append("text")
    .attr("class", "node-label")
    .attr("text-anchor", "middle")
    .attr("dy", (d) => radiusFor(d) + 14)
    .text((d) => (d.type === "theme" ? d.label : d.id));

  simulation.on("tick", () => {
    link.attr("d", (d) => `M${d.source.x},${d.source.y} L${d.target.x},${d.target.y}`);
    node.attr("transform", (d) => `translate(${d.x},${d.y})`);
  });

  function radiusFor(d) {
    return 18 + Math.min(24, (d.count || 1) * 2.5);
  }

  function drag(sim) {
    return d3
      .drag()
      .on("start", (event, d) => {
        if (!event.active) sim.alphaTarget(0.2).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on("drag", (event, d) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on("end", (event, d) => {
        if (!event.active) sim.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      });
  }
}

function applyFilter(node) {
  if (node.type === "journal") {
    document.getElementById("filter-journal").value = node.id;
  } else {
    document.getElementById("filter-theme").value = node.id;
  }
  renderPapers();
  document.getElementById("papers-panel").scrollIntoView({ behavior: "smooth" });
}

let breakdownChart = null;
function renderBreakdown() {
  const byJournal = {};
  DATA.papers.forEach((p) => {
    if (!p.theme) return;
    byJournal[p.journal] = byJournal[p.journal] || {};
    byJournal[p.journal][p.theme] = (byJournal[p.journal][p.theme] || 0) + 1;
  });

  const journals = Object.keys(byJournal);
  setEmpty("breakdown-empty", journals.length === 0);
  if (journals.length === 0) return;

  const themeIds = Object.keys(THEME_LABELS);
  const colors = ["#c17f3e", "#6fae8f", "#8a5c2c", "#3f6d58", "#b3a390"];

  const datasets = themeIds.map((themeId, i) => ({
    label: THEME_LABELS[themeId],
    data: journals.map((j) => byJournal[j][themeId] || 0),
    backgroundColor: colors[i % colors.length],
  }));

  const ctx = document.getElementById("breakdown-chart");
  if (breakdownChart) breakdownChart.destroy();
  breakdownChart = new Chart(ctx, {
    type: "bar",
    data: { labels: journals, datasets },
    options: {
      responsive: true,
      scales: {
        x: { stacked: true, ticks: { color: "#b3a390" }, grid: { color: "#3a2d20" } },
        y: { stacked: true, ticks: { color: "#b3a390" }, grid: { color: "#3a2d20" } },
      },
      plugins: { legend: { labels: { color: "#f2ead9" } } },
    },
  });
}

async function renderReports() {
  const select = document.getElementById("report-select");
  setEmpty("report-empty", DATA.reportsIndex.length === 0);
  if (DATA.reportsIndex.length === 0) return;

  select.innerHTML = DATA.reportsIndex
    .map((f) => `<option value="${f}">${f.replace(".md", "")}</option>`)
    .join("");

  async function showReport(filename) {
    const md = await loadText(`data/reports/${filename}`);
    document.getElementById("report-body").innerHTML = md ? marked.parse(md) : "";
  }

  select.addEventListener("change", (e) => showReport(e.target.value));
  showReport(DATA.reportsIndex[0]);
}

function renderPapers() {
  const journalFilter = document.getElementById("filter-journal").value;
  const themeFilter = document.getElementById("filter-theme").value;

  const filtered = DATA.papers
    .filter((p) => !journalFilter || p.journal === journalFilter)
    .filter((p) => !themeFilter || p.theme === themeFilter)
    .sort((a, b) => (b.published_date || "").localeCompare(a.published_date || ""));

  setEmpty("papers-empty", filtered.length === 0);

  const list = document.getElementById("papers-list");
  list.innerHTML = filtered
    .slice(0, 100)
    .map(
      (p) => `
      <li>
        <div class="paper-meta">
          <span class="paper-journal">${p.journal}</span>
          <span>IF ${p.impact_factor}</span><br>
          <span>${p.published_date || ""}</span>
        </div>
        <div>
          <p class="paper-title"><a href="https://doi.org/${p.doi}" target="_blank" style="color:inherit">${p.title}</a></p>
          ${p.theme ? `<span class="paper-theme">${THEME_LABELS[p.theme] || p.theme}</span>` : ""}
        </div>
      </li>`
    )
    .join("");
}

function renderAlerts() {
  const alerts = DATA.alerts.alerts || [];
  setEmpty("alert-empty", alerts.length === 0);
  const list = document.getElementById("alert-list");
  list.innerHTML = alerts
    .slice(0, 50)
    .map(
      (a) => `
      <li>
        <div class="paper-meta">
          <span class="paper-journal">${a.journal}</span>
          <span>IF ${a.impact_factor}</span><br>
          <span>${a.published_date || ""}</span>
        </div>
        <div>
          <p class="paper-title"><a href="https://doi.org/${a.doi}" target="_blank" style="color:inherit">${a.title}</a></p>
          ${(a.category_labels || []).map((c) => `<span class="alert-badge">${c}</span>`).join("")}
          ${a.rationale_ko ? `<p style="font-size:13px;color:var(--text-faint);margin-top:6px">${a.rationale_ko}</p>` : ""}
        </div>
      </li>`
    )
    .join("");
}

function populateFilters() {
  const journals = [...new Set(DATA.papers.map((p) => p.journal))].sort();
  const journalSelect = document.getElementById("filter-journal");
  journals.forEach((j) => {
    const opt = document.createElement("option");
    opt.value = j;
    opt.textContent = j;
    journalSelect.appendChild(opt);
  });

  const themeSelect = document.getElementById("filter-theme");
  Object.entries(THEME_LABELS).forEach(([id, label]) => {
    const opt = document.createElement("option");
    opt.value = id;
    opt.textContent = label;
    themeSelect.appendChild(opt);
  });

  journalSelect.addEventListener("change", renderPapers);
  themeSelect.addEventListener("change", renderPapers);
}

async function init() {
  DATA.papers = await loadJSON("data/papers.json", []);
  DATA.graph = await loadJSON("data/journal_theme_graph.json", { nodes: [], edges: [] });
  DATA.reportsIndex = await loadJSON("data/reports/index.json", []);
  DATA.alerts = await loadJSON("data/semiconductor_alerts.json", { alerts: [] });

  renderStats();
  renderAlerts();
  renderGraph();
  renderBreakdown();
  populateFilters();
  renderPapers();
  renderReports();
}

init();
