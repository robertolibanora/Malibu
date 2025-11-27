# 📋 BRIEFING PROGETTO MALIBU APP

## 🎯 PANORAMICA GENERALE

**Malibu App** è un sistema di gestione completo per discoteca/locale notturno che gestisce:
- **Clienti**: registrazione, prenotazioni, ingressi, consumi, feedback
- **Eventi**: creazione, gestione, analytics
- **Staff**: ingressisti e baristi operativi durante gli eventi
- **Fedeltà**: sistema a punti con livelli (base → loyal → premium → vip)
- **Promozioni**: assegnazione e gestione promozioni clienti
- **Analytics**: dashboard e statistiche per admin

---

## 👥 RUOLI E AUTORIZZAZIONI

### 🔐 **CLIENTE** (`require_cliente`)
- **Accesso**: Login dedicato `/auth/login-cliente` (telefono + password)
- **Poteri**:
  - Visualizzare e modificare il proprio profilo
  - Creare/cancellare prenotazioni per eventi pubblici
  - Visualizzare storico ingressi, consumi, prenotazioni
  - Lasciare feedback per eventi a cui ha partecipato
  - Visualizzare punti fedeltà e progresso livello

### 🧑‍🍳 **STAFF** (`require_staff`)
- **Ruoli**: `ingressista`, `barista`
- **Accesso**: Login dedicato `/auth/login-staff` (username + password)
- **Poteri**:
  - **Ingressista**: Scanner unificato per registrare ingressi all'evento operativo
  - **Barista**: Scanner unificato per registrare consumi/ordini per l'evento operativo
  - Visualizzare dashboard evento attivo
  - Visualizzare listino prodotti
  - Consultare prenotazioni per evento

### 👑 **ADMIN** (`require_admin`)
- **Accesso**: Login staff con ruolo `admin` o credenziali `.env` (`ADMIN_USER` / `ADMIN_PASSWORD`)
- **Poteri**: **ACCESSO COMPLETO** a tutte le funzionalità tramite 5 sezioni principali:
  - **📊 Dashboard**: Panoramica generale e statistiche
  - **📅 Eventi**: Gestione completa eventi e programmazione
  - **👥 Clienti**: Gestione anagrafica, fedeltà e promozioni
  - **📋 Operativo**: Gestione in tempo reale prenotazioni, ingressi, consumi e feedback
  - **⚙️ Impostazioni**: Gestione staff, listino, format eventi, soglie fedeltà e log attività

---

## 📊 MODELLI DATABASE

### 👤 **Cliente** (`app/models/clienti.py`)
**Cosa rappresenta**: Profilo cliente registrato
- **Campi principali**: nome, cognome, telefono, data_nascita, città, password_hash, qr_code (univoco), livello (base/loyal/premium/vip), punti_fedelta, stato_account (attivo/disattivato), nota_staff
- **Relazioni**: prenotazioni, ingressi, consumi, fedelta, feedback, promozioni
- **Chi gestisce**: 
  - **Cliente**: modifica telefono, città, password
  - **Admin**: CRUD completo, modifica livello/punti, note staff, eliminazione

### 🎉 **Evento** (`app/models/eventi.py`)
**Cosa rappresenta**: Evento/serata programmata
- **Campi principali**: nome_evento, data_evento, tipo_musica, dj_artista, promozione (testo), capienza_max, categoria (reggaeton/techno/privato/altro), stato_pubblico (programmato/attivo/chiuso), is_staff_operativo (flag), cover_url, template_id
- **Relazioni**: prenotazioni, ingressi, consumi, fedelta, feedback
- **Chi gestisce**: 
  - **Pubblico**: visualizzazione eventi pubblici (stato_pubblico = "attivo" o "programmato")
  - **Admin**: CRUD completo, attivazione/chiusura pubblico, impostazione operativo staff, analytics

### 📅 **Prenotazione** (`app/models/prenotazioni.py`)
**Cosa rappresenta**: Prenotazione cliente per evento
- **Campi principali**: cliente_id, evento_id, tipo (lista/tavolo/prevendita), num_persone, orario_previsto, note, stato (attiva/no-show/usata/cancellata)
- **Relazioni**: cliente, evento, ingressi (1:N)
- **Chi gestisce**:
  - **Cliente**: creazione (solo lista/tavolo), cancellazione (entro 18:00 giorno evento)
  - **Admin**: CRUD completo, modifica stati, analytics

### 🚪 **Ingresso** (`app/models/ingressi.py`)
**Cosa rappresenta**: Registrazione ingresso cliente a evento
- **Campi principali**: cliente_id, evento_id, prenotazione_id (opzionale), staff_id, tipo_ingresso (lista/tavolo/omaggio/prevendita), orario_ingresso, note
- **Relazioni**: cliente, evento, prenotazione, staff
- **Chi gestisce**:
  - **Staff (ingressista)**: creazione tramite scanner unificato per evento operativo
  - **Admin**: CRUD completo, override capienza, analytics

### 🍾 **Consumo** (`app/models/consumi.py`)
**Cosa rappresenta**: Acquisto/consumo cliente durante evento
- **Campi principali**: cliente_id, evento_id, staff_id, prodotto_id (opzionale), prodotto (nome), importo, data_consumo, punto_vendita (bar/tavolo/privè), note
- **Relazioni**: cliente, evento, staff, prodotto_rel
- **Chi gestisce**:
  - **Staff (barista)**: creazione tramite scanner unificato + selezione prodotti per evento operativo
  - **Cliente**: visualizzazione storico propri consumi
  - **Admin**: CRUD completo, analytics

### ⭐ **Fedelta** (`app/models/fedeltà.py`)
**Cosa rappresenta**: Movimento punti fedeltà (assegnazione/detrazione)
- **Campi principali**: cliente_id, evento_id, punti (positivi/negativi), motivo, data_assegnazione
- **Relazioni**: cliente, evento
- **Chi gestisce**:
  - **Sistema**: assegnazione automatica (ingresso, consumo, no-show, feedback)
  - **Admin**: solo visualizzazione movimenti, modifica soglie livelli

### 🎁 **Promozione** (`app/models/promozioni.py`)
**Cosa rappresenta**: Promozione disponibile per clienti
- **Campi principali**: nome, descrizione, tipo (sconto_percentuale/sconto_fisso/omaggio/ingresso_gratis/consumo_gratis/altro), valore, condizioni, attiva, data_inizio/fine, livello_richiesto, punti_richiesti, auto_assegnazione
- **Relazioni**: clienti_promozioni (tabella di join `ClientePromozione`)
- **Chi gestisce**: **Admin**: CRUD completo, assegnazione a clienti

### 💬 **Feedback** (`app/models/feedback.py`)
**Cosa rappresenta**: Recensione cliente su evento
- **Campi principali**: cliente_id, evento_id, voto_musica (1-10), voto_ingresso (1-10), voto_ambiente (1-10), voto_servizio (1-10), data_feedback, note
- **Relazioni**: cliente, evento
- **Chi gestisce**:
  - **Cliente**: creazione (solo per eventi a cui ha partecipato, una volta sola)
  - **Admin**: visualizzazione, eliminazione

### 👨‍💼 **Staff** (`app/models/staff.py`)
**Cosa rappresenta**: Membro dello staff operativo
- **Campi principali**: nome, ruolo (admin/barista/ingressista), username (univoco), password_hash, attivo
- **Relazioni**: ingressi, consumi, log_attivita
- **Chi gestisce**: **Admin**: CRUD completo

### 📦 **Prodotto** (`app/models/prodotti.py`)
**Cosa rappresenta**: Prodotto del listino
- **Campi principali**: nome (univoco), prezzo, categoria, attivo
- **Relazioni**: consumi
- **Chi gestisce**: **Admin**: CRUD completo

### 📝 **LogAttivita** (`app/models/log_attivita.py`)
**Cosa rappresenta**: Log audit di azioni staff/admin
- **Campi principali**: tabella, record_id, staff_id, azione (insert/update/delete/evento_create/...), note, timestamp
- **Relazioni**: staff
- **Chi gestisce**: **Sistema**: registrazione automatica, **Admin**: visualizzazione

### 🎚️ **SogliaFedelta** (`app/models/soglie_fedelta.py`)
**Cosa rappresenta**: Soglie punti per livelli fedeltà
- **Campi principali**: livello (base/loyal/premium/vip), punti_min
- **Chi gestisce**: **Admin**: modifica soglie

---

## 🛣️ ROUTE E FUNZIONALITÀ

### 🔐 **AUTH** (`app/routes/auth.py`)
**Chi accede**: Tutti (pubblico)
- `/auth/register` - Registrazione nuovo cliente (genera QR code automatico)
- `/auth/login-cliente` - **Login dedicato clienti** (telefono + password)
- `/auth/login-staff` - **Login dedicato staff/admin** (username + password)
- `/auth/login` - Login legacy (deprecato, reindirizza a login-cliente)
- `/auth/logout` - Logout universale

**Sicurezza**: Rate limiting attivo (5 tentativi/minuto per login e registrazione)

---

### 👤 **CLIENTI** (`app/routes/clienti.py`)
**Chi accede**: Cliente loggato + Admin

#### Cliente:
- `/clienti/me` - Area personale (profilo, QR, prenotazioni future/passate, consumi recenti, barra fedeltà)
- `/clienti/me/edit` - Modifica profilo (telefono, città, password)

#### Admin (sezione "👥 Clienti"):
- `/dashboard/admin` - Dashboard principale (statistiche generali, trend, prossimo evento)
- `/clienti/admin/list` - Lista clienti (filtri: ricerca, stato, livello, paginazione)
- `/clienti/admin/<id>` - Dettaglio cliente (statistiche, storico completo, promozioni, modifica livello/punti/note)
- `/clienti/admin/<id>/set-level` - Modifica livello cliente
- `/clienti/admin/<id>/adjust-points` - Modifica punti fedeltà
- `/clienti/admin/<id>/delete` - Eliminazione cliente
- `/clienti/admin/<id>/set-note` - Modifica nota staff

**Sezioni secondarie**:
- `/fedelta/admin` - Dashboard fedeltà (movimenti, soglie)
- `/fedelta/admin/movimenti` - Lista movimenti fedeltà
- `/fedelta/admin/analytics` - Analytics fedeltà
- `/fedelta/admin/soglie` - Gestione soglie livelli

---

### 🎉 **EVENTI** (`app/routes/eventi.py`)
**Chi accede**: Pubblico (visualizzazione) + Staff + Admin

#### Pubblico:
- `/eventi/` - Lista eventi pubblici (filtri: categoria, data)
- `/eventi/<id>` - Dettaglio evento pubblico (con sezione feedback/consumi per eventi passati)

#### Staff:
- `/eventi/staff/select` - Selezione evento operativo
- `/eventi/staff/dashboard` - Dashboard evento attivo (ingressi totali, capienza, ritmo)

#### Admin (sezione "📅 Eventi"):
- `/eventi/admin/menu` - Menu gestione eventi
- `/eventi/admin` - Lista eventi (filtri: stato, periodo)
- `/eventi/admin/new` - Creazione evento (upload cover)
- `/eventi/admin/<id>` - Dettaglio evento (statistiche complete, liste prenotazioni/ingressi/consumi/feedback, analytics)
- `/eventi/admin/<id>/edit` - Modifica evento
- `/eventi/admin/<id>/duplicate` - Duplicazione evento
- `/eventi/admin/<id>/attiva-pubblico` - Attiva evento al pubblico
- `/eventi/admin/<id>/chiudi-pubblico` - Chiude evento al pubblico
- `/eventi/admin/<id>/close` - Chiusura evento (processa automaticamente no-show prenotazioni residue)
- `/eventi/admin/<id>/delete` - Eliminazione evento

---

### 📅 **PRENOTAZIONI** (`app/routes/prenotazioni.py`)
**Chi accede**: Cliente + Staff (solo visualizzazione) + Admin

#### Cliente:
- `/prenotazioni/nuova` - Creazione prenotazione (da dettaglio evento, tipo lista o tavolo)
- `/prenotazioni/nuova-tavolo` - Creazione prenotazione tavolo (flusso dedicato)
- `/prenotazioni/mie` - Lista prenotazioni cliente (attive future, usate, no-show) con verifica automatica stati
- `/prenotazioni/mie/<id>` - Dettaglio prenotazione (consumi, feedback)
- `/prenotazioni/<id>/cancella` - Cancellazione prenotazione (entro 18:00)

#### Staff:
- `/prenotazioni/staff/evento/<id>` - Lista prenotazioni per evento

#### Admin (sezione "📋 Operativo"):
- `/prenotazioni/admin/hub` - Hub operativo (panoramica eventi attivi)
- `/prenotazioni/admin` - Lista prenotazioni (filtri: evento, tipo, stato, paginazione)
- `/prenotazioni/admin/new` - Creazione prenotazione manuale
- `/prenotazioni/admin/<id>/edit` - Modifica prenotazione
- `/prenotazioni/admin/<id>` - Dettaglio prenotazione
- `/prenotazioni/admin/<id>/delete` - Eliminazione prenotazione
- `/prenotazioni/admin/<id>/analytics` - Analytics prenotazioni evento

**Workflow automatico**:
- Prenotazioni passate senza ingresso → automaticamente marcate "no-show" con penalità -5 punti
- Prenotazioni con ingresso → automaticamente marcate "usata"

---

### 🚪 **INGRESSI** (`app/routes/ingressi.py`)
**Chi accede**: Cliente (solo visualizzazione) + Staff + Admin

#### Cliente:
- `/ingressi/mie` - Storico ingressi cliente

#### Staff (Ingressista):
- `/staff/scan` - **Scanner unificato** (porta d'ingresso principale per tutti gli operatori)
  - Rileva automaticamente ruolo staff (ingressista/barista)
  - Ingressista: interfaccia per registrare ingressi
  - Barista: interfaccia per gestire consumi
- `/staff/scan/registra-ingresso` - API per registrare ingresso rapido (usato dallo scanner unificato)
- `/staff/scan/cliente-info` - API per ottenere info cliente dopo scansione QR
- `/ingressi/staff/scan` - Route legacy (deprecata, mantiene compatibilità)
- `/ingressi/staff/scan/check` - Pre-check JSON QR (validazione)
- `/ingressi/staff/scan/preview` - Preview cliente JSON prima check-in
- `/ingressi/staff/prenotati-count` - Contatore prenotati real-time JSON
- `/ingressi/staff/esito/<id>` - Pagina esito ingresso registrato

#### Admin (sezione "📋 Operativo"):
- `/ingressi/admin` - Lista ingressi (filtri: evento, tipo, staff, date, paginazione)
- `/ingressi/admin/new` - Creazione ingresso manuale
- `/ingressi/admin/<id>/edit` - Modifica ingresso
- `/ingressi/admin/<id>` - Dettaglio ingresso
- `/ingressi/admin/<id>/delete` - Eliminazione ingresso (undo prenotazione se collegata)
- `/ingressi/admin/<id>/analytics` - Analytics ingressi evento

---

### 🍾 **CONSUMI** (`app/routes/consumi.py`)
**Chi accede**: Cliente (solo visualizzazione) + Staff + Admin

#### Cliente:
- `/consumi/miei` - Storico consumi cliente

#### Staff (Barista):
- `/staff/scan` - **Scanner unificato** (porta d'ingresso principale)
  - Barista: interfaccia per visualizzare listino e registrare consumi
- `/consumi/staff/listino` - Listino prodotti per addebito (raggruppato per categoria)
- `/consumi/staff/listino/addebito` - Processa addebito prodotti selezionati
- `/consumi/staff/new` - Creazione consumo manuale (QR + prodotto)
- `/consumi/staff/ordini` - Pagina stampa ordini per evento (raggruppati per tavolo)
- `/consumi/staff/cliente-info` - Info cliente JSON (per pre-check)
- `/consumi/staff/search-cliente` - Ricerca cliente autocomplete JSON
- `/consumi/staff/precheck` - Pre-check JSON QR per consumo
- `/consumi/staff/scan` - Route legacy (deprecata, mantiene compatibilità)

#### Admin (sezione "📋 Operativo"):
- `/consumi/admin` - Lista consumi (filtri: evento, staff, punto vendita, prodotto, date)
- `/consumi/admin/new` - Creazione consumo manuale
- `/consumi/admin/<id>/edit` - Modifica consumo
- `/consumi/admin/<id>/delete` - Eliminazione consumo
- `/consumi/admin/<id>/analytics` - Analytics consumi evento

**Sicurezza**: Rate limiting attivo (30 addebiti/minuto per staff)

---

### ⭐ **FEDELTÀ** (`app/routes/fedelta.py`)
**Chi accede**: Cliente (solo visualizzazione) + Staff + Admin

#### Cliente:
- `/fedelta/mio` - Redirect a area personale (barra fedeltà integrata)

#### Staff:
- `/fedelta/staff/scan` - Scan QR per visualizzare saldo punti/livello cliente

#### Admin (sezione "👥 Clienti" → Soglie Fedeltà):
- `/fedelta/admin` - Dashboard fedeltà (statistiche, top clienti, distribuzione livelli, movimenti recenti)
- `/fedelta/admin/movimenti` - Lista movimenti fedeltà (filtri: evento, cliente, date, paginazione)
- `/fedelta/admin/analytics` - Analytics fedeltà (top clienti periodo, distribuzione tier, punti medi per evento)
- `/fedelta/admin/soglie` - Gestione soglie livelli (base/loyal/premium/vip)

**Regole automatiche punti**:
- Ingresso con prenotazione: +10 punti
- Ingresso senza prenotazione: +5 punti
- No-show prenotazione: -5 punti (assegnato automaticamente alla chiusura evento o verifica prenotazioni)
- Consumo: +1 punto ogni 10€ (arrotondato per difetto)
- Feedback: +2 punti

---

### 🎁 **PROMOZIONI** (`app/routes/promozioni.py`)
**Chi accede**: Admin (sezione "👥 Clienti")

- `/promozioni/admin` - Lista promozioni
- `/promozioni/admin/<id>` - Dettaglio promozione (statistiche assegnazioni)
- `/promozioni/admin/<id>/edit` - Modifica promozione
- `/promozioni/admin/<id>/delete` - Eliminazione promozione
- `/promozioni/admin/<id>/assign/<cliente_id>` - Assegnazione promozione a cliente
- `/promozioni/admin/<id>/unassign/<cliente_id>` - Rimozione promozione da cliente

**Nota**: Le promozioni possono essere assegnate automaticamente alla registrazione se `auto_assegnazione=True`.

---

### 💬 **FEEDBACK** (`app/routes/feedback.py`)
**Chi accede**: Cliente + Admin

#### Cliente:
- `/feedback/miei` - Redirect a prenotazioni
- `/feedback/nuovo` - Creazione feedback (solo per eventi con ingresso valido, una volta sola)

#### Admin (sezione "📋 Operativo"):
- `/feedback/admin` - Lista feedback (filtri: evento, cliente, date, paginazione, medie voti)
- `/feedback/admin/<id>/delete` - Eliminazione feedback

**Sicurezza**: Rate limiting attivo (5 feedback/minuto per cliente)

---

### 👨‍💼 **STAFF** (`app/routes/staff.py`)
**Chi accede**: Staff + Admin

#### Staff:
- `/staff/` - Home staff (reindirizza automaticamente a scanner unificato se ruolo operativo e evento attivo)
- `/staff/scan` - **Scanner unificato** (interfaccia principale operativa)
- `/staff/evento-attivo` - Visualizzazione evento operativo

#### Admin (sezione "⚙️ Impostazioni"):
- `/admin/staff/hub` - Hub impostazioni sistema
- `/admin/staff/` - Lista staff (filtri: ruolo, attivo)
- `/admin/staff/new` - Creazione staff
- `/admin/staff/<id>/edit` - Modifica staff
- `/admin/staff/<id>/delete` - Eliminazione staff
- `/admin/staff/evento-attivo` - Impostazione evento operativo staff

---

### 📦 **PRODOTTI** (`app/routes/prodotti.py`)
**Chi accede**: Pubblico (solo visualizzazione) + Admin

#### Pubblico:
- `/prodotti/listino` - Listino pubblico prodotti attivi

#### Admin (sezione "⚙️ Impostazioni"):
- `/prodotti/admin` - Lista prodotti (filtri: categoria, attivo)
- `/prodotti/admin/new` - Creazione prodotto
- `/prodotti/admin/<id>/edit` - Modifica prodotto
- `/prodotti/admin/<id>/delete` - Eliminazione prodotto

---

### 📝 **LOG ATTIVITÀ** (`app/routes/log_attivita.py`)
**Chi accede**: Admin (sezione "⚙️ Impostazioni")

- `/admin/logs/` - Lista log attività (filtri: tabella, staff, tipo, date, paginazione)

**Azioni loggate**:
- `insert`, `update`, `delete` - Operazioni CRUD standard
- `evento_create`, `evento_duplicate` - Creazione/duplicazione eventi
- `set_operativo`, `unset_operativo` - Impostazione evento operativo
- `event_close` - Chiusura evento
- `override_capienza` - Override capienza ingresso
- `prenotazione_usata`, `prenotazione_usata_automatica` - Prenotazione marcata come usata
- `ingresso_automatico`, `ingresso_registrato` - Ingresso registrato
- `no_show_assegnato`, `no_show_automatico` - No-show assegnato
- `prenotazione_create`, `prenotazione_update` - Gestione prenotazioni

---

### 🎚️ **FORMAT/TEMPLATE EVENTI** (`app/routes/format.py`)
**Chi accede**: Admin (sezione "⚙️ Impostazioni")

- `/format/admin` - Lista template eventi
- `/format/admin/new` - Creazione template
- `/format/admin/<id>/edit` - Modifica template
- `/format/admin/<id>/delete` - Eliminazione template

**Nota**: I template possono essere selezionati durante la creazione evento per pre-compilare campi.

---

## 🔄 FLUSSI OPERATIVI PRINCIPALI

### 1. **Registrazione Cliente**
1. Cliente si registra su `/auth/register` → genera QR code automatico univoco
2. Se promozioni con `auto_assegnazione=True` → assegnate automaticamente
3. Cliente può prenotare eventi pubblici

### 2. **Prenotazione Evento**
1. Cliente visualizza eventi pubblici (`stato_pubblico = "attivo"` o `"programmato"`)
2. Cliente crea prenotazione (lista o tavolo) - una sola prenotazione attiva per evento
3. Admin può modificare/gestire prenotazioni
4. Cliente può cancellare entro 18:00 del giorno evento
5. **Al termine evento**: Sistema verifica automaticamente stati:
   - Se cliente ha ingresso → prenotazione marcata "usata"
   - Se cliente non ha ingresso → prenotazione marcata "no-show" con penalità -5 punti

### 3. **Serata Evento (Staff Operativo)**
1. **Admin** imposta evento operativo (`is_staff_operativo = True`)
2. **Staff** accede a `/staff/scan` (scanner unificato):
   - Sistema rileva automaticamente ruolo (ingressista/barista)
   - **Ingressista**: Interfaccia per scansionare QR e registrare ingressi
     - Se cliente ha prenotazione attiva → tipo da prenotazione, marca prenotazione "usata"
     - Se no prenotazione → tipo "lista"
     - Controllo capienza (con override admin)
     - Assegnazione punti: +10 (con prenotazione) o +5 (senza)
   - **Barista**: Interfaccia per scansionare QR e gestire consumi
     - Verifica ingresso valido
     - Visualizza listino prodotti (raggruppato per categoria)
     - Selezione prodotti → addebito
     - Assegnazione punti: +1 ogni 10€
3. Cliente può lasciare feedback dopo evento (una volta sola, solo se ha ingresso)

### 4. **Chiusura Evento**
1. Admin chiude evento (`stato_pubblico = "chiuso"`)
2. **Sistema processa automaticamente**:
   - Prenotazioni residue attive senza ingresso → marcate "no-show" → -5 punti
   - Prenotazioni con ingresso → marcate "usata"
3. Evento non più operativo per staff

### 5. **Sistema Fedeltà**
- Punti assegnati automaticamente: ingressi, consumi, feedback
- Punti detratti: no-show (automatico)
- Livelli calcolati automaticamente in base a soglie configurabili
- Admin può modificare manualmente punti/livelli clienti

---

## 🛡️ SICUREZZA E VALIDAZIONI

### Autenticazione:
- **Login separati**: `/auth/login-cliente` (telefono) e `/auth/login-staff` (username)
- **Rate limiting**: 
  - Login: 5 tentativi/minuto
  - Registrazione: 5 registrazioni/minuto
  - Creazione prenotazioni: 10 prenotazioni/minuto per cliente
  - Feedback: 5 feedback/minuto per cliente
  - Addebito consumi staff: 30 addebiti/minuto
- **Password**: Hash sicuro con upgrade automatico da password in chiaro legacy

### Decoratori di autorizzazione:
- `@require_cliente` - Richiede `session["cliente_id"]`, abort 401
- `@require_staff` - Richiede `session["staff_id"]`, redirect a `/auth/login-staff`
- `@require_admin` - Richiede `session["staff_role"] == "admin"` o `session["admin_user"]`, abort 403

### Validazioni principali:
- **Unicità**: Un cliente può avere una sola prenotazione attiva per evento
- **Capienza**: Blocco ingressi se capienza raggiunta (override admin disponibile)
- **Doppio ingresso**: Prevenzione ingressi duplicati per stesso evento (constraint database)
- **Feedback**: Un solo feedback per evento per cliente, solo se ha ingresso valido
- **Cancellazione prenotazione**: Solo entro 18:00 del giorno evento
- **Consumi**: Solo per clienti con ingresso valido all'evento operativo
- **Workflow automatico**: Verifica e aggiornamento stati prenotazioni (usata/no-show) automatico

---

## 📈 ANALYTICS E REPORTING

### Dashboard Admin (📊 Dashboard):
- Statistiche generali (clienti, eventi, ingressi, consumi)
- Trend temporali (grafici ingressi/consumi)
- Top clienti per punti/spesa
- Distribuzione livelli fedeltà
- Medie feedback globali
- Prossimo evento operativo

### Hub Operativo (📋 Operativo):
- Panoramica evento attivo
- Statistiche real-time (prenotazioni, ingressi, consumi)
- Quick links alle sezioni operative

### Hub Impostazioni (⚙️ Impostazioni):
- Statistiche staff, prodotti, format
- Quick links alle configurazioni

### Analytics per Evento:
- Prenotazioni: totale, per tipo, per stato, persone tavoli, no-show
- Ingressi: totale, per tipo, per staff, ritmo temporale, capienza
- Consumi: totale, per prodotto, per punto vendita, per staff, scontrino medio, top spender
- Feedback: medie voti (musica, ingresso, ambiente, servizio)

---

## 🔧 UTILITIES E HELPERS

### Helper Centralizzati (`app/utils/helpers.py`):
- `get_current_cliente_id()` - ID cliente da sessione
- `get_current_cliente(db)` - Oggetto cliente loggato
- `get_cliente_by_qr(db, qr)` - Cerca cliente per QR code
- `cliente_has_ingresso(db, cliente_id, evento_id)` - Verifica ingresso
- `get_current_staff_id()` - ID staff da sessione
- `get_current_staff_role()` - Ruolo staff da sessione
- `is_staff_admin()` / `is_staff_operative()` - Controlli ruolo
- `get_evento_attivo(db)` - Wrapper per evento operativo

### Altri Utilities:
- `app/utils/auth.py` - Hash/verifica password con upgrade automatico
- `app/utils/decorators.py` - Decoratori autorizzazione
- `app/utils/qr.py` - Generazione QR code clienti univoci
- `app/utils/events.py` - Gestione evento operativo (config_app come fonte unica)
- `app/utils/workflow.py` - **Logica workflow cliente centralizzata**:
  - `WorkflowState` - Stato aggregato cliente/evento
  - `processa_no_show_automatico()` - Processa automaticamente prenotazioni passate
  - `verifica_e_aggiorna_prenotazione_cliente()` - Verifica singola prenotazione
  - `can_cliente_see_feedback_button()` - Verifica disponibilità feedback
  - `evento_stato_badge()` - Badge stato evento per UI
- `app/utils/limiter.py` - **Rate limiting centralizzato** (Flask-Limiter)

---

## 🎨 STRUTTURA INTERFACCE

### Pannello Admin (5 sezioni principali):
1. **📊 Dashboard** - Panoramica e statistiche generali
2. **📅 Eventi** - Gestione completa eventi e programmazione
3. **👥 Clienti** - Gestione anagrafica, fedeltà e promozioni
   - Sottosezioni: Anagrafica, Punti Fedeltà, Movimenti, Analytics, Feedback
4. **📋 Operativo** - Gestione in tempo reale
   - Sottosezioni: Hub, Prenotazioni, Ingressi, Consumi, Feedback
5. **⚙️ Impostazioni** - Configurazione sistema
   - Sottosezioni: Hub, Staff, Listino, Format, Soglie Fedeltà, Log Attività

### Interfaccia Staff:
- **Scanner Unificato** (`/staff/scan`): Interfaccia principale operativa
  - Rilevamento automatico ruolo
  - Interfaccia dinamica in base a ruolo (ingressista/barista)
  - Scanner QR integrato
  - Ricerca clienti integrata
  - Azioni contestuali per ruolo

### Template:
- **Separazione login**: `clienti/login.html` e `staff/login.html`
- **Template condivisi**: Solo errori (401, 403, 404) e base
- **Template clienti**: Area personale, prenotazioni, feedback
- **Template staff**: Scanner unificato, dashboard, listino
- **Template admin**: Dashboard, gestione entità, analytics

---

## 🔄 MIGRAZIONI E COMPATIBILITÀ

### Route Legacy Mantenute:
- `/auth/login` - Reindirizza a `/auth/login-cliente` (retrocompatibilità)
- `/auth/login-admin` - Reindirizza a `/auth/login-staff` (retrocompatibilità)
- `/ingressi/staff/scan` - Mantiene funzionalità (scanner legacy)
- `/consumi/staff/scan` - Mantiene funzionalità (scanner legacy)

### Upgrade Automatici:
- **Password**: Upgrade automatico da password in chiaro a hash durante login
- **Prenotazioni**: Verifica e aggiornamento automatico stati (usata/no-show)
- **Eventi**: Processamento automatico no-show alla chiusura evento

---

**Fine briefing** 🎉
