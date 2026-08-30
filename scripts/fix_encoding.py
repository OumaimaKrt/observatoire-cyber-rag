# scripts/fix_all_encoding.py
import sys
import os
import re

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from config import DB_CONFIG

def fix_text(text):
    if not text:
        return text
    
    replacements = {
        'Ç': 'é',
        'Ã©': 'é',
        'Ã¨': 'è',
        'Ãª': 'ê',
        'Ã«': 'ë',
        'Ã ': 'à',
        'Ã¢': 'â',
        'Ã¤': 'ä',
        'Ã´': 'ô',
        'Ã¶': 'ö',
        'Ã»': 'û',
        'Ã¼': 'ü',
        'Ã¯': 'ï',
        'Ã®': 'î',
        'Ã§': 'ç',
        'Ã¹': 'ù',
        'Ã‰': 'É',
        'Ãˆ': 'È',
        'ÃŠ': 'Ê',
        'Ã€': 'À',
        'Ã‡': 'Ç',
        'Ã”': 'Ô',
        'Ã›': 'Û',
        'Ã?': 'é',
        'Ã?': 'è',
        'Ã?': 'ê',
        'Ã?': 'à',
        'Ã?': 'ç',
        'Ã?': 'ô',
        'Ã?': 'ù',
        'Å“': 'œ',
        'Å’': 'Œ',
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    return text

def fix_table(table_name, columns):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Compter les lignes concernées
    where_clause = " OR ".join([f"{col} LIKE '%Ç%' OR {col} LIKE '%Ã%'" for col in columns])
    cur.execute(f"SELECT COUNT(*) FROM {table_name} WHERE {where_clause}")
    total = cur.fetchone()[0]
    
    if total == 0:
        print(f"✅ {table_name}: 0 lignes à corriger")
        return
    
    print(f"📊 {table_name}: {total} lignes à corriger")
    
    # Récupérer les données
    cur.execute(f"SELECT id, {', '.join(columns)} FROM {table_name} WHERE {where_clause}")
    rows = cur.fetchall()
    
    for row in rows:
        id_incident = row[0]
        updates = []
        for i, col in enumerate(columns, 1):
            if row[i]:
                new_val = fix_text(row[i])
                if new_val != row[i]:
                    updates.append((new_val, col))
        
        if updates:
            set_clause = ", ".join([f"{col} = %s" for _, col in updates])
            values = [val for val, _ in updates]
            cur.execute(f"UPDATE {table_name} SET {set_clause} WHERE id = %s", (*values, id_incident))
    
    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ {table_name}: {total} lignes corrigées")

def main():
    print("\n" + "=" * 60)
    print("  🔧 CORRECTION FINALE DE TOUTES LES TABLES")
    print("=" * 60)
    
    fix_table("cyber_incidents", ["titre", "description"])
    fix_table("sector_news", ["titre", "description"])
    fix_table("sources_donnees", ["nom"])
    
    print("\n" + "=" * 60)
    print("  ✅ CORRECTION TERMINÉE")
    print("=" * 60)

if __name__ == "__main__":
    main()