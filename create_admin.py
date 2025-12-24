#!/usr/bin/env python3
"""
Script per creare un utente admin nel database
"""
from app import create_app
from app.database import SessionLocal
from app.models.staff import Staff
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    db = SessionLocal()
    try:
        # Verifica se esiste già un admin con username "admin"
        existing = db.query(Staff).filter(Staff.username == "admin").first()
        if existing:
            print(f"⚠️  L'utente 'admin' esiste già (ID: {existing.id_staff})")
            print("   Aggiorno la password...")
            existing.password_hash = generate_password_hash("admin123")
            existing.ruolo = "admin"
            existing.attivo = True
            db.commit()
            print("✅ Password aggiornata con successo!")
        else:
            # Crea nuovo utente admin
            admin = Staff(
                nome="Administrator",
                username="admin",
                password_hash=generate_password_hash("admin123"),
                ruolo="admin",
                attivo=True
            )
            db.add(admin)
            db.commit()
            print("✅ Utente admin creato con successo!")
            print(f"   Username: admin")
            print(f"   Password: admin123")
            print(f"   Ruolo: admin")
    except Exception as e:
        db.rollback()
        print(f"❌ Errore: {e}")
    finally:
        db.close()



