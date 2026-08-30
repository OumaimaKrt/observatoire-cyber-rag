import chromadb
from chromadb.utils import embedding_functions
from collections import Counter
import statistics


# ============================================================
# CONFIGURATION
# ============================================================

CHROMA_PATH = r"C:\Users\dell\Desktop\observatoire_cyber\data\chroma_db"
COLLECTION_NAME = "cmrpi_guide"
EMBEDDING_MODEL = "BAAI/bge-m3"

TOP_K = 5


# ============================================================
# CONNEXION CHROMADB
# ============================================================

print("=" * 80)
print("VERIFICATION QUALITE CHUNKS + RECUPERATION RAG")
print("=" * 80)

print("\n[1] Connexion à ChromaDB...")

try:
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    print("    OK - ChromaDB connecté")
except Exception as e:
    print(f"    ERREUR : {e}")
    raise SystemExit(1)


# ============================================================
# COLLECTIONS
# ============================================================

print("\n[2] Collections disponibles :")

collections = client.list_collections()

if not collections:
    print("    Aucune collection trouvée.")
    raise SystemExit(1)

for c in collections:
    print(f"    - {c.name}")

if COLLECTION_NAME not in [c.name for c in collections]:
    print(f"\nERREUR : collection '{COLLECTION_NAME}' introuvable.")
    raise SystemExit(1)


# ============================================================
# EMBEDDING FUNCTION
# ============================================================

print("\n[3] Chargement du modèle d'embeddings...")
print(f"    Modèle : {EMBEDDING_MODEL}")

try:
    embedding_fn = (
        embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
    )

    print("    OK - modèle chargé")

except Exception as e:
    print(f"    ERREUR : {e}")
    raise SystemExit(1)


# ============================================================
# CHARGEMENT COLLECTION
# ============================================================

try:
    collection = client.get_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn
    )

except Exception as e:
    print("\nERREUR : impossible de charger la collection")
    print(e)
    raise SystemExit(1)


count = collection.count()

print("\n[4] Informations collection")
print(f"    Collection : {COLLECTION_NAME}")
print(f"    Documents/chunks : {count}")


if count == 0:
    print("\nERREUR : collection vide.")
    raise SystemExit(1)


# ============================================================
# RECUPERATION DE TOUS LES CHUNKS
# ============================================================

print("\n[5] Analyse des chunks...")

all_data = collection.get(
    limit=count,
    include=["documents", "metadatas"]
)

documents = all_data.get("documents", [])
metadatas = all_data.get("metadatas", [])
ids = all_data.get("ids", [])


print(f"    Chunks récupérés : {len(documents)}")


# ============================================================
# STATISTIQUES CHUNKS
# ============================================================

lengths = [
    len(doc.strip())
    for doc in documents
    if doc and doc.strip()
]

empty_chunks = sum(
    1 for doc in documents
    if not doc or not doc.strip()
)

very_short = sum(
    1 for doc in documents
    if doc and len(doc.strip()) < 100
)

short_chunks = sum(
    1 for doc in documents
    if doc and len(doc.strip()) < 200
)

long_chunks = sum(
    1 for doc in documents
    if doc and len(doc.strip()) > 2000
)


print("\n" + "-" * 80)
print("STATISTIQUES DES CHUNKS")
print("-" * 80)

if lengths:
    print(f"    Taille minimale   : {min(lengths)} caractères")
    print(f"    Taille maximale   : {max(lengths)} caractères")
    print(
        f"    Taille moyenne    : "
        f"{statistics.mean(lengths):.0f} caractères"
    )
    print(
        f"    Médiane           : "
        f"{statistics.median(lengths):.0f} caractères"
    )

print(f"    Chunks vides      : {empty_chunks}")
print(f"    < 100 caractères  : {very_short}")
print(f"    < 200 caractères  : {short_chunks}")
print(f"    > 2000 caractères : {long_chunks}")


# ============================================================
# ANALYSE DES METADONNEES
# ============================================================

print("\n" + "-" * 80)
print("ANALYSE DES METADONNEES")
print("-" * 80)

pages = []

for metadata in metadatas:
    if metadata:
        page = metadata.get("page")

        if page is not None:
            pages.append(page)

print(f"    Chunks avec numéro de page : {len(pages)}")

if pages:
    page_counter = Counter(pages)

    print(
        f"    Pages différentes         : "
        f"{len(page_counter)}"
    )

    print("\n    Répartition des chunks par page :")

    for page, nb in sorted(
        page_counter.items(),
        key=lambda x: x[0]
    ):
        print(f"       Page {page}: {nb} chunk(s)")


# ============================================================
# AFFICHER QUELQUES CHUNKS
# ============================================================

print("\n" + "=" * 80)
print("ECHANTILLON DE CHUNKS")
print("=" * 80)

sample_size = min(10, len(documents))

for i in range(sample_size):

    doc = documents[i]
    metadata = metadatas[i] if i < len(metadatas) else {}
    doc_id = ids[i] if i < len(ids) else "N/A"

    print("\n" + "-" * 80)
    print(f"CHUNK #{i + 1}")
    print(f"ID       : {doc_id}")
    print(f"METADATA : {metadata}")
    print(f"TAILLE   : {len(doc) if doc else 0} caractères")

    print("\nTEXTE :")

    if doc:
        print(doc[:1200])
    else:
        print("[CHUNK VIDE]")


# ============================================================
# QUESTIONS DE TEST RAG
# ============================================================

questions = [
    "Comment protéger ma petite entreprise ?",

    "Quelles sont les bonnes pratiques pour les mots de passe ?",

    "Comment sauvegarder et protéger les données d'une PME ?",

    "Comment sensibiliser les employés à la cybersécurité ?",

    "Quelles mesures prendre contre les virus et les logiciels malveillants ?",

    "Comment protéger une entreprise contre les attaques par email ?",

    "Comment sécuriser le Wi-Fi de mon entreprise ?",

    "Comment protéger les systèmes informatiques d'une PME ?",

    "Quelles précautions prendre pour les employés ?",

    "Comment améliorer la sécurité des systèmes d'information ?",
]


# ============================================================
# TEST DE RECUPERATION RAG
# ============================================================

print("\n" + "=" * 80)
print("TEST DE RECUPERATION RAG")
print("=" * 80)

for question_number, question in enumerate(questions, start=1):

    print("\n" + "=" * 80)
    print(f"QUESTION {question_number}")
    print("=" * 80)

    print(f"\nQuestion : {question}")

    try:

        results = collection.query(
            query_texts=[question],
            n_results=TOP_K,
            include=["documents", "metadatas", "distances"]
        )

    except Exception as e:

        print(f"\nERREUR lors de la recherche : {e}")
        continue


    result_documents = results.get("documents", [[]])[0]
    result_metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]


    for rank, (doc, metadata, distance) in enumerate(
        zip(
            result_documents,
            result_metadatas,
            distances
        ),
        start=1
    ):

        print("\n" + "-" * 80)
        print(f"RESULTAT #{rank}")

        print(f"Distance : {distance:.4f}")

        if metadata:
            print(f"Page     : {metadata.get('page', 'N/A')}")
            print(f"Titre    : {metadata.get('title', 'N/A')}")
            print(f"Type     : {metadata.get('type', 'N/A')}")
        else:
            print("Metadata : aucune")

        print("\nTexte :")

        if doc:
            print(doc[:1000])
        else:
            print("[DOCUMENT VIDE]")


# ============================================================
# FIN
# ============================================================

print("\n" + "=" * 80)
print("VERIFICATION TERMINEE")
print("=" * 80)

print("\nRésumé :")
print(f"  - Collection       : {COLLECTION_NAME}")
print(f"  - Nombre de chunks : {count}")
print(f"  - Chunks vides     : {empty_chunks}")
print(f"  - Chunks < 100 car : {very_short}")
print(f"  - Chunks < 200 car : {short_chunks}")
print(f"  - Chunks > 2000 car: {long_chunks}")
print(f"  - Questions testées: {len(questions)}")

print("\nAnalyse terminée.")