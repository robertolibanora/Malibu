/**
 * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 * 🎯 QR Scanner Module - Malibu Staff
 * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 * 
 * Modulo JavaScript riutilizzabile per la scansione QR tramite html5-qrcode.
 * Progettato per ambienti mobile-first (discoteche) con feedback visivo/sonoro.
 * 
 * Caratteristiche:
 * - Gestione errori camera (permessi, disponibilità)
 * - Feedback visivo (badge status) + sonoro (beep) + tattile (vibrazione)
 * - Prevenzione doppie scansioni (<2s)
 * - Auto-submit opzionale del form
 * - Riavvio automatico dopo scansione
 * - Design nero/oro coerente con l'app
 * 
 * @author Roberto Libanora
 * @version 2.0
 */

(function(window) {
  'use strict';

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // 🔧 CONFIGURAZIONE
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  
  const CONFIG = {
    fps: 10,                    // Frame al secondo per la scansione
    qrbox: { width: 250, height: 250 },  // Dimensioni area di scansione
    aspectRatio: 1.0,           // Rapporto aspetto camera
    facingMode: "environment",  // Camera posteriore (mobile)
    duplicateDelay: 2000,       // Millisecondi per ignorare QR duplicati
    successDisplayTime: 1500,   // Tempo di visualizzazione messaggio successo
    vibrationPattern: [50, 30, 50], // Pattern vibrazione (ms)
    beepFrequency: 1200,        // Frequenza beep (Hz)
    beepDuration: 100           // Durata beep (ms)
  };

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // 🎵 AUDIO FEEDBACK
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  
  /**
   * Genera un beep sonoro usando Web Audio API
   * Utile in ambienti rumorosi come discoteche
   */
  function playBeep() {
    try {
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();
      
      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);
      
      oscillator.frequency.value = CONFIG.beepFrequency;
      oscillator.type = 'sine';
      
      gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + CONFIG.beepDuration / 1000);
      
      oscillator.start(audioContext.currentTime);
      oscillator.stop(audioContext.currentTime + CONFIG.beepDuration / 1000);
    } catch (e) {
      console.warn('🔇 Audio feedback non disponibile:', e);
    }
  }

  /**
   * Attiva vibrazione su dispositivi mobile
   */
  function vibrate() {
    if (navigator.vibrate) {
      navigator.vibrate(CONFIG.vibrationPattern);
    }
  }

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // 🎨 UI FEEDBACK
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  
  /**
   * Aggiorna il badge di stato dello scanner
   * @param {HTMLElement} statusEl - Elemento status da aggiornare
   * @param {string} message - Messaggio da visualizzare
   * @param {string} type - Tipo: 'loading', 'ready', 'success', 'error'
   */
  function updateStatus(statusEl, message, type = 'ready') {
    if (!statusEl) return;
    
    statusEl.textContent = message;
    statusEl.className = 'qr-status qr-status--' + type;
    
    // Icone contestuali
    const icons = {
      loading: '⏳',
      ready: '📸',
      success: '✅',
      error: '⚠️'
    };
    
    statusEl.textContent = icons[type] + ' ' + message;
  }

  /**
   * Mostra toast di successo temporaneo
   * @param {HTMLElement} container - Container dello scanner
   * @param {string} qrCode - Codice QR letto
   */
  function showSuccessToast(container, qrCode) {
    const toast = document.createElement('div');
    toast.className = 'qr-toast qr-toast--success';
    toast.innerHTML = `
      <div class="qr-toast__icon">✅</div>
      <div class="qr-toast__content">
        <strong>QR riconosciuto</strong>
        <div class="qr-toast__code">${qrCode.substring(0, 20)}${qrCode.length > 20 ? '...' : ''}</div>
      </div>
    `;
    
    container.appendChild(toast);
    
    // Animazione entrata
    setTimeout(() => toast.classList.add('qr-toast--visible'), 10);
    
    // Rimozione automatica
    setTimeout(() => {
      toast.classList.remove('qr-toast--visible');
      setTimeout(() => toast.remove(), 300);
    }, CONFIG.successDisplayTime);
  }

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // 🎯 SCANNER CORE
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  
  /**
   * Classe principale per la gestione dello scanner QR
   */
  class QrScanner {
    constructor(containerId, onSuccess, options = {}) {
      this.containerId = containerId;
      this.onSuccess = onSuccess;
      this.options = {
        autoSubmit: options.autoSubmit || false,
        formId: options.formId || null,
        resultInputId: options.resultInputId || 'qr-result',
        manualInputId: options.manualInputId || 'qr-manual',
        allowDuplicates: options.allowDuplicates || false,
        precheckUrl: options.precheckUrl || null,
        precheckMethod: options.precheckMethod || 'POST',
        precheckPayloadKey: options.precheckPayloadKey || 'qr'
      };
      
      this.html5QrCode = null;
      this.isScanning = false;
      this.lastScannedCode = null;
      this.lastScanTime = 0;
      this.container = null;
      this.statusEl = null;
    }

    /**
     * Inizializza lo scanner
     */
    async init() {
      this.container = document.getElementById(this.containerId);
      
      if (!this.container) {
        console.error('❌ Container scanner non trovato:', this.containerId);
        return;
      }

      // Crea elemento status se non esiste
      this.statusEl = this.container.querySelector('.qr-status');
      if (!this.statusEl) {
        this.statusEl = document.createElement('div');
        this.statusEl.className = 'qr-status';
        this.container.insertBefore(this.statusEl, this.container.firstChild);
      }

      // Sincronizza input manuale con hidden (se presente)
      this._setupManualInput();

      // Avvia scanner
      await this.start();
    }

    /**
     * Configura input manuale come fallback
     */
    _setupManualInput() {
      const manualInput = document.getElementById(this.options.manualInputId);
      const resultInput = document.getElementById(this.options.resultInputId);
      
      if (manualInput && resultInput) {
        manualInput.addEventListener('input', (e) => {
          resultInput.value = e.target.value.trim();
        });
        
        // Se c'è già un valore, sincronizzalo
        if (manualInput.value) {
          resultInput.value = manualInput.value.trim();
        }
      }
    }

    /**
     * Avvia lo scanner
     */
    async start() {
      if (this.isScanning) {
        console.warn('⚠️ Scanner già attivo');
        return;
      }

      updateStatus(this.statusEl, 'Inizializzazione...', 'loading');

      try {
        // Verifica disponibilità libreria
        if (typeof Html5Qrcode === 'undefined') {
          throw new Error('Libreria html5-qrcode non caricata');
        }

        this.html5QrCode = new Html5Qrcode(this.containerId);
        
        const config = {
          fps: CONFIG.fps,
          qrbox: CONFIG.qrbox,
          aspectRatio: CONFIG.aspectRatio
        };

        await this.html5QrCode.start(
          { facingMode: CONFIG.facingMode },
          config,
          this._onScanSuccess.bind(this),
          this._onScanFailure.bind(this)
        );

        this.isScanning = true;
        updateStatus(this.statusEl, 'Scanner attivo', 'ready');
        console.log('✅ Scanner QR avviato');

      } catch (error) {
        console.error('❌ Errore avvio scanner:', error);
        this._handleStartError(error);
      }
    }

    /**
     * Gestisce errori di avvio
     */
    _handleStartError(error) {
      let message = 'Errore camera';
      let hint = "Usa l'input manuale qui sotto per inserire il codice QR.";
      
      const insecureContext = !window.isSecureContext && window.location.protocol !== 'https:';
      const errorMsg = (error && error.message) || '';
      const errorName = error && error.name;
      
      if (errorName === 'NotAllowedError' || errorMsg.includes('Permission')) {
        message = 'Permesso camera negato';
        if (insecureContext) {
          hint = "Safari su iPhone richiede HTTPS (o localhost) per abilitare la fotocamera.";
        } else {
          hint = "Controlla le impostazioni del browser e consenti l'accesso alla fotocamera.";
        }
      } else if (errorName === 'NotFoundError') {
        message = 'Camera non trovata';
      } else if (errorName === 'NotReadableError') {
        message = 'Camera già in uso';
      } else if (insecureContext) {
        message = 'Connessione non sicura';
        hint = "Apri l'app su https:// (oppure usa localhost) per usare lo scanner.";
      }
      
      updateStatus(this.statusEl, message, 'error');
      
      const errorDiv = document.createElement('div');
      errorDiv.className = 'qr-error';
      errorDiv.innerHTML = `
        <p><strong>⚠️ ${message}</strong></p>
        <p class="text--muted">${hint}</p>
      `;
      this.container.appendChild(errorDiv);
    }

    async _precheck(decodedText) {
      if (!this.options.precheckUrl) return { ok: true };
      try {
        const res = await fetch(this.options.precheckUrl, {
          method: this.options.precheckMethod,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ [this.options.precheckPayloadKey]: decodedText }),
          credentials: 'same-origin'
        });
        return await res.json();
      } catch (e) {
        // In caso di errore rete, lascia passare ma mostra avviso
        console.warn('⚠️ Precheck non disponibile:', e);
        return { ok: true };
      }
    }

    _showWarning(message) {
      updateStatus(this.statusEl, message, 'error');
      const toast = document.createElement('div');
      toast.className = 'qr-toast qr-toast--error';
      toast.innerHTML = `
        <div class="qr-toast__icon">⚠️</div>
        <div class="qr-toast__content">
          <strong>${message}</strong>
        </div>
      `;
      this.container.appendChild(toast);
      setTimeout(() => toast.classList.add('qr-toast--visible'), 10);
      setTimeout(() => {
        toast.classList.remove('qr-toast--visible');
        setTimeout(() => toast.remove(), 300);
      }, 1600);
    }

    /**
     * Callback successo scansione
     */
    async _onScanSuccess(decodedText, decodedResult) {
      const now = Date.now();
      
      // Previeni doppie scansioni
      if (!this.options.allowDuplicates) {
        if (this.lastScannedCode === decodedText && 
            (now - this.lastScanTime) < CONFIG.duplicateDelay) {
          console.log('🔄 QR duplicato ignorato:', decodedText);
          return;
        }
      }

      this.lastScannedCode = decodedText;
      this.lastScanTime = now;

      console.log('📱 QR scansionato:', decodedText);

      // Se previsto, effettua precheck (es. già entrato)
      if (this.options.autoSubmit && this.options.formId && this.options.precheckUrl) {
        const check = await this._precheck(decodedText);
        if (!check.ok) {
          if (check.reason === 'already') {
            this._showWarning('Già entrato per questo evento');
          } else if (check.reason === 'not_found') {
            this._showWarning('QR non valido');
          } else if (check.reason === 'no_event') {
            this._showWarning('Nessun evento attivo');
          } else {
            this._showWarning('Impossibile verificare');
          }
          // Non procedere con submit in caso di blocco
          return;
        }
      }

      // Feedback multimodale
      playBeep();
      vibrate();
      updateStatus(this.statusEl, 'QR riconosciuto!', 'success');
      showSuccessToast(this.container, decodedText);

      // Popola campo hidden
      const resultInput = document.getElementById(this.options.resultInputId);
      if (resultInput) {
        resultInput.value = decodedText;
      }

      // Popola anche input manuale (se presente)
      const manualInput = document.getElementById(this.options.manualInputId);
      if (manualInput) {
        manualInput.value = decodedText;
      }

      // Callback personalizzato
      if (typeof this.onSuccess === 'function') {
        this.onSuccess(decodedText, decodedResult);
      }

      // Auto-submit form
      if (this.options.autoSubmit && this.options.formId) {
        const form = document.getElementById(this.options.formId);
        if (form) {
          console.log('📤 Auto-submit form:', this.options.formId);
          setTimeout(() => form.submit(), 300);
        }
      }

      // Ripristina stato dopo feedback
      setTimeout(() => {
        if (this.isScanning) {
          updateStatus(this.statusEl, 'Scanner attivo', 'ready');
        }
      }, CONFIG.successDisplayTime);
    }

    /**
     * Callback fallimento scansione (silenzioso)
     */
    _onScanFailure(error) {
      // Non loggare errori di scansione continui (rumore)
      // Solo errori critici
      if (error && !error.includes('NotFoundException')) {
        console.debug('🔍 Scan:', error);
      }
    }

    /**
     * Ferma lo scanner
     */
    async stop() {
      if (!this.isScanning || !this.html5QrCode) {
        return;
      }

      try {
        await this.html5QrCode.stop();
        this.isScanning = false;
        updateStatus(this.statusEl, 'Scanner fermato', 'ready');
        console.log('⏸️ Scanner QR fermato');
      } catch (error) {
        console.error('❌ Errore stop scanner:', error);
      }
    }

    /**
     * Riavvia lo scanner
     */
    async restart() {
      await this.stop();
      await this.start();
    }
  }

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // 🌍 API PUBBLICA
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  
  /**
   * Inizializza scanner QR (API semplificata)
   * 
   * @param {string} containerId - ID del container HTML
   * @param {function} onSuccess - Callback al successo: (decodedText, result) => {}
   * @param {object} options - Opzioni:
   *   - autoSubmit: boolean - Submit automatico del form
   *   - formId: string - ID del form da submitare
   *   - resultInputId: string - ID input hidden per risultato
   *   - manualInputId: string - ID input manuale fallback
   *   - allowDuplicates: boolean - Permetti scansioni duplicate
   * @returns {QrScanner} - Istanza scanner
   */
  window.initQrScanner = function(containerId, onSuccess, options = {}) {
    const scanner = new QrScanner(containerId, onSuccess, options);
    
    // Avvia quando DOM è pronto
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => scanner.init());
    } else {
      scanner.init();
    }
    
    return scanner;
  };

  /**
   * Versione semplificata per auto-submit
   */
  window.initQrScannerAutoSubmit = function(containerId, formId, resultInputId = 'qr-result') {
    return window.initQrScanner(containerId, null, {
      autoSubmit: true,
      formId: formId,
      resultInputId: resultInputId,
      manualInputId: 'qr-manual'
    });
  };

  console.log('✅ Modulo QR Scanner caricato');

})(window);

