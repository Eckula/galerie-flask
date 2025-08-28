# app.py  ────────────────────────────────────────────────────────────────────
# app.py — application Flask (complet)
# ---------------------------------------------------------------
# - Crée automatiquement le dossier ./instance et la base SQLite
#   ./instance/gallery.db (évite l’erreur “unable to open database file”).
# - Cache busting pour /static (paramètre ?v=mtime).
# - Enregistre les blueprints API: /api/media et /api/folders
# - Route /preview/<id> : proxy de lecture (PDF/Docs/…) avec fallback.
# - Petit auto-patch SQLite pour s’assurer des colonnes utiles.
#
# Dépendances (requirements) :
#   flask, flask-sqlalchemy, flask-migrate, python-dotenv, requests
#   + (optionnel) cloudinary si tu utilises l’upload Cloudinary côté API.
# ---------------------------------------------------------------

# app.py — application Flask (complet, prêt à coller)
# ---------------------------------------------------------------
# Corrige l’erreur “The current Flask app is not registered…”
# même si tu lances `python app.py` (alias sys.modules["app"]).
# Crée ./instance/gallery.db automatiquement et auto-patch
# des colonnes (media.created_at, folder.created_at, folder.pinned).
# Route /preview/<id> pour lire PDF/Docs via proxy (fallback iframe).
# ---------------------------------------------------------------

# app.py
from flask import Flask, render_template, url_for, Response, abort
from dotenv import load_dotenv
from extensions import db, migrate
import os, time, mimetypes, requests, re
from urllib.parse import urlparse
from sqlalchemy import text

def create_app():
    load_dotenv()
    app = Flask(__name__, instance_relative_config=True,
                static_folder="static", template_folder="templates")

    # ── DB locale forcée dans ./instance/gallery.db (pas de DATABASE_URL)
    os.makedirs(app.instance_path, exist_ok=True)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(app.instance_path, "gallery.db").replace("\\", "/")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "supersecret")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Dev : pas de cache
    if app.debug:
        app.config["TEMPLATES_AUTO_RELOAD"] = True
        app.jinja_env.auto_reload = True
        app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    # cache-busting ?v=mtime
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

    # Crée les tables si nouvelle DB + patch auto colonnes si DB ancienne
    with app.app_context():
        from models import Media, Folder  # registre des modèles
        db.create_all()

        try:
            with db.engine.begin() as conn:
                app.logger.info("SQLite file: %s", os.path.join(app.instance_path, "gallery.db"))

                def has_col(table, col):
                    rows = conn.execute(text(f'PRAGMA table_info("{table}")')).fetchall()
                    return any(r[1] == col for r in rows)

                # Ajout "created_at" (texte ISO accepté par SQLite) et "pinned"
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

    # -------- Preview proxy (PDF/Docs inline fiable) + fallback HTML --------
    @app.route("/preview/<int:media_id>")
    def preview(media_id: int):
        from models import Media
        m = Media.query.get(media_id)
        if not m or not m.url:
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

    return app

app = create_app()

if __name__ == "__main__":
    app.run()
