# ============================================================================
# config.py
# Configuration complète du système avec paramètres optimisés pour le RAG
# ============================================================================

import os
from dotenv import load_dotenv

load_dotenv()

# ─── Base de données ──────────────────────────────────────────────────────────
DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", 5432)),
    "database": os.getenv("DB_NAME", "observatoire_cyber"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

# ─── Chemins ──────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CHROMA_PATH = os.path.join(DATA_DIR, "chroma_db")
PDF_PATH = os.path.join(DATA_DIR, "Guide-de-bonnes-pratique.pdf")
LOG_DIR = os.path.join(BASE_DIR, "logs")

# ─── Embeddings (MODÈLE MULTILINGUE OPTIMISÉ) ──────────────────────────────
EMBEDDING_CONFIG = {
    "model_name": "BAAI/bge-m3",           
    "device": "cuda",                      
    "normalize_embeddings": True,
}

# ─── Chunking (OPTIMISÉ) ─────────────────────────────────────────────────────
CHUNKING_CONFIG = {
    "chunk_size": 400,                     # Plus petit = plus précis
    "chunk_overlap": 100,                  # 25% de recouvrement
    "separators": ["\n\n", "\n", ".", "!", "?", ";", " "],
    "length_function": len,
}

# ─── Retriever (MMR pour diversité) ─────────────────────────────────────────
RETRIEVER_CONFIG = {
    "search_type": "mmr",                  # 🔥 Max Marginal Relevance
    "search_kwargs": {
        "k": 10,                           # Top 10 résultats
        "fetch_k": 20,                     # Récupérer 20 avant de filtrer
        "lambda_mult": 0.7,                # 0 = max diversité, 1 = max similarité
    }
}

# ─── Reranker ─────────────────────────────────────────────────────────────────
RERANKER_CONFIG = {
    "model_name": "BAAI/bge-reranker-base",
    "threshold": 0.3,                      # Score minimum pour conserver un document
}

# ─── Collections ChromaDB ────────────────────────────────────────────────────
COLLECTIONS = {
    "guide": "cmrpi_guide",
    "incidents": "cyber_incidents",
    "news": "sector_news"
}

# ─── Réponse ─────────────────────────────────────────────────────────────────
RESPONSE_CONFIG = {
    "max_recommandations": 4,
    "max_statistiques": 3,
    "max_actualites": 2,
    "max_sources": 5,
    "lang_default": "fr",
}

# ─── APIs externes ───────────────────────────────────────────────────────────
ABUSEIPDB_API_KEY = os.getenv("ABUSEIPDB_API_KEY", "")
ABUSEIPDB_API_URL = "https://api.abuseipdb.com/api/v2"

URLHAUS_API_URL = "https://urlhaus-api.abuse.ch/v1/urls/recent/limit/{limit}/"
URLHAUS_API_KEY = os.getenv("URLHAUS_API_KEY", "")

NVD_API_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
NVD_API_KEY = os.getenv("NVD_API_KEY", "")
NVD_RESULTS_PER_PAGE = 100
NVD_RATE_DELAY = 1                        # 🔥 Correction: 1 seconde entre les requêtes

CIRCL_API_URL = "https://cve.circl.lu/api/last"

ALIENVAULT_OTX_URL = "https://otx.alienvault.com/api/v1/pulses/subscribed"
OTX_API_KEY = os.getenv("OTX_API_KEY", "")

EXPLOITDB_URL = "https://exploit-db.com/api/exploits/"

SHODAN_API_URL = "https://api.shodan.io"
SHODAN_API_KEY = os.getenv("SHODAN_API_KEY", "")

# ─── Sources marocaines ──────────────────────────────────────────────────────
CNDP_URL = "https://www.cndp.ma/category/actualites/"
CNDP_COMMUNIQUES_URL = "https://www.cndp.ma/communiques-de-presse/"

DGSSI_URL_FR = "https://www.dgssi.gov.ma/fr/bulletins-securite/"
DGSSI_URL_AR = "https://www.dgssi.gov.ma/ar/bulletins-securite/"
DGSSI_BULLETINS_URL = DGSSI_URL_FR
DGSSI_MACERT_URL = "https://www.dgssi.gov.ma/fr/macert"
DGSSI_URL = DGSSI_BULLETINS_URL

CERTMA_URL = DGSSI_MACERT_URL

ANRT_URL_FR = "https://www.anrt.ma/lagence/actualites"
ANRT_URL_AR = "https://www.anrt.ma/ar/lagence/actualites"

BAM_COMMUNIQUES_URL = "https://www.bkam.ma/Communiques"
MIN_TRANSITION_NUMERIQUE_URL = "https://www.mmsp.gov.ma/fr/actualites"

LE360_URL = "https://fr.le360.ma/"

MEDIAS24_TECH_URL = "https://medias24.com/categorie/tech-medias/"
TELQUEL_TECH_URL = "https://telquel.ma/tech"
TELQUEL_CYBER_URL = "https://telquel.ma/tag/cybersecurite"
CHALLENGE_TECH_URL = "https://www.challenge.ma/tech-numerique/"
LECONOMISTE_TECH_URL = "https://www.leconomiste.com/technologie"

# ─── Flux RSS ────────────────────────────────────────────────────────────────
RSS_SOURCES = [
    {"nom": "ZDNet_France", "url": "https://www.zdnet.fr/feeds/rss/actualites/", "langue": "fr", "pays": "FR", "generaliste": True},
    {"nom": "LeMagIT", "url": "https://www.lemagit.fr/rss/ContentSyndication.xml", "langue": "fr", "pays": "FR", "generaliste": True},
    {"nom": "ANSSI_France", "url": "https://www.cert.ssi.gouv.fr/feed/", "langue": "fr", "pays": "FR"},
    {"nom": "CISA_USA", "url": "https://www.cisa.gov/news.xml", "langue": "en", "pays": "US"},
    {"nom": "TheHackersNews", "url": "https://feeds.feedburner.com/TheHackersNews", "langue": "en", "pays": "US"},
    {"nom": "BleepingComputer", "url": "https://www.bleepingcomputer.com/feed/", "langue": "en", "pays": "US"},
    {"nom": "SANS_ISC", "url": "https://isc.sans.edu/rssfeed_full.xml", "langue": "en", "pays": "US"},
]

# ─── Labels de classification ──────────────────────────────────────────────
LABELS_MENACES = [
    "Phishing", "Keylogger", "Ransomware", "Spyware", "Cheval_de_Troie",
    "Spam", "Spoofing", "DDoS", "Blanchiment", "Escroquerie_paiement",
    "Piratage", "Virus", "Ver_informatique", "Inconnu"
]

LABELS_SECTEURS = [
    "Commerce_Retail", "Industrie_Manufacturing", "Services", "BTP_Construction",
    "Sante_Pharmacie", "Finance_Assurance", "Transport_Logistique",
    "Hotellerie_Tourisme", "IT_Telecom",
    "Agroalimentaire", "Energie", "Education",
    "Inconnu"
]

LABELS_SEVERITE = ["CRITIQUE", "ELEVEE", "MOYENNE", "FAIBLE", "INCONNUE"]
LABELS_PERTINENCE_PME = ["HAUTE", "MOYENNE", "FAIBLE", "INCONNUE"]

# ─── Paramètres réseau ──────────────────────────────────────────────────────
REQUEST_TIMEOUT = 30
REQUEST_DELAY = 1.5

# ─── Noms des sources pour l'affichage ──────────────────────────────────────
SOURCE_NAMES = {
    "Guide CMRPI": "Guide CMRPI - Bonnes pratiques cybersécurité",
    "cyber_incidents": "Observatoire Cyber - Incidents",
    "sector_news": "Presse sectorielle",
    "LeMagIT": "LeMagIT",
    "TheHackersNews": "The Hackers News",
    "BleepingComputer": "Bleeping Computer",
    "ZDNet_France": "ZDNet France",
    "ANSSI_France": "ANSSI France",
    "CISA_USA": "CISA USA",
    "SANS_ISC": "SANS ISC",
    "AlienVault_OTX": "AlienVault OTX",
    "Shodan": "Shodan",
    "NVD": "NIST NVD",
    "CIRCL": "CIRCL CVE",
    "DGSSI": "DGSSI Maroc",
    "CNDP": "CNDP Maroc",
    "ANRT": "ANRT Maroc",
    "BAM": "Bank Al-Maghrib",
    "LE360": "Le360",
    "MEDIAS24": "Medias24",
    "TELQUEL": "Telquel",
    "CHALLENGE": "Challenge",
    "LECONOMISTE": "L'Économiste",
}

# ─── Mots-clés pour la détection d'intention ──────────────────────────────
INTENT_KEYWORDS = {
    "guide": [
        "protéger", "sécuriser", "bonne pratique", "comment", "que faire",
        "prévenir", "éviter", "sauvegarder", "recommande", "conseil",
        "mesure", "politique", "procédure", "sensibiliser", "former",
        "pare-feu", "antivirus", "chiffrement", "authentification",
        "guide", "cmrpi", "bonnes pratiques", "recommandation"
    ],
    "incidents": [
        "attaque", "ransomware", "phishing", "malware", "virus", "piratage",
        "ddos", "cve", "incident", "menace", "vulnérabilité", "exploit",
        "intrusion", "compromission", "fuite", "donnée", "cyberattaque"
    ],
    "stats": [
        "combien", "nombre", "statistique", "tendance", "évolution",
        "pourcentage", "top", "classement", "plus actif", "fréquence",
        "proportion", "répartition", "moyenne", "total", "volume"
    ],
    "actualites": [
        "actualité", "dernier", "récent", "nouveau", "annonce", "alerte",
        "presse", "article", "dernières", "breve", "communiqué"
    ]
}

# ─── Mots français pour la détection de texte exploitable ──────────────────
MOTS_FRANCAIS_COURANTS = [
    " le ", " la ", " les ", " de ", " des ", " du ", " un ", " une ",
    " et ", " est ", " pour ", " dans ", " que ", " qui ", " sur ",
    " avec ", " ce ", " ces ", " son ", " sont ", " par ", " au ", " aux ",
]

# ─── Mots-clés malwares ──────────────────────────────────────────────────────
MALWARE_KEYWORDS = [
    # Ransomware
    "ransomware", "lockbit", "blackcat", "conti", "clop", "reveton",
    "wannacry", "petya", "notpetya", "ryuk", "darkside", "hive",
    "locker", "crypto", "bitlocker", "dearcry",
    # Malwares
    "trickbot", "emotet", "qbot", "mirai", "agent tesla",
    "formbook", "guloader", "dridex", "ursnif", "azeq",
    # Types
    "phishing", "spyware", "spoofing", "ddos", "trojan",
    "virus", "worm", "keylogger", "rootkit", "backdoor",
    "rat", "stealer", "botnet", "info-stealer", "dropper",
    # Familles
    "apt", "avalanche", "bazar", "brute force", "credential stuffing"
]

# ─── Mots-clés secteurs ──────────────────────────────────────────────────────
SECTEUR_KEYWORDS = [
    "finance", "banque", "assurance", "fintech", "cryptomonnaie",
    "telecom", "opérateur", "internet", "mobile", "réseau",
    "sante", "hôpital", "clinique", "médical", "pharmacie",
    "education", "université", "école", "formation", "recherche",
    "industrie", "manufacture", "usine", "production", "logistique",
    "commerce", "e-commerce", "retail", "distribution", "vente",
    "transport", "logistique", "aérien", "maritime", "ferroviaire",
    "energie", "électricité", "pétrole", "gaz", "renouvelable",
    "btp", "construction", "immobilier", "génie civil",
    "services", "conseil", "audit", "juridique", "comptabilité",
    "automobile", "constructeur", "pièces", "réparation",
    "aerospace", "défense", "aéronautique", "spatial",
    "agroalimentaire", "agriculture", "viticulture", "élevage",
    "hotellerie", "tourisme", "restauration", "loisirs"
]