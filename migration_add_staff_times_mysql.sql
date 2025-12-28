-- ============================================================================
-- Migration: Aggiunta colonne staff_open_at e staff_close_at alla tabella eventi
-- Data: 2025-01-XX
-- Descrizione: Aggiunge i campi per gestire l'operatività staff basata su orari
-- Versione MySQL compatibile (senza IF NOT EXISTS nelle colonne)
-- ============================================================================

USE malibu;

-- Verifica e aggiungi colonne per apertura/chiusura automatica evento
-- Nota: MySQL non supporta IF NOT EXISTS per ADD COLUMN, quindi verifica manualmente
-- Se le colonne esistono già, questo script darà errore - ignorare in quel caso

ALTER TABLE eventi 
ADD COLUMN data_ora_apertura_auto DATETIME NULL COMMENT 'Quando aprire automaticamente l\'evento';

ALTER TABLE eventi 
ADD COLUMN data_ora_chiusura_auto DATETIME NULL COMMENT 'Quando chiudere automaticamente l\'evento';

-- Aggiungi colonne per orari operatività staff
ALTER TABLE eventi 
ADD COLUMN staff_open_at DATETIME NULL COMMENT 'Quando lo staff può iniziare a operare';

ALTER TABLE eventi 
ADD COLUMN staff_close_at DATETIME NULL COMMENT 'Quando lo staff deve smettere di operare';

-- Aggiungi indici per migliorare le performance delle query
-- Nota: MySQL non supporta IF NOT EXISTS per CREATE INDEX, quindi verifica manualmente
CREATE INDEX idx_eventi_staff_open_at ON eventi(staff_open_at);
CREATE INDEX idx_eventi_staff_close_at ON eventi(staff_close_at);
CREATE INDEX idx_eventi_data_ora_apertura_auto ON eventi(data_ora_apertura_auto);
CREATE INDEX idx_eventi_data_ora_chiusura_auto ON eventi(data_ora_chiusura_auto);

