#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script per ricreare e popolare il database con dati realistici
"""

import sys
import os
from datetime import datetime, date, time, timedelta
from random import choice, randint, uniform, random
import secrets
import string

# Aggiungi il percorso dell'app al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from werkzeug.security import generate_password_hash
from sqlalchemy import text
from app.database import engine, Base, SessionLocal
from app.models.clienti import Cliente
from app.models.staff import Staff
from app.models.eventi import Evento
from app.models.prenotazioni import Prenotazione
from app.models.ingressi import Ingresso
from app.models.feedback import Feedback
from app.models.prodotti import Prodotto
from app.utils.qr import generate_short_code

# Nomi italiani realistici
NOMI = [
    "Marco", "Giulia", "Alessandro", "Sofia", "Luca", "Emma", "Matteo", "Giorgia",
    "Francesco", "Alessia", "Davide", "Martina", "Andrea", "Chiara", "Stefano", "Elisa",
    "Gabriele", "Valentina", "Riccardo", "Federica", "Simone", "Sara", "Lorenzo", "Arianna",
    "Diego", "Greta", "Edoardo", "Beatrice", "Giovanni", "Camilla", "Federico", "Alice",
    "Tommaso", "Elena", "Nicola", "Viola", "Michele", "Noemi", "Fabio", "Claudia",
    "Antonio", "Laura", "Roberto", "Lucia", "Daniele", "Silvia", "Massimo", "Anna",
    "Enrico", "Caterina", "Paolo", "Francesca", "Giacomo", "Serena", "Alessio", "Veronica",
    "Manuel", "Ilaria", "Leonardo", "Ginevra", "Mattia", "Rebecca", "Salvatore", "Aurora",
    "Vincenzo", "Giada", "Raffaele", "Erica", "Claudio", "Isabella", "Pietro", "Bianca",
    "Fabrizio", "Cristina", "Gianluca", "Diletta", "Dario", "Michela", "Emiliano", "Nadia",
    "Gianmarco", "Teresa", "Mariano", "Stefania", "Alberto", "Patrizia", "Emanuele", "Cinzia"
]

COGNOMI = [
    "Rossi", "Russo", "Ferrari", "Esposito", "Bianchi", "Romano", "Colombo", "Ricci",
    "Marino", "Greco", "Bruno", "Gallo", "Conti", "De Luca", "Costa", "Fontana",
    "Caruso", "Mancini", "Rizzo", "Lombardi", "Moretti", "Barbieri", "Gallo", "Ferrara",
    "Mariani", "Gatti", "Caruso", "Leone", "Martini", "Vitale", "Lombardo", "Serra",
    "Coppola", "De Santis", "D'Angelo", "Marchetti", "Parisi", "Villa", "Conte", "Ferretti",
    "Sala", "De Rosa", "Palumbo", "Giordano", "Rinaldi", "Monti", "Palmieri", "Bernardi",
    "Pellegrini", "Basile", "Silvestri", "Guerra", "Testa", "Valentini", "Pagano", "Battaglia",
    "Caputo", "Orlando", "Bruni", "Sanna", "Piras", "Cattaneo", "Rizzi", "Colombo",
    "Neri", "Santoro", "Marino", "Ferri", "Cattaneo", "Galli", "Mazza", "Piazza",
    "Silva", "Amato", "Caruso", "Barbieri", "Longo", "Verdi", "Bruno", "Ferrero"
]

CITTA = [
    "Milano", "Roma", "Napoli", "Torino", "Palermo", "Genova", "Bologna", "Firenze",
    "Bari", "Catania", "Venezia", "Verona", "Messina", "Padova", "Trieste", "Brescia",
    "Taranto", "Prato", "Parma", "Modena", "Reggio Calabria", "Reggio Emilia", "Perugia",
    "Livorno", "Ravenna", "Cagliari", "Foggia", "Rimini", "Salerno", "Ferrara", "Sassari",
    "Monza", "Bergamo", "Pescara", "Trento", "Vicenza", "Bolzano", "Udine", "Ancona",
    "Arezzo", "Cesena", "Lecce", "Piacenza", "La Spezia", "Pisa", "Como", "Novara"
]

DJ_COMMERCIALE = [
    "DJ Massimo", "DJ Stefano", "DJ Marco V", "DJ Luca", "DJ Francesco",
    "DJ Alessandro", "DJ Andrea", "DJ Matteo", "DJ Paolo", "DJ Davide"
]

DJ_REGGETON = [
    "DJ El Moro", "DJ Latino", "DJ Reggae", "DJ Caribe", "DJ Tropical",
    "DJ Rumba", "DJ Salsa", "DJ Bomba", "DJ Fuego", "DJ Caliente"
]

DJ_TECHNO = [
    "DJ Techno Master", "DJ Dark Beat", "DJ Pulse", "DJ Electronic", "DJ Deep",
    "DJ Subzero", "DJ Nexus", "DJ Vortex", "DJ Matrix", "DJ Digital"
]

PROMOZIONI = [
    "Ingresso ridotto prima delle 24:00",
    "Aperitivo incluso",
    "2x1 cocktail fino alle 23:00",
    "Omaggio per compleanni",
    "Happy hour esteso",
    "Bottiglia omaggio per tavoli da 8+",
    "Playlist speciale richiesta",
    "VIP area access",
    "Drink speciale del giorno",
    None
]

ALPHABET = string.ascii_uppercase + string.digits

def generate_unique_qr_code(db):
    """Genera un QR code unico"""
    while True:
        code = generate_short_code(10)
        if not db.query(Cliente).filter_by(qr_code=code).first():
            return code

def generate_phone():
    """Genera un numero di telefono italiano realistico"""
    prefixes = ["333", "334", "335", "336", "337", "338", "339", "340", "346", "347", "348", "349",
                "320", "321", "322", "323", "324", "325", "326", "327", "328", "329",
                "366", "380", "388", "389", "391", "392", "393"]
    return f"+39{choice(prefixes)}{randint(1000000, 9999999)}"

def create_database():
    """Ricrea il database da zero"""
    print("🗑️  Eliminazione e ricreazione database...")
    
    # Crea tutte le tabelle tramite SQLAlchemy (questo ricrea le tabelle se non esistono)
    # Prima droppa tutte le tabelle
    Base.metadata.drop_all(bind=engine)
    # Poi ricreale
    Base.metadata.create_all(bind=engine)
    
    # Ora inserisci i dati iniziali (soglie_fedelta)
    db = SessionLocal()
    try:
        # Inserisci le soglie fedeltà
        insert_soglie = text("""
            INSERT IGNORE INTO soglie_fedelta (livello, punti_min) VALUES
            ('base', 0),
            ('loyal', 100),
            ('premium', 250),
            ('vip', 500)
        """)
        db.execute(insert_soglie)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"⚠️  Warning: {e}")
    finally:
        db.close()
    
    print("✅ Database ricreato con successo!")

def seed_staff(db):
    """Crea membri dello staff"""
    print("👥 Creazione staff...")
    
    staff_members = [
        {"nome": "Admin Malibu", "ruolo": "admin", "username": "admin", "password": "admin123"},
        {"nome": "Marco Ingressista", "ruolo": "ingressista", "username": "ingresso1", "password": "ingresso123"},
        {"nome": "Sara Barista", "ruolo": "barista", "username": "barista1", "password": "bar123"},
        {"nome": "Luca Ingressista", "ruolo": "ingressista", "username": "ingresso2", "password": "ingresso456"},
        {"nome": "Giulia Barista", "ruolo": "barista", "username": "barista2", "password": "bar456"},
    ]
    
    credentials_staff = []
    
    for s in staff_members:
        staff = Staff(
            nome=s["nome"],
            ruolo=s["ruolo"],
            username=s["username"],
            password_hash=generate_password_hash(s["password"]),
            attivo=True
        )
        db.add(staff)
        credentials_staff.append({"username": s["username"], "password": s["password"], "ruolo": s["ruolo"]})
    
    db.commit()
    print(f"✅ Creati {len(staff_members)} membri dello staff")
    return credentials_staff

def seed_eventi(db):
    """Crea eventi ricorrenti per Middle, El Moro, Attico"""
    print("🎉 Creazione eventi...")
    
    eventi_data = []
    oggi = date.today()
    
    # Eventi passati (ultimi 2 mesi)
    for i in range(30, 0, -7):  # Ogni settimana
        data_evt = oggi - timedelta(days=i)
        
        # Middle (musica commerciale) - ogni venerdì e sabato
        if data_evt.weekday() in [4, 5]:  # Venerdì o sabato
            eventi_data.append({
                "nome_evento": "Middle",
                "data_evento": data_evt,
                "tipo_musica": "Commerciale",
                "dj_artista": choice(DJ_COMMERCIALE),
                "categoria": "altro",
                "promozione": choice(PROMOZIONI),
                "stato_pubblico": "chiuso",
                "is_staff_operativo": False
            })
        
        # El Moro (reggaeton) - ogni giovedì e domenica
        if data_evt.weekday() in [3, 6]:  # Giovedì o domenica
            eventi_data.append({
                "nome_evento": "El Moro",
                "data_evento": data_evt,
                "tipo_musica": "Reggaeton",
                "dj_artista": choice(DJ_REGGETON),
                "categoria": "reggaeton",
                "promozione": choice(PROMOZIONI),
                "stato_pubblico": "chiuso",
                "is_staff_operativo": False
            })
        
        # Attico (techno) - ogni sabato sera
        if data_evt.weekday() == 5:  # Sabato
            eventi_data.append({
                "nome_evento": "Attico",
                "data_evento": data_evt,
                "tipo_musica": "Techno",
                "dj_artista": choice(DJ_TECHNO),
                "categoria": "techno",
                "promozione": choice(PROMOZIONI),
                "stato_pubblico": "chiuso",
                "is_staff_operativo": False
            })
    
    # Eventi futuri (prossimi 2 mesi)
    for i in range(7, 60, 7):  # Ogni settimana
        data_evt = oggi + timedelta(days=i)
        
        # Middle
        if data_evt.weekday() in [4, 5]:
            stato = "attivo" if i <= 14 else "programmato"
            eventi_data.append({
                "nome_evento": "Middle",
                "data_evento": data_evt,
                "tipo_musica": "Commerciale",
                "dj_artista": choice(DJ_COMMERCIALE),
                "categoria": "altro",
                "promozione": choice(PROMOZIONI),
                "stato_pubblico": stato,
                "is_staff_operativo": stato == "attivo"
            })
        
        # El Moro
        if data_evt.weekday() in [3, 6]:
            stato = "attivo" if i <= 14 else "programmato"
            eventi_data.append({
                "nome_evento": "El Moro",
                "data_evento": data_evt,
                "tipo_musica": "Reggaeton",
                "dj_artista": choice(DJ_REGGETON),
                "categoria": "reggaeton",
                "promozione": choice(PROMOZIONI),
                "stato_pubblico": stato,
                "is_staff_operativo": stato == "attivo"
            })
        
        # Attico
        if data_evt.weekday() == 5:
            stato = "attivo" if i <= 14 else "programmato"
            eventi_data.append({
                "nome_evento": "Attico",
                "data_evento": data_evt,
                "tipo_musica": "Techno",
                "dj_artista": choice(DJ_TECHNO),
                "categoria": "techno",
                "promozione": choice(PROMOZIONI),
                "stato_pubblico": stato,
                "is_staff_operativo": stato == "attivo"
            })
    
    eventi_ids = []
    for evt_data in eventi_data:
        evento = Evento(**evt_data)
        db.add(evento)
        db.flush()
        eventi_ids.append(evento.id_evento)
    
    db.commit()
    print(f"✅ Creati {len(eventi_data)} eventi")
    return eventi_ids

def seed_clienti(db, num_clienti=100):
    """Crea clienti con dati realistici"""
    print(f"👤 Creazione {num_clienti} clienti...")
    
    clienti_ids = []
    credentials_cliente = None
    
    for i in range(num_clienti):
        nome = choice(NOMI)
        cognome = choice(COGNOMI)
        
        # Calcola età tra 18 e 50 anni
        anni = randint(18, 50)
        data_nascita = date.today() - timedelta(days=anni * 365 + randint(0, 364))
        
        # Genera telefono unico
        telefono = generate_phone()
        while db.query(Cliente).filter_by(telefono=telefono).first():
            telefono = generate_phone()
        
        # Genera QR code unico
        qr_code = generate_unique_qr_code(db)
        
        # Password semplice per tutti (useremo "cliente123")
        password = "cliente123"
        
        # Livello fedeltà basato su punti (distribuzione realistica)
        if i < 10:  # 10 VIP
            livello = "vip"
            punti = randint(500, 1000)
        elif i < 30:  # 20 Premium
            livello = "premium"
            punti = randint(250, 499)
        elif i < 60:  # 30 Loyal
            livello = "loyal"
            punti = randint(100, 249)
        else:  # 40 Base
            livello = "base"
            punti = randint(0, 99)
        
        cliente = Cliente(
            nome=nome,
            cognome=cognome,
            data_nascita=data_nascita,
            citta=choice(CITTA),
            telefono=telefono,
            password_hash=generate_password_hash(password),
            qr_code=qr_code,
            livello=livello,
            punti_fedelta=punti,
            stato_account="attivo",
            data_registrazione=datetime.now() - timedelta(days=randint(1, 365))
        )
        
        db.add(cliente)
        db.flush()
        clienti_ids.append(cliente.id_cliente)
        
        # Salva credenziali del primo cliente
        if i == 0 and not credentials_cliente:
            credentials_cliente = {
                "telefono": telefono,
                "password": password,
                "nome": f"{nome} {cognome}"
            }
    
    db.commit()
    print(f"✅ Creati {num_clienti} clienti")
    return clienti_ids, credentials_cliente

def seed_prenotazioni(db, clienti_ids, eventi_ids):
    """Crea prenotazioni con show/no show"""
    print("📅 Creazione prenotazioni...")
    
    prenotazioni = []
    staff_ids = [s.id_staff for s in db.query(Staff).all()]
    
    # Per ogni evento passato, crea prenotazioni
    eventi_passati = db.query(Evento).filter(Evento.data_evento < date.today()).all()
    
    for evento in eventi_passati:
        # Numero di prenotazioni per evento (variabile)
        num_pren = randint(20, 80)
        clienti_evento = secrets.SystemRandom().sample(clienti_ids, min(num_pren, len(clienti_ids)))
        
        for cliente_id in clienti_evento:
            tipo = choice(["lista", "tavolo", "prevendita"])
            num_persone = randint(1, 8) if tipo == "tavolo" else randint(1, 4)
            
            # Stato: attiva, usata, no-show, cancellata
            # Per eventi passati, distribuzione realistica
            rand = random()
            if rand < 0.15:  # 15% no-show
                stato = "no-show"
            elif rand < 0.70:  # 55% usata
                stato = "usata"
            elif rand < 0.85:  # 15% cancellata
                stato = "cancellata"
            else:  # 15% ancora attiva (strano ma possibile)
                stato = "attiva"
            
            # Orario previsto tra 22:00 e 01:00
            ora_prevista = time(hour=randint(22, 23), minute=randint(0, 59))
            if randint(0, 1):
                ora_prevista = time(hour=0, minute=randint(0, 59))
            
            prenotazione = Prenotazione(
                cliente_id=cliente_id,
                evento_id=evento.id_evento,
                tipo=tipo,
                num_persone=num_persone,
                orario_previsto=ora_prevista,
                stato=stato,
                note=choice([None, "Compleanno", "Anniversario", "Tavolo preferito", None, None])
            )
            
            db.add(prenotazione)
            db.flush()
            prenotazioni.append({
                "id": prenotazione.id_prenotazione,
                "cliente_id": cliente_id,
                "evento_id": evento.id_evento,
                "stato": stato
            })
    
    # Alcune prenotazioni per eventi futuri
    eventi_futuri = db.query(Evento).filter(Evento.data_evento >= date.today()).limit(10).all()
    for evento in eventi_futuri:
        num_pren = randint(10, 40)
        clienti_evento = secrets.SystemRandom().sample(clienti_ids, min(num_pren, len(clienti_ids)))
        
        for cliente_id in clienti_evento:
            tipo = choice(["lista", "tavolo", "prevendita"])
            num_persone = randint(1, 8) if tipo == "tavolo" else randint(1, 4)
            
            prenotazione = Prenotazione(
                cliente_id=cliente_id,
                evento_id=evento.id_evento,
                tipo=tipo,
                num_persone=num_persone,
                orario_previsto=time(hour=randint(22, 23), minute=randint(0, 59)),
                stato="attiva"
            )
            
            db.add(prenotazione)
            db.flush()
            prenotazioni.append({
                "id": prenotazione.id_prenotazione,
                "cliente_id": cliente_id,
                "evento_id": evento.id_evento,
                "stato": "attiva"
            })
    
    db.commit()
    print(f"✅ Create {len(prenotazioni)} prenotazioni")
    return prenotazioni

def seed_ingressi(db, prenotazioni):
    """Crea ingressi collegati alle prenotazioni"""
    print("🚪 Creazione ingressi...")
    
    staff_ids = [s.id_staff for s in db.query(Staff).filter(Staff.ruolo == "ingressista").all()]
    
    ingressi_count = 0
    
    for pren in prenotazioni:
        # Crea ingresso solo per prenotazioni "usate" o "attiva" (non per no-show o cancellate)
        if pren["stato"] in ["usata", "attiva"]:
            evento = db.get(Evento, pren["evento_id"])
            if not evento:
                continue
            
            # Data e ora ingresso
            data_evento = evento.data_evento
            # Ora ingresso tra 22:00 e 01:00
            ora_ingresso = randint(22, 23)
            if randint(0, 2) == 0:  # 33% dopo mezzanotte
                ora_ingresso = randint(0, 1)
            minuto_ingresso = randint(0, 59)
            
            orario_ingresso = datetime.combine(data_evento, time(hour=ora_ingresso, minute=minuto_ingresso))
            
            # Tipo ingresso (coerente con prenotazione quando possibile)
            tipo_ingresso = pren.get("tipo", choice(["lista", "tavolo", "prevendita", "omaggio"]))
            
            ingresso = Ingresso(
                cliente_id=pren["cliente_id"],
                evento_id=pren["evento_id"],
                prenotazione_id=pren["id"],
                staff_id=choice(staff_ids) if staff_ids else None,
                tipo_ingresso=tipo_ingresso,
                orario_ingresso=orario_ingresso,
                note=choice([None, "Check-in rapido", "Gruppo numeroso", None])
            )
            
            try:
                db.add(ingresso)
                db.flush()
                ingressi_count += 1
            except Exception as e:
                # Potrebbe esserci un vincolo unique (cliente, evento)
                db.rollback()
                continue
    
    # Aggiungi alcuni ingressi senza prenotazione (walk-in)
    eventi_passati = db.query(Evento).filter(Evento.data_evento < date.today()).limit(15).all()
    clienti_ids = [c.id_cliente for c in db.query(Cliente).all()]
    
    for evento in eventi_passati:
        num_walkin = randint(5, 20)
        clienti_walkin = secrets.SystemRandom().sample(clienti_ids, min(num_walkin, len(clienti_ids)))
        
        for cliente_id in clienti_walkin:
            # Verifica che non ci sia già un ingresso
            if db.query(Ingresso).filter_by(cliente_id=cliente_id, evento_id=evento.id_evento).first():
                continue
            
            ora_ingresso = randint(22, 23)
            if randint(0, 2) == 0:
                ora_ingresso = randint(0, 1)
            
            orario_ingresso = datetime.combine(
                evento.data_evento,
                time(hour=ora_ingresso, minute=randint(0, 59))
            )
            
            ingresso = Ingresso(
                cliente_id=cliente_id,
                evento_id=evento.id_evento,
                prenotazione_id=None,
                staff_id=choice(staff_ids) if staff_ids else None,
                tipo_ingresso=choice(["lista", "omaggio"]),
                orario_ingresso=orario_ingresso
            )
            
            try:
                db.add(ingresso)
                db.flush()
                ingressi_count += 1
            except Exception:
                db.rollback()
                continue
    
    db.commit()
    print(f"✅ Creati {ingressi_count} ingressi")
    return ingressi_count

def seed_feedback(db, clienti_ids, eventi_ids):
    """Crea feedback per vari eventi"""
    print("⭐ Creazione feedback...")
    
    feedback_count = 0
    eventi_passati = db.query(Evento).filter(Evento.data_evento < date.today()).all()
    
    for evento in eventi_passati:
        # Verifica quali clienti hanno avuto un ingresso per questo evento
        ingressi = db.query(Ingresso).filter_by(evento_id=evento.id_evento).all()
        clienti_evento = list(set([ing.cliente_id for ing in ingressi]))
        
        # Solo una percentuale di clienti lascia feedback (30-50%)
        num_feedback = int(len(clienti_evento) * uniform(0.3, 0.5))
        clienti_feedback = secrets.SystemRandom().sample(clienti_evento, min(num_feedback, len(clienti_evento)))
        
        for cliente_id in clienti_feedback:
            # Verifica che non ci sia già un feedback
            if db.query(Feedback).filter_by(cliente_id=cliente_id, evento_id=evento.id_evento).first():
                continue
            
            # Voti realistici (distribuzione leggermente positiva)
            voto_musica = randint(6, 10) if random() < 0.7 else randint(4, 7)
            voto_ingresso = randint(7, 10) if random() < 0.8 else randint(5, 8)
            voto_ambiente = randint(7, 10) if random() < 0.75 else randint(5, 8)
            voto_servizio = randint(7, 10) if random() < 0.75 else randint(5, 8)
            
            note_options = [
                None, None, None, None,  # 50% senza note
                "Serata fantastica!",
                "Ottima musica",
                "Tornerò sicuramente",
                "Un po' affollato ma bello",
                "Servizio veloce",
                "Ambiente perfetto"
            ]
            
            data_feedback = datetime.combine(
                evento.data_evento + timedelta(days=1),
                time(hour=randint(10, 18), minute=randint(0, 59))
            )
            
            feedback = Feedback(
                cliente_id=cliente_id,
                evento_id=evento.id_evento,
                voto_musica=voto_musica,
                voto_ingresso=voto_ingresso,
                voto_ambiente=voto_ambiente,
                voto_servizio=voto_servizio,
                data_feedback=data_feedback,
                note=choice(note_options)
            )
            
            db.add(feedback)
            db.flush()
            feedback_count += 1
    
    db.commit()
    print(f"✅ Creati {feedback_count} feedback")
    return feedback_count

def main():
    """Funzione principale"""
    print("=" * 60)
    print("🌴 POPOLAMENTO DATABASE MALIBU 🌴")
    print("=" * 60)
    
    db = SessionLocal()
    
    try:
        # 1. Ricrea database
        create_database()
        
        # 2. Crea staff
        credentials_staff = seed_staff(db)
        
        # 3. Crea eventi
        eventi_ids = seed_eventi(db)
        
        # 4. Crea clienti
        clienti_ids, credentials_cliente = seed_clienti(db, num_clienti=100)
        
        # 5. Crea prenotazioni
        prenotazioni = seed_prenotazioni(db, clienti_ids, eventi_ids)
        
        # 6. Crea ingressi
        seed_ingressi(db, prenotazioni)
        
        # 7. Crea feedback
        seed_feedback(db, clienti_ids, eventi_ids)
        
        print("\n" + "=" * 60)
        print("✅ POPOLAMENTO COMPLETATO CON SUCCESSO!")
        print("=" * 60)
        print("\n📋 CREDENZIALI DI ACCESSO:\n")
        
        print("👤 CLIENTE:")
        if credentials_cliente:
            print(f"   Telefono: {credentials_cliente['telefono']}")
            print(f"   Password: {credentials_cliente['password']}")
            print(f"   Nome: {credentials_cliente['nome']}")
        
        print("\n👥 STAFF:")
        for cred in credentials_staff:
            print(f"   Username: {cred['username']}")
            print(f"   Password: {cred['password']}")
            print(f"   Ruolo: {cred['ruolo']}")
            print()
        
    except Exception as e:
        print(f"\n❌ ERRORE: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()

