# ============================================================================
# rag_fusion.py
# FUSION DES RÉSULTATS RAG + RERANKING
# VERSION FINALE - OPTIMISATION COMPLÈTE
# ============================================================================

import os
import re
import sys
from typing import Any, Dict, List, Optional


# ============================================================================
# CONFIGURATION DU PROJET
# ============================================================================

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from scripts.response_builder import nettoyer_artefacts_avance


# ============================================================================
# CONFIGURATION - OPTIMISÉE
# ============================================================================

MIN_QUALITY_SCORE = 0.35  # 🔥 Augmenté de 0.30 à 0.35

DEFAULT_TOP_K = 3

_USE_RERANKER = True

RERANKER_MODEL = "BAAI/bge-reranker-base"

_RERANKER = None


# ============================================================================
# MESSAGES STANDARD
# ============================================================================

NO_ANSWER_MESSAGE = (
    "Je n'ai trouvé aucune information "
    "sur cette question dans les documents disponibles."
)

ABSTENTION_RESPONSES = [
    "Je ne dispose pas de prévisions",
    "Je ne peux pas prédire",
    "Je ne dispose pas d'informations sur les PME marocaines",
    "Je ne peux pas désigner de 'meilleur expert'",
    "Je ne peux pas lister les failles de sécurité spécifiques",
    "Le Guide ne recommande aucune marque spécifique",
    "Je ne dispose pas de données fiables sur les salaires",
    "Je ne peux pas fournir d'adresse IP",
    "Je ne peux pas vous aider avec cette demande",
]

def _est_reponse_abstention(texte: str) -> bool:
    """Détecte si la réponse est une abstention (doit être conservée)."""
    if not texte:
        return False
    for pattern in ABSTENTION_RESPONSES:
        if pattern in texte:
            return True
    return False

_PATTERNS_REPONSE_IMPOSSIBLE = [
    r"impossible d[e']\s*(offrir|donner|fournir)\s+une réponse",
    r"ne (permettent|permet) pas de répondre",
    r"ne contiennent pas (suffisamment d[e']informations|d[e']information)",
    r"ne contient pas (suffisamment d[e']informations|d[e']information)",
    r"n[e']ai (pas trouvé|trouvé aucune) (de |d')?(information|réponse)",
    r"aucune information (fiable |pertinente )?(sur|concernant) cette question",
    r"il n[e']est pas possible de répondre",
    r"ne correspond à aucun (contenu|document) fourni",
]


def _reponse_indique_absence_info(texte: str) -> bool:
    """Détecte si le texte exprime une incapacité à répondre."""
    if not texte:
        return False
    texte_lower = texte.lower()
    return any(re.search(pattern, texte_lower) for pattern in _PATTERNS_REPONSE_IMPOSSIBLE)


# ============================================================================
# RERANKER
# ============================================================================

def get_reranker():
    """Charge le reranker une seule fois."""

    global _RERANKER

    if _RERANKER is not None:
        return _RERANKER

    if not _USE_RERANKER:
        return None

    try:
        from sentence_transformers import CrossEncoder

        print(f"📦 Chargement du reranker ({RERANKER_MODEL})...")
        _RERANKER = CrossEncoder(RERANKER_MODEL)
        print("✅ Reranker chargé")
        return _RERANKER

    except Exception as e:
        print(f"⚠️ Impossible de charger le reranker : {e}")
        _RERANKER = None
        return None


# ============================================================================
# OUTILS GÉNÉRAUX
# ============================================================================

def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


# ============================================================================
# RERANKING
# ============================================================================

def reranker_documents(query: str, documents: list, top_k: int = DEFAULT_TOP_K) -> list:
    """Réordonne les documents selon leur pertinence réelle."""

    if not documents:
        return []

    if not query:
        return documents[:top_k]

    if not _USE_RERANKER:
        return documents[:top_k]

    reranker = get_reranker()

    if reranker is None:
        return documents[:top_k]

    try:
        valid_documents = [
            doc for doc in documents
            if isinstance(doc, dict)
            and str(doc.get("texte", "")).strip()
        ]

        if not valid_documents:
            return []

        pairs = [[query, doc["texte"]] for doc in valid_documents]
        scores = reranker.predict(pairs, show_progress_bar=False)

        for doc, score in zip(valid_documents, scores):
            doc["rerank_score"] = _safe_float(score, default=0.0)

        sorted_documents = sorted(
            valid_documents,
            key=lambda x: x.get("rerank_score", 0.0),
            reverse=True
        )

        return sorted_documents[:max(1, top_k)]

    except Exception as e:
        print(f"⚠️ Erreur pendant le reranking : {e}")
        return documents[:top_k]


# ============================================================================
# NORMALISATION DES MOTS
# ============================================================================

def normaliser_mots(texte: str) -> set:
    """Transforme un texte en ensemble de mots simples."""

    if not texte:
        return set()

    texte = str(texte).lower()
    texte = re.sub(r"[^\w\sÀ-ÿ-]", " ", texte)
    mots = texte.split()

    return {mot for mot in mots if len(mot) >= 3}


# ============================================================================
# SCORE DE SIMILARITÉ CHROMADB
# ============================================================================

def compute_similarity_score(distance: Any) -> float:
    """Transforme une distance ChromaDB en score compris entre 0 et 1."""

    if distance is None:
        return 0.0

    try:
        distance = float(distance)
        if distance < 0:
            distance = 0.0
        score = 1.0 - distance
        return max(0.0, min(1.0, score))
    except (TypeError, ValueError):
        return 0.0


# ============================================================================
# PERTINENCE THÉMATIQUE
# ============================================================================

def _mots_sujet(query: str) -> set:
    stop = {
        "que", "quels", "quelles", "quel", "quelle", "comment", "pourquoi",
        "peut", "peut-elle", "peut-il", "doit", "doivent", "faire", "faire",
        "recommande", "recommandations", "recommandation", "conseils", "conseil",
        "mesures", "mesure", "principales", "principal", "guide", "cmrpi",
        "dans", "pour", "contre", "avec", "une", "des", "les", "du", "de",
        "la", "le", "un", "et", "aux", "au", "sur", "sont", "est", "plus",
        "fréquent", "fréquente", "fréquents", "fréquentes", "observées", "observés",
        "observé", "observes", "menaces", "menace", "incidents", "incident",
        "ransomwares", "ransomware", "phishing", "piratage", "ddos",
        "vulnérabilité", "vulnérabilités", "virus", "malware", "malwares",
    }
    words = normaliser_mots(query)
    return {w for w in words if w not in stop and len(w) >= 4}


def _filtrer_pertinence_thematique(items: list, query: str, source_type: str) -> list:
    """Évite qu'un chunk hors sujet soit envoyé au LLM."""

    if not items or source_type != "guide":
        return items

    q = str(query or "").lower()
    sujet = _mots_sujet(q)

    if not sujet:
        return items

    scored = []
    for item in items:
        words = normaliser_mots(item.get("texte", ""))
        overlap = len(sujet & words)
        if overlap > 0:
            item["topic_overlap"] = overlap
            scored.append(item)

    if scored:
        sans_overlap = [it for it in items if it not in scored]
        scored.sort(key=lambda x: x.get("topic_overlap", 0), reverse=True)
        return scored + sans_overlap

    return items


# ============================================================================
# SCORE DE QUALITÉ D'UN CHUNK - ÉLARGI
# ============================================================================

def compute_chunk_quality(chunk: dict, query: str) -> dict:
    """Calcule un score complémentaire de qualité."""

    if not isinstance(chunk, dict):
        return {
            "similarity_score": 0.0,
            "length_score": 0.0,
            "keyword_score": 0.0,
            "source_score": 0.0,
            "quality_score": 0.0,
            "rejected": True
        }

    texte_chunk = str(chunk.get("texte", "") or "")
    texte_lower = texte_chunk.lower()

    _MOTIFS_CONTAMINATION = (
        "## your task",
        "your task:",
        "craft a comprehensive response",
        "you are an ai",
        "you are a helpful assistant",
        "system prompt",
        "ignore previous instructions",
        "ignore all previous instructions",
        "as an ai",
        "as a language model",
        "i am an ai",
        "i am a large language model",
        "i don't have personal",
        "i don't have access to",
        "as an ai language model",
        "as an ai assistant",
    )

    est_contamine = any(motif in texte_lower for motif in _MOTIFS_CONTAMINATION)

    if not est_contamine:
        est_contamine = bool(
            re.search(
                r'#{2,4}\s*question\s*:.{0,200}#{2,4}\s*r[ée]ponse\s*:',
                texte_chunk,
                flags=re.IGNORECASE | re.DOTALL
            )
        )

    if est_contamine:
        print(f"⚠️ Chunk exclu (contamination) : {texte_chunk[:80]!r}...")
        return {
            "similarity_score": 0.0,
            "length_score": 0.0,
            "keyword_score": 0.0,
            "source_score": 0.0,
            "quality_score": 0.0,
            "rejected": True
        }

    texte = str(chunk.get("texte", "")).strip()

    if not texte:
        return {
            "similarity_score": 0.0,
            "length_score": 0.0,
            "keyword_score": 0.0,
            "source_score": 0.0,
            "quality_score": 0.0,
            "rejected": True
        }

    distance = chunk.get("distance", None)
    similarity_score = compute_similarity_score(distance)

    length = len(texte)

    if 80 <= length <= 700:
        length_score = 1.0
    elif 40 <= length < 80:
        length_score = 0.7
    elif 700 < length <= 1200:
        length_score = 0.7
    elif 20 <= length < 40:
        length_score = 0.4
    elif 1200 < length <= 1800:
        length_score = 0.4
    else:
        length_score = 0.2

    query_words = normaliser_mots(query)
    chunk_words = normaliser_mots(texte)

    if query_words:
        overlap = len(query_words.intersection(chunk_words)) / len(query_words)
    else:
        overlap = 0.0

    keyword_score = min(1.0, overlap * 1.5)

    source_type = str(chunk.get("source_type", "")).lower().strip()

    if source_type == "guide":
        source_score = 1.0
    elif source_type == "incidents":
        source_score = 0.9
    elif source_type == "news":
        source_score = 0.8
    else:
        source_score = 0.6

    quality_score = (
        similarity_score * 0.35
        + length_score * 0.15
        + keyword_score * 0.30
        + source_score * 0.20
    )

    quality_score = round(quality_score, 3)

    return {
        "similarity_score": round(similarity_score, 3),
        "length_score": round(length_score, 3),
        "keyword_score": round(keyword_score, 3),
        "source_score": round(source_score, 3),
        "quality_score": quality_score,
        "rejected": (
            quality_score < MIN_QUALITY_SCORE
            or (similarity_score < 0.12 and keyword_score < 0.10)
        )
    }


# ============================================================================
# EXTRACTION DES RÉSULTATS CHROMADB
# ============================================================================

def extraire_metadonnees(results, source_type: str, query: str = "") -> list:
    """Transforme les résultats ChromaDB en objets homogènes."""

    items = []

    if not results:
        return items

    if not isinstance(results, dict):
        return items

    documents = results.get("documents", [])

    if not documents:
        return items

    if isinstance(documents, list) and documents and isinstance(documents[0], list):
        documents = documents[0]
    elif not isinstance(documents, list):
        documents = [documents]

    if not documents:
        return items

    metadatas = results.get("metadatas", [])

    if isinstance(metadatas, list) and metadatas and isinstance(metadatas[0], list):
        metadatas = metadatas[0]
    elif not isinstance(metadatas, list):
        metadatas = []

    distances = results.get("distances", [])

    if isinstance(distances, list) and distances and isinstance(distances[0], list):
        distances = distances[0]
    elif not isinstance(distances, list):
        distances = []

    ids = results.get("ids", [])

    if isinstance(ids, list) and ids and isinstance(ids[0], list):
        ids = ids[0]
    elif not isinstance(ids, list):
        ids = []

    print(f"📄 {len(documents)} documents trouvés pour {source_type}")

    for i, document in enumerate(documents):
        if document is None:
            continue

        document = str(document).strip()

        if not document:
            continue

        meta = {}

        if i < len(metadatas):
            current_meta = metadatas[i]
            if isinstance(current_meta, dict):
                meta = current_meta.copy()

        distance = None
        if i < len(distances):
            distance = distances[i]

        document_id = None
        if i < len(ids):
            document_id = ids[i]

        document = nettoyer_artefacts_avance(document)

        if not document:
            continue

        item = {
            "texte": document,
            "meta": meta,
            "distance": distance,
            "document_id": document_id,
            "source_type": source_type,
            "quality": None,
            "rerank_score": None,
            "categorie": None
        }

        items.append(item)

    print(f"✅ {len(items)} items conservés pour {source_type}")

    return items


# ============================================================================
# DÉDOUBLONNAGE
# ============================================================================

def dedoublonner_documents(documents: list) -> list:
    """Supprime les documents identiques ou quasiment identiques."""

    if not documents:
        return []

    vus = set()
    resultat = []

    for doc in documents:
        if not isinstance(doc, dict):
            continue

        texte = str(doc.get("texte", "")).strip()

        if not texte:
            continue

        cle = texte.lower()
        cle = re.sub(r"\s+", " ", cle)
        cle = re.sub(r"[^\w\sÀ-ÿ-]", "", cle)
        cle = cle.strip()

        if not cle:
            continue

        if cle in vus:
            continue

        vus.add(cle)
        resultat.append(doc)

    return resultat


# ============================================================================
# DIVERSIFICATION DES DOCUMENTS - 🔥 OPTIMISÉ
# ============================================================================

def diversifier_documents(documents: list, top_k: int = DEFAULT_TOP_K) -> list:
    """Évite qu'une seule collection monopolise tous les documents."""

    if not documents:
        return []

    top_k = max(1, top_k)

    if len(documents) <= top_k:
        return documents

    resultat = []
    categories_vues = set()

    for document in documents:
        categorie = document.get("categorie", "")

        if categorie in categories_vues:
            continue

        resultat.append(document)
        categories_vues.add(categorie)

        if len(resultat) >= top_k:
            return resultat

    for document in documents:
        if document in resultat:
            continue

        resultat.append(document)

        if len(resultat) >= top_k:
            break

    return resultat


# ============================================================================
# CONSTRUCTION DES SOURCES
# ============================================================================

def construire_sources(documents: list) -> list:
    """Construit les sources uniquement à partir des documents réellement utilisés."""

    if not documents:
        return []

    guide_pages = set()
    autres_sources = []

    for item in documents:
        if not isinstance(item, dict):
            continue

        meta = item.get("meta", {}) or {}

        if not isinstance(meta, dict):
            meta = {}

        source_name = str(meta.get("source_name", "")).strip()
        source = str(meta.get("source", "")).strip()
        page = str(meta.get("page", "")).strip()
        title = str(meta.get("title", "")).strip()
        url = str(meta.get("url", "")).strip()

        is_guide = (
            source_name.lower() == "guide cmrpi"
            or source.upper() == "CMRPI"
            or item.get("source_type") == "guide"
        )

        if is_guide:
            if page.isdigit():
                guide_pages.add(int(page))
            else:
                guide_pages.add(None)
            continue

        if item.get("source_type") == "incidents":
            type_menace = str(meta.get("type_menace", "")).strip()

            if type_menace and type_menace.upper() not in {"INCONNU", "INCONNUE", "UNKNOWN"}:
                valeur = f"Incident : {type_menace}"
            elif source:
                valeur = source
            elif source_name:
                valeur = source_name
            else:
                valeur = "Données incidents"

            if valeur not in autres_sources:
                autres_sources.append(valeur)
            continue

        if item.get("source_type") == "news":
            if source_name:
                valeur = source_name
            elif source:
                valeur = source
            elif title:
                valeur = title
            else:
                valeur = "Actualités cyber"

            if url:
                valeur = f"{valeur} — {url}"

            if valeur not in autres_sources:
                autres_sources.append(valeur)
            continue

        valeur = source_name or source or title

        if valeur and valeur not in autres_sources:
            autres_sources.append(valeur)

    sources = []

    pages_numeriques = sorted(p for p in guide_pages if p is not None)

    if pages_numeriques:
        pages = ", ".join(str(p) for p in pages_numeriques)
        sources.append(f"Guide CMRPI (pages {pages})")
    elif None in guide_pages:
        sources.append("Guide CMRPI")

    sources.extend(autres_sources)

    sources_uniques = []

    for source in sources:
        if source and source not in sources_uniques:
            sources_uniques.append(source)

    return sources_uniques[:5]


# ============================================================================
# PRÉPARATION DU CONTEXTE LLM
# ============================================================================

def construire_contexte_llm(documents: list, top_k: int = DEFAULT_TOP_K) -> str:
    """Construit le contexte envoyé au LLM."""

    if not documents:
        return ""

    contexte_parts = []

    for index, item in enumerate(documents[:top_k], start=1):
        texte = str(item.get("texte", "")).strip()

        if not texte:
            continue

        contexte_parts.append(f"CONTENU {index} :\n{texte}")

    return "\n\n".join(contexte_parts)


# ============================================================================
# DÉTECTION DU MODE DE RECHERCHE
# ============================================================================

def _detecter_mode_recherche(query: str) -> str:
    """Détermine la famille documentaire prioritaire pour la question."""

    q = str(query or '').lower().strip()

    news = ('actualité', 'actualités', 'récent', 'récente', 'dernière', 'dernières',
            'récemment', "aujourd'hui", 'cette semaine', 'ce mois', 'presse', 'alerte')

    stats = ('combien', 'nombre', 'total', 'proportion', 'pourcentage', 'part',
             'fréquent', 'fréquente', 'fréquents', 'plus fréquent', 'principal',
             'principaux', 'statistique', 'statistiques', 'tendance', 'évolution',
             'augmentation', 'diminution', 'compare', 'comparer', 'classement')

    guide = ('protéger', 'protection', 'sécuriser', 'sécurité', 'prévenir', 'prévention',
             'recommandation', 'recommandations', 'conseil', 'conseils', 'bonne pratique',
             'bonnes pratiques', 'mesure', 'mesures', 'antivirus', 'mot de passe',
             'mots de passe', 'sauvegarde', 'wifi', 'wi-fi', 'pare-feu', 'firewall',
             'mise à jour', 'mises à jour', 'guide cmrpi',
             'email suspect', 'pirate', 'verrouiller écran', 'télécharger')

    has_news = any(x in q for x in news)
    has_stats = any(x in q for x in stats)
    has_guide = any(x in q for x in guide)

    if has_news and (has_stats or has_guide):
        return 'mixte'
    if has_news:
        return 'news'
    if has_stats and has_guide:
        return 'mixte'
    if has_stats:
        return 'stats'
    if has_guide:
        return 'guide'
    return 'general'


def _filtrer_par_mode(items: list, mode: str) -> list:
    if mode == 'guide':
        return [x for x in items if x.get('source_type') == 'guide']
    if mode == 'stats':
        return [x for x in items if x.get('source_type') == 'incidents']
    if mode == 'news':
        return [x for x in items if x.get('source_type') == 'news']
    if mode == 'mixte':
        return items
    return items


# ============================================================================
# FUSION PRINCIPALE - 🔥 OPTIMISÉ
# ============================================================================

def fusionner_reponses(
    resultats: dict,
    query: str,
    lang: str = "fr",
    ollama_call=None,
    stats_result=None,
    conversation_context: str = "",
    intent: str | None = None
) -> dict:
    """
    Fusionne les résultats provenant des collections.
    """

    print("\n" + "=" * 70)
    print("🔍 FUSION DES RÉSULTATS")
    print("=" * 70)

    query = str(query or "").strip()

    if not isinstance(resultats, dict):
        resultats = {}

    reponse = {
        "query": query,
        "recommandations": [],
        "statistiques": [],
        "actualites": [],
        "sources": [],
        "sources_affichees": [],
        "synthese_llm": None,
        "no_answer": False,
        "mode_recherche": None,
        "is_abstention": False
    }

    # ================================================================
    # 🔥 MODIFIÉ : Utiliser stats_for_llm pour le LLM
    # ================================================================
    if stats_result and stats_result.get("success") and stats_result.get("data"):
        try:
            from scripts.agent_orchestrator import format_sql_results
            
            # Format pour l'affichage utilisateur
            reponse["stats_postgres"] = format_sql_results(stats_result, lang)
            reponse["statistiques_postgres"] = stats_result.get("data", [])
            reponse["statistiques_label"] = stats_result.get("label", "")
            
            # 🔥 Format pour le LLM (plus explicite)
            if stats_result.get("stats_for_llm"):
                reponse["stats_llm"] = stats_result["stats_for_llm"]
            else:
                # Fallback : formater manuellement
                reponse["stats_llm"] = format_sql_results(stats_result, lang)
            
            print(f"📊 Statistiques PostgreSQL ajoutées à la réponse")
            print(f"📊 Format LLM: {reponse['stats_llm'][:100]}...")
        except Exception as e:
            print(f"⚠️ Erreur formatage stats PostgreSQL: {e}")

    # Extraction
    guide_items = extraire_metadonnees(resultats.get("guide", {}), "guide", query)
    incidents_items = extraire_metadonnees(resultats.get("incidents", {}), "incidents", query)
    news_items = extraire_metadonnees(resultats.get("news", {}), "news", query)

    print(f"📊 Guide     : {len(guide_items)}")
    print(f"📊 Incidents : {len(incidents_items)}")
    print(f"📊 News      : {len(news_items)}")

    # Catégorisation
    for item in guide_items:
        item["categorie"] = "recommandations"

    for item in incidents_items:
        item["categorie"] = "statistiques"

    for item in news_items:
        item["categorie"] = "actualites"

    # Filtrage selon l'intention
    mode_recherche = intent or _detecter_mode_recherche(query)

    if mode_recherche == "incidents":
        mode_recherche = "stats"
    elif mode_recherche == "actualites":
        mode_recherche = "news"

    reponse["mode_recherche"] = mode_recherche
    print(f"🎯 Mode documentaire : {mode_recherche}")

    guide_items = _filtrer_par_mode(guide_items, mode_recherche)
    incidents_items = _filtrer_par_mode(incidents_items, mode_recherche)
    news_items = _filtrer_par_mode(news_items, mode_recherche)

    guide_items = _filtrer_pertinence_thematique(guide_items, query, "guide")

    # Fusion
    tous_les_items = guide_items + incidents_items + news_items

    if not tous_les_items:
        reponse["no_answer"] = True
        reponse["message"] = NO_ANSWER_MESSAGE
        return reponse

    # Dédoublonnage
    tous_les_items = dedoublonner_documents(tous_les_items)
    print(f"📊 Documents après dédoublonnage : {len(tous_les_items)}")

    # Quality score
    documents_valides = []

    for item in tous_les_items:
        quality = compute_chunk_quality(item, query)
        item["quality"] = quality

        if not quality["rejected"]:
            documents_valides.append(item)

    print(f"📊 Documents après contrôle qualité : {len(documents_valides)}")

    # Filtrage strict par intention
    if intent == "guide":
        documents_valides = [d for d in documents_valides if d.get("source_type") == "guide"]

    if intent == "incidents":
        documents_valides = [d for d in documents_valides if d.get("source_type") == "incidents"]

    if not documents_valides:
        print("⚠️ Aucun document ne dépasse le seuil de qualité.")
        return {
            **reponse,
            "no_answer": True,
            "message": NO_ANSWER_MESSAGE
        }

    # Reranking
    if documents_valides:
        print(f"🔄 Reranking de {len(documents_valides)} documents...")
        documents_valides = reranker_documents(
            query,
            documents_valides,
            top_k=len(documents_valides)
        )
        print("✅ Reranking terminé")

    # Tri final
    documents_valides = sorted(
        documents_valides,
        key=lambda x: (
            x.get("rerank_score", 0.0),
            x.get("quality", {}).get("quality_score", 0.0)
        ),
        reverse=True
    )

    # ================================================================
    # 🔥 DIVERSIFICATION OPTIMISÉE - 2 POUR GUIDE ET STATS
    # ================================================================
    if mode_recherche == "guide":
        # 🔥 Pour les questions Guide, réduire à 2 documents
        documents_finaux = documents_valides[:2]
    elif mode_recherche == "stats":
        # 🔥 Pour les questions Statistiques, réduire à 2 documents aussi
        documents_finaux = documents_valides[:2]
    elif mode_recherche == "mixte":
        guides = [d for d in documents_valides if d.get("source_type") == "guide"][:2]
        incidents = [d for d in documents_valides if d.get("source_type") == "incidents"][:2]
        news = [d for d in documents_valides if d.get("source_type") == "news"][:1]
        documents_finaux = guides + incidents + news
        documents_finaux = documents_finaux[:4]
    else:
        documents_finaux = documents_valides[:3]

    print(f"📊 Documents finaux : {len(documents_finaux)}")

    if not documents_finaux:
        reponse["no_answer"] = True
        reponse["message"] = NO_ANSWER_MESSAGE
        return reponse

    # Catégories finales
    for item in documents_finaux:
        categorie = item.get("categorie")

        if categorie == "statistiques":
            reponse["statistiques"].append(item)
        elif categorie == "actualites":
            reponse["actualites"].append(item)
        else:
            reponse["recommandations"].append(item)

    # Sources
    sources = construire_sources(documents_finaux)
    reponse["sources"] = sources
    reponse["sources_affichees"] = sources

    print(f"📚 Sources utilisées : {sources}")

    # Abstention
    from scripts.intent_router import is_abstention_required
    is_abstention, abstention_message = is_abstention_required(query)
    
    if is_abstention:
        reponse["is_abstention"] = True
        reponse["synthese_llm"] = abstention_message
        reponse["no_answer"] = False
        print(f"✅ Abstention détectée : {abstention_message[:50]}...")
        return reponse

    # Synthèse LLM
    if ollama_call:
        try:
            from scripts.prompt_system import get_system_prompt

            system_prompt = get_system_prompt("fr")

            contexte = construire_contexte_llm(documents_finaux, top_k=len(documents_finaux))

            # 🔥 MODIFIÉ : Utiliser stats_llm pour le LLM
            if reponse.get("stats_llm"):
                contexte = (
                    "📊 STATISTIQUES STRUCTURÉES (À UTILISER EXACTEMENT) :\n"
                    + reponse["stats_llm"]
                    + "\n\n"
                    + contexte
                )

            if not contexte and not conversation_context:
                reponse["no_answer"] = True
                reponse["message"] = NO_ANSWER_MESSAGE
                return reponse

            if not contexte:
                contexte = (
                    "(Aucun nouveau document pertinent trouvé pour cette "
                    "question — réponds uniquement à partir de "
                    "l'historique de conversation ci-dessus si cela "
                    "permet de répondre ; sinon indique que les documents "
                    "disponibles ne permettent pas de répondre.)"
                )

            bloc_historique = ""

            if conversation_context:
                bloc_historique = f"""
HISTORIQUE RÉCENT DE LA CONVERSATION (pour référence uniquement) :
{conversation_context}

"""

            prompt_llm = f"""
{system_prompt}
{bloc_historique}
QUESTION DE L'UTILISATEUR :
{query}

CONTEXTE DOCUMENTAIRE :
{contexte}

INSTRUCTIONS POUR CETTE RÉPONSE :

- Réponds directement à la question.
- Ne recopie jamais le libellé "QUESTION DE L'UTILISATEUR" ni la
  question elle-même en début de réponse — commence directement par
  le contenu de ta réponse, sans aucun préfixe du type "Question :"
  ou "Réponse :".
- Si la question comporte plusieurs volets, réponds à CHAQUE volet
  séparément.
- Si un historique de conversation est fourni, utilise-le uniquement
  pour comprendre à quoi la question actuelle fait référence.
- Ne recopie jamais l'historique dans ta réponse.
- Réponds uniquement en français.
- Utilise uniquement les informations présentes dans le contexte documentaire.
- Ne complète pas les informations avec tes connaissances générales.
- Ne crée aucun chiffre, nom d'entreprise, ou date.
- Si les documents ne permettent pas de répondre précisément,
  indique clairement que les documents disponibles
  ne contiennent pas suffisamment d'informations.
- N'utilise que les passages qui répondent directement à la question.
- Si une donnée statistique structurée est fournie, utilise-la telle quelle.
- Ne mentionne pas le processus RAG, ChromaDB, les embeddings, le reranker.
- Ne crée pas de section "Sources".
- N'invente aucune information absente du contexte.

🔴 RÈGLE STATISTIQUES IMPÉRATIVE :
QUAND tu vois une section "📊 STATISTIQUES STRUCTURÉES" dans le contexte,
tu DOIS l'utiliser EXACTEMENT.
Exemple : si tu vois "CRITIQUES : 985", réponds "985" et non "3".

🔴 RÈGLE DE PERTINENCE :
Si la question demande une FRÉQUENCE, donne la fréquence exacte.
Si la question demande un NOMBRE, donne le nombre exact.
Si la question demande des CONSEILS, liste les conseils spécifiques.
Ne donne pas d'informations générales si la question est spécifique.
""".strip()

            print("🤖 Génération de la réponse...")

            textes_contextuels = [
                item["texte"]
                for item in documents_finaux
                if item.get("texte")
            ]

            texte_llm = ollama_call(prompt_llm, textes_contextuels)

            if texte_llm:
                texte_llm = nettoyer_artefacts_avance(texte_llm)

                if _est_reponse_abstention(texte_llm):
                    reponse["is_abstention"] = True
                    reponse["synthese_llm"] = texte_llm.strip()
                    print("✅ Réponse d'abstention générée")
                    return reponse

                if _reponse_indique_absence_info(texte_llm):
                    reponse["no_answer"] = True
                    reponse["message"] = NO_ANSWER_MESSAGE
                    print("⚠️ Le LLM indique ne pas pouvoir répondre — message standard utilisé")
                    return reponse

                if len(texte_llm.strip()) >= 10:
                    reponse["synthese_llm"] = texte_llm.strip()
                    print("✅ Réponse LLM générée")
                else:
                    print("⚠️ Réponse LLM trop courte")
            else:
                print("⚠️ Le LLM n'a retourné aucune réponse")

        except Exception as e:
            print(f"⚠️ Erreur synthèse LLM : {e}")

    return reponse