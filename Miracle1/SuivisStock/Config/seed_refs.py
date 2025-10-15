#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import sqlite3
from contextlib import closing

# Par défaut, on cible la base à côté du script
DEFAULT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.sqlite3")

# Données par défaut (modifie librement)
DEFAULT_CATEGORIES = [
    "Produits laitiers",
    "Fruits",
    "Légumes",
    "Boissons",
    "Viandes",
    "Poisson",
    "Sauce",
    "Épicerie",
    "Boulangerie",
    "Surgelés",
    "Autre",
]

DEFAULT_LOCATIONS = [
    "Cuisine",
    "Frigo",
    "Congélateur",
    "Cellier",
    "Placard Cuisine",
    "Autre",
]

def get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def ensure_schema(db_path: str) -> None:
    """Crée les tables si elles n'existent pas (sécurisé/idempotent)."""
    with closing(get_conn(db_path)) as conn, conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS category (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS location (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );
            -- item est optionnelle ici, on ne l'insère pas dans ce script
            CREATE TABLE IF NOT EXISTS item (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category_id INTEGER NOT NULL,
                perishable INTEGER NOT NULL DEFAULT 1,
                dlc DATE NOT NULL,
                location_id INTEGER NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES category(id) ON DELETE RESTRICT,
                FOREIGN KEY (location_id) REFERENCES location(id) ON DELETE RESTRICT
            );
            CREATE INDEX IF NOT EXISTS idx_item_dlc ON item(dlc);
            CREATE INDEX IF NOT EXISTS idx_item_category ON item(category_id);
            CREATE INDEX IF NOT EXISTS idx_item_location ON item(location_id);
        """)

def seed_categories(db_path: str, names) -> int:
    count = 0
    with closing(get_conn(db_path)) as conn, conn:
        for n in names:
            n = n.strip()
            if not n:
                continue
            conn.execute("INSERT OR IGNORE INTO category(name) VALUES (?)", (n,))
            count += 1
    return count

def seed_locations(db_path: str, names) -> int:
    count = 0
    with closing(get_conn(db_path)) as conn, conn:
        for n in names:
            n = n.strip()
            if not n:
                continue
            conn.execute("INSERT OR IGNORE INTO location(name) VALUES (?)", (n,))
            count += 1
    return count

def wipe_refs(db_path: str) -> None:
    """Vide uniquement les référentiels (pas la table item)."""
    with closing(get_conn(db_path)) as conn, conn:
        conn.execute("DELETE FROM category;")
        conn.execute("DELETE FROM location;")

def main():
    p = argparse.ArgumentParser(description="Seed des référentiels (catégories / lieux) pour main.sqlite3")
    p.add_argument("--db", default=DEFAULT_DB, help="Chemin de la base SQLite (défaut: main.sqlite3 à côté du script)")
    p.add_argument("--categories", help="Liste CSV de catégories à insérer (sinon défauts)")
    p.add_argument("--locations", help="Liste CSV de lieux à insérer (sinon défauts)")
    p.add_argument("--wipe", action="store_true", help="Vider les référentiels avant d'insérer")
    args = p.parse_args()

    db_path = os.path.abspath(args.db)
    ensure_schema(db_path)

    cats = [c.strip() for c in args.categories.split(",")] if args.categories else DEFAULT_CATEGORIES
    locs = [l.strip() for l in args.locations.split(",")] if args.locations else DEFAULT_LOCATIONS

    if args.wipe:
        wipe_refs(db_path)
        print("🧹 Référentiels vidés (category, location).")

    c = seed_categories(db_path, cats)
    l = seed_locations(db_path, locs)

    print(f"✅ Seed OK → base: {db_path}")
    print(f"   • Catégories insérées (INSERT OR IGNORE): {len(cats)}")
    print(f"   • Lieux insérés (INSERT OR IGNORE): {len(locs)}")

if __name__ == "__main__":
    main()
