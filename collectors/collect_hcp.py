# collectors/collect_hcp.py

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.http_retry import get_with_retry

import re
import hashlib
import requests
from datetime import datetime
from typing import List, Dict, Any
from bs4 import BeautifulSoup

from collectors.base_news import BaseNewsCollector
from utils.logger import get_logger

logger = get_logger("collect_hcp")

HCP_SOURCE_NAME = "HCP_Maroc"


class HCPCollector(BaseNewsCollector):

    source_name = HCP_SOURCE_NAME
    langue = "fr"
    pays = "MA"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "fr,fr-FR;q=0.9",
    }

    def collect(self, max_articles: int = 10) -> List[Dict[str, Any]]:
        logger.info(f"Collecte HCP — {max_articles} articles")
        
        urls = [
            "https://www.hcp.ma/Communiques-de-presse_rubrique_r3.html",
            "https://www.hcp.ma/",
            "https://www.hcp.ma/Actualites_rubrique_r2.html",
        ]
        
        for url in urls:
            try:
                articles = self._scrape_communiques(url, max_articles)
                if articles:
                    logger.info(f"HCP: {len(articles)} communiqués trouvés sur {url}")
                    return articles
            except Exception as e:
                logger.warning(f"HCP: erreur sur {url} - {e}")
                continue

        logger.warning("HCP: aucune donnée collectée, utilisation des données démo")
        return self._get_demo_data()

    def _scrape_communiques(self, url: str, max_articles: int) -> List[Dict[str, Any]]:
        """Scrape les communiqués de presse du HCP."""
        articles = []
        
        try:
            resp = get_with_retry(
                url,
                headers=self.HEADERS,
                timeout=15,
                tentatives=3,
                backoff_seconds=3.0,
                logger_prefix="HCP",
                verify=False
            )
            
            if resp.status_code != 200:
                logger.warning(f"HCP: HTTP {resp.status_code} sur {url}")
                return []
            
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Stratégie 1: Chercher les communiqués
            communiques = []
            
            # Chercher les liens vers des communiqués
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                titre = a.get_text(strip=True)
                
                if not titre or len(titre) < 10:
                    continue
                
                # Filtrer les communiqués
                if "communique" in href.lower() or "communique" in titre.lower():
                    communiques.append((a, href, titre))
                elif "actualites" in href.lower() and "communique" in href.lower():
                    communiques.append((a, href, titre))
            
            # Stratégie 2: Chercher les blocs d'actualités
            if not communiques:
                for elem in soup.find_all(["article", "div"], class_=re.compile(r"article|actu|news|item|communique")):
                    a = elem.find("a", href=True)
                    if a:
                        titre = a.get_text(strip=True)
                        href = a["href"]
                        if titre and len(titre) > 10:
                            communiques.append((a, href, titre))
            
            logger.info(f"HCP: trouvé {len(communiques)} communiqués")
            
            for a, href, titre in communiques[:max_articles]:
                # Construire l'URL absolue
                if href.startswith("/"):
                    url_article = "https://www.hcp.ma" + href
                elif href.startswith("http"):
                    url_article = href
                else:
                    url_article = "https://www.hcp.ma/" + href.lstrip("/")
                
                # Extraire la date et la description
                date_incident = datetime.now()
                description = ""
                
                parent = a.find_parent(["article", "div", "li"])
                if parent:
                    # Date
                    date_elem = parent.find(["span", "div"], class_=re.compile(r"date|time|publi"))
                    if date_elem:
                        date_text = date_elem.get_text(strip=True)
                        try:
                            date_incident = datetime.strptime(date_text, "%d/%m/%Y")
                        except:
                            try:
                                date_incident = datetime.strptime(date_text, "%Y-%m-%d")
                            except:
                                pass
                    
                    # Description
                    desc_elem = parent.find("p")
                    if desc_elem:
                        description = desc_elem.get_text(strip=True)[:500]
                
                # Si pas de description, aller chercher l'article
                if not description:
                    description = self._fetch_article_summary(url_article)
                
                articles.append({
                    "source_ext_id": hashlib.sha256(f"HCP|{url_article}".encode()).hexdigest()[:32],
                    "titre": titre[:300],
                    "description": description[:1000] if description else f"Communiqué du HCP: {titre}",
                    "date_publication": date_incident,
                    "categorie": "Economie",
                    "url_source": url_article,
                    "raw_data": {"source": "HCP", "titre": titre},
                })
            
        except Exception as e:
            logger.error(f"HCP erreur: {e}")
        
        return articles

    def _fetch_article_summary(self, url: str) -> str:
        """Récupère le résumé d'un article."""
        try:
            resp = get_with_retry(
                url,
                headers=self.HEADERS,
                timeout=10,
                tentatives=3,
                backoff_seconds=3.0,
                logger_prefix="HCP",
                verify=False
            )
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Chercher le contenu
            content = soup.find("article") or soup.find("main") or soup.find("div", class_=re.compile(r"content|body|texte|article"))
            if content:
                paragraphs = content.find_all("p")
                text = " ".join(p.get_text(strip=True) for p in paragraphs[:3])
                return text[:500] if text else ""
            
            # Fallback: premier paragraphe conséquent
            for p in soup.find_all("p"):
                text = p.get_text(strip=True)
                if len(text) > 50:
                    return text[:500]
                    
        except Exception:
            pass
        return ""

    def _get_demo_data(self) -> List[Dict[str, Any]]:
        """Données de démonstration."""
        logger.info("HCP: utilisation des données de démonstration")
        return [
            {
                "source_ext_id": "demo_hcp_001",
                "titre": "HCP - Croissance économique des PME marocaines",
                "description": "Le HCP publie les chiffres de la croissance des PME au Maroc. Le secteur du BTP connaît une hausse de 5,2% et le secteur des services de 4,8%.",
                "date_publication": datetime(2026, 6, 15),
                "categorie": "Economie",
                "url_source": "https://www.hcp.ma",
                "raw_data": {"source": "demo"},
            },
            {
                "source_ext_id": "demo_hcp_002",
                "titre": "HCP - Emploi et digitalisation des PME",
                "description": "La digitalisation des PME marocaines crée 15 000 nouveaux emplois en 2026. Les secteurs les plus dynamiques sont les services et le commerce.",
                "date_publication": datetime(2026, 6, 1),
                "categorie": "Emploi",
                "url_source": "https://www.hcp.ma",
                "raw_data": {"source": "demo"},
            },
            {
                "source_ext_id": "demo_hcp_003",
                "titre": "HCP - Investissements dans le secteur numérique",
                "description": "Les investissements dans le numérique au Maroc augmentent de 12% en 2026, soutenus par les stratégies gouvernementales.",
                "date_publication": datetime(2026, 5, 20),
                "categorie": "Numérique",
                "url_source": "https://www.hcp.ma",
                "raw_data": {"source": "demo"},
            },
        ]


if __name__ == "__main__":
    print("=" * 60)
    print("  TEST DU COLLECTEUR HCP")
    print("=" * 60)
    
    collector = HCPCollector()
    result = collector.run(max_articles=5)
    
    print("\n" + "=" * 60)
    print("  RÉSULTAT")
    print("=" * 60)
    print(f"  Source: {result.get('source')}")
    print(f"  Alertes trouvées: {result.get('alertes_trouvees', 0)}")
    print(f"  Nouvelles insérées: {result.get('nouvelles_inserees', 0)}")
    print(f"  Statut: {result.get('statut')}")
    print("=" * 60)