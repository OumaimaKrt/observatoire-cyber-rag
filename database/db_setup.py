# database/db_setup.py
import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DB_CONFIG
from utils.logger import get_logger

logger = get_logger("db_setup")


def get_connection():
    """Retourne une connexion PostgreSQL."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.OperationalError as e:
        logger.error(f"Connexion PostgreSQL echouee : {e}")
        raise


def create_database():
    """Cree la base de donnees si elle n'existe pas."""
    config = DB_CONFIG.copy()
    dbname = config.pop("database")

    try:
        conn = psycopg2.connect(**config, dbname="postgres")
        conn.autocommit = True
        cur = conn.cursor()

        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
        exists = cur.fetchone()

        if not exists:
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
            logger.info(f"Base de donnees '{dbname}' creee avec succes.")
        else:
            logger.info(f"Base de donnees '{dbname}' existe deja.")

        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Erreur creation base : {e}")
        raise


def create_tables():
    """Cree toutes les tables du projet."""
    conn = get_connection()
    cur = conn.cursor()

    # ─── 1. sources_donnees ──────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sources_donnees (
            id              SERIAL PRIMARY KEY,
            nom             VARCHAR(100)  UNIQUE NOT NULL,
            url             TEXT,
            type_source     VARCHAR(50),
            format_donnees  VARCHAR(20),
            langue          VARCHAR(20),
            frequence_maj   VARCHAR(50),
            priorite        INTEGER       DEFAULT 2,
            est_actif       BOOLEAN       DEFAULT TRUE,
            derniere_collecte TIMESTAMP,
            nb_incidents    INTEGER       DEFAULT 0,
            notes           TEXT,
            created_at      TIMESTAMP     DEFAULT NOW()
        );
    """)
    logger.info("Table 'sources_donnees' creee/verifiee.")

    # ─── 2. cyber_incidents ────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cyber_incidents (
            id              SERIAL PRIMARY KEY,
            source_id       INTEGER       REFERENCES sources_donnees(id) ON DELETE SET NULL,
            source          VARCHAR(50)   NOT NULL,
            source_ext_id   VARCHAR(200)  UNIQUE,
            titre           TEXT          NOT NULL,
            description     TEXT,
            date_incident   TIMESTAMP,
            date_collecte   TIMESTAMP     DEFAULT NOW(),
            type_menace     VARCHAR(50)   DEFAULT 'INCONNU',
            secteur_cible   VARCHAR(50)   DEFAULT 'INCONNU',
            severite        VARCHAR(20)   DEFAULT 'INCONNU',
            pays            VARCHAR(10)   DEFAULT 'MA',
            score_cvss      FLOAT,
            url_source      TEXT,
            langue          VARCHAR(5)    DEFAULT 'fr',
            est_annote      BOOLEAN       DEFAULT FALSE,
            raw_data        JSONB,
            created_at      TIMESTAMP     DEFAULT NOW(),
            updated_at      TIMESTAMP     DEFAULT NOW(),
            -- Colonnes de confiance et risque
            confiance_type FLOAT,
            confiance_secteur FLOAT,
            confiance_severite FLOAT,
            confiance_globale FLOAT,
            niveau_confiance_type VARCHAR(20),
            niveau_confiance_secteur VARCHAR(20),
            niveau_confiance_severite VARCHAR(20),
            risque INTEGER,
            niveau_risque VARCHAR(20),
            acteur_menace VARCHAR(100),
            type_acteur VARCHAR(50),
            confiance_acteur FLOAT,
            preuves_menace TEXT[],
            preuves_secteur TEXT[],
            preuves_severite TEXT[],
            classification_method VARCHAR(50),
            classification_model VARCHAR(50),
            ancienne_confiance_type FLOAT,
            nouvelle_confiance_type FLOAT,
            pertinence_pme VARCHAR(20) DEFAULT 'INCONNUE',
            technologies_detectees TEXT[]
        );
    """)
    logger.info("Table 'cyber_incidents' creee/verifiee.")

    # ─── 3. sector_news ──────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sector_news (
            id              SERIAL PRIMARY KEY,
            source_id       INTEGER       REFERENCES sources_donnees(id) ON DELETE SET NULL,
            source          VARCHAR(50)   NOT NULL,
            source_ext_id   VARCHAR(200)  UNIQUE,
            titre           TEXT          NOT NULL,
            description     TEXT,
            date_publication TIMESTAMP,
            categorie       VARCHAR(50),
            url_source      TEXT,
            pays            VARCHAR(10)   DEFAULT 'MA',
            langue          VARCHAR(5)    DEFAULT 'fr',
            raw_data        JSONB,
            created_at      TIMESTAMP     DEFAULT NOW(),
            -- Colonnes de confiance et risque pour les news
            confiance_type FLOAT,
            confiance_secteur FLOAT,
            confiance_severite FLOAT,
            confiance_globale FLOAT,
            niveau_confiance_type VARCHAR(20),
            niveau_confiance_secteur VARCHAR(20),
            niveau_confiance_severite VARCHAR(20),
            risque INTEGER,
            acteur_menace VARCHAR(100),
            preuves_menace TEXT[],
            preuves_secteur TEXT[],
            preuves_severite TEXT[]
        );
    """)
    logger.info("Table 'sector_news' creee/verifiee.")

    # ─── 4. classification_history ──────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS classification_history (
            id SERIAL PRIMARY KEY,
            incident_id INTEGER REFERENCES cyber_incidents(id) ON DELETE CASCADE,
            ancien_type VARCHAR(50),
            nouveau_type VARCHAR(50),
            ancien_secteur VARCHAR(50),
            nouveau_secteur VARCHAR(50),
            ancienne_severite VARCHAR(20),
            nouvelle_severite VARCHAR(20),
            confiance_type FLOAT,
            confiance_secteur FLOAT,
            confiance_severite FLOAT,
            confiance_globale FLOAT,
            ancienne_confiance_type FLOAT,
            nouvelle_confiance_type FLOAT,
            ancien_risque INTEGER,
            nouveau_risque INTEGER,
            preuves_menace TEXT[],
            preuves_secteur TEXT[],
            preuves_severite TEXT[],
            acteur_menace VARCHAR(100),
            type_acteur VARCHAR(50),
            date_modification TIMESTAMP DEFAULT NOW(),
            modele_version VARCHAR(20) DEFAULT '1.0',
            source VARCHAR(100)
        )
    """)
    logger.info("Table 'classification_history' creee/verifiee.")

    # ─── 5. classification_metrics ──────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS classification_metrics (
            id SERIAL PRIMARY KEY,
            run_id VARCHAR(50),
            date_run TIMESTAMP DEFAULT NOW(),
            source VARCHAR(100),
            nb_incidents INTEGER,
            nb_modifies_type INTEGER,
            nb_modifies_secteur INTEGER,
            nb_modifies_severite INTEGER,
            moyenne_confiance_type FLOAT,
            moyenne_confiance_secteur FLOAT,
            moyenne_confiance_severite FLOAT,
            moyenne_confiance_globale FLOAT,
            moyenne_risque FLOAT,
            modele_version VARCHAR(20) DEFAULT '1.0'
        )
    """)
    logger.info("Table 'classification_metrics' creee/verifiee.")

    # ─── 6. historique_collecte ─────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS historique_collecte (
            id              SERIAL PRIMARY KEY,
            source          VARCHAR(50)   NOT NULL,
            date_debut      TIMESTAMP     NOT NULL,
            date_fin        TIMESTAMP,
            alertes_trouvees INTEGER      DEFAULT 0,
            nouvelles_inserees INTEGER    DEFAULT 0,
            duree_secondes  FLOAT,
            statut          VARCHAR(20)   DEFAULT 'EN_COURS',
            erreur          TEXT,
            created_at      TIMESTAMP     DEFAULT NOW()
        );
    """)
    logger.info("Table 'historique_collecte' creee/verifiee.")

    # ─── Index ──────────────────────────────────────────────────────────────
    try:
        cur.execute("CREATE INDEX IF NOT EXISTS idx_incidents_source ON cyber_incidents(source);")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_cyber_incidents_source_ext_id ON cyber_incidents(source_ext_id) WHERE source_ext_id IS NOT NULL AND source_ext_id <> '';")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_incidents_type ON cyber_incidents(type_menace);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_incidents_secteur ON cyber_incidents(secteur_cible);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_incidents_date ON cyber_incidents(date_incident);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_incidents_pertinence_pme ON cyber_incidents(pertinence_pme);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sector_news_source ON sector_news(source);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sector_news_date ON sector_news(date_publication);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sector_news_categorie ON sector_news(categorie);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_classification_history_incident ON classification_history(incident_id);")
    except Exception as e:
        logger.warning(f"Index existants: {e}")
    
    logger.info("Index crees/verifies.")

    # ─── Sources de reference ───────────────────────────────────────────────
    sources = [
        ("NVD - NIST", "https://nvd.nist.gov/developers/vulnerabilities", "API REST", "JSON", "en", "En continu", 3),
        ("CIRCL CVE Search", "https://cve.circl.lu/api", "API REST", "JSON", "en", "En continu", 3),
        ("DGSSI-maCERT", "https://www.dgssi.gov.ma/fr/bulletins-securite/", "Web scraping", "HTML", "fr", "Quotidien", 3),
        ("ANSSI_France", "https://www.cert.ssi.gouv.fr/feed/", "RSS", "XML", "fr", "Quotidien", 2),
        ("CISA_USA", "https://www.cisa.gov/news.xml", "RSS", "XML", "en", "Quotidien", 2),
        ("TheHackersNews", "https://feeds.feedburner.com/TheHackersNews", "RSS", "XML", "en", "Quotidien", 2),
        ("BleepingComputer", "https://www.bleepingcomputer.com/feed/", "RSS", "XML", "en", "Quotidien", 2),
        ("SANS_ISC", "https://isc.sans.edu/rssfeed_full.xml", "RSS", "XML", "en", "Quotidien", 2),
        ("AlienVault_OTX", "https://otx.alienvault.com", "API REST", "JSON", "en", "Temps reel", 3),
        ("ExploitDB", "https://exploit-db.com", "CSV/API", "CSV/JSON", "en", "Quotidien", 2),
        ("ANRT_Maroc", "https://www.anrt.ma/lagence/actualites", "Web scraping (Selenium)", "HTML", "fr", "Hebdomadaire", 2),
        ("HCP_Maroc", "https://www.hcp.ma/", "Web scraping", "HTML", "fr", "Hebdomadaire", 2),
        ("BAM_Maroc", "https://www.bkam.ma/Communiques", "Web scraping", "HTML", "fr", "Hebdomadaire", 1),
        ("MTNRA_Maroc", "https://www.mmsp.gov.ma/fr/actualites", "Web scraping", "HTML", "fr", "Hebdomadaire", 2),
        ("Le360_Maroc", "https://fr.le360.ma/", "Web scraping", "HTML", "fr", "Quotidien", 2),
        ("Medias24_Tech", "https://medias24.com/categorie/tech-medias/", "Web scraping", "HTML", "fr", "Quotidien", 2),
        ("Telquel_Tech", "https://telquel.ma/", "Web scraping", "HTML", "fr", "Quotidien", 2),
        ("Challenge_Tech", "https://www.challenge.ma/tech-numerique/", "Web scraping", "HTML", "fr", "Quotidien", 2),
        ("LEconomiste_Tech", "https://www.leconomiste.com/technologie", "Web scraping", "HTML", "fr", "Quotidien", 2),
        ("URLhaus", "https://urlhaus.abuse.ch", "API REST", "JSON", "en", "Temps reel", 3),
        ("AbuseIPDB", "https://api.abuseipdb.com/api/v2", "API REST", "JSON", "en", "Temps reel", 3),
    ]
    for s in sources:
        cur.execute("""
            INSERT INTO sources_donnees (nom, url, type_source, format_donnees, langue, frequence_maj, priorite)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (nom) DO UPDATE SET
                url = EXCLUDED.url,
                type_source = EXCLUDED.type_source,
                format_donnees = EXCLUDED.format_donnees,
                langue = EXCLUDED.langue,
                frequence_maj = EXCLUDED.frequence_maj,
                priorite = EXCLUDED.priorite;
        """, s)
    logger.info("Sources de reference inserees/mises a jour.")

    conn.commit()
    cur.close()
    conn.close()
    logger.info("Toutes les tables sont pretes.")


def test_connection():
    """Teste la connexion et affiche les stats."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    tables = ["cyber_incidents", "sources_donnees", "historique_collecte", "sector_news", "classification_history", "classification_metrics"]
    print("\n" + "=" * 60)
    print("  OBSERVATOIRE CYBER PME MAROC — Etat de la base")
    print("=" * 60)
    for table in tables:
        try:
            cur.execute(
                sql.SQL("SELECT COUNT(*) as n FROM {}").format(sql.Identifier(table))
            )
            row = cur.fetchone()
            print(f"  {table:<25} {row['n']:>8} enregistrements")
        except psycopg2.errors.UndefinedTable:
            conn.rollback()
            print(f"  {table:<25} ATTENTION Table non creee")
    print("=" * 60 + "\n")

    cur.close()
    conn.close()


if __name__ == "__main__":
    logger.info("=== Setup base de donnees ===")
    create_database()
    create_tables()
    test_connection()
    logger.info("Base de donnees prete.")