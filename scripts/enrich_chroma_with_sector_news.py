# ============================================================================
# enrich_chroma_with_sector_news.py
# Enrichit ChromaDB avec les articles de sector_news
# ============================================================================

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
import chromadb
from chromadb.utils import embedding_functions
from config import DB_CONFIG, EMBEDDING_CONFIG
from utils.logger import get_logger

logger = get_logger("enrich_chroma_sector_news")

# ─── Configuration ─────────────────────────────────────────────────────────────
CHROMA_PATH = "data/chroma_db"
COLLECTION_NAME = "sector_news"
EMBEDDING_MODEL = EMBEDDING_CONFIG.get("model_name", "BAAI/bge-m3")


def get_articles(limit: int = None):
    """Récupère les articles de sector_news."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    query = """
        SELECT id, source, titre, description, categorie, date_publication, created_at
        FROM sector_news
        WHERE titre IS NOT NULL
        ORDER BY created_at DESC
    """
    if limit:
        query += f" LIMIT {limit}"
    
    cur.execute(query)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    return rows


def enrich_chroma_sector_news(limit: int = None, force_recreate: bool = False):
    """Enrichit ChromaDB avec les articles de sector_news."""
    
    print("\n📊 Récupération des articles sector_news...")
    rows = get_articles(limit)
    
    if not rows:
        print("❌ Aucun article trouvé dans sector_news.")
        return
    
    print(f"   ✅ {len(rows)} articles trouvés")
    
    print("\n💾 Connexion à ChromaDB...")
    os.makedirs(CHROMA_PATH, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )
    
    if force_recreate:
        try:
            client.delete_collection(COLLECTION_NAME)
            print(f"   🗑️ Collection '{COLLECTION_NAME}' supprimée")
        except:
            pass
    
    try:
        collection = client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn
        )
        print(f"   ✅ Collection '{COLLECTION_NAME}' récupérée")
    except:
        collection = client.create_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn,
            metadata={"description": "Articles de presse sectorielle"}
        )
        print(f"   ✅ Collection '{COLLECTION_NAME}' créée")
    
    print(f"\n📤 Ingestion des articles dans ChromaDB...")
    
    documents = []
    ids = []
    metadatas = []
    
    for row in rows:
        id_article, source, titre, description, categorie, date_publication, created_at = row
        
        texte = f"{titre}"
        if description:
            texte += f" {description}"
        
        meta = {
            "id": id_article,
            "source": source or "Inconnu",
            "categorie": categorie or "Inconnu",
            "date_publication": str(date_publication) if date_publication else "",
            "created_at": str(created_at) if created_at else "",
            "source_name": source or "Presse",
            "type": "news"
        }
        
        documents.append(texte)
        ids.append(f"sector_news_{id_article}")
        metadatas.append(meta)
    
    batch_size = 100
    total_added = 0
    
    for i in range(0, len(documents), batch_size):
        batch_docs = documents[i:i+batch_size]
        batch_ids = ids[i:i+batch_size]
        batch_metas = metadatas[i:i+batch_size]
        
        try:
            collection.add(
                documents=batch_docs,
                ids=batch_ids,
                metadatas=batch_metas
            )
            total_added += len(batch_docs)
            print(f"   Batch {i//batch_size + 1}: {len(batch_docs)} ajoutés ({total_added}/{len(documents)})")
        except Exception as e:
            print(f"   ❌ Erreur batch {i//batch_size + 1}: {e}")
    
    print(f"\n✅ {total_added} articles ingérés dans ChromaDB")
    print(f"   Collection: {COLLECTION_NAME}")
    print(f"   Base: {CHROMA_PATH}")
    
    return collection


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Enrichit ChromaDB avec les articles sectoriels")
    parser.add_argument("--limit", type=int, help="Nombre d'articles à ingérer")
    parser.add_argument("--force", action="store_true", help="Recréer la collection")
    args = parser.parse_args()
    
    print("\n" + "=" * 70)
    print("  📰 ENRICHISSEMENT CHROMADB AVEC SECTOR_NEWS")
    print("=" * 70)
    print(f"  Modèle: {EMBEDDING_MODEL}")
    print(f"  Collection: {COLLECTION_NAME}")
    if args.limit:
        print(f"  Limite: {args.limit} articles")
    print("=" * 70)
    
    enrich_chroma_sector_news(limit=args.limit, force_recreate=args.force)
    
    print("\n" + "=" * 70)
    print("  ✅ ENRICHISSEMENT TERMINÉ")
    print("=" * 70)


if __name__ == "__main__":
    main()