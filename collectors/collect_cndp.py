# collectors/collect_cndp.py
import sys
import os
import re
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional
from utils.http_retry import get_with_retry

import requests
from bs4 import BeautifulSoup

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collectors.base_news import BaseNewsCollector
from config import CNDP_URL, CNDP_COMMUNIQUES_URL, REQUEST_TIMEOUT, REQUEST_DELAY
from utils.logger import get_logger

logger = get_logger("collect_cndp")

CNDP_SOURCE_NAME = "CNDP_Maroc"

MOIS_FR = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# (url_categorie, libellé_categorie) — le libellé finit dans sector_news.categorie
FLUX_CNDP = [
    (CNDP_COMMUNIQUES_URL, "Communique_Presse"),
    (CNDP_URL, "Actualite"),
]


def _extraire_date_pour_h2(h2) -> Optional[datetime]:
    """
    Récupère le texte brut situé entre le <h2> précédent (ou le début du
    conteneur) et ce <h2>, puis y cherche un motif "jour mois ... année".
    Fonctionne que "22 Mai" et "2026" soient un seul noeud de texte fusionné
    ou deux noeuds séparés — on ne suppose plus une structure DOM précise
    non vérifiée, seulement l'ordre du texte tel qu'il apparaît à l'écran.
    """
    morceaux = []
    for el in h2.previous_elements:
        if getattr(el, "name", None) == "h2":
            break  # on a remonté jusqu'à l'article précédent, on s'arrête
        if isinstance(el, str):
            texte = el.strip()
            if texte:
                morceaux.append(texte)
        if len(morceaux) > 12:
            break
    bloc = " ".join(reversed(morceaux))
    match = re.search(r"(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\D{0,15}(\d{4})", bloc)
    if not match:
        return None
    jour = int(match.group(1))
    mois = MOIS_FR.get(match.group(2).lower())
    if not mois:
        return None
    try:
        return datetime(int(match.group(3)), mois, jour)
    except ValueError:
        return None


def _pdf_associe(h2) -> Optional[str]:
    """
    Cherche un lien .pdf entre ce <h2> et le <h2> suivant (le communiqué
    officiel joint, observé sur communiques-de-presse). Traverse les
    éléments suivants dans l'ordre du document et s'arrête au prochain
    <h2> pour ne pas rattacher le PDF d'un autre article.
    """
    for el in h2.find_all_next():
        if getattr(el, "name", None) == "h2":
            break
        if getattr(el, "name", None) == "a":
            href = el.get("href", "")
            if href.lower().endswith(".pdf"):
                return href
    return None


class CNDPCollector(BaseNewsCollector):
    source_name = CNDP_SOURCE_NAME
    langue = "fr"
    pays = "MA"
    categorie_defaut = "Protection_Donnees"

    def collect(self, max_pages_par_flux: int = 3, max_articles: int = 100) -> List[Dict[str, Any]]:
        logger.info(f"Collecte CNDP — {len(FLUX_CNDP)} flux, jusqu'à {max_pages_par_flux} page(s) chacun")
        articles: List[Dict[str, Any]] = []
        urls_vues_global = set()

        for url_categorie, categorie in FLUX_CNDP:
            if len(articles) >= max_articles:
                break
            articles += self._collecter_un_flux(
                url_categorie, categorie, max_pages_par_flux,
                max_articles - len(articles), urls_vues_global
            )

        logger.info(f"CNDP — {len(articles)} article(s) collecté(s) au total (tous flux confondus)")
        
        if not articles:
            logger.warning("CNDP — 0 article collecté sur aucun flux")
            return []
        
        return articles

    def _collecter_un_flux(
        self, url_base: str, categorie: str, max_pages: int,
        max_articles: int, urls_vues_global: set
    ) -> List[Dict[str, Any]]:
        articles: List[Dict[str, Any]] = []
        contenu_page_precedente = None

        for page in range(1, max_pages + 1):
            if len(articles) >= max_articles:
                break

            url = url_base if page == 1 else f"{url_base.rstrip('/')}/page/{page}/"
            logger.info(f"CNDP [{categorie}] — page {page} : {url}")

            try:
                resp = get_with_retry(
                    url,
                    headers=HEADERS,
                    timeout=REQUEST_TIMEOUT,
                    tentatives=3,
                    backoff_seconds=3.0,
                    logger_prefix="CNDP"
                )
            except requests.exceptions.RequestException as e:
                logger.warning(f"CNDP [{categorie}] page {page} — erreur réseau : {e}")
                break

            if resp.status_code == 404:
                logger.info(f"CNDP [{categorie}] page {page} — 404, fin de ce flux.")
                break
            if resp.status_code != 200:
                logger.warning(f"CNDP [{categorie}] page {page} — statut HTTP {resp.status_code}, arrêt.")
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            titres_h2 = [h2 for h2 in soup.find_all("h2") if h2.find("a", href=True)]

            if not titres_h2:
                logger.warning(
                    f"CNDP [{categorie}] page {page} — aucun <h2> avec lien trouvé. "
                    f"La structure du site a peut-être changé : vérifier manuellement."
                )
                break

            urls_cette_page = set()
            for h2 in titres_h2:
                a = h2.find("a", href=True)
                titre = a.get_text(strip=True)
                url_article = a["href"]
                if not url_article.startswith("http"):
                    url_article = "https://www.cndp.ma" + url_article

                urls_cette_page.add(url_article)
                if url_article in urls_vues_global:
                    continue

                date_publication = datetime.now()
                parsed = _extraire_date_pour_h2(h2)
                if parsed:
                    date_publication = parsed
                else:
                    logger.debug(f"CNDP — date non trouvée pour '{titre[:50]}', date de collecte utilisée à la place")

                pdf_url = _pdf_associe(h2)

                source_ext_id = hashlib.sha256(f"{CNDP_SOURCE_NAME}|{url_article}".encode()).hexdigest()[:32]

                articles.append({
                    "source_ext_id": source_ext_id,
                    "titre": titre[:300],
                    "description": "",
                    "date_publication": date_publication,
                    "categorie": categorie,
                    "url_source": url_article,
                    "raw_data": {
                        "source": "CNDP", "titre": titre, "page": page,
                        "categorie": categorie, "pdf_url": pdf_url,
                    },
                })

                if len(articles) >= max_articles:
                    break

            if contenu_page_precedente is not None and urls_cette_page == contenu_page_precedente:
                logger.info(f"CNDP [{categorie}] page {page} — contenu identique à la page précédente, arrêt.")
                break
            contenu_page_precedente = urls_cette_page
            urls_vues_global |= urls_cette_page

        return articles


if __name__ == "__main__":
    collector = CNDPCollector()
    result = collector.run(max_pages_par_flux=3, max_articles=100)
    print(result)