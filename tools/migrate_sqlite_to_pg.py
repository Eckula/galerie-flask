# tools/migrate_sqlite_to_pg.py
import os, sys
from sqlalchemy import create_engine, text

# --- Config ---
# Chemin / URI SQLite source (ton fichier actuel)
SQLITE_URI = os.environ.get("SQLITE_URI", "sqlite:///instance/gallery.db")
# URI Postgres cible (Neon) - à passer en variable d'env
PG_URI = os.environ.get("TARGET_DATABASE_URL")

if not PG_URI:
    print("ERROR: set TARGET_DATABASE_URL to your Neon postgres URL")
    sys.exit(1)

src = create_engine(SQLITE_URI, future=True)
dst = create_engine(PG_URI, future=True)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS folder (
  id         SERIAL PRIMARY KEY,
  name       VARCHAR(160) UNIQUE NOT NULL,
  pinned     BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS media (
  id         SERIAL PRIMARY KEY,
  url        VARCHAR(600) NOT NULL,
  public_id  VARCHAR(255) NOT NULL,
  folder_id  INTEGER REFERENCES folder(id) ON DELETE SET NULL,
  created_at TIMESTAMP
);
"""

def copy_table(table):
    with src.connect() as s, dst.begin() as d:
        rows = s.execute(text(f"SELECT * FROM {table}")).mappings().all()
        if not rows:
            print(f"- {table}: 0 rows")
            return
        cols = rows[0].keys()
        col_list = ",".join(cols)
        vals = ",".join([f":{c}" for c in cols])
        d.execute(text(f"TRUNCATE {table} RESTART IDENTITY CASCADE"))
        d.execute(text(f"INSERT INTO {table} ({col_list}) VALUES ({vals})"), rows)
        print(f"- {table}: {len(rows)} rows")

def fix_sequences():
    with dst.begin() as d:
        d.execute(text("SELECT setval(pg_get_serial_sequence('folder','id'), COALESCE((SELECT MAX(id) FROM folder),1))"))
        d.execute(text("SELECT setval(pg_get_serial_sequence('media','id'),  COALESCE((SELECT MAX(id) FROM media),1))"))

def main():
    print("Creating schema on Postgres if missing …")
    with dst.begin() as d:
        for stmt in SCHEMA_SQL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                d.execute(text(stmt))
    print("Copying tables …")
    copy_table("folder")
    copy_table("media")
    fix_sequences()
    print("OK.")

if __name__ == "__main__":
    main()
