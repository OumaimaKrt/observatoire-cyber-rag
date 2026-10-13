
# 🛡️ Observatoire Cyber — Observatoire data-driven des cybermenaces visant les PME au Maroc

Plateforme d'observation, d'analyse et d'aide à l'exploitation de l'information cyber, qui collecte automatiquement des données de cybermenaces issues de sources hétérogènes, les normalise, les classifie, les enrichit, puis les exploite via un système **RAG (Retrieval-Augmented Generation)** et un **LLM local**.

> Projet réalisé au sein du **CMRPI – Espace Maroc Cyberconfiance (EMC)**
> **Réalisé par :** Oumaima Kourchte · **Encadrante :** Dr. Yasmina Al Marouni
> **Formation :** Master Data Analytics & Intelligence Artificielle (ADIA)
> **Période :** 01 juillet 2026 – 31 août 2026

---


## 🎯 Contexte et objectifs

Les PME marocaines sont exposées à de nombreuses cybermenaces (vulnérabilités, ransomwares, phishing, DDoS, fuites de données…). Les informations utiles sont dispersées entre de nombreuses sources, aux formats, langues et niveaux de détail différents, ce qui rend leur exploitation directe difficile.

**Problématique :** comment concevoir une chaîne de traitement data-driven permettant de collecter, normaliser, classifier et enrichir automatiquement des données de cybermenaces, puis de les exploiter avec du RAG et des modèles de langage pour produire une information fiable et utile à la surveillance des menaces visant les PME au Maroc ?

**Objectifs :**

1. Collecter automatiquement des données depuis plusieurs sources ouvertes et spécialisées
2. Centraliser, nettoyer, normaliser et dédupliquer les données
3. Classifier automatiquement les cybermenaces (règles + Machine Learning)
4. Enrichir les données (secteur ciblé, sévérité, attributs techniques)
5. Mettre en place un système RAG avec un LLM local
6. Expérimenter le fine-tuning avec LoRA/QLoRA
7. Évaluer la classification et le système RAG (RAGAS + métriques personnalisées)
8. Fournir une base exploitable pour l'évolution de l'Observatoire

---

## ✨ Fonctionnalités

- **Collecte multi-sources** automatisée (API REST, flux RSS, web scraping, fichiers CSV/JSON) avec planification
- **Nettoyage, normalisation et déduplication** des données dans un schéma commun
- **Classification des cybermenaces** : moteur de règles expertes et modèle ML (TF-IDF + LinearSVC)
- **Enrichissement** : secteur ciblé, sévérité, identifiants techniques (CVE, CWE, IP, URL…), langue, provenance
- **Assistant cyber (RAG)** : réponses contextualisées avec sources, refus des demandes malveillantes, abstention
- **Dashboard** : indicateurs clés, top menaces, top secteurs, évolution des incidents
- **Liste des incidents** : recherche, filtres, pagination, export CSV
- **Rapports sectoriels** : génération par secteur, impression, export PDF/CSV
- **Évaluation** : métriques de classification, RAGAS et métriques personnalisées

---

## 🏗️ Architecture

```
Sources de données
        ↓
Collecte automatisée
        ↓
Nettoyage et normalisation
        ↓
Stockage centralisé (PostgreSQL)
        ↓
Classification et enrichissement
        ↓
Base documentaire / Base vectorielle (ChromaDB)
        ↓
RAG + Modèle de langage local
        ↓
Évaluation et génération de rapports
```

**Pipeline RAG :**

```
Documents nettoyés → Découpage en chunks → Embeddings (BAAI/bge-m3)
→ ChromaDB → Recherche des documents pertinents → Construction du contexte
→ LLM local → Réponse générée (avec sources)
```

---

## 🌐 Sources de données

**21 sources** sont intégrées au dispositif de collecte, en français et en anglais :

| Catégorie | Sources |
|---|---|
| Vulnérabilités et sécurité technique | NVD – NIST, CIRCL CVE Search, DGSSI-maCERT, ANSSI France, CISA USA, SANS ISC, ExploitDB |
| Threat Intelligence | AlienVault OTX, URLhaus, AbuseIPDB |
| Sources marocaines institutionnelles et sectorielles | DGSSI-maCERT, ANRT Maroc, HCP Maroc, Bank Al-Maghrib (BAM), MTNRA |
| Actualité et veille technologique | The Hacker News, BleepingComputer, Le360 Maroc, Medias24 Tech, TelQuel Tech, Challenge Tech, L'Economiste Tech |

**Mécanismes de collecte :** API REST (NVD, CIRCL, AlienVault OTX, URLhaus, AbuseIPDB), flux RSS, web scraping (sources institutionnelles et médiatiques marocaines), fichiers CSV/JSON (ExploitDB).

---

## 🧠 Classification des cybermenaces

Deux approches complémentaires ont été comparées :

1. **Classification par règles** : mots-clés, expressions caractéristiques, identifiants CWE, produits/vendors, scores pondérés par catégorie. Avantage : interprétable.
2. **Classification par Machine Learning** : vectorisation **TF-IDF** (unigrammes et bigrammes) + modèles supervisés (**LinearSVC**, Logistic Regression) avec pondération des classes pour limiter l'impact du déséquilibre.

**Comparaison des approches :**

| Méthode | Accuracy | Precision macro | Recall macro | Macro-F1 | Weighted-F1 |
|---|---|---|---|---|---|
| Classification par règles | 82,66 % | 51,52 % | 43,04 % | 40,52 % | 84,03 % |
| **LinearSVC** | **92,63 %** | **70,64 %** | **61,80 %** | **64,21 %** | **92,44 %** |

**LinearSVC (C = 1.0)** est retenu comme modèle principal. Le classifieur par règles reste pertinent comme mécanisme complémentaire (règles métier, cas nécessitant une décision explicable).

---

## 🧩 Enrichissement des données

Chaque événement est enrichi pour passer d'une donnée brute à un **événement cyber structuré** :

- **Secteur ciblé** : Finance et banque, Santé, Télécommunications, Administration publique, Industrie, Énergie, Commerce, Éducation, Technologies de l'information, Autres
- **Sévérité** : Faible, Moyenne, Élevée, Critique (distinction conservée entre sévérité fournie par la source et sévérité estimée)
- **Attributs techniques et contextuels** : source, date, identifiants (CVE, CWE, exploits, IP, URLs, domaines), URL d'origine, langue, description textuelle

---

## 🤖 Système RAG

- **Embeddings :** `BAAI/bge-m3`
- **Base vectorielle :** ChromaDB
- **LLM local** exécuté via Ollama
- **Métadonnées conservées** pour chaque chunk (source, date, titre, URL) afin d'assurer la traçabilité
- **Deux types de sources** pour les réponses : documents (Guide CMRPI, avec numéros de pages) et données PostgreSQL (statistiques en temps réel)
- **Comportements gérés :** refus éthique des demandes malveillantes, abstention lorsque le contexte est insuffisant
- **Fine-tuning :** expérimentation LoRA/QLoRA avec la bibliothèque PEFT

---

## 🖥️ Interface utilisateur

Interface web **React** avec navigation latérale, organisée en quatre pages :

| Page | Description |
|---|---|
| **Dashboard** | Indicateurs clés, top 5 menaces, top 5 secteurs, évolution des incidents |
| **Incidents** | Tableau des incidents, filtres (type, secteur, source, date), recherche par mots-clés, pagination, export CSV |
| **Assistant** | Chat avec le système RAG, sources affichées, historique des échanges |
| **Rapports** | Génération de rapports sectoriels, impression, export PDF/CSV |

---

## 📊 Résultats et évaluation

### Classification ML (3 391 incidents, 10 classes)

| Modèle | Accuracy | Precision macro | Recall macro | Macro-F1 | Weighted-F1 |
|---|---|---|---|---|---|
| LinearSVC_C1.0 | 0,9263 | 0,7064 | 0,6180 | 0,6421 | 0,9244 |
| LinearSVC_C5.0 | 0,9283 | 0,7085 | 0,6062 | 0,6372 | 0,9253 |
| LinearSVC_C2.0 | 0,9283 | 0,6872 | 0,6100 | 0,6326 | 0,9260 |
| LinearSVC_C0.5 | 0,9242 | 0,6928 | 0,6205 | 0,6396 | 0,9229 |
| LogisticRegression | 0,8882 | 0,5692 | 0,7509 | 0,6314 | 0,8953 |

Très bonnes performances sur les classes majoritaires (`VULNERABILITE` F1 = 0,98, `MALWARE` F1 = 0,91), plus faibles sur les classes minoritaires (`PHISHING`, `EXPLOITATION`) en raison du déséquilibre des classes.

### Évaluation RAGAS (70 questions, 5 catégories)

| Métrique | Moyenne |
|---|---|
| Faithfulness | 0,474 |
| Answer Relevancy | 0,386 |
| Context Precision | 0,510 |
| **Context Recall** | **0,809** |
| Answer Correctness | 0,395 |
| Answer Similarity | 0,602 |

**Score composite :** Retrieval 0,659 · Generation 0,439 · Accuracy 0,478 · **Global 0,539**

### Métriques personnalisées

| Métrique | Score |
|---|---|
| Statistical Accuracy | 1,000 |
| Refusal Accuracy | 1,000 |
| Abstention Accuracy | 0,875 |
| Hallucination Proxy Rate | 0,100 |
| Ambiguous Success | 0,583 |
| API Error Rate | 0,000 |

### Performance temporelle

Temps médian : **3,09 s** · moyen : 9,09 s · P95 : 29,16 s · maximum : 64,05 s

> **Lecture des résultats :** la récupération du contexte est le point fort du système (Context Recall 0,809) ; la qualité de la génération (fidélité, pertinence, correction) reste le principal axe d'amélioration.

---

## 🧰 Stack technique

| Domaine | Technologies |
|---|---|
| Langage | Python, JavaScript |
| Collecte et orchestration | Scripts Python, scheduler (`run_scheduler.py`), API REST, RSS, web scraping |
| Stockage | PostgreSQL, ChromaDB |
| Machine Learning / NLP | scikit-learn (TF-IDF, LinearSVC, Logistic Regression), spaCy |
| RAG / LLM | Embeddings BAAI/bge-m3, ChromaDB, LLM local via Ollama, LoRA/QLoRA (PEFT) |
| Évaluation | RAGAS, métriques personnalisées |
| Backend | Python (dossier `backend/`) |
| Frontend | React, Tailwind CSS |

---

## 📁 Structure du dépôt

```
observatoire-cyber-rag/
├── backend/            # API et logique serveur
├── frontend/           # Interface React
├── collectors/         # Scripts de collecte multi-sources
├── pipelines/          # Pipelines de traitement des données
├── database/           # Schéma et scripts de base de données
├── ml/                 # Classification Machine Learning
├── models/             # Modèles entraînés (threat_classifier)
├── results/            # Résultats d'évaluation (classification)
├── ragas_results/      # Résultats d'évaluation RAGAS
├── chroma_db/          # Base vectorielle ChromaDB
├── data/               # Données
├── data_sample/        # Échantillon de données
├── scripts/            # Scripts utilitaires
├── utils/              # Fonctions utilitaires
├── rag_core.py         # Cœur du système RAG
├── run_scheduler.py    # Planification de la collecte
├── run_scheduler.bat   # Lancement du scheduler (Windows)
├── config.py           # Configuration
├── requirements.txt    # Dépendances Python
└── package.json        # Dépendances front-end
```

---

## 🚀 Installation et lancement

### Prérequis

- Python 3.10+
- Node.js et npm
- PostgreSQL
- [Ollama](https://ollama.com) (LLM local)

### 1. Cloner le dépôt

```bash
git clone https://github.com/OumaimaKrt/observatoire-cyber-rag.git
cd observatoire-cyber-rag
```

### 2. Environnement Python

```bash
python -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configuration

Renseigner les paramètres de connexion à PostgreSQL, les clés d'API des sources concernées (par ex. AlienVault OTX, AbuseIPDB) et les modèles utilisés dans `config.py`.

### 4. Modèle de langage local

```bash
ollama pull <nom-du-modèle>
```

### 5. Collecte planifiée

```bash
python run_scheduler.py         # Windows : run_scheduler.bat
```

### 6. Interface web

```bash
npm install
npm run dev                     # adapter selon les scripts de package.json
```


## 👩‍💻 Auteure

- **Auteure :** Oumaima Kourchte — Master Data Analytics & Intelligence Artificielle (ADIA)
- **Encadrante :** Dr. Yasmina Al Marouni
- **Organisme d'accueil :** CMRPI – Espace Maroc Cyberconfiance (EMC)

---

*Projet réalisé du 01 juillet 2026 au 31 août 2026.*
