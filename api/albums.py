# ============================================ # api/albums.py — Endpoints albums # Rôle : créer/lister les albums + rattacher des dossiers # ============================================

from flask import Blueprint, request, jsonifyfrom app import dbfrom models import Album, Folder

albums_bp = Blueprint("albums", __name__)
@albums_bp.route("/create", methods=["POST"])
def create_album():
    """[Album] Crée un album."""    
    payload = request.get_json(silent=True) or {}
    name = payload.get("name")
    if not name:
        return jsonify({"error": "Missing 'name'"}), 400
    album = Album(name=name)
    db.session.add(album)
    db.session.commit()
    return jsonify({"id": album.id, "name": album.name})
@albums_bp.route("/list", methods=["GET"])def list_albums():
    """[Album] Liste les albums avec leurs dossiers."""    
    albums = Album.query.all()
    return jsonify([
        {"id": a.id, "name": a.name, "folders": [{"id": f.id, "name": f.name} for f in a.folders]}
        for a in albums
    ])
@albums_bp.route("/add-folder", methods=["POST"])
def add_folder_to_album():
    """[Album] Ajoute un dossier existant à un album."""    
    payload = request.get_json(silent=True) or {}
    album_id = payload.get("album_id")
    folder_id = payload.get("folder_id")

    album = Album.query.get(album_id)
    folder = Folder.query.get(folder_id)
    if not album or not folder:
        return jsonify({"error": "Album or Folder not found"}), 404
    folder.album = album
    db.session.commit()
    return jsonify({"album": album.name, "folder": folder.name})