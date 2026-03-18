import os
import json
import sqlite3
from datetime import date
from pathlib import Path
from time import time_ns
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.staticfiles import StaticFiles
from routers import changelog

load_dotenv()
app = FastAPI()
app.include_router(changelog.router)


## Configurations
PORT = int(os.getenv("PORT", 3000))
DB_PATH = os.getenv("DB_PATH", Path(__file__).parent.parent / "data" / "recipes.db")
RECIPE_PASSWORD = os.getenv("RECIPE_PASSWORD", "changeme")


def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            method TEXT NOT NULL,
            desc TEXT,
            ingredients TEXT,
            steps TEXT,
            notes TEXT
    );

    CREATE TABLE IF NOT EXISTS houses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
                 """)

    # ingredients 旧表迁移：从 UNIQUE(name) 升级为 UNIQUE(name, house_id)
    ingredient_cols = [
        r["name"] for r in conn.execute("PRAGMA table_info(ingredients)").fetchall()
    ]
    if not ingredient_cols:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ingredients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                owned INTEGER NOT NULL DEFAULT 0,
                stock_date TEXT,
                expiry_date TEXT,
                house_id INTEGER NOT NULL DEFAULT 1,
                UNIQUE(name, house_id)
            )
            """
        )
    elif "house_id" not in ingredient_cols:
        conn.executescript(
            """
            ALTER TABLE ingredients RENAME TO ingredients_old;
            CREATE TABLE ingredients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                owned INTEGER NOT NULL DEFAULT 0,
                stock_date TEXT,
                expiry_date TEXT,
                house_id INTEGER NOT NULL DEFAULT 1,
                UNIQUE(name, house_id)
            );
            INSERT OR IGNORE INTO ingredients (name, category, owned, house_id)
            SELECT name, category, owned, 1 FROM ingredients_old;
            DROP TABLE ingredients_old;
            """
        )

    # ingredients 新字段迁移：入库日期、过期日期
    ingredient_cols = [
        r["name"] for r in conn.execute("PRAGMA table_info(ingredients)").fetchall()
    ]
    if "stock_date" not in ingredient_cols:
        conn.execute("ALTER TABLE ingredients ADD COLUMN stock_date TEXT")
    if "expiry_date" not in ingredient_cols:
        conn.execute("ALTER TABLE ingredients ADD COLUMN expiry_date TEXT")

    # extra_categories 迁移为按 house_id 隔离
    extra_cols = [
        r["name"]
        for r in conn.execute("PRAGMA table_info(extra_categories)").fetchall()
    ]
    if not extra_cols:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS extra_categories (
                name TEXT NOT NULL,
                house_id INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (name, house_id)
            )
            """
        )
    elif "house_id" not in extra_cols:
        conn.executescript(
            """
            ALTER TABLE extra_categories RENAME TO extra_categories_old;
            CREATE TABLE extra_categories (
                name TEXT NOT NULL,
                house_id INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (name, house_id)
            );
            INSERT OR IGNORE INTO extra_categories (name, house_id)
            SELECT name, 1 FROM extra_categories_old;
            DROP TABLE extra_categories_old;
            """
        )

    # 创建默认家（如果不存在）
    default_house_count = conn.execute(
        "SELECT COUNT(*) FROM houses WHERE id=1"
    ).fetchone()[0]
    if default_house_count == 0:
        conn.execute("INSERT INTO houses (id, name) VALUES (1, '默认家')")
        conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]
    print(count)
    if count == 0:  # write default data
        path = Path(__file__).parent / "defaults.json"
        data = json.loads(path.read_text())
        for r in data["recipes"]:
            conn.execute(
                "INSERT INTO recipes (id, title, method, desc, ingredients, steps, notes) VALUES (?,?,?,?,?,?,?)",
                (
                    r["id"],
                    r["title"],
                    r["method"],
                    r.get("desc", ""),
                    json.dumps(r.get("ingredients", []), ensure_ascii=False),
                    json.dumps(r.get("steps", []), ensure_ascii=False),
                    r.get("notes", ""),
                ),
            )

        for i in data["ingredients"]:
            conn.execute(
                "INSERT INTO ingredients (name, category, owned, house_id) VALUES (?,?,?,?)",
                (i["name"], i["category"], (1 if i["owned"] else 0), 1),
            )

    # 迁移旧数据：recipes 格式
    rows = conn.execute("SELECT id, ingredients FROM recipes").fetchall()
    for row in rows:
        ingredients = json.loads(row["ingredients"] or "[]")
        if ingredients and isinstance(ingredients[0], str):
            # 旧格式，需要迁移
            new_ingredients = [{"name": i, "required": False} for i in ingredients]
            conn.execute(
                "UPDATE recipes SET ingredients=? WHERE id=?",
                [json.dumps(new_ingredients, ensure_ascii=False), row["id"]],
            )

    conn.execute("UPDATE ingredients SET house_id=1 WHERE house_id IS NULL")

    conn.commit()
    conn.close()


# Initialize
init_db()


# Help Function
def parse_recipe(row):
    r = dict(row)
    r["ingredients"] = json.loads(r.get("ingredients") or "[]")
    r["steps"] = json.loads(r.get("steps") or "[]")
    return r


def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)  # 1. 建立连接
    conn.row_factory = sqlite3.Row
    try:
        yield conn  # 2. 把连接交给路由函数使用，暂停
        # 请求处理中...
    finally:
        conn.close()  # 3. 请求处理完，继续执行，关闭连接


class RecipeBody(BaseModel):
    title: str
    method: str
    desc: str = ""
    ingredients: list = []
    steps: list = []
    notes: str = ""


class IngredientBody(BaseModel):
    name: str
    category: str
    owned: bool = False
    stock_date: Optional[str] = None
    expiry_date: Optional[str] = None
    house_id: int = 1


class OwnedUpdate(BaseModel):
    name: str
    owned: bool


class OwnedBatch(BaseModel):
    updates: list[OwnedUpdate]
    house_id: int = 1


class IngredientStockBody(BaseModel):
    name: str
    owned: bool
    stock_date: Optional[str] = None
    expiry_date: Optional[str] = None
    house_id: int = 1


class CategoryRename(BaseModel):
    oldName: str
    newName: str
    house_id: int = 1


class CategoryBody(BaseModel):
    name: str
    house_id: int = 1


class HouseBody(BaseModel):
    name: str


class HouseScopeBody(BaseModel):
    house_id: int = 1


# Authentication Function
def require_auth(x_recipe_password: str = Header(default="")):
    if x_recipe_password != RECIPE_PASSWORD:
        raise HTTPException(status_code=401, detail="密码错误?")


def normalize_date(date_str: Optional[str], field_label: str) -> Optional[str]:
    if date_str is None:
        return None
    normalized = date_str.strip()
    if not normalized:
        return None
    try:
        date.fromisoformat(normalized)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field_label}格式应为 YYYY-MM-DD")
    return normalized


# Routes of houses
## 1. Get all houses
@app.get("/api/houses")
def get_houses(db=Depends(get_db)):
    rows = db.execute("SELECT id, name, created_at FROM houses ORDER BY id").fetchall()
    return [dict(row) for row in rows]


## 2. Create new house
@app.post("/api/houses", dependencies=[Depends(require_auth)])
def create_house(body: HouseBody, db=Depends(get_db)):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="家名不能为空")
    try:
        db.execute("INSERT INTO houses (name) VALUES (?)", [name])
        db.commit()
        # 获取新创建的家的 ID
        new_house = db.execute(
            "SELECT id, name, created_at FROM houses WHERE name=?", [name]
        ).fetchone()
        return dict(new_house)
    except Exception:
        raise HTTPException(status_code=409, detail="家已存在")


## 3. Rename house
@app.put("/api/houses/{house_id}", dependencies=[Depends(require_auth)])
def rename_house(house_id: int, body: HouseBody, db=Depends(get_db)):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="家名不能为空")

    house = db.execute("SELECT id FROM houses WHERE id=?", [house_id]).fetchone()
    if not house:
        raise HTTPException(status_code=404, detail="家不存在")

    try:
        db.execute("UPDATE houses SET name=? WHERE id=?", [name, house_id])
        db.commit()
        updated = db.execute(
            "SELECT id, name, created_at FROM houses WHERE id=?", [house_id]
        ).fetchone()
        return dict(updated)
    except Exception:
        raise HTTPException(status_code=409, detail="家已存在")


## 4. Delete house
@app.delete("/api/houses/{house_id}", dependencies=[Depends(require_auth)])
def delete_house(house_id: int, db=Depends(get_db)):
    # 检查是否至少有一个家
    house_count = db.execute("SELECT COUNT(*) FROM houses").fetchone()[0]
    if house_count <= 1:
        raise HTTPException(status_code=400, detail="至少需要一个家")

    # 检查家是否存在
    house = db.execute("SELECT id FROM houses WHERE id=?", [house_id]).fetchone()
    if not house:
        raise HTTPException(status_code=404, detail="家不存在")

    # 删除家及其食材与分类
    db.execute("DELETE FROM ingredients WHERE house_id=?", [house_id])
    db.execute("DELETE FROM extra_categories WHERE house_id=?", [house_id])
    db.execute("DELETE FROM houses WHERE id=?", [house_id])
    db.commit()
    return {"ok": True}


# Routes of recipes


## 1. Read all recipes
@app.get("/api/recipes")
def get_recipes(db=Depends(get_db)):
    rows = db.execute("SELECT * FROM recipes ORDER BY id").fetchall()
    return [parse_recipe(row) for row in rows]


## 2. Add new recipe
@app.post("/api/recipes", dependencies=[Depends(require_auth)])
def create_recipe(body: RecipeBody, db=Depends(get_db)):
    new_id = time_ns() // 1_000_000
    db.execute(
        "INSERT INTO recipes (id, title, method, desc, ingredients, steps, notes) VALUES (?,?,?,?,?,?,?)",
        (
            new_id,
            body.title,
            body.method,
            body.desc,
            json.dumps(body.ingredients, ensure_ascii=False),
            json.dumps(body.steps, ensure_ascii=False),
            body.notes,
        ),
    )
    db.commit()
    return {"id": new_id}


## 3. Save editted recipe
@app.put("/api/recipes/{recipe_id}", dependencies=[Depends(require_auth)])
def save_recipe(recipe_id: int, body: RecipeBody, db=Depends(get_db)):
    db.execute(
        "UPDATE recipes SET title=?, method=?, desc=?, ingredients=?, steps=?, notes=? WHERE id=?",
        (
            body.title,
            body.method,
            body.desc,
            json.dumps(body.ingredients, ensure_ascii=False),
            json.dumps(body.steps, ensure_ascii=False),
            body.notes,
            recipe_id,
        ),
    )
    db.commit()


## 4. Delete a recipe.
@app.delete("/api/recipes/{recipe_id}", dependencies=[Depends(require_auth)])
def delete_recipe(recipe_id: int, db=Depends(get_db)):
    db.execute("DELETE FROM recipes WHERE id=?", [recipe_id])
    db.commit()


# Routes of ingredients
## 1. Access all ingredients for a house
@app.get("/api/ingredients")
def get_ingredients(house_id: int = 1, db=Depends(get_db)):
    rows = db.execute(
        "SELECT id, name, category, owned, stock_date, expiry_date FROM ingredients WHERE house_id=? ORDER BY category, name",
        [house_id],
    ).fetchall()
    cats = db.execute(
        "SELECT name FROM extra_categories WHERE house_id=? ORDER BY name",
        [house_id],
    ).fetchall()
    return {
        "ingredients": [dict(row) for row in rows],
        "extraCategories": [row["name"] for row in cats],
    }


## 2. Add ingredients
@app.post("/api/ingredients", dependencies=[Depends(require_auth)])
def add_ingredients(body: IngredientBody, db=Depends(get_db)):
    stock_date = normalize_date(body.stock_date, "入库日期")
    expiry_date = normalize_date(body.expiry_date, "过期日期")
    if stock_date and expiry_date and expiry_date < stock_date:
        raise HTTPException(status_code=400, detail="过期日期不能早于入库日期")

    try:
        db.execute(
            "INSERT INTO ingredients (name, category, owned, stock_date, expiry_date, house_id) VALUES (?, ?, ?, ?, ?, ?)",
            [
                body.name,
                body.category,
                body.owned,
                stock_date,
                expiry_date,
                body.house_id,
            ],
        )
        db.commit()
        return {"ok": True}
    except Exception:
        raise HTTPException(status_code=400, detail="食材已存在")


## 3. Update Ingredients Owned State
@app.put("/api/ingredients/owned", dependencies=[Depends(require_auth)])
def toggle_owned(body: OwnedBatch, db=Depends(get_db)):
    for u in body.updates:
        db.execute(
            "UPDATE ingredients SET owned=? WHERE name=? AND house_id=?",
            [(1 if u.owned else 0), u.name, body.house_id],
        )
    db.commit()
    return {"ok": True}


## 3.1 Update ingredient stock + expiry details
@app.put("/api/ingredients/stock", dependencies=[Depends(require_auth)])
def update_ingredient_stock(body: IngredientStockBody, db=Depends(get_db)):
    stock_date = normalize_date(body.stock_date, "入库日期")
    expiry_date = normalize_date(body.expiry_date, "过期日期")
    if stock_date and expiry_date and expiry_date < stock_date:
        raise HTTPException(status_code=400, detail="过期日期不能早于入库日期")

    cursor = db.execute(
        "UPDATE ingredients SET owned=?, stock_date=?, expiry_date=? WHERE name=? AND house_id=?",
        [(1 if body.owned else 0), stock_date, expiry_date, body.name, body.house_id],
    )
    if cursor.rowcount <= 0:
        raise HTTPException(status_code=404, detail="食材不存在")
    db.commit()
    return {"ok": True}


## 3.2 Clear all expired owned ingredients for a house
@app.put("/api/ingredients/clear-expired", dependencies=[Depends(require_auth)])
def clear_expired_ingredients(body: HouseScopeBody, db=Depends(get_db)):
    today = date.today().isoformat()
    cursor = db.execute(
        """
                UPDATE ingredients
                SET owned=0, stock_date=NULL, expiry_date=NULL
                WHERE house_id=?
                    AND owned=1
                    AND expiry_date IS NOT NULL
                    AND expiry_date <> ''
                    AND expiry_date < ?
                """,
        [body.house_id, today],
    )
    db.commit()
    return {"ok": True, "cleared": cursor.rowcount}


## 4. Delete Ingredients
@app.delete("/api/ingredients/{name}", dependencies=[Depends(require_auth)])
def delete_ingredients(name: str, house_id: int = 1, db=Depends(get_db)):
    db.execute("DELETE FROM ingredients WHERE name=? AND house_id=?", [name, house_id])
    db.commit()
    return {"ok": True}


## 5. delete the catagory
@app.delete(
    "/api/ingredients/category/{cat_name}", dependencies=[Depends(require_auth)]
)
def delete_category(cat_name: str, house_id: int = 1, db=Depends(get_db)):
    db.execute(
        "DELETE FROM ingredients WHERE category=? AND house_id=?", [cat_name, house_id]
    )
    db.execute(
        "DELETE FROM extra_categories WHERE name=? AND house_id=?",
        [cat_name, house_id],
    )
    db.commit()
    return {"ok": True}


## 6. Rename Cat
@app.put("/api/ingredients/category/rename", dependencies=[Depends(require_auth)])
def rename_category(body: CategoryRename, db=Depends(get_db)):
    db.execute(
        "UPDATE ingredients SET category=? WHERE category=? AND house_id=?",
        [body.newName, body.oldName, body.house_id],
    )
    db.execute(
        "UPDATE extra_categories SET name=? WHERE name=? AND house_id=?",
        [body.newName, body.oldName, body.house_id],
    )
    db.commit()
    return {"ok": True}


## 7. Add a new Category
@app.post("/api/ingredients/category", dependencies=[Depends(require_auth)])
def add_category(body: CategoryBody, db=Depends(get_db)):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="分类名不能为空")
    db.execute(
        "INSERT OR IGNORE INTO extra_categories (name, house_id) VALUES (?, ?)",
        [name, body.house_id],
    )
    db.commit()
    return {"ok": True}


## Register static file
PUBLIC_DIR = Path(__file__).parent.parent / "public"
app.mount("/", StaticFiles(directory=str(PUBLIC_DIR), html=True), name="static")
