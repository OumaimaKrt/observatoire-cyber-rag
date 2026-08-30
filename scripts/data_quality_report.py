# scripts/data_quality_report.py
# =============================================================================
# Vérifie la DONNÉE produite par tous les collecteurs (pas leur code), pour
# repérer les anomalies qu'une relecture de code ne peut pas détecter : un
# site qui a changé de structure sans faire planter le scraper, un filtre
# trop strict/trop large, des dates aberrantes, une source qui ne renvoie
# plus que des doublons ou que des données de démo, etc.
#
# 🔥 AMÉLIORATION (2026-07-14) : Ajout de la détection automatique des
# problèmes de taxonomie (mélange de codes Inconnu/INCONNU, TELECOM/IT_Telecom)
# qui a dû être chassé à la main avec des SELECT DISTINCT manuels.
#
# Usage : python scripts/data_quality_report.py
# =============================================================================
import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import RealDictCursor
from config import DB_CONFIG

# ─── TAXONOMIE OFFICIELLE CMRPI ─────────────────────────────────────────────
# 🔥 Ajout : Les valeurs attendues pour les codes officiels

TAXONOMIE_MENACES_OFFICIELLES = {
    "RANSOMWARE", "PHISHING", "CHEVAL_TROIE", "DDOS", "KEYLOGGER",
    "SPYWARE", "SPOOFING", "ESCROQUERIE", "PIRATAGE", "VIRUS",
    "VER", "SPAM", "BLANCHIMENT", "INCONNU"
}

TAXONOMIE_SECTEURS_OFFICIELS = {
    "FINANCE", "COMMERCE", "INDUSTRIE", "SANTE", "TRANSPORT",
    "TELECOM", "BTP", "SERVICES", "HOTELLERIE", "AGROALIMENTAIRE",
    "ENERGIE", "EDUCATION", "INCONNU"
}

TAXONOMIE_SEVERITES_OFFICIELLES = {
    "CRITIQUE", "ELEVEE", "MOYENNE", "FAIBLE", "INCONNUE"
}

# 🔥 Anciens codes à détecter (problèmes de mapping)
ANCIENS_CODES_MENACES = {
    "Piratage", "Inconnu", "DDoS", "Phishing", "Ransomware",
    "Spoofing", "Spyware", "Blanchiment", "Virus", "Cheval_de_Troie"
}

ANCIENS_CODES_SECTEURS = {
    "IT_Telecom", "Commerce_Retail", "Transport_Logistique",
    "Finance_Assurance", "Sante_Pharmacie", "BTP_Construction",
    "Hotellerie_Tourisme", "Agroalimentaire", "Energie", "Education",
    "Inconnu"
}

ALERTES = []  # (niveau, message) accumulés pour le résumé final


def alerte(niveau: str, message: str):
    ALERTES.append((niveau, message))
    print(f"  {niveau} {message}")


def detecter_taxonomie(cur):
    """
    🔥 NOUVEAU : Détecte automatiquement les problèmes de taxonomie :
    - Mélange de codes officiels et non-officiels
    - Anciens codes qui devraient être mappés
    - Codes en minuscules/majuscules mélangées
    """
    print("\n" + "=" * 72)
    print("  🔍 TAXONOMIE — Détection des codes non normalisés")
    print("=" * 72)
    
    # ─── 1. Détection des types de menace non officiels ──────────────────
    cur.execute("""
        SELECT DISTINCT type_menace 
        FROM cyber_incidents 
        WHERE type_menace IS NOT NULL 
          AND type_menace != ''
          AND type_menace NOT IN %s
    """, (tuple(TAXONOMIE_MENACES_OFFICIELLES),))
    
    valeurs_inattendues = [r["type_menace"] for r in cur.fetchall()]
    
    if valeurs_inattendues:
        # Vérifier si ce sont des anciens codes
        anciens_trouves = [v for v in valeurs_inattendues if v in ANCIENS_CODES_MENACES]
        autres = [v for v in valeurs_inattendues if v not in ANCIENS_CODES_MENACES]
        
        if anciens_trouves:
            alerte("🔴", f"Anciens codes type_menace trouvés (à mapper) : {anciens_trouves}")
            alerte("💡", f"   Ces codes devraient être mappés vers les codes officiels CMRPI.")
        
        if autres:
            alerte("🔴", f"Codes type_menace inattendus : {autres}")
    
    # ─── 2. Détection des secteurs non officiels ──────────────────────────
    cur.execute("""
        SELECT DISTINCT secteur_cible 
        FROM cyber_incidents 
        WHERE secteur_cible IS NOT NULL 
          AND secteur_cible != ''
          AND secteur_cible NOT IN %s
    """, (tuple(TAXONOMIE_SECTEURS_OFFICIELS),))
    
    valeurs_inattendues = [r["secteur_cible"] for r in cur.fetchall()]
    
    if valeurs_inattendues:
        anciens_trouves = [v for v in valeurs_inattendues if v in ANCIENS_CODES_SECTEURS]
        autres = [v for v in valeurs_inattendues if v not in ANCIENS_CODES_SECTEURS]
        
        if anciens_trouves:
            alerte("🔴", f"Anciens codes secteur_cible trouvés (à mapper) : {anciens_trouves}")
            alerte("💡", f"   Ces codes devraient être mappés vers les codes officiels CMRPI.")
        
        if autres:
            alerte("🔴", f"Codes secteur_cible inattendus : {autres}")
    
    # ─── 3. Détection des sévérités non officielles ──────────────────────
    cur.execute("""
        SELECT DISTINCT severite 
        FROM cyber_incidents 
        WHERE severite IS NOT NULL 
          AND severite != ''
          AND severite NOT IN %s
    """, (tuple(TAXONOMIE_SEVERITES_OFFICIELLES),))
    
    valeurs_inattendues = [r["severite"] for r in cur.fetchall()]
    
    if valeurs_inattendues:
        alerte("🔴", f"Codes severite inattendus : {valeurs_inattendues}")
        alerte("💡", f"   Les valeurs attendues sont : {TAXONOMIE_SEVERITES_OFFICIELLES}")
    
    # ─── 4. Détection des mélanges casse (Inconnu vs INCONNU) ────────────
    cur.execute("""
        SELECT type_menace, COUNT(*) 
        FROM cyber_incidents 
        WHERE type_menace IN %s
        GROUP BY type_menace
    """, (tuple(ANCIENS_CODES_MENACES),))
    
    anciens = cur.fetchall()
    if anciens:
        alerte("🟠", f"{len(anciens)} ancien(s) code(s) type_menace encore présents :")
        for row in anciens:
            alerte("   ", f"  - {row['type_menace']}: {row['count']} occurrences")
    
    cur.execute("""
        SELECT secteur_cible, COUNT(*) 
        FROM cyber_incidents 
        WHERE secteur_cible IN %s
        GROUP BY secteur_cible
    """, (tuple(ANCIENS_CODES_SECTEURS),))
    
    anciens = cur.fetchall()
    if anciens:
        alerte("🟠", f"{len(anciens)} ancien(s) code(s) secteur_cible encore présents :")
        for row in anciens:
            alerte("   ", f"  - {row['secteur_cible']}: {row['count']} occurrences")
    
    if not valeurs_inattendues and not anciens:
        print("  ✅ Aucun problème de taxonomie détecté.")


def rapport_cyber_incidents(cur):
    print("\n" + "=" * 72)
    print("  CYBER_INCIDENTS — par source")
    print("=" * 72)

    cur.execute("""
        SELECT
            source,
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE raw_data->>'source' = 'demo') AS demo,
            COUNT(DISTINCT url_source) AS urls_distinctes,
            MIN(date_incident) AS date_min,
            MAX(date_incident) AS date_max,
            COUNT(*) FILTER (WHERE date_incident > NOW() + INTERVAL '1 day') AS dates_futures,
            COUNT(*) FILTER (WHERE date_incident IS NULL) AS dates_nulles
        FROM cyber_incidents
        GROUP BY source
        ORDER BY total DESC
    """)
    lignes = cur.fetchall()

    for l in lignes:
        print(f"\n  {l['source']} — {l['total']} ligne(s)")
        print(f"    Période : {l['date_min']} -> {l['date_max']}")

        if l["total"] > 0 and l["demo"] == l["total"]:
            alerte("🔴", f"[{l['source']}] 100% des lignes sont des données de démo "
                          f"({l['demo']}/{l['total']}) — la collecte réelle échoue systématiquement.")
        elif l["demo"] > 0:
            pct = round(100 * l["demo"] / l["total"], 1)
            if pct > 20:
                alerte("🟠", f"[{l['source']}] {pct}% de données de démo ({l['demo']}/{l['total']}) "
                              f"— la collecte réelle échoue souvent.")

        if l["total"] > 1 and l["urls_distinctes"] < l["total"] * 0.5:
            alerte("🔴", f"[{l['source']}] seulement {l['urls_distinctes']} URL distinctes pour "
                          f"{l['total']} lignes — le dédoublonnage ne fonctionne peut-être pas "
                          f"(vérifier la contrainte UNIQUE et l'ID stable).")

        if l["dates_futures"] > 0:
            alerte("🟠", f"[{l['source']}] {l['dates_futures']} ligne(s) avec une date_incident "
                          f"dans le futur — probable bug de parsing de date.")

        if l["total"] > 5 and l["dates_nulles"] == l["total"]:
            alerte("🟡", f"[{l['source']}] toutes les dates sont NULL — vérifier le parsing de date "
                          f"de ce collecteur (ou si c'est un choix assumé, ignorer).")

    # ── Concentration suspecte sur une seule valeur de sévérité/type ────────
    cur.execute("""
        SELECT source, severite, COUNT(*) AS n,
               SUM(COUNT(*)) OVER (PARTITION BY source) AS total_source
        FROM cyber_incidents
        GROUP BY source, severite
    """)
    for l in cur.fetchall():
        if l["total_source"] >= 10 and l["n"] == l["total_source"]:
            alerte("🟡", f"[{l['source']}] 100% des lignes ont severite='{l['severite']}' "
                          f"— vérifier que ce n'est pas une valeur inventée par défaut "
                          f"(voir le bug historique INCONNUE->MOYENNE de ce projet).")

    # ── pertinence_pme : une source 100% FAIBLE peut signaler un vocabulaire
    # non couvert par utils/pertinence_pme.py plutôt qu'une vraie absence de
    # pertinence PME.
    cur.execute("""
        SELECT source, COUNT(*) AS total,
               COUNT(*) FILTER (WHERE pertinence_pme = 'FAIBLE') AS n_faible
        FROM cyber_incidents
        GROUP BY source
    """)
    for l in cur.fetchall():
        if l["total"] >= 10 and l["n_faible"] == l["total"]:
            alerte("🟡", f"[{l['source']}] 100% en pertinence_pme='FAIBLE' — à vérifier : "
                          f"vrai signal (source hors-sujet PME) ou vocabulaire non couvert "
                          f"par utils/pertinence_pme.py ?")


def rapport_sector_news(cur):
    print("\n" + "=" * 72)
    print("  SECTOR_NEWS — par source")
    print("=" * 72)

    cur.execute("""
        SELECT
            source,
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE raw_data->>'source' = 'demo') AS demo,
            COUNT(DISTINCT url_source) AS urls_distinctes,
            MIN(date_publication) AS date_min,
            MAX(date_publication) AS date_max,
            COUNT(*) FILTER (WHERE date_publication > NOW() + INTERVAL '1 day') AS dates_futures,
            COUNT(*) FILTER (
                WHERE date_publication::date = created_at::date
            ) AS dates_egales_collecte
        FROM sector_news
        GROUP BY source
        ORDER BY total DESC
    """)
    lignes = cur.fetchall()

    for l in lignes:
        print(f"\n  {l['source']} — {l['total']} ligne(s)")
        print(f"    Période : {l['date_min']} -> {l['date_max']}")

        if l["total"] > 0 and l["demo"] == l["total"]:
            alerte("🔴", f"[{l['source']}] 100% des lignes sont des données de démo.")

        if l["total"] > 1 and l["urls_distinctes"] < l["total"] * 0.5:
            alerte("🔴", f"[{l['source']}] doublons probables : {l['urls_distinctes']} URL "
                          f"distinctes pour {l['total']} lignes.")

        if l["total"] >= 5 and l["dates_egales_collecte"] == l["total"]:
            alerte("🟠", f"[{l['source']}] date_publication == date_collecte pour TOUTES les "
                          f"lignes — signe classique que le parsing de date échoue et retombe "
                          f"systématiquement sur la date du jour (voir le bug ANRT/HCP historique "
                          f"de ce projet).")


def resume_final():
    print("\n" + "=" * 72)
    print("  RÉSUMÉ")
    print("=" * 72)
    if not ALERTES:
        print("  ✅ Aucune anomalie détectée par les heuristiques de ce script.")
        print("     (Ça ne remplace pas une relecture de code — juste un signal en plus.)")
    else:
        n_rouge = sum(1 for n, _ in ALERTES if n == "🔴")
        n_orange = sum(1 for n, _ in ALERTES if n == "🟠")
        n_jaune = sum(1 for n, _ in ALERTES if n == "🟡")
        n_info = sum(1 for n, _ in ALERTES if n == "💡")
        print(f"  🔴 {n_rouge} critique(s)  🟠 {n_orange} à vérifier  🟡 {n_jaune} pour info  💡 {n_info} suggestion(s)")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 🔥 NOUVEAU : Détection de taxonomie AVANT les autres rapports
    detecter_taxonomie(cur)
    
    rapport_cyber_incidents(cur)
    rapport_sector_news(cur)
    resume_final()

    cur.close()
    conn.close()