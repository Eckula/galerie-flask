from __future__ import annotations
import os, sys, time, re, mimetypes
from urllib.parse import urlparse

from flask import Flask, render_template, url_for, Response, abort
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.engine import make_url
import requests

from extensions import db, migrate


def _normalize_db_url(uri: str) -> str:
    if not uri:
        return uri
    if uri.startswith("postgres://"):
        uri = "postgresql://" + uri[len("postgres://"):]
    return uri


def _choose_db_uri(app: Flask) -> str:
    env_uri = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URI")
    if env_uri:
        return _normalize_db_url(env_uri)
    os.makedirs(app.instance_path, exist_ok=True)
    sqlite_path = os.path.join(app.instance_path, "gallery.db").replace("\\", "/")
    return f"sqlite:///{sqlite_path}"


def create_app() -> Flask:
    load_dotenv()

    app = Flask(
        __name__,
        instance_relative_config=True,
        static_folder="static",
        template_folder="templates",
    )

    # --- Base de données (ENV d'abord, sinon SQLite local)
    db_uri = _choose_db_uri(app)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_uri

    # Log de l'URI (mot de passe masqué)
    try:
        url = make_url(db_uri)
        app.logger.info("DB -> %s", url.render_as_string(hide_password=True))
    except Exception:
        app.logger.info("DB -> %s", db_uri)

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "supersecret")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    if app.debug:
        app.config["TEMPLATES_AUTO_RELOAD"] = True
        app.jinja_env.auto_reload = True
        app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    # cache-busting /static
    @app.context_processor
    def override_url_for():
        def dated_url_for(endpoint, **values):
            if endpoint == "static":
                filename = values.get("filename", "")
                file_path = os.path.join(app.static_folder, filename)
                values["v"] = int(os.stat(file_path).st_mtime) if os.path.exists(file_path) else int(time.time())
            return url_for(endpoint, **values)
        return dict(url_for=dated_url_for)

    # Init extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Création tables + auto-patch (SQLite uniquement)
    with app.app_context():
        from models import Media, Folder  # noqa: F401
        db.create_all()
        try:
            if db.engine.url.get_backend_name() == "sqlite":
                with db.engine.begin() as conn:
                    def has_col(table: str, col: str) -> bool:
                        rows = conn.execute(text(f'PRAGMA table_info("{table}")')).fetchall()
                        return any(r[1] == col for r in rows)
                    if not has_col("media", "created_at"):
                        conn.execute(text('ALTER TABLE "media" ADD COLUMN "created_at" TEXT'))
                    if not has_col("folder", "created_at"):
                        conn.execute(text('ALTER TABLE "folder" ADD COLUMN "created_at" TEXT'))
                    if not has_col("folder", "pinned"):
                        conn.execute(text('ALTER TABLE "folder" ADD COLUMN "pinned" INTEGER DEFAULT 0'))
        except Exception as e:
            app.logger.warning("Auto-patch schema skipped: %s", e)

    # Blueprints
    from api.media import media_bp
    from api.folders import folders_bp
    app.register_blueprint(media_bp,   url_prefix="/api/media")
    app.register_blueprint(folders_bp, url_prefix="/api/folders")

    # Pages
    @app.route("/")
    def home():
        return render_template("index.html")

    @app.route("/gallery")
    @app.route("/galerie")
    def gallery():
        return render_template("gallery.html")

    # Preview proxy
    @app.route("/preview/<int:media_id>")
    def preview(media_id: int):
        from models import Media
        m = db.session.get(Media, media_id)
        if not m or not getattr(m, "url", None):
            abort(404)
        url = m.url

        def guess_mime(u: str) -> str:
            if re.search(r"\.pdf(?:$|\?)", u, re.I): return "application/pdf"
            mt, _ = mimetypes.guess_type(u)
            return mt or "application/octet-stream"

        ses = requests.Session()
        headers = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari"}

        try:
            h = ses.head(url, headers=headers, allow_redirects=True, timeout=8)
            mime = (h.headers.get("Content-Type") if h.ok else None) or guess_mime(url)
            r = ses.get(h.url if h.ok else url, headers=headers, stream=True, allow_redirects=True, timeout=20)
            r.raise_for_status()
            name = os.path.basename(urlparse(r.url).path) or f"file-{media_id}"

            def generate():
                for chunk in r.iter_content(64 * 1024):
                    if chunk: yield chunk

            resp = Response(generate(), mimetype=mime)
            resp.headers["Content-Disposition"] = f'inline; filename="{name}"'
            resp.headers["Cache-Control"] = "public, max-age=3600"
            return resp

        except Exception:
            html = f"""<!doctype html>
<html><head><meta charset="utf-8">
<style>html,body,iframe{{margin:0;border:0;height:100%;width:100%;background:#111}}</style>
</head><body>
  <iframe src="{url}" title="Document"></iframe>
</body></html>"""
            return html, 200, {"Content-Type": "text/html; charset=utf-8"}

    # alias utile si appelé via 'python app.py'
    sys.modules.setdefault("app", sys.modules[__name__])

    return app


# Instance globale
app = create_app()

if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "0") in ("1", "true", "True")
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=debug)
