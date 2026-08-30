# ============================================================================
# scripts/verify_stats.py
# ============================================================================
# Vérification de cohérence des statistiques
#
# Objectif :
#   Vérifier que les statistiques produites sur plusieurs jours
#   restent cohérentes avec les données présentes en base.
# ============================================================================

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

import psycopg2
import pandas as pd

from config import DB_CONFIG
from utils.logger import get_logger


logger = get_logger("verify_stats")


# ============================================================================
# VERIFICATION
# ============================================================================

def verify_stats():

    conn = None

    try:

        conn = psycopg2.connect(
            **DB_CONFIG
        )

        print("\n" + "=" * 70)
        print(" VÉRIFICATION DE COHÉRENCE DES STATISTIQUES")
        print("=" * 70)

        # ====================================================================
        # 1. TOTAL EN BASE
        # ====================================================================

        df_total = pd.read_sql(
            """
            SELECT COUNT(*) AS total
            FROM cyber_incidents
            """,
            conn
        )

        total = int(
            df_total["total"].iloc[0]
        )

        # ====================================================================
        # 2. TOTAL PAR TYPE
        # ====================================================================

        df_types = pd.read_sql(
            """
            SELECT
                COALESCE(
                    NULLIF(TRIM(type_menace), ''),
                    'INCONNU'
                ) AS type_menace,

                COUNT(*) AS nb

            FROM cyber_incidents

            GROUP BY
                COALESCE(
                    NULLIF(TRIM(type_menace), ''),
                    'INCONNU'
                )
            """,
            conn
        )

        total_types = int(
            df_types["nb"].sum()
        )

        # ====================================================================
        # 3. TOTAL PAR JOUR
        # ====================================================================

        df_jours = pd.read_sql(
            """
            SELECT
                DATE(created_at) AS jour,
                COUNT(*) AS nb

            FROM cyber_incidents

            WHERE created_at IS NOT NULL

            GROUP BY DATE(created_at)

            ORDER BY jour ASC
            """,
            conn
        )

        total_jours = int(
            df_jours["nb"].sum()
        )

        # ====================================================================
        # 4. STATISTIQUES SUR LES 15 DERNIERS JOURS
        # ====================================================================

        df_15jours = pd.read_sql(
            """
            SELECT
                DATE(created_at) AS jour,
                COUNT(*) AS nb

            FROM cyber_incidents

            WHERE
                created_at >= CURRENT_DATE - INTERVAL '14 days'

            GROUP BY DATE(created_at)

            ORDER BY jour ASC
            """,
            conn
        )

        # ====================================================================
        # 5. AFFICHAGE DES RESULTATS
        # ====================================================================

        print("\n TOTAL GLOBAL")
        print("-" * 70)

        print(
            f"Total en base       : {total}"
        )

        print(
            f"Total par type      : {total_types}"
        )

        print(
            f"Total par jour      : {total_jours}"
        )

        # ====================================================================
        # 6. COHERENCE TOTAL / TYPES
        # ====================================================================

        print("\n COHÉRENCE DES TYPES DE MENACES")
        print("-" * 70)

        if total == total_types:

            print(
                " OK : "
                "la somme des types correspond au total."
            )

        else:

            print(
                " ERREUR : "
                f"écart de {total - total_types}"
            )

        # ====================================================================
        # 7. COHERENCE TOTAL / JOURS
        # ====================================================================

        print("\n COHÉRENCE DES ÉVÉNEMENTS PAR JOUR")
        print("-" * 70)

        if total == total_jours:

            print(
                " OK : "
                "la somme des événements journaliers "
                "correspond au total."
            )

        else:

            print(
                " Écart entre total et événements journaliers : "
                f"{total - total_jours}"
            )

            print(
                "   Vérifier les lignes dont created_at est NULL."
            )

        # ====================================================================
        # 8. RECHERCHE DE VALEURS ANORMALES
        # ====================================================================

        print("\n CONTRÔLE DES VALEURS")
        print("-" * 70)

        if not df_types.empty:

            if (df_types["nb"] < 0).any():

                print(
                    " Nombre négatif trouvé dans les types."
                )

            else:

                print(
                    " Aucun nombre négatif dans les types."
                )

        if not df_jours.empty:

            if (df_jours["nb"] < 0).any():

                print(
                    " Nombre négatif trouvé dans les jours."
                )

            else:

                print(
                    " Aucun nombre négatif dans les jours."
                )

        # ====================================================================
        # 9. AFFICHAGE DES 15 JOURS
        # ====================================================================

        print("\nÉVÉNEMENTS SUR LES 15 DERNIERS JOURS")
        print("-" * 70)

        if not df_15jours.empty:

            print(
                df_15jours.to_string(
                    index=False
                )
            )

            print(
                f"\nNombre de jours avec événements : "
                f"{len(df_15jours)}"
            )

            print(
                f"Total événements sur cette période : "
                f"{int(df_15jours['nb'].sum())}"
            )

        else:

            print(
                "Aucun événement trouvé."
            )

        # ====================================================================
        # 10. RESULTAT FINAL
        # ====================================================================

        types_ok = (
            total == total_types
        )

        jours_ok = (
            total == total_jours
        )

        valeurs_ok = (
            not df_types.empty
            and not (df_types["nb"] < 0).any()
            and (
                df_jours.empty
                or not (df_jours["nb"] < 0).any()
            )
        )

        print("\n" + "=" * 70)

        if types_ok and jours_ok and valeurs_ok:

            print(
                "RÉSULTAT FINAL : "
                "STATISTIQUES COHÉRENTES"
            )

        elif types_ok and valeurs_ok:

            print(
                "RÉSULTAT FINAL : "
                "STATISTIQUES GLOBALEMENT COHÉRENTES"
            )

            print(
                "   L'écart sur les jours peut provenir "
                "de created_at NULL."
            )

        else:

            print(
                "RÉSULTAT FINAL : "
                "VÉRIFICATION À CORRIGER"
            )

        print("=" * 70)

        return {
            "total": total,
            "total_types": total_types,
            "total_jours": total_jours,
            "types_ok": types_ok,
            "jours_ok": jours_ok,
            "valeurs_ok": valeurs_ok
        }

    except Exception as e:

        logger.error(
            f"Erreur vérification statistiques : {e}"
        )

        print(
            f"Erreur : {e}"
        )

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

    verify_stats()