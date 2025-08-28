# api/folders.py  — COMPLET (tri A→Z, Z→A, récents, anciens, plus fournis)
# api/folders.py  ─────────────────────────────────────────────────────────────
# api/folders.py
from flask import Blueprint, request, jsonify
from sqlalchemy import func
from extensions import db
from models import Folder, Media

folders_bp = Blueprint("folders", __name__)

def _with_counts(query):
    counts = dict(db.session.query(Media.folder_id, func.count(Media.id))
                  .group_by(Media.folder_id).all())
    out = []
    for f in query:
        out.append({
            "id": f.id,
            "name": f.name,
            "pinned": bool(f.pinned),
            "created_at": (f.created_at.isoformat() if hasattr(f.created_at, "isoformat") else str(f.created_at)),
            "count": int(counts.get(f.id, 0))
        })
    return out

@folders_bp.get("/list")
def list_folders():
    sort = (request.args.get("sort") or "az").lower()
    qtxt = (request.args.get("q") or "").strip().lower()

    q = Folder.query
    if qtxt:
        q = q.filter(func.lower(Folder.name).contains(qtxt))

    if sort == "za":
        q = q.order_by(Folder.name.desc())
    elif sort == "recent":
        q = q.order_by(Folder.created_at.desc())
    elif sort == "oldest":
        q = q.order_by(Folder.created_at.asc())
    elif sort == "count":
        sub = (db.session.query(Media.folder_id, func.count(Media.id).label("c"))
               .group_by(Media.folder_id).subquery())
        q = q.outerjoin(sub, Folder.id == sub.c.folder_id) \
             .order_by((sub.c.c.is_(None)).asc(), sub.c.c.desc(), Folder.name.asc())
    else:
        q = q.order_by(Folder.name.asc())

    return jsonify(_with_counts(q.all()))

@folders_bp.post("/create")
def create_folder():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "empty"}), 400
    ex = Folder.query.filter(func.lower(Folder.name) == name.lower()).first()
    if ex:
        return jsonify({"ok": True, "id": ex.id, "name": ex.name})
    f = Folder(name=name)
    db.session.add(f); db.session.commit()
    return jsonify({"ok": True, "id": f.id, "name": f.name})

@folders_bp.post("/rename")
def rename_folder():
    data = request.get_json(silent=True) or {}
    fid = data.get("id")
    new = (data.get("new_name") or "").strip()
    if not fid or not new:
        return jsonify({"ok": False, "error": "bad_input"}), 400
    f = Folder.query.get_or_404(fid)
    f.name = new
    db.session.commit()
    return jsonify({"ok": True})

@folders_bp.post("/merge")
def merge_folders():
    data = request.get_json(silent=True) or {}
    src = data.get("source_id")
    dst = data.get("target_id")
    if not src or not dst or src == dst:
        return jsonify({"ok": False, "error": "bad_input"}), 400
    s = Folder.query.get_or_404(src)
    d = Folder.query.get_or_404(dst)
    Media.query.filter_by(folder_id=s.id).update({"folder_id": d.id})
    db.session.delete(s)
    db.session.commit()
    return jsonify({"ok": True})
