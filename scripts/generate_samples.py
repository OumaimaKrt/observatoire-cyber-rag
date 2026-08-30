# scripts/generate_samples.py
# ============================================================================
# Génère des échantillons de données pour l'encadrante
# Exporte en CSV des échantillons diversifiés par source
# ============================================================================
import sys
import os
import pandas as pd
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DB_CONFIG
from utils.logger import get_logger

logger = get_logger("generate_samples")

# Dossier de sortie
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data_sample")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def get_connection():
    """Retourne une connexion PostgreSQL."""
    import psycopg2
    return psycopg2.connect(**DB_CONFIG)


def get_source_distribution(conn):
    """
    Récupère la distribution des sources dans la base.
    """
    query = """
        SELECT 
            source,
            COUNT(*) as nb,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) as pct
        FROM cyber_incidents
        WHERE source IS NOT NULL AND source != ''
        GROUP BY source
        ORDER BY nb DESC
    """
    return pd.read_sql(query, conn)


def generate_cyber_incidents_sample_stratified(limit: int = 100):
    """
    Génère un échantillon stratifié par source.
    Chaque source est représentée proportionnellement à sa présence dans la base.
    """
    conn = get_connection()
    
    # 1. Récupérer la distribution des sources
    df_sources = get_source_distribution(conn)
    
    if df_sources.empty:
        print("⚠️ Aucune source trouvée dans la base")
        conn.close()
        return pd.DataFrame()
    
    # 2. Calculer le nombre d'échantillons par source (proportionnel)
    total = df_sources['nb'].sum()
    df_sources['sample_size'] = (df_sources['nb'] / total * limit).round().astype(int)
    
    # 3. Ajuster pour atteindre exactement 'limit'
    diff = limit - df_sources['sample_size'].sum()
    if diff > 0:
        # Ajouter aux sources les plus importantes
        for i in range(diff):
            idx = df_sources['nb'].idxmax()
            df_sources.loc[idx, 'sample_size'] += 1
            df_sources.loc[idx, 'nb'] -= 1
    elif diff < 0:
        # Retirer des sources les moins importantes
        for i in range(abs(diff)):
            idx = df_sources[df_sources['sample_size'] > 0]['nb'].idxmin()
            df_sources.loc[idx, 'sample_size'] -= 1
    
    # 4. Récupérer les échantillons pour chaque source
    dfs = []
    sampling_details = []
    
    for _, row in df_sources.iterrows():
        if row['sample_size'] > 0:
            query = f"""
                SELECT 
                    id,
                    source,
                    source_ext_id,
                    titre,
                    LEFT(description, 500) as description,
                    date_incident,
                    type_menace,
                    secteur_cible,
                    severite,
                    pays,
                    score_cvss,
                    pertinence_pme,
                    technologies_detectees,
                    confiance_type,
                    confiance_secteur,
                    confiance_severite,
                    confiance_globale,
                    risque,
                    niveau_risque,
                    acteur_menace,
                    preuves_menace,
                    preuves_secteur,
                    preuves_severite,
                    created_at
                FROM cyber_incidents
                WHERE source = '{row['source']}'
                ORDER BY date_incident DESC, created_at DESC
                LIMIT {row['sample_size']}
            """
            
            try:
                df_temp = pd.read_sql(query, conn)
                dfs.append(df_temp)
                sampling_details.append({
                    'source': row['source'],
                    'total_db': row['nb'],
                    'pct_db': row['pct'],
                    'sample_size': row['sample_size'],
                    'actual_size': len(df_temp)
                })
            except Exception as e:
                print(f"  ⚠️ Erreur pour la source {row['source']}: {e}")
    
    conn.close()
    
    if not dfs:
        return pd.DataFrame()
    
    df = pd.concat(dfs, ignore_index=True)
    
    # 5. Afficher les détails de l'échantillonnage
    print("\n📊 Détails de l'échantillonnage stratifié:")
    print("-" * 70)
    for detail in sampling_details:
        ratio = detail['sample_size'] / detail['total_db'] * 100 if detail['total_db'] > 0 else 0
        print(f"  {detail['source']:<20} "
              f"DB: {detail['total_db']:>5} ({detail['pct_db']:>5.1f}%) → "
              f"Sample: {detail['sample_size']:>3} ({ratio:.1f}%)")
    print("-" * 70)
    print(f"  Total échantillon: {len(df)}")
    
    return df


def generate_cyber_incidents_sample_diverse(limit: int = 100):
    """
    Génère un échantillon diversifié avec un nombre égal par source.
    """
    conn = get_connection()
    
    # Récupérer les sources disponibles
    df_sources = get_source_distribution(conn)
    
    if df_sources.empty:
        conn.close()
        return pd.DataFrame()
    
    # Calculer le nombre par source
    n_sources = len(df_sources)
    per_source = max(1, limit // n_sources)
    
    dfs = []
    for src in df_sources['source']:
        query = f"""
            SELECT 
                id,
                source,
                source_ext_id,
                titre,
                LEFT(description, 500) as description,
                date_incident,
                type_menace,
                secteur_cible,
                severite,
                pays,
                score_cvss,
                pertinence_pme,
                technologies_detectees,
                confiance_type,
                confiance_secteur,
                confiance_severite,
                confiance_globale,
                risque,
                niveau_risque,
                acteur_menace,
                preuves_menace,
                preuves_secteur,
                preuves_severite,
                created_at
            FROM cyber_incidents
            WHERE source = '{src}'
            ORDER BY date_incident DESC, created_at DESC
            LIMIT {per_source}
        """
        try:
            df_temp = pd.read_sql(query, conn)
            dfs.append(df_temp)
        except Exception as e:
            print(f"  ⚠️ Erreur pour la source {src}: {e}")
    
    conn.close()
    
    if not dfs:
        return pd.DataFrame()
    
    df = pd.concat(dfs, ignore_index=True)
    df = df.head(limit)  # Limiter au nombre demandé
    
    print("\n📊 Détails de l'échantillonnage diversifié:")
    print("-" * 70)
    source_counts = df['source'].value_counts()
    for src, count in source_counts.items():
        print(f"  {src:<20} {count:>3} incidents")
    print("-" * 70)
    
    return df


def generate_cyber_incidents_sample_recent(limit: int = 100):
    """
    Génère les 100 incidents les plus récents (méthode d'origine).
    """
    conn = get_connection()
    
    query = f"""
        SELECT 
            id,
            source,
            source_ext_id,
            titre,
            LEFT(description, 500) as description,
            date_incident,
            type_menace,
            secteur_cible,
            severite,
            pays,
            score_cvss,
            pertinence_pme,
            technologies_detectees,
            confiance_type,
            confiance_secteur,
            confiance_severite,
            confiance_globale,
            risque,
            niveau_risque,
            acteur_menace,
            preuves_menace,
            preuves_secteur,
            preuves_severite,
            created_at
        FROM cyber_incidents
        ORDER BY created_at DESC
        LIMIT {limit}
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    print("\n📊 Détails de l'échantillon récent:")
    print("-" * 70)
    source_counts = df['source'].value_counts()
    for src, count in source_counts.items():
        print(f"  {src:<20} {count:>3} incidents")
    print("-" * 70)
    
    return df


def generate_cyber_incidents_sample(limit: int = 100, method: str = 'stratified'):
    """
    Génère un échantillon des incidents cyber.
    
    Args:
        limit: Nombre d'incidents à récupérer
        method: 'stratified' (recommandé), 'diverse', ou 'recent'
    """
    print(f"\n📥 Génération d'un échantillon ({method})...")
    
    if method == 'stratified':
        df = generate_cyber_incidents_sample_stratified(limit)
    elif method == 'diverse':
        df = generate_cyber_incidents_sample_diverse(limit)
    else:
        df = generate_cyber_incidents_sample_recent(limit)
    
    if df.empty:
        print("❌ Aucune donnée récupérée")
        return df
    
    # Nettoyer les colonnes pour l'export
    list_columns = ['technologies_detectees', 'preuves_menace', 'preuves_secteur', 'preuves_severite']
    for col in list_columns:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: ', '.join(x) if isinstance(x, list) else x
            )
    
    # Ajouter une colonne pour les statistiques
    df['statut_classification'] = df.apply(
        lambda row: 'OK' if row['type_menace'] != 'INCONNU' else 'A_CLASSIFIER',
        axis=1
    )
    
    # Ajouter des métadonnées
    df['date_export'] = datetime.now().strftime('%Y-%m-%d')
    
    # Réorganiser les colonnes
    cols = [
        'id', 'source', 'titre', 'description', 'date_incident',
        'type_menace', 'secteur_cible', 'severite',
        'confiance_type', 'confiance_secteur', 'confiance_severite', 'confiance_globale',
        'risque', 'niveau_risque',
        'acteur_menace', 'preuves_menace',
        'pertinence_pme', 'technologies_detectees',
        'statut_classification', 'date_export', 'created_at'
    ]
    df = df[[c for c in cols if c in df.columns]]
    
    return df


def generate_sector_news_sample(limit: int = 50):
    """
    Génère un échantillon des news sectorielles.
    Prend les 50 plus récentes.
    """
    conn = get_connection()
    
    try:
        query = f"""
            SELECT 
                id,
                source,
                source_ext_id,
                titre,
                LEFT(description, 500) as description,
                date_publication,
                categorie,
                url_source,
                pays,
                langue,
                created_at
            FROM sector_news
            ORDER BY date_publication DESC, created_at DESC
            LIMIT {limit}
        """
        df = pd.read_sql(query, conn)
        conn.close()
        
        if df.empty:
            print("⚠️ Aucune donnée dans sector_news")
            return pd.DataFrame()
        
        df['date_export'] = datetime.now().strftime('%Y-%m-%d')
        return df
        
    except Exception as e:
        print(f"⚠️ Table sector_news non disponible: {e}")
        conn.close()
        return pd.DataFrame()


def generate_summary():
    """
    Génère un résumé des statistiques.
    Version corrigée pour PostgreSQL.
    """
    conn = get_connection()
    
    try:
        # Total incidents
        total = pd.read_sql("SELECT COUNT(*) as total FROM cyber_incidents", conn)['total'][0]
        
        # Distribution des sources
        df_sources = pd.read_sql("""
            SELECT 
                source,
                COUNT(*) as nb,
                ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) as pct
            FROM cyber_incidents
            WHERE source IS NOT NULL AND source != ''
            GROUP BY source
            ORDER BY nb DESC
        """, conn)
        
        # Distribution type_menace
        df_type = pd.read_sql("""
            SELECT 
                type_menace,
                COUNT(*) as nb,
                ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) as pct
            FROM cyber_incidents
            GROUP BY type_menace
            ORDER BY nb DESC
            LIMIT 10
        """, conn)
        
        # Distribution secteurs
        df_secteur = pd.read_sql("""
            SELECT 
                secteur_cible,
                COUNT(*) as nb,
                ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) as pct
            FROM cyber_incidents
            GROUP BY secteur_cible
            ORDER BY nb DESC
            LIMIT 10
        """, conn)
        
        # Distribution severites
        df_severite = pd.read_sql("""
            SELECT 
                severite,
                COUNT(*) as nb,
                ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) as pct
            FROM cyber_incidents
            GROUP BY severite
            ORDER BY nb DESC
        """, conn)
        
        # Statistiques de confiance - Version corrigée PostgreSQL
        confiance_stats = pd.read_sql("""
            SELECT 
                ROUND(AVG(confiance_type) * 100)::numeric as avg_type,
                ROUND(AVG(confiance_secteur) * 100)::numeric as avg_secteur,
                ROUND(AVG(confiance_severite) * 100)::numeric as avg_severite,
                ROUND(AVG(confiance_globale) * 100)::numeric as avg_globale
            FROM cyber_incidents
        """, conn)
        
        conn.close()
        
        return {
            'total': total,
            'sources': df_sources,
            'type_menace': df_type,
            'secteur_cible': df_secteur,
            'severite': df_severite,
            'confiance': confiance_stats
        }
        
    except Exception as e:
        print(f"❌ Erreur lors de la génération du résumé: {e}")
        conn.close()
        return None


def save_summary(summary, output_dir):
    """Sauvegarde le résumé en CSV et texte."""
    if summary is None:
        return
    
    # Sauvegarder les CSV
    for key in ['sources', 'type_menace', 'secteur_cible', 'severite']:
        if key in summary and not summary[key].empty:
            filename = f"summary_{key}.csv"
            summary[key].to_csv(
                os.path.join(output_dir, filename),
                index=False,
                encoding='utf-8-sig'
            )
    
    # Sauvegarder la confiance
    if 'confiance' in summary and not summary['confiance'].empty:
        summary['confiance'].to_csv(
            os.path.join(output_dir, 'summary_confiance.csv'),
            index=False,
            encoding='utf-8-sig'
        )
    
    # Créer un fichier texte
    with open(os.path.join(output_dir, 'summary.txt'), 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write("  OBSERVATOIRE CYBER PME MAROC - RESUME DES DONNEES\n")
        f.write("=" * 70 + "\n")
        f.write(f"  Date : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 70 + "\n\n")
        
        f.write(f"  Total incidents : {summary['total']:,}\n\n")
        
        f.write("  Distribution des sources :\n")
        for _, row in summary['sources'].iterrows():
            f.write(f"    {row['source']:<20} {row['nb']:>6} ({row['pct']:>5.1f}%)\n")
        
        f.write("\n  Distribution type_menace :\n")
        for _, row in summary['type_menace'].iterrows():
            f.write(f"    {row['type_menace']:<20} {row['nb']:>6} ({row['pct']:>5.1f}%)\n")
        
        f.write("\n  Distribution secteur_cible :\n")
        for _, row in summary['secteur_cible'].iterrows():
            f.write(f"    {row['secteur_cible']:<20} {row['nb']:>6} ({row['pct']:>5.1f}%)\n")
        
        f.write("\n  Distribution severite :\n")
        for _, row in summary['severite'].iterrows():
            f.write(f"    {row['severite']:<20} {row['nb']:>6} ({row['pct']:>5.1f}%)\n")
        
        f.write("\n  Scores de confiance moyens :\n")
        if not summary['confiance'].empty:
            row = summary['confiance'].iloc[0]
            f.write(f"    Type      : {row['avg_type']:>5.1f}%\n")
            f.write(f"    Secteur   : {row['avg_secteur']:>5.1f}%\n")
            f.write(f"    Sévérité  : {row['avg_severite']:>5.1f}%\n")
            f.write(f"    Globale   : {row['avg_globale']:>5.1f}%\n")
        else:
            f.write("    Données de confiance non disponibles\n")
        
        f.write("\n" + "=" * 70 + "\n")
        f.write("  FIN DU RESUME\n")
        f.write("=" * 70 + "\n")


def main():
    """Fonction principale."""
    print("\n" + "=" * 70)
    print("  GENERATION DES ECHANTILLONS DE DONNEES")
    print("=" * 70)
    
    # 1. Générer les incidents cyber avec échantillonnage stratifié
    print("\n[+] Génération des incidents cyber (échantillonnage stratifié)...")
    df_cyber = generate_cyber_incidents_sample(limit=100, method='stratified')
    
    if df_cyber.empty:
        print("❌ Erreur: Aucun incident récupéré")
        sys.exit(1)
    
    cyber_path = os.path.join(OUTPUT_DIR, 'cyber_incidents_sample.csv')
    df_cyber.to_csv(cyber_path, index=False, encoding='utf-8-sig')
    print(f"    ✅ {len(df_cyber)} incidents exportés dans {cyber_path}")
    
    # 2. Générer les news sectorielles
    print("\n[+] Génération des news sectorielles...")
    df_news = generate_sector_news_sample(limit=50)
    if not df_news.empty:
        news_path = os.path.join(OUTPUT_DIR, 'sector_news_sample.csv')
        df_news.to_csv(news_path, index=False, encoding='utf-8-sig')
        print(f"    ✅ {len(df_news)} news exportées dans {news_path}")
    else:
        print("    ⚠️ Aucune news exportée")
    
    # 3. Générer le résumé
    print("\n[+] Génération du résumé...")
    summary = generate_summary()
    if summary:
        save_summary(summary, OUTPUT_DIR)
        print(f"    ✅ Résumé généré dans {os.path.join(OUTPUT_DIR, 'summary.txt')}")
    else:
        print("    ⚠️ Erreur lors de la génération du résumé")
    
    # 4. Créer un fichier README
    print("\n[+] Création du README...")
    readme_path = os.path.join(OUTPUT_DIR, 'README.txt')
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write("  DONNEES DE L'OBSERVATOIRE CYBER PME MAROC\n")
        f.write("=" * 70 + "\n")
        f.write("\nCe dossier contient des echantillons des donnees collectees.\n\n")
        f.write("Fichiers disponibles :\n")
        f.write("  - cyber_incidents_sample.csv : 100 incidents (echantillonnage stratifie)\n")
        f.write("  - sector_news_sample.csv     : 50 dernieres news sectorielles\n")
        f.write("  - summary.txt                : Resume statistique\n")
        f.write("  - summary_*.csv              : Donnees detaillees\n\n")
        f.write("Methodologie d'echantillonnage :\n")
        f.write("  - Echantillonnage stratifie par source\n")
        f.write("  - Chaque source est representee proportionnellement\n")
        f.write("  - Garantit une diversite des sources dans l'echantillon\n\n")
        f.write("Ces donnees sont au format CSV (UTF-8 avec BOM) et peuvent etre\n")
        f.write("ouvertes avec Excel ou tout autre tableur.\n")
        f.write("Les colonnes sont auto-documentees.\n")
        f.write("-" * 70 + "\n")
        f.write(f"Date de generation : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 70 + "\n")
    print(f"    ✅ README créé dans {readme_path}")
    
    print("\n" + "=" * 70)
    print("  EXPORT TERMINE")
    print("=" * 70)
    print(f"📁 Dossier : {OUTPUT_DIR}")
    print(f"📊 Nombre d'incidents : {len(df_cyber)}")
    print(f"📊 Sources représentées : {df_cyber['source'].nunique()}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()