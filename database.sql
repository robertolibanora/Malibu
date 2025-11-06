CREATE TABLE clienti (
    id_cliente INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(50) NOT NULL,
    cognome VARCHAR(50) NOT NULL,
    data_nascita DATE NULL,
    citta VARCHAR(100) NULL,
    telefono VARCHAR(20) UNIQUE,
    password_hash VARCHAR(255) NOT NULL, -- NUOVA COLONNA: per l'autenticazione
    data_registrazione DATETIME DEFAULT CURRENT_TIMESTAMP,
    ultimo_accesso DATETIME DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
    qr_code VARCHAR(255) UNIQUE,
    livello ENUM('base', 'loyal', 'premium', 'vip') DEFAULT 'base',
    punti_fedelta INT DEFAULT 0,
    
    INDEX idx_qr_code (qr_code),
    INDEX idx_telefono (telefono),
    -- L'indice idx_email non è più necessario
    INDEX idx_livello (livello)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE staff (
    id_staff INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    ruolo ENUM('admin', 'staff', 'barista', 'cassa') NOT NULL DEFAULT 'staff',
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    attivo BOOLEAN DEFAULT TRUE,

    INDEX idx_ruolo (ruolo),
    INDEX idx_attivo (attivo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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

    INDEX idx_data_evento (data_evento),
    INDEX idx_stato (stato)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE prenotazioni (
    id_prenotazione INT AUTO_INCREMENT PRIMARY KEY,
    cliente_id INT NOT NULL,
    evento_id INT NOT NULL,
    tipo ENUM('lista', 'tavolo', 'prevendita') NOT NULL,
    num_persone INT DEFAULT NULL,
    orario_previsto TIME DEFAULT NULL,
    note TEXT,
    stato ENUM('attiva', 'no-show', 'usata', 'cancellata') DEFAULT 'attiva',

    INDEX idx_evento_id (evento_id),
    INDEX idx_cliente_id (cliente_id),
    INDEX idx_stato (stato),

    CONSTRAINT fk_prenotazioni_clienti 
        FOREIGN KEY (cliente_id) REFERENCES clienti(id_cliente)
        ON DELETE CASCADE ON UPDATE CASCADE,

    CONSTRAINT fk_prenotazioni_eventi 
        FOREIGN KEY (evento_id) REFERENCES eventi(id_evento)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE ingressi (
    id_ingresso INT AUTO_INCREMENT PRIMARY KEY,
    cliente_id INT NOT NULL,
    evento_id INT NOT NULL,
    prenotazione_id INT DEFAULT NULL,
    staff_id INT DEFAULT NULL,  -- ✅ consentito NULL
    tipo_ingresso ENUM('lista', 'tavolo', 'omaggio', 'prevendita') NOT NULL,
    orario_ingresso DATETIME DEFAULT CURRENT_TIMESTAMP,
    note TEXT,
    INDEX idx_evento_id (evento_id),
    INDEX idx_cliente_id (cliente_id),
    INDEX idx_orario_ingresso (orario_ingresso),
    CONSTRAINT fk_ingressi_clienti FOREIGN KEY (cliente_id) REFERENCES clienti(id_cliente)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_ingressi_eventi FOREIGN KEY (evento_id) REFERENCES eventi(id_evento)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_ingressi_prenotazioni FOREIGN KEY (prenotazione_id) REFERENCES prenotazioni(id_prenotazione)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_ingressi_staff FOREIGN KEY (staff_id) REFERENCES staff(id_staff)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE consumi (
    id_consumo INT AUTO_INCREMENT PRIMARY KEY,
    cliente_id INT NOT NULL,
    evento_id INT NOT NULL,
    staff_id INT DEFAULT NULL,  -- ✅ consentito NULL
    prodotto VARCHAR(100) NOT NULL,
    importo DECIMAL(8,2) NOT NULL,
    data_consumo DATETIME DEFAULT CURRENT_TIMESTAMP,
    punto_vendita ENUM('tavolo', 'privè') NOT NULL,
    note TEXT,
    INDEX idx_evento_id (evento_id),
    INDEX idx_data_consumo (data_consumo),
    INDEX idx_cliente_id (cliente_id),
    CONSTRAINT fk_consumi_clienti FOREIGN KEY (cliente_id) REFERENCES clienti(id_cliente)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_consumi_eventi FOREIGN KEY (evento_id) REFERENCES eventi(id_evento)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_consumi_staff FOREIGN KEY (staff_id) REFERENCES staff(id_staff)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE fedelta (
    id_fedelta INT AUTO_INCREMENT PRIMARY KEY,
    cliente_id INT NOT NULL,
    evento_id INT NOT NULL,
    punti INT NOT NULL,
    motivo VARCHAR(200),
    data_assegnazione DATETIME DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_cliente_id (cliente_id),
    INDEX idx_evento_id (evento_id),

    CONSTRAINT fk_fedelta_clienti
        FOREIGN KEY (cliente_id) REFERENCES clienti(id_cliente)
        ON DELETE CASCADE ON UPDATE CASCADE,

    CONSTRAINT fk_fedelta_eventi
        FOREIGN KEY (evento_id) REFERENCES eventi(id_evento)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE feedback (
    id_feedback INT AUTO_INCREMENT PRIMARY KEY,
    cliente_id INT NOT NULL,
    evento_id INT NOT NULL,
    voto_musica TINYINT UNSIGNED CHECK (voto_musica BETWEEN 1 AND 10),
    voto_ingresso TINYINT UNSIGNED CHECK (voto_ingresso BETWEEN 1 AND 10),
    voto_ambiente TINYINT UNSIGNED CHECK (voto_ambiente BETWEEN 1 AND 10),
    data_feedback DATETIME DEFAULT CURRENT_TIMESTAMP,
    note TEXT,

    INDEX idx_evento_id (evento_id),
    INDEX idx_cliente_id (cliente_id),

    CONSTRAINT fk_feedback_clienti
        FOREIGN KEY (cliente_id) REFERENCES clienti(id_cliente)
        ON DELETE CASCADE ON UPDATE CASCADE,

    CONSTRAINT fk_feedback_eventi
        FOREIGN KEY (evento_id) REFERENCES eventi(id_evento)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE log_attivita (
    id_log INT AUTO_INCREMENT PRIMARY KEY,
    tabella VARCHAR(50) NOT NULL,
    record_id INT NOT NULL,
    staff_id INT,
    azione ENUM('insert', 'update', 'delete') NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_tabella (tabella),
    INDEX idx_staff_id (staff_id),

    CONSTRAINT fk_log_staff
        FOREIGN KEY (staff_id) REFERENCES staff(id_staff)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

 Alter Table clienti 
    ADD COLUMN stato_account ENUM('attivo','disattivato') NOT NULL DEFAULT 'attivo' AFTER punti_fedelta,
    ADD COLUMN nota_staff TEXT NULL AFTER stato_account;

ALTER TABLE eventi
  ADD COLUMN cover_url VARCHAR(255) NULL AFTER promozione;

-- Tabella prodotti
CREATE TABLE prodotti (
  id_prodotto INT AUTO_INCREMENT PRIMARY KEY,
  nome VARCHAR(100) NOT NULL UNIQUE,
  prezzo DECIMAL(8,2) NOT NULL,
  categoria VARCHAR(50) NULL,
  attivo BOOLEAN DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- (Opzionale) collegare consumi a prodotti mantenendo anche il nome libero:
ALTER TABLE consumi
  ADD COLUMN prodotto_id INT NULL,
  ADD INDEX idx_prodotto_id (prodotto_id),
  ADD CONSTRAINT fk_consumi_prodotti
    FOREIGN KEY (prodotto_id) REFERENCES prodotti(id_prodotto)
    ON DELETE SET NULL ON UPDATE CASCADE;

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

-- Tabella promozioni (benefit per clienti)
CREATE TABLE promozioni (
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
CREATE TABLE clienti_promozioni (
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