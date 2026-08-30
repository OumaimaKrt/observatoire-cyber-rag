# scripts/verify_reclassification.py
# ============================================================================
# Vérifie les résultats du reclassement AVANT d'appliquer
# ============================================================================
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
import pandas as pd
from config import DB_CONFIG
from utils.logger import get_logger

logger = get_logger("verify_reclassification")


def get_stats():
    """Récupère les statistiques actuelles."""
    conn = psycopg2.connect(**DB_CONFIG)
    
    print("\n" + "=" * 70)
    print("  STATISTIQUES ACTUELLES")
    print("=" * 70)
    
    # ─── 1. Distribution type_menace ────────────────────────────────────
    df_type = pd.read_sql("""
        SELECT 
            type_menace,
            COUNT(*) AS nb,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) AS pct
        FROM cyber_incidents
        GROUP BY type_menace
        ORDER BY nb DESC
        LIMIT 15
    """, conn)
    
    print("\n📌 Top 15 type_menace :")
    print(df_type.to_string(index=False))
    
    # ─── 2. Distribution secteur_cible ──────────────────────────────────
    df_secteur = pd.read_sql("""
        SELECT 
            secteur_cible,
            COUNT(*) AS nb,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) AS pct
        FROM cyber_incidents
        GROUP BY secteur_cible
        ORDER BY nb DESC
        LIMIT 15
    """, conn)
    
    print("\n Top 15 secteur_cible :")
    print(df_secteur.to_string(index=False))
    
    # ─── 3. Distribution severite ───────────────────────────────────────
    df_severite = pd.read_sql("""
        SELECT 
            severite,
            COUNT(*) AS nb,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) AS pct
        FROM cyber_incidents
        GROUP BY severite
        ORDER BY nb DESC
    """, conn)
    
    print("\n Distribution severite :")
    print(df_severite.to_string(index=False))
    
    # ─── 4. Inconnus par source ─────────────────────────────────────────
    df_inconnus = pd.read_sql("""
        SELECT 
            source,
            COUNT(*) AS total,
            SUM(CASE WHEN type_menace = 'Inconnu' THEN 1 ELSE 0 END) AS type_inconnu,
            SUM(CASE WHEN secteur_cible = 'Inconnu' THEN 1 ELSE 0 END) AS secteur_inconnu,
            SUM(CASE WHEN severite = 'INCONNUE' THEN 1 ELSE 0 END) AS severite_inconnue
        FROM cyber_incidents
        GROUP BY source
        ORDER BY total DESC
    """, conn)
    
    print("\n Inconnus par source :")
    print(df_inconnus.to_string(index=False))
    
    # ─── 5. Synthèse ────────────────────────────────────────────────────
    total = pd.read_sql("SELECT COUNT(*) as total FROM cyber_incidents", conn)['total'][0]
    
    print("\n" + "=" * 70)
    print("   SYNTHÈSE")
    print("=" * 70)
    print(f"  Total incidents : {total}")
    
    # Type_menace
    df_type_count = pd.read_sql("""
        SELECT 
            COUNT(*) AS total,
            SUM(CASE WHEN type_menace = 'Inconnu' THEN 1 ELSE 0 END) AS inconnu
        FROM cyber_incidents
    """, conn)
    type_total = df_type_count['total'][0]
    type_inconnu = df_type_count['inconnu'][0]
    print(f"\n  type_menace :")
    print(f"    - Classifiés : {type_total - type_inconnu} ({(type_total - type_inconnu)/type_total*100:.1f}%)")
    print(f"    - Inconnus   : {type_inconnu} ({type_inconnu/type_total*100:.1f}%)")
    
    # Secteur_cible
    df_secteur_count = pd.read_sql("""
        SELECT 
            COUNT(*) AS total,
            SUM(CASE WHEN secteur_cible = 'Inconnu' THEN 1 ELSE 0 END) AS inconnu
        FROM cyber_incidents
    """, conn)
    secteur_total = df_secteur_count['total'][0]
    secteur_inconnu = df_secteur_count['inconnu'][0]
    print(f"\n  secteur_cible :")
    print(f"    - Classifiés : {secteur_total - secteur_inconnu} ({(secteur_total - secteur_inconnu)/secteur_total*100:.1f}%)")
    print(f"    - Inconnus   : {secteur_inconnu} ({secteur_inconnu/secteur_total*100:.1f}%)")
    
    # Severite
    df_severite_count = pd.read_sql("""
        SELECT 
            COUNT(*) AS total,
            SUM(CASE WHEN severite = 'INCONNUE' THEN 1 ELSE 0 END) AS inconnue
        FROM cyber_incidents
    """, conn)
    severite_total = df_severite_count['total'][0]
    severite_inconnue = df_severite_count['inconnue'][0]
    print(f"\n  severite :")
    print(f"    - Classifiés : {severite_total - severite_inconnue} ({(severite_total - severite_inconnue)/severite_total*100:.1f}%)")
    print(f"    - Inconnues  : {severite_inconnue} ({severite_inconnue/severite_total*100:.1f}%)")
    
    conn.close()
    
    return {
        'type': {'total': type_total, 'inconnu': type_inconnu},
        'secteur': {'total': secteur_total, 'inconnu': secteur_inconnu},
        'severite': {'total': severite_total, 'inconnue': severite_inconnue}
    }


def show_examples(source: str = None, limit: int = 5):
    """Affiche des exemples d'incidents à reclassifier."""
    conn = psycopg2.connect(**DB_CONFIG)
    
    where = f"AND source = '{source}'" if source else ""
    
    query = f"""
        SELECT 
            id, source, type_menace, secteur_cible, severite,
            LEFT(titre, 80) as titre_court
        FROM cyber_incidents
        WHERE (type_menace = 'Inconnu' OR secteur_cible = 'Inconnu' OR severite = 'INCONNUE')
        {where}
        ORDER BY created_at DESC
        LIMIT {limit}
    """
    
    df = pd.read_sql(query, conn)
    
    print("\n" + "=" * 70)
    print(f"   EXEMPLES D'INCIDENTS À RECLASSIFIER (limite: {limit})")
    print("=" * 70)
    
    if df.empty:
        print("   Aucun incident à reclassifier !")
    else:
        for _, row in df.iterrows():
            print(f"\n  ID {row['id']} | {row['source']}")
            print(f"    Titre : {row['titre_court']}...")
            print(f"    type_menace : {row['type_menace']}")
            print(f"    secteur_cible : {row['secteur_cible']}")
            print(f"    severite : {row['severite']}")
            print("-" * 40)
    
    conn.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Vérifie les statistiques actuelles avant reclassification."
    )
    parser.add_argument("--source", type=str, default=None, help="Filtrer par source.")
    parser.add_argument("--examples", type=int, default=5, help="Nombre d'exemples à afficher.")
    args = parser.parse_args()
    
    get_stats()
    show_examples(source=args.source, limit=args.examples)
    
    print("\n" + "=" * 70)
    print("  PROCHAINES ÉTAPES")
    print("=" * 70)
    print("  1. Vérifier les stats ci-dessus")
    print("  2. Lancer dry-run : python scripts/recompute_classification.py")
    print("  3. Vérifier les modifications proposées")
    print("  4. Appliquer : python scripts/recompute_classification.py --apply")
    print("  5. Relancer ce script pour voir l'amélioration")
    print("=" * 70)
    