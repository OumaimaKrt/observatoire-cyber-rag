# ============================================================================
# rag_core.py
# CORE RAG - OBSERVATOIRE CYBER CMRPI
# VERSION CORRIGÉE - LLAMA3.2:3b
# ============================================================================

import os
import re
import json

import chromadb
from chromadb.utils import embedding_functions
import requests


# ============================================================================
# CHARGEMENT DU .env (optionnel)
# ============================================================================

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ============================================================================
# CONFIGURATION - LLAMA3.2:3b
# ============================================================================

OLLAMA_URL = "http://localhost:11434/api/generate"

# 🔥 MODIFIÉ : llama3.2:3b
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")

OLLAMA_TIMEOUT = (10, 180)

# Paramètres optimisés pour llama3.2:3b
OLLAMA_TEMPERATURE = 0.1
OLLAMA_NUM_PREDICT = 500
OLLAMA_TOP_P = 0.9
OLLAMA_TOP_K = 40
OLLAMA_REPEAT_PENALTY = 1.1


# ============================================================================
# 🔥 CHEMIN CHROMADB FLEXIBLE
# ============================================================================

CHROMA_PATH = (
    os.environ.get("CHROMA_DB_PATH") or
    os.path.join(
        os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        ),
        "data",
        "chroma_db"
    )
)

if not os.path.exists(CHROMA_PATH):
    FALLBACK_PATH = r"C:\Users\dell\Desktop\observatoire_cyber\data\chroma_db"
    if os.path.exists(FALLBACK_PATH):
        CHROMA_PATH = FALLBACK_PATH
        print(f"⚠️ Utilisation du chemin fallback : {CHROMA_PATH}")
    else:
        print(f"⚠️ Chemin ChromaDB non trouvé : {CHROMA_PATH}")

EMBEDDING_MODEL = "BAAI/bge-m3"

DEFAULT_N_RESULTS = 10


# ============================================================================
# MESSAGES
# ============================================================================

NO_INFORMATION_MESSAGE = (
    "Je n'ai trouvé aucune information sur cette question "
    "dans les documents disponibles."
)

LLM_ERROR_MESSAGE = (
    "Une erreur est survenue lors de la génération de la réponse."
)


# ============================================================================
# NETTOYAGE DU TEXTE
# ============================================================================

def clean_rag_text(text: str) -> str:
    """Nettoyage léger du texte provenant de ChromaDB."""

    if not text:
        return ""

    text = str(text)

    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)

    replacements = {
        "\ufffd": " ",
        "\u00b4": "'",
        "\u2026": "...",
        "\xa0": " ",
        "\xad": "-",
        "\u2122": "TM",
        "\u00a9": "(c)",
        "\u00ae": "(R)",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ============================================================================
# INITIALISATION CHROMADB
# ============================================================================

def init_chroma_collections():
    """Initialise les collections ChromaDB."""

    try:

        if not os.path.exists(CHROMA_PATH):
            print(f"❌ Dossier ChromaDB introuvable : {CHROMA_PATH}")
            return None

        client = chromadb.PersistentClient(path=CHROMA_PATH)

        collections_list = [
            collection.name
            for collection in client.list_collections()
        ]

        print(f"📚 Collections ChromaDB disponibles : {collections_list}")

        embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )

        collections = {}

        if "cmrpi_guide" in collections_list:
            collections["guide"] = client.get_collection(
                name="cmrpi_guide",
                embedding_function=embedding_fn
            )
            print(f"✅ Guide CMRPI chargé : {collections['guide'].count()} documents")
        else:
            collections["guide"] = None
            print("⚠️ Collection 'cmrpi_guide' absente")

        if "cyber_incidents" in collections_list:
            collections["incidents"] = client.get_collection(
                name="cyber_incidents",
                embedding_function=embedding_fn
            )
            print(f"✅ Incidents chargés : {collections['incidents'].count()} documents")
        else:
            collections["incidents"] = None
            print("⚠️ Collection 'cyber_incidents' absente")

        if "sector_news" in collections_list:
            collections["news"] = client.get_collection(
                name="sector_news",
                embedding_function=embedding_fn
            )
            print(f"✅ Actualités chargées : {collections['news'].count()} documents")
        else:
            collections["news"] = None
            print("⚠️ Collection 'sector_news' absente")

        return collections

    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation ChromaDB : {e}")
        return None


# ============================================================================
# FILTRES CHROMADB
# ============================================================================

def construire_filtre(collection_name: str, filters: dict = None):
    """Construit les filtres ChromaDB avec support des conditions multiples."""

    where = {}

    if not filters:
        return where

    filtres_nettoyes = {}

    for key, value in filters.items():
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if not value:
                continue
            if value.upper() == "INCONNU":
                continue
        filtres_nettoyes[key] = value

    if not filtres_nettoyes:
        return where

    if len(filtres_nettoyes) == 1:
        return filtres_nettoyes

    conditions = [{key: value} for key, value in filtres_nettoyes.items()]
    return {"$and": conditions}


# ============================================================================
# REQUÊTE CHROMADB
# ============================================================================

def query_collection(collection, query: str, n_results: int = DEFAULT_N_RESULTS, filters: dict = None):
    """Recherche sémantique dans une collection ChromaDB."""

    empty_result = {"documents": [[]], "metadatas": [[]], "distances": [[]]}

    if collection is None:
        return empty_result

    if not query or not query.strip():
        return empty_result

    try:
        query = clean_rag_text(query)
        collection_name = getattr(collection, "name", "")
        where_clause = construire_filtre(collection_name, filters)

        print("\n" + "=" * 60)
        print("🔎 RECHERCHE CHROMADB")
        print("=" * 60)
        print(f"Collection : {collection_name}")
        print(f"Question   : {query}")
        print(f"Filtre     : {where_clause if where_clause else 'aucun'}")

        result = collection.query(
            query_texts=[query],
            n_results=max(1, int(n_results)),
            include=["documents", "metadatas", "distances"],
            where=where_clause if where_clause else None,
        )

        if not result:
            return empty_result

        documents = result.get("documents") or [[]]
        metadatas = result.get("metadatas") or [[]]
        distances = result.get("distances") or [[]]

        if not documents:
            documents = [[]]
        if not metadatas:
            metadatas = [[]]
        if not distances:
            distances = [[]]

        if documents and documents[0]:
            documents[0] = [
                clean_rag_text(document)
                for document in documents[0]
                if document
            ]

        nb_results = len(documents[0])
        print(f"📊 Résultats récupérés : {nb_results}")

        return {
            "documents": documents,
            "metadatas": metadatas,
            "distances": distances,
        }

    except Exception as e:
        print(f"❌ Erreur ChromaDB ({getattr(collection, 'name', 'unknown')}) : {e}")
        return empty_result


# ============================================================================
# RECHERCHE MULTI-COLLECTION
# ============================================================================

def search_collections(collections: dict, query: str, use_guide: bool = True, use_incidents: bool = True, use_news: bool = False, n_results: int = DEFAULT_N_RESULTS):
    """Recherche uniquement dans les collections demandées par le routeur."""

    results = {}

    if use_guide:
        results["guide"] = query_collection(
            collections.get("guide"),
            query,
            n_results=n_results
        )

    if use_incidents:
        results["incidents"] = query_collection(
            collections.get("incidents"),
            query,
            n_results=n_results
        )

    if use_news:
        results["news"] = query_collection(
            collections.get("news"),
            query,
            n_results=n_results
        )

    empty = {"documents": [[]], "metadatas": [[]], "distances": [[]]}

    results.setdefault("guide", empty.copy())
    results.setdefault("incidents", empty.copy())
    results.setdefault("news", empty.copy())

    return results


# ============================================================================
# APPEL OLLAMA - OPTIMISÉ
# ============================================================================

def _ollama_request(prompt: str, stream: bool = False):
    """Appel centralisé à Ollama avec paramètres optimisés."""

    if not prompt:
        return None

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": stream,
                "options": {
                    "temperature": OLLAMA_TEMPERATURE,
                    "top_p": OLLAMA_TOP_P,
                    "top_k": OLLAMA_TOP_K,
                    "repeat_penalty": OLLAMA_REPEAT_PENALTY,
                    "num_predict": OLLAMA_NUM_PREDICT,
                },
            },
            stream=stream,
            timeout=OLLAMA_TIMEOUT,
        )

        response.raise_for_status()
        return response

    except requests.exceptions.Timeout:
        print("❌ Timeout Ollama")
        return None

    except requests.exceptions.ConnectionError:
        print("❌ Impossible de contacter Ollama. Vérifiez que le serveur Ollama est lancé.")
        return None

    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur HTTP Ollama : {e}")
        return None


# ============================================================================
# RÉPONSE SIMPLE
# ============================================================================

def generate_llm_answer_simple(prompt: str, chunks: list = None) -> str:
    """Génère une réponse non-streaming."""

    if not prompt:
        return ""

    full_prompt = prompt.strip()

    if chunks:
        selected_chunks = [
            clean_rag_text(chunk)
            for chunk in chunks[:5]
            if chunk
        ]

        if selected_chunks:
            contexte = "\n\n".join(
                f"DOCUMENT {i}\n{chunk}"
                for i, chunk in enumerate(selected_chunks, start=1)
            )
            full_prompt = f"{full_prompt}\n\nCONTEXTE DOCUMENTAIRE :\n{contexte}"

    response = _ollama_request(full_prompt, stream=False)

    if response is None:
        return ""

    try:
        data = response.json()
        answer = data.get("response", "")
        return clean_rag_text(answer)

    except Exception as e:
        print(f"❌ Erreur lecture réponse Ollama : {e}")
        return ""


# ============================================================================
# RÉPONSE STREAMING
# ============================================================================

def generate_llm_answer_stream(query: str, chunks: list, lang: str = "fr"):
    """Génère une réponse en streaming."""

    if not chunks:
        yield NO_INFORMATION_MESSAGE
        return

    from scripts.prompt_system import get_system_prompt

    system_prompt = get_system_prompt("fr")

    selected_chunks = [
        clean_rag_text(chunk)
        for chunk in chunks[:5]
        if chunk
    ]

    if not selected_chunks:
        yield NO_INFORMATION_MESSAGE
        return

    contexte = "\n\n".join(
        f"DOCUMENT {i}\n{chunk}"
        for i, chunk in enumerate(selected_chunks, start=1)
    )

    prompt = f"""
{system_prompt}

QUESTION DE L'UTILISATEUR :
{query}

CONTEXTE DOCUMENTAIRE :
{contexte}

RÉPONDS DIRECTEMENT À LA QUESTION :
"""

    response = _ollama_request(prompt, stream=True)

    if response is None:
        yield LLM_ERROR_MESSAGE
        return

    try:
        for line in response.iter_lines():
            if not line:
                continue
            try:
                data = json.loads(line.decode("utf-8"))
                text = data.get("response", "")
                if text:
                    yield text
                if data.get("done", False):
                    break
            except json.JSONDecodeError:
                continue

    except Exception as e:
        print(f"❌ Erreur streaming Ollama : {e}")
        yield LLM_ERROR_MESSAGE