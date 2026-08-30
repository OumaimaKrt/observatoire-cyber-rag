#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================================
utils/classifiers.py
============================================================================

MOTEUR CENTRAL DE CLASSIFICATION CYBER

Architecture :
    1. Classification par règles
    2. Classification ML LinearSVC
    3. Fusion hybride Règles + ML
    4. Calcul de confiance
    5. Classification secteur
    6. Classification sévérité
    7. Calcul du risque
    8. Normalisation pour PostgreSQL

VERSION : 5.2 - COMPLETE
============================================================================
"""

import os
import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

import joblib
import numpy as np


# ============================================================================
# CONFIGURATION
# ============================================================================

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

MODEL_PATH = os.path.join(
    PROJECT_ROOT,
    "models",
    "threat_classifier",
    "best_threat_classifier.joblib"
)


# ============================================================================
# CLASSES OFFICIELLES
# ============================================================================

CLASSES_ML = [
    "CHEVAL_TROIE",
    "DDOS",
    "EXPLOITATION",
    "FUITE_DONNEES",
    "MALWARE",
    "PHISHING",
    "PIRATAGE",
    "RANSOMWARE",
    "SPYWARE",
    "VULNERABILITE",
]


# Classes métier supplémentaires pouvant être reconnues par les règles.
# Elles ne doivent PAS être produites par le modèle ML si elles ne sont
# pas présentes dans ses classes.
CLASSES_METIER = [
    "PIRATAGE",
    "VULNERABILITE",
    "DDOS",
    "RANSOMWARE",
    "FUITE_DONNEES",
    "CHEVAL_TROIE",
    "PHISHING",
    "SPYWARE",
    "MALWARE",
    "EXPLOITATION",
    "INGENIERIE_SOCIALE",
    "BOTNET",
    "COMPROMISSION_COMPTE",
    "VOL_IDENTIFIANTS",
    "DEFAÇAGE",
    "CRYPTOJACKING",
    "SPOOFING",
    "VIRUS",
    "KEYLOGGER",
    "SPAM",
    "VER_INFORMATIQUE",
    "ESCROQUERIE_PAIEMENT",
    "INCIDENT",
    "INCONNU",
]


# ============================================================================
# PARAMÈTRES
# ============================================================================

DEFAULT_CONFIDENCE_THRESHOLD = 0.35

MODEL_VERSION = "LinearSVC_10_CLASSES"

RULE_STRONG_THRESHOLD = 0.70
RULE_MEDIUM_THRESHOLD = 0.45

ML_STRONG_THRESHOLD = 0.60
ML_MEDIUM_THRESHOLD = 0.35


# ============================================================================
# CACHE DU MODÈLE
# ============================================================================

_ML_MODEL = None
_ML_LOAD_ERROR = None


# ============================================================================
# NORMALISATION TEXTE
# ============================================================================

def normaliser_texte(texte: Any) -> str:
    """
    Normalise un texte pour la classification.
    Supporte FR / EN / AR.
    """

    if texte is None:
        return ""

    if not isinstance(texte, str):
        try:
            texte = str(texte)
        except Exception:
            return ""

    texte = texte.strip()

    if not texte:
        return ""

    # Espaces multiples
    texte = re.sub(r"\s+", " ", texte)

    return texte.lower()


# ============================================================================
# CONSTRUCTION DU TEXTE GLOBAL
# ============================================================================

def construire_texte_global(
    titre: str = "",
    description: str = "",
    raw_data: Optional[Dict[str, Any]] = None
) -> str:
    """
    Construit le texte utilisé par le moteur ML.
    """

    morceaux = []

    if titre:
        morceaux.append(str(titre))

    if description:
        morceaux.append(str(description))

    if raw_data:

        try:
            if isinstance(raw_data, dict):

                champs_prioritaires = [
                    "title",
                    "description",
                    "summary",
                    "details",
                    "name",
                    "category",
                    "type",
                    "threat",
                    "attack",
                    "attack_type",
                    "malware",
                    "family",
                    "cve",
                    "cwe",
                    "impact",
                    "tags",
                    "source"
                ]

                for champ in champs_prioritaires:

                    valeur = raw_data.get(champ)

                    if valeur:
                        morceaux.append(str(valeur))

                try:
                    morceaux.append(
                        json.dumps(
                            raw_data,
                            ensure_ascii=False,
                            default=str
                        )
                    )
                except Exception:
                    pass

        except Exception:
            pass

    return " ".join(morceaux).strip()


# ============================================================================
# CHARGEMENT DU MODÈLE ML
# ============================================================================

def charger_modele_ml():
    """
    Charge le modèle LinearSVC une seule fois.
    """

    global _ML_MODEL
    global _ML_LOAD_ERROR

    if _ML_MODEL is not None:
        return _ML_MODEL

    if _ML_LOAD_ERROR is not None:
        return None

    if not os.path.exists(MODEL_PATH):

        _ML_LOAD_ERROR = (
            f"Modèle introuvable : {MODEL_PATH}"
        )

        logger.warning(_ML_LOAD_ERROR)

        return None

    try:

        _ML_MODEL = joblib.load(MODEL_PATH)

        logger.info(
            "Modèle ML chargé : %s",
            MODEL_PATH
        )

        return _ML_MODEL

    except Exception as exc:

        _ML_LOAD_ERROR = str(exc)

        logger.exception(
            "Erreur chargement modèle ML"
        )

        return None


# ============================================================================
# STATUT DU MODÈLE
# ============================================================================

def get_ml_classifier_status() -> Dict[str, Any]:
    """
    Retourne le statut détaillé du classifieur ML.
    Compatible avec recompute_classification.py.
    """

    model = charger_modele_ml()

    if model is None:

        return {
            "enabled": True,
            "available": False,
            "loaded": False,
            "classes": [],
            "error": _ML_LOAD_ERROR
        }

    try:

        classes = list(
            getattr(model, "classes_", [])
        )

        classes = [
            str(c)
            for c in classes
        ]

        return {
            "enabled": True,
            "available": True,
            "loaded": True,
            "classes": classes,
            "error": None
        }

    except Exception as exc:

        return {
            "enabled": True,
            "available": True,
            "loaded": True,
            "classes": [],
            "error": str(exc)
        }


# ============================================================================
# PREDICTION ML
# ============================================================================

def classifier_ml_detaille(
    texte: str
) -> Dict[str, Any]:
    """
    Classification LinearSVC détaillée.

    Retourne :
        prediction
        confiance
        scores
        classes
    """

    model = charger_modele_ml()

    if model is None:

        return {
            "prediction": "INCONNU",
            "confiance": 0.0,
            "scores": {},
            "classes": [],
            "available": False
        }

    texte = texte or ""

    if not texte.strip():

        return {
            "prediction": "INCONNU",
            "confiance": 0.0,
            "scores": {},
            "classes": [],
            "available": True
        }

    try:

        prediction = model.predict([texte])[0]

        classes = list(
            getattr(model, "classes_", [])
        )

        classes = [
            str(c)
            for c in classes
        ]

        scores = {}

        if hasattr(model, "decision_function"):

            decision = model.decision_function([texte])

            decision = np.asarray(decision)

            if decision.ndim == 1:

                values = decision

            else:

                values = decision[0]

            for classe, score in zip(
                classes,
                values
            ):
                scores[classe] = float(score)

            if len(values) > 0:

                values = np.asarray(
                    values,
                    dtype=float
                )

                shifted = values - np.max(values)

                exp_values = np.exp(
                    np.clip(
                        shifted,
                        -50,
                        50
                    )
                )

                probabilities = (
                    exp_values /
                    np.sum(exp_values)
                )

                confidence_map = {
                    classe: float(prob)
                    for classe, prob in zip(
                        classes,
                        probabilities
                    )
                }

                confiance = confidence_map.get(
                    str(prediction),
                    0.0
                )

            else:

                confiance = 0.0

        else:

            confiance = 0.50

        return {
            "prediction": str(prediction),
            "confiance": float(confiance),
            "scores": scores,
            "classes": classes,
            "available": True
        }

    except Exception as exc:

        logger.exception(
            "Erreur classification ML"
        )

        return {
            "prediction": "INCONNU",
            "confiance": 0.0,
            "scores": {},
            "classes": [],
            "available": False,
            "error": str(exc)
        }


# ============================================================================
# RÈGLES — UTILITAIRES
# ============================================================================

def contient_un_des(
    texte: str,
    mots: List[str]
) -> bool:

    texte = normaliser_texte(texte)

    return any(
        mot.lower() in texte
        for mot in mots
    )


def compter_occurrences(
    texte: str,
    mots: List[str]
) -> int:

    texte = normaliser_texte(texte)

    return sum(
        texte.count(mot.lower())
        for mot in mots
    )


# ============================================================================
# CLASSIFICATION PAR RÈGLES
# ============================================================================

def classifier_regles_detaille(
    texte: str
) -> Dict[str, Any]:
    """
    Classification déterministe par règles.

    Retourne :
        prediction
        confiance
        preuves
    """

    texte_original = texte or ""
    texte = normaliser_texte(texte_original)

    if len(texte) < 5:

        return {
            "prediction": "INCONNU",
            "confiance": 0.0,
            "preuves": []
        }

    scores: Dict[str, float] = {}
    preuves: Dict[str, List[str]] = {}

    def ajouter(
        classe: str,
        poids: float,
        preuve: str
    ):

        scores[classe] = (
            scores.get(classe, 0.0)
            + poids
        )

        preuves.setdefault(
            classe,
            []
        ).append(preuve)

    # ========================================================================
    # RANSOMWARE
    # ========================================================================

    mots = [
        "ransomware",
        "rançongiciel",
        "ransom",
        "ransom note",
        "encrypted files",
        "fichiers chiffrés",
        "fichiers cryptés",
        "demande de rançon",
        "demande rançon",
        "lockbit",
        "blackcat",
        "alphv",
        "clop",
        "revil",
        "conti",
        "ryuk",
        "wannacry",
        "akira",
        "play ransomware"
    ]

    for mot in mots:

        if mot in texte:

            ajouter(
                "RANSOMWARE",
                1.0,
                f"ransomware:{mot}"
            )

    # ========================================================================
    # DDOS
    # ========================================================================

    mots = [
        "ddos",
        "denial of service",
        "distributed denial",
        "attaque par déni de service",
        "déni de service distribué",
        "trafic massif",
        "flood attack",
        "syn flood",
        "udp flood",
        "http flood"
    ]

    for mot in mots:

        if mot in texte:

            ajouter(
                "DDOS",
                1.0,
                f"ddos:{mot}"
            )

    # ========================================================================
    # PHISHING
    # ========================================================================

    mots = [
        "phishing",
        "hameçonnage",
        "hameconnage",
        "spear phishing",
        "email fraud",
        "fraudulent email",
        "fake login",
        "fausse page de connexion",
        "page de connexion frauduleuse",
        "credential harvesting",
        "vol d'identifiants",
        "vol des identifiants"
    ]

    for mot in mots:

        if mot in texte:

            ajouter(
                "PHISHING",
                1.0,
                f"phishing:{mot}"
            )

    # ========================================================================
    # FUITE DE DONNÉES
    # ========================================================================

    mots = [
        "data breach",
        "data leak",
        "database leak",
        "information leak",
        "fuite de données",
        "fuite des données",
        "données volées",
        "donnees volees",
        "stolen data",
        "exfiltration",
        "exfiltrated data",
        "exfiltration de données"
    ]

    for mot in mots:

        if mot in texte:

            ajouter(
                "FUITE_DONNEES",
                1.0,
                f"fuite_donnees:{mot}"
            )

    # ========================================================================
    # MALWARE
    # ========================================================================

    mots = [
        "malware",
        "maliciel",
        "malicious software",
        "trojan",
        "trojan horse",
        "cheval de troie",
        "virus",
        "worm",
        "ver informatique",
        "botnet",
        "backdoor",
        "rootkit",
        "payload malveillant",
        "malicious payload"
    ]

    for mot in mots:

        if mot in texte:

            ajouter(
                "MALWARE",
                0.75,
                f"malware:{mot}"
            )

    # ========================================================================
    # CHEVAL DE TROIE
    # ========================================================================

    mots = [
        "trojan",
        "trojan horse",
        "cheval de troie",
        "remote access trojan",
        "rat malware",
        "rat trojan"
    ]

    for mot in mots:

        if mot in texte:

            ajouter(
                "CHEVAL_TROIE",
                1.2,
                f"trojan:{mot}"
            )

    # ========================================================================
    # SPYWARE
    # ========================================================================

    mots = [
        "spyware",
        "logiciel espion",
        "keylogger",
        "keylogging",
        "surveillance malware",
        "stalkerware",
        "information stealer",
        "infostealer"
    ]

    for mot in mots:

        if mot in texte:

            ajouter(
                "SPYWARE",
                1.0,
                f"spyware:{mot}"
            )

    # ========================================================================
    # EXPLOITATION / CVE
    # ========================================================================

    mots = [
        "exploit",
        "exploitation",
        "exploited",
        "vulnerability exploited",
        "remote code execution",
        "rce",
        "zero-day",
        "zero day",
        "preuve de concept",
        "proof of concept",
        "poc",
        "arbitrary code execution"
    ]

    for mot in mots:

        if mot in texte:

            ajouter(
                "EXPLOITATION",
                0.90,
                f"exploitation:{mot}"
            )

    # ========================================================================
    # VULNERABILITE
    # ========================================================================

    mots = [
        "cve-",
        "cwe-",
        "vulnerability",
        "vulnerable",
        "vulnérabilité",
        "vulnerabilite",
        "security flaw",
        "security vulnerability",
        "faille de sécurité",
        "faille",
        "patch",
        "security update",
        "mise à jour de sécurité",
        "mise a jour de securite",
        "cvss"
    ]

    for mot in mots:

        if mot in texte:

            ajouter(
                "VULNERABILITE",
                0.75,
                f"vulnerabilite:{mot}"
            )

    # ========================================================================
    # PIRATAGE
    # ========================================================================

    mots = [
        "hacked",
        "hacking",
        "hack",
        "piratage",
        "piraté",
        "pirate",
        "compromised",
        "compromise",
        "compromission",
        "intrusion",
        "unauthorized access",
        "accès non autorisé",
        "acces non autorise",
        "cyberattack",
        "cyber attack",
        "cyberattaque",
        "attaque informatique"
    ]

    for mot in mots:

        if mot in texte:

            ajouter(
                "PIRATAGE",
                0.70,
                f"piratage:{mot}"
            )

    # ========================================================================
    # INGENIERIE SOCIALE
    # ========================================================================

    mots = [
        "social engineering",
        "ingénierie sociale",
        "ingenierie sociale",
        "social engineering attack",
        "manipulation psychologique",
        "psychological manipulation"
    ]

    for mot in mots:

        if mot in texte:

            ajouter(
                "INGENIERIE_SOCIALE",
                1.0,
                f"ingenierie_sociale:{mot}"
            )

    # ========================================================================
    # SELECTION
    # ========================================================================

    if not scores:

        return {
            "prediction": "INCONNU",
            "confiance": 0.0,
            "preuves": []
        }

    priorite = [
        "RANSOMWARE",
        "DDOS",
        "PHISHING",
        "FUITE_DONNEES",
        "CHEVAL_TROIE",
        "SPYWARE",
        "EXPLOITATION",
        "VULNERABILITE",
        "MALWARE",
        "PIRATAGE",
        "INGENIERIE_SOCIALE"
    ]

    candidats = sorted(
        scores.items(),
        key=lambda x: (
            x[1],
            -priorite.index(x[0])
            if x[0] in priorite
            else -999
        ),
        reverse=True
    )

    prediction = candidats[0][0]
    score_max = candidats[0][1]

    total_score = sum(
        max(v, 0.0)
        for v in scores.values()
    )

    if total_score > 0:

        confiance = (
            score_max /
            total_score
        )

    else:

        confiance = 0.0

    nb_preuves = len(
        preuves.get(
            prediction,
            []
        )
    )

    if nb_preuves >= 3:

        confiance = min(
            0.98,
            confiance + 0.10
        )

    elif nb_preuves == 2:

        confiance = min(
            0.95,
            confiance + 0.05
        )

    return {
        "prediction": prediction,
        "confiance": float(
            min(
                max(
                    confiance,
                    0.0
                ),
                1.0
            )
        ),
        "preuves": preuves.get(
            prediction,
            []
        ),
        "scores": scores
    }


# ============================================================================
# CLASSIFICATION HYBRIDE MENACE
# ============================================================================

def classifier_menace_hybride(
    texte: str,
    seuil_confiance: float = DEFAULT_CONFIDENCE_THRESHOLD
) -> Dict[str, Any]:
    """
    Fusion Règles + ML.
    """

    rules = classifier_regles_detaille(
        texte
    )

    ml = classifier_ml_detaille(
        texte
    )

    rule_pred = rules["prediction"]
    rule_conf = float(
        rules["confiance"]
    )

    ml_pred = ml["prediction"]
    ml_conf = float(
        ml["confiance"]
    )

    ml_available = ml.get(
        "available",
        False
    )

    accord = (
        rule_pred != "INCONNU"
        and ml_pred != "INCONNU"
        and rule_pred == ml_pred
    )

    if accord:

        confiance = max(
            rule_conf,
            ml_conf
        )

        confiance = min(
            0.99,
            confiance + 0.10
        )

        methode = "HYBRIDE_RULES_ML"

        prediction = rule_pred

    elif (
        rule_pred != "INCONNU"
        and rule_conf >= RULE_STRONG_THRESHOLD
        and not ml_available
    ):

        prediction = rule_pred
        confiance = rule_conf
        methode = "RULE_BASED"

    elif (
        rule_pred != "INCONNU"
        and rule_conf >= RULE_STRONG_THRESHOLD
        and (
            ml_pred == "INCONNU"
            or ml_conf < ML_MEDIUM_THRESHOLD
        )
    ):

        prediction = rule_pred
        confiance = rule_conf
        methode = "RULE_BASED_PRIORITY"

    elif (
        ml_pred != "INCONNU"
        and ml_conf >= ML_STRONG_THRESHOLD
        and (
            rule_pred == "INCONNU"
            or rule_conf < RULE_MEDIUM_THRESHOLD
        )
    ):

        prediction = ml_pred
        confiance = ml_conf
        methode = "ML_LinearSVC"

    elif (
        rule_pred != "INCONNU"
        and ml_pred != "INCONNU"
    ):

        if rule_conf >= (
            ml_conf + 0.15
        ):

            prediction = rule_pred
            confiance = rule_conf
            methode = "RULE_BASED_PRIORITY"

        elif ml_conf >= (
            rule_conf + 0.15
        ):

            prediction = ml_pred
            confiance = ml_conf
            methode = "ML_LinearSVC_PRIORITY"

        else:

            prediction = ml_pred
            confiance = ml_conf
            methode = "ML_LinearSVC"

    elif rule_pred != "INCONNU":

        prediction = rule_pred
        confiance = rule_conf
        methode = "RULE_BASED"

    elif ml_pred != "INCONNU":

        prediction = ml_pred
        confiance = ml_conf
        methode = "ML_LinearSVC"

    else:

        prediction = "INCONNU"
        confiance = 0.0
        methode = "none"

    if (
        prediction != "INCONNU"
        and confiance < seuil_confiance
    ):

        if not (
            methode.startswith("RULE")
            and rule_conf >= RULE_STRONG_THRESHOLD
        ):

            prediction = "INCONNU"
            methode = "none"

    return {
        "prediction": prediction,
        "confiance": float(
            min(
                max(
                    confiance,
                    0.0
                ),
                1.0
            )
        ),

        "prediction_ml": ml_pred,
        "confiance_ml": ml_conf,

        "prediction_regles": rule_pred,
        "confiance_regles": rule_conf,

        "accord": accord,

        "methode": methode,

        "preuves": rules.get(
            "preuves",
            []
        ),

        "scores_ml": ml.get(
            "scores",
            {}
        )
    }


# ============================================================================
# CLASSIFICATION SECTEUR
# ============================================================================

def classifier_secteur(
    texte: str
) -> Tuple[str, float, List[str]]:

    texte = normaliser_texte(
        texte
    )

    secteurs = {

        "FINANCE": [
            "banque",
            "bank",
            "finance",
            "financial",
            "paiement",
            "payment",
            "assurance",
            "insurance",
            "fintech",
            "credit",
            "crédit"
        ],

        "SANTE": [
            "hôpital",
            "hopital",
            "hospital",
            "health",
            "healthcare",
            "santé",
            "sante",
            "clinic",
            "clinique",
            "patient",
            "medical",
            "médical"
        ],

        "EDUCATION": [
            "université",
            "universite",
            "university",
            "school",
            "école",
            "ecole",
            "education",
            "étudiant",
            "etudiant",
            "student"
        ],

        "ADMINISTRATION": [
            "government",
            "gouvernement",
            "ministère",
            "ministere",
            "administration",
            "public sector",
            "secteur public",
            "municipality",
            "mairie"
        ],

        "TELECOM": [
            "telecom",
            "télécom",
            "telecommunication",
            "5g",
            "4g",
            "operator",
            "opérateur",
            "network operator"
        ],

        "INDUSTRIE": [
            "industry",
            "industrie",
            "industrial",
            "manufacturing",
            "usine",
            "factory",
            "production"
        ],

        "ENERGIE": [
            "energy",
            "énergie",
            "energie",
            "electricity",
            "électricité",
            "electricite",
            "power grid",
            "oil",
            "gaz",
            "gas"
        ],

        "COMMERCE": [
            "retail",
            "commerce",
            "ecommerce",
            "e-commerce",
            "shop",
            "store",
            "magasin",
            "marketplace"
        ],

        "TRANSPORT": [
            "transport",
            "airline",
            "aviation",
            "airport",
            "aéroport",
            "aeroport",
            "railway",
            "train",
            "logistics",
            "logistique"
        ]
    }

    scores = {}

    for secteur, mots in secteurs.items():

        score = 0

        for mot in mots:

            if mot in texte:
                score += 1

        if score > 0:
            scores[secteur] = score

    if not scores:

        return (
            "INCONNU",
            0.0,
            []
        )

    secteur = max(
        scores,
        key=scores.get
    )

    score = scores[secteur]

    confiance = min(
        0.95,
        0.45 + (
            0.15 * min(score, 3)
        )
    )

    preuves = [
        mot
        for mot in secteurs[secteur]
        if mot in texte
    ]

    return (
        secteur,
        float(confiance),
        preuves
    )


# Alias pour compatibilité
def classifier_secteur_texte(texte: str) -> Tuple[str, float, List[str]]:
    """Alias pour classifier_secteur."""
    return classifier_secteur(texte)


def classifier_secteur_texte_simple(texte: str) -> str:
    """Version simplifiée de classifier_secteur."""
    if not texte:
        return "INCONNU"
    secteur, _, _ = classifier_secteur(texte)
    return secteur


# ============================================================================
# CLASSIFICATION SEVERITE
# ============================================================================

def classifier_severite(
    texte: str,
    score_cvss: Optional[float] = None
) -> Tuple[str, float, List[str]]:

    texte = normaliser_texte(
        texte
    )

    preuves = []

    if score_cvss is not None:

        try:

            score = float(
                score_cvss
            )

            if score >= 9.0:

                return (
                    "CRITIQUE",
                    0.98,
                    [f"CVSS={score:.1f}"]
                )

            if score >= 7.0:

                return (
                    "ELEVEE",
                    0.95,
                    [f"CVSS={score:.1f}"]
                )

            if score >= 4.0:

                return (
                    "MOYENNE",
                    0.90,
                    [f"CVSS={score:.1f}"]
                )

            return (
                "FAIBLE",
                0.90,
                [f"CVSS={score:.1f}"]
            )

        except Exception:
            pass

    mots_critiques = [
        "critical",
        "critique",
        "remote code execution",
        "rce",
        "zero-day",
        "zero day",
        "ransomware",
        "ransom"
    ]

    for mot in mots_critiques:

        if mot in texte:

            preuves.append(mot)

    if preuves:

        return (
            "CRITIQUE",
            0.90,
            preuves
        )

    mots_eleves = [
        "high severity",
        "high risk",
        "severity high",
        "exploitation active",
        "actively exploited",
        "compromission",
        "data breach",
        "fuite de données",
        "intrusion"
    ]

    for mot in mots_eleves:

        if mot in texte:

            preuves.append(mot)

    if preuves:

        return (
            "ELEVEE",
            0.82,
            preuves
        )

    mots_moyens = [
        "medium",
        "moderate",
        "moyenne",
        "moderate risk"
    ]

    for mot in mots_moyens:

        if mot in texte:

            preuves.append(mot)

    if preuves:

        return (
            "MOYENNE",
            0.75,
            preuves
        )

    mots_faibles = [
        "low",
        "faible",
        "informational",
        "information"
    ]

    for mot in mots_faibles:

        if mot in texte:

            preuves.append(mot)

    if preuves:

        return (
            "FAIBLE",
            0.70,
            preuves
        )

    return (
        "MOYENNE",
        0.40,
        []
    )


# ============================================================================
# MAP SEVERITE CVSS
# ============================================================================

def map_severite_cvss(score: Optional[float]) -> Tuple[str, float]:
    """Map un score CVSS vers une sévérité."""
    if score is None:
        return "INCONNU", 0.0
    
    try:
        score = float(score)
    except (TypeError, ValueError):
        return "INCONNU", 0.0
    
    if score >= 9.0:
        return "CRITIQUE", 0.95
    if score >= 7.0:
        return "ELEVEE", 0.90
    if score >= 4.0:
        return "MOYENNE", 0.85
    if score >= 1.0:
        return "FAIBLE", 0.80
    return "INCONNU", 0.0


def map_severite_cvss_simple(score: Optional[float]) -> str:
    """Version simplifiée de map_severite_cvss."""
    result, _ = map_severite_cvss(score)
    return result


# ============================================================================
# MAP NIVEAU RISQUE TEXTE
# ============================================================================

def map_niveau_risque_texte(texte: str, titre: str = "", raw_data: Optional[Dict[str, Any]] = None) -> Tuple[str, float, List[str]]:
    """
    Version compatible avec les collecteurs existants.
    Accepte les 3 paramètres comme dans collect_dgssi.py.
    """
    # Si titre ou raw_data sont fournis, construire le texte complet
    if titre or raw_data:
        texte_complet = construire_texte_global(
            titre=titre,
            description=texte,
            raw_data=raw_data
        )
    else:
        texte_complet = texte or ""
    
    # Si le texte est vide, retourner INCONNU
    if not texte_complet.strip():
        return "INCONNU", 0.0, []
    
    return classifier_severite(texte_complet)


def map_niveau_risque_texte_simple(texte: str) -> str:
    """Version simplifiée de map_niveau_risque_texte."""
    if not texte:
        return "INCONNU"
    result, _, _ = map_niveau_risque_texte(texte)
    return result


# ============================================================================
# NIVEAU DE RISQUE
# ============================================================================

def niveau_risque(risque: Any) -> str:
    """
    Convertit un score de risque en niveau.
    Utilisé par recompute_classification.py.
    """
    try:
        risque = float(risque or 0)
    except (ValueError, TypeError):
        risque = 0

    if risque >= 80:
        return "CRITIQUE"

    if risque >= 60:
        return "ELEVEE"

    if risque >= 35:
        return "MOYENNE"

    return "FAIBLE"


# ============================================================================
# RISQUE
# ============================================================================

def calculer_risque(
    menace: str,
    confiance_menace: float,
    severite: str,
    confiance_severite: float,
    secteur: str
) -> int:
    """
    Calcule un score de risque 0-100.
    """

    score = 0.0

    poids_menace = {

        "RANSOMWARE": 95,
        "DDOS": 75,
        "FUITE_DONNEES": 90,
        "CHEVAL_TROIE": 80,
        "SPYWARE": 75,
        "MALWARE": 75,
        "PHISHING": 65,
        "EXPLOITATION": 85,
        "PIRATAGE": 70,
        "VULNERABILITE": 60,
        "INGENIERIE_SOCIALE": 60,
        "INCONNU": 20
    }

    base_menace = poids_menace.get(
        menace,
        50
    )

    poids_severite = {

        "CRITIQUE": 100,
        "ELEVEE": 80,
        "MOYENNE": 55,
        "FAIBLE": 30,
        "INCONNU": 20
    }

    base_severite = poids_severite.get(
        severite,
        50
    )

    multiplicateur_secteur = {

        "SANTE": 1.10,
        "FINANCE": 1.10,
        "ADMINISTRATION": 1.05,
        "ENERGIE": 1.10,
        "TELECOM": 1.05,
        "INDUSTRIE": 1.05
    }.get(
        secteur,
        1.0
    )

    score = (
        0.55 * base_menace * max(
            confiance_menace,
            0.50
        )
        +
        0.45 * base_severite * max(
            confiance_severite,
            0.50
        )
    )

    score *= multiplicateur_secteur

    return int(
        max(
            0,
            min(
                100,
                round(score)
            )
        )
    )


# ============================================================================
# NIVEAU DE CONFIANCE
# ============================================================================

def niveau_confiance(
    confiance: Any
) -> str:

    try:
        confiance = float(
            confiance
        )
    except (
        ValueError,
        TypeError
    ):
        confiance = 0.0

    if confiance >= 0.80:
        return "TRES_ELEVEE"

    if confiance >= 0.65:
        return "ELEVEE"

    if confiance >= 0.45:
        return "MOYENNE"

    if confiance >= 0.25:
        return "FAIBLE"

    return "TRES_FAIBLE"


# ============================================================================
# CLASSIFICATION COMPLÈTE
# ============================================================================

def classifier_cyber_complet(
    titre: str = "",
    description: str = "",
    raw_data: Optional[Dict[str, Any]] = None,
    score_cvss: Optional[float] = None,
    seuil_confiance: float = DEFAULT_CONFIDENCE_THRESHOLD
) -> Dict[str, Any]:
    """
    Fonction centrale appelée par les collecteurs et
    recompute_classification.py.

    Retourne exactement les champs attendus par le pipeline.
    """

    texte = construire_texte_global(
        titre=titre,
        description=description,
        raw_data=raw_data
    )

    menace = classifier_menace_hybride(
        texte,
        seuil_confiance=seuil_confiance
    )

    type_menace = menace["prediction"]

    confiance_menace = menace[
        "confiance"
    ]

    secteur, confiance_secteur, preuves_secteur = (
        classifier_secteur(
            texte
        )
    )

    severite, confiance_severite, preuves_severite = (
        classifier_severite(
            texte,
            score_cvss=score_cvss
        )
    )

    confiance_globale = (
        0.50 * confiance_menace
        +
        0.25 * confiance_secteur
        +
        0.25 * confiance_severite
    )

    risque = calculer_risque(
        menace=type_menace,
        confiance_menace=confiance_menace,
        severite=severite,
        confiance_severite=confiance_severite,
        secteur=secteur
    )

    return {

        "type_menace": type_menace,

        "confiance_menace": float(
            confiance_menace
        ),

        "secteur_cible": secteur,

        "confiance_secteur": float(
            confiance_secteur
        ),

        "severite": severite,

        "confiance_severite": float(
            confiance_severite
        ),

        "confiance_globale": float(
            confiance_globale
        ),

        "niveau_confiance": niveau_confiance(
            confiance_globale
        ),

        "risque": int(
            risque
        ),

        "methode_classification_menace": menace[
            "methode"
        ],

        "prediction_ml_menace": menace[
            "prediction_ml"
        ],

        "confiance_ml_menace": float(
            menace[
                "confiance_ml"
            ]
        ),

        "prediction_regles_menace": menace[
            "prediction_regles"
        ],

        "confiance_regles_menace": float(
            menace[
                "confiance_regles"
            ]
        ),

        "accord_regles_ml": bool(
            menace[
                "accord"
            ]
        ),

        "preuves": {

            "menace": menace.get(
                "preuves",
                []
            ),

            "secteur": preuves_secteur,

            "severite": preuves_severite
        },

        "classification_model": MODEL_VERSION,

        "texte_utilise": texte
    }


# ============================================================================
# ALIAS / COMPATIBILITÉ
# ============================================================================

def classifier_menace_texte(
    texte: str,
    seuil_confiance: float = DEFAULT_CONFIDENCE_THRESHOLD
) -> Tuple[str, float]:

    resultat = classifier_menace_hybride(
        texte,
        seuil_confiance
    )

    return (
        resultat["prediction"],
        resultat["confiance"]
    )


def classifier_menace_texte_simple(texte: str) -> str:
    """
    Version simplifiée de classifier_menace_texte.
    Retourne uniquement le type de menace.
    Compatible avec les collecteurs existants (CIRCL, BAM, DGSSI, etc.)
    """
    if not texte:
        return "INCONNU"
    
    resultat, _ = classifier_menace_texte(texte)
    return resultat


def classifier_menace_texte_detaille(
    texte: str,
    seuil_confiance: float = DEFAULT_CONFIDENCE_THRESHOLD
) -> Dict[str, Any]:

    return classifier_menace_hybride(
        texte,
        seuil_confiance
    )


def classifier_menace_cve_simple(description: str) -> str:
    """Version simplifiée pour les CVE."""
    if not description:
        return "INCONNU"
    
    type_menace, _ = classifier_menace_texte(description)
    return type_menace


# ============================================================================
# NORMALISATION MENACE
# ============================================================================

def normaliser_menace(
    valeur: Any
) -> str:

    if valeur is None:
        return "INCONNU"

    valeur = str(
        valeur
    ).strip().upper()

    mappings = {

        "TROJAN": "CHEVAL_TROIE",
        "TROJAN_HORSE": "CHEVAL_TROIE",
        "CHEVAL DE TROIE": "CHEVAL_TROIE",
        "CHEVAL_DE_TROIE": "CHEVAL_TROIE",

        "DATA_LEAK": "FUITE_DONNEES",
        "DATA_BREACH": "FUITE_DONNEES",
        "FUITE DE DONNEES": "FUITE_DONNEES",

        "DENIAL_OF_SERVICE": "DDOS",
        "DOS": "DDOS",

        "RANÇONGICIEL": "RANSOMWARE",
        "RANCONGICIEL": "RANSOMWARE",

        "VULNERABILITY": "VULNERABILITE",

        "HACK": "PIRATAGE",
        "HACKING": "PIRATAGE",

        "SOCIAL_ENGINEERING": "INGENIERIE_SOCIALE",

        # Ajouts pour compatibilité avec URLhaus et autres
        "MALICIEL": "MALWARE",
        "MALICIOUS_SOFTWARE": "MALWARE",
        "CHEVAL_DE_TROIE": "CHEVAL_TROIE",
        "RANSONGICIEL": "RANSOMWARE",
        "INCIDENT": "INCIDENT",
        "FUITE_DONNEES": "FUITE_DONNEES",
        "EXPLOITATION": "EXPLOITATION",
        "SPOOFING": "SPOOFING",
        "KEYLOGGER": "KEYLOGGER",
        "VIRUS": "VIRUS",
        "VER_INFORMATIQUE": "VER_INFORMATIQUE",
        "SPAM": "SPAM",
        "ESCROQUERIE": "ESCROQUERIE_PAIEMENT",
        "ESCROQUERIE_PAIEMENT": "ESCROQUERIE_PAIEMENT",
        "BLANCHIMENT": "BLANCHIMENT",
        "BOTNET": "BOTNET",
        "COMPROMISSION_COMPTE": "COMPROMISSION_COMPTE",
        "VOL_IDENTIFIANTS": "VOL_IDENTIFIANTS",
        "DEFAÇAGE": "DEFAÇAGE",
        "CRYPTOJACKING": "CRYPTOJACKING",
        "PHISHING": "PHISHING",
        "RANSOMWARE": "RANSOMWARE",
        "DDOS": "DDOS",
        "PIRATAGE": "PIRATAGE",
        "VULNERABILITE": "VULNERABILITE",
        "SPYWARE": "SPYWARE",
        "MALWARE": "MALWARE",
        "INGENIERIE_SOCIALE": "INGENIERIE_SOCIALE",
        "INCONNU": "INCONNU",
    }

    return mappings.get(
        valeur,
        "INCONNU" if valeur not in CLASSES_METIER else valeur
    )


# ============================================================================
# NORMALISATION SECTEUR
# ============================================================================

def normaliser_secteur(
    valeur: Any
) -> str:

    if valeur is None:
        return "INCONNU"

    valeur = str(
        valeur
    ).strip().upper()

    mappings = {

        "FINANCE": "FINANCE",
        "FINANCIAL": "FINANCE",
        "BANQUE": "FINANCE",
        "FINANCE_ASSURANCE": "FINANCE",

        "HEALTH": "SANTE",
        "HEALTHCARE": "SANTE",
        "SANTÉ": "SANTE",
        "SANTE": "SANTE",
        "SANTE_PHARMACIE": "SANTE",

        "EDUCATION": "EDUCATION",
        "ÉDUCATION": "EDUCATION",

        "GOVERNMENT": "ADMINISTRATION",
        "GOUVERNEMENT": "ADMINISTRATION",

        "TELECOMMUNICATION": "TELECOM",
        "TELECOMMUNICATIONS": "TELECOM",
        "IT_TELECOM": "TELECOM",

        "ENERGY": "ENERGIE",
        "ÉNERGIE": "ENERGIE",

        "COMMERCE": "COMMERCE",
        "COMMERCE_RETAIL": "COMMERCE",
        "RETAIL": "COMMERCE",

        "INDUSTRIE": "INDUSTRIE",
        "INDUSTRIE_MANUFACTURING": "INDUSTRIE",
        "MANUFACTURING": "INDUSTRIE",

        "TRANSPORT": "TRANSPORT",
        "TRANSPORT_LOGISTIQUE": "TRANSPORT",

        "BTP": "BTP",
        "BTP_CONSTRUCTION": "BTP",
        "CONSTRUCTION": "BTP",

        "SERVICES": "SERVICES",
        "HOTELLERIE": "HOTELLERIE",
        "HOTELLERIE_TOURISME": "HOTELLERIE",
        "AGROALIMENTAIRE": "AGROALIMENTAIRE",
        "INCONNU": "INCONNU",
    }

    return mappings.get(
        valeur,
        "INCONNU"
    )


# ============================================================================
# NORMALISATION SEVERITE
# ============================================================================

def normaliser_severite(
    valeur: Any
) -> str:

    if valeur is None:
        return "INCONNU"

    valeur = str(
        valeur
    ).strip().upper()

    mappings = {

        "CRITICAL": "CRITIQUE",
        "CRITIQUE": "CRITIQUE",

        "HIGH": "ELEVEE",
        "ÉLEVÉE": "ELEVEE",
        "ELEVEE": "ELEVEE",

        "MEDIUM": "MOYENNE",
        "MODERATE": "MOYENNE",
        "MOYENNE": "MOYENNE",

        "LOW": "FAIBLE",
        "FAIBLE": "FAIBLE",

        "INCONNUE": "INCONNU",
        "INCONNU": "INCONNU",
    }

    return mappings.get(
        valeur,
        "INCONNU"
    )


# ============================================================================
# NORMALISATION POUR STOCKAGE
# ============================================================================

def normaliser_pour_stockage_menace(
    valeur: Any
) -> str:

    valeur = normaliser_menace(
        valeur
    )

    valeurs_valides = {
        "PIRATAGE",
        "VULNERABILITE",
        "DDOS",
        "RANSOMWARE",
        "FUITE_DONNEES",
        "CHEVAL_TROIE",
        "PHISHING",
        "SPYWARE",
        "MALWARE",
        "EXPLOITATION",
        "INGENIERIE_SOCIALE",
        "BOTNET",
        "COMPROMISSION_COMPTE",
        "VOL_IDENTIFIANTS",
        "DEFAÇAGE",
        "CRYPTOJACKING",
        "SPOOFING",
        "VIRUS",
        "KEYLOGGER",
        "SPAM",
        "VER_INFORMATIQUE",
        "ESCROQUERIE_PAIEMENT",
        "INCIDENT",
        "INCONNU"
    }

    if valeur not in valeurs_valides:
        return "INCONNU"

    return valeur


def normaliser_pour_stockage_secteur(
    valeur: Any
) -> str:

    return normaliser_secteur(
        valeur
    )


def normaliser_pour_stockage_severite(
    valeur: Any
) -> str:

    return normaliser_severite(
        valeur
    )


# ============================================================================
# FONCTIONS DE MAPPING OFFICIEL
# ============================================================================

def map_menace_to_official_simple(menace: str) -> str:
    """
    Version simplifiée pour mapper une menace vers les classes officielles.
    Utilisée par les collecteurs (NVD, CIRCL, BAM, DGSSI, etc.)
    """
    if not menace:
        return "INCONNU"
    
    return normaliser_menace(menace)


def map_secteur_to_official_simple(secteur: str) -> str:
    """
    Version simplifiée pour mapper un secteur vers les classes officielles.
    Utilisée par les collecteurs (NVD, CIRCL, BAM, DGSSI, etc.)
    """
    if not secteur:
        return "INCONNU"
    
    return normaliser_secteur(secteur)


def map_severite_to_official_simple(severite: str) -> str:
    """
    Version simplifiée pour mapper une sévérité vers les classes officielles.
    Utilisée par les collecteurs (NVD, CIRCL, DGSSI, etc.)
    """
    if not severite:
        return "INCONNU"
    
    return normaliser_severite(severite)


def map_menace_to_official(menace: str) -> str:
    """Alias pour map_menace_to_official_simple."""
    return map_menace_to_official_simple(menace)


def map_secteur_to_official(secteur: str) -> str:
    """Alias pour map_secteur_to_official_simple."""
    return map_secteur_to_official_simple(secteur)


def map_severite_to_official(severite: str) -> str:
    """Alias pour map_severite_to_official_simple."""
    return map_severite_to_official_simple(severite)


# ============================================================================
# FONCTIONS DE PERTINENCE CYBER
# ============================================================================

def est_pertinent_cyber(texte: str, seuil_confiance: float = 0.2) -> Tuple[bool, float, List[str]]:
    """
    Vérifie si un texte est pertinent pour la cybersécurité.
    Retourne (est_pertinent, confiance, mots_cles_trouves).
    Compatible avec les collecteurs RSS.
    """
    if not texte:
        return False, 0.0, []
    
    texte_lower = texte.lower()
    
    mots_cyber_forts = [
        "cyber", "security", "vulnerability", "ransomware", "phishing",
        "malware", "trojan", "backdoor", "exploit", "zero-day",
        "0-day", "cve-", "breach", "hack", "hacking", "intrusion",
        "attack", "attaque", "piratage", "hameçonnage", "rançongiciel",
        "vulnérabilité", "exploitation", "compromis", "menace",
        "cyberattaque", "cybercriminalité", "ransom", "lockbit",
        "conti", "clop", "apt", "espionnage", "fuite", "data breach",
        "data leak", "cybersécurité", "cybersecurity", "sécurité informatique",
        "ssi", "faille", "patch", "logiciel malveillant", "virus",
        "cheval de troie", "spyware", "keylogger", "ddos",
        "déni de service", "usurpation", "spoofing", "hacker",
        "cybercriminel", "protection des données", "rgpd", "gdpr",
        "cndp", "anssi", "cisa", "cert-", "dgssi", "pare-feu",
        "firewall", "pentest", "audit de sécurité", "darknet",
        "dark web", "mfa", "chiffrement", "اختراق", "هجوم",
        "ثغرة", "برمجيات خبيثة", "فدية", "exploitation",
        "malicious", "campaign", "cybercrime", "compromission",
        "vol d'identifiants", "credential", "authentification"
    ]
    
    mots_exclusion = [
        "football", "sport", "jeux vidéo", "cinéma", "musique",
        "recette", "cuisine", "gastronomie", "voyage", "tourisme",
        "mode", "beauté", "people", "divertissement", "culture",
        "livre", "roman", "poésie", "théâtre", "danse"
    ]
    
    for mot in mots_exclusion:
        if mot in texte_lower:
            return False, 0.0, [mot]
    
    mots_trouves = []
    for mot in mots_cyber_forts:
        if mot in texte_lower:
            mots_trouves.append(mot)
    
    if mots_trouves:
        confiance = min(0.5 + (len(mots_trouves) * 0.05), 0.95)
        return True, confiance, mots_trouves
    
    type_menace, confiance_menace = classifier_menace_texte(texte)
    if type_menace != "INCONNU" and confiance_menace >= seuil_confiance:
        return True, confiance_menace, [type_menace]
    
    return False, 0.0, []


def est_pertinent_cyber_simple(texte: str, seuil_confiance: float = 0.2) -> bool:
    """
    Version simplifiée de est_pertinent_cyber.
    Retourne uniquement un booléen.
    Compatible avec les collecteurs RSS.
    """
    result, _, _ = est_pertinent_cyber(texte, seuil_confiance)
    return result


# ============================================================================
# PARSE DATE FR
# ============================================================================

def parse_date_fr(date_text: str) -> Optional[datetime]:
    """
    Parse une date en français.
    Compatible avec les collecteurs existants (BAM, DGSSI, MTNRA).
    """
    if not date_text:
        return None
    
    date_text = date_text.strip()
    
    mois_fr = {
        "janvier": 1, "février": 2, "mars": 3, "avril": 4,
        "mai": 5, "juin": 6, "juillet": 7, "août": 8,
        "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12,
    }
    
    # Format: "22 mai 2026"
    match = re.search(r'(\d{1,2})\s+([a-zà-ÿ]+)\s+(\d{4})', date_text, re.I)
    if match:
        jour = int(match.group(1))
        mois = mois_fr.get(match.group(2).lower())
        if mois:
            try:
                return datetime(int(match.group(3)), mois, jour)
            except ValueError:
                pass
    
    # Format: "22/05/2026"
    match = re.search(r'(\d{2})/(\d{2})/(\d{4})', date_text)
    if match:
        try:
            return datetime(int(match.group(3)), int(match.group(2)), int(match.group(1)))
        except ValueError:
            pass
    
    # Format: "22-05-2026"
    match = re.search(r'(\d{2})-(\d{2})-(\d{4})', date_text)
    if match:
        try:
            return datetime(int(match.group(3)), int(match.group(2)), int(match.group(1)))
        except ValueError:
            pass
    
    return None


# ============================================================================
# TEST DIRECT
# ============================================================================

if __name__ == "__main__":

    print()
    print("=" * 80)
    print("TEST DU MOTEUR CENTRAL classifiers.py")
    print("=" * 80)

    status = get_ml_classifier_status()

    print()
    print("STATUT ML")
    print("-" * 80)

    print(
        "Activé      :",
        status["enabled"]
    )

    print(
        "Disponible  :",
        status["available"]
    )

    print(
        "Chargé      :",
        status["loaded"]
    )

    print(
        "Classes     :",
        len(status["classes"])
    )

    print(
        "Classes     :",
        status["classes"]
    )

    if status["error"]:

        print(
            "Erreur      :",
            status["error"]
        )

    # ------------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------------

    tests = [

        (
            "Ransomware",
            "Une attaque ransomware a chiffré les fichiers "
            "de l'entreprise et demande une rançon."
        ),

        (
            "Phishing",
            "Une campagne de phishing utilise une fausse "
            "page de connexion pour voler les identifiants."
        ),

        (
            "Vulnérabilité",
            "CVE-2026-1234 est une vulnérabilité critique "
            "permettant une remote code execution."
        ),

        (
            "DDoS",
            "Une attaque DDoS massive a rendu le serveur "
            "indisponible."
        ),

        (
            "Fuite",
            "Une base de données contenant des informations "
            "clients a été exposée sur Internet."
        )
    ]

    for nom, texte in tests:

        print()
        print("-" * 80)
        print(
            f"TEST : {nom}"
        )
        print(
            f"Texte : {texte}"
        )

        resultat = classifier_cyber_complet(
            description=texte
        )

        print()
        print(
            "Menace       :",
            resultat["type_menace"]
        )

        print(
            "Confiance    :",
            f"{resultat['confiance_menace']:.3f}"
        )

        print(
            "Méthode      :",
            resultat[
                "methode_classification_menace"
            ]
        )

        print(
            "Règles       :",
            resultat[
                "prediction_regles_menace"
            ],
            f"({resultat['confiance_regles_menace']:.3f})"
        )

        print(
            "ML           :",
            resultat[
                "prediction_ml_menace"
            ],
            f"({resultat['confiance_ml_menace']:.3f})"
        )

        print(
            "Accord       :",
            resultat[
                "accord_regles_ml"
            ]
        )

        print(
            "Secteur      :",
            resultat[
                "secteur_cible"
            ]
        )

        print(
            "Sévérité     :",
            resultat[
                "severite"
            ]
        )

        print(
            "Risque       :",
            resultat[
                "risque"
            ]
        )

    print()
    print("=" * 80)
    print("TEST TERMINÉ")
    print("=" * 80)