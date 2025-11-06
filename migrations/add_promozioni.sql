-- Tabella promozioni (benefit per clienti)
CREATE TABLE IF NOT EXISTS promozioni (
  id_promozione INT AUTO_INCREMENT PRIMARY KEY,
  nome VARCHAR(100) NOT NULL,
  descrizione TEXT,
  tipo ENUM('sconto_percentuale', 'sconto_fisso', 'omaggio', 'ingresso_gratis', 'consumo_gratis', 'altro') NOT NULL DEFAULT 'altro',
  valore DECIMAL(8,2) NULL, -- percentuale o importo fisso a seconda del tipo
  condizioni TEXT, -- condizioni per ottenere la promozione
  attiva BOOLEAN DEFAULT TRUE,
  data_inizio DATE NULL,
  data_fine DATE NULL,
  livello_richiesto ENUM('base', 'loyal', 'premium', 'vip') NULL, -- livello minimo richiesto
  punti_richiesti INT NULL, -- punti minimi richiesti
  auto_assegnazione BOOLEAN DEFAULT FALSE, -- se true, viene assegnata automaticamente alla registrazione
  
  INDEX idx_attiva (attiva),
  INDEX idx_data_inizio (data_inizio),
  INDEX idx_data_fine (data_fine)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabella di collegamento clienti-promozioni
CREATE TABLE IF NOT EXISTS clienti_promozioni (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cliente_id INT NOT NULL,
  promozione_id INT NOT NULL,
  data_assegnazione DATETIME DEFAULT CURRENT_TIMESTAMP,
  data_scadenza DATE NULL,
  usata BOOLEAN DEFAULT FALSE,
  data_uso DATETIME NULL,
  note TEXT,
  
  INDEX idx_cliente_id (cliente_id),
  INDEX idx_promozione_id (promozione_id),
  INDEX idx_usata (usata),
  INDEX idx_data_scadenza (data_scadenza),
  
  CONSTRAINT fk_clienti_promozioni_cliente
    FOREIGN KEY (cliente_id) REFERENCES clienti(id_cliente)
    ON DELETE CASCADE ON UPDATE CASCADE,
  
  CONSTRAINT fk_clienti_promozioni_promozione
    FOREIGN KEY (promozione_id) REFERENCES promozioni(id_promozione)
    ON DELETE CASCADE ON UPDATE CASCADE,
  
  UNIQUE KEY unique_cliente_promozione (cliente_id, promozione_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

