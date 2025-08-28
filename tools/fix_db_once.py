# tools/fix_db_once.py  ───────────────────────────────────────────────────────
# Usage (Windows PowerShell/CMD depuis la racine du projet) :
#   .\venv\Scripts\python.exe tools\fix_db_once.py
# tools/fix_db_once.py
import os, sqlite3

BASE = os.path.dirname(os.path.dirname(__file__))
DB   = os.path.join(BASE, "instance", "gallery.db")
os.makedirs(os.path.dirname(DB), exist_ok=True)

con = sqlite3.connect(DB)
cur = con.cursor()

def has_col(table, col):
    cur.execute(f'PRAGMA table_info("{table}")')
    return any(r[1] == col for r in cur.fetchall())

for tbl, col, sql in [
    ("media",  "created_at", "ALTER TABLE media  ADD COLUMN created_at TEXT"),
    ("folder", "created_at", "ALTER TABLE folder ADD COLUMN created_at TEXT"),
    ("folder", "pinned",     "ALTER TABLE folder ADD COLUMN pinned INTEGER DEFAULT 0")
]:
    try:
        if not has_col(tbl, col):
            cur.execute(sql)
            print("ADDED:", tbl, col)
        else:
            print("OK   :", tbl, col)
    except Exception as e:
        print("SKIP :", tbl, col, "-", e)

con.commit(); con.close()
print("Done ->", DB)
