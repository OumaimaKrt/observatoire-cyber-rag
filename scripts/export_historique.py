# ============================================================================
# scripts/export_historique.py
# ============================================================================
# Export de l'historique cumulé des données collectées
#
# Objectif :
#   Construire un historique exploitable de tous les incidents collectés.
# ============================================================================

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

import psycopg2
import pandas as pd
from datetime import datetime

from config import DB_CONFIG
from utils.logger import get_logger


logger = get_logger("export_historique")

HISTORIQUE_PATH = os.path.join(
    "data",
    "historique"
)


# ============================================================================
# EXPORT DE L'HISTORIQUE
# ============================================================================

def export_historique():

    os.makedirs(
        HISTORIQUE_PATH,
        exist_ok=True
    )

    conn = None

    try:

        conn = psycopg2.connect(
            **DB_CONFIG
        )

        print("\n" + "=" * 70)
        print("EXPORT DE L'HISTORIQUE CUMULÉ")
        print("=" * 70)

        # ====================================================================
        # 1. HISTORIQUE COMPLET
        # ====================================================================

        df = pd.read_sql(
            """
            SELECT
                id,
                source,
                titre,
                description,
                date_incident,
                date_collecte,
                created_at,
                type_menace,
                secteur_cible,
                severite,
                pays,
                score_cvss,
                url_source,
                langue,
                pertinence_pme,
                confiance_globale,
                risque,
                acteur_menace,
                classification_method
            FROM cyber_incidents
            ORDER BY created_at ASC, id ASC
            """,
            conn
        )

        print(
            f" Nombre total d'incidents : {len(df)}"
        )

        # ====================================================================
        # 2. FICHIER CUMULÉ PRINCIPAL
        # ====================================================================

        fichier_historique = os.path.join(
            HISTORIQUE_PATH,
            "cyber_incidents_historique.csv"
        )

        df.to_csv(
            fichier_historique,
            index=False,
            encoding="utf-8"
        )

        print(
            f"Historique cumulé : "
            f"{fichier_historique}"
        )

        # ====================================================================
        # 3. HISTORIQUE DES 15 DERNIERS JOURS
        # ====================================================================

        df_15jours = pd.read_sql(
            """
            SELECT
                DATE(created_at) AS jour,
                COUNT(*) AS nb_evenements,

                COUNT(
                    CASE
                        WHEN UPPER(
                            COALESCE(type_menace, 'INCONNU')
                        ) != 'INCONNU'
                        THEN 1
                    END
                ) AS menaces_identifiees,

                COUNT(
                    CASE
                        WHEN UPPER(
                            COALESCE(type_menace, 'INCONNU')
                        ) = 'INCONNU'
                        THEN 1
                    END
                ) AS menaces_inconnues

            FROM cyber_incidents

            WHERE created_at >= CURRENT_DATE - INTERVAL '14 days'

            GROUP BY DATE(created_at)

            ORDER BY jour ASC
            """,
            conn
        )

        fichier_15jours = os.path.join(
            HISTORIQUE_PATH,
            "resume_15jours.csv"
        )

        df_15jours.to_csv(
            fichier_15jours,
            index=False,
            encoding="utf-8"
        )

        # ====================================================================
        # 4. RÉPARTITION PAR TYPE SUR LES 15 JOURS
        # ====================================================================

        df_types_15jours = pd.read_sql(
            """
            SELECT
                COALESCE(
                    NULLIF(TRIM(type_menace), ''),
                    'INCONNU'
                ) AS type_menace,

                COUNT(*) AS nb

            FROM cyber_incidents

            WHERE created_at >= CURRENT_DATE - INTERVAL '14 days'

            GROUP BY
                COALESCE(
                    NULLIF(TRIM(type_menace), ''),
                    'INCONNU'
                )

            ORDER BY nb DESC
            """,
            conn
        )

        fichier_types = os.path.join(
            HISTORIQUE_PATH,
            "menaces_15jours.csv"
        )

        df_types_15jours.to_csv(
            fichier_types,
            index=False,
            encoding="utf-8"
        )

        # ====================================================================
        # 5. RÉSUMÉ GLOBAL
        # ====================================================================

        total = len(df)

        jours = (
            df["created_at"]
            .dropna()
            .dt.date
            .nunique()
            if not df.empty
            else 0
        )

        resume = pd.DataFrame([
            {
                "date_export": datetime.now().isoformat(),
                "total_incidents": total,
                "nombre_jours_couverts": jours,
                "fichier_historique": (
                    "cyber_incidents_historique.csv"
                )
            }
        ])

        fichier_resume = os.path.join(
            HISTORIQUE_PATH,
            "resume_historique.csv"
        )

        resume.to_csv(
            fichier_resume,
            index=False,
            encoding="utf-8"
        )

        # ====================================================================
        # 6. AFFICHAGE
        # ====================================================================

        print("\n" + "-" * 70)
        print("RÉSUMÉ DES 15 DERNIERS JOURS")
        print("-" * 70)

        if not df_15jours.empty:
            print(
                df_15jours.to_string(
                    index=False
                )
            )
        else:
            print(
                "Aucune donnée disponible "
                "sur les 15 derniers jours."
            )

        print("\n" + "-" * 70)
        print("RÉPARTITION DES MENACES SUR LES 15 DERNIERS JOURS")
        print("-" * 70)

        if not df_types_15jours.empty:
            print(
                df_types_15jours.to_string(
                    index=False
                )
            )

        print("\n FICHIERS GÉNÉRÉS")
        print(
            f"  - {fichier_historique}"
        )
        print(
            f"  - {fichier_15jours}"
        )
        print(
            f"  - {fichier_types}"
        )
        print(
            f"  - {fichier_resume}"
        )

        print("=" * 70)

        return df

    except Exception as e:

        logger.error(
            f"Erreur export historique : {e}"
        )

        print(
            f" Erreur : {e}"
        )

        import traceback
        traceback.print_exc()

        return None

    finally:

        if conn:
            conn.close()


# ============================================================================
# STATISTIQUES CHROMADB
# ============================================================================

def export_collection_stats():

    try:

        import chromadb

        from config import CHROMA_PATH

        client = chromadb.PersistentClient(
            path=CHROMA_PATH
        )

        print("\n" + "=" * 70)
        print(" STATISTIQUES DES COLLECTIONS CHROMADB")
        print("=" * 70)

        stats = []

        for collection in client.list_collections():

            count = collection.count()

            stats.append({
                "collection": collection.name,
                "documents": count
            })

            print(
                f"  {collection.name}: "
                f"{count} documents"
            )

        df = pd.DataFrame(stats)

        fichier = os.path.join(
            HISTORIQUE_PATH,
            "chromadb_stats.csv"
        )

        df.to_csv(
            fichier,
            index=False,
            encoding="utf-8"
        )

        print(
            f"Statistiques ChromaDB : "
            f"{fichier}"
        )

        return stats

    except Exception as e:

        print(
            f"Erreur ChromaDB : {e}"
        )

        return None


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":

    print("\n" + "=" * 70)
    print("EXPORT HISTORIQUE OBSERVATOIRE CYBER")
    print("=" * 70)

    export_historique()

    export_collection_stats()