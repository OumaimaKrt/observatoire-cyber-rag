# scripts/filter_existing_news.py (version avec suppression)
import sys
import os
import re
import psycopg2
import pandas as pd
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DB_CONFIG
from utils.logger import get_logger

logger = get_logger("filter_existing_news")

# --- MOTS-CLÉS CYBER (pour garder) ---
CYBER_KEYWORDS = [
    "cyber", "sécurité", "securite", "cybersécurité", "cybersecurite",
    "cyberattaque", "piratage", "ransomware", "phishing", "hameçonnage",
    "malware", "virus", "vulnérabilité", "vulnerabilite", "faille",
    "exploit", "zero-day", "CVE", "backdoor", "porte dérobée",
    "DGSSI", "maCERT", "CNDP", "ANRT", "RGPD",
    "menace", "attaque", "intrusion", "espionnage",
    "sécurité informatique", "protection des données",
    "ausimètre", "baromètre", "cybersécurité au maroc",
    "cloud", "données", "donnees", "confidentialité",
]

# --- MOTS-CLÉS D'EXCLUSION (pour supprimer) ---
EXCLUSION_KEYWORDS = [
    "football", "mondial", "coupe du monde", "joueur", "équipe", "fifa",
    "roi", "trône", "accession au trône", "marocain",
    "viande", "ovine", "consommation", "prix",
    "météo", "chaleur", "pluie", "température",
    "mariage", "naissance", "décès", "hommage",
    "sport", "culture", "cinéma", "musique",
    "artiste", "chanteur", "acteur",
    "protocole", "cérémonie", "visite officielle",
    "élection", "politique", "parti",
]

def is_cyber_news(titre: str, description: str) -> tuple:
    """Vérifie si un article est pertinent pour la cybersécurité."""
    texte = f"{titre} {description}".lower()
    
    # 1. Vérifier les exclusions (prioritaires)
    for excl in EXCLUSION_KEYWORDS:
        if excl in texte:
            return False, f"EXCLU: {excl}"
    
    # 2. Vérifier les mots-clés cyber
    for mot in CYBER_KEYWORDS:
        if mot in texte:
            return True, f"GARDÉ: {mot}"
    
    # 3. Vérifier les sources marocaines de cybersécurité
    sources_cyber = ["dgssi", "macert", "cndp", "anrt", "ausimètre"]
    for src in sources_cyber:
        if src in texte:
            return True, f"GARDÉ: source {src}"
    
    return False, "REJETÉ: aucun mot-clé"

def filter_news_sample(delete_from_db: bool = False):
    """
    Filtre les news pour ne garder que les pertinentes.
    
    Args:
        delete_from_db: Si True, supprime les articles non pertinents de la base
    """
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Récupérer les 50 dernières news
    cur.execute("""
        SELECT id, source, titre, description, categorie, url_source, date_publication
        FROM sector_news
        ORDER BY created_at DESC
        LIMIT 50
    """)
    
    articles = cur.fetchall()
    kept = []
    removed = []
    deleted_ids = []
    
    print("\n" + "=" * 70)
    print("  FILTRAGE DES NEWS SECTORIELLES")
    if delete_from_db:
        print("  ⚠️  MODE SUPPRESSION : les articles non pertinents seront supprimés de la base")
    else:
        print("  ℹ️  MODE ANALYSE : les articles ne sont PAS supprimés de la base")
    print("=" * 70)
    
    for art in articles:
        art_id, source, titre, description, categorie, url, date_pub = art
        description = description or ""
        
        pertinent, raison = is_cyber_news(titre, description)
        
        if pertinent:
            kept.append(art)
            print(f"  ✅ GARDÉ: {titre[:60]}... ({raison})")
        else:
            removed.append(art)
            deleted_ids.append(art_id)
            print(f"  ❌ SUPPRIMÉ: {titre[:60]}... ({raison})")
    
    # --- SUPPRESSION DE LA BASE (si demandée) ---
    if delete_from_db and deleted_ids:
        print("\n" + "-" * 70)
        print(f"  🗑️  Suppression de {len(deleted_ids)} articles de la base...")
        
        for art_id in deleted_ids:
            cur.execute("DELETE FROM sector_news WHERE id = %s", (art_id,))
        
        conn.commit()
        print(f"  ✅ {len(deleted_ids)} articles supprimés de la base")
    
    print("-" * 70)
    print(f"  📊 Résultat: {len(kept)} gardés, {len(removed)} supprimés")
    if delete_from_db:
        print(f"  🗑️  {len(deleted_ids)} supprimés de la base de données")
    print("=" * 70)
    
    # --- EXPORT CSV ---
    df_kept = pd.DataFrame(kept, columns=['id', 'source', 'titre', 'description', 
                                          'categorie', 'url_source', 'date_publication'])
    
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data_sample")
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(output_dir, 'sector_news_pertinent.csv')
    df_kept.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\n✅ Fichier CSV généré: {output_file}")
    
    # Afficher les articles gardés
    print("\n📋 ARTICLES GARDÉS:")
    for i, art in enumerate(kept[:10], 1):
        print(f"  {i}. {art[2][:80]}... ({art[1]})")
    
    cur.close()
    conn.close()
    
    return kept, removed

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Filtre les news sectorielles')
    parser.add_argument('--delete', action='store_true', 
                        help='Supprime les articles non pertinents de la base')
    args = parser.parse_args()
    
    # Par défaut: NE PAS supprimer
    kept, removed = filter_news_sample(delete_from_db=args.delete)