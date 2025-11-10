import os
import random
import uuid
import hashlib
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal
from app.models.clienti import Cliente
from app.models.eventi import Evento
from app.models.prenotazioni import Prenotazione
from app.models.ingressi import Ingresso
from app.models.consumi import Consumo
from app.models.fedeltà import Fedelta
from app.models.staff import Staff


FIRST_NAMES = [
    "Luca", "Giulia", "Marco", "Francesca", "Alessandro", "Sara", "Federico", "Martina",
    "Davide", "Chiara", "Simone", "Elisa", "Matteo", "Valentina", "Andrea", "Laura",
    "Gabriele", "Silvia", "Edoardo", "Alice", "Nicola", "Marta", "Tommaso", "Ilaria",
    "Riccardo", "Noemi", "Stefano", "Camilla", "Alberto", "Beatrice", "Fabio", "Elena"
]

LAST_NAMES = [
    "Rossi", "Ferrari", "Russo", "Bianchi", "Romano", "Gallo", "Costa", "Fontana",
    "Greco", "Conti", "Esposito", "Marino", "Giordano", "Barbieri", "Moretti", "Lombardi",
    "Bruno", "Gatti", "Testa", "Ferri", "Grassi", "Pellegrini", "Rizzo", "Monti",
    "Sanna", "Caruso", "Parisi", "Villa", "Bianco", "Martini", "Leone", "Serra"
]

CITIES = [
    "Milano", "Roma", "Torino", "Napoli", "Bologna", "Firenze", "Genova", "Verona",
    "Palermo", "Catania", "Bari", "Parma", "Modena", "Padova", "Trieste", "Bolzano",
    "Ancona", "Perugia", "Pescara", "Cagliari", "Lecce", "Livorno", "Venezia", "Messina",
    "Udine", "Ravenna", "Reggio Emilia", "Trento", "La Spezia", "Vicenza", "Brescia", "Forlì"
]

MUSIC_TYPES = ["reggaeton", "techno", "privato", "altro"]
EVENT_NAMES = [
    "Malibu Nights", "Sunset Vibes", "Electro Wave", "Urban Jungle",
    "Midnight Groove", "Galaxy Beats", "Rhythm Lounge", "Velvet Sessions",
    "Neon Dreams", "Tropical Escape"
]

PRENOTAZIONE_TYPES = ["lista", "tavolo", "prevendita"]
INGRESSO_TYPES = ["lista", "tavolo", "omaggio", "prevendita"]
PRODUCTS = [
    "Champagne", "Gin Tonic", "Moscow Mule", "Spritz", "Bottiglia Vodka", "Cocktail Signature",
    "Whisky Sour", "Rum & Cola", "Tequila Shot", "Bottiglia Prosecco", "Analcolico Premium"
]
PUNTI_VENDITA = ["tavolo", "privè"]


def random_phone(existing: set[str]) -> str:
    while True:
        phone = f"+39 3{random.randint(10, 99)} {random.randint(1000000, 9999999)}"
        if phone not in existing:
            existing.add(phone)
            return phone


def random_date_of_birth() -> date:
    start = date(1965, 1, 1)
    end = date(2005, 12, 31)
    delta_days = (end - start).days
    return start + timedelta(days=random.randint(0, delta_days))


def determine_livello(punti_totali: int) -> str:
    if punti_totali >= 300:
        return "vip"
    if punti_totali >= 180:
        return "premium"
    if punti_totali >= 80:
        return "loyal"
    return "base"


def create_staff(session):
    existing_staff = session.query(Staff).count()
    if existing_staff >= 5:
        return list(session.query(Staff).all())

    seed_staff = []
    templates = [
        ("Alessio Conti", "admin"),
        ("Giada Verdi", "staff"),
        ("Claudio Rinaldi", "barista"),
        ("Paola Moreau", "cassa"),
        ("Enrico Sarti", "staff"),
        ("Veronica Neri", "barista")
    ]

    for idx, (name, role) in enumerate(templates, start=1):
        nome, cognome = name.split()
        staffer = Staff(
            nome=name,
            ruolo=role,
            username=f"seed_staff_{idx}",
            password_hash=hashlib.sha256(f"{name}{idx}".encode()).hexdigest(),
            attivo=True
        )
        seed_staff.append(staffer)

    session.add_all(seed_staff)
    session.flush()
    return list(session.query(Staff).all())


def create_events(session) -> list[Evento]:
    num_events = random.randint(5, 8)
    today = date.today()
    events = []
    used_names = set()

    for i in range(num_events):
        name = random.choice(EVENT_NAMES)
        while name in used_names:
            name = random.choice(EVENT_NAMES)
        used_names.add(name)

        offset_days = random.randint(-45, 30)
        event_date = today + timedelta(days=offset_days)

        if event_date > today + timedelta(days=7):
            stato_pubblico = "programmato"
            legacy_state = "attivo"
            is_staff_operativo = False
        elif event_date >= today - timedelta(days=3):
            stato_pubblico = "attivo"
            legacy_state = "attivo"
            is_staff_operativo = True
        else:
            stato_pubblico = "chiuso"
            legacy_state = "chiuso"
            is_staff_operativo = False

        evento = Evento(
            nome_evento=name,
            data_evento=event_date,
            tipo_musica=random.choice(["DJ Set", "Live Set", "Special Guest"]),
            dj_artista=random.choice(["DJ Alex", "DJ Luna", "DJ Marco", "DJ Stella"]),
            promozione=random.choice([
                "2x1 entro le 23",
                "Ingresso omaggio donna",
                "Happy hour esclusivo",
                "Guest list VIP"
            ]),
            capienza_max=random.randint(150, 400),
            categoria=random.choice(MUSIC_TYPES),
            stato=legacy_state,
            stato_pubblico=stato_pubblico,
            is_staff_operativo=is_staff_operativo,
            cover_url=None
        )
        session.add(evento)
        events.append(evento)

    session.flush()
    return events


def create_clients(session, total: int = 110) -> list[Cliente]:
    clients = []
    phones = set()
    for _ in range(total):
        nome = random.choice(FIRST_NAMES)
        cognome = random.choice(LAST_NAMES)
        telefono = random_phone(phones)
        qr_code = uuid.uuid4().hex
        registrazione = datetime.now() - timedelta(days=random.randint(1, 365))
        ultimo_accesso = registrazione + timedelta(days=random.randint(0, 90))
        password_hash = hashlib.sha256(f"{nome}{cognome}{registrazione}".encode()).hexdigest()

        cliente = Cliente(
            nome=nome,
            cognome=cognome,
            data_nascita=random_date_of_birth(),
            citta=random.choice(CITIES),
            telefono=telefono,
            password_hash=password_hash,
            data_registrazione=registrazione,
            ultimo_accesso=ultimo_accesso,
            qr_code=qr_code,
            livello="base",
            punti_fedelta=0,
            stato_account="attivo"
        )
        session.add(cliente)
        clients.append(cliente)

    session.flush()
    return clients


def seed_data():
    session = SessionLocal()

    # Evita doppioni grossolani: se ci sono già clienti seed, non procedere
    existing_seed = session.query(Cliente).filter(Cliente.telefono.like("+39 3%")).count()
    if existing_seed >= 100:
        print("Sono già presenti dati clienti: interruzione del seed per evitare duplicati.")
        session.close()
        return

    try:
        staff_members = create_staff(session)
        eventi = create_events(session)
        clienti = create_clients(session, total=random.randint(105, 130))

        loyalty_breakdown = defaultdict(list)
        loyalty_totals = defaultdict(int)
        ingressi_per_evento = set()

        clienti_con_prenotazioni = random.sample(
            clienti,
            k=int(len(clienti) * random.uniform(0.62, 0.68))
        )

        for cliente in clienti_con_prenotazioni:
            num_prenotazioni = random.choice([1, 1, 2])
            eventi_prenotati = random.sample(eventi, k=min(num_prenotazioni, len(eventi)))

            for evento in eventi_prenotati:
                tipo = random.choice(PRENOTAZIONE_TYPES)
                stato = "attiva"

                if evento.data_evento < date.today():
                    stato = random.choices(
                        ["usata", "no-show"],
                        weights=[0.7, 0.3],
                        k=1
                    )[0]
                elif evento.stato_pubblico == "attivo":
                    stato = random.choices(
                        ["attiva", "usata"],
                        weights=[0.5, 0.5],
                        k=1
                    )[0]

                prenotazione = Prenotazione(
                    cliente=cliente,
                    evento=evento,
                    tipo=tipo,
                    num_persone=random.randint(1, 6),
                    stato=stato
                )
                session.add(prenotazione)
                session.flush()

                pair_key = (cliente.id_cliente, evento.id_evento)

                if pair_key in ingressi_per_evento:
                    # Evita ingressi duplicati sullo stesso evento per cliente
                    continue

                if stato == "usata":
                    ingresso = Ingresso(
                        cliente=cliente,
                        evento=evento,
                        prenotazione=prenotazione,
                        staff=random.choice(staff_members),
                        tipo_ingresso=random.choice(INGRESSO_TYPES),
                        note=None
                    )
                    session.add(ingresso)
                    session.flush()
                    ingressi_per_evento.add(pair_key)
                    loyalty_breakdown[(cliente, evento)].append(("Prenotazione utilizzata", 10))
                    loyalty_totals[cliente] += 10
                elif stato == "no-show":
                    loyalty_breakdown[(cliente, evento)].append(("Prenotazione non utilizzata (no-show)", -5))
                    loyalty_totals[cliente] -= 5

        # Walk-in senza prenotazione (solo eventi attivi o passati)
        potenziali_walkin = [c for c in clienti if c not in clienti_con_prenotazioni or random.random() < 0.35]
        walkin_count = 0
        for cliente in potenziali_walkin:
            if random.random() < 0.45:
                evento = random.choice([ev for ev in eventi if ev.stato_pubblico != "programmato"])
                pair_key = (cliente.id_cliente, evento.id_evento)
                if pair_key in ingressi_per_evento:
                    continue

                ingresso = Ingresso(
                    cliente=cliente,
                    evento=evento,
                    prenotazione=None,
                    staff=random.choice(staff_members),
                    tipo_ingresso=random.choice(INGRESSO_TYPES),
                    note="Ingresso walk-in"
                )
                session.add(ingresso)
                session.flush()
                ingressi_per_evento.add(pair_key)
                loyalty_breakdown[(cliente, evento)].append(("Ingresso diretto (walk-in)", 5))
                loyalty_totals[cliente] += 5
                walkin_count += 1

        # Consumi solo per clienti entrati
        ingressi = session.query(Ingresso).all()
        consumi_totali = defaultdict(Decimal)

        for ingresso in ingressi:
            consumi_per_evento = random.randint(0, 3)
            for _ in range(consumi_per_evento):
                importo = Decimal(random.randint(10, 200))
                consumo = Consumo(
                    cliente_id=ingresso.cliente_id,
                    evento_id=ingresso.evento_id,
                    staff=random.choice(staff_members),
                    prodotto=random.choice(PRODUCTS),
                    importo=importo,
                    punto_vendita=random.choice(PUNTI_VENDITA),
                    note=None
                )
                session.add(consumo)
                consumi_totali[(ingresso.cliente_id, ingresso.evento_id)] += importo

        session.flush()

        for (cliente_obj, evento_obj), movimenti in loyalty_breakdown.items():
            cliente_id = cliente_obj.id_cliente
            evento_id = evento_obj.id_evento
            for motivo, punti in movimenti:
                fedelta_mov = Fedelta(
                    cliente_id=cliente_id,
                    evento_id=evento_id,
                    punti=punti,
                    motivo=motivo
                )
                session.add(fedelta_mov)

        for (cliente_id, evento_id), totale_importo in consumi_totali.items():
            punti = int(totale_importo // Decimal(10))
            if punti > 0:
                fedelta_mov = Fedelta(
                    cliente_id=cliente_id,
                    evento_id=evento_id,
                    punti=punti,
                    motivo=f"Consumi totali {totale_importo}€"
                )
                session.add(fedelta_mov)
                cliente = next(c for c in clienti if c.id_cliente == cliente_id)
                loyalty_totals[cliente] += punti

        session.flush()

        for cliente in clienti:
            cliente.punti_fedelta = loyalty_totals.get(cliente, 0)
            cliente.livello = determine_livello(cliente.punti_fedelta)

        session.commit()
        print(f"Seed completato: {len(clienti)} clienti, {len(eventi)} eventi, {len(ingressi)} ingressi, {walkin_count} walk-in.")

    except SQLAlchemyError as exc:
        session.rollback()
        print(f"Errore durante il seed: {exc}")
    finally:
        session.close()


if __name__ == "__main__":
    seed_data()
    os.remove(__file__)

