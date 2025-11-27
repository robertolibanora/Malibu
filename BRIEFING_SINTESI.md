# 📋 MALIBU APP - SINTESI ESSENZIALE

## 👥 RUOLI

**Cliente**: Login telefono → Prenota eventi → Check-in QR → Consumi → Feedback  
**Staff**: Login username → Scanner unificato (ingressista/barista automatico) → Operazioni evento  
**Admin**: Login admin → 5 sezioni (Dashboard, Eventi, Clienti, Operativo, Impostazioni)

---

## 🔐 AUTENTICAZIONE

- `/auth/login-cliente` - Clienti (telefono + password)
- `/auth/login-staff` - Staff/Admin (username + password)
- Rate limiting: 5 tentativi/minuto login, 30/minuto operazioni staff

---

## 🎯 FUNZIONALITÀ PRINCIPALI

### Cliente
- Registrazione → QR code generato
- Prenotazione eventi (lista/tavolo)
- Cancellazione entro 18:00
- Visualizza storico (prenotazioni, ingressi, consumi)
- Feedback eventi partecipati
- Punti fedeltà (livelli: base → loyal → premium → vip)

### Staff Operativo
- **Scanner unificato** (`/staff/scan`):
  - **Ingressista**: Scansiona QR → Registra ingresso
  - **Barista**: Scansiona QR → Listino → Addebito consumi

### Admin
**5 Sezioni:**
1. **📊 Dashboard** - Statistiche generali
2. **📅 Eventi** - CRUD eventi, analytics
3. **👥 Clienti** - CRUD, fedeltà, promozioni
4. **📋 Operativo** - Prenotazioni, ingressi, consumi, feedback (tempo reale)
5. **⚙️ Impostazioni** - Staff, prodotti, format, soglie, log

---

## 🔄 FLUSSO OPERATIVO

1. **Registrazione** → Cliente con QR
2. **Prenotazione** → Evento futuro (lista/tavolo)
3. **Evento attivo** → Admin imposta operativo
4. **Serata**:
   - Ingressista: Scan QR → Ingresso (+10 punti con pren, +5 senza)
   - Barista: Scan QR → Consumi (+1 ogni 10€)
5. **Chiusura** → No-show automatici (-5 punti)
6. **Feedback** → Cliente lascia recensione (+2 punti)

---

## ⭐ FEDELTÀ

**Punti automatici:**
- Ingresso con prenotazione: +10
- Ingresso senza prenotazione: +5
- Consumo: +1 ogni 10€
- Feedback: +2
- No-show: -5

**Livelli**: base (0) → loyal (100) → premium (250) → vip (500) [soglie configurabili]

---

## 🛡️ SICUREZZA

- Login separati clienti/staff
- Rate limiting su rotte sensibili
- Verifica autorizzazioni con decoratori
- Workflow automatico (no-show, stati prenotazioni)
- Hash password con upgrade automatico

---

## 📁 ARCHITETTURA

**Route principali:**
- `auth.py` - Autenticazione
- `clienti.py` - Area cliente + admin clienti
- `eventi.py` - Eventi pubblici + admin
- `prenotazioni.py` - Prenotazioni (con workflow automatico)
- `ingressi.py` - Ingressi (staff + admin)
- `consumi.py` - Consumi (staff + admin)
- `staff.py` - Scanner unificato + gestione staff
- `fedelta.py` - Sistema punti
- `feedback.py` - Recensioni

**Utils centralizzati:**
- `helpers.py` - Funzioni comuni (get_cliente, get_staff, etc.)
- `workflow.py` - Logica stati prenotazioni/ingressi/feedback
- `limiter.py` - Rate limiting
- `events.py` - Gestione evento operativo

---

## 🎨 INTERFACCE

**Admin**: 5 sezioni con hub e navigazione secondaria  
**Staff**: Scanner unificato mobile-friendly  
**Cliente**: Area personale + storico completo

---

**Fine sintesi** ✅

