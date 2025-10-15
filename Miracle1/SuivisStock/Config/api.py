# api.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import sqlite3, os
from datetime import date
from contextlib import closing
from fastapi.middleware.cors import CORSMiddleware
from typing import Literal

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.sqlite3")

app = FastAPI(title="DLC Stock API")

# Autorise ton front local (vite:5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

# --- Schemas ---
class ItemIn(BaseModel):
    name: str = Field(min_length=1)
    category: str
    perishable: bool
    dlc: date
    location: str

class ItemOut(BaseModel):
    id: int
    name: str
    category: str
    perishable: bool
    dlc: str
    location: str
    created_at: str

class DisposalIn(BaseModel):
    outcome: Literal["consomme", "perdu"]

# --- Helpers ---
def find_or_create(conn, table: str, name: str) -> int:
    row = conn.execute(f"SELECT id FROM {table} WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute(f"INSERT INTO {table}(name) VALUES (?)", (name,))
    return cur.lastrowid

# --- Endpoints ---
@app.get("/health")
def health():
    ok = os.path.exists(DB_PATH)
    return {"db_path": DB_PATH, "db_exists": ok}

@app.get("/categories", response_model=List[str])
def get_categories():
    with closing(get_conn()) as conn:
        rows = conn.execute("SELECT name FROM category ORDER BY name ASC").fetchall()
    return [r["name"] for r in rows]

@app.get("/locations", response_model=List[str])
def get_locations():
    with closing(get_conn()) as conn:
        rows = conn.execute("SELECT name FROM location ORDER BY name ASC").fetchall()
    return [r["name"] for r in rows]

@app.get("/items", response_model=List[ItemOut])
def list_items():
    with closing(get_conn()) as conn:
        rows = conn.execute("""
            SELECT i.id, i.name, i.perishable, i.dlc, c.name AS category, l.name AS location, i.created_at
            FROM item i
            JOIN category c ON c.id = i.category_id
            JOIN location l ON l.id = i.location_id
            ORDER BY date(i.dlc) ASC, i.name ASC
        """).fetchall()
    return [
        ItemOut(
            id=r["id"],
            name=r["name"],
            category=r["category"],
            perishable=bool(r["perishable"]),
            dlc=r["dlc"],
            location=r["location"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


@app.post("/items/{item_id}/dispose", status_code=201)
def dispose_item(item_id: int, payload: DisposalIn):
    with closing(get_conn()) as conn, conn:
        row = conn.execute("""
            SELECT i.id, i.name, i.perishable, i.dlc, c.name AS category, l.name AS location
            FROM item i
            JOIN category c ON c.id = i.category_id
            JOIN location l ON l.id = i.location_id
            WHERE i.id = ?
        """, (item_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Item introuvable")

        # Log dans waste_log
        conn.execute("""
            INSERT INTO waste_log(item_id, name, category, location, perishable, dlc, outcome)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            row["id"], row["name"], row["category"], row["location"],
            int(row["perishable"]), row["dlc"], payload.outcome
        ))

        # Supprime de l'inventaire
        conn.execute("DELETE FROM item WHERE id = ?", (item_id,))

    return {"status": "ok", "id": item_id, "outcome": payload.outcome}


@app.post("/items", response_model=ItemOut, status_code=201)
def create_item(payload: ItemIn):
    with closing(get_conn()) as conn, conn:
        cat_id = find_or_create(conn, "category", payload.category.strip())
        loc_id = find_or_create(conn, "location", payload.location.strip())
        cur = conn.execute(
            """INSERT INTO item(name, category_id, perishable, dlc, location_id)
               VALUES (?, ?, ?, ?, ?)""",
            (payload.name.strip(), cat_id, 1 if payload.perishable else 0, payload.dlc.isoformat(), loc_id)
        )
        item_id = cur.lastrowid
        row = conn.execute("""
            SELECT i.id, i.name, i.perishable, i.dlc, c.name AS category, l.name AS location, i.created_at
            FROM item i
            JOIN category c ON c.id = i.category_id
            JOIN location l ON l.id = i.location_id
            WHERE i.id = ?
        """, (item_id,)).fetchone()
        if not row:
            raise HTTPException(500, "Insertion échouée")
    return ItemOut(
        id=row["id"],
        name=row["name"],
        category=row["category"],
        perishable=bool(row["perishable"]),
        dlc=row["dlc"],
        location=row["location"],
        created_at=row["created_at"],
    )
