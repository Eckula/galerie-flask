# api/media_cloudinary.py  — endpoints JSON (upload, list, delete)
import os
from flask import Blueprint, request, jsonify
from sqlalchemy import func
from models import db, Folder, Media

import cloudinary
import cloudinary.uploader

# Config Cloudinary depuis .env
#   soit CLOUDINARY_URL=cloudinary://<key>:<secret>@<cloud>
#   soit CLOUDINARY_CLOUD_NAME + CLOUDINARY_API_KEY + CLOUDINARY_API_SECRET
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,
)

media_api = Blueprint("media_api", __name__)

def get_or_create_folder(name: str) -> Folder:
    name = (name or "").strip() or "General"
    found = Folder.query.filter(func.lower(Folder.name) == name.lower()).first()
    if found:
        return found
    new = Folder(name=name)
    db.session.add(new)
    db.session.commit()
    return new

@media_api.route("/folders", methods=["GET"])
def list_folders():
    folders = Folder.query.order_by(Folder.name.asc()).all()
    return jsonify([{"id": f.id, "name": f.name} for f in folders])

@media_api.route("/media", methods=["GET"])
def list_media_all():
    medias = (
        db.session.query(Media, Folder)
        .join(Folder, Media.folder_id == Folder.id)
        .order_by(Media.created_at.desc())
        .all()
    )
    return jsonify([
        {
            "id": m.Media.id,
            "url": m.Media.url,
            "public_id": m.Media.public_id,
            "folder_id": m.Folder.id,
            "folder_name": m.Folder.name,
        }
        for m in medias
    ])

@media_api.route("/media/by-folder/<int:folder_id>", methods=["GET"])
def list_media_by_folder(folder_id):
    medias = Media.query.filter_by(folder_id=folder_id).order_by(Media.created_at.desc()).all()
    return jsonify([{"id": m.id, "url": m.url, "public_id": m.public_id, "folder_id": m.folder_id} for m in medias])

@media_api.route("/media/upload", methods=["POST"])
def upload_media():
    file = request.files.get("image")
    if not file or file.filename == "":
        return jsonify({"ok": False, "error": "no_file"}), 400

    folder_id = request.form.get("folder_id", type=int)
    new_folder = request.form.get("new_folder", "", type=str).strip()

    folder = None
    if new_folder:
        folder = get_or_create_folder(new_folder)
    elif folder_id:
        folder = Folder.query.get(folder_id)
    if not folder:
        folder = get_or_create_folder("General")

    try:
        result = cloudinary.uploader.upload(
            file,
            folder=f"famille/{folder.name}",  # organise côté Cloudinary
            resource_type="image",
            overwrite=False,
            invalidate=True,
        )
        public_id = result["public_id"]      # ex: famille/Album/xyz
        secure_url = result["secure_url"]

        media = Media(folder_id=folder.id, public_id=public_id, url=secure_url)
        db.session.add(media)
        db.session.commit()

        return jsonify({
            "ok": True,
            "media": {
                "id": media.id,
                "url": media.url,
                "public_id": media.public_id,
                "folder_id": media.folder_id,
                "folder_name": folder.name,
            }
        }), 201
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@media_api.route("/media/<int:media_id>", methods=["DELETE"])
def delete_media(media_id):
    media = Media.query.get_or_404(media_id)
    try:
        cloudinary.uploader.destroy(media.public_id, invalidate=True, resource_type="image")
    except Exception:
        # on continue quand même à supprimer en base
        pass
    db.session.delete(media)
    db.session.commit()
    return jsonify({"ok": True, "deleted": media_id})
