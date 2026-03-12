const express = require('express');
const Database = require('better-sqlite3');
const cors = require('cors');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;
const DB_PATH = process.env.DB_PATH || path.join(__dirname, '../data/recipes.db');
const PUBLIC_DIR = fs.existsSync(path.join(__dirname, '../public'))
  ? path.join(__dirname, '../public')
  : path.join(__dirname, 'public');

app.use(cors());
app.use(express.json());
app.use(express.static(PUBLIC_DIR));

// ─── 初始化数据库 ──────────────────────────────────────────────────────────────

const db = new Database(DB_PATH);

db.exec(`
  CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    method TEXT NOT NULL,
    desc TEXT,
    ingredients TEXT,
    steps TEXT,
    notes TEXT
  );

  CREATE TABLE IF NOT EXISTS ingredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    owned INTEGER NOT NULL DEFAULT 0
  );

  CREATE TABLE IF NOT EXISTS extra_categories (
    name TEXT PRIMARY KEY
  );
`);

// 检查是否需要写入默认数据
const recipeCount = db.prepare('SELECT COUNT(*) as c FROM recipes').get().c;
if (recipeCount === 0) {
  const defaultData = JSON.parse(fs.readFileSync(path.join(__dirname, 'defaults.json'), 'utf-8'));

  const insertRecipe = db.prepare(`
    INSERT INTO recipes (id, title, method, desc, ingredients, steps, notes)
    VALUES (@id, @title, @method, @desc, @ingredients, @steps, @notes)
  `);
  for (const r of defaultData.recipes) {
    insertRecipe.run({
      ...r,
      ingredients: JSON.stringify(r.ingredients),
      steps: JSON.stringify(r.steps),
    });
  }

  const insertIng = db.prepare(`
    INSERT OR IGNORE INTO ingredients (name, category, owned)
    VALUES (@name, @category, @owned)
  `);
  for (const i of defaultData.ingredients) {
    insertIng.run({ ...i, owned: i.owned ? 1 : 0 });
  }
}

// ─── 辅助函数 ─────────────────────────────────────────────────────────────────

function parseRecipe(row) {
  return {
    ...row,
    ingredients: JSON.parse(row.ingredients || '[]'),
    steps: JSON.parse(row.steps || '[]'),
  };
}

// ─── 认证中间件 ───────────────────────────────────────────────────────────────

// 密码通过环境变量 RECIPE_PASSWORD 设置，默认值需在部署时修改
const RECIPE_PASSWORD = process.env.RECIPE_PASSWORD || 'changeme';

function requireAuth(req, res, next) {
  const auth = req.headers['x-recipe-password'];
  if (auth === RECIPE_PASSWORD) return next();
  res.status(401).json({ error: '密码错误' });
}

// ─── 菜谱 API ─────────────────────────────────────────────────────────────────

// 获取所有菜谱
app.get('/api/recipes', (req, res) => {
  const rows = db.prepare('SELECT * FROM recipes ORDER BY id').all();
  res.json(rows.map(parseRecipe));
});

// 新建菜谱
app.post('/api/recipes', requireAuth, (req, res) => {
  const { title, method, desc, ingredients, steps, notes } = req.body;
  const id = Date.now();
  db.prepare(`
    INSERT INTO recipes (id, title, method, desc, ingredients, steps, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `).run(id, title, method, desc || '', JSON.stringify(ingredients || []), JSON.stringify(steps || []), notes || '');
  res.json({ id });
});

// 更新菜谱
app.put('/api/recipes/:id', requireAuth, (req, res) => {
  const { title, method, desc, ingredients, steps, notes } = req.body;
  db.prepare(`
    UPDATE recipes SET title=?, method=?, desc=?, ingredients=?, steps=?, notes=? WHERE id=?
  `).run(title, method, desc || '', JSON.stringify(ingredients || []), JSON.stringify(steps || []), notes || '', req.params.id);
  res.json({ ok: true });
});

// 删除菜谱
app.delete('/api/recipes/:id', requireAuth, (req, res) => {
  db.prepare('DELETE FROM recipes WHERE id=?').run(req.params.id);
  res.json({ ok: true });
});

// ─── 食材 API ─────────────────────────────────────────────────────────────────

// 获取所有食材
app.get('/api/ingredients', (req, res) => {
  const rows = db.prepare('SELECT * FROM ingredients ORDER BY category, name').all();
  const cats = db.prepare('SELECT name FROM extra_categories').all().map(r => r.name);
  res.json({
    ingredients: rows.map(r => ({ ...r, owned: r.owned === 1 })),
    extraCategories: cats
  });
});

// 新增食材
app.post('/api/ingredients', requireAuth, (req, res) => {
  const { name, category, owned } = req.body;
  try {
    db.prepare('INSERT INTO ingredients (name, category, owned) VALUES (?, ?, ?)').run(name, category, owned ? 1 : 0);
    res.json({ ok: true });
  } catch (e) {
    res.status(400).json({ error: '食材已存在' });
  }
});

// 更新食材 owned 状态（批量）
app.put('/api/ingredients/owned', requireAuth, (req, res) => {
  const { updates } = req.body; // [{ name, owned }]
  const update = db.prepare('UPDATE ingredients SET owned=? WHERE name=?');
  const tx = db.transaction(() => {
    for (const u of updates) update.run(u.owned ? 1 : 0, u.name);
  });
  tx();
  res.json({ ok: true });
});

// 删除食材
app.delete('/api/ingredients/:name', requireAuth, (req, res) => {
  db.prepare('DELETE FROM ingredients WHERE name=?').run(decodeURIComponent(req.params.name));
  res.json({ ok: true });
});

// 删除整个分类
app.delete('/api/ingredients/category/:cat', requireAuth, (req, res) => {
  const cat = decodeURIComponent(req.params.cat);
  db.prepare('DELETE FROM ingredients WHERE category=?').run(cat);
  db.prepare('DELETE FROM extra_categories WHERE name=?').run(cat);
  res.json({ ok: true });
});

// 重命名分类
app.put('/api/ingredients/category/rename', requireAuth, (req, res) => {
  const { oldName, newName } = req.body;
  db.prepare('UPDATE ingredients SET category=? WHERE category=?').run(newName, oldName);
  db.prepare('UPDATE extra_categories SET name=? WHERE name=?').run(newName, oldName);
  res.json({ ok: true });
});

// 新增空分类
app.post('/api/ingredients/category', requireAuth, (req, res) => {
  const { name } = req.body;
  try {
    db.prepare('INSERT OR IGNORE INTO extra_categories (name) VALUES (?)').run(name);
    res.json({ ok: true });
  } catch(e) {
    res.status(400).json({ error: '分类已存在' });
  }
});

// ─── 启动 ─────────────────────────────────────────────────────────────────────

app.listen(PORT, () => {
  console.log(`食谱应用已启动：http://localhost:${PORT}`);
});
