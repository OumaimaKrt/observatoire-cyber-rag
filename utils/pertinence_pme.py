# utils/pertinence_pme.py
# =============================================================================
# Scoring de pertinence PME — Observatoire cybermenaces PME Maroc
# =============================================================================

from typing import List, Tuple
import re

_CACHE_REGEX = {}


def _regex_mot_entier(mot_cle: str) -> "re.Pattern":
    if mot_cle not in _CACHE_REGEX:
        _CACHE_REGEX[mot_cle] = re.compile(r"\b" + re.escape(mot_cle) + r"\b")
    return _CACHE_REGEX[mot_cle]


def _matches_sans_doublon(mots_cles: List[str], texte_lower: str) -> List[str]:
    """Retourne les mots-clés trouvés, dans l'ordre, sans doublon."""
    trouves = []
    for mot_cle in mots_cles:
        if mot_cle not in trouves and _regex_mot_entier(mot_cle).search(texte_lower):
            trouves.append(mot_cle)
    return trouves

# ─── HAUTE pertinence ────────────────────────────────────────────────────────
# Technologies très majoritairement utilisées par les TPE/PME marocaines :
# hébergement mutualisé, CMS/e-commerce grand public, logiciels de gestion
# accessibles, accès distant basique, messagerie bureautique standard.

TECH_HAUTE = [
    # CMS et e-commerce (très courants en PME)
    "wordpress", "woocommerce", "prestashop", "phpmyadmin", "cpanel", "plesk",
    "joomla", "opencart", "magento", "elementor", "wp plugin", "wordpress plugin",
    "drupal", "shopify",
    # Logiciels de gestion
    "sage", "odoo", "quickbooks", "tally", "sap business one",
    # Messagerie
    "roundcube", "rainloop", "webmail", "squirrelmail",
    "microsoft 365", "office 365", "exchange server", "outlook web access", "owa",
    # Accès distant
    "rdp", "remote desktop protocol", "teamviewer", "anydesk", "vnc",
    # Serveurs FTP
    "ftp server", "filezilla", "vsftpd", "proftpd",
    # Bases de données courantes
    "mysql", "mariadb", "phpmailer", "mongodb", "elasticsearch", "elastic",
    "postgresql",
    # Plugins WordPress courants
    "contact form 7", "yoast", "akismet", "jetpack", "woocommerce",
    # Hébergement
    "hosting", "hébergement", "mutualisé", "shared hosting", "ovh", "gandi",
    "site web", "site internet", "boutique en ligne", "e-commerce",
    "logiciel de gestion", "crm", "gestion commerciale", "gestion de stock",
    "facturation", "devis", "comptabilité", "paie",
]

TECH_MOYENNE = [
    # Serveurs
    "apache", "nginx", "php", "docker", "linux kernel",
    "windows server", "active directory", "iis",
    # Sécurité
    "fortinet", "fortigate", "pfsense", "sonicwall", "checkpoint", "palo alto",
    # Réseau
    "tp-link", "d-link", "mikrotik", "netgear", "asus router",
    "cisco", "vmware", "citrix", "proxmox",
    # VPN
    "vpn", "openvpn", "wireguard", "ipsec", "ssl vpn",
    # Logiciels
    "adobe", "java", "android", "chrome", "firefox", "edge",
    "zoom", "teams", "slack", "google workspace", "google drive",
    "dropbox", "onedrive",
    # Stockage
    "nas", "synology", "qnap", "western digital", "seagate",
    "serveur", "réseau", "pare-feu", "firewall", "antivirus",
    "sauvegarde", "backup", "cloud", "infrastructure",
    "téléphonie", "voip", "sip",
]


# ─── HAUTE pertinence entreprise (mots-clés marocains) ──────────────────────

TECH_HAUTE_MAROC = [
    "pme", "tpme", "pme maroc", "petite entreprise", "moyenne entreprise",
    "très petite entreprise", "artisan", "commerçant", "auto-entrepreneur",
    "boutique", "magasin", "commerce de proximité", "commerce en ligne",
    "site vitrine", "blog", "association",
]

TECH_MOYENNE_MAROC = [
    "entreprise", "société", "sarl", "sa", "holding",
    "maroc", "casablanca", "rabat", "tanger", "agadir", "marrakech",
    "fès", "meknès", "tétouan", "oujda", "kenitra", "salé",
]


def evaluer_pertinence_pme(texte: str) -> Tuple[str, List[str]]:
    """
    Évalue la pertinence PME d'un texte.
    Retourne (niveau, [technologies trouvées]).
    
    Niveaux:
    - HAUTE: Technologies très spécifiques aux PME (CMS, e-commerce, gestion)
    - MOYENNE: Technologies plus généralistes
    - FAIBLE: Aucune technologie PME détectée
    """
    if not texte or not texte.strip():
        return "INCONNUE", []

    texte_lower = texte.lower().replace("_", " ")

    # 1. Vérifier les mots-clés marocains PME (prioritaires)
    matches_maroc = _matches_sans_doublon(TECH_HAUTE_MAROC, texte_lower)
    if matches_maroc:
        # Si le texte mentionne explicitement "PME", on vérifie aussi les technos
        matches_haute = _matches_sans_doublon(TECH_HAUTE, texte_lower)
        if matches_haute:
            return "HAUTE", matches_haute + matches_maroc
        # Sinon, on vérifie les technos moyennes
        matches_moyenne = _matches_sans_doublon(TECH_MOYENNE, texte_lower)
        if matches_moyenne:
            return "MOYENNE", matches_moyenne + matches_maroc
        # Si aucune techno, mais mention PME → HAUTE par défaut
        return "HAUTE", matches_maroc

    # 2. Vérifier les technologies haute
    matches_haute = _matches_sans_doublon(TECH_HAUTE, texte_lower)
    if matches_haute:
        return "HAUTE", matches_haute

    # 3. Vérifier les technologies moyennes
    matches_moyenne = _matches_sans_doublon(TECH_MOYENNE, texte_lower)
    if matches_moyenne:
        return "MOYENNE", matches_moyenne

    # 4. Vérifier les mots-clés marocains de niveau moyen
    matches_maroc_moyen = _matches_sans_doublon(TECH_MOYENNE_MAROC, texte_lower)
    if matches_maroc_moyen:
        return "MOYENNE", matches_maroc_moyen

    return "FAIBLE", []


def evaluer_pertinence_pme_simple(texte: str) -> str:
    """Version simplifiée : ne retourne que le niveau (sans le détail techno)."""
    niveau, _ = evaluer_pertinence_pme(texte)
    return niveau


# ─── Test rapide ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        ("WordPress vulnerability in plugin", "HAUTE"),
        ("Banking trojan targeting financial institutions", "FAIBLE"),
        ("PME marocaine victime d'un ransomware", "HAUTE"),
        ("Apache server misconfiguration in Moroccan company", "MOYENNE"),
        ("Cyberattack on e-commerce site", "HAUTE"),
        ("Industrial control system vulnerability", "MOYENNE"),
    ]
    
    print("=" * 60)
    print("  TEST PERTINENCE PME")
    print("=" * 60)
    for texte, attendu in tests:
        niveau, techs = evaluer_pertinence_pme(texte)
        print(f"  {niveau:8} | {attendu:8} | {texte[:50]}...")
        if techs:
            print(f"             → {', '.join(techs[:3])}")
    print("=" * 60)