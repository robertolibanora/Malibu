# 📊 FLUSSO VISUALE LINEARE — Malibù App

## 🎭 Percorso Completo Cliente

```
┌─────────────────────────────────────────────────────────────────────┐
│                    🔐 CLIENT ACCEDE ALL'APP                         │
│                                                                     │
│  Session: cliente_id=X | QR Code: univoco                         │
└─────────────────────────────────────────────────────────────────────┘
                                  ↓
        ╔══════════════════════════════════════════════════╗
        ║            📅 STEP 1: SCEGLI EVENTO             ║
        ╚══════════════════════════════════════════════════╝
                                  ↓
                    ┌─────────────────────┐
                    │ /eventi             │  Lista eventi pubblici
                    │ stato_pubblico !=   │  (programmato, attivo)
                    │ "chiuso"            │
                    └─────────────────────┘
                                  ↓
                    ✅ EVENTO VISIBILE?
                      ├─ SÌ: continua
                      └─ NO: nascondi evento
                                  ↓
              Badge evento: ORO (attivo) / GRIGIO (programmato)
              Bottone "Prenota" abilitato se evento aperto
                                  ↓
        ╔══════════════════════════════════════════════════╗
        ║        🎟️ STEP 2: PRENOTA PRENOTAZIONE         ║
        ╚══════════════════════════════════════════════════╝
                                  ↓
                ┌──────────────────────────────────┐
                │ /prenotazioni/nuova?evento_id=X  │
                │ Form: tipo (lista/tavolo) +      │
                │ num_persone + note + orario      │
                └──────────────────────────────────┘
                                  ↓
        CONTROLLI VALIDAZIONE:
        ├─ Cliente ha già prenotazione attiva?
        │   ├─ SÌ: ❌ Errore "già prenotato"
        │   └─ NO: continua
        ├─ Tipo = tavolo?
        │   ├─ SÌ: num_persone obbligatorio + nome tavolo in note
        │   └─ NO: (num_persone = null)
        └─ Evento aperto?
            ├─ SÌ: continua
            └─ NO: ❌ Evento non disponibile
                                  ↓
              ✅ PRENOTAZIONE CREATA
              stato = "attiva"
              Badge: ORO + 🎟️ "Prenotazione attiva"
              Prossimo: Attendi ingresso presso evento
                                  ↓
        ╔══════════════════════════════════════════════════╗
        ║          🚪 STEP 3: REGISTRA INGRESSO           ║
        ║             (Staff scansiona QR)                 ║
        ╚══════════════════════════════════════════════════╝
                                  ↓
            ┌────────────────────────────────┐
            │ Staff: /ingressi/scan_qr       │
            │ Scansione QR cliente           │
            │ Evento: attivo (is_staff_      │
            │ operativo = True)              │
            └────────────────────────────────┘
                                  ↓
        MATCHING:
        ├─ Prenotazione attiva per cliente?
        │   ├─ SÌ: ingresso.tipo = prenotazione.tipo
        │   │       prenotazione.stato = "usata"
        │   │       +10 pt fedeltà (SHOW)
        │   └─ NO: ingresso.tipo = "lista"
        │         (cliente senza prenotazione)
        └─ Warning: capienza superata?
            ├─ SÌ: ⚠️ "Evento quasi pieno"
            └─ NO: ok
                                  ↓
        ✅ INGRESSO REGISTRATO
        Badge cliente: NERO "🚪 Entrato"
        Prenotazione: ORO "✓ Usata (ingresso valido)"
        Fedeltà: +10 pt aggiunto
                                  ↓
        ╔══════════════════════════════════════════════════╗
        ║       ⭐ STEP 4A: LASCIA FEEDBACK              ║
        ║       (parallelo, dopo ingresso)                 ║
        ╚══════════════════════════════════════════════════╝
                                  ↓
        BLOCCO LOGICO:
        └─ Cliente ha ingresso? ─┐
           ├─ SÌ: ✅ Mostra bottone "Lascia feedback"
           └─ NO: ❌ "Disponibile solo dopo ingresso"
                                  ↓
            ┌────────────────────────────────┐
            │ /feedback/nuova?evento_id=X    │
            │ Form: voto musica (1-10) +     │
            │ voto_ingresso + voto_ambiente  │
            │ + voto_servizio + note         │
            └────────────────────────────────┘
                                  ↓
        VALIDAZIONE:
        └─ Feedback già lasciato?
           ├─ SÌ: ❌ "Hai già reviewato questo evento"
           └─ NO: ✅ Salva feedback
                   Badge: ⭐ "Feedback lasciato"
                                  ↓
        ╔══════════════════════════════════════════════════╗
        ║        🍾 STEP 4B: REGISTRA CONSUMI             ║
        ║       (parallelo, dopo ingresso)                 ║
        ╚══════════════════════════════════════════════════╝
                                  ↓
        BLOCCO LOGICO:
        └─ Cliente ha ingresso? ─┐
           ├─ SÌ: ✅ Mostra sezione "Consumi"
           └─ NO: ❌ Nascondi sezione
                                  ↓
            ┌────────────────────────────────┐
            │ Staff: /consumi/nuova          │
            │ Form: cliente_id (search) +    │
            │ prodotto + importo +           │
            │ punto_vendita (bar/tavolo/privè)
            └────────────────────────────────┘
                                  ↓
        REGISTRAZIONE:
        ├─ Importo riconosciuto
        ├─ Fedeltà: +1 pt ogni 10€ (calcolato)
        └─ Totale fedeltà = 10 (show) + N (consumi)
                                  ↓
            ✅ CONSUMO REGISTRATO
            Badge: 🍾 "Acquisto registrato"
            Fedeltà: aggiornata
                                  ↓
        ╔══════════════════════════════════════════════════╗
        ║              📊 STATO FINALE CLIENTE            ║
        ╚══════════════════════════════════════════════════╝
                                  ↓
        ┌─────────────────────────────────────────────────┐
        │ PRENOTAZIONE          │ stato = "usata"        │
        │ INGRESSO              │ registrato ✓           │
        │ FEEDBACK              │ lasciato ⭐            │
        │ CONSUMI               │ €50.00 registrati      │
        │ FEDELTÀ TOTALE        │ +10 (show)             │
        │                       │ +5 (consumi €50)       │
        │                       │ = +15 pt totale        │
        └─────────────────────────────────────────────────┘
```

---

## 🔄 Flusso Alternativo: NO-SHOW

```
┌─────────────────────────────────────────────────────┐
│       CLIENTE PRENOTA MA NON SI PRESENTA            │
└─────────────────────────────────────────────────────┘
                          ↓
            ┌─────────────────────────┐
            │ Admin: Chiudi evento    │
            │ /eventi/<id>/close      │
            └─────────────────────────┘
                          ↓
        AZIONE ATOMICA (transazione):
        ├─ evento.stato_pubblico = "chiuso"
        ├─ evento.is_staff_operativo = False
        ├─ Tutte prenotazioni attive:
        │   ├─ stato = "no-show"
        │   ├─ Fedeltà: −5 pt (penalità)
        │   └─ Log action registrato
        └─ Reset evento operativo
                          ↓
        ✅ PRENOTAZIONE MARCATA NO-SHOW
        Badge: NERO "✗ No-show (−5 pt)"
        Fedeltà: −5 punti sottratti
```

---

## 🎛️ Flusso Cancellazione Prenotazione

```
┌──────────────────────────────────────────────────────┐
│     CLIENTE CANCELLA PRENOTAZIONE                    │
└──────────────────────────────────────────────────────┘
                          ↓
            ┌─────────────────────┐
            │ /prenotazioni/<id>  │
            │ /cancella (POST)    │
            └─────────────────────┘
                          ↓
        CONTROLLO DEADLINE:
        └─ Ora <= 18:00 giorno evento? ─┐
           ├─ SÌ: ✅ Consenti cancellazione
           │       stato = "cancellata"
           │       Mostra contatore: "ore_rimaste"
           └─ NO: ❌ "Troppo tardi, deadline 18:00"
                     (pulsante disabilitato dopo 18:00)
                          ↓
        ✅ PRENOTAZIONE CANCELLATA
        Scomparsa da "/prenotazioni/mie"
        Nessun effetto fedeltà
```

---

## 📱 UI STEP INDICATOR (Mobile-First)

### Desktop (768px+)
```
┌─────────────────────────────────────────────────────────────────┐
│ [1] Evento → [2] Prenotazione → [3] Ingresso → [4] Feedback    │
│     ✓ done     ✓ done          ● current        future          │
└─────────────────────────────────────────────────────────────────┘
                    ↓ Current Step Info
            "Entra con il tuo QR al venue"
```

### Mobile (<480px)
```
┌────────────────┐
│ [1] Evento   ✓ │
├────────────────┤
│ [2] Prenot.  ✓ │
├────────────────┤
│ [3] Ingress  ● │ ← Current (pulsante)
├────────────────┤
│ [4] Feedback   │ ← Futura (bloccata)
├────────────────┤
│ [5] Consumi    │ ← Futura (bloccata)
└────────────────┘
```

---

## 🎨 BADGE & COLORI

### Evento
```
Programmato:     ⏱️ ● Programmato      [GRIGIO]
Attivo:          🔴 ● ATTIVO ADESSO    [ORO]
Chiuso:          ⏹️ ● Chiuso           [NERO]
```

### Prenotazione
```
Attiva:          🎟️ Prenotazione attiva       [ORO]
Usata:           ✓ Usata (ingresso valido)    [ORO]
No-show:         ✗ No-show (−5 pt)            [NERO]
Cancellata:      🚫 Cancellata                [GRIGIO]
```

### Ingresso
```
Entrato:         🚪 Entrato       [NERO]
Non entrato:     ⏳ Ancora non entrato  [GRIGIO]
```

### Feedback
```
Completato:      ⭐ Feedback lasciato     [ORO]
Disponibile:     ⭐ Lascia una review     [link enable]
Bloccato:        ⏳ Solo se entrato       [disabled]
```

### Fedeltà
```
+10 pt Show:     "✓ Sei entrato +10 pt"
+N pt Consumi:   "🍾 €50.00 +5 pt"
−5 pt No-show:   "✗ Non presentato −5 pt"
```

---

## 🔐 Matrice Permessi

| Azione | Cliente | Staff | Admin |
|--------|---------|-------|-------|
| Vedi evento pubblico | ✅ | ✅ | ✅ |
| Prenota evento | ✅ | ❌ | ✅ |
| Scansiona QR | ❌ | ✅ | ✅ |
| Registra consumo | ❌ | ✅ | ✅ |
| Lascia feedback | ✅ | ❌ | ❌ |
| Forza stato prenotazione | ❌ | ❌ | ✅ |
| Chiudi evento | ❌ | ❌ | ✅ |
| Dashboard evento | ❌ | ✅ | ✅ |
| Analytics evento | ❌ | ❌ | ✅ |

---

## 📝 Template Coinvolti

### Cliente
- ✅ `templates/clienti/base.html` — Nav principale (Home, Eventi, Prenotazioni)
- ✅ `templates/clienti/eventi_list.html` — Lista con badge + workflow
- ✅ `templates/clienti/evento_detail.html` — Dettaglio + PRENOTA bottone
- ✅ `templates/clienti/prenotazioni_new.html` — Form prenotazione
- ✅ `templates/clienti/prenotazioni_list.html` — Mie prenotazioni + step indicator
- ✅ `templates/clienti/prenotazione_detail.html` — Dettaglio (se usata) + feedback/consumi
- ✅ `templates/clienti/feedback_form.html` — Form feedback (se consentito)
- ✅ `templates/clienti/consumi_list.html` — Cronologia consumi (se entrato)

### Staff
- ✅ `templates/staff/evento_select.html` — Sceglie evento operativo
- ✅ `templates/staff/evento_dashboard.html` — Dashboard live (capienza, ritmo)
- ✅ `templates/staff/ingressi_scan_qr_evento.html` — Scansione QR
- ✅ `templates/staff/ingressi_esito.html` — Conferma ingresso
- ✅ `templates/staff/prenotazioni_evento.html` — Lista prenotati evento
- ✅ `templates/staff/consumi_new.html` — Registra consumo cliente

### Macro Riusabili
- ✅ `templates/clienti/_step_indicator.html` — Step progress (5 step)
- ✅ `templates/clienti/_status_badges.html` — Badge stato evento/prenotazione/ingresso

### Admin
- ✅ `templates/admin/eventi_form.html` — Crea/modifica evento
- ✅ `templates/admin/evento_attivo.html` — Scegli evento operativo + chiusura
- ✅ `templates/admin/evento_detail.html` — Analytics evento completo
- ✅ `templates/admin/prenotazioni_list.html` — Gestione prenotazioni

---

## 🚀 Implementazione Step-by-Step

### 1. Backend (Routes)
- [x] `app/utils/workflow.py` — Helper + WorkflowState
- [x] Route `/eventi` — pass workflow_map + evento_badge_map
- [x] Route `/eventi/<id>` — pass workflow_state + evento_badge
- [x] Route `/prenotazioni/mie` — pass workflow_map
- [x] Route `/prenotazioni/nuova` — check cliente_puo_prenotare()
- [ ] Route `/feedback/nuova` — check cliente_puo_lasciare_feedback()
- [ ] Route `/consumi/nuova` — check cliente_puo_registrare_consumi()

### 2. Frontend (Templates)
- [x] Step indicator macro
- [x] Badge status macro
- [x] Update `eventi_list.html` con workflow
- [ ] Update `evento_detail.html` con step + badge
- [ ] Update `prenotazioni_list.html` con step indicator
- [ ] Update `prenotazione_detail.html` con step + feedback/consumi bloccati se no ingresso
- [ ] Update `feedback_form.html` con blocco se no ingresso
- [ ] Update `consumi_list.html` con blocco se no ingresso

### 3. CSS (Responsive)
- [x] Colori badge ORO/NERO/GRIGIO
- [x] Step indicator mobile-first
- [ ] Event card responsive
- [ ] Form styling coerente

### 4. Testing
- [ ] Flow completo cliente: evento → prenota → ingresso → feedback/consumi
- [ ] Blocchi logici: niente feedback senza ingresso
- [ ] Cancellazione entro 18:00
- [ ] No-show chiusura evento
- [ ] Badge colori corretti su mobile
- [ ] QA staff: scansione QR, registrazione consumo

---

## 📊 Stato Implementazione

| Fase | Compito | Status |
|------|---------|--------|
| 1 | Helper workflow.py | ✅ Completato |
| 2 | Step indicator macro | ✅ Completato |
| 3 | Badge status macro | ✅ Completato |
| 4 | Update route eventi | ✅ Completato |
| 5 | Update route prenotazioni | ✅ Completato |
| 6 | Update template eventi_list | ✅ Completato |
| 7 | Update template evento_detail | ⏳ In progress |
| 8 | Update template prenotazioni | ⏳ In progress |
| 9 | Update template feedback | ⏳ Pending |
| 10 | Update template consumi | ⏳ Pending |
| 11 | CSS responsive | ⏳ Pending |
| 12 | Testing E2E | ⏳ Pending |

---

**Generated:** 2025-11-11  
**Schema:** Lineare, dipendente, bloccante per ogni step  
**UX:** Mobile-first, colori coerenti (ORO/NERO), badge chiari

