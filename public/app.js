// ─── 密码管理 ─────────────────────────────────────────────────────────────────

// 会话内记住密码，不用每次都输
let sessionPassword = sessionStorage.getItem("recipe_pw") || "";

// 支持多个并发写请求等待同一次密码输入
let pwWaiters = [];
let pwOverlayOpen = false;

function queuePasswordWaiter(resolve, reject) {
  pwWaiters.push({ resolve, reject });
}

function resolvePasswordWaiters(pw) {
  const waiters = pwWaiters;
  pwWaiters = [];
  waiters.forEach((w) => w.resolve(pw));
}

function rejectPasswordWaiters(err) {
  const waiters = pwWaiters;
  pwWaiters = [];
  waiters.forEach((w) => w.reject(err));
}

function requirePassword() {
  // 如果已有密码，直接用
  if (sessionPassword) return Promise.resolve(sessionPassword);

  // 否则弹窗（若已打开，直接复用同一轮输入）
  return new Promise((resolve, reject) => {
    queuePasswordWaiter(resolve, reject);
    if (!pwOverlayOpen) {
      pwOverlayOpen = true;
      const overlay = document.getElementById("pwOverlay");
      const input = document.getElementById("pwInput");
      input.value = "";
      input.classList.remove("error");
      overlay.classList.add("open");
      setTimeout(() => input.focus(), 50);
    }
  });
}

function pwConfirm() {
  const input = document.getElementById("pwInput");
  const pw = input.value;
  if (!pw) return;
  document.getElementById("pwOverlay").classList.remove("open");
  pwOverlayOpen = false;
  resolvePasswordWaiters(pw);
}

function pwCancel() {
  document.getElementById("pwOverlay").classList.remove("open");
  pwOverlayOpen = false;
  rejectPasswordWaiters(new Error("cancelled"));
}

function pwWrongPassword() {
  // 密码错误：清除记忆，提示用户
  sessionPassword = "";
  sessionStorage.removeItem("recipe_pw");
  const overlay = document.getElementById("pwOverlay");
  const input = document.getElementById("pwInput");
  input.value = "";
  input.classList.add("error");
  setTimeout(() => input.classList.remove("error"), 600);
  overlay.classList.add("open");
  pwOverlayOpen = true;
  setTimeout(() => input.focus(), 50);

  // 重新等待用户输入
  return new Promise((resolve, reject) => queuePasswordWaiter(resolve, reject));
}

async function readJsonSafe(res) {
  const text = await res.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch (_) {
    return { raw: text };
  }
}

// ─── API ──────────────────────────────────────────────────────────────────────

async function api(method, path, body) {
  const opts = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch("/api" + path, opts);
  if (!res.ok) throw new Error(await res.text());
  return readJsonSafe(res);
}

// 需要密码的 API 调用，自动处理弹窗和重试
async function apiAuth(method, path, body) {
  let pw;
  try {
    pw = await requirePassword();
  } catch (e) {
    throw new Error("cancelled");
  }

  const opts = {
    method,
    headers: {
      "Content-Type": "application/json",
      "x-recipe-password": pw,
    },
  };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch("/api" + path, opts);

  if (res.status === 401) {
    // 密码错误，重试
    try {
      pw = await pwWrongPassword();
    } catch (e) {
      throw new Error("cancelled");
    }
    // 用新密码再试一次
    const opts2 = {
      method,
      headers: {
        "Content-Type": "application/json",
        "x-recipe-password": pw,
      },
    };
    if (body !== undefined) opts2.body = JSON.stringify(body);
    const res2 = await fetch("/api" + path, opts2);
    if (res2.status === 401) {
      sessionPassword = "";
      sessionStorage.removeItem("recipe_pw");
      throw new Error("密码错误");
    }
    // 密码正确，记住它
    sessionPassword = pw;
    sessionStorage.setItem("recipe_pw", pw);
    if (!res2.ok) throw new Error(await res2.text());
    return readJsonSafe(res2);
  }

  // 密码正确，记住它
  sessionPassword = pw;
  sessionStorage.setItem("recipe_pw", pw);
  if (!res.ok) throw new Error(await res.text());
  return readJsonSafe(res);
}

function showStatus(type, text) {
  const el = document.getElementById("saveStatus");
  el.className = type;
  el.textContent = text;
  if (type === "saved")
    setTimeout(() => {
      el.style.opacity = 0;
    }, 2000);
}

// ─── STATE ────────────────────────────────────────────────────────────────────

let state = {
  ingredients: [],
  extraCategories: [],
  recipes: [],
  filter: "all",
  matchOwned: false,
};

async function loadAll() {
  const [recipesData, ingsData] = await Promise.all([
    api("GET", "/recipes"),
    api("GET", "/ingredients"),
  ]);
  state.recipes = recipesData;
  state.ingredients = ingsData.ingredients;
  state.extraCategories = ingsData.extraCategories;
}

// ─── HELPERS ─────────────────────────────────────────────────────────────────

function getOwnedNames() {
  return new Set(state.ingredients.filter((i) => i.owned).map((i) => i.name));
}

function getMatchInfo(recipe) {
  const owned = getOwnedNames();
  const required = recipe.ingredients.filter((i) => i.required);
  const optional = recipe.ingredients.filter((i) => !i.required);

  const total = recipe.ingredients.length;
  const haveRequired = required.filter((i) => owned.has(i.name)).length;
  const haveOptional = optional.filter((i) => owned.has(i.name)).length;
  const have = haveRequired + haveOptional;
  const totalRequired = required.length;
  return {
    have,
    total,
    haveRequired,
    totalRequired,
    haveOptional,
    full: have === total, // 全部齐全
    hasRequired: haveRequired === totalRequired, // 必要齐全
  };
}

function methodLabel(m) {
  if (m === "boil") return { text: "🫕 水煮", cls: "method-boil" };
  if (m === "oven") return { text: "🔥 烤箱", cls: "method-oven" };
  if (m === "air") return { text: "💨 空气炸锅", cls: "method-air" };
  if (m === "fry") return { text: "🍳 炒菜", cls: "method-fry" };
  return { text: "🥄 其它", cls: "method-other" };
}

function escHtml(s) {
  return String(s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ─── VIEWS ────────────────────────────────────────────────────────────────────

function switchView(view, btn) {
  document
    .querySelectorAll(".view")
    .forEach((v) => v.classList.remove("active"));
  document
    .querySelectorAll(".tab-btn")
    .forEach((b) => b.classList.remove("active"));
  document.getElementById("view-" + view).classList.add("active");
  if (btn) btn.classList.add("active");
  if (view === "ingredients") renderIngredients();
  if (view === "manage") renderManage();
}

function setFilter(f) {
  state.filter = f;
  document.querySelectorAll(".filter-chip").forEach((c) => {
    c.classList.toggle("active", c.dataset.filter === f);
  });
  renderRecipes();
}

function toggleMatchFilter() {
  state.matchOwned = !state.matchOwned;
  document
    .getElementById("matchToggle")
    .classList.toggle("on", state.matchOwned);
  renderRecipes();
}

// ─── RECIPES ─────────────────────────────────────────────────────────────────

function renderRecipes() {
  const query = document
    .getElementById("searchInput")
    .value.trim()
    .toLowerCase();
  const owned = getOwnedNames();

  let filtered = state.recipes.filter((r) => {
    if (state.filter !== "all" && r.method !== state.filter) return false;
    if (
      query &&
      !r.title.includes(query) &&
      !r.ingredients
        .map((i) => i.name)
        .join("")
        .includes(query)
    )
      return false;
    if (state.matchOwned) return getMatchInfo(r).hasRequired;
    return true;
  });

  filtered.sort((a, b) => {
    const am = getMatchInfo(a),
      bm = getMatchInfo(b);
    if (am.full && !bm.full) return -1;
    if (!am.full && bm.full) return 1;
    return bm.have / (bm.total || 1) - am.have / (am.total || 1);
  });

  document.getElementById("resultsCount").innerHTML =
    `共 <strong>${filtered.length}</strong> 个菜谱` +
    (state.matchOwned ? `（仅显示必要食材齐全的）` : "");

  const grid = document.getElementById("recipeGrid");
  if (filtered.length === 0) {
    grid.innerHTML = `<div class="no-results" style="grid-column:1/-1">
      <span class="emoji">🥣</span>没有找到匹配的菜谱<br>
      <span style="font-size:13px">试试调整筛选条件，或新建一个菜谱</span></div>`;
    return;
  }

  grid.innerHTML = filtered
    .map((r) => {
      const ml = methodLabel(r.method);
      const {
        have,
        total,
        haveRequired,
        totalRequired,
        haveOptional,
        full,
        hasRequired,
      } = getMatchInfo(r);

      const badge1 = full
        ? `<div class="match-badge">✓ 食材齐全</div>`
        : hasRequired
          ? `<div class="match-badge partial">✓ 必要齐全</div>`
          : `<div class="match-badge missing">✗ 必要不完整 ${haveRequired}/${totalRequired}</div>`;

      const badge2 = full
        ? ``
        : `<div class="match-badge partial">拥有 ${have}/${total}</div>`;

      const badge = `<div class="card-match-badges">${badge1}${badge2}</div>`;

      const ings = r.ingredients
        .map(
          (i) =>
            `<span class="ing-tag ${owned.has(i.name) ? "" : "missing"}">${escHtml(i.name)}</span>`,
        )
        .join("");
      return `<div class="recipe-card ${full ? "" : "missing-some"}" onclick="openRecipe(${r.id})">
      <div class="card-top-row">
        <div class="card-method ${ml.cls}">${ml.text}</div>
        ${badge}
      </div>
      <div class="card-title">${escHtml(r.title)}</div>
      <div class="card-desc">${escHtml(r.desc)}</div>
      <div class="card-ingredients">${ings}</div>
    </div>`;
    })
    .join("");
}

// ─── RECIPE MODAL ─────────────────────────────────────────────────────────────

function openRecipe(id) {
  const r = state.recipes.find((x) => x.id === id);
  if (!r) return;
  renderModal(r, false);
  document.getElementById("modalOverlay").classList.add("open");
}

async function openNewRecipe() {
  showStatus("saving", "创建中...");
  try {
    const { id } = await apiAuth("POST", "/recipes", {
      title: "新菜谱",
      method: "boil",
      desc: "",
      ingredients: [],
      steps: [],
      notes: "",
    });
    const newR = {
      id,
      title: "新菜谱",
      method: "boil",
      desc: "",
      ingredients: [],
      steps: [],
      notes: "",
    };
    state.recipes.push(newR);
    showStatus("saved", "已保存");
    renderModal(newR, true);
    document.getElementById("modalOverlay").classList.add("open");
    renderRecipes();
  } catch (e) {
    if (e.message !== "cancelled") showStatus("error", "创建失败");
    else showStatus("", "");
  }
}

function renderModal(r, editMode) {
  const owned = getOwnedNames();
  const ml = methodLabel(r.method);

  if (editMode) {
    const requiredIngs = r.ingredients
      .filter((i) => i.required)
      .map((i) => i.name)
      .join("\n");
    const optionalIngs = r.ingredients
      .filter((i) => !i.required)
      .map((i) => i.name)
      .join("\n");
    document.getElementById("modalContent").innerHTML = `
      <label class="edit-label">菜名</label>
      <input class="edit-field" id="edit-title" value="${escHtml(r.title)}">
      <label class="edit-label">烹饪方式</label>
      <select class="edit-field" id="edit-method">
        <option value="boil"  ${r.method === "boil" ? "selected" : ""}>🫕 水煮</option>
        <option value="oven"  ${r.method === "oven" ? "selected" : ""}>🔥 烤箱</option>
        <option value="air"   ${r.method === "air" ? "selected" : ""}>💨 空气炸锅</option>
        <option value="fry"   ${r.method === "fry" ? "selected" : ""}>🍳 炒菜</option>
        <option value="other" ${r.method === "other" ? "selected" : ""}>🥄 其它</option>
      </select>
      <label class="edit-label">简介</label>
      <textarea class="edit-field" id="edit-desc">${escHtml(r.desc)}</textarea>
      <label class="edit-label">食材</label>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">
        <div>
          <label class="edit-label">必要</label>
          <textarea class="edit-field" id="edit-ingredients-required" style="min-height:100px">${requiredIngs}</textarea>
        </div>
        <div>
          <label class="edit-label">可选</label>
          <textarea class="edit-field" id="edit-ingredients-optional" style="min-height:100px">${optionalIngs}</textarea>
        </div>
      </div>
      <label class="edit-label">步骤（每行一步）</label>
      <textarea class="edit-field" id="edit-steps" style="min-height:120px">${r.steps.join("\n")}</textarea>
      <label class="edit-label">小贴士（可选）</label>
      <textarea class="edit-field" id="edit-notes">${escHtml(r.notes || "")}</textarea>
      <div class="modal-actions">
        <button class="modal-delete-btn" data-action="delete-recipe" data-id="${r.id}">删除</button>
        <button class="modal-edit-btn" onclick="renderModal(state.recipes.find(x=>x.id===${r.id}), false)">取消</button>
        <button class="modal-save-btn" onclick="saveRecipe(${r.id})">保存</button>
      </div>`;
  } else {
    const steps = (r.steps || [])
      .map(
        (s, i) =>
          `<div class="step-item"><div class="step-num">${i + 1}</div><div class="step-text">${escHtml(s)}</div></div>`,
      )
      .join("");

    const req_ings = (
      r.ingredients.filter((i) => i.required).map((i) => i.name) || []
    )
      .map(
        (i) =>
          `<span class="modal-ing ${owned.has(i) ? "" : "missing"}">${escHtml(i)}</span>`,
      )
      .join("");
    const opt_ings = (
      r.ingredients.filter((i) => !i.required).map((i) => i.name) || []
    )
      .map(
        (i) =>
          `<span class="modal-ing ${owned.has(i) ? "" : "missing"}">${escHtml(i)}</span>`,
      )
      .join("");
    const notes = r.notes
      ? `<div class="modal-notes">💡 ${escHtml(r.notes)}</div>`
      : "";
    document.getElementById("modalContent").innerHTML = `
      <div class="modal-method"><span class="card-method ${ml.cls}">${ml.text}</span></div>
      <div class="modal-title">${escHtml(r.title)}</div>
      <div class="modal-desc">${escHtml(r.desc)}</div>
      <div class="modal-section-title">必要食材</div>
      <div class="modal-ingredients">${req_ings}</div>
      <div class="modal-section-title">可选食材</div>
      <div class="modal-ingredients">${opt_ings}</div>
      <div class="modal-section-title">步骤</div>
      <div class="modal-steps">${steps}</div>
      ${notes}
      <div class="modal-actions">
        <button class="modal-delete-btn" data-action="delete-recipe" data-id="${r.id}">删除</button>
        <button class="modal-edit-btn" onclick="renderModal(state.recipes.find(x=>x.id===${r.id}), true)">编辑</button>
      </div>`;
  }
}

async function saveRecipe(id) {
  const r = state.recipes.find((x) => x.id === id);
  const updated = {
    title: document.getElementById("edit-title").value.trim() || "未命名菜谱",
    method: document.getElementById("edit-method").value,
    desc: document.getElementById("edit-desc").value.trim(),
    ingredients: [
      ...document
        .getElementById("edit-ingredients-required")
        .value.split("\n")
        .map((s) => s.trim())
        .filter(Boolean)
        .map((s) => ({ name: s, required: true })),
      ...document
        .getElementById("edit-ingredients-optional")
        .value.split("\n")
        .map((s) => s.trim())
        .filter(Boolean)
        .map((s) => ({ name: s, required: false })),
    ],
    steps: document
      .getElementById("edit-steps")
      .value.split("\n")
      .map((s) => s.trim())
      .filter(Boolean),
    notes: document.getElementById("edit-notes").value.trim(),
  };
  showStatus("saving", "保存中...");
  try {
    await apiAuth("PUT", `/recipes/${id}`, updated);
    Object.assign(r, updated);
    showStatus("saved", "已保存");
    renderModal(r, false);
    renderRecipes();
  } catch (e) {
    if (e.message !== "cancelled") showStatus("error", "保存失败");
    else showStatus("", "");
  }
}

async function deleteRecipe(id) {
  showStatus("saving", "删除中...");
  try {
    await apiAuth("DELETE", `/recipes/${id}`);
    state.recipes = state.recipes.filter((r) => r.id !== id);
    showStatus("saved", "已删除");
    closeModal();
    renderRecipes();
  } catch (e) {
    if (e.message !== "cancelled") showStatus("error", "删除失败");
    else showStatus("", "");
  }
}

function closeModal() {
  document.getElementById("modalOverlay").classList.remove("open");
}
function closeModalOnOverlay(e) {
  if (e.target === document.getElementById("modalOverlay")) closeModal();
}

// ─── INGREDIENTS ─────────────────────────────────────────────────────────────

function renderIngredients() {
  const categories = [...new Set(state.ingredients.map((i) => i.category))];
  const owned = state.ingredients.filter((i) => i.owned);
  document.getElementById("ownedCount").textContent = owned.length;

  let html = "";
  categories.forEach((cat) => {
    const items = state.ingredients.filter((i) => i.category === cat);
    html += `<div style="margin-bottom:20px;">
      <div style="font-family:'Noto Serif SC',serif; font-size:14px; font-weight:600; color:var(--accent); letter-spacing:1px; margin-bottom:10px; padding-bottom:6px; border-bottom:1px solid var(--border);">${escHtml(cat)}</div>
      <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(140px, 1fr)); gap:6px;">
        ${items
          .map(
            (ing) => `
          <label style="display:flex; align-items:center; gap:8px; padding:8px 10px; background:var(--paper); border:1.5px solid ${ing.owned ? "var(--accent-light)" : "var(--border)"}; border-radius:5px; cursor:pointer; transition:border-color 0.15s;">
            <input type="checkbox" class="ing-check" ${ing.owned ? "checked" : ""} data-action="toggle-owned" data-name="${escHtml(ing.name)}" style="flex-shrink:0;">
            <span style="font-size:14px;">${escHtml(ing.name)}</span>
          </label>`,
          )
          .join("")}
      </div>
    </div>`;
  });
  document.getElementById("ingredientsCheckList").innerHTML = html;
}

// Debounce owned updates to batch them
let ownedDebounceTimer = null;
let pendingOwnedUpdates = {};

function toggleOwned(name, checked) {
  const ing = state.ingredients.find((i) => i.name === name);
  if (!ing) return;
  ing.owned = checked;
  renderIngredients();
  renderRecipes();

  pendingOwnedUpdates[name] = checked;
  clearTimeout(ownedDebounceTimer);
  showStatus("saving", "保存中...");
  ownedDebounceTimer = setTimeout(async () => {
    const updates = Object.entries(pendingOwnedUpdates).map(
      ([name, owned]) => ({ name, owned }),
    );
    pendingOwnedUpdates = {};
    try {
      await apiAuth("PUT", "/ingredients/owned", { updates });
      showStatus("saved", "已保存");
    } catch (e) {
      if (e.message !== "cancelled") showStatus("error", "保存失败");
      else showStatus("", "");
    }
  }, 800);
}

// ─── MANAGE ──────────────────────────────────────────────────────────────────

function renderManage() {
  const usedCats = [...new Set(state.ingredients.map((i) => i.category))];
  const extra = (state.extraCategories || [])
    .map((c) => c.name)
    .filter((c) => !usedCats.includes(c));
  const categories = [...usedCats, ...extra];

  document.getElementById("manageGrid").innerHTML = categories
    .map((cat) => {
      const items = state.ingredients.filter((i) => i.category === cat);
      const itemsHtml = items
        .map(
          (ing) => `
      <div class="manage-ing-item">
        <span class="manage-ing-name">${escHtml(ing.name)}</span>
        <button class="ing-del-btn" data-action="del-ing" data-name="${escHtml(ing.name)}" title="删除">✕</button>
      </div>`,
        )
        .join("");
      return `<div class="cat-card">
      <div class="cat-header">
        <div class="cat-name-display" data-label-cat="${escHtml(cat)}">
          ${escHtml(cat)} <span class="cat-count">${items.length}</span>
        </div>
        <div class="cat-actions">
          <button class="cat-action-btn" data-action="rename-cat" data-cat="${escHtml(cat)}">改名</button>
          <button class="cat-action-btn danger" data-action="del-cat" data-cat="${escHtml(cat)}">删除</button>
        </div>
      </div>
      <div class="cat-items">${itemsHtml || '<div style="font-size:13px;color:var(--ink-light);padding:8px 4px;">暂无食材</div>'}</div>
      <div class="cat-add-row">
        <input type="text" placeholder="添加食材..." class="cat-ing-input" data-cat="${escHtml(cat)}">
        <button class="cat-add-btn" data-action="add-ing" data-cat="${escHtml(cat)}">添加</button>
      </div>
    </div>`;
    })
    .join("");
}

async function addCategory() {
  const input = document.getElementById("newCatInput");
  const name = input.value.trim();
  if (!name) return;
  const allCats = [
    ...new Set(state.ingredients.map((i) => i.category)),
    ...(state.extraCategories || []),
  ];
  if (allCats.includes(name)) {
    showStatus("error", "分类已存在");
    return;
  }
  showStatus("saving", "保存中...");
  try {
    await apiAuth("POST", "/ingredients/category", { name });
    if (!state.extraCategories) state.extraCategories = [];
    state.extraCategories.push(name);
    input.value = "";
    showStatus("saved", "已保存");
    renderManage();
  } catch (e) {
    if (e.message !== "cancelled") showStatus("error", "添加失败");
    else showStatus("", "");
  }
}

// ─── EVENT DELEGATION ─────────────────────────────────────────────────────────

document.addEventListener("click", async function (e) {
  const btn = e.target.closest("[data-action]");
  if (!btn) return;
  const action = btn.dataset.action;

  if (action === "toggle-owned") {
    // handled by change event below
    return;
  }

  if (action === "delete-recipe") {
    const id = parseInt(btn.dataset.id);
    if (btn.dataset.confirming) {
      await deleteRecipe(id);
    } else {
      btn.dataset.confirming = "1";
      btn.textContent = "确认删除";
      btn.style.cssText =
        "background:#c05050;color:white;border:none;border-radius:3px;padding:4px 12px;cursor:pointer;font-size:13px;margin-right:auto;";
      setTimeout(() => {
        if (btn.dataset.confirming) {
          btn.dataset.confirming = "";
          btn.textContent = "删除";
          btn.style.cssText = "";
        }
      }, 3000);
    }
  }

  if (action === "del-ing") {
    const name = btn.dataset.name;
    if (btn.dataset.confirming) {
      showStatus("saving", "删除中...");
      try {
        await apiAuth("DELETE", `/ingredients/${encodeURIComponent(name)}`);
        state.ingredients = state.ingredients.filter((i) => i.name !== name);
        showStatus("saved", "已删除");
        renderManage();
        renderIngredients();
        renderRecipes();
      } catch (e) {
        if (e.message !== "cancelled") showStatus("error", "删除失败");
        else showStatus("", "");
      }
    } else {
      btn.dataset.confirming = "1";
      btn.textContent = "确认";
      btn.style.cssText =
        "background:#c05050;color:white;border:none;border-radius:3px;padding:2px 8px;cursor:pointer;font-size:12px;";
      setTimeout(() => {
        if (btn.dataset.confirming) {
          btn.dataset.confirming = "";
          btn.textContent = "✕";
          btn.style.cssText = "";
        }
      }, 3000);
    }
  }

  if (action === "add-ing") {
    const cat = btn.dataset.cat;
    const input = btn.closest(".cat-add-row").querySelector(".cat-ing-input");
    const name = input.value.trim();
    if (!name) return;
    if (state.ingredients.find((i) => i.name === name)) {
      input.style.borderColor = "#c05050";
      setTimeout(() => (input.style.borderColor = ""), 1500);
      return;
    }
    showStatus("saving", "保存中...");
    try {
      await apiAuth("POST", "/ingredients", {
        name,
        category: cat,
        owned: false,
      });
      state.ingredients.push({ name, category: cat, owned: false });
      input.value = "";
      showStatus("saved", "已保存");
      renderManage();
      renderRecipes();
    } catch (e) {
      if (e.message !== "cancelled") showStatus("error", "添加失败");
      else showStatus("", "");
    }
  }

  if (action === "del-cat") {
    const cat = btn.dataset.cat;
    if (btn.dataset.confirming) {
      showStatus("saving", "删除中...");
      try {
        await apiAuth(
          "DELETE",
          `/ingredients/category/${encodeURIComponent(cat)}`,
        );
        state.ingredients = state.ingredients.filter((i) => i.category !== cat);
        state.extraCategories = (state.extraCategories || []).filter(
          (c) => c !== cat,
        );
        showStatus("saved", "已删除");
        renderManage();
        renderIngredients();
        renderRecipes();
      } catch (e) {
        if (e.message !== "cancelled") showStatus("error", "删除失败");
        else showStatus("", "");
      }
    } else {
      btn.dataset.confirming = "1";
      btn.textContent = "确认删除分类";
      btn.style.cssText =
        "background:#c05050;color:white;border:none;border-radius:3px;padding:3px 8px;cursor:pointer;font-size:12px;";
      setTimeout(() => {
        if (btn.dataset.confirming) {
          btn.dataset.confirming = "";
          btn.textContent = "删除";
          btn.style.cssText = "";
        }
      }, 3000);
    }
  }

  if (action === "rename-cat") {
    const cat = btn.dataset.cat;
    const allLabels = document.querySelectorAll("[data-label-cat]");
    let targetLabel = null;
    allLabels.forEach((el) => {
      if (el.dataset.labelCat === cat) targetLabel = el;
    });
    if (!targetLabel) return;
    targetLabel.innerHTML = `<input class="cat-rename-input" data-rename-for="${escHtml(cat)}" value="${escHtml(cat)}">`;
    const inp = targetLabel.querySelector("input");
    inp.focus();
    inp.select();
    inp.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") {
        ev.preventDefault();
        finishRenameCategory(inp);
      }
      if (ev.key === "Escape") renderManage();
    });
    inp.addEventListener("blur", () => finishRenameCategory(inp));
  }
});

// Checkbox change via delegation
document.addEventListener("change", function (e) {
  const el = e.target;
  if (el.dataset.action === "toggle-owned") {
    toggleOwned(el.dataset.name, el.checked);
  }
});

// Enter key in cat-ing-input
document.addEventListener("keydown", function (e) {
  if (e.key !== "Enter" || !e.target.classList.contains("cat-ing-input"))
    return;
  const fakeBtn = {
    dataset: { cat: e.target.dataset.cat },
    closest: () => e.target.closest(".cat-add-row"),
  };
  e.target.closest(".cat-add-row").querySelector(".cat-add-btn").click();
});

async function finishRenameCategory(inp) {
  const oldCat = inp.dataset.renameFor;
  const newCat = inp.value.trim();
  if (!oldCat) return;
  inp.dataset.renameFor = "";
  if (!newCat || newCat === oldCat) {
    renderManage();
    return;
  }
  showStatus("saving", "保存中...");
  try {
    await apiAuth("PUT", "/ingredients/category/rename", {
      oldName: oldCat,
      newName: newCat,
    });
    state.ingredients.forEach((i) => {
      if (i.category === oldCat) i.category = newCat;
    });
    state.extraCategories = (state.extraCategories || []).map((c) =>
      c === oldCat ? newCat : c,
    );
    showStatus("saved", "已保存");
    renderManage();
  } catch (e) {
    if (e.message !== "cancelled") showStatus("error", "重命名失败");
    else showStatus("", "");
    renderManage();
  }
}

// ─── INIT ─────────────────────────────────────────────────────────────────────

(async () => {
  try {
    await loadAll();
    document.getElementById("loadingOverlay").classList.add("hidden");
    renderRecipes();
  } catch (e) {
    document.getElementById("loadingOverlay").innerHTML =
      `<div style="color:#c05050; text-align:center; padding:40px">
        <div style="font-size:32px; margin-bottom:16px">⚠️</div>
        <div style="font-size:16px; font-weight:600; margin-bottom:8px">无法连接到服务器</div>
        <div style="font-size:13px; color:#999">请确认后端服务已启动</div>
      </div>`;
  }
})();

// Fetch the version
fetch("/api/version")
  .then((r) => r.json())
  .then((d) => (document.getElementById("version").textContent = d.version));
