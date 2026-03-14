import os
import json
import sqlite3
from pathlib import Path
from time import time_ns
from pydantic import BaseModel


from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.staticfiles import StaticFiles


id = time_ns() 

app = FastAPI()


## Configurations
PORT = int(os.getenv("PORT", 3000))
DB_PATH = os.getenv("DB_PATH",Path(__file__).parent.parent / "data" / "recipes.db")
RECIPE_PASSWORD = os.getenv("RECIPE_PASSWORD",'changeme')

def init_db():
    conn = sqlite3.connect(DB_PATH,check_same_thread=False)

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

    CREATE TABLE IF NOT EXISTS ingredients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        category TEXT NOT NULL,
        owned INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS extra_categories (
        name TEXT PRIMARY KEY
    );
                 """)
    
    count = conn.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]
    print(count)
    if count == 0: # write default data
        path = Path(__file__).parent / "defaults.json"
        data = json.loads(path.read_text())
        for r in data['recipes']:
            conn.execute(
                "INSERT INTO recipes (id, title, method, desc, ingredients, steps, notes) VALUES (?,?,?,?,?,?,?)",
                (r["id"], r["title"], r["method"], r.get("desc", ""),
                json.dumps(r.get("ingredients",[]),ensure_ascii=False),
                json.dumps(r.get("steps", []),ensure_ascii=False),
                r.get("notes", ""))
            )
        
        for i in data['ingredients']:
            conn.execute(
                "INSERT INTO ingredients (name, category, owned) VALUES (?,?,?)",
                (i["name"], i["category"], (1 if i["owned"] else 0))
            )

        conn.commit()

    conn.close()

init_db()



# Help Function
def parse_recipe(row):
    r = dict(row)
    r["ingredients"] = json.loads(r.get("ingredients") or "[]")
    r["steps"] = json.loads(r.get("steps") or "[]")
    return r

def get_db():
    conn = sqlite3.connect(DB_PATH,check_same_thread=False)  # 1. 建立连接
    conn.row_factory = sqlite3.Row
    try:
        yield conn                    # 2. 把连接交给路由函数使用，暂停
        # 请求处理中...
    finally:
        conn.close()                  # 3. 请求处理完，继续执行，关闭连接


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

class OwnedUpdate(BaseModel):
    name: str
    owned: bool

class OwnedBatch(BaseModel):
    updates: list[OwnedUpdate]

class CategoryRename(BaseModel):
    oldName: str
    newName: str

class CategoryBody(BaseModel):
    name: str

# Authentication Function
def require_auth(x_recipe_password: str = Header(default="")):
    if x_recipe_password != RECIPE_PASSWORD:
        raise HTTPException(status_code=401, detail="密码错误?")

# Routes of recipes

## 1. Read all recipes 
@app.get("/api/recipes")
def get_recipes(db=Depends(get_db)):
    rows = db.execute("SELECT * FROM recipes ORDER BY id").fetchall()
    return [parse_recipe(row) for row in rows]

## 2. Add new recipe
@app.post("/api/recipes", dependencies=[Depends(require_auth)])
def create_recipe(body: RecipeBody, db = Depends(get_db)):
    new_id = time_ns() // 1_000_000
    db.execute(
        "INSERT INTO recipes (id, title, method, desc, ingredients, steps, notes) VALUES (?,?,?,?,?,?,?)",
        (new_id, body.title, body.method, body.desc,
         json.dumps(body.ingredients, ensure_ascii=False),
         json.dumps(body.steps, ensure_ascii=False),
         body.notes)
    )
    db.commit()
    return {"id": new_id}

## 3. Save editted recipe
@app.put("/api/recipes/{recipe_id}", dependencies=[Depends(require_auth)])
def save_recipe(recipe_id: int, body: RecipeBody, db = Depends(get_db)):
    db.execute(
        "UPDATE recipes SET title=?, method=?, desc=?, ingredients=?, steps=?, notes=? WHERE id=?",
        (body.title, body.method, body.desc,
         json.dumps(body.ingredients, ensure_ascii=False),
         json.dumps(body.steps, ensure_ascii=False),
         body.notes, recipe_id)
    )
    db.commit()

## 4. Delete a recipe.
@app.delete("/api/recipes/{recipe_id}", dependencies=[Depends(require_auth)])
def delete_recipe(recipe_id: int, db=Depends(get_db)):
    db.execute(
        'DELETE FROM recipes WHERE id=?',[recipe_id]
    )
    db.commit()

# Routes of ingredients
## 1. Aeccess all ingredient
@app.get("/api/ingredients")
def get_ingredients(db=Depends(get_db)):
    rows = db.execute('SELECT * FROM ingredients ORDER BY category, name').fetchall()
    cats = db.execute('SELECT name FROM extra_categories').fetchall()
    return {"ingredients": rows, "extraCategories": cats}


## 2. Add ingredients
@app.post("/api/ingredients", dependencies=[Depends(require_auth)])
def add_ingredients(body: IngredientBody, db=Depends(get_db)):
    try:
        db.execute('INSERT INTO ingredients (name, category, owned) VALUES (?, ?, ?)',[body.name, body.category, body.owned])
        db.commit()
        return {"ok": True}
    except Exception:
        raise HTTPException(status_code=400, detail="食材已存在")

## 3. Update Ingredients Owned State 
@app.put("/api/ingredients/owned", dependencies=[Depends(require_auth)])
def toggle_owned(body: OwnedBatch, db=Depends(get_db)):
    for u in body.updates:
        db.execute('UPDATE ingredients SET owned=? WHERE name=?', [(1 if u.owned else 0), u.name])
    db.commit()
    return {"ok": True}

## 4. delete Ingredients
@app.delete("/api/ingredients/{name}", dependencies=[Depends(require_auth)])
def delete_ingredients(name: str, db=Depends(get_db)):
    db.execute('DELETE FROM ingredients WHERE name=?', [name])
    db.commit()
    return {"ok": True}

## 5. delete the catagory
@app.delete("/api/ingredients/category/{cat_name}", dependencies=[Depends(require_auth)])
def delete_category(cat_name:str, db=Depends(get_db)):
    db.execute('DELETE FROM ingredients WHERE category=?',[cat_name])
    db.execute('DELETE FROM extra_categories WHERE name=?',[cat_name])
    db.commit()
    return {"ok": True}

## 6. Rename Cat
@app.put("/api/ingredients/category/rename", dependencies=[Depends(require_auth)])
def rename_category(body: CategoryRename, db=Depends(get_db)):
    db.execute('UPDATE ingredients SET category=? WHERE category=?', [body.newName, body.oldName])
    db.execute('UPDATE extra_categories SET name=? WHERE name=?', [body.newName, body.oldName])
    db.commit()
    return {"ok": True}

## 7. Add a new Category
@app.post("/api/ingredients/category", dependencies=[Depends(require_auth)])
def add_category(body: CategoryBody, db=Depends(get_db)):
    db.execute('INSERT OR IGNORE INTO extra_categories (name) VALUES (?)', [body.name])
    db.commit()
    return {"ok": True}


## Register static file
PUBLIC_DIR = Path(__file__).parent.parent / "public"
app.mount("/", StaticFiles(directory=str(PUBLIC_DIR), html=True), name="static")