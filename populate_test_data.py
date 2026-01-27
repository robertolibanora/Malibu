#!/usr/bin/env python3
"""
Script per popolare il database con dati di test.
Crea un cliente di test, un evento attivo e dati correlati seguendo tutte le relazioni DB.
"""

from datetime import datetime, date, timedelta, time
from app.database import SessionLocal, engine
from app.models.clienti import Cliente
from app.models.eventi import Evento
from app.models.staff import Staff
from app.models.prodotti import Prodotto
from app.models.tavoli_evento import TavoloEvento
from app.models.prenotazioni import Prenotazione
from app.models.ingressi import Ingresso
from app.models.consumi import Consumo
from app.models.fedeltà import Fedelta
from app.models.feedback import Feedback
from app.models.config_app import ConfigApp
from app.utils.auth import hash_password
from app.utils.qr import generate_short_code
from app.utils.events import set_evento_operativo_id, EVENTO_OPERATIVO_KEY
from sqlalchemy import text

def populate_test_data():
    """Popola il database con dati di test"""
    db = SessionLocal()
    
    try:
        print("🚀 Inizio popolamento database con dati di test...")
        
        # 1. CREA CLIENTE DI TEST
        print("\n1️⃣ Creazione cliente di test...")
        cliente_test = db.query(Cliente).filter_by(telefono="3331234567").first()
        if not cliente_test:
            qr_code = generate_short_code(10)
            cliente_test = Cliente(
                nome="Mario",
                cognome="Rossi",
                data_nascita=date(1990, 5, 15),
                citta="Roma",
                telefono="3331234567",
                password_hash=hash_password("test123"),  # Password: test123
                qr_code=qr_code,
                livello="loyal",
                punti_fedelta=150,
                stato_account="attivo"
            )
            db.add(cliente_test)
            db.commit()
            db.refresh(cliente_test)
            print(f"   ✅ Cliente creato: {cliente_test.nome} {cliente_test.cognome}")
            print(f"   📱 Telefono: {cliente_test.telefono}")
            print(f"   🔑 Password: test123")
            print(f"   📱 QR Code: {cliente_test.qr_code}")
        else:
            print(f"   ℹ️  Cliente già esistente: {cliente_test.nome} {cliente_test.cognome}")
        
        # 2. CREA STAFF DI TEST (opzionale ma utile)
        print("\n2️⃣ Creazione staff di test...")
        staff_admin = db.query(Staff).filter_by(username="admin").first()
        if not staff_admin:
            staff_admin = Staff(
                nome="Admin",
                ruolo="admin",
                username="admin",
                password_hash=hash_password("admin123"),  # Password: admin123
                attivo=True
            )
            db.add(staff_admin)
            db.commit()
            print(f"   ✅ Staff admin creato: {staff_admin.username} (password: admin123)")
        else:
            print(f"   ℹ️  Staff admin già esistente")
        
        staff_ingressista = db.query(Staff).filter_by(username="ingressista").first()
        if not staff_ingressista:
            staff_ingressista = Staff(
                nome="Luca",
                ruolo="ingressista",
                username="ingressista",
                password_hash=hash_password("ingressista123"),  # Password: ingressista123
                attivo=True
            )
            db.add(staff_ingressista)
            db.commit()
            db.refresh(staff_ingressista)
            print(f"   ✅ Staff ingressista creato: {staff_ingressista.username} (password: ingressista123)")
        else:
            print(f"   ℹ️  Staff ingressista già esistente")
            db.refresh(staff_ingressista)
        
        # 3. CREA EVENTO ATTIVO
        print("\n3️⃣ Creazione evento attivo...")
        evento_attivo = db.query(Evento).filter_by(nome_evento="Serata Reggaeton Test").first()
        if not evento_attivo:
            evento_attivo = Evento(
                nome_evento="Serata Reggaeton Test",
                data_evento=date.today(),
                tipo_musica="Reggaeton",
                dj_artista="DJ Test",
                capienza_max=500,
                categoria="reggaeton",
                stato="attivo",
                stato_pubblico="attivo",  # Evento pubblico e prenotabile
                is_staff_operativo=True,  # Staff può operare
                cover_url=None
            )
            db.add(evento_attivo)
            db.commit()
            db.refresh(evento_attivo)
            print(f"   ✅ Evento creato: {evento_attivo.nome_evento} (ID: {evento_attivo.id_evento})")
        else:
            # Aggiorna l'evento per renderlo attivo
            evento_attivo.stato_pubblico = "attivo"
            evento_attivo.is_staff_operativo = True
            db.commit()
            db.refresh(evento_attivo)
            print(f"   ✅ Evento già esistente, reso attivo: {evento_attivo.nome_evento} (ID: {evento_attivo.id_evento})")
        
        # 4. IMPOSTA EVENTO COME OPERATIVO
        print("\n4️⃣ Impostazione evento come operativo...")
        set_evento_operativo_id(db, evento_attivo.id_evento)
        print(f"   ✅ Evento {evento_attivo.id_evento} impostato come operativo")
        
        # 5. CREA PRODOTTI
        print("\n5️⃣ Creazione prodotti...")
        prodotti_data = [
            {"nome": "Birra Media", "prezzo": 5.00, "categoria": "bevande"},
            {"nome": "Birra Grande", "prezzo": 7.00, "categoria": "bevande"},
            {"nome": "Cocktail Mojito", "prezzo": 10.00, "categoria": "cocktail"},
            {"nome": "Cocktail Margarita", "prezzo": 12.00, "categoria": "cocktail"},
            {"nome": "Acqua", "prezzo": 2.00, "categoria": "bevande"},
            {"nome": "Coca Cola", "prezzo": 3.50, "categoria": "bevande"},
            {"nome": "Patatine", "prezzo": 4.00, "categoria": "snack"},
            {"nome": "Pizza Slice", "prezzo": 6.00, "categoria": "food"},
        ]
        
        prodotti_creati = []
        for prod_data in prodotti_data:
            prodotto = db.query(Prodotto).filter_by(nome=prod_data["nome"]).first()
            if not prodotto:
                prodotto = Prodotto(
                    nome=prod_data["nome"],
                    prezzo=prod_data["prezzo"],
                    categoria=prod_data["categoria"],
                    attivo=True
                )
                db.add(prodotto)
                prodotti_creati.append(prod_data["nome"])
            else:
                prodotti_creati.append(f"{prod_data['nome']} (già esistente)")
        
        db.commit()
        print(f"   ✅ Prodotti creati/verificati: {', '.join(prodotti_creati)}")
        
        # 6. CREA TAVOLI PER L'EVENTO
        print("\n6️⃣ Creazione tavoli per l'evento...")
        tavoli_data = [
            {"numero_tavolo": 1, "nome_tavolo": "Tavolo VIP 1", "capienza": 6, "prezzo_minimo": 200},
            {"numero_tavolo": 2, "nome_tavolo": "Tavolo VIP 2", "capienza": 8, "prezzo_minimo": 300},
            {"numero_tavolo": 3, "nome_tavolo": "Tavolo Standard 1", "capienza": 4, "prezzo_minimo": 100},
            {"numero_tavolo": 4, "nome_tavolo": "Tavolo Standard 2", "capienza": 4, "prezzo_minimo": 100},
        ]
        
        tavoli_creati = []
        for tav_data in tavoli_data:
            tavolo = db.query(TavoloEvento).filter_by(
                evento_id=evento_attivo.id_evento,
                numero_tavolo=tav_data["numero_tavolo"]
            ).first()
            if not tavolo:
                tavolo = TavoloEvento(
                    evento_id=evento_attivo.id_evento,
                    numero_tavolo=tav_data["numero_tavolo"],
                    nome_tavolo=tav_data["nome_tavolo"],
                    capienza=tav_data["capienza"],
                    prezzo_minimo=tav_data["prezzo_minimo"],
                    attivo=True
                )
                db.add(tavolo)
                tavoli_creati.append(tav_data["nome_tavolo"])
            else:
                tavoli_creati.append(f"{tav_data['nome_tavolo']} (già esistente)")
        
        db.commit()
        print(f"   ✅ Tavoli creati/verificati: {', '.join(tavoli_creati)}")
        
        # 7. CREA PRENOTAZIONI
        print("\n7️⃣ Creazione prenotazioni...")
        
        # Prenotazione lista
        pren_lista = db.query(Prenotazione).filter_by(
            cliente_id=cliente_test.id_cliente,
            evento_id=evento_attivo.id_evento,
            tipo="lista"
        ).first()
        if not pren_lista:
            pren_lista = Prenotazione(
                cliente_id=cliente_test.id_cliente,
                evento_id=evento_attivo.id_evento,
                tipo="lista",
                num_persone=2,
                orario_previsto=time(22, 0),
                stato="attiva",
                ruolo_tavolo="none"
            )
            db.add(pren_lista)
            db.commit()
            db.refresh(pren_lista)
            print(f"   ✅ Prenotazione lista creata (ID: {pren_lista.id_prenotazione})")
        else:
            print(f"   ℹ️  Prenotazione lista già esistente")
        
        # Prenotazione tavolo (referente)
        tavolo_vip = db.query(TavoloEvento).filter_by(
            evento_id=evento_attivo.id_evento,
            numero_tavolo=1
        ).first()
        
        pren_tavolo = db.query(Prenotazione).filter_by(
            cliente_id=cliente_test.id_cliente,
            evento_id=evento_attivo.id_evento,
            tipo="tavolo",
            ruolo_tavolo="referente"
        ).first()
        if not pren_tavolo and tavolo_vip:
            pren_tavolo = Prenotazione(
                cliente_id=cliente_test.id_cliente,
                evento_id=evento_attivo.id_evento,
                tipo="tavolo",
                num_persone=4,
                orario_previsto=time(21, 30),
                stato="attiva",
                ruolo_tavolo="referente",
                numero_tavolo=tavolo_vip.id_tavolo,
                nome_tavolo_gruppo="Gruppo Test",
                stato_approvazione_tavolo="approvata"
            )
            db.add(pren_tavolo)
            db.commit()
            db.refresh(pren_tavolo)
            print(f"   ✅ Prenotazione tavolo creata (ID: {pren_tavolo.id_prenotazione})")
        else:
            print(f"   ℹ️  Prenotazione tavolo già esistente o tavolo non disponibile")
        
        # 8. CREA INGRESSI
        print("\n8️⃣ Creazione ingressi...")
        
        ingresso_lista = db.query(Ingresso).filter_by(
            cliente_id=cliente_test.id_cliente,
            evento_id=evento_attivo.id_evento,
            tipo_ingresso="lista"
        ).first()
        if not ingresso_lista:
            ingresso_lista = Ingresso(
                cliente_id=cliente_test.id_cliente,
                evento_id=evento_attivo.id_evento,
                prenotazione_id=pren_lista.id_prenotazione if pren_lista else None,
                staff_id=staff_ingressista.id_staff,
                tipo_ingresso="lista",
                orario_ingresso=datetime.now() - timedelta(hours=1),
                note="Ingresso test"
            )
            db.add(ingresso_lista)
            print(f"   ✅ Ingresso lista creato")
        else:
            print(f"   ℹ️  Ingresso lista già esistente")
        
        if pren_tavolo:
            ingresso_tavolo = db.query(Ingresso).filter_by(
                cliente_id=cliente_test.id_cliente,
                evento_id=evento_attivo.id_evento,
                tipo_ingresso="tavolo"
            ).first()
            if not ingresso_tavolo:
                ingresso_tavolo = Ingresso(
                    cliente_id=cliente_test.id_cliente,
                    evento_id=evento_attivo.id_evento,
                    prenotazione_id=pren_tavolo.id_prenotazione,
                    staff_id=staff_ingressista.id_staff,
                    tipo_ingresso="tavolo",
                    orario_ingresso=datetime.now() - timedelta(minutes=30),
                    note="Ingresso tavolo test"
                )
                db.add(ingresso_tavolo)
                print(f"   ✅ Ingresso tavolo creato")
            else:
                print(f"   ℹ️  Ingresso tavolo già esistente")
        
        db.commit()
        
        # 9. CREA CONSUMI
        print("\n9️⃣ Creazione consumi...")
        
        birra_media = db.query(Prodotto).filter_by(nome="Birra Media").first()
        cocktail_mojito = db.query(Prodotto).filter_by(nome="Cocktail Mojito").first()
        
        consumi_creati = 0
        if birra_media:
            consumo1 = Consumo(
                cliente_id=cliente_test.id_cliente,
                evento_id=evento_attivo.id_evento,
                staff_id=staff_ingressista.id_staff,
                prodotto_id=birra_media.id_prodotto,
                prodotto="Birra Media",
                importo=5.00,
                data_consumo=datetime.now() - timedelta(minutes=45),
                punto_vendita="bar",
                note="Consumo test"
            )
            db.add(consumo1)
            consumi_creati += 1
        
        if cocktail_mojito:
            consumo2 = Consumo(
                cliente_id=cliente_test.id_cliente,
                evento_id=evento_attivo.id_evento,
                staff_id=staff_ingressista.id_staff,
                prodotto_id=cocktail_mojito.id_prodotto,
                prodotto="Cocktail Mojito",
                importo=10.00,
                data_consumo=datetime.now() - timedelta(minutes=20),
                punto_vendita="tavolo",
                note="Consumo tavolo test"
            )
            db.add(consumo2)
            consumi_creati += 1
        
        db.commit()
        print(f"   ✅ {consumi_creati} consumi creati")
        
        # 10. CREA PUNTI FEDELTÀ
        print("\n🔟 Creazione punti fedeltà...")
        
        fedelta1 = Fedelta(
            cliente_id=cliente_test.id_cliente,
            evento_id=evento_attivo.id_evento,
            punti=50,
            motivo="Consumo evento test"
        )
        db.add(fedelta1)
        
        db.commit()
        print(f"   ✅ Punti fedeltà creati: 50 punti")
        
        # 11. CREA FEEDBACK (opzionale)
        print("\n1️⃣1️⃣ Creazione feedback...")
        
        feedback = db.query(Feedback).filter_by(
            cliente_id=cliente_test.id_cliente,
            evento_id=evento_attivo.id_evento
        ).first()
        if not feedback:
            feedback = Feedback(
                cliente_id=cliente_test.id_cliente,
                evento_id=evento_attivo.id_evento,
                voto_musica=9,
                voto_ingresso=8,
                voto_ambiente=9,
                voto_servizio=8,
                note="Serata fantastica!"
            )
            db.add(feedback)
            db.commit()
            print(f"   ✅ Feedback creato")
        else:
            print(f"   ℹ️  Feedback già esistente")
        
        print("\n" + "="*60)
        print("✅ POPOLAMENTO COMPLETATO CON SUCCESSO!")
        print("="*60)
        print(f"\n📋 RIEPILOGO DATI DI TEST:")
        print(f"   👤 Cliente: {cliente_test.nome} {cliente_test.cognome}")
        print(f"      📱 Telefono: {cliente_test.telefono}")
        print(f"      🔑 Password: test123")
        print(f"      📱 QR Code: {cliente_test.qr_code}")
        print(f"\n   🎉 Evento Attivo: {evento_attivo.nome_evento}")
        print(f"      📅 Data: {evento_attivo.data_evento}")
        print(f"      🆔 ID: {evento_attivo.id_evento}")
        print(f"\n   👨‍💼 Staff Admin: admin / admin123")
        print(f"   👨‍💼 Staff Ingressista: ingressista / ingressista123")
        print(f"\n   📦 Prodotti: {len(prodotti_data)} prodotti disponibili")
        print(f"   🪑 Tavoli: {len(tavoli_data)} tavoli configurati")
        print(f"   📝 Prenotazioni: almeno 1 prenotazione lista e 1 tavolo")
        print(f"   🚪 Ingressi: almeno 1 ingresso registrato")
        print(f"   🍺 Consumi: {consumi_creati} consumi registrati")
        print(f"   ⭐ Punti Fedeltà: 50 punti assegnati")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ ERRORE durante il popolamento: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    populate_test_data()
