# 🎬 FLUSSO UTENTE LINEARE — Malibù App

## Panoramica Generale

Il flusso è **completamente lineare e dipendente da step precedenti**:

```
📅 EVENTO
  ↓ (cliente vede solo eventi attivi/programmati)
  ↓
🎟️ PRENOTAZIONE  
  ↓ (solo se ha prenotazione attiva)
  ↓
🚪 INGRESSO (scansione QR staff)
  ↓ (solo se ha ingresso valido = "show")
  ↓
⭐ FEEDBACK + 🍾 CONSUMI (paralleli, dopo ingresso)
```

---

## 1️⃣ EVENTO (📅)

### Logica Backend
- **Visibilità cliente**: Solo eventi con `stato_pubblico IN ("programmato", "attivo")`
- **Eventi chiusi**: Hidden (stato = "chiuso")
- **Admin può**:
  - Creare/modificare/duplicare/chiudere evento
  - Impostare evento come operativo (staff lavora su questo)

### Condizioni di Accesso
- ✅ Cliente può VEDERE evento → deve avere `evento.stato_pubblico != "chiuso"`
- ✅ Cliente può PRENOTARE → evento visibile + nessuna prenotazione attiva

### Badge Stato Evento
| Stato | Badge | Colore | Icona |
|-------|-------|--------|-------|
| attivo | ● ATTIVO ADESSO | ORO | 🔴 |
| programmato | ● Programmato | GRIGIO | ⏱️ |
| chiuso | ● Chiuso | NERO | ⏹️ |

### Template
- `templates/clienti/eventi_list.html` → lista eventi con badge + workflow status
- `templates/clienti/evento_detail.html` → dettaglio + bottone PRENOTA (se consentito)
- `templates/public/listino_prodotti.html` → listino disponibile sempre

---

## 2️⃣ PRENOTAZIONE (🎟️)

### Logica Backend
- **Regola universale**: Un cliente ha **MAX 1 prenotazione ATTIVA** per evento
- **Tipi consentiti**: `lista` | `tavolo` (nome obbligatorio) | `prevendita`
- **Cancellazione**: Entro le 18:00 del giorno dell'evento
- **Transizioni stato**:
  - `attiva` → `usata` (quando ingresso registrato)
  - `attiva` → `no-show` (evento chiuso, no-show −5 pt)
  - `attiva` → `cancellata` (cliente entro deadline)

### Condizioni di Accesso
- ✅ Cliente può PRENOTARE → evento aperto + nessuna prenotazione attiva
- ✅ Cliente può CANCELLARE → prenotazione attiva + prima delle 18:00 del giorno evento
- ✅ Staff VISUALIZZA prenotazioni evento (read-only)

### Badge Prenotazione
| Stato | Badge | Colore | Significato |
|-------|-------|--------|------------|
| attiva | 🎟️ Prenotazione attiva | ORO | Pronto per entrare |
| usata | ✓ Usata (ingresso valido) | ORO | Entrato, può fare feedback |
| no-show | ✗ No-show (−5 pt) | NERO | Non si è presentato |
| cancellata | 🚫 Cancellata | GRIGIO | Prenotazione annullata |

### Template
- `templates/clienti/prenotazioni_new.html` → form nuova prenotazione (attivo se consentito)
- `templates/clienti/prenotazioni_list.html` → lista mie prenotazioni + workflow progress
- `templates/clienti/prenotazione_detail.html` → dettaglio prenotazione (se usata)

---

## 3️⃣ INGRESSO (🚪)

### Logica Backend
- **Registrazione**: Staff scansiona QR cliente → crea ingresso
- **Collegamento**: Se cliente ha prenotazione attiva → eredita tipo_ingresso da prenotazione
- **Senza prenotazione**: Ingresso generico lista `tipo_ingresso = "lista"`
- **Blocco doppi ingressi**: DB constraint unico (cliente_id, evento_id, orario_ingresso)
- **Capienza**: Warning se superata

### Transizioni Stato
```
Prenotazione attiva + QR scansionato
  ↓
  Ingresso registrato
  ↓
  Prenotazione → stato = "usata"
  ↓
  Fedeltà: +10 pt (show)
```

### Condizioni di Accesso
- ✅ Staff può SCANSIONARE QR → solo evento operativo attivo
- ✅ Client vede INGRESSO nel workflow → visibilità sola lettura
- ✅ Warning capienza → se ingressi_tot > capienza_max

### Template
- `templates/staff/ingressi_scan_qr_evento.html` → scansione QR (evento attivo)
- `templates/staff/ingressi_esito.html` → confermato ingresso
- `templates/clienti/ingressi_list.html` → cronologia ingressi cliente

---

## 4️⃣ FEEDBACK (⭐)

### Logica Backend
- **Requisito**: Cliente MUST avere ingresso valido (show)
- **Campi**: Voto musica (1-10) + ingresso (1-10) + ambiente (1-10) + servizio (1-10) + note
- **Unico per evento**: Un solo feedback per cliente per evento
- **Blocco**: Se cliente non ha ingresso → no feedback button

### Condizioni di Accesso
- ✅ Cliente può LASCIARE FEEDBACK → ha ingresso + non ha già feedback
- ✅ Feedback visibile solo se cliente è entrato (show)
- ✅ Admin vede tutti i feedback → analytics media voti

### Badge Feedback
| Stato | Label | Icona |
|-------|-------|-------|
| completato | ⭐ Feedback lasciato | ✓ |
| disponibile | ⭐ Lascia una recensione | ← pulsante abilitato |
| bloccato | ⏳ Disponibile solo se entrato | ✗ pulsante disabilitato |

### Template
- `templates/clienti/feedback_form.html` → form feedback (se consentito)
- `templates/clienti/feedback_miei.html` → feedback lasciati cliente

---

## 5️⃣ CONSUMI (🍾)

### Logica Backend
- **Requisito**: Cliente MUST avere ingresso valido
- **Registrazione**: Staff registra consumo (prodotto, importo, punto_vendita)
- **Fedeltà**: +1 pt ogni 10€ di consumo
- **Punto vendita**: bar | tavolo | privè

### Transizioni Fedeltà
```
Ingresso registrato (show) = +10 pt base
  ↓
Per ogni 10€ consumo = +1 pt aggiuntivo
  ↓
Totale punti = 10 + (importo_totale // 10)
```

### Condizioni di Accesso
- ✅ Staff può REGISTRARE CONSUMO → cliente ha ingresso valido
- ✅ Warning se cliente non risulta entrato
- ✅ Cliente vede CONSUMI propri → after ingresso

### Template
- `templates/staff/consumi_new.html` → form nuovo consumo (se cliente entrato)
- `templates/clienti/consumi_list.html` → cronologia consumi cliente

---

## 🎛️ CHIUSURA EVENTO (Admin)

### Azioni Atomiche
1. **Stato evento**: `stato_pubblico = "chiuso"`
2. **Disattiva operatività staff**: `is_staff_operativo = False`
3. **Prenotazioni residue attive** → `stato = "no-show"` + **-5 pt fedeltà**
4. **Log action**: Registra chiusura evento

### Ledger Fedeltà
```python
# Alla chiusura evento:
for pren in event.prenotazioni:
    if pren.stato == "attiva":
        pren.stato = "no-show"
        fedelta_record = Fedelta(
            cliente_id=pren.cliente_id,
            evento_id=pren.evento_id,
            punti=-5,
            motivo="No-show: non si è presentato"
        )
```

### Template
- Admin vede bottone "Chiudi evento" → conferma atomica

---

## 🗂️ STRUTTURA HELPER (app/utils/workflow.py)

### Class: `WorkflowState`
Aggrega lo stato completo di un cliente per un evento.

```python
state = WorkflowState(cliente_id=123, evento_id=456, db=db)

# Verifiche binarie
state.evento_visibile_cliente()           # bool
state.cliente_puo_prenotare()             # bool
state.cliente_puo_cancellare_prenotazione()  # bool
state.cliente_ha_ingresso_valido()        # bool
state.cliente_puo_registrare_consumi()    # bool
state.cliente_puo_lasciare_feedback()     # bool
state.cliente_ha_feedback()               # bool

# Info UI
state.stato_prenotazione_badge()          # dict badge
state.stato_ingresso_badge()              # dict badge
state.step_progress()                     # dict step indicator

# Relazioni caricate
state.prenotazione_attiva                 # Prenotazione | None
state.ingresso_registrato                 # Ingresso | None
state.feedback_lasciato                   # Feedback | None
state.consumi                             # List[Consumo]
```

### Funzioni Helper

```python
from app.utils.workflow import (
    get_workflow_state,
    can_cliente_see_feedback_button,
    can_cliente_see_consumi_section,
    evento_stato_badge
)

# Uso in route
state = get_workflow_state(db, cliente_id, evento_id)
if state.cliente_puo_prenotare():
    # Mostra bottone prenota
    pass

# Uso in template
{% if state.cliente_puo_lasciare_feedback() %}
    {% include "clienti/feedback_form.html" %}
{% endif %}
```

---

## 🎨 COLORI + BADGE (Mobile-First)

### Palette Colori
| Uso | Colore | Hex | CSS |
|-----|--------|-----|-----|
| **Completato/Attivo** | ORO | #D4A574 | `.badge--success` |
| **Disabilitato/Passato** | NERO | #1A1A1A | `.badge--danger` |
| **Futuro/Info** | GRIGIO | #999999 | `.badge--muted` |

### CSS Reusable
```css
/* Badge oro (completato/attivo) */
.badge--success {
    background: #FFF8E7;
    color: #D4A574;
    border: 1px solid #E8C79C;
}

/* Badge nero (closed/danger) */
.badge--danger {
    background: #f5f5f5;
    color: #c41e3a;
    border: 1px solid #ddd;
}

/* Step indicator */
.step-indicator__step--completed .step-indicator__circle {
    background: #D4A574;
    color: white;
}

.step-indicator__step--current .step-indicator__circle {
    border-color: #D4A574;
    box-shadow: 0 0 0 3px rgba(212, 165, 116, 0.2);
}
```

---

## 📱 Responsive Design

### Mobile (<480px)
- Step indicator: stack verticale, connettori nascosti
- Event card: layout singola colonna
- Badge: inline, testo ridotto

### Tablet (768px)
- Step indicator: orizzontale con connettori
- Event card: 2 colonne
- Padding aumentato

### Desktop (1200px+)
- Layout completo
- Sidebar eventuale per stat fedeltà
- Tabelle analytics full-width

---

## 🔄 Route Finali Cliente (lineare)

| Endpoint | Descrizione | Workflow |
|----------|-------------|----------|
| `/eventi` | Lista eventi pubblici | EVENTO |
| `/eventi/<id>` | Dettaglio evento + PRENOTA | EVENTO |
| `/prenotazioni/nuova?evento_id=X` | Form prenotazione | EVENTO → PRENOTAZIONE |
| `/prenotazioni/mie` | Mie prenotazioni | PRENOTAZIONE |
| `/prenotazioni/mie/<id>` | Dettaglio prenotazione (se usata) | PRENOTAZIONE → INGRESSO → FEEDBACK/CONSUMI |
| `/prenotazioni/<id>/cancella` | Cancella prenotazione | PRENOTAZIONE (disattiva) |
| `/ingressi/<id>` | Cronologia ingressi | INGRESSO (read-only) |
| `/feedback/nuova?evento_id=X` | Lascia feedback | INGRESSO → FEEDBACK |
| `/consumi/<id>` | Cronologia consumi | INGRESSO → CONSUMI |

---

## 🧑‍💼 Ruoli e Permessi

### CLIENTE
- ✅ Vedi eventi pubblici
- ✅ Prenota fino a evento attivo
- ✅ Cancella prenotazione (entro 18:00)
- ✅ Visualizza proprio QR
- ✅ Lascia feedback (se entrato)
- ✅ Visualizza propri consumi (se entrato)
- ❌ Non può modificare stato prenotazione
- ❌ Non può registrare ingresso (staff lo fa)

### STAFF (ingressista/barista)
- ✅ Visualizza prenotazioni evento attivo
- ✅ Scansiona QR → registra ingresso
- ✅ Registra consumi
- ✅ Dashboard live evento (capienza, ritmo)
- ❌ Non può modificare stato evento
- ❌ Non può cancellare prenotazioni

### ADMIN
- ✅ Crea/modifica/chiude evento
- ✅ Imposta evento operativo (staff)
- ✅ Force stato prenotazione
- ✅ CRUD prenotazioni
- ✅ Analytics evento complete
- ✅ Gestione fedeltà manuale

---

## 📊 Step Indicator UI

Template: `templates/clienti/_step_indicator.html`

Visualizza il progresso:
```
[1. Evento] — [2. Prenotazione] — [3. Ingresso] — [4. Feedback] — [5. Consumi]
   ✓ done       ✓ done              → current        future          future
```

- **Verde/Oro**: Completato
- **Pulsante**: Step corrente
- **Grigio**: Bloccato (dipendenza non soddisfatta)

---

## 📝 Checklist di Verifiche

### Backend
- [ ] Route evento: mostra solo stato_pubblico != "chiuso"
- [ ] Route prenotazione: controlla una sola attiva per cliente/evento
- [ ] Route ingresso: collega a prenotazione se esiste
- [ ] Chiusura evento: transazione atomica (stato + staff + prenotazioni → no-show + fedeltà)
- [ ] Fedeltà: +10 per show, −5 per no-show, +1 ogni 10€

### Frontend
- [ ] Step indicator visibile in prenotazioni_list
- [ ] Badge stato evento in lista eventi
- [ ] Bottone PRENOTA disabilitato se non consentito
- [ ] Feedback form nascosto se no ingresso
- [ ] Consumi visualizzati solo dopo ingresso
- [ ] Cancellazione prenotazione mostra countdown 18:00

### UX
- [ ] Flusso verticale chiaro: eventi → prenotazioni → ingressi
- [ ] Testi coerenti tra pagine
- [ ] Warning inline se azione bloccata
- [ ] Mobile-first: no scrolling orizzontale

---

## 🚀 Deployment

1. **Esegui migrazioni DB** (app/models già definiti)
2. **Importa workflow.py** in routes
3. **Aggiorna templates** con badge/step-indicator
4. **Test**: Percorso completo cliente da login → evento → prenotazione → ingresso → feedback
5. **QA**: Verifica blocchi logici (niente feedback senza ingresso, etc.)

---

**Last updated:** 2025-11-11  
**Status:** ✅ Lineare, coerente, mobile-first

