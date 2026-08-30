# ============================================================================
# enrich_chroma_with_entities.py
# Enrichit ChromaDB avec les incidents + entités NER
# ============================================================================

import sys
import os
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
import chromadb
from chromadb.utils import embedding_functions
from config import DB_CONFIG, EMBEDDING_CONFIG
from utils.logger import get_logger

logger = get_logger("enrich_chroma_entities")

# ─── Configuration ─────────────────────────────────────────────────────────────
CHROMA_PATH = "data/chroma_db"
COLLECTION_NAME = "cyber_incidents"
EMBEDDING_MODEL = EMBEDDING_CONFIG.get("model_name", "BAAI/bge-m3")


# ─── Fonction utilitaire pour extraire les valeurs des entités ──────────────

def extract_entity_values(entities_dict, entity_type):
    """
    Extrait les valeurs des entités de type 'entity_type' depuis le dictionnaire.
    Les entités sont stockées sous forme de dictionnaires avec une clé 'value'.
    """
    entity_list = entities_dict.get(entity_type, [])
    if not entity_list:
        return []
    
    values = []
    for item in entity_list:
        if isinstance(item, dict):
            # Les entités ont une clé 'value' (ex: {"value": "CVE-2024-1234", "type": "CVE", "confidence": 0.99})
            values.append(item.get('value', str(item)))
        else:
            # Fallback si ce n'est pas un dictionnaire
            values.append(str(item))
    return values


# ─── Connexion PostgreSQL ────────────────────────────────────────────────────

def get_incidents_with_entities(limit: int = None):
    """Récupère les incidents avec entités NER."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    query = """
        SELECT id, titre, description, type_menace, secteur_cible, 
               severite, source, created_at, raw_data
        FROM cyber_incidents
        WHERE raw_data->'entities' IS NOT NULL
        ORDER BY created_at DESC
    """
    if limit:
        query += f" LIMIT {limit}"
    
    cur.execute(query)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    return rows


def build_enriched_text(row):
    """
    Construit un texte enrichi à partir des données.
    🔥 CORRIGÉ : Gère les entités sous forme de dictionnaires
    """
    id_incident, titre, description, type_menace, secteur_cible, severite, source, created_at, raw_data = row
    
    entities = raw_data.get('entities', {}) if raw_data else {}
    
    # Texte de base
    texte = f"{titre}"
    if description:
        texte += f" {description}"
    
    # 🔥 CORRECTION : Utiliser extract_entity_values pour extraire les valeurs
    cve_values = extract_entity_values(entities, 'cve')
    if cve_values:
        texte += f" CVE: {', '.join(cve_values)}"
    
    malware_values = extract_entity_values(entities, 'malwares')
    if malware_values:
        texte += f" Malware: {', '.join(malware_values)}"
    
    sector_values = extract_entity_values(entities, 'secteurs')
    if sector_values:
        texte += f" Secteur: {', '.join(sector_values)}"
    
    country_values = extract_entity_values(entities, 'pays')
    if country_values:
        texte += f" Pays: {', '.join(country_values)}"
    
    # Ajouter les métadonnées
    texte += f" Type: {type_menace}"
    if severite and severite != 'INCONNUE':
        texte += f" Sévérité: {severite}"
    
    return texte, entities


def enrich_chroma(limit: int = None, force_recreate: bool = False):
    """Enrichit la collection ChromaDB avec les incidents."""
    
    print("\n📊 Récupération des incidents avec entités...")
    rows = get_incidents_with_entities(limit)
    
    if not rows:
        print("❌ Aucun incident avec entités trouvé.")
        print("   Lance d'abord : python scripts/extract_entities_ner.py --apply")
        return
    
    print(f"   ✅ {len(rows)} incidents trouvés")
    
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
            metadata={"description": "Incidents cyber avec entités NER"}
        )
        print(f"   ✅ Collection '{COLLECTION_NAME}' créée")
    
    print("\n📤 Ingestion des incidents dans ChromaDB...")
    
    documents = []
    ids = []
    metadatas = []
    
    for row in rows:
        id_incident, titre, description, type_menace, secteur_cible, severite, source, created_at, raw_data = row
        
        texte_enrichi, entities = build_enriched_text(row)
        
        # 🔥 CORRECTION : Extraire les valeurs pour les métadonnées
        cve_values = extract_entity_values(entities, 'cve')
        malware_values = extract_entity_values(entities, 'malwares')
        sector_values = extract_entity_values(entities, 'secteurs')
        country_values = extract_entity_values(entities, 'pays')
        
        meta = {
            "id": id_incident,
            "type_menace": type_menace or "Inconnu",
            "secteur_cible": secteur_cible or "Inconnu",
            "severite": severite or "INCONNUE",
            "source": source or "Inconnu",
            "cve": ", ".join(cve_values) if cve_values else "",
            "malwares": ", ".join(malware_values) if malware_values else "",
            "secteurs": ", ".join(sector_values) if sector_values else "",
            "pays": ", ".join(country_values) if country_values else "",
            "created_at": str(created_at) if created_at else "",
            "source_name": "Incident cyber",
            "type": "incident"
        }
        
        documents.append(texte_enrichi)
        ids.append(f"incident_{id_incident}")
        metadatas.append(meta)
    
    # Ingestion par batch
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
    
    print(f"\n✅ {total_added} incidents ingérés dans ChromaDB")
    print(f"   Collection: {COLLECTION_NAME}")
    print(f"   Base: {CHROMA_PATH}")
    
    print("\n📊 Statistiques de la collection:")
    try:
        count = collection.count()
        print(f"   Total documents: {count}")
        
        sample = collection.get(limit=3)
        if sample and sample['metadatas']:
            print("\n   Exemple de métadonnées:")
            for meta in sample['metadatas'][:3]:
                print(f"     - type: {meta.get('type_menace', '?')} | secteur: {meta.get('secteur_cible', '?')} | malware: {meta.get('malwares', '?')}")
    except Exception as e:
        print(f"   ❌ Erreur statistiques: {e}")
    
    return collection


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Enrichit ChromaDB avec les entités NER")
    parser.add_argument("--limit", type=int, help="Nombre d'incidents à ingérer")
    parser.add_argument("--force", action="store_true", help="Recréer la collection")
    args = parser.parse_args()
    
    print("\n" + "=" * 70)
    print("  🔥 ENRICHISSEMENT CHROMADB AVEC LES ENTITÉS NER")
    print("=" * 70)
    print(f"  Modèle: {EMBEDDING_MODEL}")
    print(f"  Collection: {COLLECTION_NAME}")
    if args.limit:
        print(f"  Limite: {args.limit} incidents")
    if args.force:
        print("  Mode: Re-création de la collection")
    print("=" * 70)
    
    enrich_chroma(limit=args.limit, force_recreate=args.force)
    
    print("\n" + "=" * 70)
    print("  ✅ ENRICHISSEMENT TERMINÉ")
    print("=" * 70)


if __name__ == "__main__":
    main()