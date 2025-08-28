# populate_db.py
from app import create_app, db
from models import Folder, Media

app = create_app()

with app.app_context():
    # --- Création des dossiers ---
    folder1 = Folder(name="Plage")
    folder2 = Folder(name="Dossier 1")

    db.session.add_all([folder1, folder2])
    db.session.commit()

    # --- Création des médias ---
    medias = [
        Media(
            folder_id=folder1.id,
            url="https://res.cloudinary.com/dtbkiwrwr/image/upload/v1756315747/seed_media/axyxseacobrgn3xag4is.jpg",
            public_id="axyxseacobrgn3xag4is"
        ),
        Media(
            folder_id=folder1.id,
            url="https://res.cloudinary.com/dtbkiwrwr/image/upload/v1756315749/seed_media/bcnjeezueqq61l0ehtcf.jpg",
            public_id="bcnjeezueqq61l0ehtcf"
        ),
        Media(
            folder_id=folder1.id,
            url="https://res.cloudinary.com/dtbkiwrwr/image/upload/v1756315750/seed_media/dqe22tohp2rrqev9zpon.jpg",
            public_id="dqe22tohp2rrqev9zpon"
        ),
        Media(
            folder_id=folder1.id,
            url="https://via.placeholder.com/150",
            public_id="placeholder1"
        ),
    ]

    db.session.add_all(medias)
    db.session.commit()

    print("✅ Dossiers et médias de test créés !")
