# api/media.py
import os, re
from flask import Blueprint, request, jsonify
from sqlalchemy import func
from extensions import db
from models import Media, Folder

import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url

# Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,
)
BASE_FOLDER = os.getenv("CLOUDINARY_FOLDER", "galerie-flask")

media_bp = Blueprint("media", __name__)

AUDIO_EXT = {"mp3","wav","m4a","aac","ogg","oga","flac"}
DOC_EXT   = {"pdf","doc","docx","ppt","pptx","xls","xlsx","odt","ods","odp","txt","csv"}
VID_EXT   = {"mp4","webm","ogg","mov","m4v","3gp","mkv"}
IMG_EXT   = {"jpg","jpeg","png","gif","webp","bmp","svg","heic","heif","avif"}
_YT_RE    = re.compile(r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|embed/|shorts/))([A-Za-z0-9_-]{6,})")

def _is_youtube(url:str)->bool:
    u=(url or "").lower()
    return "youtube.com" in u or "youtu.be" in u

def _yt_id(url:str)->str|None:
    m=_YT_RE.search(url or "")
    return m.group(1) if m else None

def _ext_from_url(url:str)->str:
    u=(url or "").split("?")[0].lower()
    m=re.search(r"\.([a-z0-9]{2,5})$", u)
    return (m.group(1) if m else "") or ""

def _guess_kind_from_url(url: str):
    """
    Classement robuste même si l’URL n’a pas d’extension.
    On s’appuie sur les segments Cloudinary:
      /image/upload/ → photos
      /video/upload/ → vidéos
      /raw/upload/   → documents
    """
    u=(url or "").lower()
    if _is_youtube(u):                   return ("videos","yt")

    ext=_ext_from_url(u)
    if ext in IMG_EXT:                   return ("photos",    ext)
    if ext in VID_EXT:                   return ("videos",    ext)
    if ext in AUDIO_EXT:                 return ("audio",     ext)
    if ext in DOC_EXT:                   return ("documents", ext)

    # Détection par chemin Cloudinary
    if "/raw/upload/"   in u:            return ("documents", ext or "")
    if "/video/upload/" in u:            return ("videos",    ext or "mp4")
    if "/image/upload/" in u:            return ("photos",    ext or "jpg")

    # Par défaut on range dans documents (plus sûr que "photos")
    return ("documents", ext or "")

def _thumb_url(public_id: str, kind: str, url:str) -> str:
    if kind=="videos":
        if _is_youtube(url):
            vid=_yt_id(url)
            return f"https://img.youtube.com/vi/{vid}/hqdefault.jpg" if vid else ""
        u,_=cloudinary_url(public_id, resource_type="video", type="upload", format="jpg",
                           transformation=[{"width":480,"height":320,"crop":"fill","gravity":"auto",
                                            "quality":"auto","fetch_format":"auto","start_offset":"auto"}])
        return u
    if kind=="photos":
        u,_=cloudinary_url(public_id, resource_type="image", type="upload",
                           transformation=[{"width":480,"height":320,"crop":"fill","gravity":"auto",
                                            "quality":"auto","fetch_format":"auto"}])
        return u
    return ""

def _serialize(m: Media):
    kind, ext = _guess_kind_from_url(m.url)
    return {
        "id": m.id,
        "url": m.url,
        "public_id": m.public_id,
        "folder_id": m.folder_id,
        "kind": kind,
        "ext": ext,
        "thumb": _thumb_url(m.public_id, kind, m.url)
    }

# ─── LIST ────────────────────────────────────────────────────────────────────
@media_bp.get("/list/<int:folder_id>")
def list_by_folder(folder_id):
    paged  = request.args.get("mode") == "paged"
    offset = request.args.get("offset", type=int, default=0)
    limit  = request.args.get("limit",  type=int, default=60)
    q = Media.query.filter_by(folder_id=folder_id).order_by(Media.id.desc())
    total = q.count(); rows = q.offset(offset).limit(limit).all()
    items = [_serialize(m) for m in rows]
    if not paged:
        # compat: ancienne route renvoyait un tableau basique
        return jsonify([{"id":x["id"],"url":x["url"],"public_id":x["public_id"]} for x in items])
    next_off = offset + limit
    return jsonify({"items": items, "has_more": next_off < total,
                    "next_offset": (next_off if next_off < total else None), "total": total})

@media_bp.get("/list")
def list_all():
    offset = request.args.get("offset", type=int, default=0)
    limit  = request.args.get("limit",  type=int, default=60)
    q = Media.query.order_by(Media.id.desc())
    total=q.count(); rows=q.offset(offset).limit(limit).all()
    items=[_serialize(m) for m in rows]
    next_off = offset + limit
    return jsonify({"items": items, "has_more": next_off < total,
                    "next_offset": (next_off if next_off < total else None), "total": total})

# ─── UPLOAD fichier ──────────────────────────────────────────────────────────
@media_bp.post("/upload")
def upload():
    file = request.files.get("image")
    if not file or file.filename == "":
        return jsonify({"ok": False, "error": "no_file"}), 400

    folder_name = (request.form.get("new_folder") or "").strip()
    folder_id   = request.form.get("folder_id", type=int)
    folder = None
    if folder_name:
        folder = Folder.query.filter(func.lower(Folder.name)==folder_name.lower()).first()
        if not folder:
            folder = Folder(name=folder_name); db.session.add(folder); db.session.commit()
    elif folder_id:
        folder = Folder.query.get(folder_id)
    if not folder:
        folder = Folder.query.filter(func.lower(Folder.name)=="general").first()
        if not folder:
            folder = Folder(name="General"); db.session.add(folder); db.session.commit()

    try:
        res = cloudinary.uploader.upload(
            file,
            folder=f"{BASE_FOLDER}/{folder.name}",
            resource_type="auto",
            overwrite=False,
            invalidate=True
        )
        media = Media(folder_id=folder.id, public_id=res["public_id"], url=res["secure_url"])
        db.session.add(media); db.session.commit()
        return jsonify({"ok": True, "media": _serialize(media)}), 201
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ─── Lien YouTube ────────────────────────────────────────────────────────────
@media_bp.post("/add_youtube")
def add_youtube():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    folder_id = data.get("folder_id")
    try:
        folder_id = int(folder_id) if folder_id not in (None, "", "null") else None
    except (TypeError, ValueError):
        folder_id = None
    new_folder = (data.get("new_folder") or "").strip()

    if not url or not _is_youtube(url):
        return jsonify({"ok":False,"error":"bad_youtube_url"}), 400

    folder=None
    if new_folder:
        folder = Folder.query.filter(func.lower(Folder.name)==new_folder.lower()).first()
        if not folder:
            folder = Folder(name=new_folder); db.session.add(folder); db.session.commit()
    elif folder_id:
        folder = Folder.query.get(folder_id)
    if not folder:
        folder = Folder.query.filter(func.lower(Folder.name)=="general").first()
        if not folder:
            folder = Folder(name="General"); db.session.add(folder); db.session.commit()

    vid=_yt_id(url)
    m = Media(folder_id=folder.id, url=url, public_id=f"yt:{vid or 'unknown'}")
    db.session.add(m); db.session.commit()
    return jsonify({"ok":True,"media":_serialize(m)}), 201

# ─── SUPPRESSION ─────────────────────────────────────────────────────────────
@media_bp.delete("/<int:media_id>")
def delete_media(media_id):
    m = Media.query.get_or_404(media_id)
    try:
        if not _is_youtube(m.url):
            cloudinary.uploader.destroy(m.public_id, invalidate=True, resource_type="auto")
    except Exception:
        pass
    db.session.delete(m); db.session.commit()
    return jsonify({"ok": True, "deleted": media_id})

@media_bp.delete("/bulk")
def bulk_delete():
    data = request.get_json(silent=True) or {}
    ids = data.get("ids") or []
    if not ids: return jsonify({"ok": False, "error": "no_ids"}), 400
    rows = Media.query.filter(Media.id.in_(ids)).all()
    for m in rows:
        try:
            if not _is_youtube(m.url):
                cloudinary.uploader.destroy(m.public_id, invalidate=True, resource_type="auto")
        except Exception:
            pass
        db.session.delete(m)
    db.session.commit()
    return jsonify({"ok": True, "deleted": [m.id for m in rows]})
