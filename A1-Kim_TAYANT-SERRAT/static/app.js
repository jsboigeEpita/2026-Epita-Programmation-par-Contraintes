const API = "";

const state = {
  foods: [],
  excluded: new Set(),
};

const CATEGORY_STYLES = {
  "féculent":   { bg: "bg-amber-100",    text: "text-amber-800",    label: "Féculent",  icon: "🍞" },
  "légume":     { bg: "bg-emerald-100",  text: "text-emerald-800",  label: "Légume",    icon: "🥬" },
  "viande":     { bg: "bg-rose-100",     text: "text-rose-800",     label: "Viande",    icon: "🥩" },
  "poisson":    { bg: "bg-sky-100",      text: "text-sky-800",      label: "Poisson",   icon: "🐟" },
  "protéine":   { bg: "bg-violet-100",   text: "text-violet-800",   label: "Protéine",  icon: "🥚" },
  "dessert":    { bg: "bg-pink-100",     text: "text-pink-800",     label: "Dessert",   icon: "🍓" },
  "autre":      { bg: "bg-stone-100",    text: "text-stone-700",    label: "Autre",     icon: "•"  },
};

const STATUS_STYLES = {
  optimal:    { bg: "bg-emerald-100", text: "text-emerald-700",  dot: "bg-emerald-500", label: "Optimal" },
  feasible:   { bg: "bg-amber-100",   text: "text-amber-700",    dot: "bg-amber-500",   label: "Faisable" },
  infeasible: { bg: "bg-red-100",     text: "text-red-700",      dot: "bg-red-500",     label: "Infaisable" },
};

// --- Init ---
async function init() {
  bindForm();
  try {
    const foods = await fetchJSON("/api/foods");
    state.foods = foods.sort((a, b) => a.nom.localeCompare(b.nom));
    setStatus(`${foods.length} aliments chargés`, true);
  } catch (e) {
    setStatus("API indisponible", false);
    showError(`Impossible de charger les aliments : ${e.message}`);
  }
  bindExcludeSearch();
}

function setStatus(text, ok = true) {
  const el = document.getElementById("api-status");
  el.textContent = text;
  el.parentElement.querySelector("span").className = ok
    ? "text-emerald-600 pulse-dot"
    : "text-red-500 pulse-dot";
}

async function fetchJSON(path, opts = {}) {
  const r = await fetch(API + path, opts);
  if (!r.ok) {
    const detail = await r.json().catch(() => ({}));
    throw new Error(detail.detail || `HTTP ${r.status}`);
  }
  return r.json();
}

// --- Form ---
function bindForm() {
  const slider = document.getElementById("budget-slider");
  const display = document.getElementById("budget-display");
  slider.addEventListener("input", () => {
    display.textContent = `${slider.value} €`;
  });

  document.getElementById("menu-form").addEventListener("submit", onSubmit);
}

async function onSubmit(e) {
  e.preventDefault();
  const fd = new FormData(e.target);
  const payload = {
    days: parseInt(fd.get("days"), 10),
    meals_per_day: parseInt(fd.get("meals_per_day"), 10),
    budget_eur: parseFloat(fd.get("budget_eur")),
    vegetarian: fd.get("vegetarian") === "on",
    excluded_foods: [...state.excluded],
    seed: fd.get("seed") ? parseInt(fd.get("seed"), 10) : null,
  };

  toggleStates({ loading: true });
  document.getElementById("generate-btn").disabled = true;

  try {
    const result = await fetchJSON("/api/menu", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    renderResults(result);
  } catch (err) {
    showError(err.message);
  } finally {
    document.getElementById("generate-btn").disabled = false;
  }
}

function toggleStates({ empty = false, loading = false, error = false, results = false }) {
  document.getElementById("empty-state").classList.toggle("hidden", !empty);
  document.getElementById("loading-state").classList.toggle("hidden", !loading);
  document.getElementById("error-state").classList.toggle("hidden", !error);
  document.getElementById("results").classList.toggle("hidden", !results);
}

function showError(msg) {
  toggleStates({ error: true });
  document.getElementById("error-message").textContent = msg;
}

// --- Exclude search ---
function bindExcludeSearch() {
  const input = document.getElementById("exclude-search");
  const box = document.getElementById("exclude-suggestions");

  input.addEventListener("input", () => {
    const q = input.value.trim().toLowerCase();
    if (!q) { box.classList.add("hidden"); return; }
    const matches = state.foods
      .filter(f => f.nom.toLowerCase().includes(q) && !state.excluded.has(f.nom))
      .slice(0, 8);
    if (!matches.length) { box.classList.add("hidden"); return; }
    box.innerHTML = matches.map(f => `
      <button type="button" data-name="${escapeHtml(f.nom)}"
              class="suggestion w-full text-left px-3 py-2 hover:bg-emerald-50 text-sm border-b border-stone-100 last:border-0 flex items-center gap-2">
        <span class="text-xs">${(CATEGORY_STYLES[f.categorie] || CATEGORY_STYLES.autre).icon}</span>
        <span class="truncate">${escapeHtml(f.nom)}</span>
      </button>
    `).join("");
    box.classList.remove("hidden");
  });

  box.addEventListener("click", e => {
    const btn = e.target.closest(".suggestion");
    if (!btn) return;
    addExcluded(btn.dataset.name);
    input.value = "";
    box.classList.add("hidden");
  });

  document.addEventListener("click", e => {
    if (!e.target.closest("#exclude-search") && !e.target.closest("#exclude-suggestions")) {
      box.classList.add("hidden");
    }
  });
}

function addExcluded(name) {
  state.excluded.add(name);
  renderChips();
}

function removeExcluded(name) {
  state.excluded.delete(name);
  renderChips();
}

function renderChips() {
  const container = document.getElementById("exclude-chips");
  container.innerHTML = [...state.excluded].map(name => `
    <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-stone-100 text-stone-700 text-xs border border-stone-200">
      <span class="truncate max-w-[160px]">${escapeHtml(name)}</span>
      <button type="button" data-remove="${escapeHtml(name)}" class="text-stone-400 hover:text-red-500 font-bold leading-none">×</button>
    </span>
  `).join("");
  container.querySelectorAll("[data-remove]").forEach(b => {
    b.addEventListener("click", () => removeExcluded(b.dataset.remove));
  });
}

// --- Results ---
function renderResults(data) {
  toggleStates({ results: true });
  const container = document.getElementById("results");

  const totalFoods = data.days.flat().reduce((acc, m) => acc + m.foods.length, 0);
  const uniqueNames = new Set(data.days.flat().flatMap(m => m.foods.map(f => f.nom)));

  container.innerHTML = `
    <!-- Summary banner -->
    <div class="bg-gradient-to-br from-ink-900 to-ink-950 text-white rounded-2xl p-6 mb-6 fade-in shadow-lg">
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        ${stat("Coût total", `${data.total_cost.toFixed(2)} €`, "text-emerald-300")}
        ${stat("Coût/jour", `${(data.total_cost / data.days.length).toFixed(2)} €`, "text-emerald-300")}
        ${stat("Aliments uniques", uniqueNames.size, "text-amber-300")}
        ${stat("Repas générés", `${data.params.days} × ${data.params.meals_per_day}`, "text-sky-300")}
      </div>
    </div>

    <!-- Days grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
      ${data.days.map((meals, i) => renderDay(i + 1, meals, data.params.meals_per_day)).join("")}
    </div>
  `;
}

function stat(label, value, color) {
  return `
    <div>
      <div class="text-xs text-stone-400 uppercase tracking-wider">${label}</div>
      <div class="text-2xl font-bold ${color} mt-1">${value}</div>
    </div>
  `;
}

function renderDay(dayNum, meals, mealsPerDay) {
  const labels = meals.map((_, i) => `Repas ${i + 1}`);
  const dayCost = meals.reduce((acc, m) => acc + m.cost, 0);

  return `
    <div class="bg-white rounded-2xl border border-stone-200 shadow-sm overflow-hidden fade-in" style="animation-delay: ${dayNum * 40}ms">
      <div class="px-5 py-3 border-b border-stone-100 flex items-center justify-between bg-gradient-to-r from-stone-50 to-white">
        <h3 class="font-bold text-stone-800">Jour ${dayNum}</h3>
        <span class="text-sm font-semibold text-emerald-700">${dayCost.toFixed(2)} €</span>
      </div>
      <div class="divide-y divide-stone-100">
        ${meals.map((meal, i) => renderMeal(meal, labels[i] || `Repas ${i + 1}`)).join("")}
      </div>
    </div>
  `;
}

function renderMeal(meal, label) {
  const status = STATUS_STYLES[meal.status] || STATUS_STYLES.infeasible;

  if (meal.status === "infeasible") {
    return `
      <div class="px-5 py-4">
        <div class="flex items-center justify-between mb-2">
          <span class="font-semibold text-stone-700">${label}</span>
          <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${status.bg} ${status.text}">
            <span class="w-1.5 h-1.5 rounded-full ${status.dot}"></span>${status.label}
          </span>
        </div>
        <p class="text-sm text-red-600">Aucun repas réalisable avec ces contraintes.</p>
      </div>
    `;
  }

  const foodsHtml = meal.foods.map(f => {
    const cat = guessCategory(f.nom);
    const style = CATEGORY_STYLES[cat] || CATEGORY_STYLES.autre;
    return `
      <li class="flex items-center justify-between gap-3 py-1.5">
        <div class="flex items-center gap-2 min-w-0 flex-1">
          <span class="inline-flex items-center justify-center w-6 h-6 rounded-md ${style.bg} ${style.text} text-[10px] flex-shrink-0">${style.icon}</span>
          <span class="text-sm text-stone-700 truncate" title="${escapeHtml(f.nom)}">${escapeHtml(f.nom)}</span>
        </div>
        <span class="text-xs font-mono font-medium text-stone-500 flex-shrink-0">${f.qty_g} g</span>
      </li>
    `;
  }).join("");

  return `
    <div class="px-5 py-4">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-2">
          <span class="font-semibold text-stone-800">${label}</span>
          <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium ${status.bg} ${status.text}">
            <span class="w-1.5 h-1.5 rounded-full ${status.dot}"></span>${status.label}
          </span>
        </div>
        <span class="text-sm font-semibold text-stone-700">${meal.cost.toFixed(2)} €</span>
      </div>
      <ul class="space-y-0.5">${foodsHtml}</ul>
    </div>
  `;
}

function guessCategory(name) {
  const f = state.foods.find(x => x.nom === name);
  return f ? f.categorie : "autre";
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

init();
