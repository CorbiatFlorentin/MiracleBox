#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stock Tracker (DLC-based) — Python + SQLite
- Tables: category, location, item
- CLI: init, seed, add, list, check
- Alerte e-mail optionnelle sur les items qui expirent dans N jours

Exemples:
  python main.py init
  python main.py seed --categories "Produits laitiers,Fruits,Boissons" --locations "Cuisine,Frigo,Cellier"
  python main.py add --name "Yaourt nature" --category "Produits laitiers" --perishable 1 --dlc 2025-11-01 --location "Frigo"
  python main.py list
  python main.py check --days 7 --send-email 0
"""

import argparse
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, date
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

# Toujours créer la DB à côté du script, peu importe le répertoire courant
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.sqlite3")

DEFAULT_CATEGORIES = [
    "Produits laitiers", "Fruits", "Légumes", "Boissons",
    "Viandes", "Poisson", "Sauce", "Épicerie",
    "Boulangerie", "Surgelés", "Autre"
]

DEFAULT_LOCATIONS = [
    "Cuisine", "Frigo", "Congélateur", "Cellier",
    "Placard Cuisine", "Autre"
]

def get_conn() -> sqlite3.Connection:
    # isolation_level=None => autocommit si besoin; ici on commit via context manager
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db() -> None:
    with closing(get_conn()) as conn, conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS category (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS location (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS item (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category_id INTEGER NOT NULL,
                perishable INTEGER NOT NULL DEFAULT 1, -- 1=True, 0=False
                dlc DATE NOT NULL,
                location_id INTEGER NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES category(id) ON DELETE RESTRICT,
                FOREIGN KEY (location_id) REFERENCES location(id) ON DELETE RESTRICT
            );

            CREATE INDEX IF NOT EXISTS idx_item_dlc ON item(dlc);
            CREATE INDEX IF NOT EXISTS idx_item_category ON item(category_id);
            CREATE INDEX IF NOT EXISTS idx_item_location ON item(location_id);

            CREATE TABLE IF NOT EXISTS waste_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            location TEXT NOT NULL,
            perishable INTEGER NOT NULL,
            dlc DATE NOT NULL,
            outcome TEXT NOT NULL CHECK (outcome IN ('consomme','perdu')),
            logged_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
           );
           CREATE INDEX IF NOT EXISTS idx_waste_log_outcome ON waste_log(outcome);
           CREATE INDEX IF NOT EXISTS idx_waste_log_logged_at ON waste_log(logged_at);

            """
        )

    # Ces prints doivent être APRÈS le bloc with pour que le fichier soit réellement écrit
    print(f"✅ Base initialisée : {os.path.abspath(DB_PATH)}")
    print(f"🧱 Fichier créé ? {'✅ oui' if os.path.exists(DB_PATH) else '❌ non'}")

def seed_refs(categories: Optional[List[str]] = None, locations: Optional[List[str]] = None) -> None:
    categories = categories or DEFAULT_CATEGORIES
    locations = locations or DEFAULT_LOCATIONS
    with closing(get_conn()) as conn, conn:
        for c in categories:
            conn.execute("INSERT OR IGNORE INTO category(name) VALUES (?)", (c.strip(),))
        for l in locations:
            conn.execute("INSERT OR IGNORE INTO location(name) VALUES (?)", (l.strip(),))
    print("✅ Référentiels insérés (catégories/lieux).")

def find_or_create(conn: sqlite3.Connection, table: str, name: str) -> int:
    row = conn.execute(f"SELECT id FROM {table} WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute(f"INSERT INTO {table}(name) VALUES (?)", (name,))
    return cur.lastrowid

def add_item(name: str, category: str, perishable: int, dlc: str, location: str) -> int:
    # Validation date
    try:
        dlc_date = datetime.strptime(dlc, "%Y-%m-%d").date()
    except ValueError:
        raise SystemExit("Erreur: --dlc doit être au format YYYY-MM-DD (ex: 2025-10-31).")

    with closing(get_conn()) as conn, conn:
        cat_id = find_or_create(conn, "category", category.strip())
        loc_id = find_or_create(conn, "location", location.strip())
        cur = conn.execute(
            """
            INSERT INTO item(name, category_id, perishable, dlc, location_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name.strip(), cat_id, int(bool(perishable)), dlc_date.isoformat(), loc_id)
        )
        item_id = cur.lastrowid
    print(f"✅ Article #{item_id} ajouté: {name} (DLC {dlc_date.isoformat()})")
    return item_id

def list_items() -> None:
    with closing(get_conn()) as conn:
        rows = conn.execute(
            """
            SELECT i.id, i.name, i.perishable, i.dlc, c.name AS category, l.name AS location, i.created_at
            FROM item i
            JOIN category c ON c.id = i.category_id
            JOIN location l ON l.id = i.location_id
            ORDER BY date(i.dlc) ASC, i.name ASC
            """
        ).fetchall()

    if not rows:
        print("Aucun article.")
        return

    print(f"{'ID':<4} {'Nom':<30} {'Catégorie':<20} {'Lieu':<16} {'Périssable':<10} {'DLC':<10}")
    print("-" * 100)
    for r in rows:
        print(f"{r['id']:<4} {r['name']:<30} {r['category']:<20} {r['location']:<16} {('oui' if r['perishable'] else 'non'):<10} {r['dlc']:<10}")

def items_expiring_within(days: int = 7):
    today = date.today()
    limit = today + timedelta(days=days)
    with closing(get_conn()) as conn:
        rows = conn.execute(
            """
            SELECT i.id, i.name, i.dlc, i.perishable, c.name AS category, l.name AS location
            FROM item i
            JOIN category c ON c.id = i.category_id
            JOIN location l ON l.id = i.location_id
            WHERE i.perishable = 1
              AND date(i.dlc) BETWEEN date(?) AND date(?)
            ORDER BY date(i.dlc) ASC
            """,
            (today.isoformat(), limit.isoformat())
        ).fetchall()
    return rows

def build_email_html(rows, days: int) -> str:
    if not rows:
        return f"<p>Aucun article n'expire dans les {days} prochains jours.</p>"
    rows_html = "".join(
        f"<tr>"
        f"<td style='padding:6px 10px;border:1px solid #ddd'>{r['name']}</td>"
        f"<td style='padding:6px 10px;border:1px solid #ddd'>{r['category']}</td>"
        f"<td style='padding:6px 10px;border:1px solid #ddd'>{r['location']}</td>"
        f"<td style='padding:6px 10px;border:1px solid #ddd'>{r['dlc']}</td>"
        f"</tr>"
        for r in rows
    )
    return f"""
    <p>Voici la liste des produits qui arrivent à échéance dans les {days} jours :</p>
    <table style="border-collapse:collapse;border:1px solid #ddd">
      <thead>
        <tr>
          <th style='padding:6px 10px;border:1px solid #ddd;text-align:left'>Nom</th>
          <th style='padding:6px 10px;border:1px solid #ddd;text-align:left'>Catégorie</th>
          <th style='padding:6px 10px;border:1px solid #ddd;text-align:left'>Lieu</th>
          <th style='padding:6px 10px;border:1px solid #ddd;text-align:left'>DLC</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    """

def send_email(rows, days: int, to_email: Optional[str] = None) -> None:
    to_email = to_email or os.environ.get("ALERT_EMAIL", "florentin.corbiat@yahoo.fr")
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    mail_from = os.environ.get("SMTP_FROM", "Alerte DLC <noreply@example.com>")

    if not smtp_host or not smtp_user or not smtp_pass:
        raise SystemExit("Erreur: SMTP_HOST, SMTP_USER, SMTP_PASS (et idéalement SMTP_FROM) doivent être définis dans l'environnement.")

    subject = f"[Alerte DLC] {len(rows)} article(s) expirent sous {days} jours"
    html = build_email_html(rows, days)
    text = f"Articles expirant dans {days} jours:\n" + "\n".join(
        f"- {r['name']} ({r['category']}, {r['location']}) — DLC {r['dlc']}" for r in rows
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = to_email
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(mail_from, [to_email], msg.as_string())

def main():
    parser = argparse.ArgumentParser(description="Suivi de stock basé sur DLC (SQLite).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # init
    sub.add_parser("init", help="Créer la base de données et les tables.")

    # seed
    p_seed = sub.add_parser("seed", help="Insérer des catégories/lieux par défaut (ou personnalisés).")
    p_seed.add_argument("--categories", type=str, help="Liste CSV de catégories")
    p_seed.add_argument("--locations", type=str, help="Liste CSV de lieux")

    # add
    p_add = sub.add_parser("add", help="Ajouter un article.")
    p_add.add_argument("--name", required=True, type=str)
    p_add.add_argument("--category", required=True, type=str)
    p_add.add_argument("--perishable", required=True, type=int, choices=[0,1])
    p_add.add_argument("--dlc", required=True, type=str)  # YYYY-MM-DD
    p_add.add_argument("--location", required=True, type=str)

    # list
    sub.add_parser("list", help="Lister tous les articles (triés par DLC).")

    # check
    p_check = sub.add_parser("check", help="Lister (et envoyer) les articles expirant bientôt.")
    p_check.add_argument("--days", type=int, default=7)
    p_check.add_argument("--send-email", type=int, choices=[0,1], default=0)
    p_check.add_argument("--to", type=str, help="Destinataire (défaut: ALERT_EMAIL env)")

    args = parser.parse_args()

    if args.cmd == "init":
        init_db()
        return

    if args.cmd == "seed":
        cats = [c.strip() for c in args.categories.split(",")] if args.categories else None
        locs = [l.strip() for l in args.locations.split(",")] if args.locations else None
        seed_refs(cats, locs)
        return

    if args.cmd == "add":
        add_item(args.name, args.category, args.perishable, args.dlc, args.location)
        return

    if args.cmd == "list":
        list_items()
        return

    if args.cmd == "check":
        rows = items_expiring_within(args.days)
        if rows:
            print(f"⚠️  {len(rows)} article(s) expirent dans les {args.days} jour(s) :")
            for r in rows:
                print(f"- {r['name']} ({r['category']} @ {r['location']}) — DLC {r['dlc']}")
        else:
            print(f"✅ Aucun article n'expire dans les {args.days} prochains jours.")
        if args.send_email == 1:
            send_email(rows, args.days, to_email=args.to)
            print(f"📧 Email envoyé à {args.to or os.environ.get('ALERT_EMAIL', 'florentin.corbiat@yahoo.fr')}")
        return

if __name__ == "__main__":
    main()
