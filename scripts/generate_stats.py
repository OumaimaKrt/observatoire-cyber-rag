# ============================================================================
# scripts/generate_stats.py
# ============================================================================
# Génération des statistiques de l'Observatoire Cyber
#
# Objectifs :
#   - Nombre d'événements par jour
#   - Répartition par type de menace
#   - Répartition par secteur
#   - Statistiques des dernières 24h
#   - Vérification de cohérence
#   - Export CSV + JSON
# ============================================================================

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

import psycopg2
import pandas as pd
from datetime import datetime, date
import json
from decimal import Decimal

from config import DB_CONFIG
from utils.logger import get_logger


logger = get_logger("stats")

STATS_PATH = os.path.join("data", "stats")


# ============================================================================
# SERIALISATION JSON
# ============================================================================

def json_serializer(obj):
    """Convertit les types non JSON en types sérialisables."""

    if isinstance(obj, (datetime, pd.Timestamp)):
        return obj.isoformat()

    if isinstance(obj, date):
        return obj.isoformat()

    if isinstance(obj, Decimal):
        return float(obj)

    if isinstance(obj, bytes):
        return obj.decode("utf-8")

    raise TypeError(f"Type {type(obj)} non sérialisable")


# ============================================================================
# GENERATION DES STATISTIQUES
# ============================================================================

def generate_stats():

    os.makedirs(STATS_PATH, exist_ok=True)

    conn = None

    try:

        conn = psycopg2.connect(**DB_CONFIG)

        now = datetime.now()

        print("\n" + "=" * 70)
        print("GÉNÉRATION DES STATISTIQUES")
        print("=" * 70)

        # ====================================================================
        # 1. TOTAL DES INCIDENTS
        # ====================================================================

        df_total = pd.read_sql(
            """
            SELECT COUNT(*) AS total
            FROM cyber_incidents
            """,
            conn
        )

        total = int(df_total["total"].iloc[0])

        # ====================================================================
        # 2. NOMBRE D'ÉVÉNEMENTS PAR JOUR
        # ====================================================================

        df_jour = pd.read_sql(
            """
            SELECT
                DATE(created_at) AS jour,
                COUNT(*) AS nb
            FROM cyber_incidents
            WHERE created_at IS NOT NULL
            GROUP BY DATE(created_at)
            ORDER BY jour DESC
            """,
            conn
        )

        if not df_jour.empty:
            df_jour["nb"] = df_jour["nb"].astype(int)

        # ====================================================================
        # 3. RÉPARTITION PAR TYPE DE MENACE
        # ====================================================================
        # IMPORTANT :
        # On conserve INCONNU afin que la somme représente 100 % des incidents.

        df_types = pd.read_sql(
            """
            SELECT
                COALESCE(NULLIF(TRIM(type_menace), ''), 'INCONNU')
                    AS type_menace,
                COUNT(*) AS nb,
                ROUND(
                    COUNT(*) * 100.0 /
                    NULLIF(SUM(COUNT(*)) OVER (), 0),
                    1
                ) AS pourcentage
            FROM cyber_incidents
            GROUP BY
                COALESCE(NULLIF(TRIM(type_menace), ''), 'INCONNU')
            ORDER BY nb DESC
            """,
            conn
        )

        if not df_types.empty:
            df_types["nb"] = df_types["nb"].astype(int)
            df_types["pourcentage"] = df_types["pourcentage"].astype(float)

        # ====================================================================
        # 4. RÉPARTITION PAR SECTEUR
        # ====================================================================

        df_secteurs = pd.read_sql(
            """
            SELECT
                COALESCE(NULLIF(TRIM(secteur_cible), ''), 'INCONNU')
                    AS secteur_cible,
                COUNT(*) AS nb,
                ROUND(
                    COUNT(*) * 100.0 /
                    NULLIF(SUM(COUNT(*)) OVER (), 0),
                    1
                ) AS pourcentage
            FROM cyber_incidents
            GROUP BY
                COALESCE(NULLIF(TRIM(secteur_cible), ''), 'INCONNU')
            ORDER BY nb DESC
            """,
            conn
        )

        if not df_secteurs.empty:
            df_secteurs["nb"] = df_secteurs["nb"].astype(int)
            df_secteurs["pourcentage"] = df_secteurs["pourcentage"].astype(float)

        # ====================================================================
        # 5. DERNIÈRES 24 HEURES
        # ====================================================================

        df_24h = pd.read_sql(
            """
            SELECT
                COUNT(*) AS nb_24h,
                COUNT(DISTINCT source) AS nb_sources_24h
            FROM cyber_incidents
            WHERE created_at >= NOW() - INTERVAL '24 hours'
            """,
            conn
        )

        nb_24h = (
            int(df_24h["nb_24h"].iloc[0])
            if not df_24h.empty
            else 0
        )

        nb_sources_24h = (
            int(df_24h["nb_sources_24h"].iloc[0])
            if not df_24h.empty
            else 0
        )

        # ====================================================================
        # 6. STATISTIQUES DES 15 DERNIERS JOURS
        # ====================================================================

        df_15jours = pd.read_sql(
            """
            SELECT
                DATE(created_at) AS jour,
                COUNT(*) AS nb
            FROM cyber_incidents
            WHERE created_at >= CURRENT_DATE - INTERVAL '14 days'
            GROUP BY DATE(created_at)
            ORDER BY jour ASC
            """,
            conn
        )

        if not df_15jours.empty:
            df_15jours["nb"] = df_15jours["nb"].astype(int)

        # ====================================================================
        # 7. VÉRIFICATION DE COHÉRENCE
        # ====================================================================

        print("\n" + "-" * 70)
        print("🔍 VÉRIFICATION DE COHÉRENCE")
        print("-" * 70)

        # Total calculé par les types
        total_types = (
            int(df_types["nb"].sum())
            if not df_types.empty
            else 0
        )

        # Total des événements journaliers
        total_jours = (
            int(df_jour["nb"].sum())
            if not df_jour.empty
            else 0
        )

        # Somme des pourcentages
        somme_pourcentages = (
            float(df_types["pourcentage"].sum())
            if not df_types.empty
            else 0
        )

        print(f"Total incidents en base       : {total}")
        print(f"Total selon les types         : {total_types}")
        print(f"Total selon les jours         : {total_jours}")

        print(
            f"Somme des pourcentages        : "
            f"{somme_pourcentages:.1f}%"
        )

        # Vérification types
        if total_types == total:
            print("Cohérence TOTAL / TYPES : OK")
        else:
            print(
                f"Cohérence TOTAL / TYPES : "
                f"ERREUR ({total - total_types})"
            )

        # Vérification jours
        if total_jours == total:
            print("Cohérence TOTAL / JOURS : OK")
        else:
            print(
                f"TOTAL / JOURS différent : "
                f"{total - total_jours}"
            )
            print(
                "   Cela peut être normal si certains incidents "
                "ont created_at = NULL."
            )

        # Vérification valeurs négatives
        if not df_jour.empty and (df_jour["nb"] < 0).any():
            print("Valeur négative détectée")
        else:
            print("Aucun nombre négatif")

        # Vérification pourcentages
        if 99.0 <= somme_pourcentages <= 101.0:
            print("Répartition des menaces : cohérente")
        else:
            print(" Somme des pourcentages légèrement différente de 100%")

        # ====================================================================
        # 8. EXPORT CSV
        # ====================================================================

        date_str = now.strftime("%Y%m%d_%H%M%S")

        fichier_jour = os.path.join(
            STATS_PATH,
            f"evolution_journaliere_{date_str}.csv"
        )

        fichier_types = os.path.join(
            STATS_PATH,
            f"repartition_menaces_{date_str}.csv"
        )

        fichier_secteurs = os.path.join(
            STATS_PATH,
            f"repartition_secteurs_{date_str}.csv"
        )

        fichier_15jours = os.path.join(
            STATS_PATH,
            f"evolution_15jours_{date_str}.csv"
        )

        df_jour.to_csv(
            fichier_jour,
            index=False,
            encoding="utf-8"
        )

        df_types.to_csv(
            fichier_types,
            index=False,
            encoding="utf-8"
        )

        df_secteurs.to_csv(
            fichier_secteurs,
            index=False,
            encoding="utf-8"
        )

        df_15jours.to_csv(
            fichier_15jours,
            index=False,
            encoding="utf-8"
        )

        # ====================================================================
        # 9. EXPORT JSON
        # ====================================================================

        stats = {
            "date_generation": now.isoformat(),

            "total_incidents": total,

            "dernieres_24h": {
                "nombre_evenements": nb_24h,
                "nombre_sources": nb_sources_24h
            },

            "coherence": {
                "total_base": total,
                "total_types": total_types,
                "total_jours": total_jours,
                "somme_pourcentages": round(
                    somme_pourcentages,
                    1
                ),
                "types_coherents": total_types == total,
                "valeurs_negatives": False
            },

            "types_menaces": (
                df_types.to_dict("records")
                if not df_types.empty
                else []
            ),

            "secteurs": (
                df_secteurs.to_dict("records")
                if not df_secteurs.empty
                else []
            ),

            "evolution_journaliere": (
                df_jour.to_dict("records")
                if not df_jour.empty
                else []
            ),

            "evolution_15jours": (
                df_15jours.to_dict("records")
                if not df_15jours.empty
                else []
            )
        }

        fichier_json = os.path.join(
            STATS_PATH,
            f"stats_{date_str}.json"
        )

        with open(
            fichier_json,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                stats,
                f,
                ensure_ascii=False,
                indent=2,
                default=json_serializer
            )

        # ====================================================================
        # 10. AFFICHAGE
        # ====================================================================

        print("\n" + "=" * 70)
        print(
            f"STATISTIQUES - "
            f"{now.strftime('%d/%m/%Y %H:%M:%S')}"
        )
        print("=" * 70)

        print(f"Total incidents : {total}")
        print(f"Dernières 24h   : {nb_24h}")
        print(f"Sources 24h     : {nb_sources_24h}")

        print("\n🔝 RÉPARTITION PAR TYPE DE MENACE")
        print("-" * 70)

        if not df_types.empty:
            print(
                df_types.to_string(index=False)
            )

        print("\n ÉVÉNEMENTS PAR JOUR")
        print("-" * 70)

        if not df_15jours.empty:
            print(
                df_15jours.to_string(index=False)
            )

        print("\n RÉPARTITION PAR SECTEUR")
        print("-" * 70)

        if not df_secteurs.empty:
            print(
                df_secteurs.head(10).to_string(index=False)
            )

        print("\nFICHIERS GÉNÉRÉS")
        print(f"  - {fichier_jour}")
        print(f"  - {fichier_types}")
        print(f"  - {fichier_secteurs}")
        print(f"  - {fichier_15jours}")
        print(f"  - {fichier_json}")

        print("=" * 70)

        return stats

    except Exception as e:

        logger.error(
            f"Erreur génération statistiques : {e}"
        )

        print(f"Erreur : {e}")

        import traceback
        traceback.print_exc()

        return None

    finally:

        if conn:
            conn.close()


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    generate_stats()