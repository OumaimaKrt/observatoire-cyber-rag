# 🛡️ Observatoire Cyber

**Observatoire data-driven des cybermenaces visant les PME au Maroc**

Plateforme qui collecte automatiquement des données de cybermenaces issues de 21 sources, les normalise, les classifie, les enrichit, puis les exploite via un système **RAG** et un **LLM local**.

> Projet réalisé au sein du **CMRPI – Espace Maroc Cyberconfiance (EMC)**
> **Auteure :** Oumaima Kourchte · **Encadrante :** Dr. Yasmina Al Marouni
> **Formation :** Master Data Analytics & Intelligence Artificielle (ADIA) · **Période :** juillet – août 2026

---

## ✨ Points clés

- **21 sources** collectées automatiquement (API REST, RSS, web scraping, CSV/JSON), en français et en anglais
- **Classification des menaces** : LinearSVC (TF-IDF) à **92,63 % d'Accuracy**, contre 82,66 % pour l'approche par règles
- **Enrichissement** : secteur ciblé, sévérité, identifiants techniques (CVE, CWE, IP, URL…)
- **Assistant cyber RAG** avec sources citées, refus des demandes malveillantes et abstention
- **Interface React** : dashboard, incidents, assistant, rapports sectoriels (export PDF/CSV)
- **Évaluation complète** : métriques de classification, RAGAS et métriques personnalisées

---

## 🏗️ Architecture

```
Sources de données → Collecte automatisée → Nettoyage et normalisation
→ Stockage (PostgreSQL) → Classification et enrichissement
→ Base vectorielle (ChromaDB) → RAG + LLM local → Évaluation et rapports
```

**Pipeline RAG :** documents nettoyés → chunks → embeddings (`BAAI/bge-m3`) → ChromaDB → recherche → contexte → LLM local (Ollama) → réponse avec sources.

---

## 📊 Résultats principaux

| Composant | Résultat |
|---|---|
| Classification ML (LinearSVC) | Accuracy **92,63 %** · Weighted-F1 **0,924** · Macro-F1 0,642 |
| Classification par règles | Accuracy 82,66 % · Macro-F1 0,405 |
| RAG : récupération | Context Recall **0,809** |
| RAG : score composite | 0,539 (Retrieval 0,659 · Generation 0,439) |
| Sécurité | Refusal Accuracy **1,000** |
| Statistiques (PostgreSQL) | Statistical Accuracy **1,000** |
| Stabilité | API Error Rate **0 %** |
| Temps de réponse | Médiane 3,09 s |

La récupération du contexte est le point fort du RAG ; la qualité de la génération (fidélité, pertinence) est le principal axe d'amélioration. Le Macro-F1 plus bas que le Weighted-F1 s'explique par le déséquilibre des classes (`PHISHING` et `EXPLOITATION` peu représentées).

📄 **Détails complets** (comparaison des modèles, rapport par classe, RAGAS par catégorie, métriques personnalisées) : [`docs/EVALUATION.md`](docs/EVALUATION.md)

---

## 🖥️ Interface

| Page | Description |
|---|---|
| **Dashboard** | Indicateurs clés, top menaces, top secteurs, évolution des incidents |
| **Incidents** | Recherche, filtres (type, secteur, source, date), pagination, export CSV |
| **Assistant** | Chat RAG avec sources (Guide CMRPI, données PostgreSQL) |
| **Rapports** | Rapports sectoriels, impression, export PDF/CSV |

---

## 🧰 Stack technique

| Domaine | Technologies |
|---|---|
| Langages | Python, JavaScript |
| Collecte | Scripts Python, scheduler, API REST, RSS, web scraping |
| Stockage | PostgreSQL, ChromaDB |
| ML / NLP | scikit-learn (TF-IDF, LinearSVC), spaCy |
| RAG / LLM | `BAAI/bge-m3`, ChromaDB, Ollama, LoRA/QLoRA (PEFT) |
| Évaluation | RAGAS, métriques personnalisées |
| Frontend | React, Tailwind CSS |

---

## 📁 Structure du dépôt

```
├── backend/          # API et logique serveur
├── frontend/         # Interface React
├── collectors/       # Collecte multi-sources
├── pipelines/        # Pipelines de traitement
├── database/         # Base de données
├── ml/               # Classification Machine Learning
├── models/           # Modèle entraîné (threat_classifier)
├── results/          # Résultats de classification
├── ragas_results/    # Résultats RAGAS
├── chroma_db/        # Base vectorielle
├── data/ · data_sample/
├── scripts/ · utils/
├── rag_core.py       # Cœur du système RAG
├── run_scheduler.py  # Planification de la collecte
├── config.py         # Configuration
└── requirements.txt
```

---

## 🚀 Installation

**Prérequis :** Python 3.10+, Node.js, PostgreSQL, [Ollama](https://ollama.com)

```bash
git clone https://github.com/OumaimaKrt/observatoire-cyber-rag.git
cd observatoire-cyber-rag

python -m venv venv
source venv/bin/activate          # Windows : venv\Scripts\activate
pip install -r requirements.txt
npm install
```

1. Renseigner dans `config.py` la connexion PostgreSQL, les clés d'API nécessaires et le modèle utilisé
2. Télécharger le modèle local : `ollama pull <nom-du-modèle>`
3. Lancer la collecte planifiée : `python run_scheduler.py` (Windows : `run_scheduler.bat`)
4. Lancer le backend et l'interface selon vos scripts (`npm run dev` pour le front)

---



## 👩‍💻 Auteure

**Oumaima Kourchte** — Master Data Analytics & IA
