# seed.py
import os
from app import app, db
from models import Media, Folder, Album
import cloudinary
import cloudinary.uploader

# Configuration Cloudinary depuis les variables d'environnement
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)

# Liste de fichiers locaux à uploader pour le seed (ex: ./seed_media/)
SEED_FILES = [
    "./seed_media/photo1.jpg",
    "./seed_media/photo2.jpg",
    "./seed_media/photo3.jpg",
]

with app.app_context():
    # Réinitialisation de la base
    db.drop_all()
    db.create_all()

    # Création d'un album
    album1 = Album(name="Vacances 2025")
    db.session.add(album1)

    # Création d'un dossier
    folder1 = Folder(name="Plage", album=album1)
    db.session.add(folder1)

    db.session.commit()

    # Upload sur Cloudinary et création des Media
    for file_path in SEED_FILES:
        if not os.path.exists(file_path):
            print(f"Fichier introuvable: {file_path}")
            continue

        upload_result = cloudinary.uploader.upload(
            file_path,
            folder=os.getenv("CLOUDINARY_FOLDER") or "seed_media"
        )

        media = Media(
            url=upload_result["secure_url"],
            public_id=upload_result["public_id"],
            folder=folder1
        )
        db.session.add(media)

    db.session.commit()
    print("Seed terminé avec succès !")
