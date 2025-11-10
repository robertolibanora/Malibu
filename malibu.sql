-- ============================================================================
-- Malibu Nightclub Platform - Complete Database Schema
-- Target: MySQL 8.x (InnoDB, utf8mb4_unicode_ci)
-- This script creates the entire schema from scratch, including seed data.
-- ============================================================================

DROP DATABASE IF EXISTS malibu;
CREATE DATABASE malibu CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE malibu;

-- --------------------------------------------------------------------------
-- Table: clienti
-- --------------------------------------------------------------------------
CREATE TABLE clienti (
  id_cliente INT AUTO_INCREMENT PRIMARY KEY,
  nome VARCHAR(50) NOT NULL,
  cognome VARCHAR(50) NOT NULL,
  data_nascita DATE NULL,
  citta VARCHAR(100) NULL,
  telefono VARCHAR(20) UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  data_registrazione DATETIME DEFAULT CURRENT_TIMESTAMP,
  ultimo_accesso DATETIME DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
  qr_code VARCHAR(255) UNIQUE,
  livello ENUM('base', 'loyal', 'premium', 'vip') DEFAULT 'base',
  punti_fedelta INT DEFAULT 0,
  stato_account ENUM('attivo', 'disattivato') NOT NULL DEFAULT 'attivo',
  nota_staff TEXT NULL,
  INDEX idx_clienti_telefono (telefono),
  INDEX idx_clienti_livello (livello)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------------------------
-- Table: staff
-- --------------------------------------------------------------------------
CREATE TABLE staff (
  id_staff INT AUTO_INCREMENT PRIMARY KEY,
  nome VARCHAR(100) NOT NULL,
  ruolo ENUM('admin', 'barista', 'ingressista') NOT NULL DEFAULT 'ingressista',
  username VARCHAR(50) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  attivo BOOLEAN DEFAULT TRUE,
  INDEX idx_staff_ruolo (ruolo),
  INDEX idx_staff_attivo (attivo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------------------------
-- Table: eventi
-- --------------------------------------------------------------------------
CREATE TABLE eventi (
  id_evento INT AUTO_INCREMENT PRIMARY KEY,
  nome_evento VARCHAR(100) NOT NULL,
  data_evento DATE NOT NULL,
  tipo_musica VARCHAR(50),
  dj_artista VARCHAR(100),
  promozione VARCHAR(200),
  capienza_max INT DEFAULT 2500,
  categoria ENUM('reggaeton', 'techno', 'privato', 'altro') DEFAULT 'altro',
  stato ENUM('attivo', 'chiuso') DEFAULT 'attivo',
  stato_pubblico ENUM('programmato', 'attivo', 'chiuso') NOT NULL DEFAULT 'programmato',
  is_staff_operativo BOOLEAN NOT NULL DEFAULT FALSE,
  cover_url VARCHAR(255),
  template_id INT NULL,
  INDEX idx_eventi_data (data_evento),
  INDEX idx_eventi_stato_pubblico (stato_pubblico),
  INDEX idx_eventi_is_staff_operativo (is_staff_operativo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- template_eventi referenced by app; can be created separately if needed.

-- --------------------------------------------------------------------------
-- Table: prenotazioni
-- --------------------------------------------------------------------------
CREATE TABLE prenotazioni (
  id_prenotazione INT AUTO_INCREMENT PRIMARY KEY,
  cliente_id INT NOT NULL,
  evento_id INT NOT NULL,
  tipo ENUM('lista', 'tavolo', 'prevendita') NOT NULL,
  num_persone INT DEFAULT NULL,
  orario_previsto TIME DEFAULT NULL,
  note TEXT,
  stato ENUM('attiva', 'no-show', 'usata', 'cancellata') DEFAULT 'attiva',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_prenotazioni_cliente (cliente_id),
  INDEX idx_prenotazioni_evento (evento_id),
  INDEX idx_prenotazioni_stato (stato),
  CONSTRAINT fk_prenotazioni_clienti
    FOREIGN KEY (cliente_id) REFERENCES clienti(id_cliente)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_prenotazioni_eventi
    FOREIGN KEY (evento_id) REFERENCES eventi(id_evento)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DELIMITER //

CREATE TRIGGER trg_prenotazioni_before_insert
BEFORE INSERT ON prenotazioni
FOR EACH ROW
BEGIN
  IF NEW.stato = 'attiva' THEN
    IF EXISTS (
      SELECT 1
      FROM prenotazioni p
      WHERE p.cliente_id = NEW.cliente_id
        AND p.evento_id = NEW.evento_id
        AND p.stato = 'attiva'
    ) THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Prenotazione attiva già presente per questo cliente ed evento';
    END IF;
  END IF;
END//

CREATE TRIGGER trg_prenotazioni_before_update
BEFORE UPDATE ON prenotazioni
FOR EACH ROW
BEGIN
  IF NEW.stato = 'attiva' THEN
    IF EXISTS (
      SELECT 1
      FROM prenotazioni p
      WHERE p.cliente_id = NEW.cliente_id
        AND p.evento_id = NEW.evento_id
        AND p.stato = 'attiva'
        AND p.id_prenotazione <> NEW.id_prenotazione
    ) THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Prenotazione attiva già presente per questo cliente ed evento';
    END IF;
  END IF;
END//

DELIMITER ;

-- --------------------------------------------------------------------------
-- Table: ingressi
-- --------------------------------------------------------------------------
CREATE TABLE ingressi (
  id_ingresso INT AUTO_INCREMENT PRIMARY KEY,
  cliente_id INT NOT NULL,
  evento_id INT NOT NULL,
  prenotazione_id INT NULL,
  staff_id INT NULL,
  tipo_ingresso ENUM('lista', 'tavolo', 'omaggio', 'prevendita') NOT NULL,
  orario_ingresso DATETIME DEFAULT CURRENT_TIMESTAMP,
  note TEXT,
  UNIQUE KEY uniq_ingressi_cliente_evento (cliente_id, evento_id),
  INDEX idx_ingressi_evento (evento_id),
  INDEX idx_ingressi_cliente (cliente_id),
  INDEX idx_ingressi_staff (staff_id),
  CONSTRAINT fk_ingressi_clienti
    FOREIGN KEY (cliente_id) REFERENCES clienti(id_cliente)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_ingressi_eventi
    FOREIGN KEY (evento_id) REFERENCES eventi(id_evento)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_ingressi_prenotazioni
    FOREIGN KEY (prenotazione_id) REFERENCES prenotazioni(id_prenotazione)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_ingressi_staff
    FOREIGN KEY (staff_id) REFERENCES staff(id_staff)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------------------------
-- Table: consumi
-- --------------------------------------------------------------------------
CREATE TABLE consumi (
  id_consumo INT AUTO_INCREMENT PRIMARY KEY,
  cliente_id INT NOT NULL,
  evento_id INT NOT NULL,
  staff_id INT NULL,
  prodotto_id INT NULL,
  prodotto VARCHAR(100) NOT NULL,
  importo DECIMAL(8,2) NOT NULL,
  data_consumo DATETIME DEFAULT CURRENT_TIMESTAMP,
  punto_vendita ENUM('bar', 'tavolo', 'privè') NOT NULL DEFAULT 'bar',
  note TEXT,
  INDEX idx_consumi_evento (evento_id),
  INDEX idx_consumi_cliente (cliente_id),
  INDEX idx_consumi_data (data_consumo),
  CONSTRAINT fk_consumi_clienti
    FOREIGN KEY (cliente_id) REFERENCES clienti(id_cliente)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_consumi_eventi
    FOREIGN KEY (evento_id) REFERENCES eventi(id_evento)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_consumi_staff
    FOREIGN KEY (staff_id) REFERENCES staff(id_staff)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------------------------
-- Table: prodotti
-- --------------------------------------------------------------------------
CREATE TABLE prodotti (
  id_prodotto INT AUTO_INCREMENT PRIMARY KEY,
  nome VARCHAR(100) NOT NULL UNIQUE,
  prezzo DECIMAL(8,2) NOT NULL,
  categoria VARCHAR(50) NULL,
  attivo BOOLEAN DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Link optional: consumi.prodotto_id references prodotti
ALTER TABLE consumi
  ADD CONSTRAINT fk_consumi_prodotti
    FOREIGN KEY (prodotto_id) REFERENCES prodotti(id_prodotto)
    ON DELETE SET NULL ON UPDATE CASCADE;

-- --------------------------------------------------------------------------
-- Table: fedelta
-- --------------------------------------------------------------------------
CREATE TABLE fedelta (
  id_fedelta INT AUTO_INCREMENT PRIMARY KEY,
  cliente_id INT NOT NULL,
  evento_id INT NOT NULL,
  punti INT NOT NULL,
  motivo VARCHAR(200),
  data_assegnazione DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_fedelta_cliente (cliente_id),
  INDEX idx_fedelta_evento (evento_id),
  CONSTRAINT fk_fedelta_clienti
    FOREIGN KEY (cliente_id) REFERENCES clienti(id_cliente)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_fedelta_eventi
    FOREIGN KEY (evento_id) REFERENCES eventi(id_evento)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------------------------
-- Table: soglie_fedelta
-- --------------------------------------------------------------------------
CREATE TABLE soglie_fedelta (
  id INT AUTO_INCREMENT PRIMARY KEY,
  livello ENUM('base','loyal','premium','vip') NOT NULL UNIQUE,
  punti_min INT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO soglie_fedelta (livello, punti_min) VALUES
('base', 0),
('loyal', 100),
('premium', 250),
('vip', 500);

-- --------------------------------------------------------------------------
-- Table: feedback
-- --------------------------------------------------------------------------
CREATE TABLE feedback (
  id_feedback INT AUTO_INCREMENT PRIMARY KEY,
  cliente_id INT NOT NULL,
  evento_id INT NOT NULL,
  voto_musica TINYINT UNSIGNED CHECK (voto_musica BETWEEN 1 AND 10),
  voto_ingresso TINYINT UNSIGNED CHECK (voto_ingresso BETWEEN 1 AND 10),
  voto_ambiente TINYINT UNSIGNED CHECK (voto_ambiente BETWEEN 1 AND 10),
  data_feedback DATETIME DEFAULT CURRENT_TIMESTAMP,
  note TEXT,
  INDEX idx_feedback_evento (evento_id),
  INDEX idx_feedback_cliente (cliente_id),
  CONSTRAINT fk_feedback_clienti
    FOREIGN KEY (cliente_id) REFERENCES clienti(id_cliente)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_feedback_eventi
    FOREIGN KEY (evento_id) REFERENCES eventi(id_evento)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------------------------
-- Table: log_attivita
-- --------------------------------------------------------------------------
CREATE TABLE log_attivita (
  id_log INT AUTO_INCREMENT PRIMARY KEY,
  tabella VARCHAR(50) NOT NULL,
  record_id INT NOT NULL,
  staff_id INT NULL,
  azione ENUM(
    'insert',
    'update',
    'delete',
    'evento_create',
    'evento_duplicate',
    'set_operativo',
    'unset_operativo',
    'event_close',
    'override_capienza',
    'prenotazione_usata',
    'ingresso_automatico',
    'no_show_assegnato'
  ) NOT NULL,
  note VARCHAR(255) NULL,
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_log_tabella (tabella),
  INDEX idx_log_staff (staff_id),
  CONSTRAINT fk_log_staff
    FOREIGN KEY (staff_id) REFERENCES staff(id_staff)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------------------------
-- Consistency triggers / checks (optional comments)
-- --------------------------------------------------------------------------
-- NOTE:
-- Enforce single active prenotazione per cliente/evento via application logic,
-- or via partial unique index (supported in MySQL 8.0.13+ using generated column).
-- Example (not executed by default):
-- ALTER TABLE prenotazioni
--   ADD COLUMN is_attiva TINYINT AS (stato = 'attiva') STORED,
--   ADD UNIQUE KEY uniq_pren_attiva (cliente_id, evento_id, is_attiva)
--   WHERE is_attiva = 1;

-- --------------------------------------------------------------------------
-- End of schema
-- --------------------------------------------------------------------------

