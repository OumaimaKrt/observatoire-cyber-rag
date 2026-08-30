# collectors/collect_anrt.py
# =============================================================================
# Collecteur ANRT — Actualités et communiqués de presse
# Version sans Selenium (requests + BeautifulSoup)
# =============================================================================
import sys
import os
import re
import hashlib
import requests
from datetime import datetime
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from utils.http_retry import get_with_retry

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collectors.base_news import BaseNewsCollector
from utils.logger import get_logger

logger = get_logger("collect_anrt")

ANRT_SOURCE_NAME = "ANRT_Maroc"

ANRT_URL = "https://www.anrt.ma/lagence/actualites"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
    "Accept-Language": "fr,fr-FR;q=0.9,en;q=0.8",
}

# Mots-clés pour filtrer les articles pertinents
MOTS_CLES_CYBER = [
    "cyber", "sécurité", "securite", "cybersécurité", "cybersecurite",
    "cyberattaque", "piratage", "hacker", "virus", "malware",
    "ransomware", "phishing", "hameçonnage", "vulnérabilité", "vulnerabilite",
    "faille", "exploit", "zero-day", "CVE", "backdoor",
    "données", "donnees", "protection", "confidentialité", "confidentialite",
    "RGPD", "DGSSI", "ANRT", "CNDP", "CNPD",
    "numérique", "numerique", "digital", "infrastructure",
    "réseau", "reseau", "telecom", "5G", "fibre",
    "attaque", "menace", "intrusion", "espionnage",
]


class ANRTCollector(BaseNewsCollector):
    """Collecteur ANRT sans Selenium (requests + BeautifulSoup)."""

    source_name = ANRT_SOURCE_NAME
    langue = "fr"
    pays = "MA"
    categorie_defaut = "Telecom"

    def collect(self, max_articles: int = 10) -> List[Dict[str, Any]]:
        logger.info(f"Collecte ANRT — {max_articles} articles")
        articles = []
        urls_vues = set()
        nb_rejetes = 0

        try:
            logger.info(f"ANRT: collecte FR — {ANRT_URL}")
            
            # Récupérer la page avec requests
            resp = get_with_retry(
                ANRT_URL,
                headers=HEADERS,
                timeout=15,
                tentatives=3,
                backoff_seconds=3.0,
                logger_prefix="ANRT"
            )
            
            if resp is None:
                logger.error("ANRT: échec de la requête")
                return []
            
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Trouver les liens vers les articles
            articles_found = []
            
            # Stratégie 1: Balises article
            for article in soup.find_all("article"):
                articles_found.append(article)
            
            # Stratégie 2: Liens vers /lagence/actualites/
            if not articles_found:
                for a in soup.find_all("a", href=True):
                    href = a.get("href", "")
                    titre = a.get_text(strip=True)
                    if "/lagence/actualites/" in href and titre and len(titre) > 10:
                        if href != "/lagence/actualites":
                            articles_found.append(a)
            
            # Stratégie 3: Div avec classes
            if not articles_found:
                for div in soup.find_all("div", class_=re.compile(r"article|news|item|post|actualite")):
                    if div.find("a", href=True):
                        articles_found.append(div)
            
            logger.info(f"ANRT: {len(articles_found)} éléments trouvés")
            
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
                
                # Construire l'URL absolue
                if href.startswith("/"):
                    url_article = "https://www.anrt.ma" + href
                elif href.startswith("http"):
                    url_article = href
                else:
                    url_article = ANRT_URL + href
                
                if url_article in urls_vues:
                    continue
                urls_vues.add(url_article)
                
                # Extraire la date
                date_publication = datetime.now()
                parent = a.find_parent(["article", "div", "li"])
                if parent:
                    date_elem = parent.find(["time", "span"], class_=re.compile(r"date|time|publi"))
                    if date_elem:
                        date_text = date_elem.get_text(strip=True)
                        try:
                            date_publication = datetime.strptime(date_text, "%d/%m/%Y")
                        except:
                            try:
                                date_publication = datetime.strptime(date_text, "%Y-%m-%d")
                            except:
                                pass
                
                # Extraire la description
                description = ""
                if parent:
                    p = parent.find("p")
                    if p:
                        description = p.get_text(strip=True)[:500]
                
                # Si pas de description, aller chercher l'article
                if not description:
                    description = self._fetch_article_description(url_article)
                
                # FILTRE CYBERSÉCURITÉ
                texte_complet = f"{titre} {description}".lower()
                est_pertinent = any(mot.lower() in texte_complet for mot in MOTS_CLES_CYBER)
                
                if not est_pertinent:
                    nb_rejetes += 1
                    continue
                
                source_ext_id = hashlib.sha256(f"ANRT|{url_article}".encode()).hexdigest()[:32]
                
                articles.append({
                    "source_ext_id": source_ext_id,
                    "titre": titre[:300],
                    "description": description[:500],
                    "date_publication": date_publication,
                    "categorie": "Telecom",
                    "url_source": url_article,
                    "raw_data": {
                        "source": "ANRT",
                        "langue": "fr",
                        "titre": titre,
                        "url": url_article,
                    },
                })
            
        except requests.exceptions.RequestException as e:
            logger.error(f"ANRT erreur réseau: {e}")
        except Exception as e:
            logger.error(f"ANRT erreur: {e}")

        if nb_rejetes:
            logger.info(f"ANRT: {nb_rejetes} article(s) rejeté(s) (hors cybersécurité)")

        if not articles:
            logger.warning("ANRT: aucun article collecté")
            return []
        
        logger.info(f"ANRT: {len(articles)} articles collectés")
        return articles

    def _fetch_article_description(self, url: str) -> str:
        """Récupère la description d'un article."""
        try:
            resp = requests.get(url, timeout=10, headers=HEADERS)
            soup = BeautifulSoup(resp.text, "html.parser")
            
            content = soup.find("article") or soup.find("main") or soup.find("div", class_=re.compile(r"content|body|texte"))
            if content:
                paragraphs = content.find_all("p")
                text = " ".join(p.get_text(strip=True) for p in paragraphs[:3])
                return text[:500] if text else ""
            
            for p in soup.find_all("p"):
                text = p.get_text(strip=True)
                if len(text) > 50:
                    return text[:500]
                    
        except Exception:
            pass
        return ""


if __name__ == "__main__":
    print("=" * 60)
    print("  TEST DU COLLECTEUR ANRT (sans Selenium)")
    print("=" * 60)
    
    collector = ANRTCollector()
    result = collector.run(max_articles=5)
    
    print("\n" + "=" * 60)
    print("  RÉSULTAT")
    print("=" * 60)
    print(f"  Source: {result.get('source')}")
    print(f"  Alertes trouvées: {result.get('alertes_trouvees', 0)}")
    print(f"  Nouvelles insérées: {result.get('nouvelles_inserees', 0)}")
    print(f"  Statut: {result.get('statut')}")
    print("=" * 60)