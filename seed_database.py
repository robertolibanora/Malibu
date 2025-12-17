#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script per ricreare e popolare il database con dati realistici e coerenti
Ogni cliente ha una storia completa: prenotazioni → ingressi → consumi → punti → livello
"""

import sys
import os
from datetime import datetime, date, time, timedelta
from random import choice, randint, uniform, random
import secrets
import string
from decimal import Decimal

# Aggiungi il percorso dell'app al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from werkzeug.security import generate_password_hash
from sqlalchemy import text
from app.database import engine, Base, SessionLocal
from app.models.clienti import Cliente
from app.models.staff import Staff
from app.models.eventi import Evento
from app.models.prenotazioni import Prenotazione
from app.models.tavoli_evento import TavoloEvento
from app.models.ingressi import Ingresso
from app.models.feedback import Feedback
from app.models.consumi import Consumo
from app.models.prodotti import Prodotto
from app.models.fedeltà import Fedelta
from app.utils.qr import generate_short_code
from app.routes.fedelta import PUNTI_INGRESSO_PRENOTAZIONE, PUNTI_INGRESSO_LIBERO, compute_level, get_thresholds

INVITE_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

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

# Prodotti tipici di un locale
PRODOTTI_DATA = [
    {"nome": "Birra", "prezzo": 5.00, "categoria": "Drink"},
    {"nome": "Cocktail", "prezzo": 10.00, "categoria": "Drink"},
    {"nome": "Vodka Red Bull", "prezzo": 12.00, "categoria": "Drink"},
    {"nome": "Gin Tonic", "prezzo": 11.00, "categoria": "Drink"},
    {"nome": "Whiskey", "prezzo": 15.00, "categoria": "Drink"},
    {"nome": "Champagne", "prezzo": 80.00, "categoria": "Bottiglia"},
    {"nome": "Bottiglia Vodka", "prezzo": 120.00, "categoria": "Bottiglia"},
    {"nome": "Bottiglia Whiskey", "prezzo": 150.00, "categoria": "Bottiglia"},
    {"nome": "Acqua", "prezzo": 3.00, "categoria": "Drink"},
    {"nome": "Coca Cola", "prezzo": 4.00, "categoria": "Drink"},
    {"nome": "Aperitivo", "prezzo": 8.00, "categoria": "Drink"},
    {"nome": "Shot", "prezzo": 6.00, "categoria": "Drink"},
]

TAVOLI_DATA = [
    {"numero_tavolo": 1, "capienza": 2},
    {"numero_tavolo": 2, "capienza": 4},
    {"numero_tavolo": 3, "capienza": 6},
    {"numero_tavolo": 4, "capienza": 8},
    {"numero_tavolo": 5, "capienza": 10},
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

def generate_invite_code(db):
    while True:
        code = "".join(secrets.choice(INVITE_CODE_ALPHABET) for _ in range(6))
        if not db.query(Prenotazione.id_prenotazione).filter(Prenotazione.codice_invito == code).first():
            return code

def create_database():
    """Ricrea il database da zero"""
    print("🗑️  Eliminazione e ricreazione database...")
    
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
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

def seed_prodotti(db):
    """Crea prodotti se non esistono"""
    print("🍹 Creazione prodotti...")
    
    prodotti_esistenti = {p.nome: p for p in db.query(Prodotto).all()}
    prodotti_creati = 0
    
    for prod_data in PRODOTTI_DATA:
        if prod_data["nome"] not in prodotti_esistenti:
            prodotto = Prodotto(
                nome=prod_data["nome"],
                prezzo=Decimal(str(prod_data["prezzo"])),
                categoria=prod_data["categoria"],
                attivo=True
            )
            db.add(prodotto)
            prodotti_creati += 1
    
    db.commit()
    print(f"✅ Creati {prodotti_creati} prodotti (totale: {len(PRODOTTI_DATA)})")
    return db.query(Prodotto).all()

def seed_tavoli_evento(db, evento_id, num_tavoli=20):
    """
    Crea tavoli da 1 a num_tavoli per un evento specifico
    Ogni tavolo ha una capienza fissa e realistica (non decisa dal cliente)
    """
    evento = db.query(Evento).get(evento_id)
    if not evento:
        return []
    
    tavoli_creati = []
    
    # Distribuzione realistica delle capienze:
    # - 20% tavoli da 2 persone (intimi)
    # - 40% tavoli da 4 persone (più comuni)
    # - 25% tavoli da 6 persone (gruppi medi)
    # - 10% tavoli da 8 persone (gruppi grandi)
    # - 5% tavoli da 10+ persone (VIP/gruppi molto grandi)
    
    capienze_distribuzione = []
    for i in range(num_tavoli):
        rand = random()
        if rand < 0.20:
            capienza = 2
        elif rand < 0.60:
            capienza = 4
        elif rand < 0.85:
            capienza = 6
        elif rand < 0.95:
            capienza = 8
        else:
            capienza = 10
        capienze_distribuzione.append(capienza)
    
    for numero in range(1, num_tavoli + 1):
        esistente = db.query(TavoloEvento).filter(
            TavoloEvento.evento_id == evento_id,
            TavoloEvento.numero_tavolo == numero
        ).first()
        
        if not esistente:
            capienza = capienze_distribuzione[numero - 1]
            tavolo = TavoloEvento(
                evento_id=evento_id,
                numero_tavolo=numero,
                nome_tavolo=None,
                capienza=capienza,  # Capienza fissa del tavolo
                prezzo_minimo=None,
                attivo=True
            )
            db.add(tavolo)
            tavoli_creati.append(tavolo)
    
    db.commit()
    return tavoli_creati

def seed_eventi(db):
    """Crea eventi ricorrenti per Middle, El Moro, Attico"""
    print("🎉 Creazione eventi...")
    
    eventi_data = []
    oggi = date.today()
    
    # Eventi passati (ultimi 2 mesi)
    for i in range(30, 0, -7):
        data_evt = oggi - timedelta(days=i)
        
        if data_evt.weekday() in [4, 5]:
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
        
        if data_evt.weekday() in [3, 6]:
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
        
        if data_evt.weekday() == 5:
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
    for i in range(7, 60, 7):
        data_evt = oggi + timedelta(days=i)
        stato = "attivo" if i <= 14 else "programmato"
        
        if data_evt.weekday() in [4, 5]:
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
        
        if data_evt.weekday() in [3, 6]:
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
        
        if data_evt.weekday() == 5:
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

def seed_cliente_completo(db, cliente_id, profilo_cliente, eventi_passati, prodotti, staff_ids, baristi_ids):
    """
    Crea una storia completa per un cliente:
    - Eventi frequentati (in base al profilo)
    - Prenotazioni
    - Ingressi
    - Consumi (che generano punti)
    - Movimenti fedeltà
    - Feedback
    """
    cliente = db.query(Cliente).get(cliente_id)
    if not cliente:
        return
    
    # Profilo cliente: determina quanti eventi frequenta
    num_eventi_target = profilo_cliente["num_eventi"]
    eventi_frequentati = secrets.SystemRandom().sample(eventi_passati, min(num_eventi_target, len(eventi_passati)))
    
    punti_totali = 0
    movimenti_fedelta = []
    consumi_creati = []
    
    for evento in eventi_frequentati:
        # Decidi se ha prenotazione o walk-in
        ha_prenotazione = random() < 0.7  # 70% con prenotazione
        
        prenotazione_id = None
        tavolo_selezionato = None
        if ha_prenotazione:
            # Crea prenotazione
            tipo = choice(["lista", "tavolo", "prevendita"])
            
            # Se è prenotazione tavolo, seleziona un tavolo disponibile e rispetta la sua capienza
            if tipo == "tavolo":
                # Recupera tavoli disponibili per questo evento
                tavoli_disponibili = db.query(TavoloEvento).filter(
                    TavoloEvento.evento_id == evento.id_evento,
                    TavoloEvento.attivo == True
                ).all()
                
                # Verifica quali tavoli sono già prenotati
                tavoli_prenotati = db.query(Prenotazione.numero_tavolo).filter(
                    Prenotazione.evento_id == evento.id_evento,
                    Prenotazione.stato == "attiva",
                    Prenotazione.numero_tavolo.isnot(None)
                ).all()
                tavoli_prenotati_ids = {t[0] for t in tavoli_prenotati}
                
                # Filtra tavoli disponibili
                tavoli_liberi = [t for t in tavoli_disponibili if t.id_tavolo not in tavoli_prenotati_ids]
                
                if tavoli_liberi:
                    # Seleziona un tavolo casuale tra quelli disponibili
                    tavolo_selezionato = choice(tavoli_liberi)
                    # Il numero di persone deve rispettare la capienza del tavolo
                    num_persone = randint(1, tavolo_selezionato.capienza)
                else:
                    # Nessun tavolo disponibile, cambia tipo a "lista"
                    tipo = "lista"
                    num_persone = randint(1, 4)
            else:
                num_persone = randint(1, 4)
            
            # Per eventi passati: stato realista
            if evento.data_evento < date.today():
                rand = random()
                if rand < 0.15:
                    stato = "no-show"
                elif rand < 0.70:
                    stato = "usata"
                elif rand < 0.85:
                    stato = "cancellata"
                else:
                    stato = "attiva"
            else:
                stato = "attiva"
            
            codice_invito = generate_invite_code(db) if tipo == "tavolo" else None
            prenotazione = Prenotazione(
                cliente_id=cliente_id,
                evento_id=evento.id_evento,
                tipo=tipo,
                num_persone=num_persone,
                orario_previsto=time(hour=randint(22, 23), minute=randint(0, 59)),
                stato=stato,
                ruolo_tavolo="referente" if tipo == "tavolo" else "none",
                codice_invito=codice_invito,
                numero_tavolo=tavolo_selezionato.id_tavolo if tavolo_selezionato else None,
                nome_tavolo_gruppo=f"Gruppo {cliente.nome}" if tipo == "tavolo" and tavolo_selezionato else None
            )
            db.add(prenotazione)
            db.flush()
            prenotazione_id = prenotazione.id_prenotazione
            
            # Se no-show, penalità punti
            if stato == "no-show":
                punti_no_show = -5
                movimento = Fedelta(
                    cliente_id=cliente_id,
                    evento_id=evento.id_evento,
                    punti=punti_no_show,
                    motivo=f"No-show evento #{evento.id_evento}"
                )
                db.add(movimento)
                punti_totali += punti_no_show
                movimenti_fedelta.append(movimento)
        
        # Crea ingresso solo se prenotazione usata/attiva o walk-in
        crea_ingresso = False
        if not ha_prenotazione:
            crea_ingresso = True
        elif ha_prenotazione and stato in ["usata", "attiva"]:
            crea_ingresso = True
        
        if crea_ingresso:
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
                prenotazione_id=prenotazione_id,
                staff_id=choice(staff_ids) if staff_ids else None,
                tipo_ingresso=choice(["lista", "tavolo", "prevendita", "omaggio"]),
                orario_ingresso=orario_ingresso
            )
            db.add(ingresso)
            db.flush()
            
            # Punti per ingresso
            punti_ingresso = PUNTI_INGRESSO_PRENOTAZIONE if ha_prenotazione else PUNTI_INGRESSO_LIBERO
            movimento = Fedelta(
                cliente_id=cliente_id,
                evento_id=evento.id_evento,
                punti=punti_ingresso,
                motivo=f"Ingresso evento #{evento.id_evento} ({'prenotazione' if ha_prenotazione else 'walk-in'})"
            )
            db.add(movimento)
            punti_totali += punti_ingresso
            movimenti_fedelta.append(movimento)
            
            # Crea consumi per questo evento (solo se ha ingresso)
            # Importo target basato sul profilo cliente
            importo_target = profilo_cliente["importo_per_evento"]
            importo_attuale = Decimal("0.00")
            
            # Crea consumi fino a raggiungere l'importo target
            while float(importo_attuale) < importo_target:
                prodotto = choice(prodotti)
                quantita = randint(1, 3)
                importo_consumo = Decimal(str(prodotto.prezzo)) * quantita
                
                # Non superare troppo l'importo target
                if float(importo_attuale + importo_consumo) > importo_target * 1.2:
                    break
                
                consumo = Consumo(
                    cliente_id=cliente_id,
                    evento_id=evento.id_evento,
                    staff_id=choice(baristi_ids) if baristi_ids else None,
                    prodotto_id=prodotto.id_prodotto,
                    prodotto=f"{prodotto.nome}" + (f" x{quantita}" if quantita > 1 else ""),
                    importo=importo_consumo,
                    punto_vendita=choice(["bar", "tavolo", "privè"]),
                    data_consumo=orario_ingresso + timedelta(minutes=randint(30, 180))
                )
                db.add(consumo)
                db.flush()
                consumi_creati.append(consumo)
                
                # Punti da consumo: 1 punto ogni 10€
                punti_consumo = int(float(importo_consumo) // 10.0)
                if punti_consumo > 0:
                    movimento = Fedelta(
                        cliente_id=cliente_id,
                        evento_id=evento.id_evento,
                        punti=punti_consumo,
                        motivo=f"Consumo evento #{evento.id_evento}"
                    )
                    db.add(movimento)
                    punti_totali += punti_consumo
                    movimenti_fedelta.append(movimento)
                
                importo_attuale += importo_consumo
            
            # Crea feedback (solo per eventi passati, 40% probabilità)
            if evento.data_evento < date.today() and random() < 0.4:
                feedback = Feedback(
                    cliente_id=cliente_id,
                    evento_id=evento.id_evento,
                    voto_musica=randint(6, 10) if random() < 0.7 else randint(4, 7),
                    voto_ingresso=randint(7, 10) if random() < 0.8 else randint(5, 8),
                    voto_ambiente=randint(7, 10) if random() < 0.75 else randint(5, 8),
                    voto_servizio=randint(7, 10) if random() < 0.75 else randint(5, 8),
                    data_feedback=datetime.combine(
                        evento.data_evento + timedelta(days=1),
                        time(hour=randint(10, 18), minute=randint(0, 59))
                    ),
                    note=choice([None, None, None, "Serata fantastica!", "Ottima musica", "Tornerò sicuramente"])
                )
                db.add(feedback)
    
    # Aggiorna punti e livello cliente
    cliente.punti_fedelta = punti_totali
    thresholds = get_thresholds(db)
    cliente.livello = compute_level(punti_totali, thresholds)
    
    db.commit()
    return {
        "prenotazioni": len(eventi_frequentati),
        "ingressi": len(consumi_creati) > 0,  # Se ha consumi, ha avuto ingresso
        "consumi": len(consumi_creati),
        "punti": punti_totali
    }

def seed_clienti_completi(db, eventi_passati, prodotti, staff_ids, baristi_ids, num_clienti=100):
    """Crea clienti con storie complete e coerenti"""
    print(f"👤 Creazione {num_clienti} clienti con storie complete...")
    
    clienti_ids = []
    credentials_cliente = None
    
    # Definisci profili cliente
    profili = []
    for i in range(num_clienti):
        if i < 10:  # 10 VIP
            profili.append({
                "livello_target": "vip",
                "punti_target": randint(500, 1000),
                "num_eventi": randint(15, 25),  # Molti eventi
                "importo_per_evento": randint(80, 200)  # Spende molto
            })
        elif i < 30:  # 20 Premium
            profili.append({
                "livello_target": "premium",
                "punti_target": randint(250, 499),
                "num_eventi": randint(8, 15),
                "importo_per_evento": randint(50, 120)
            })
        elif i < 60:  # 30 Loyal
            profili.append({
                "livello_target": "loyal",
                "punti_target": randint(100, 249),
                "num_eventi": randint(4, 10),
                "importo_per_evento": randint(30, 80)
            })
        else:  # 40 Base
            profili.append({
                "livello_target": "base",
                "punti_target": randint(0, 99),
                "num_eventi": randint(0, 5),
                "importo_per_evento": randint(10, 50)
            })
    
    # Crea clienti
    for i, profilo in enumerate(profili):
        nome = choice(NOMI)
        cognome = choice(COGNOMI)
        
        anni = randint(18, 50)
        data_nascita = date.today() - timedelta(days=anni * 365 + randint(0, 364))
        
        telefono = generate_phone()
        while db.query(Cliente).filter_by(telefono=telefono).first():
            telefono = generate_phone()
        
        qr_code = generate_unique_qr_code(db)
        password = "cliente123"
        
        cliente = Cliente(
            nome=nome,
            cognome=cognome,
            data_nascita=data_nascita,
            citta=choice(CITTA),
            telefono=telefono,
            password_hash=generate_password_hash(password),
            qr_code=qr_code,
            livello="base",  # Sarà aggiornato dopo i consumi
            punti_fedelta=0,  # Sarà calcolato
            stato_account="attivo",
            data_registrazione=datetime.now() - timedelta(days=randint(30, 365))
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
    print(f"✅ Creati {num_clienti} clienti base")
    
    # Ora crea la storia completa per ogni cliente
    print("📚 Creazione storie complete per ogni cliente...")
    stats_totali = {"prenotazioni": 0, "ingressi": 0, "consumi": 0}
    
    for i, cliente_id in enumerate(clienti_ids):
        if i % 10 == 0:
            print(f"   Progresso: {i}/{num_clienti} clienti processati...")
        
        stats = seed_cliente_completo(
            db, cliente_id, profili[i], eventi_passati, prodotti, staff_ids, baristi_ids
        )
        if stats:
            stats_totali["prenotazioni"] += stats.get("prenotazioni", 0)
            stats_totali["ingressi"] += stats.get("ingressi", 0)
            stats_totali["consumi"] += stats.get("consumi", 0)
    
    print(f"✅ Storie complete create:")
    print(f"   - Prenotazioni: {stats_totali['prenotazioni']}")
    print(f"   - Ingressi: {stats_totali['ingressi']}")
    print(f"   - Consumi: {stats_totali['consumi']}")
    
    return clienti_ids, credentials_cliente

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
        staff_ids = [s.id_staff for s in db.query(Staff).all()]
        baristi_ids = [s.id_staff for s in db.query(Staff).filter(Staff.ruolo == "barista").all()]
        ingressisti_ids = [s.id_staff for s in db.query(Staff).filter(Staff.ruolo == "ingressista").all()]
        
        # 3. Crea prodotti
        prodotti = seed_prodotti(db)
        
        # 4. Crea eventi
        eventi_ids = seed_eventi(db)
        
        # 5. Crea tavoli per tutti gli eventi (con capienze fisse)
        print("🪑 Creazione tavoli per eventi...")
        for evento_id in eventi_ids:
            seed_tavoli_evento(db, evento_id, num_tavoli=20)
        print("✅ Tavoli creati con capienze fisse")
        
        # 6. Crea clienti con storie complete
        eventi_passati = db.query(Evento).filter(Evento.data_evento < date.today()).all()
        clienti_ids, credentials_cliente = seed_clienti_completi(
            db,
            eventi_passati=eventi_passati,
            prodotti=prodotti,
            staff_ids=ingressisti_ids,
            baristi_ids=baristi_ids,
            num_clienti=100
        )
        
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
        
        # Verifica coerenza
        print("\n🔍 VERIFICA COERENZA DATI:")
        clienti_vip = db.query(Cliente).filter(Cliente.livello == "vip").all()
        print(f"   Clienti VIP: {len(clienti_vip)}")
        for c in clienti_vip[:3]:
            consumi_count = db.query(Consumo).filter(Consumo.cliente_id == c.id_cliente).count()
            ingressi_count = db.query(Ingresso).filter(Ingresso.cliente_id == c.id_cliente).count()
            print(f"   - {c.nome} {c.cognome}: {c.punti_fedelta} punti, {ingressi_count} ingressi, {consumi_count} consumi")
        
    except Exception as e:
        print(f"\n❌ ERRORE: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        evento_id = int(sys.argv[1])
        db = SessionLocal()
        try:
            seed_tavoli_evento(db, evento_id, num_tavoli=20)
            print(f"\n✅ Tavoli aggiunti per evento_id={evento_id} (con capienze fisse)")
        except Exception as e:
            print(f"\n❌ ERRORE: {e}")
            import traceback
            traceback.print_exc()
            db.rollback()
        finally:
            db.close()
    else:
        main()
