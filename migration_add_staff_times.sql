-- ============================================================================
-- Migration: Aggiunta colonne staff_open_at e staff_close_at alla tabella eventi
-- Data: 2025-01-XX
-- Descrizione: Aggiunge i campi per gestire l'operatività staff basata su orari
-- ============================================================================

USE malibu;

-- Aggiungi colonne per apertura/chiusura automatica evento (se non esistono già)
ALTER TABLE eventi 
ADD COLUMN IF NOT EXISTS data_ora_apertura_auto DATETIME NULL COMMENT 'Quando aprire automaticamente l\'evento',
ADD COLUMN IF NOT EXISTS data_ora_chiusura_auto DATETIME NULL COMMENT 'Quando chiudere automaticamente l\'evento';

-- Aggiungi colonne per orari operatività staff
ALTER TABLE eventi 
ADD COLUMN IF NOT EXISTS staff_open_at DATETIME NULL COMMENT 'Quando lo staff può iniziare a operare',
ADD COLUMN IF NOT EXISTS staff_close_at DATETIME NULL COMMENT 'Quando lo staff deve smettere di operare';

-- Aggiungi indici per migliorare le performance delle query
CREATE INDEX IF NOT EXISTS idx_eventi_staff_open_at ON eventi(staff_open_at);
CREATE INDEX IF NOT EXISTS idx_eventi_staff_close_at ON eventi(staff_close_at);
CREATE INDEX IF NOT EXISTS idx_eventi_data_ora_apertura_auto ON eventi(data_ora_apertura_auto);
CREATE INDEX IF NOT EXISTS idx_eventi_data_ora_chiusura_auto ON eventi(data_ora_chiusura_auto);

