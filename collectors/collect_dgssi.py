# collectors/collect_dgssi.py
import time
import re
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urljoin, urlparse

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collectors.base import BaseCollector
from config import DGSSI_URL, REQUEST_DELAY
from utils.classifiers import (
    classifier_menace_texte_simple,
    map_niveau_risque_texte_simple,
    classifier_secteur_texte_simple,
    parse_date_fr,
    map_menace_to_official_simple,
    map_secteur_to_official_simple,
    map_severite_to_official_simple,
)
from utils.logger import get_logger

logger = get_logger("collect_dgssi")

# ─── CONSTANTES ──────────────────────────────────────────────────────────────
DGSSI_SOURCE_NAME = "DGSSI-maCERT"

BULLETIN_URL_RE = re.compile(r"/fr/bulletins/[a-z0-9\-]+/?$", re.I)
BULLETIN_URL_RE_AR = re.compile(r"/ar/bulletins/[a-z0-9\-]+/?$", re.I)

EXCLUDE_TITLES = {
    "bulletins de sécurité",
    "bulletin de sécurité",
}

DGSSI_URLS = {
    "fr": "https://www.dgssi.gov.ma/fr/bulletins-securite/",
    "ar": "https://www.dgssi.gov.ma/ar/bulletins-securite/",
}


class DGSSICollector(BaseCollector):
   
    source_name = DGSSI_SOURCE_NAME
    langue = "fr"
    pays = "MA"

    def collect(self, max_pages: int = 5) -> List[Dict[str, Any]]:
        logger.info(f"Collecte DGSSI — FR + AR, max {max_pages} pages")
        alertes = []
        
        for langue, url_base in DGSSI_URLS.items():
            logger.info(f"DGSSI: collecte en {langue.upper()} — {url_base}")
            
            driver = self._get_driver(page_load_timeout=45)
            all_seen_urls: Set[str] = set()
            previous_page_urls: Optional[Set[str]] = None

            try:
                for page in range(1, max_pages + 1):
                    url = url_base if page == 1 else f"{url_base}?page={page}"
                    logger.info(f"DGSSI {langue.upper()} — Page {page} : {url}")

                    try:
                        driver.get(url)
                        WebDriverWait(driver, 25).until(
                            EC.presence_of_element_located((By.TAG_NAME, "body"))
                        )
                        time.sleep(3)
                    except TimeoutException:
                        logger.warning(f"DGSSI {langue.upper()} page {page} — timeout, on continue avec le contenu partiel")
                    except WebDriverException as e:
                        logger.warning(f"DGSSI {langue.upper()} page {page} — erreur Selenium : {e}")
                        continue

                    try:
                        soup = BeautifulSoup(driver.page_source, "html.parser")
                    except Exception:
                        logger.warning(f"DGSSI {langue.upper()} page {page} — impossible de parser le HTML")
                        continue

                    # Sélectionner la bonne regex selon la langue
                    url_re = BULLETIN_URL_RE_AR if langue == "ar" else BULLETIN_URL_RE
                    items = self._extract_bulletins(soup, url_base, url_re, langue)
                    current_page_urls = {it["url"] for it in items}

                    if previous_page_urls is not None and current_page_urls == previous_page_urls:
                        logger.info(f"DGSSI {langue.upper()} page {page} — contenu identique, arrêt.")
                        break
                    previous_page_urls = current_page_urls

                    pas_encore_vus_ce_run = [it for it in items if it["url"] not in all_seen_urls]
                    logger.info(f"DGSSI {langue.upper()} page {page} — {len(items)} bulletins trouvés, "
                                f"{len(pas_encore_vus_ce_run)} pas encore vus dans ce run")

                    for item in pas_encore_vus_ce_run:
                        all_seen_urls.add(item["url"])

                        texte_complet = f"{item['titre']} {item['resume']}"
                        
                        type_menace_raw = classifier_menace_texte_simple(texte_complet)
                        secteur_raw = classifier_secteur_texte_simple(texte_complet)
                        severite_raw = map_niveau_risque_texte_simple(texte_complet)
                        
                        type_menace = map_menace_to_official_simple(type_menace_raw)
                        secteur = map_secteur_to_official_simple(secteur_raw)
                        severite = map_severite_to_official_simple(severite_raw)
                        
                        alerte = {
                            "source_ext_id": hashlib.sha256(item["url"].encode()).hexdigest()[:32],
                            "titre": item["titre"],
                            "description": item["resume"],
                            "date_incident": parse_date_fr(item.get("date_texte", "")) or datetime.now(),
                            "type_menace": type_menace,
                            "severite": severite,
                            "secteur_cible": secteur,
                            "url_source": item["url"],
                            "langue": langue,
                            "raw_data": {
                                "titre": item["titre"],
                                "resume": item["resume"],
                                "texte_complet": texte_complet,
                                "langue": langue,
                            },
                        }
                        alertes.append(alerte)

                    time.sleep(REQUEST_DELAY)

            finally:
                try:
                    driver.quit()
                except Exception:
                    pass

        if not alertes:
            logger.warning("DGSSI: aucune alerte collectée")
            return []

        logger.info(f"DGSSI: {len(alertes)} alertes collectées (FR + AR)")
        return alertes

    def _get_driver(self, page_load_timeout: int = 60):
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--allow-insecure-localhost")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )
        driver.set_page_load_timeout(page_load_timeout)
        return driver

    def _extract_bulletins(self, soup: BeautifulSoup, base_url: str, url_re, langue: str) -> List[dict]:
        """Extrait les bulletins depuis le HTML."""
        items = []
        seen_urls: Set[str] = set()

        for link in soup.find_all("a", href=True):
            href = link["href"].strip()
            titre = link.get_text(strip=True)

            if not titre or len(titre) < 5:
                continue
            if titre.lower() in EXCLUDE_TITLES:
                continue

            absolute_url = urljoin(base_url, href)
            parsed = urlparse(absolute_url)

            if not url_re.search(parsed.path):
                continue

            if absolute_url in seen_urls:
                continue
            seen_urls.add(absolute_url)

            resume = ""
            parent = link.find_parent(["article", "div", "li"])
            if parent:
                p = parent.find("p")
                if p:
                    resume = p.get_text(strip=True)[:500]

            items.append({
                "titre": titre,
                "resume": resume,
                "url": absolute_url,
                "date_texte": "",
            })

        return items


if __name__ == "__main__":
    print("=" * 60)
    print("  TEST DU COLLECTEUR DGSSI (Bilingue FR + AR)")
    print("=" * 60)
    
    collector = DGSSICollector()
    result = collector.run(max_pages=3)
    
    print("\n" + "=" * 60)
    print("  RÉSULTAT")
    print("=" * 60)
    print(f"  Source: {result.get('source')}")
    print(f"  Alertes trouvées: {result.get('alertes_trouvees', 0)}")
    print(f"  Nouvelles insérées: {result.get('nouvelles_inserees', 0)}")
    print(f"  Statut: {result.get('statut')}")
    print("=" * 60)