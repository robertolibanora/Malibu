#!/usr/bin/env python3
"""
Script di migrazione per aggiungere colonne staff_open_at e staff_close_at
alla tabella eventi. Verifica se le colonne esistono già prima di aggiungerle.
"""
import sys
from sqlalchemy import text, inspect
from app.database import engine, SessionLocal

def column_exists(db, table_name, column_name):
    """Verifica se una colonna esiste nella tabella"""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

def run_migration():
    """Esegue la migrazione aggiungendo le colonne mancanti"""
    db = SessionLocal()
    
    try:
        print("🔍 Verifica colonne esistenti...")
        
        # Lista delle colonne da aggiungere
        columns_to_add = [
            ('data_ora_apertura_auto', 'DATETIME NULL COMMENT "Quando aprire automaticamente l\'evento"'),
            ('data_ora_chiusura_auto', 'DATETIME NULL COMMENT "Quando chiudere automaticamente l\'evento"'),
            ('staff_open_at', 'DATETIME NULL COMMENT "Quando lo staff può iniziare a operare"'),
            ('staff_close_at', 'DATETIME NULL COMMENT "Quando lo staff deve smettere di operare"'),
        ]
        
        # Lista degli indici da creare
        indexes_to_add = [
            ('idx_eventi_staff_open_at', 'staff_open_at'),
            ('idx_eventi_staff_close_at', 'staff_close_at'),
            ('idx_eventi_data_ora_apertura_auto', 'data_ora_apertura_auto'),
            ('idx_eventi_data_ora_chiusura_auto', 'data_ora_chiusura_auto'),
        ]
        
        # Aggiungi colonne mancanti
        for column_name, column_def in columns_to_add:
            if column_exists(db, 'eventi', column_name):
                print(f"  ✓ Colonna '{column_name}' già esistente, skip")
            else:
                print(f"  ➕ Aggiungo colonna '{column_name}'...")
                sql = f"ALTER TABLE eventi ADD COLUMN {column_name} {column_def}"
                db.execute(text(sql))
                db.commit()
                print(f"  ✓ Colonna '{column_name}' aggiunta con successo")
        
        # Aggiungi indici mancanti
        print("\n🔍 Verifica indici esistenti...")
        inspector = inspect(engine)
        existing_indexes = [idx['name'] for idx in inspector.get_indexes('eventi')]
        
        for index_name, column_name in indexes_to_add:
            if index_name in existing_indexes:
                print(f"  ✓ Indice '{index_name}' già esistente, skip")
            else:
                print(f"  ➕ Aggiungo indice '{index_name}' su '{column_name}'...")
                sql = f"CREATE INDEX {index_name} ON eventi({column_name})"
                db.execute(text(sql))
                db.commit()
                print(f"  ✓ Indice '{index_name}' creato con successo")
        
        print("\n✅ Migrazione completata con successo!")
        return True
        
    except Exception as e:
        print(f"\n❌ Errore durante la migrazione: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Migrazione: Aggiunta colonne staff_open_at e staff_close_at")
    print("=" * 60)
    
    success = run_migration()
    
    if success:
        print("\n🎉 Il database è stato aggiornato correttamente!")
        sys.exit(0)
    else:
        print("\n💥 La migrazione è fallita. Controlla gli errori sopra.")
        sys.exit(1)

