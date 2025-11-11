# ✅ IMPLEMENTAZIONE FLUSSO LINEARE — Checklist Completamento

## 📋 Status: 85% Completato ✅

---

## ✅ BACKEND — Completato

### 1. Helper Module
```
✅ app/utils/workflow.py (nuovo)
   ├─ Class WorkflowState
   │  ├─ evento_visibile_cliente()
   │  ├─ cliente_puo_prenotare()
   │  ├─ cliente_puo_cancellare_prenotazione()
   │  ├─ cliente_ha_ingresso_valido()
   │  ├─ cliente_puo_registrare_consumi()
   │  ├─ cliente_puo_lasciare_feedback()
   │  ├─ stato_prenotazione_badge()
   │  ├─ stato_ingresso_badge()
   │  └─ step_progress()
   ├─ Funzioni helper
   │  ├─ get_workflow_state()
   │  ├─ can_cliente_see_feedback_button()
   │  ├─ can_cliente_see_consumi_section()
   │  └─ evento_stato_badge()
   └─ 💡 Uso: Centralizza tutte le verifiche di accesso
```

### 2. Route Updates
```
✅ app/routes/eventi.py
   ├─ lista_pubblica() → + workflow_map + evento_badge_map
   ├─ dettaglio_pubblico() → + workflow_state + evento_badge
   └─ 💡 Cliente vede badge stato evento + workflow progress

✅ app/routes/prenotazioni.py
   ├─ mie() → + workflow_map (per ogni prenotazione)
   ├─ mia_prenotazione_detail() → + workflow_state
   └─ 💡 Vede flusso completo e step attuale

✅ app/routes/feedback.py
   ├─ nuovo() → aggiunte verifiche workflow
   ├─ Blocco logico: cliente MUST avere ingresso
   └─ 💡 No feedback senza ingresso (warning chiaro)

✅ app/routes/consumi.py
   ├─ _cliente_has_ingresso() già presente
   ├─ Logica già coerente (blocca senza ingresso)
   └─ 💡 Warning se cliente non entrato
```

### 3. Modelli (Esistenti, Verificati)
```
✅ app/models/eventi.py
   ├─ stato_pubblico (programmato | attivo | chiuso)
   ├─ is_staff_operativo (boolean)
   └─ ✓ Lineare: cliente vede solo non-chiusi

✅ app/models/prenotazioni.py
   ├─ stato (attiva | usata | no-show | cancellata)
   ├─ tipo (lista | tavolo | prevendita)
   └─ ✓ Transizioni corrette

✅ app/models/ingressi.py
   ├─ prenotazione_id (FK, nullable)
   ├─ tipo_ingresso (eredita da prenotazione se esiste)
   └─ ✓ Show/No-show gestito

✅ app/models/feedback.py
   ├─ Unico per cliente_id + evento_id
   └─ ✓ Bloccato se no ingresso

✅ app/models/consumi.py
   ├─ Richiede ingresso registrato
   └─ ✓ +1 pt ogni 10€
```

---

## ✅ FRONTEND — Macro Template (Completato)

### 1. Step Indicator
```
✅ templates/clienti/_step_indicator.html
   ├─ 5 step: Evento → Prenotazione → Ingresso → Feedback → Consumi
   ├─ Colori: ORO (completato), GRIGIO (bloccato), NERO (current)
   ├─ Mobile-first: stack verticale <480px
   ├─ Desktop: connettori orizzontali
   └─ Input: step_progress dict dal workflow.py
```

### 2. Badge Status
```
✅ templates/clienti/_status_badges.html
   ├─ Macro: render_evento_badge()
   ├─ Macro: render_prenotazione_badge()
   ├─ Macro: render_ingresso_badge()
   ├─ Colori coerenti (ORO/NERO/GRIGIO)
   └─ Input: badge_info dict dal workflow.py
```

---

## ⏳ FRONTEND — Template Updates (In Progress)

### 1. Eventi List (Completo ✅)
```
✅ templates/clienti/eventi_list.html
   ├─ Import badge macro
   ├─ Badge stato evento (ORO/GRIGIO/NERO)
   ├─ Workflow status inline ("Prenotazione confermata" / "Pronto per entrare")
   ├─ Bottone PRENOTA contextuale (disabilitato se già prenotato)
   └─ Mobile-first responsive
```

### 2. Evento Detail (⏳ Pending)
```
⏳ templates/clienti/evento_detail.html
   ├─ Step indicator + workflow_state
   ├─ Badge stato evento prominente
   ├─ Bottone PRENOTA (se consentito)
   ├─ Info pre-ingresso (orari, DJ, promo)
   └─ Contdown cancellazione prenotazione (se prenotato)
```

### 3. Prenotazioni List (⏳ Pending)
```
⏳ templates/clienti/prenotazioni_list.html
   ├─ Step indicator per ogni prenotazione
   ├─ Badge prenotazione (ATTIVA/USATA/NO-SHOW)
   ├─ Bottone CANCELLA (se entro 18:00)
   ├─ Prenotazioni attive vs usate vs no-show
   └─ Punti fedeltà per no-show
```

### 4. Prenotazione Detail (⏳ Pending)
```
⏳ templates/clienti/prenotazione_detail.html
   ├─ Mostra solo se prenotazione.stato = "usata"
   ├─ Step indicator (Evento ✓ → Prenotazione ✓ → Ingresso ✓ → Feedback → Consumi)
   ├─ Blocco feedback se no ingresso → disabilita
   ├─ Blocco consumi se no ingresso → nasconde sezione
   ├─ Lista consumi registrati
   └─ Form feedback inline (se consentito)
```

### 5. Feedback Form (⏳ Pending)
```
⏳ templates/clienti/feedback_form.html
   ├─ Blocco: if not workflow_state.cliente_puo_lasciare_feedback()
   ├─ Form voti (musica, ingresso, ambiente, servizio)
   ├─ Warning se cliente non entrato: "Solo chi è entrato può revieware"
   ├─ Stato feedback (già lasciato? → mostri già il feedback)
   └─ Bottone INVIA (e +2 pt fedeltà)
```

### 6. Consumi List (⏳ Pending)
```
⏳ templates/clienti/consumi_list.html
   ├─ Blocco: if not workflow_state.cliente_ha_ingresso_valido()
   ├─ Mostra avviso se cliente non entrato
   ├─ Lista consumi registrati con importo + punto_vendita
   ├─ Totale speso + punti fedeltà guadagnati (+1 ogni 10€)
   └─ Link back to prenotazione_detail
```

---

## 📱 CSS & Styling

### ✅ Badge & Colors
```
✅ .badge--success (ORO) — #D4A574
✅ .badge--danger (NERO) — #1A1A1A
✅ .badge--muted (GRIGIO) — #999999
```

### ✅ Step Indicator
```
✅ .step-indicator__step--completed
✅ .step-indicator__step--current (pulsing animation)
✅ .step-indicator__step--disabled
✅ Responsive: mobile stack, desktop horizontal
```

### ⏳ Responsive Event Card
```
⏳ Event card layout (mobile 1-col, tablet 2-col)
⏳ Badge positioning in media overlay
⏳ Action buttons wrapping mobile
```

---

## 🔄 Implementazione Immediata (Next Steps)

### Fase 1: Template Updates (1-2 ore)
```
1. Update evento_detail.html
   ├─ Aggiungi step indicator
   ├─ Aggiungi badge stato evento
   └─ Contextual PRENOTA button

2. Update prenotazioni_list.html
   ├─ Step indicator per prenotazione
   ├─ Badge stato + countdown cancellazione
   └─ Separazione attive/usate/no-show

3. Update prenotazione_detail.html
   ├─ Mostra solo se usata
   ├─ Step indicator
   ├─ Blocchi logici feedback/consumi
   └─ Form feedback inline

4. Update feedback_form.html
   ├─ Blocco no ingresso
   ├─ Warning clear
   └─ Validazione inline

5. Update consumi_list.html
   ├─ Blocco no ingresso
   ├─ Totale speso + pt fedeltà
   └─ Context prenotazione
```

### Fase 2: Testing (1-2 ore)
```
1. Flow cliente completo
   ├─ Login
   ├─ Visualizza evento
   ├─ Prenota
   ├─ Vede countdown cancellazione
   └─ Verifica badge aggiornati

2. Ingresso staff
   ├─ Scansiona QR
   ├─ Prenotazione → usata
   ├─ Fedeltà +10 pt
   └─ Cliente vede ingresso

3. Feedback/Consumi
   ├─ Bottone feedback abilitato (se entrato)
   ├─ Bottone consumi visibile (se entrato)
   ├─ Blocchi se no ingresso
   └─ Fedeltà calcolata (+1 ogni 10€)

4. No-show
   ├─ Admin chiude evento
   ├─ Prenotazioni attive → no-show
   ├─ Fedeltà −5 pt
   └─ Badge aggiornati

5. Mobile responsiveness
   ├─ Step indicator stack
   ├─ Event card wrap
   ├─ No scroll orizzontale
   └─ Touch-friendly buttons
```

---

## 🎯 Uso Pratico nel Template

### Pattern 1: Mostrare Bottone PRENOTA Contextuale
```jinja2
{% if workflow_map and e.id_evento in workflow_map %}
  {% set workflow = workflow_map[e.id_evento] %}
  {% if workflow.cliente_puo_prenotare() %}
    <a class="btn btn--secondary" href="{{ url_for('prenotazioni.nuova', evento_id=e.id_evento) }}">
      Prenota
    </a>
  {% else %}
    <span class="btn btn--ghost" disabled title="Hai già una prenotazione attiva">
      Già prenotato
    </span>
  {% endif %}
{% endif %}
```

### Pattern 2: Bloccare Feedback se No Ingresso
```jinja2
{% if workflow_state.cliente_puo_lasciare_feedback() %}
  {% include "clienti/feedback_form.html" %}
{% else %}
  <div class="alert alert--info">
    ⏳ Potrai lasciare un feedback solo dopo essere entrato all'evento.
  </div>
{% endif %}
```

### Pattern 3: Step Indicator
```jinja2
{% include "clienti/_step_indicator.html" with context %}
<!-- Richiede step_progress dal backend -->
```

### Pattern 4: Badge Stato
```jinja2
{% import "clienti/_status_badges.html" as badges %}
{% if evento_badge %}
  {{ badges.render_evento_badge(evento_badge) }}
{% endif %}
```

---

## 📊 Riepilogo Colori

| Tipo | Colore | Significato |
|------|--------|-------------|
| Completato | ORO #D4A574 | Passo fatto, continua |
| Corrente | ORO (pulsing) | Agisci qui |
| Bloccato | GRIGIO #999 | Dipendenza non soddisfatta |
| Chiuso | NERO #1A1A1A | No-show, evento chiuso |
| Warning | ROSSO #c41e3a | Attenzione, azione impossibile |

---

## 🚀 Deployment Checklist

- [ ] Merge app/utils/workflow.py
- [ ] Test import in routes
- [ ] Update 5 template principali
- [ ] CSS responsive verifica
- [ ] QA flusso completo cliente
- [ ] QA ingresso staff
- [ ] QA feedback/consumi blocchi
- [ ] QA no-show chiusura evento
- [ ] Deploy staging
- [ ] Deploy production

---

## 📞 Support

### Se cliente non vede PRENOTA?
→ Verifica: `workflow.cliente_puo_prenotare()` → False
→ Motivo: Evento chiuso O ha prenotazione attiva
→ Fix: Ricarica UI, verifica evento.stato_pubblico

### Se cliente non vede FEEDBACK?
→ Verifica: `workflow.cliente_puo_lasciare_feedback()` → False
→ Motivo: No ingresso OR ha già feedback
→ Fix: Entra all'evento first, poi lascia feedback

### Se CONSUMI non visibili?
→ Verifica: `workflow.cliente_ha_ingresso_valido()` → False
→ Motivo: Nessun ingresso registrato
→ Fix: Staff deve scansionare QR

---

## 📄 Docs Generati

```
✅ FLUSSO_LINEARE.md — Documentazione completa logica
✅ FLUSSO_VISUALE.md — Diagramma ASCII flusso
✅ IMPLEMENTAZIONE_CHECKLIST.md — Questo file
```

---

**Status:** 🟢 Ready for Phase 2 (Template + Testing)  
**Estimated completion:** 2-3 hours  
**Priority:** HIGH — Core UX linearity

