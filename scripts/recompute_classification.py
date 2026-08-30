#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ============================================================================
# scripts/recompute_classification.py
# ============================================================================
# RECLASSIFICATION DES PIRATAGE EXISTANTS
#
# Moteur hybride Règles + ML via classifiers.py
#
# MODES :
#   DRY-RUN :
#       python scripts/recompute_classification.py
#
#   APPLICATION :
#       python scripts/recompute_classification.py --apply
#
#   APPLICATION FORCÉE :
#       python scripts/recompute_classification.py --apply --force
#
#   SEUIL :
#       python scripts/recompute_classification.py --seuil 0.35
#
# ============================================================================

import sys
import os
import argparse
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

# ============================================================================
# PATH PROJET
# ============================================================================

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ============================================================================
# DEPENDANCES
# ============================================================================

import psycopg2
from psycopg2.extras import RealDictCursor

from config import DB_CONFIG
from utils.logger import get_logger

from utils.classifiers import (
    classifier_cyber_complet,
    niveau_confiance,
    niveau_risque,  # ✅ Importé depuis classifiers.py
    normaliser_pour_stockage_menace,
    normaliser_pour_stockage_secteur,
    normaliser_pour_stockage_severite,
    get_ml_classifier_status,
)

logger = get_logger("recompute_classification")

# ============================================================================
# CONFIGURATION
# ============================================================================

MODEL_VERSION = "RULES_ML_v4"
CLASSIFICATION_METHOD = "HYBRIDE_RULES_ML"
DEFAULT_THRESHOLD = 0.35


# ============================================================================
# UTILITAIRES
# ============================================================================

def valeur_str(value: Any, default: str = "INCONNU") -> str:
    """
    Convertit proprement une valeur en chaîne normalisée.
    """
    if value is None:
        return default

    value = str(value).strip()

    if not value:
        return default

    return value


def normaliser_comparaison(value: Any) -> str:
    """
    Normalisation utilisée uniquement pour comparer deux valeurs.
    """
    return valeur_str(value).strip().upper()


def securiser_raw_data(raw_data: Any) -> Dict[str, Any]:
    """
    Transforme raw_data en dictionnaire exploitable.
    """

    if raw_data is None:
        return {}

    if isinstance(raw_data, dict):
        return raw_data

    if isinstance(raw_data, str):
        try:
            value = json.loads(raw_data)

            if isinstance(value, dict):
                return value

        except (json.JSONDecodeError, TypeError):
            return {}

    try:
        if hasattr(raw_data, "items"):
            return dict(raw_data)
    except Exception:
        pass

    return {}


# ============================================================================
# MIGRATION BASE DE DONNEES
# ============================================================================

def ajouter_colonnes(conn) -> None:
    """
    Ajoute les colonnes nécessaires.

    IMPORTANT :
    Cette fonction NE FAIT PAS de commit.
    Le commit est géré par recompute().
    """

    cur = conn.cursor()

    colonnes = {
        "confiance_type": "FLOAT",
        "confiance_secteur": "FLOAT",
        "confiance_severite": "FLOAT",
        "confiance_globale": "FLOAT",

        "niveau_confiance_type": "VARCHAR(20)",
        "niveau_confiance_secteur": "VARCHAR(20)",
        "niveau_confiance_severite": "VARCHAR(20)",

        "classification_method": "VARCHAR(100)",
        "classification_model": "VARCHAR(100)",

        "preuves_menace": "TEXT[]",
        "preuves_secteur": "TEXT[]",
        "preuves_severite": "TEXT[]",

        "risque": "INTEGER",
        "niveau_risque": "VARCHAR(20)",

        "updated_at": "TIMESTAMP DEFAULT NOW()",

        "ancien_type_menace": "VARCHAR(50)",
        "ancien_secteur": "VARCHAR(50)",
        "ancienne_severite": "VARCHAR(20)",
        "ancien_risque": "INTEGER",

        "prediction_ml": "VARCHAR(50)",
        "confiance_ml": "FLOAT",

        "prediction_regles": "VARCHAR(50)",
        "confiance_regles": "FLOAT",

        "accord_regles_ml": "BOOLEAN",
        "methode_menace": "VARCHAR(50)",
    }

    try:

        for col, dtype in colonnes.items():

            cur.execute(
                f"""
                ALTER TABLE cyber_incidents
                ADD COLUMN IF NOT EXISTS {col} {dtype}
                """
            )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_cyber_incidents_ancien_type
            ON cyber_incidents(ancien_type_menace)
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_cyber_incidents_classification_method
            ON cyber_incidents(classification_method)
            """
        )

        logger.info(
            "Colonnes de classification vérifiées/ajoutées."
        )

    finally:
        cur.close()


# ============================================================================
# HISTORIQUE
# ============================================================================

def creer_historique(conn) -> None:
    """
    Crée la table d'historique.

    IMPORTANT :
    Aucun commit ici.
    """

    cur = conn.cursor()

    try:

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS classification_history (

                id SERIAL PRIMARY KEY,

                incident_id INTEGER
                    REFERENCES cyber_incidents(id)
                    ON DELETE CASCADE,

                ancien_type VARCHAR(50),
                ancien_secteur VARCHAR(50),
                ancienne_severite VARCHAR(20),
                ancien_risque INTEGER,

                nouveau_type VARCHAR(50),
                nouveau_secteur VARCHAR(50),
                nouvelle_severite VARCHAR(20),
                nouveau_risque INTEGER,

                confiance_type FLOAT,
                confiance_secteur FLOAT,
                confiance_severite FLOAT,
                confiance_globale FLOAT,

                preuves_menace TEXT[],
                preuves_secteur TEXT[],
                preuves_severite TEXT[],

                methode_classification VARCHAR(100),
                modele_version VARCHAR(50),
                source VARCHAR(100),

                prediction_ml VARCHAR(50),
                confiance_ml FLOAT,

                prediction_regles VARCHAR(50),
                confiance_regles FLOAT,

                accord_regles_ml BOOLEAN,

                date_modification TIMESTAMP DEFAULT NOW()
            )
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_classification_history_incident
            ON classification_history(incident_id)
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_classification_history_date
            ON classification_history(date_modification DESC)
            """
        )

        logger.info(
            "Table classification_history vérifiée."
        )

    finally:
        cur.close()


# ============================================================================
# BACKUP
# ============================================================================

def creer_backup(conn) -> str:
    """
    Crée un backup des PIRATAGE avant application.
    """

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    table_name = (
        f"cyber_incidents_backup_piratage_{timestamp}"
    )

    cur = conn.cursor()

    try:

        cur.execute(
            f"""
            CREATE TABLE {table_name} AS
            SELECT *
            FROM cyber_incidents
            WHERE UPPER(
                COALESCE(type_menace, '')
            ) = 'PIRATAGE'
            """
        )

        cur.execute(
            f"""
            COMMENT ON TABLE {table_name} IS
            'Backup des incidents PIRATAGE avant reclassification du {timestamp}'
            """
        )

        logger.info(
            f"Backup PIRATAGE créé : {table_name}"
        )

        return table_name

    finally:
        cur.close()


# ============================================================================
# CONSTRUCTION DU TEXTE
# ============================================================================

def construire_texte(row: Dict[str, Any]) -> str:
    """
    Construit le texte envoyé au moteur de classification.
    """

    titre = valeur_str(row.get("titre"), "")
    description = valeur_str(
        row.get("description"),
        ""
    )

    raw_data = securiser_raw_data(
        row.get("raw_data")
    )

    morceaux = []

    if titre:
        morceaux.append(titre)

    if description:
        morceaux.append(description)

    if raw_data:

        try:
            morceaux.append(
                json.dumps(
                    raw_data,
                    ensure_ascii=False
                )
            )

        except Exception:
            pass

    return " ".join(morceaux).strip()


# ============================================================================
# SCORE CVSS
# ============================================================================

def extraire_score_cvss(
    row: Dict[str, Any]
) -> Optional[float]:

    raw_data = securiser_raw_data(
        row.get("raw_data")
    )

    if not raw_data:
        return None

    candidats = [

        raw_data.get("cvss"),
        raw_data.get("cvss_score"),
        raw_data.get("baseScore"),

        raw_data.get("cvss_v3"),
        raw_data.get("cvss_v31"),
        raw_data.get("cvss_v30"),

        raw_data.get("score"),
    ]

    for valeur in candidats:

        if valeur is None:
            continue

        try:

            score = float(valeur)

            if 0 <= score <= 10:
                return score

        except (ValueError, TypeError):
            continue

    return None


# ============================================================================
# PREUVES - VERSION ROBUSTE
# ============================================================================

def formater_preuves(
    preuves: Any,
    max_items: int = 5
) -> str:
    """
    Formate une liste de preuves pour l'affichage.
    Gère les cas où preuves n'est pas une liste.
    """
    if not preuves:
        return "aucune"

    # Si c'est une liste, on la formate
    if isinstance(preuves, list):
        return ", ".join(map(str, preuves[:max_items]))

    # Si c'est une chaîne, on la retourne telle quelle
    if isinstance(preuves, str):
        return preuves

    # Si c'est autre chose (dict, etc.), on le convertit en chaîne
    return str(preuves)


# ============================================================================
# AFFICHAGE
# ============================================================================

def afficher_classification(
    row: Dict[str, Any],
    resultat: Dict[str, Any],
    ancien_type: str,
    ancien_secteur: str,
    ancienne_severite: str,
    ancien_risque: int
) -> None:

    methode = resultat.get(
        "methode_classification_menace",
        "INCONNU"
    )

    accord = resultat.get(
        "accord_regles_ml",
        False
    )

    if "ML" in methode and "RULE" in methode:
        icone = "🔄"

    elif "ML" in methode:
        icone = "🤖"

    elif "RULE" in methode:
        icone = "📋"

    else:
        icone = "❓"

    print()

    print(
        f"{icone} [ID {row['id']}] "
        f"{ancien_type} -> "
        f"{resultat.get('type_menace', 'INCONNU')}"
    )

    print(
        f"    Source : "
        f"{row.get('source') or 'INCONNU'}"
    )

    print(
        f"    Méthode : {methode} "
        f"{'✅ ACCORD' if accord else '⚠️ DÉSACCORD'}"
    )

    print(
        f"    Règles : "
        f"{resultat.get('prediction_regles_menace', 'INCONNU')} "
        f"({resultat.get('confiance_regles_menace', 0.0):.3f})"
    )

    print(
        f"    ML : "
        f"{resultat.get('prediction_ml_menace', 'INCONNU')} "
        f"({resultat.get('confiance_ml_menace', 0.0):.3f})"
    )

    print(
        f"    Secteur : "
        f"{ancien_secteur} -> "
        f"{resultat.get('secteur_cible', 'INCONNU')} "
        f"({resultat.get('confiance_secteur', 0.0):.3f})"
    )

    print(
        f"    Sévérité : "
        f"{ancienne_severite} -> "
        f"{resultat.get('severite', 'INCONNU')} "
        f"({resultat.get('confiance_severite', 0.0):.3f})"
    )

    print(
        f"    Confiance globale : "
        f"{resultat.get('confiance_globale', 0.0):.3f} "
        f"({resultat.get('niveau_confiance', 'INCONNU')})"
    )

    print(
        f"    Risque : "
        f"{ancien_risque} -> "
        f"{resultat.get('risque', 0)}/100 "
        f"({niveau_risque(resultat.get('risque', 0))})"  # ✅ Utilise la fonction importée
    )

    # Récupération sécurisée des preuves
    preuves = resultat.get('preuves', {})

    # Si preuves est un dictionnaire, on récupère 'menace'
    if isinstance(preuves, dict):
        preuves_menace = preuves.get('menace', [])
    else:
        # Si preuves n'est pas un dict, on l'utilise directement
        preuves_menace = preuves

    print(
        f"    Preuves menace : "
        f"{formater_preuves(preuves_menace)}"
    )


# ============================================================================
# STATISTIQUES
# ============================================================================

def afficher_statistiques_methodes(
    methodes: Dict[str, int],
    total: int
) -> None:

    print()
    print("=" * 100)
    print("STATISTIQUES DES MÉTHODES DE CLASSIFICATION")
    print("=" * 100)

    ordre = [
        "HYBRIDE_RULES_ML",
        "ML_LinearSVC",
        "ML_LinearSVC_PRIORITY",
        "RULE_BASED",
        "RULE_BASED_PRIORITY",
        "none",
    ]

    for methode in ordre:

        if methode in methodes:

            count = methodes[methode]

            pct = (
                count * 100 / total
                if total
                else 0
            )

            print(
                f"    {methode:<30}"
                f"{count:>6} "
                f"({pct:>5.1f}%)"
            )

    for methode, count in sorted(
        methodes.items()
    ):

        if methode in ordre:
            continue

        pct = (
            count * 100 / total
            if total
            else 0
        )

        print(
            f"    {methode:<30}"
            f"{count:>6} "
            f"({pct:>5.1f}%)"
        )

    print("=" * 100)


# ============================================================================
# TABLEAU SOURCE × CATEGORIE
# ============================================================================

def afficher_tableau_sources(
    sources: Dict[str, Dict[str, int]]
) -> None:

    if not sources:
        print("⚠️ Aucune donnée à afficher.")
        return

    categories = set()

    for data in sources.values():
        categories.update(data.keys())

    # ✅ CORRECTION: CHEVAL_TROIE au lieu de CHEVAL_DE_TROIE
    ordre_categories = [
        "PIRATAGE",
        "RANSOMWARE",
        "MALWARE",
        "PHISHING",
        "VULNERABILITE",
        "EXPLOITATION",
        "FUITE_DONNEES",
        "CHEVAL_TROIE",      # ✅ Corrigé
        "SPYWARE",
        "BOTNET",
        "DDOS",
        "COMPROMISSION_COMPTE",
        "VOL_IDENTIFIANTS",
        "DEFAÇAGE",
        "CRYPTOJACKING",
        "INGENIERIE_SOCIALE",
        "SPOOFING",
        "VIRUS",
        "INCIDENT",
        "INCONNU",
    ]

    categories_triees = [
        c for c in ordre_categories
        if c in categories
    ]

    for c in sorted(categories):

        if c not in categories_triees:
            categories_triees.append(c)

    print()
    print("=" * 100)
    print("TABLEAU SOURCE × CATÉGORIE")
    print("=" * 100)

    print(
        f"{'Source':<25}",
        end=""
    )

    for cat in categories_triees:
        print(
            f"{cat[:14]:<15}",
            end=""
        )

    print("TOTAL")

    print(
        "-" * (
            25 +
            15 * len(categories_triees) +
            8
        )
    )

    totals = {
        cat: 0
        for cat in categories_triees
    }

    total_global = 0

    for source in sorted(sources):

        print(
            f"{source[:25]:<25}",
            end=""
        )

        total_source = 0

        for cat in categories_triees:

            nb = sources[source].get(
                cat,
                0
            )

            print(
                f"{nb:<15}",
                end=""
            )

            total_source += nb
            totals[cat] += nb

        print(total_source)

        total_global += total_source

    print(
        "-" * (
            25 +
            15 * len(categories_triees) +
            8
        )
    )

    print(
        f"{'TOTAL':<25}",
        end=""
    )

    for cat in categories_triees:
        print(
            f"{totals[cat]:<15}",
            end=""
        )

    print(total_global)

    print("=" * 100)


# ============================================================================
# RECOMPUTE
# ============================================================================

def recompute(
    apply: bool = False,
    seuil: float = DEFAULT_THRESHOLD,
    force: bool = False
) -> None:

    conn = psycopg2.connect(
        **DB_CONFIG
    )

    cur = None

    try:

        # ====================================================================
        # HEADER
        # ====================================================================

        print()
        print("=" * 100)
        print("RECLASSIFICATION DES PIRATAGE")
        print("=" * 100)

        print()
        print(
            f"Mode : "
            f"{'APPLICATION' if apply else 'DRY-RUN'}"
        )

        print(
            f"Seuil : {seuil}"
        )

        print(
            f"Forcer : "
            f"{'OUI' if force else 'NON'}"
        )

        print(
            f"Version modèle : {MODEL_VERSION}"
        )

        # ====================================================================
        # STATUT ML
        # ====================================================================

        ml_status = get_ml_classifier_status()

        print()
        print("STATUT DU MOTEUR ML")
        print("-" * 50)

        print(
            f"Activé     : {ml_status.get('enabled')}"
        )

        print(
            f"Disponible : {ml_status.get('available')}"
        )

        print(
            f"Chargé     : {ml_status.get('loaded')}"
        )

        print(
            f"Classes    : "
            f"{len(ml_status.get('classes', []))}"
        )

        if ml_status.get("error"):
            print(
                f"Erreur     : "
                f"{ml_status['error']}"
            )

        # ====================================================================
        # MIGRATION
        # ====================================================================

        print()
        print("Vérification du schéma...")

        ajouter_colonnes(conn)
        creer_historique(conn)

        # ====================================================================
        # BACKUP
        # ====================================================================

        backup = None

        if apply:

            print()
            print("Création du backup...")

            backup = creer_backup(conn)

        # ====================================================================
        # SELECTION
        # ====================================================================

        cur = conn.cursor(
            cursor_factory=RealDictCursor
        )

        query = """
            SELECT
                id,
                titre,
                description,
                source,
                raw_data,

                type_menace,
                secteur_cible,
                severite,

                confiance_type,
                confiance_secteur,
                confiance_severite,
                confiance_globale,

                risque,

                classification_method

            FROM cyber_incidents

            WHERE UPPER(
                COALESCE(type_menace, '')
            ) = 'PIRATAGE'
        """

        if not force:

            query += """
                AND (
                    classification_method IS NULL

                    OR classification_method NOT IN (
                        'HYBRIDE_RULES_ML',
                        'RULES_ML_PIRATAGE_V4',
                        'RULES_PIRATAGE_V3'
                    )
                )
            """

        query += """
            ORDER BY id
        """

        cur.execute(query)

        rows = cur.fetchall()

        print()
        print(
            f"PIRATAGE trouvés : {len(rows)}"
        )

        # ====================================================================
        # STATISTIQUES
        # ====================================================================

        stats_menaces = {}
        stats_methodes = {}
        stats_sources = {}

        total_analyses = 0
        total_modifications = 0
        total_type_changes = 0
        total_metadata_changes = 0
        total_inconnus = 0
        total_errors = 0

        ml_used = 0
        rules_used = 0
        hybrid_used = 0

        # ====================================================================
        # BOUCLE
        # ====================================================================

        for idx, row in enumerate(
            rows,
            1
        ):

            incident_id = row["id"]

            try:

                if idx % 100 == 0:

                    print(
                        f"Progression : "
                        f"{idx}/{len(rows)}"
                    )

                texte = construire_texte(row)

                # ------------------------------------------------------------
                # TEXTE INSUFFISANT
                # ------------------------------------------------------------

                if len(texte.strip()) < 5:

                    total_inconnus += 1

                    stats_menaces["INCONNU"] = (
                        stats_menaces.get(
                            "INCONNU",
                            0
                        ) + 1
                    )

                    source = (
                        row.get("source")
                        or "INCONNU"
                    )

                    stats_sources.setdefault(
                        source,
                        {}
                    )

                    stats_sources[source]["INCONNU"] = (
                        stats_sources[source].get(
                            "INCONNU",
                            0
                        ) + 1
                    )

                    continue

                total_analyses += 1

                # ------------------------------------------------------------
                # ANCIENNES VALEURS
                # ------------------------------------------------------------

                ancien_type = valeur_str(
                    row.get("type_menace"),
                    "PIRATAGE"
                )

                ancien_secteur = valeur_str(
                    row.get("secteur_cible")
                )

                ancienne_severite = valeur_str(
                    row.get("severite")
                )

                ancien_risque = (
                    row.get("risque")
                    if row.get("risque") is not None
                    else 0
                )

                # ------------------------------------------------------------
                # CVSS
                # ------------------------------------------------------------

                score_cvss = extraire_score_cvss(
                    row
                )

                # ------------------------------------------------------------
                # CLASSIFICATION
                # ------------------------------------------------------------

                resultat = classifier_cyber_complet(

                    titre=row.get("titre") or "",

                    description=(
                        row.get("description")
                        or ""
                    ),

                    raw_data=securiser_raw_data(
                        row.get("raw_data")
                    ),

                    score_cvss=score_cvss,

                    seuil_confiance=seuil
                )

                # ------------------------------------------------------------
                # NORMALISATION
                # ------------------------------------------------------------

                categorie = (
                    normaliser_pour_stockage_menace(
                        resultat.get(
                            "type_menace",
                            "INCONNU"
                        )
                    )
                )

                secteur = (
                    normaliser_pour_stockage_secteur(
                        resultat.get(
                            "secteur_cible",
                            "INCONNU"
                        )
                    )
                )

                severite = (
                    normaliser_pour_stockage_severite(
                        resultat.get(
                            "severite",
                            "INCONNU"
                        )
                    )
                )

                risque_nouveau = int(
                    resultat.get(
                        "risque",
                        0
                    ) or 0
                )

                # ------------------------------------------------------------
                # MÉTHODE
                # ------------------------------------------------------------

                methode = resultat.get(
                    "methode_classification_menace",
                    "none"
                )

                stats_methodes[methode] = (
                    stats_methodes.get(
                        methode,
                        0
                    ) + 1
                )

                if (
                    "ML" in methode
                    and "RULE" in methode
                ):
                    hybrid_used += 1

                elif "ML" in methode:
                    ml_used += 1

                elif "RULE" in methode:
                    rules_used += 1

                # ------------------------------------------------------------
                # STATISTIQUES MENACES
                # ------------------------------------------------------------

                stats_menaces[categorie] = (
                    stats_menaces.get(
                        categorie,
                        0
                    ) + 1
                )

                source = (
                    row.get("source")
                    or "INCONNU"
                )

                stats_sources.setdefault(
                    source,
                    {}
                )

                stats_sources[source][categorie] = (
                    stats_sources[source].get(
                        categorie,
                        0
                    ) + 1
                )

                # ------------------------------------------------------------
                # COMPARAISON
                # ------------------------------------------------------------

                changement_type = (
                    normaliser_comparaison(
                        categorie
                    )
                    != normaliser_comparaison(
                        ancien_type
                    )
                )

                changement_secteur = (
                    normaliser_comparaison(
                        secteur
                    )
                    != normaliser_comparaison(
                        ancien_secteur
                    )
                )

                changement_severite = (
                    normaliser_comparaison(
                        severite
                    )
                    != normaliser_comparaison(
                        ancienne_severite
                    )
                )

                changement_risque = (
                    risque_nouveau
                    != int(ancien_risque or 0)
                )

                # ------------------------------------------------------------
                # MÉTADONNÉES
                # ------------------------------------------------------------

                ancienne_confiance_globale = (
                    row.get(
                        "confiance_globale"
                    )
                )

                nouvelle_confiance_globale = (
                    resultat.get(
                        "confiance_globale",
                        0.0
                    )
                )

                changement_metadata = (
                    ancienne_confiance_globale is None
                    or abs(
                        float(
                            ancienne_confiance_globale
                        )
                        -
                        float(
                            nouvelle_confiance_globale
                        )
                    ) > 1e-6
                    or row.get(
                        "classification_method"
                    ) != CLASSIFICATION_METHOD
                )

                changement = (
                    changement_type
                    or changement_secteur
                    or changement_severite
                    or changement_risque
                    or changement_metadata
                )

                if changement:
                    total_modifications += 1

                if (
                    changement_type
                    or changement_secteur
                    or changement_severite
                    or changement_risque
                ):
                    total_type_changes += 1

                if changement_metadata:
                    total_metadata_changes += 1

                # ------------------------------------------------------------
                # AFFICHAGE
                # ------------------------------------------------------------

                if changement or idx <= 10:

                    afficher_classification(
                        row,
                        resultat,
                        ancien_type,
                        ancien_secteur,
                        ancienne_severite,
                        ancien_risque
                    )

                # ------------------------------------------------------------
                # DRY-RUN
                # ------------------------------------------------------------

                if not apply:
                    continue

                # ============================================================
                # SAVEPOINT
                # ============================================================

                savepoint = (
                    f"incident_{incident_id}"
                )

                cur.execute(
                    f"SAVEPOINT {savepoint}"
                )

                try:

                    # ========================================================
                    # CONSERVATION DE L'ÉTAT ORIGINAL
                    # ========================================================

                    #
                    # IMPORTANT :
                    # On ne remplit ancien_* que si ces champs
                    # sont encore NULL.
                    #
                    cur.execute(
                        """
                        UPDATE cyber_incidents
                        SET
                            ancien_type_menace =
                                COALESCE(
                                    ancien_type_menace,
                                    %s
                                ),

                            ancien_secteur =
                                COALESCE(
                                    ancien_secteur,
                                    %s
                                ),

                            ancienne_severite =
                                COALESCE(
                                    ancienne_severite,
                                    %s
                                ),

                            ancien_risque =
                                COALESCE(
                                    ancien_risque,
                                    %s
                                )

                        WHERE id = %s
                        """,
                        (
                            ancien_type,
                            ancien_secteur,
                            ancienne_severite,
                            ancien_risque,
                            incident_id
                        )
                    )

                    # ========================================================
                    # UPDATE CLASSIFICATION
                    # ========================================================

                    cur.execute(
                        """
                        UPDATE cyber_incidents

                        SET

                            type_menace = %s,
                            secteur_cible = %s,
                            severite = %s,

                            confiance_type = %s,
                            confiance_secteur = %s,
                            confiance_severite = %s,
                            confiance_globale = %s,

                            niveau_confiance_type = %s,
                            niveau_confiance_secteur = %s,
                            niveau_confiance_severite = %s,

                            classification_method = %s,
                            classification_model = %s,

                            preuves_menace = %s,
                            preuves_secteur = %s,
                            preuves_severite = %s,

                            risque = %s,
                            niveau_risque = %s,

                            prediction_ml = %s,
                            confiance_ml = %s,

                            prediction_regles = %s,
                            confiance_regles = %s,

                            accord_regles_ml = %s,
                            methode_menace = %s,

                            updated_at = NOW()

                        WHERE id = %s
                        """,
                        (

                            categorie,
                            secteur,
                            severite,

                            resultat.get(
                                "confiance_menace",
                                0.0
                            ),

                            resultat.get(
                                "confiance_secteur",
                                0.0
                            ),

                            resultat.get(
                                "confiance_severite",
                                0.0
                            ),

                            resultat.get(
                                "confiance_globale",
                                0.0
                            ),

                            niveau_confiance(
                                resultat.get(
                                    "confiance_menace",
                                    0.0
                                )
                            ),

                            niveau_confiance(
                                resultat.get(
                                    "confiance_secteur",
                                    0.0
                                )
                            ),

                            niveau_confiance(
                                resultat.get(
                                    "confiance_severite",
                                    0.0
                                )
                            ),

                            CLASSIFICATION_METHOD,

                            MODEL_VERSION,

                            resultat.get(
                                "preuves",
                                {}
                            ).get(
                                "menace",
                                []
                            ),

                            resultat.get(
                                "preuves",
                                {}
                            ).get(
                                "secteur",
                                []
                            ),

                            resultat.get(
                                "preuves",
                                {}
                            ).get(
                                "severite",
                                []
                            ),

                            risque_nouveau,

                            niveau_risque(
                                risque_nouveau
                            ),

                            resultat.get(
                                "prediction_ml_menace",
                                "INCONNU"
                            ),

                            resultat.get(
                                "confiance_ml_menace",
                                0.0
                            ),

                            resultat.get(
                                "prediction_regles_menace",
                                "INCONNU"
                            ),

                            resultat.get(
                                "confiance_regles_menace",
                                0.0
                            ),

                            resultat.get(
                                "accord_regles_ml",
                                False
                            ),

                            methode,

                            incident_id
                        )
                    )

                    # ========================================================
                    # HISTORIQUE
                    # ========================================================

                    #
                    # On conserve UNE trace de chaque reclassification
                    # effectivement appliquée.
                    #

                    if changement:

                        cur.execute(
                            """
                            INSERT INTO classification_history (

                                incident_id,

                                ancien_type,
                                ancien_secteur,
                                ancienne_severite,
                                ancien_risque,

                                nouveau_type,
                                nouveau_secteur,
                                nouvelle_severite,
                                nouveau_risque,

                                confiance_type,
                                confiance_secteur,
                                confiance_severite,
                                confiance_globale,

                                preuves_menace,
                                preuves_secteur,
                                preuves_severite,

                                methode_classification,
                                modele_version,
                                source,

                                prediction_ml,
                                confiance_ml,

                                prediction_regles,
                                confiance_regles,

                                accord_regles_ml

                            )

                            VALUES (

                                %s, %s, %s, %s, %s,

                                %s, %s, %s, %s,

                                %s, %s, %s, %s,

                                %s, %s, %s,

                                %s, %s, %s,

                                %s, %s,

                                %s, %s,

                                %s
                            )
                            """,
                            (

                                incident_id,

                                ancien_type,
                                ancien_secteur,
                                ancienne_severite,
                                ancien_risque,

                                categorie,
                                secteur,
                                severite,
                                risque_nouveau,

                                resultat.get(
                                    "confiance_menace",
                                    0.0
                                ),

                                resultat.get(
                                    "confiance_secteur",
                                    0.0
                                ),

                                resultat.get(
                                    "confiance_severite",
                                    0.0
                                ),

                                resultat.get(
                                    "confiance_globale",
                                    0.0
                                ),

                                resultat.get(
                                    "preuves",
                                    {}
                                ).get(
                                    "menace",
                                    []
                                ),

                                resultat.get(
                                    "preuves",
                                    {}
                                ).get(
                                    "secteur",
                                    []
                                ),

                                resultat.get(
                                    "preuves",
                                    {}
                                ).get(
                                    "severite",
                                    []
                                ),

                                CLASSIFICATION_METHOD,
                                MODEL_VERSION,

                                source,

                                resultat.get(
                                    "prediction_ml_menace",
                                    "INCONNU"
                                ),

                                resultat.get(
                                    "confiance_ml_menace",
                                    0.0
                                ),

                                resultat.get(
                                    "prediction_regles_menace",
                                    "INCONNU"
                                ),

                                resultat.get(
                                    "confiance_regles_menace",
                                    0.0
                                ),

                                resultat.get(
                                    "accord_regles_ml",
                                    False
                                ),
                            )
                        )

                    cur.execute(
                        f"RELEASE SAVEPOINT {savepoint}"
                    )

                except Exception:

                    cur.execute(
                        f"ROLLBACK TO SAVEPOINT {savepoint}"
                    )

                    raise

            except Exception as e:

                total_errors += 1

                logger.exception(
                    f"Erreur classification "
                    f"incident {incident_id}: {e}"
                )

                print(
                    f"\n❌ ERREUR ID {incident_id}: {e}"
                )

                # En mode apply, la transaction principale
                # reste utilisable grâce au SAVEPOINT.

                continue

        # ====================================================================
        # COMMIT / ROLLBACK
        # ====================================================================

        if apply:

            conn.commit()

            print()
            print(
                "✅ Modifications enregistrées."
            )

        else:

            #
            # IMPORTANT :
            # Aucun commit n'a été fait pendant le traitement.
            #

            conn.rollback()

            print()
            print(
                "ℹ️ DRY-RUN : aucune modification enregistrée."
            )

        # ====================================================================
        # RESUME
        # ====================================================================

        print()
        print("=" * 100)
        print("RÉSUMÉ DE LA RECLASSIFICATION")
        print("=" * 100)

        print()
        print(
            f"PIRATAGE examinés       : {len(rows)}"
        )

        print(
            f"Incidents analysés      : {total_analyses}"
        )

        print(
            f"Modifications détectées : "
            f"{total_modifications}"
        )

        print(
            f"Changements classification : "
            f"{total_type_changes}"
        )

        print(
            f"Changements métadonnées : "
            f"{total_metadata_changes}"
        )

        print(
            f"INCONNU / texte insuffisant : "
            f"{total_inconnus}"
        )

        print(
            f"Erreurs                 : "
            f"{total_errors}"
        )

        print()
        print(
            f"ML                      : "
            f"{ml_used}"
        )

        print(
            f"Règles                  : "
            f"{rules_used}"
        )

        print(
            f"Hybride                 : "
            f"{hybrid_used}"
        )

        # ====================================================================
        # DISTRIBUTION
        # ====================================================================

        print()
        print(
            "DISTRIBUTION DES NOUVELLES CATÉGORIES"
        )

        print()

        total_stats = sum(
            stats_menaces.values()
        )

        for categorie, nombre in sorted(
            stats_menaces.items(),
            key=lambda x: x[1],
            reverse=True
        ):

            pct = (
                nombre * 100 / total_stats
                if total_stats
                else 0
            )

            print(
                f"    {categorie:<30}"
                f"{nombre:>6} "
                f"({pct:>5.1f}%)"
            )

        # ====================================================================
        # METHODES
        # ====================================================================

        afficher_statistiques_methodes(
            stats_methodes,
            total_analyses
        )

        # ====================================================================
        # SOURCE × CATEGORIE
        # ====================================================================

        afficher_tableau_sources(
            stats_sources
        )

        # ====================================================================
        # BACKUP
        # ====================================================================

        if backup:

            print()
            print(
                f"💾 Backup créé : {backup}"
            )

            print()
            print(
                "⚠️ Conserver ce backup jusqu'à "
                "validation complète des résultats."
            )

        # ====================================================================
        # FIN
        # ====================================================================

        print()
        print("=" * 100)

        if apply:
            print(
                "✅ RECLASSIFICATION TERMINÉE"
            )
        else:
            print(
                "ℹ️ SIMULATION TERMINÉE"
            )

        print("=" * 100)

    except Exception as e:

        conn.rollback()

        logger.exception(
            f"Erreur critique : {e}"
        )

        print()
        print(
            f"❌ ERREUR CRITIQUE : {e}"
        )

        raise

    finally:

        if cur is not None:

            try:
                cur.close()
            except Exception:
                pass

        try:
            conn.close()
        except Exception:
            pass


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description=(
            "Reclassification des anciens PIRATAGE "
            "avec le moteur central Rules + ML."
        )
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Applique réellement les modifications "
            "dans PostgreSQL."
        )
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Reclasse tous les PIRATAGE, "
            "y compris ceux déjà traités."
        )
    )

    parser.add_argument(
        "--seuil",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=(
            f"Seuil de confiance "
            f"(défaut : {DEFAULT_THRESHOLD})."
        )
    )

    args = parser.parse_args()

    if not 0.0 <= args.seuil <= 1.0:

        parser.error(
            "Le seuil doit être compris entre 0.0 et 1.0."
        )

    recompute(
        apply=args.apply,
        seuil=args.seuil,
        force=args.force
    )