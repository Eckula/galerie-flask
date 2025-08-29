# tools/migrate_sqlite_to_pg.py
import os, sys
from typing import Iterable, Dict, Any, List
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

SQLITE_URI = os.environ.get("SQLITE_URI", "sqlite:///instance/gallery.db")

def _normalize_pg_uri(uri: str | None) -> str | None:
    if not uri:
        return uri
    if uri.startswith("postgres://"):
        uri = "postgresql://" + uri[len("postgres://"):]
    return uri

PG_URI = _normalize_pg_uri(
    os.environ.get("TARGET_DATABASE_URL") or os.environ.get("DATABASE_URL")
)

if not PG_URI:
    print("ERROR: set TARGET_DATABASE_URL (or DATABASE_URL) to your Neon Postgres URL")
    sys.exit(1)

src: Engine = create_engine(SQLITE_URI, future=True)
dst: Engine = create_engine(PG_URI, future=True)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS album (
  id         SERIAL PRIMARY KEY,
  name       VARCHAR(160) NOT NULL,
  created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS folder (
  id         SERIAL PRIMARY KEY,
  name       VARCHAR(160) NOT NULL,
  album_id   INTEGER REFERENCES album(id) ON DELETE SET NULL,
  created_at TIMESTAMP,
  pinned     BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS media (
  id         SERIAL PRIMARY KEY,
  url        VARCHAR(600) NOT NULL,
  public_id  VARCHAR(255),
  folder_id  INTEGER REFERENCES folder(id) ON DELETE SET NULL,
  created_at TIMESTAMP
);
"""

def chunked(iterable: Iterable[Dict[str, Any]], size: int = 1000):
    batch = []
    for row in iterable:
        batch.append(row)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch

def table_exists_sqlite(table: str) -> bool:
    with src.connect() as c:
        row = c.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=:t"
        ), {"t": table}).fetchone()
        return row is not None

def dest_columns(table: str) -> List[str]:
    with dst.connect() as c:
        rows = c.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name=:t
            ORDER BY ordinal_position
        """), {"t": table}).fetchall()
        return [r[0] for r in rows]

def copy_table(table: str):
    if not table_exists_sqlite(table):
        print(f"WARNING: table '{table}' not found in SQLite, skipping.")
        return

    print(f"→ Copying '{table}' …")
    with src.connect() as s:
        rows_map = s.execute(text(f"SELECT * FROM {table}")).mappings().all()

    total = len(rows_map)
    if total == 0:
        print(f"  - {table}: 0 rows (nothing to do)")
        with dst.begin() as d:
            d.execute(text(f"TRUNCATE {table} RESTART IDENTITY CASCADE"))
        return

    dst_cols = dest_columns(table)

    rows: List[Dict[str, Any]] = []
    for rm in rows_map:
        dct = {col: rm.get(col, None) for col in dst_cols}
        if table == "folder" and "pinned" in dct:
            v = dct["pinned"]
            dct["pinned"] = bool(v) if v is not None else None
        rows.append(dct)

    col_list = ",".join(dst_cols)
    val_list = ",".join([f":{c}" for c in dst_cols])
    insert_sql = text(f"INSERT INTO {table} ({col_list}) VALUES ({val_list})")

    with dst.begin() as d:
        d.execute(text(f"TRUNCATE {table} RESTART IDENTITY CASCADE"))
        inserted = 0
        for batch in chunked(rows, size=1000):
            d.execute(insert_sql, batch)
            inserted += len(batch)

    print(f"  - {table}: {inserted}/{total} rows")

def fix_sequences():
    print("→ Fixing sequences …")
    with dst.begin() as d:
        d.execute(text(
            "SELECT setval(pg_get_serial_sequence('album','id'), COALESCE((SELECT MAX(id) FROM album),1))"
        ))
        d.execute(text(
            "SELECT setval(pg_get_serial_sequence('folder','id'), COALESCE((SELECT MAX(id) FROM folder),1))"
        ))
        d.execute(text(
            "SELECT setval(pg_get_serial_sequence('media','id'),  COALESCE((SELECT MAX(id) FROM media),1))"
        ))
    print("  - sequences synced")

def ensure_schema():
    print("→ Ensuring schema on Postgres …")
    stmts = [s.strip() for s in SCHEMA_SQL.strip().split(";") if s.strip()]
    with dst.begin() as d:
        for stmt in stmts:
            d.execute(text(stmt))
    print("  - schema OK")

def sanity_check():
    with dst.connect() as c:
        a = c.execute(text("SELECT COUNT(*) FROM album")).scalar_one()
        f = c.execute(text("SELECT COUNT(*) FROM folder")).scalar_one()
        m = c.execute(text("SELECT COUNT(*) FROM media")).scalar_one()
        print(f"→ Sanity check: album={a}, folder={f}, media={m}")

def main():
    print("SQLite  →", SQLITE_URI)
    print("Postgres →", PG_URI)
    try:
        ensure_schema()
        print("→ Copying tables (order matters) …")
        copy_table("album")
        copy_table("folder")
        copy_table("media")
        fix_sequences()
        sanity_check()
        print("OK.")
    except SQLAlchemyError as e:
        print("SQLAlchemy error:", e)
        sys.exit(2)
    except Exception as e:
        print("Unexpected error:", e)
        sys.exit(3)

if __name__ == "__main__":
    main()
