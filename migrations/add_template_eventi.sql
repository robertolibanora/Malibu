-- Crea tabella per i format (template eventi ricorrenti)
CREATE TABLE IF NOT EXISTS template_eventi (
  id_template INT AUTO_INCREMENT PRIMARY KEY,
  nome VARCHAR(100) NOT NULL UNIQUE,
  categoria VARCHAR(50) NOT NULL DEFAULT 'altro',
  tipo_musica VARCHAR(50) NULL,
  capienza INT NULL
);


