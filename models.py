# ============================================ 
# models.py — Modèles SQLAlchemy (Media, Folder, Album)
# Rôle : schéma SQLite + relations 
# ============================================
# À coller si besoin pour s'aligner avec ta migration Alembic
# models.py — (mise à jour : champs "kind" côté Media + "pinned" côté Folder)
# models.py  — schéma minimal stable (Folder + Media uniquement)
# models.py  ──────────────────────────────────────────────────────────────────
# models.py — schéma minimal stable
# models.py
from datetime import datetime
from extensions import db

class Folder(db.Model):
    __tablename__ = "folder"
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(160), unique=True, nullable=False)
    pinned     = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    medias     = db.relationship("Media", backref="folder",
                                 cascade="all, delete-orphan", lazy=True)

class Media(db.Model):
    __tablename__ = "media"
    id         = db.Column(db.Integer, primary_key=True)
    url        = db.Column(db.String(600), nullable=False)
    public_id  = db.Column(db.String(255), nullable=False)   # cloudinary ou 'yt:<id>'
    folder_id  = db.Column(db.Integer, db.ForeignKey("folder.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)




