# app.py — Flask + SQLAlchemy (pool Neon robuste) + proxys fichiers
from __future__ import annotations
import os, sys, time, re, mimetypes
from urllib.parse import urlparse

from flask import Flask, render_template, url_for, Response, abort, request
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

    app = Flask(__name__, instance_relative_config=True,
                static_folder="static", template_folder="templates")

    # --- DB
    db_uri = _choose_db_uri(app)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_uri
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
        "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
        "pool_timeout": 30,
        "connect_args": {"sslmode": "require", "connect_timeout": 10},
    }
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

    @app.context_processor
    def override_url_for():
        def dated_url_for(endpoint, **values):
            if endpoint == "static":
                filename = values.get("filename", "")
                file_path = os.path.join(app.static_folder, filename)
                values["v"] = int(os.stat(file_path).st_mtime) if os.path.exists(file_path) else int(time.time())
            return url_for(endpoint, **values)
        return dict(url_for=dated_url_for)

    db.init_app(app)
    migrate.init_app(app, db)

    with app.app_context():
        from models import Media, Folder  # noqa
        try:
            if db.engine.url.get_backend_name() == "sqlite":
                db.create_all()
            db.session.execute(text("select 1"))
        except Exception as e:
            app.logger.warning("DB warmup failed: %s", e)

    @app.teardown_appcontext
    def _shutdown_session(exc=None):
        db.session.remove()

    # Blueprints API
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

    # Debug DB
    @app.route("/__db")
    def __db():
        url_str = db.engine.url.render_as_string(hide_password=True)
        try:
            f = db.session.execute(text("select count(*) from folder")).scalar_one()
            m = db.session.execute(text("select count(*) from media")).scalar_one()
        except Exception as e:
            return {"url": url_str, "error": str(e)}, 500
        return {"url": url_str, "folder_count": f, "media_count": m}, 200

    # ---------- Streaming helpers ----------
    _UA = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari"}

    def _guess_mime_from_url(u: str) -> str:
        if re.search(r"\.pdf(?:$|\?)", u, re.I): return "application/pdf"
        mt, _ = mimetypes.guess_type(u)
        return mt or "application/octet-stream"

    def _stream_remote(url: str, filename: str | None = None, force_mime: str | None = None):
        ses = requests.Session()
        try:
            h = ses.head(url, headers=_UA, allow_redirects=True, timeout=8)
            mime = force_mime or (h.headers.get("Content-Type") if h.ok else None) or _guess_mime_from_url(url)
            r = ses.get(h.url if h.ok else url, headers=_UA, stream=True, allow_redirects=True, timeout=20)
            r.raise_for_status()
            name = filename or os.path.basename(urlparse(r.url).path) or "file"
            def generate():
                for chunk in r.iter_content(64 * 1024):
                    if chunk: yield chunk
            resp = Response(generate(), mimetype=mime)
            resp.headers["Content-Disposition"] = f'inline; filename="{name}"'
            resp.headers["Cache-Control"] = "public, max-age=3600"
            return resp
        except Exception:
            # Last resort: simple iframe fallback (still works for most viewers)
            html = f"""<!doctype html>
<html><head><meta charset="utf-8">
<style>html,body,iframe{{margin:0;border:0;height:100%;width:100%;background:#111}}</style>
</head><body><iframe src="{url}" title="Document"></iframe></body></html>"""
            return html, 200, {"Content-Type": "text/html; charset=utf-8"}

    # Existing PDF proxy (kept for direct PDF opening)
    @app.route("/preview/<int:media_id>")
    def preview(media_id: int):
        from models import Media
        m = db.session.get(Media, media_id)
        if not m or not getattr(m, "url", None): abort(404)
        return _stream_remote(m.url)

    # NEW: generic file proxy with extension in PATH (great for Office/Google viewers)
    # Example URL we will give to viewers:
    #   https://<yourapp>/file/123/my-doc.docx
    @app.route("/file/<int:media_id>/<path:filename>")
    def file_with_ext(media_id: int, filename: str):
        from models import Media
        m = db.session.get(Media, media_id)
        if not m or not getattr(m, "url", None): abort(404)
        ext = os.path.splitext(filename)[1].lower()
        mime = mimetypes.types_map.get(ext, None) if ext else None
        return _stream_remote(m.url, filename=filename, force_mime=mime)

    # alias utile si "python app.py"
    sys.modules.setdefault("app", sys.modules[__name__])
    return app


app = create_app()

if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "0") in ("1", "true", "True")
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=debug)
