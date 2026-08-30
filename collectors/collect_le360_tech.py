# collectors/collect_le360.py

import sys
import os
import re
import hashlib
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from utils.http_retry import get_with_retry

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collectors.base_news import BaseNewsCollector
from config import LE360_URL, REQUEST_TIMEOUT
from utils.logger import get_logger

logger = get_logger("collect_le360")

LE360_SOURCE_NAME = "Le360_Maroc"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "fr,fr-FR;q=0.9,en;q=0.8",
}

# MOTS-CLÉS ÉLARGIS
MOTS_CLES_CYBER = [
    "cyber", "cybersécurité", "cybersecurite", "cyberattaque", "cyber-attaque",
    "cybercriminalité", "cybercriminalite", "cybermenace", "cybermenaces",
    "sécurité", "securite", "attaque", "piratage", "hacker", "hacking",
    "virus", "malware", "ransomware", "phishing", "hameçonnage",
    "spoofing", "usurpation", "vulnérabilité", "vulnerabilite", "faille",
    "exploit", "zero-day", "données", "donnees", "protection",
    "confidentialité", "confidentialite", "RGPD", "CNPD", "CNDP",
    "DGSSI", "ANRT", "numérique", "numerique", "digital",
    "transformation numérique", "intelligence artificielle", "IA",
    "cloud", "infrastructure", "internet", "réseau", "reseau",
    "ordinateur", "smartphone", "application", "logiciel", "plateforme",
    "arnaque", "fraude", "escroquerie", "colis", "livraison",
    "faux", "contrefaçon", "contrefacon", "banque", "finance",
    "paiement", "transaction", "PME", "entreprise", "startup",
    "alerte", "vigilance", "recommandation", "mise en garde",
    "prévention", "prevention", "protection", "mesure",
]


def parse_date_le360(date_text: str) -> Optional[datetime]:
    """Parse les dates au format Le360."""
    if not date_text:
        return None
    
    date_text = date_text.strip()
    
    # Format 1: "Le 06/07/2026 à 02h57"
    match = re.search(r'(\d{2})/(\d{2})/(\d{4})', date_text)
    if match:
        try:
            return datetime(int(match.group(3)), int(match.group(2)), int(match.group(1)))
        except ValueError:
            pass
    
    # Format 2: "mardi 7 juillet 2026"
    mois_fr = {
        "janvier": 1, "février": 2, "mars": 3, "avril": 4,
        "mai": 5, "juin": 6, "juillet": 7, "août": 8,
        "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12,
    }
    match = re.search(r'(\d{1,2})\s+([a-zà-ÿ]+)\s+(\d{4})', date_text, re.I)
    if match:
        jour = int(match.group(1))
        mois = mois_fr.get(match.group(2).lower())
        if mois:
            try:
                return datetime(int(match.group(3)), mois, jour)
            except ValueError:
                pass
    
    return None


def extraire_date_depuis_article(url: str) -> Optional[datetime]:
    """
    Scrape la page de l'article pour en extraire la date de publication.
    """
    try:
        resp = requests.get(url, timeout=15, headers=HEADERS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Chercher la date dans plusieurs endroits
        patterns = [
            # Balise time avec attribut datetime
            lambda s: s.find("time", {"datetime": True}),
            # Span avec classe date
            lambda s: s.find("span", class_=re.compile(r"date|time|publi|published|meta")),
            # Div avec classe date
            lambda s: s.find("div", class_=re.compile(r"date|time|publi|published|meta")),
            # Paragraphe contenant "Le JJ/MM/AAAA"
            lambda s: s.find(string=re.compile(r'Le\s+\d{2}/\d{2}/\d{4}')),
        ]
        
        for pattern in patterns:
            elem = pattern(soup)
            if elem:
                if isinstance(elem, str):
                    date_text = elem
                else:
                    date_text = elem.get_text(strip=True)
                parsed = parse_date_le360(date_text)
                if parsed:
                    return parsed
        
        # Chercher dans le texte de l'article
        for p in soup.find_all("p"):
            text = p.get_text(strip=True)
            if re.search(r'Le\s+\d{2}/\d{2}/\d{4}', text):
                parsed = parse_date_le360(text)
                if parsed:
                    return parsed
                    
    except Exception as e:
        logger.debug(f"Erreur extraction date depuis {url}: {e}")
    
    return None


class Le360Collector(BaseNewsCollector):
    """
    Collecteur pour Le360 Maroc — Articles tech et cybersécurité.
    """
    source_name = LE360_SOURCE_NAME
    langue = "fr"
    pays = "MA"
    categorie_defaut = "Actualite"

    def collect(self, max_articles: int = 20) -> List[Dict[str, Any]]:
        logger.info(f"Collecte Le360 — {max_articles} articles")
        articles = []
        urls_vues = set()
        nb_rejetes = 0

        urls_a_scraper = [
            LE360_URL,
            "https://fr.le360.ma/economie",
            "https://fr.le360.ma/societe",
        ]

        for url_base in urls_a_scraper:
            if len(articles) >= max_articles:
                break

            try:
                resp = get_with_retry(
                    url_base,
                    headers=HEADERS,
                    timeout=REQUEST_TIMEOUT,
                    tentatives=3,
                    backoff_seconds=3.0,
                    logger_prefix=self.source_name
                )
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
                
                articles_found = []
                
                # Stratégie 1: Tous les liens vers des articles
                for a in soup.find_all("a", href=True):
                    href = a.get("href", "")
                    titre = a.get_text(strip=True)
                    
                    if "/economie/" in href or "/societe/" in href:
                        if not href.endswith("/economie") and not href.endswith("/societe"):
                            if titre and len(titre) > 10:
                                articles_found.append(a)
                
                # Stratégie 2: Balises article
                if not articles_found:
                    for article in soup.find_all("article"):
                        articles_found.append(article)
                
                # Stratégie 3: Div avec classes
                if not articles_found:
                    for div in soup.find_all("div", class_=re.compile(r"col|row|block|card|item|post|article|content|main")):
                        if div.find("a", href=True):
                            articles_found.append(div)
                
                logger.info(f"Le360 [{url_base}]: {len(articles_found)} éléments trouvés")
                
                for element in articles_found[:max_articles * 3]:
                    if element.name == "a":
                        a = element
                        titre = a.get_text(strip=True)
                        href = a.get("href", "")
                    else:
                        a = element.find("a", href=True)
                        if not a:
                            continue
                        titre = a.get_text(strip=True)
                        href = a["href"]
                    
                    if not titre or len(titre) < 10:
                        continue
                    
                    if href.startswith("/"):
                        url_article = "https://fr.le360.ma" + href
                    elif href.startswith("http"):
                        url_article = href
                    else:
                        url_article = url_base + href
                    
                    if url_article in urls_vues:
                        continue
                    urls_vues.add(url_article)
                    
                    # Extraire la date depuis la page de l'article
                    date_publication = extraire_date_depuis_article(url_article) or datetime.now()
                    
                    # Extraire la description
                    description = ""
                    if element.name != "a":
                        p = element.find("p")
                        if p:
                            description = p.get_text(strip=True)[:500]
                    
                    # FILTRE CYBERSÉCURITÉ
                    texte_complet = f"{titre} {description}".lower()
                    est_pertinent = any(mot.lower() in texte_complet for mot in MOTS_CLES_CYBER)
                    
                    if not est_pertinent:
                        nb_rejetes += 1
                        continue
                    
                    source_ext_id = hashlib.sha256(f"{LE360_SOURCE_NAME}|{url_article}".encode()).hexdigest()[:32]
                    
                    articles.append({
                        "source_ext_id": source_ext_id,
                        "titre": titre[:300],
                        "description": description[:500],                    "date_publication": date_publication,
                        "categorie": "Actualite",
                        "url_source": url_article,
                        "raw_data": {
                            "source": "Le360",
                            "langue": "fr",
                            "titre": titre,
                            "url": url_article,
                        },
                    })
                    
                    if len(articles) >= max_articles:
                        break
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"Le360 [{url_base}] erreur: {e}")
            except Exception as e:
                logger.warning(f"Le360 [{url_base}] erreur inattendue: {e}")

        if nb_rejetes:
            logger.info(f"Le360: {nb_rejetes} article(s) rejeté(s) (hors cybersécurité)")

        if not articles:
            logger.warning("Le360: aucun article collecté")
            return []
        
        logger.info(f"Le360: {len(articles)} articles collectés")
        return articles


if __name__ == "__main__":
    print("=" * 60)
    print("  TEST DU COLLECTEUR LE360")
    print("=" * 60)
    
    collector = Le360Collector()
    result = collector.run(max_articles=10)
    
    print("\n" + "=" * 60)
    print("  RÉSULTAT")
    print("=" * 60)
    print(f"  Source: {result.get('source')}")
    print(f"  Alertes trouvées: {result.get('alertes_trouvees', 0)}")
    print(f"  Nouvelles insérées: {result.get('nouvelles_inserees', 0)}")
    print(f"  Statut: {result.get('statut')}")
    print("=" * 60)