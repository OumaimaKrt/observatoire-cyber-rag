# ============================================================================
# migrer_classification_history.py
# Migration de la table classification_history
# ============================================================================

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from config import DB_CONFIG


def migrer_classification_history():
    """
    Ajoute les colonnes nécessaires à classification_history.
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Vérifier et ajouter confiance_globale
        cur.execute("""
            SELECT COUNT(*) 
            FROM information_schema.columns 
            WHERE table_name = 'classification_history' 
              AND column_name = 'confiance_globale'
        """)
        
        exists = cur.fetchone()[0]
        
        if exists == 0:
            print("📌 Ajout de la colonne 'confiance_globale'...")
            cur.execute("""
                ALTER TABLE classification_history 
                ADD COLUMN confiance_globale FLOAT
            """)
            conn.commit()
            print("✅ Colonne 'confiance_globale' ajoutée")
        else:
            print("✅ Colonne 'confiance_globale' existe déjà")
        
        # Vérifier et ajouter type_acteur
        cur.execute("""
            SELECT COUNT(*) 
            FROM information_schema.columns 
            WHERE table_name = 'classification_history' 
              AND column_name = 'type_acteur'
        """)
        
        exists_type = cur.fetchone()[0]
        
        if exists_type == 0:
            print("📌 Ajout de la colonne 'type_acteur'...")
            cur.execute("""
                ALTER TABLE classification_history 
                ADD COLUMN type_acteur VARCHAR(50)
            """)
            conn.commit()
            print("✅ Colonne 'type_acteur' ajoutée")
        else:
            print("✅ Colonne 'type_acteur' existe déjà")
        
        # Afficher les colonnes
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'classification_history' 
            ORDER BY ordinal_position
        """)
        
        print("\n📋 Colonnes de classification_history:")
        for row in cur.fetchall():
            print(f"   - {row[0]} ({row[1]})")
        
        cur.close()
        conn.close()
        print("\n✅ Migration terminée")
        
    except psycopg2.Error as e:
        print(f"❌ Erreur PostgreSQL: {e}")
        if 'conn' in locals():
            conn.rollback()
        raise
    except Exception as e:
        print(f"❌ Erreur: {e}")
        raise


if __name__ == "__main__":
    print("=" * 70)
    print("  🔧 MIGRATION DE classification_history")
    print("=" * 70)
    migrer_classification_history()
    print("=" * 70)