# collectors/collect_leconomiste.py
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
from config import LECONOMISTE_TECH_URL, REQUEST_TIMEOUT
from utils.logger import get_logger

logger = get_logger("collect_leconomiste")

LECONOMISTE_SOURCE_NAME = "LEconomiste_Tech"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "fr,fr-FR;q=0.9,en;q=0.8",
}

MOTS_CLES_CYBER = [
    "cyber", "sécurité", "securite", "cybersécurité", "cybersecurite",
    "cyberattaque", "piratage", "hacker", "virus", "malware",
    "ransomware", "phishing", "hameçonnage", "vulnérabilité",
    "données", "donnees", "protection", "RGPD", "CNPD", "CNDP",
    "DGSSI", "ANRT", "numérique", "numerique", "digital",
    "transformation numérique", "intelligence artificielle", "IA",
    "cloud", "internet", "réseau", "reseau", "banque", "finance",
    "paiement", "transaction", "PME", "startup",
]


class LEconomisteCollector(BaseNewsCollector):
    source_name = LECONOMISTE_SOURCE_NAME
    langue = "fr"
    pays = "MA"
    categorie_defaut = "Technologie"

    def collect(self, max_articles: int = 15) -> List[Dict[str, Any]]:
        logger.info(f"Collecte L'Économiste — {max_articles} articles")
        articles = []
        urls_vues = set()
        nb_rejetes = 0

        url_base = LECONOMISTE_TECH_URL

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
            
            # Stratégie 1: Balises article
            for article in soup.find_all("article"):
                articles_found.append(article)
            
            # Stratégie 2: Liens vers des articles
            if not articles_found:
                for a in soup.find_all("a", href=True):
                    href = a.get("href", "")
                    titre = a.get_text(strip=True)
                    if "/technologie/" in href and titre and len(titre) > 10:
                        articles_found.append(a)
            
            logger.info(f"L'Économiste: {len(articles_found)} éléments trouvés")
            
            for element in articles_found[:max_articles * 2]:
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
                    url_article = "https://www.leconomiste.com" + href
                elif href.startswith("http"):
                    url_article = href
                else:
                    url_article = LECONOMISTE_TECH_URL + href
                
                if url_article in urls_vues:
                    continue
                urls_vues.add(url_article)
                
                date_publication = None
                date_elem = element.find(["time", "span"], class_=re.compile(r"date|time|meta|publi"))
                if date_elem:
                    for candidat in (date_elem.get("datetime"), date_elem.get_text(strip=True)):
                        if candidat:
                            parsed = parse_date_leconomiste(candidat)
                            if parsed:
                                date_publication = parsed
                                break
                if date_publication is None:
                    date_publication = extraire_date_depuis_article_leconomiste(url_article) or datetime.now()
                
                description = ""
                if element.name != "a":
                    p = element.find("p")
                    if p:
                        description = p.get_text(strip=True)[:500]
                
                texte_complet = f"{titre} {description}".lower()
                if not any(mot.lower() in texte_complet for mot in MOTS_CLES_CYBER):
                    nb_rejetes += 1
                    continue
                
                source_ext_id = hashlib.sha256(f"{LECONOMISTE_SOURCE_NAME}|{url_article}".encode()).hexdigest()[:32]
                
                articles.append({
                    "source_ext_id": source_ext_id,
                    "titre": titre[:300],
                    "description": description[:500],
                    "date_publication": date_publication,
                    "categorie": "Technologie",
                    "url_source": url_article,
                    "raw_data": {
                        "source": "LEconomiste",
                        "langue": "fr",
                        "titre": titre,
                        "url": url_article,
                    },
                })
                
        except Exception as e:
            logger.error(f"L'Économiste erreur: {e}")

        if nb_rejetes:
            logger.info(f"L'Économiste: {nb_rejetes} article(s) rejeté(s)")

        if not articles:
            logger.warning("L'Économiste: aucun article collecté")
            return []
        
        logger.info(f"L'Économiste: {len(articles)} articles collectés")
        return articles


def _date_est_plausible(date: datetime) -> bool:
    return 2023 <= date.year and date <= datetime.now()


def extraire_date_depuis_article_leconomiste(url: str) -> Optional[datetime]:
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        texte_page = soup.get_text(" ", strip=True)
        match = re.search(r"Edition\s*N°\s*:\s*\d+\s*Le\s+(\d{2}/\d{2}/\d{4})", texte_page)
        if match:
            parsed = parse_date_leconomiste(match.group(1))
            if parsed:
                return parsed

        for time_tag in soup.find_all("time"):
            for candidat in (time_tag.get("datetime"), time_tag.get_text(strip=True)):
                if candidat:
                    parsed = parse_date_leconomiste(candidat)
                    if parsed:
                        return parsed
    except Exception:
        pass
    return None


def parse_date_leconomiste(date_text: str) -> Optional[datetime]:
    if not date_text:
        return None
    date_text = date_text.strip()

    # Format ISO 8601 (attribut datetime="")
    try:
        d = datetime.fromisoformat(date_text.replace("Z", "+00:00")).replace(tzinfo=None)
        if _date_est_plausible(d):
            return d
    except ValueError:
        pass

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
    
    match = re.search(r'(\d{2})/(\d{2})/(\d{4})', date_text)
    if match:
        try:
            return datetime(int(match.group(3)), int(match.group(2)), int(match.group(1)))
        except ValueError:
            pass
    
    return None


if __name__ == "__main__":
    print("=" * 60)
    print("  TEST DU COLLECTEUR L'ÉCONOMISTE")
    print("=" * 60)
    
    collector = LEconomisteCollector()
    result = collector.run(max_articles=10)
    
    print("\n" + "=" * 60)
    print("  RÉSULTAT")
    print("=" * 60)
    print(f"  Source: {result.get('source')}")
    print(f"  Alertes trouvées: {result.get('alertes_trouvees', 0)}")
    print(f"  Nouvelles insérées: {result.get('nouvelles_inserees', 0)}")
    print(f"  Statut: {result.get('statut')}")
    print("=" * 60)