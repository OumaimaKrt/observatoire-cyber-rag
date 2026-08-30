# ============================================================================
# extract_entities_ner.py
# EXTRACTEUR D'ENTITÉS CYBER AVANCÉ - VERSION SIMPLIFIÉE
# (Sans EntityRuler pour éviter les problèmes de compatibilité)
# ============================================================================

import sys
import os
import re
import json
from collections import defaultdict
from typing import List, Dict, Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
import spacy
from config import DB_CONFIG
from utils.logger import get_logger

logger = get_logger("extract_entities_ner")

# ─── Charger les modèles spaCy ──────────────────────────────────────────────
nlp_fr = spacy.load("fr_core_news_md")
nlp_en = spacy.load("en_core_web_md")

# ─── Normalisation des secteurs ─────────────────────────────────────────────

SECTOR_NORMALIZATION = {
    "banque": "Finance",
    "finance": "Finance",
    "fintech": "Finance",
    "banking": "Finance",
    "bank": "Finance",
    "assurance": "Finance",
    "insurance": "Finance",
    "sante": "Santé",
    "hôpital": "Santé",
    "hospital": "Santé",
    "medical": "Santé",
    "pharmacie": "Santé",
    "telecom": "Télécommunications",
    "internet": "Télécommunications",
    "mobile": "Télécommunications",
    "network": "Télécommunications",
    "industrie": "Industrie",
    "manufacture": "Industrie",
    "production": "Industrie",
    "usine": "Industrie",
    "energie": "Énergie",
    "electricite": "Énergie",
    "petrole": "Énergie",
    "gaz": "Énergie",
    "education": "Éducation",
    "universite": "Éducation",
    "ecole": "Éducation",
    "commerce": "Commerce",
    "retail": "Commerce",
    "distribution": "Commerce",
}

# ─── Normalisation des pays ─────────────────────────────────────────────────

COUNTRY_NORMALIZATION = {
    "maroc": "Maroc",
    "morocco": "Maroc",
    "ma": "Maroc",
    "france": "France",
    "fr": "France",
    "usa": "États-Unis",
    "us": "États-Unis",
    "united states": "États-Unis",
    "uk": "Royaume-Uni",
    "united kingdom": "Royaume-Uni",
    "england": "Royaume-Uni",
    "germany": "Allemagne",
    "deutschland": "Allemagne",
    "de": "Allemagne",
    "espagne": "Espagne",
    "spain": "Espagne",
    "es": "Espagne",
    "canada": "Canada",
    "ca": "Canada",
    "chine": "Chine",
    "china": "Chine",
    "cn": "Chine",
}

# ─── Liste des malwares ─────────────────────────────────────────────────────

MALWARE_KEYWORDS = [
    # Ransomware
    "lockbit", "blackcat", "conti", "clop", "reveton",
    "wannacry", "petya", "notpetya", "ryuk", "darkside", "hive",
    "locker", "crypto", "bitlocker", "dearcry",
    # Banking Trojans
    "trickbot", "emotet", "qbot", "dridex", "ursnif",
    # RATs
    "agent tesla", "formbook", "guloader", "azer",
    # Botnets
    "mirai",
    # Types
    "ransomware", "phishing", "spyware", "spoofing", "ddos", 
    "trojan", "virus", "worm", "keylogger", "rootkit", "backdoor",
    "rat", "stealer", "infostealer"
]

# ─── Liste des organisations ────────────────────────────────────────────────

ORG_KEYWORDS = {
    "cert-ma": "CERT",
    "cert": "CERT",
    "dgssi": "GOVERNMENT",
    "cndp": "GOVERNMENT",
    "anrt": "GOVERNMENT",
    "anssi": "GOVERNMENT",
    "cisa": "GOVERNMENT",
    "nist": "GOVERNMENT",
    "microsoft": "VENDOR",
    "cisco": "VENDOR",
    "google": "VENDOR",
    "oracle": "VENDOR",
    "ibm": "VENDOR",
    "symantec": "VENDOR",
    "mcafee": "VENDOR",
    "crowdstrike": "VENDOR",
    "palo alto": "VENDOR",
    "fortinet": "VENDOR",
}

# ─── Regex pour les IOC ─────────────────────────────────────────────────────

CVE_PATTERN = re.compile(r'CVE-\d{4}-\d{4,7}', re.IGNORECASE)
CWE_PATTERN = re.compile(r'CWE-\d+', re.IGNORECASE)
IP_PATTERN = re.compile(r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b')
DOMAIN_PATTERN = re.compile(r'\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b')
URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')
EMAIL_PATTERN = re.compile(r'\b[\w\.-]+@[\w\.-]+\.\w+\b')
MD5_PATTERN = re.compile(r'\b[a-fA-F0-9]{32}\b')
SHA1_PATTERN = re.compile(r'\b[a-fA-F0-9]{40}\b')
SHA256_PATTERN = re.compile(r'\b[a-fA-F0-9]{64}\b')
PORT_PATTERN = re.compile(r'\b(?:port\s+)?(\d{1,5})\b', re.IGNORECASE)

# ─── Techniques MITRE ──────────────────────────────────────────────────────

MITRE_TECHNIQUES = {
    "T1059": "Command and Scripting Interpreter",
    "T1566": "Phishing",
    "T1486": "Data Encrypted for Impact",
    "T1547": "Boot or Logon Autostart Execution",
    "T1047": "Windows Management Instrumentation",
    "T1053": "Scheduled Task/Job",
    "T1071": "Application Layer Protocol",
    "T1087": "Account Discovery",
    "T1082": "System Information Discovery",
    "T1003": "Credential Dumping",
    "T1218": "Signed Binary Proxy Execution",
    "T1140": "Deobfuscate/Decode Files or Information",
    "T1562": "Impair Defenses",
    "T1490": "Inhibit System Recovery",
    "T1529": "System Shutdown/Reboot",
    "T1070": "Indicator Removal on Host",
    "T1036": "Masquerading",
    "T1027": "Obfuscated Files or Information",
}

MITRE_TACTICS = {
    "TA0001": "Initial Access",
    "TA0002": "Execution",
    "TA0003": "Persistence",
    "TA0004": "Privilege Escalation",
    "TA0005": "Defense Evasion",
    "TA0006": "Credential Access",
    "TA0007": "Discovery",
    "TA0008": "Lateral Movement",
    "TA0009": "Collection",
    "TA0010": "Exfiltration",
    "TA0011": "Command and Control",
    "TA0040": "Impact",
}


# ─── Fonctions d'extraction ─────────────────────────────────────────────────

def extract_cves(texte: str) -> List[Dict[str, Any]]:
    """Extrait les CVE."""
    results = []
    for match in CVE_PATTERN.finditer(texte):
        results.append({
            "value": match.group().upper(),
            "type": "CVE",
            "confidence": 0.99,
            "source": "regex"
        })
    return results


def extract_cwes(texte: str) -> List[Dict[str, Any]]:
    """Extrait les CWE."""
    results = []
    for match in CWE_PATTERN.finditer(texte):
        results.append({
            "value": match.group().upper(),
            "type": "CWE",
            "confidence": 0.95,
            "source": "regex"
        })
    return results


def extract_ips(texte: str) -> List[Dict[str, Any]]:
    """Extrait les adresses IP."""
    results = []
    for match in IP_PATTERN.finditer(texte):
        ip = match.group()
        # Filtrer les IP privées
        if not ip.startswith(('10.', '192.168.', '172.16.', '172.17.', '172.18.', '172.19.', 
                              '172.20.', '172.21.', '172.22.', '172.23.', '172.24.', '172.25.',
                              '172.26.', '172.27.', '172.28.', '172.29.', '172.30.', '172.31.',
                              '127.', '0.0.0.0')):
            results.append({
                "value": ip,
                "type": "IP",
                "confidence": 0.95,
                "source": "regex"
            })
    return results


def extract_domains(texte: str) -> List[Dict[str, Any]]:
    """Extrait les domaines."""
    results = []
    for match in DOMAIN_PATTERN.finditer(texte):
        domain = match.group()
        if len(domain) > 3 and '.' in domain:
            if not re.match(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', domain):
                results.append({
                    "value": domain.lower(),
                    "type": "DOMAIN",
                    "confidence": 0.85,
                    "source": "regex"
                })
    return results


def extract_urls(texte: str) -> List[Dict[str, Any]]:
    """Extrait les URLs."""
    results = []
    for match in URL_PATTERN.finditer(texte):
        results.append({
            "value": match.group(),
            "type": "URL",
            "confidence": 0.95,
            "source": "regex"
        })
    return results


def extract_emails(texte: str) -> List[Dict[str, Any]]:
    """Extrait les emails."""
    results = []
    for match in EMAIL_PATTERN.finditer(texte):
        results.append({
            "value": match.group().lower(),
            "type": "EMAIL",
            "confidence": 0.95,
            "source": "regex"
        })
    return results


def extract_hashes(texte: str) -> List[Dict[str, Any]]:
    """Extrait les hashs."""
    results = []
    
    for match in MD5_PATTERN.finditer(texte):
        results.append({
            "value": match.group().lower(),
            "type": "HASH_MD5",
            "confidence": 0.95,
            "source": "regex"
        })
    
    for match in SHA1_PATTERN.finditer(texte):
        if not MD5_PATTERN.fullmatch(match.group()):
            results.append({
                "value": match.group().lower(),
                "type": "HASH_SHA1",
                "confidence": 0.95,
                "source": "regex"
            })
    
    for match in SHA256_PATTERN.finditer(texte):
        if not MD5_PATTERN.fullmatch(match.group()) and not SHA1_PATTERN.fullmatch(match.group()):
            results.append({
                "value": match.group().lower(),
                "type": "HASH_SHA256",
                "confidence": 0.95,
                "source": "regex"
            })
    
    return results


def extract_ports(texte: str) -> List[Dict[str, Any]]:
    """Extrait les ports."""
    results = []
    for match in PORT_PATTERN.finditer(texte):
        port = int(match.group(1))
        if 1 <= port <= 65535:
            results.append({
                "value": port,
                "type": "PORT",
                "confidence": 0.80,
                "source": "regex"
            })
    return results


def extract_malwares(texte: str) -> List[Dict[str, Any]]:
    """Extrait les malwares avec mots-clés et regex."""
    results = []
    texte_lower = texte.lower()
    
    for malware in MALWARE_KEYWORDS:
        pattern = re.compile(r'\b' + re.escape(malware) + r'\b', re.IGNORECASE)
        if pattern.search(texte_lower):
            results.append({
                "value": malware,
                "type": "MALWARE",
                "confidence": 0.80,
                "source": "keyword"
            })
    
    return deduplicate_entities(results)


def extract_mitre(texte: str) -> List[Dict[str, Any]]:
    """Extrait les techniques MITRE."""
    results = []
    texte_upper = texte.upper()
    
    # Techniques
    for tech_id, tech_name in MITRE_TECHNIQUES.items():
        if tech_id in texte_upper or tech_name.upper() in texte_upper:
            results.append({
                "value": tech_id,
                "name": tech_name,
                "type": "MITRE_TECHNIQUE",
                "confidence": 0.85,
                "source": "keyword"
            })
    
    # Tactics
    for tactic_id, tactic_name in MITRE_TACTICS.items():
        if tactic_id in texte_upper or tactic_name.upper() in texte_upper:
            results.append({
                "value": tactic_id,
                "name": tactic_name,
                "type": "MITRE_TACTIC",
                "confidence": 0.85,
                "source": "keyword"
            })
    
    return deduplicate_entities(results)


def extract_organizations(texte: str) -> List[Dict[str, Any]]:
    """Extrait les organisations."""
    results = []
    texte_lower = texte.lower()
    
    for org, org_type in ORG_KEYWORDS.items():
        pattern = re.compile(r'\b' + re.escape(org) + r'\b', re.IGNORECASE)
        if pattern.search(texte_lower):
            results.append({
                "value": org,
                "type": org_type,
                "confidence": 0.85,
                "source": "keyword"
            })
    
    # Utiliser spaCy pour les ORG
    doc = nlp_en(texte)
    for ent in doc.ents:
        if ent.label_ == "ORG" and len(ent.text) > 2:
            results.append({
                "value": ent.text,
                "type": "ORG",
                "confidence": 0.70,
                "source": "spacy_ner"
            })
    
    return deduplicate_entities(results)


def extract_sectors(texte: str) -> List[Dict[str, Any]]:
    """Extrait les secteurs."""
    results = []
    texte_lower = texte.lower()
    
    for secteur, normalized in SECTOR_NORMALIZATION.items():
        pattern = re.compile(r'\b' + re.escape(secteur) + r'\b', re.IGNORECASE)
        if pattern.search(texte_lower):
            results.append({
                "value": normalized,
                "original": secteur,
                "type": "SECTOR",
                "confidence": 0.80,
                "source": "keyword"
            })
    
    return deduplicate_entities(results)


def extract_countries(texte: str) -> List[Dict[str, Any]]:
    """Extrait les pays."""
    results = []
    texte_lower = texte.lower()
    
    for country, normalized in COUNTRY_NORMALIZATION.items():
        pattern = re.compile(r'\b' + re.escape(country) + r'\b', re.IGNORECASE)
        if pattern.search(texte_lower):
            results.append({
                "value": normalized,
                "original": country,
                "type": "COUNTRY",
                "confidence": 0.80,
                "source": "keyword"
            })
    
    # Utiliser spaCy pour les LOC
    doc = nlp_fr(texte)
    for ent in doc.ents:
        if ent.label_ == "LOC" and len(ent.text) > 2:
            normalized = COUNTRY_NORMALIZATION.get(ent.text.lower(), ent.text)
            results.append({
                "value": normalized,
                "original": ent.text,
                "type": "COUNTRY",
                "confidence": 0.70,
                "source": "spacy_ner"
            })
    
    return deduplicate_entities(results)


def deduplicate_entities(entities: List[Dict]) -> List[Dict]:
    """Déduplique les entités en gardant la meilleure confiance."""
    seen = {}
    for ent in entities:
        key = ent["value"]
        if key not in seen or ent["confidence"] > seen[key]["confidence"]:
            seen[key] = ent
    return list(seen.values())


def extract_with_confidence(entities: List[Dict], threshold: float = 0.5) -> List[Dict]:
    """Filtre les entités par score de confiance."""
    return [e for e in entities if e.get("confidence", 0) >= threshold]


def extract_all_entities(texte: str) -> Dict[str, List[Dict[str, Any]]]:
    """Extrait toutes les entités d'un texte."""
    entities = {
        "cve": extract_cves(texte),
        "cwe": extract_cwes(texte),
        "ip": extract_ips(texte),
        "domain": extract_domains(texte),
        "url": extract_urls(texte),
        "email": extract_emails(texte),
        "hash_md5": [],
        "hash_sha1": [],
        "hash_sha256": [],
        "malware": extract_malwares(texte),
        "mitre_technique": [],
        "mitre_tactic": [],
        "sector": extract_sectors(texte),
        "country": extract_countries(texte),
        "organization": extract_organizations(texte),
        "port": extract_ports(texte),
    }
    
    # Extraire les hashs
    hashes = extract_hashes(texte)
    for h in hashes:
        if h["type"] == "HASH_MD5":
            entities["hash_md5"].append(h)
        elif h["type"] == "HASH_SHA1":
            entities["hash_sha1"].append(h)
        elif h["type"] == "HASH_SHA256":
            entities["hash_sha256"].append(h)
    
    # Extraire MITRE
    mitre_entities = extract_mitre(texte)
    for m in mitre_entities:
        if m["type"] == "MITRE_TECHNIQUE":
            entities["mitre_technique"].append(m)
        elif m["type"] == "MITRE_TACTIC":
            entities["mitre_tactic"].append(m)
    
    # Nettoyer les doublons
    for key in entities:
        entities[key] = deduplicate_entities(entities[key])
    
    return entities


# ─── Traitement des incidents ─────────────────────────────────────────────

def process_incidents(limit: int = None, apply: bool = False):
    """Traite les incidents pour extraire les entités."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    query = """
        SELECT id, titre, description, type_menace, secteur_cible, raw_data
        FROM cyber_incidents
        WHERE type_menace != 'Inconnu'
    """
    if limit:
        query += f" LIMIT {limit}"
    
    cur.execute(query)
    rows = cur.fetchall()
    
    print(f"\n📊 Traitement de {len(rows)} incidents...")
    
    results = []
    updated = 0
    
    for i, row in enumerate(rows, 1):
        id_incident, titre, description, type_menace, secteur_cible, raw_data = row
        texte = f"{titre} {description or ''}"
        
        # Extraire les entités
        entities = extract_all_entities(texte)
        
        # Filtrer les entités avec confiance > 0.5
        filtered_entities = {}
        for key, values in entities.items():
            filtered_entities[key] = extract_with_confidence(values, threshold=0.5)
        
        # Enrichir raw_data
        if not raw_data:
            raw_data = {}
        raw_data['entities'] = filtered_entities
        raw_data['entity_count'] = {
            key: len(values) for key, values in filtered_entities.items()
        }
        
        results.append({
            "id": id_incident,
            "type_menace": type_menace,
            "secteur_cible": secteur_cible,
            "entities": filtered_entities
        })
        
        # Mise à jour en base
        if apply:
            cur.execute("""
                UPDATE cyber_incidents
                SET raw_data = %s, updated_at = NOW()
                WHERE id = %s
            """, (json.dumps(raw_data, default=str), id_incident))
            updated += 1
        
        if i % 50 == 0:
            print(f"   {i}/{len(rows)} traités...")
    
    if apply:
        conn.commit()
        print(f"✅ {updated} incidents mis à jour")
    
    cur.close()
    conn.close()
    
    return results


# ─── Statistiques ──────────────────────────────────────────────────────────

def generate_stats(results):
    """Génère des statistiques détaillées sur les entités extraites."""
    stats = {
        "total": 0,
        "by_type": defaultdict(int),
        "by_confidence": {"high": 0, "medium": 0, "low": 0},
        "top_cve": defaultdict(int),
        "top_malware": defaultdict(int),
        "top_sector": defaultdict(int),
        "top_country": defaultdict(int),
        "top_mitre": defaultdict(int),
        "top_organization": defaultdict(int),
        "top_ip": defaultdict(int),
        "top_domain": defaultdict(int),
    }
    
    for r in results:
        entities = r.get("entities", {})
        for ent_type, ent_list in entities.items():
            for ent in ent_list:
                stats["total"] += 1
                stats["by_type"][ent_type] += 1
                
                conf = ent.get("confidence", 0)
                if conf >= 0.8:
                    stats["by_confidence"]["high"] += 1
                elif conf >= 0.5:
                    stats["by_confidence"]["medium"] += 1
                else:
                    stats["by_confidence"]["low"] += 1
                
                value = ent.get("value", "")
                if ent_type == "cve":
                    stats["top_cve"][value] += 1
                elif ent_type == "malware":
                    stats["top_malware"][value] += 1
                elif ent_type == "sector":
                    stats["top_sector"][value] += 1
                elif ent_type == "country":
                    stats["top_country"][value] += 1
                elif ent_type == "mitre_technique":
                    stats["top_mitre"][value] += 1
                elif ent_type == "organization" or ent_type == "ORG":
                    stats["top_organization"][value] += 1
                elif ent_type == "ip":
                    stats["top_ip"][value] += 1
                elif ent_type == "domain":
                    stats["top_domain"][value] += 1
    
    print("\n" + "=" * 70)
    print("  📊 STATISTIQUES DÉTAILLÉES DES ENTITÉS EXTRAITES")
    print("=" * 70)
    print(f"  Total entités      : {stats['total']}")
    print(f"  Types d'entités    : {len(stats['by_type'])}")
    print(f"  Confiance élevée   : {stats['by_confidence']['high']}")
    print(f"  Confiance moyenne  : {stats['by_confidence']['medium']}")
    print(f"  Confiance faible   : {stats['by_confidence']['low']}")
    
    print("\n  📌 Répartition par type:")
    for ent_type, count in sorted(stats["by_type"].items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"    {ent_type:<20} : {count}")
    
    if stats["top_cve"]:
        print("\n  🔝 Top CVE:")
        for cve, count in sorted(stats["top_cve"].items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"    {cve:<20} : {count}")
    
    if stats["top_malware"]:
        print("\n  🔝 Top Malwares:")
        for malware, count in sorted(stats["top_malware"].items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"    {malware:<20} : {count}")
    
    if stats["top_sector"]:
        print("\n  🔝 Top Secteurs:")
        for sector, count in sorted(stats["top_sector"].items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"    {sector:<20} : {count}")
    
    if stats["top_country"]:
        print("\n  🔝 Top Pays:")
        for country, count in sorted(stats["top_country"].items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"    {country:<20} : {count}")
    
    if stats["top_mitre"]:
        print("\n  🔝 Top Techniques MITRE:")
        for mitre, count in sorted(stats["top_mitre"].items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"    {mitre:<20} : {count}")
    
    return stats


# ─── Main ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="Limiter le nombre d'incidents")
    parser.add_argument("--apply", action="store_true", help="Appliquer les modifications")
    parser.add_argument("--stats", action="store_true", help="Générer les statistiques")
    args = parser.parse_args()
    
    print("🚀 Lancement de l'extraction NER avancée...")
    
    # Extraire les entités
    results = process_incidents(limit=args.limit, apply=args.apply)
    
    # Générer les statistiques
    if args.stats:
        generate_stats(results)