# collectors/collect_challenge.py
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
from config import CHALLENGE_TECH_URL, REQUEST_TIMEOUT
from utils.logger import get_logger

logger = get_logger("collect_challenge")

CHALLENGE_SOURCE_NAME = "Challenge_Tech"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "fr,fr-FR;q=0.9,en;q=0.8",
}

MOTS_CLES_CYBER = [
    "cyber", "sécurité", "securite", "cybersécurité", "cybersecurite",
    "cyberattaque", "cyber-attaque", "cybercriminalité", "cybercriminalite",
    "cybermenace", "cybermenaces", "piratage", "hacker", "hacking",
    "virus", "malware", "ransomware", "phishing", "hameçonnage",
    "vulnérabilité", "vulnerabilite", "faille", "exploit", "zero-day",
    "données", "donnees", "protection", "confidentialité", "confidentialite",
    "RGPD", "CNPD", "CNDP", "DGSSI", "ANRT",
    "numérique", "numerique", "digital", "transformation numérique",
    "intelligence artificielle", "IA", "cloud", "infrastructure",
    "internet", "réseau", "reseau", "banque", "finance",
    "paiement", "transaction", "PME", "startup", "start-up",
    "innovation", "technologie", "5G", "data", "données personnelles",
    "fuite", "attaque", "menace", "protection des données",
    "digital nation", "maroc digital", "cyber resilience",
]


class ChallengeCollector(BaseNewsCollector):
    source_name = CHALLENGE_SOURCE_NAME
    langue = "fr"
    pays = "MA"
    categorie_defaut = "Technologie"

    def collect(self, max_articles: int = 15) -> List[Dict[str, Any]]:
        logger.info(f"Collecte Challenge.ma — {max_articles} articles")
        articles = []
        urls_vues = set()
        nb_rejetes = 0

        url_base = CHALLENGE_TECH_URL

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
            
            # Stratégie 1: Liens vers des articles (plus fiable pour Challenge)
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                titre = a.get_text(strip=True)
                
                # Challenge a des URLs 
                if "/" in href and len(href) > 20 and href.count("/") >= 2:
                    if "tech-numerique" not in href and "category" not in href and "tag" not in href:
                        if titre and len(titre) > 15:
                            articles_found.append(a)
            
            # Stratégie 2: Balises article
            if not articles_found:
                for article in soup.find_all("article"):
                    articles_found.append(article)
            
            # Stratégie 3: Div avec classes
            if not articles_found:
                for div in soup.find_all("div", class_=re.compile(r"post|article|item|card|block|entry|news")):
                    if div.find("a", href=True):
                        articles_found.append(div)
            
            logger.info(f"Challenge: {len(articles_found)} éléments trouvés")
            
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
                    url_article = "https://www.challenge.ma" + href
                elif href.startswith("http"):
                    url_article = href
                else:
                    url_article = CHALLENGE_TECH_URL + href
                
                if url_article in urls_vues:
                    continue
                urls_vues.add(url_article)
                
                # Extraire la date
                date_publication = None
                date_text = None
                
                # Chercher la date dans plusieurs endroits
                date_elem = element.find(["time", "span"], class_=re.compile(r"date|time|meta|publi|published"))
                if date_elem:
                    date_text = date_elem.get("datetime") or date_elem.get_text(strip=True)
                else:
                    # Chercher dans le texte de l'élément
                    texte = element.get_text()
                    # Format: "16 juin 2026"
                    match = re.search(r'(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+(\d{4})', texte, re.I)
                    if match:
                        date_text = match.group(0)
                
                if date_text:
                    parsed = parse_date_challenge(date_text)
                    if parsed:
                        date_publication = parsed

                if date_publication is None:
                    # La page de liste n'a rien donné : on va chercher la
                    # date sur la page de l'article plutôt que de retomber
                    # silencieusement sur "aujourd'hui".
                    date_publication = extraire_date_depuis_article_challenge(url_article) or datetime.now()
                
                # Extraire la description
                description = ""
                if element.name != "a":
                    p = element.find("p")
                    if p:
                        description = p.get_text(strip=True)[:500]
                    else:
                        excerpt = element.find(class_=re.compile(r"excerpt|summary|description|chapo"))
                        if excerpt:
                            description = excerpt.get_text(strip=True)[:500]
                
                # FILTRE CYBERSÉCURITÉ (élargi)
                texte_complet = f"{titre} {description}".lower()
                est_pertinent = any(mot.lower() in texte_complet for mot in MOTS_CLES_CYBER)
                
                # Si ce n'est pas pertinent, on le rejette
                if not est_pertinent:
                    nb_rejetes += 1
                    continue
                
                source_ext_id = hashlib.sha256(f"{CHALLENGE_SOURCE_NAME}|{url_article}".encode()).hexdigest()[:32]
                
                articles.append({
                    "source_ext_id": source_ext_id,
                    "titre": titre[:300],
                    "description": description[:500],
                    "date_publication": date_publication,
                    "categorie": "Technologie",
                    "url_source": url_article,
                    "raw_data": {
                        "source": "Challenge",
                        "langue": "fr",
                        "titre": titre,
                        "url": url_article,
                    },
                })
                
        except Exception as e:
            logger.error(f"Challenge erreur: {e}")

        if nb_rejetes:
            logger.info(f"Challenge: {nb_rejetes} article(s) rejeté(s) (hors cybersécurité)")

        if not articles:
            logger.warning("Challenge: aucun article collecté")
            return []
        
        logger.info(f"Challenge: {len(articles)} articles collectés")
        return articles


def extraire_date_depuis_article_challenge(url: str) -> Optional[datetime]:
    """Repli : va chercher la date sur la page de l'article quand la page
    de liste n'en fournit pas."""
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for time_tag in soup.find_all("time"):
            for candidat in (time_tag.get("datetime"), time_tag.get_text(strip=True)):
                if candidat:
                    parsed = parse_date_challenge(candidat)
                    if parsed:
                        return parsed
    except Exception:
        pass
    return None


def parse_date_challenge(date_text: str) -> Optional[datetime]:
    if not date_text:
        return None
    
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
    print("  TEST DU COLLECTEUR CHALLENGE")
    print("=" * 60)
    
    collector = ChallengeCollector()
    result = collector.run(max_articles=10)
    
    print("\n" + "=" * 60)
    print("  RÉSULTAT")
    print("=" * 60)
    print(f"  Source: {result.get('source')}")
    print(f"  Alertes trouvées: {result.get('alertes_trouvees', 0)}")
    print(f"  Nouvelles insérées: {result.get('nouvelles_inserees', 0)}")
    print(f"  Statut: {result.get('statut')}")
    print("=" * 60)