-- Aggiunge colonna template_id a eventi e FK verso template_eventi
ALTER TABLE eventi
  ADD COLUMN IF NOT EXISTS template_id INT NULL;

-- In alcuni RDBMS (es. MySQL <8) non esiste IF NOT EXISTS su ADD CONSTRAINT.
-- Creiamo la FK in modo idempotente se possibile, altrimenti lanciare manualmente.
ALTER TABLE eventi
  ADD CONSTRAINT fk_eventi_template
  FOREIGN KEY (template_id)
  REFERENCES template_eventi(id_template)
  ON UPDATE CASCADE
  ON DELETE SET NULL;


