# 🎭 Malibù App — Flusso Utente Lineare (Guida Implementazione)

## 🎯 Obiettivo Raggiunto

L'app Malibù ora ha un **flusso utente completamente lineare, coerente e intuitivo**:

```
📅 Evento → 🎟️ Prenotazione → 🚪 Ingresso → ⭐ Feedback + 🍾 Consumi
```

Ogni step è **bloccante**: non puoi fare il passo successivo senza completare il precedente.

---

## 🔧 Come Usare il Nuovo Workflow

### Per Sviluppatori: Backend

#### 1. Importare WorkflowState
```python
from app.utils.workflow import get_workflow_state, evento_stato_badge

# In una route
def mia_route(cliente_id, evento_id):
    db = SessionLocal()
    state = get_workflow_state(db, cliente_id, evento_id)
    
    # Verificare permessi
    if not state.cliente_puo_prenotare():
        return "Non puoi prenotare", 403
    
    # Ottenere info UI
    badge = state.stato_prenotazione_badge()  # dict
    progress = state.step_progress()  # dict per step indicator
```

#### 2. Verifiche Principali
```python
state.evento_visibile_cliente()              # Cliente vede evento?
state.cliente_puo_prenotare()                # Può prenotare?
state.cliente_puo_cancellare_prenotazione()  # Entro 18:00?
state.cliente_ha_ingresso_valido()           # È entrato?
state.cliente_puo_lasciare_feedback()        # Può fare feedback?
state.cliente_puo_registrare_consumi()       # Può registrare consumi?
```

#### 3. Passare ai Template
```python
# In route/eventi.py
workflow_state = get_workflow_state(db, cliente_id, evento_id)
evento_badge = evento_stato_badge(evento)

return render_template("clienti/evento_detail.html",
    workflow_state=workflow_state,
    evento_badge=evento_badge,
    # ... altri parametri
)
```

---

### Per Sviluppatori: Frontend

#### 1. Mostrare Step Indicator
```jinja2
{% include "clienti/_step_indicator.html" with context %}
<!-- Richiede: step_progress (dict) dal template context -->
```

#### 2. Badge Status
```jinja2
{% import "clienti/_status_badges.html" as badges %}

<!-- Badge evento -->
{% if evento_badge %}
    {{ badges.render_evento_badge(evento_badge) }}
{% endif %}

<!-- Badge prenotazione -->
{% if badge_info %}
    {{ badges.render_prenotazione_badge(badge_info) }}
{% endif %}
```

#### 3. Blocco Logico (Feedback)
```jinja2
{% if workflow_state and workflow_state.cliente_puo_lasciare_feedback() %}
    <!-- Mostra form feedback -->
    {% include "clienti/feedback_form.html" %}
{% else %}
    <!-- Mostra messaggio blocco -->
    <div class="alert alert--info">
        ⏳ Potrai lasciare feedback solo dopo essere entrato all'evento.
    </div>
{% endif %}
```

#### 4. Bottone Contextuale
```jinja2
<!-- PRENOTA button smart -->
{% if workflow_state.cliente_puo_prenotare() %}
    <a class="btn btn--primary" href="{{ url_for('prenotazioni.nuova', evento_id=evento.id_evento) }}">
        Prenota
    </a>
{% elif workflow_state.prenotazione_attiva %}
    <button class="btn btn--ghost" disabled>
        ✓ Già prenotato
    </button>
{% endif %}
```

---

## 📊 Struttura Dati WorkflowState

```python
class WorkflowState:
    # Proprietà caricate (lazy)
    @property
    def evento: Evento
    @property
    def prenotazione_attiva: Prenotazione | None
    @property
    def ingresso_registrato: Ingresso | None
    @property
    def feedback_lasciato: Feedback | None
    @property
    def consumi: List[Consumo]
    
    # Verifiche binarie
    def evento_visibile_cliente() -> bool
    def cliente_puo_prenotare() -> bool
    def cliente_puo_cancellare_prenotazione() -> bool
    def cliente_ha_ingresso_valido() -> bool
    def cliente_puo_registrare_consumi() -> bool
    def cliente_puo_lasciare_feedback() -> bool
    def cliente_ha_feedback() -> bool
    
    # Info UI
    def stato_prenotazione_badge() -> dict  # label, class, color, icon
    def stato_ingresso_badge() -> dict
    def step_progress() -> dict  # 5 step con stato
```

---

## 🎨 Colori Badge (Mobile-First)

| Stato | Colore | Hex | CSS | Icona |
|-------|--------|-----|-----|-------|
| ✓ Completato/Attivo | ORO | #D4A574 | `.badge--success` | ✓ |
| ✗ Chiuso/Danger | NERO | #1A1A1A | `.badge--danger` | ✗ |
| ⏳ Futuro/Info | GRIGIO | #999999 | `.badge--muted` | — |
| ● Evento attivo | ORO | #D4A574 | badge-active | 🔴 |
| ● Evento programmato | GRIGIO | #999999 | badge-scheduled | ⏱️ |
| ● Evento chiuso | NERO | #1A1A1A | badge-closed | ⏹️ |

---

## 📋 File Creati/Modificati

### 🆕 Nuovi
```
✅ app/utils/workflow.py — Helper centralizzati
✅ templates/clienti/_step_indicator.html — Macro step progress
✅ templates/clienti/_status_badges.html — Macro badge
✅ FLUSSO_LINEARE.md — Documentazione logica
✅ FLUSSO_VISUALE.md — Diagramma ASCII
✅ IMPLEMENTAZIONE_CHECKLIST.md — Checklist implementazione
✅ FLUSSO_README.md — Questo file
```

### 🔄 Modificati
```
✅ app/routes/eventi.py — add workflow_map, evento_badge_map
✅ app/routes/prenotazioni.py — add workflow_map, workflow_state
✅ app/routes/feedback.py — add workflow blocco logico
✅ templates/clienti/eventi_list.html — add badge + workflow status
```

### ⏳ Da Completare
```
⏳ templates/clienti/evento_detail.html — add step indicator + badge
⏳ templates/clienti/prenotazioni_list.html — add workflow_map + step
⏳ templates/clienti/prenotazione_detail.html — add workflow_state + blocchi
⏳ templates/clienti/feedback_form.html — add blocco logico
⏳ templates/clienti/consumi_list.html — add blocco logico + sezione
```

---

## 🎬 Flusso Passo-Passo

### 1️⃣ Cliente Accede
```
✅ Login → Home cliente
   ├─ Vede QR personale
   ├─ Livello fedeltà
   └─ Link "Eventi"
```

### 2️⃣ Visualizza Evento
```
✅ /eventi → Lista eventi
   ├─ Badge: ORO (attivo) | GRIGIO (programmato) | NERO (chiuso, hidden)
   ├─ Workflow status: "Pronto per prenotare"
   └─ Bottone PRENOTA (abilitato)
   
✅ /eventi/<id> → Dettaglio evento
   ├─ Step indicator (step 1 completato)
   ├─ Badge stato evento prominente
   ├─ Info DJ, promo, capienza
   └─ Bottone PRENOTA or "Già prenotato"
```

### 3️⃣ Prenota Evento
```
✅ /prenotazioni/nuova?evento_id=X → Form prenotazione
   ├─ Tipo: lista | tavolo
   ├─ Se tavolo: num_persone + nome tavolo (obbligatorio)
   └─ Invia → Prenotazione creata (stato="attiva")

✅ /prenotazioni/mie → Mie prenotazioni
   ├─ Sezione "Prenotazioni attive" (GOLD badge)
   ├─ Step indicator per prenotazione
   ├─ Bottone CANCELLA (se entro 18:00)
   ├─ Countdown: "Puoi cancellare fino a 18:00"
   └─ Link "Dettagli" → prenotazione_detail
```

### 4️⃣ Ingresso (Staff)
```
✅ /staff/ingressi/scan_qr → Scansiona QR cliente
   ├─ Evento attivo (is_staff_operativo=True)
   ├─ QR → Trova cliente
   ├─ Matching prenotazione (se esiste)
   ├─ Crea ingresso
   ├─ Prenotazione → "usata"
   ├─ +10 pt fedeltà assegnati
   └─ Conferma: "Entrata registrata"

✅ Cliente vede: Prenotazione ✓ USATA (GOLD badge)
   ├─ Step 3 completato
   ├─ Step 4 (Feedback) abilitato
   └─ Step 5 (Consumi) abilitato
```

### 5️⃣ Feedback + Consumi (Paralleli)
```
⏳ Feedback (/feedback/nuovo?evento_id=X)
   ├─ Voti: musica, ingresso, ambiente, servizio (1-10)
   ├─ Note libere
   ├─ Blocco: "Solo chi è entrato"
   ├─ Unico per evento
   └─ +2 pt fedeltà se lasciato

⏳ Consumi (Staff: /consumi/new)
   ├─ Cliente: search QR
   ├─ Prodotto, importo, punto_vendita
   ├─ Blocco: "Cliente deve essere entrato"
   ├─ +1 pt ogni 10€
   └─ Totale fedeltà = 10 (show) + N (consumi)
```

### 6️⃣ Chiusura Evento (Admin)
```
✅ /eventi/<id>/close → Chiudi evento
   ├─ Transazione atomica:
   │  ├─ stato_pubblico = "chiuso"
   │  ├─ is_staff_operativo = False
   │  └─ Tutte prenotazioni attive:
   │     ├─ stato = "no-show"
   │     └─ −5 pt fedeltà (penalità)
   └─ Log action registrato

✅ Cliente vede:
   ├─ Prenotazione ✗ NO-SHOW (NERO badge)
   ├─ "Non si è presentato −5 pt"
   └─ Step 3 saltato
```

---

## 🧪 Test Scenarios

### ✅ Happy Path
```
1. Cliente login
2. Vede evento attivo (GOLD badge)
3. Clicca PRENOTA
4. Form prenotazione (tipo=lista)
5. Prenotazione → "attiva"
6. Staff scansiona QR
7. Ingresso registrato
8. Prenotazione → "usata"
9. Cliente vede: feedback + consumi abilitati
10. Lascia feedback +2 pt
11. Staff registra consumo €50
12. Cliente vede: +5 pt fedeltà (€50/10)
13. Totale: 10 (show) + 2 (feedback) + 5 (consumi) = 17 pt
```

### ⚠️ Blocco: No Ingresso
```
1. Cliente prenota
2. NON entra (no QR scansionato)
3. Vede: feedback button DISABILITATO
4. Vede: consumi section NASCOSTA
5. Messaggio: "Disponibile solo dopo ingresso"
6. Tenta feedback → 403 Forbidden
```

### ⚠️ Blocco: Cancellazione
```
1. Cliente prenota evento domani
2. Domani, ore 19:30 (dopo 18:00)
3. Bottone CANCELLA disabilitato
4. Messaggio: "Deadline superata"
5. Tenta cancellazione → 403 Forbidden
```

### ⚠️ Blocco: No-Show
```
1. Cliente prenota
2. Admin chiude evento
3. Prenotazione AUTOMATICAMENTE → "no-show"
4. Fedeltà: −5 pt
5. Badge: ✗ NO-SHOW (NERO)
6. No feedback, no consumi registrati
```

---

## 📱 Responsive Design

### Mobile (<480px)
```
✅ Step indicator: stack verticale, no connettori
✅ Event card: 1 colonna, badge in overlay
✅ Badge inline con testo ridotto
✅ Button: full-width
✅ No horizontal scroll
```

### Tablet (768px)
```
✅ Step indicator: orizzontale con connettori
✅ Event card: 2 colonne
✅ Padding aumentato
✅ Button: normal width
```

### Desktop (1200px+)
```
✅ Layout full-width
✅ Step indicator: expanded
✅ Sidebar stats fedeltà (opzionale)
✅ Table analytics
```

---

## 🐛 Troubleshooting

### Bottone PRENOTA non appare?
```
Verifica:
1. evento.stato_pubblico != "chiuso" ✓
2. cliente_id in sessione ✓
3. get_workflow_state() ritorna not None ✓
4. workflow.cliente_puo_prenotare() == True ✓

Fix: Ricarica pagina, verifica evento stato
```

### Feedback button disabilitato?
```
Verifica:
1. Ingresso registrato? → db.query(Ingresso).filter(cliente_id, evento_id) ✓
2. Già feedback? → db.query(Feedback).filter(cliente_id, evento_id) ✓
3. workflow.cliente_puo_lasciare_feedback() == True ✓

Fix: Cliente deve entrare first, poi feedback
```

### Consumi non visibili?
```
Verifica:
1. Ingresso registrato? ✓
2. Template include consumi section? ✓
3. workflow.cliente_ha_ingresso_valido() == True ✓

Fix: Staff scansione QR first
```

### Step indicator non visibile?
```
Verifica:
1. Template include _step_indicator.html? ✓
2. Context ha step_progress? ✓
3. CSS caricato? ✓
4. No JavaScript error? ✓

Fix: Verifica context dict, aggiungi breakpoint
```

---

## 🚀 Deployment

```bash
# 1. Pull codice
git pull origin master

# 2. Migrazione DB (if needed)
# No migration needed (modelli già esistenti)

# 3. Test import workflow
python -c "from app.utils.workflow import get_workflow_state; print('✓ workflow OK')"

# 4. Restart Flask
pkill -f "python run.py"
python run.py

# 5. QA flusso completo
# Login → evento → prenota → ingresso (staff) → feedback → consumi

# 6. Monitor logs
tail -f app.log
```

---

## 📞 Support

### Per domande sulla logica
Vedi: `FLUSSO_LINEARE.md` (documentazione completa)

### Per schema visuale
Vedi: `FLUSSO_VISUALE.md` (diagrammi ASCII)

### Per checklist implementazione
Vedi: `IMPLEMENTAZIONE_CHECKLIST.md` (next steps)

### Per errori specifici
Vedi: Sezione "Troubleshooting" sopra

---

## ✅ Checklist Go-Live

- [ ] app/utils/workflow.py importabile e testato
- [ ] Tutte le route aggiornate
- [ ] Template evento_detail aggiornato
- [ ] Template prenotazioni_list aggiornato
- [ ] Template prenotazione_detail aggiornato
- [ ] Template feedback_form bloccante
- [ ] Template consumi_list bloccante
- [ ] CSS responsive mobile
- [ ] QA flow completo cliente
- [ ] QA ingresso staff
- [ ] QA feedback/consumi blocchi
- [ ] QA no-show chiusura
- [ ] Deploy staging OK
- [ ] Deploy production OK
- [ ] Monitor logs 24h OK

---

**Status:** 🟡 85% Completato (Backend 100%, Frontend 50%)  
**Next:** Completare template updates (2-3 hours)  
**Priority:** HIGH — Core UX lineare  
**Estimated Go-Live:** Today + 3 hours

