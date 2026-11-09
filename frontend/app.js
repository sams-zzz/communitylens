"use strict";
// Tout texte venu de l'API passe par textContent : un message communautaire ne peut pas injecter de HTML.
const API = window.CL_API || "";
const $ = (id) => document.getElementById(id);
const fr = (value, digits = 1) =>
  Number(value).toLocaleString("fr-FR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
const SVG_NS = "http://www.w3.org/2000/svg";
const STATUS = {
  soutenue: { label: "Soutenue par les données", path: "M2 9l4 4 8-9" },
  contredite: { label: "Contredite par les données", path: "M3 3l10 10M13 3L3 13" },
  non_verifiable: { label: "Non vérifiable avec nos données", path: "M3 8h10" },
};
let tickers = [];
let current = null;

async function getJson(path, options) {
  const response = await fetch(API + path, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(payload.detail || "Le service ne répond pas. Réessayez dans un instant.");
    error.status = response.status;
    throw error;
  }
  return payload;
}

function dateFr(iso) {
  return new Date(`${iso.slice(0, 10)}T12:00:00Z`).toLocaleDateString("fr-FR", {
    day: "numeric", month: "long", year: "numeric",
  });
}

function svgEl(name, attrs = {}, text) {
  const node = document.createElementNS(SVG_NS, name);
  Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
  if (text !== undefined) node.textContent = text;
  return node;
}

function drawChart(history, forecast) {
  const width = Math.max(300, $("chart").clientWidth || 1000);
  const compact = width < 600;
  const height = compact ? 280 : 360;
  const margin = { top: 16, right: compact ? 92 : 150, bottom: 28, left: 44 };
  const values = history.flatMap((d) => [d.low, d.high, d.realized].filter((v) => v !== null));
  values.push(forecast.low_pct, forecast.high_pct);
  const maxY = Math.ceil(Math.max(...values) / 10) * 10;
  const x = (i) => margin.left + (i / (history.length - 1)) * (width - margin.left - margin.right);
  const y = (v) => height - margin.bottom - (v / maxY) * (height - margin.top - margin.bottom);
  const svg = svgEl("svg", {
    viewBox: `0 0 ${width} ${height}`,
    role: "img",
    "aria-label": `Volatilité prévue et observée de ${forecast.ticker} sur les derniers mois.`,
  });
  for (let tick = 0; tick <= maxY; tick += maxY > 80 ? 20 : 10) {
    svg.append(svgEl("line", { class: "gridline", x1: margin.left, x2: width - margin.right, y1: y(tick), y2: y(tick) }));
    svg.append(svgEl("text", { class: "axis", x: margin.left - 8, y: y(tick) + 4, "text-anchor": "end" }, `${tick} %`));
  }
  const top = history.map((d, i) => `${x(i)},${y(d.high)}`).join(" ");
  const bottom = history.map((d, i) => `${x(i)},${y(d.low)}`).reverse().join(" ");
  svg.append(svgEl("polygon", { class: "area", points: `${top} ${bottom}` }));
  svg.append(svgEl("polyline", { class: "forecast", points: history.map((d, i) => `${x(i)},${y(d.predicted)}`).join(" ") }));
  history.forEach((d, i) => {
    if (d.realized !== null) svg.append(svgEl("circle", { class: "realized", cx: x(i), cy: y(d.realized), r: 2.6 }));
  });
  const ticks = compact ? [0, history.length - 1] : [0, Math.floor(history.length / 2), history.length - 1];
  ticks.forEach((i) => {
    const anchor = i === 0 ? "start" : i === history.length - 1 ? "end" : "middle";
    svg.append(svgEl("text", { class: "axis", x: x(i), y: height - 6, "text-anchor": anchor }, dateFr(history[i].date)));
  });
  const nextX = width - margin.right + (compact ? 18 : 28);
  svg.append(svgEl("rect", { class: "next-area", x: nextX - 12, width: 24, y: y(forecast.high_pct), height: y(forecast.low_pct) - y(forecast.high_pct) }));
  svg.append(svgEl("line", { class: "next-line", x1: nextX - 14, x2: nextX + 14, y1: y(forecast.volatility_pct), y2: y(forecast.volatility_pct) }));
  svg.append(svgEl("text", { class: "next-label", x: nextX + 18, y: y(forecast.volatility_pct) + 5 }, `${fr(forecast.volatility_pct)} %`));
  svg.append(svgEl("text", { class: "axis", x: nextX + 18, y: y(forecast.high_pct) + 4 }, `${fr(forecast.high_pct)} %`));
  svg.append(svgEl("text", { class: "axis", x: nextX + 18, y: y(forecast.low_pct) + 4 }, `${fr(forecast.low_pct)} %`));
  $("chart").replaceChildren(svg);
}

function renderCited(container, text, analysis) {
  const facts = Object.fromEntries(analysis.facts.map((f) => [f.id, f]));
  const passages = Object.fromEntries(analysis.passages.map((p) => [p.id, p]));
  container.replaceChildren();
  text.split(/(\[(?:F|P)\d+\])/).forEach((part) => {
    const match = part.match(/^\[((?:F|P)\d+)\]$/);
    if (!match) {
      container.append(document.createTextNode(part));
      return;
    }
    const fact = facts[match[1]];
    const passage = passages[match[1]];
    const url = passage && passage.url && /^https:\/\//.test(passage.url) ? passage.url : null;
    const cite = document.createElement(url ? "a" : "span");
    cite.className = "cite";
    cite.textContent = match[1];
    cite.title = fact ? `${fact.label} : ${fr(fact.value)}` : passage ? passage.text : "";
    if (url) {
      cite.href = url;
      cite.target = "_blank";
      cite.rel = "noopener noreferrer";
    }
    container.append(cite);
  });
}

function renderClaims(analysis) {
  const list = $("claims");
  list.replaceChildren();
  const passages = Object.fromEntries(analysis.passages.map((p) => [p.id, p]));
  analysis.explanation.claims.forEach((claim) => {
    const item = document.createElement("li");
    const status = document.createElement("span");
    status.className = `claim-status ${claim.status}`;
    const icon = svgEl("svg", { viewBox: "0 0 16 16", "aria-hidden": "true" });
    icon.append(svgEl("path", { d: STATUS[claim.status].path, fill: "none", stroke: "currentColor", "stroke-width": "2.5" }));
    status.append(icon, document.createTextNode(STATUS[claim.status].label));
    const text = document.createElement("p");
    text.className = "claim-text";
    renderCited(text, claim.text, analysis);
    item.append(status, text);
    const source = claim.evidence.map((id) => passages[id]).find(Boolean);
    if (source) {
      const line = document.createElement("p");
      line.className = "claim-source";
      line.textContent = `${source.source}, ${dateFr(source.published_at)}`;
      item.append(line);
    }
    list.append(item);
  });
  $("no-claims").hidden = analysis.explanation.claims.length > 0;
}

function renderDrivers(forecast) {
  const list = $("drivers");
  list.replaceChildren();
  const max = Math.max(...forecast.attributions.map((a) => Math.abs(a.effect_pct)), 1);
  forecast.attributions.forEach((attribution) => {
    const item = document.createElement("li");
    const name = document.createElement("div");
    name.className = "driver-name";
    const label = document.createElement("span");
    label.textContent = attribution.label;
    const value = document.createElement("strong");
    value.textContent = `${attribution.effect_pct > 0 ? "+" : ""}${fr(attribution.effect_pct)} %`;
    name.append(label, value);
    const bar = document.createElement("div");
    bar.className = "driver-bar";
    const fill = document.createElement("div");
    fill.className = `driver-fill ${attribution.effect_pct >= 0 ? "up" : "down"}`;
    fill.style.width = `${(Math.abs(attribution.effect_pct) / max) * 50}%`;
    bar.append(fill);
    item.append(name, bar);
    list.append(item);
  });
}

function renderMode(generation) {
  const mode = $("mode");
  const messages = {
    demo: "Mode démonstration : le texte vient de règles simples, sans LLM. Les messages affichés sont fictifs.",
    "repli-sans-llm": "Le texte du modèle n'a pas passé nos contrôles. Ce résumé a été écrit par le code.",
  };
  mode.textContent = messages[generation.generator] || "";
  mode.hidden = !messages[generation.generator];
}

function render(analysis, history) {
  current = analysis;
  const f = analysis.forecast;
  const direction = f.volatility_pct >= f.usual_volatility_pct ? "plus agitée" : "plus calme";
  $("headline").textContent = `L'action ${analysis.company} devrait être ${direction} que d'habitude cette semaine.`;
  $("dated").textContent = `Données du ${dateFr(f.as_of)}. Prévision à ${f.horizon_days} jours de bourse.`;
  $("corridor-reading").textContent =
    `Volatilité annualisée prévue : ${fr(f.volatility_pct)} %, probablement entre ${fr(f.low_pct)} % et ${fr(f.high_pct)} %. ` +
    `Sur les 60 derniers jours mesurés, la réalité est tombée dans l'intervalle ${fr(f.coverage_60d_pct, 0)} % du temps, pour une cible de ${f.level_pct} %.`;
  if (history.length > 1) drawChart(history, f);
  renderCited($("summary"), analysis.explanation.summary, analysis);
  renderClaims(analysis);
  $("limits").textContent = analysis.explanation.limits;
  renderDrivers(f);
  renderMode(analysis.generation);
  $("vote-result").textContent = "";
  ["vote-yes", "vote-no"].forEach((id) => { $(id).disabled = false; });
  $("report").hidden = false;
  $("status").textContent = "";
}

function findTicker(query) {
  const text = query.trim().toLowerCase();
  if (!text) return null;
  return (
    tickers.find((t) => t.ticker.toLowerCase() === text || t.company.toLowerCase() === text) ||
    tickers.find((t) => t.company.toLowerCase().startsWith(text) || `${t.company} (${t.ticker})`.toLowerCase() === text) ||
    null
  );
}

async function loadTicker(ticker) {
  $("status").textContent = "Vérification en cours.";
  try {
    const [analysis, history] = await Promise.all([
      getJson(`/v1/tickers/${ticker}/analysis`),
      getJson(`/v1/tickers/${ticker}/history`),
    ]);
    window.location.hash = `#/analyse/${analysis.id}`;
    render(analysis, history);
  } catch (error) {
    $("report").hidden = true;
    $("status").textContent = error.message;
  }
}

async function loadShared(id) {
  $("status").textContent = "Chargement de l'analyse partagée.";
  try {
    const analysis = await getJson(`/v1/analyses/${id}`);
    const history = await getJson(`/v1/tickers/${analysis.ticker}/history`).catch(() => []);
    render(analysis, history);
  } catch (error) {
    $("report").hidden = true;
    $("status").textContent = error.status === 404 ? "Ce lien ne correspond à aucune analyse." : error.message;
  }
}

function voterToken() {
  try {
    let token = localStorage.getItem("cl-voter");
    if (!token) {
      token = crypto.randomUUID();
      localStorage.setItem("cl-voter", token);
    }
    return token;
  } catch {
    return crypto.randomUUID();
  }
}

async function vote(useful) {
  if (!current) return;
  try {
    const counts = await getJson(`/v1/analyses/${current.id}/votes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: voterToken(), useful }),
    });
    $("vote-result").textContent = `Vote enregistré. Oui : ${counts.useful}, non : ${counts.not_useful}.`;
  } catch (error) {
    $("vote-result").textContent = error.message;
  }
  ["vote-yes", "vote-no"].forEach((id) => { $(id).disabled = true; });
}

function tableFrom(headers, rows) {
  const wrap = document.createElement("div");
  wrap.className = "table-wrap";
  const table = document.createElement("table");
  const head = table.createTHead().insertRow();
  headers.forEach((text, i) => {
    const th = document.createElement("th");
    th.textContent = text;
    if (i) th.className = "num";
    head.append(th);
  });
  const body = table.createTBody();
  rows.forEach((row) => {
    const tr = body.insertRow();
    row.forEach((text, i) => {
      const cell = tr.insertCell();
      cell.textContent = text;
      if (i) cell.className = "num";
    });
  });
  wrap.append(table);
  return wrap;
}

async function loadReliability() {
  const body = $("reliability-body");
  if (body.childElementCount) return;
  try {
    const m = await getJson("/v1/metrics");
    const names = { ridge: "Notre modèle (Ridge)", xgboost: "XGBoost", har: "HAR", persistence: "Volatilité récente reconduite", historical_mean: "Moyenne historique" };
    const intro = document.createElement("p");
    intro.textContent = `Test sur ${m.dataset.tickers} titres, du ${dateFr(m.dataset.out_of_sample_start)} au ${dateFr(m.dataset.end)}, sans jamais utiliser le futur. Plus l'erreur est basse, mieux c'est.`;
    const rows = Object.entries(m.volatility.models).map(([key, v]) => [names[key], fr(v.mae, 3), fr(v.qlike, 3)]);
    const direction = document.createElement("p");
    direction.textContent = `Prédire la hausse ou la baisse du lendemain ne fonctionne pas sur ces données : ${fr(m.direction.xgboost.accuracy * 100)} % de réussite, contre ${fr(m.direction.always_up_accuracy * 100)} % en répondant toujours « hausse ». C'est pourquoi nous prévoyons le risque et non la direction.`;
    const coverage = document.createElement("p");
    coverage.textContent = `L'intervalle annoncé à 80 % a contenu la réalité dans ${fr(m.intervals.adaptive_80.coverage * 100)} % des cas.`;
    body.append(intro, tableFrom(["Modèle", "Erreur absolue", "QLIKE"], rows), coverage, direction);
  } catch (error) {
    body.textContent = error.message;
  }
}

async function init() {
  try {
    tickers = await getJson("/v1/tickers");
    $("tickers").replaceChildren(
      ...tickers.map((t) => {
        const option = document.createElement("option");
        option.value = `${t.company} (${t.ticker})`;
        return option;
      }),
    );
  } catch (error) {
    $("status").textContent = error.message;
    return;
  }
  const shared = window.location.hash.match(/^#\/analyse\/([0-9a-f]{32})$/);
  if (shared) await loadShared(shared[1]);
  else if (tickers.some((t) => t.ticker === "AAPL")) await loadTicker("AAPL");
}

$("search").addEventListener("submit", (event) => {
  event.preventDefault();
  const found = findTicker($("query").value);
  if (found) loadTicker(found.ticker);
  else $("status").textContent = "Ce titre n'est pas suivi. Essayez Apple, Microsoft ou Coca-Cola.";
});
$("vote-yes").addEventListener("click", () => vote(true));
$("vote-no").addEventListener("click", () => vote(false));
$("copy").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(window.location.href);
    $("copy").textContent = "Lien copié";
  } catch {
    $("copy").textContent = "Copiez l'adresse de cette page";
  }
});
$("reliability").addEventListener("toggle", loadReliability);
init();
