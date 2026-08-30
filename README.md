

## Structure du projet

```
observatoire_cyber/
│
├── config.py                  # Configuration centralisée (DB, APIs, labels)
├── run_mardi.py               # ▶ Script principal du mardi
│
├── database/
│   └── db_setup.py            # Création PostgreSQL + toutes les tables
│
├── collectors/
│   ├── collect_cve.py         # Collecteur NVD + CIRCL (CVE)
│   └── collect_maroc.py       # Scraper CERT-MA + DGSSI
│
├── utils/
│   └── logger.py              # Logging centralisé
│
├── logs/
│   └── observatoire.log       # Logs automatiques
│
└── data/                      # Données brutes téléchargées
```

---

## Installation

```bash
# 1. Cloner le repo
git clone https://github.com/TON_USERNAME/observatoire-cyber-pme-maroc.git
cd observatoire-cyber-pme-maroc

# 2. Créer environnement virtuel
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows

# 3. Installer les dépendances
pip install requests beautifulsoup4 psycopg2-binary

# 4. Configurer PostgreSQL dans config.py
# Modifier DB_CONFIG avec tes identifiants PostgreSQL
```

---

## Lancement rapide (mardi)

```bash
# Tout lancer en une seule commande
python run_mardi.py
```

Ou étape par étape :

```bash
# 1. Setup base de données
python database/db_setup.py

# 2. Collecter CVE (NVD + CIRCL)
python collectors/collect_cve.py

# 3. Scraper CERT-MA + DGSSI
python collectors/collect_maroc.py
```

---

## Tables PostgreSQL créées

| Table | Description |
|-------|-------------|
| `cyber_incidents` | Table principale unifiée — tous les incidents |
| `cve_vulnerabilities` | CVE techniques (NVD + CIRCL) |
| `alertes_maroc` | Alertes CERT-MA et DGSSI |
| `sources_donnees` | Référentiel des sources |
| `dataset_annote` | Dataset annoté pour l'entraînement AI |

---

## Labels de classification (guide CMRPI/AUSIM)

**Menaces :** Phishing, Ransomware, Keylogger, Spyware, Cheval_de_Troie,
Spam, Spoofing, DDoS, Blanchiment, Escroquerie_paiement, Piratage, Virus, Ver_informatique

**Secteurs :** Commerce_Retail, Industrie_Manufacturing, Services,
BTP_Construction, Sante_Pharmacie, Finance_Assurance, Transport_Logistique,
Hotellerie_Tourisme, IT_Telecom

---

## Prochaines étapes

- **Mercredi S3** : Apache Airflow pour automatisation + NER spaCy
- **S2** : Setup Ollama + Mistral 7B + ChromaDB → module RAG
- **S4** : Fine-tuning LoRA + évaluation RAGAS

---

*Stage PFA 2026 — CMRPI Espace Maroc Cyberconfiance*
*Superviseur : Dr. Yasmina Al Marouni | Dr. Rachid Abouettahir*
