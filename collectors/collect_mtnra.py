# collectors/collect_mtnra.py
import re
import hashlib
import requests
from datetime import datetime
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from utils.http_retry import get_with_retry

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collectors.base import BaseCollector
from utils.logger import get_logger
from utils.classifiers import parse_date_fr  # ✅ Import ajouté

logger = get_logger("collect_mtnra")

MTNRA_ACTUALITES_URL = "https://www.mmsp.gov.ma/fr/actualites"

MOTS_PERTINENCE = [
    "cybersécurité", "cybersecurite",
    "cyber",
    "sécurité", "securite",
    "protection", "données", "donnees",
    "rgpd",
    "faille", "attaque", "malware", "ransomware", "phishing", "piratage",
    "pme", "tpme", "startup",
    "cloud", "datacenter",
    "infrastructure", "connectivité",
    "souveraineté",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "fr,fr-FR;q=0.9",
}


class MTNRACollector(BaseCollector):
 
    source_name = "MTNRA_Maroc"
    langue = "fr"
    pays = "MA"

    def collect(self, max_pages: int = 5) -> List[Dict[str, Any]]:
        logger.info(f"Collecte MTNRA — {MTNRA_ACTUALITES_URL} ({max_pages} page(s))")
        alertes = []
        pages_echouees = 0

        for page in range(max_pages):
            url_page = MTNRA_ACTUALITES_URL if page == 0 else f"{MTNRA_ACTUALITES_URL}?page={page}"

            items = None
            for tentative in range(2):
                try:
                    resp = get_with_retry(
                        url_page,
                        headers=HEADERS,
                        timeout=20,
                        tentatives=3,
                        backoff_seconds=3.0,
                        logger_prefix="MTNRA"
                    )
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, "html.parser")
                    items = self._extraire_articles(soup)
                    break
                except requests.exceptions.RequestException as e:
                    if tentative == 0:
                        logger.warning(f"MTNRA page {page+1} — erreur ({e}), retry...")
                    else:
                        logger.warning(f"MTNRA page {page+1} — échec définitif ({e}), page ignorée.")
                        pages_echouees += 1

            if items is None:
                continue

            if not items:
                logger.warning(f"MTNRA page {page+1} — aucun article trouvé, arrêt pagination.")
                break

            logger.info(f"MTNRA page {page+1} — {len(items)} article(s) trouvé(s)")

            for href, titre, date_incident in items:
                texte_verif = titre.lower()
                if not any(mot in texte_verif for mot in MOTS_PERTINENCE):
                    continue  # actu protocolaire hors sujet numérique/PME

                url_complete = href if href.startswith("http") else f"https://www.mmsp.gov.ma{href}"
                alertes.append({
                    "source_ext_id": hashlib.sha256(f"MTNRA|{url_complete}".encode()).hexdigest()[:32],
                    "titre": titre[:300],
                    "description": titre,  # ✅ description succincte
                    "date_publication": date_incident or datetime.utcnow(),
                    "categorie": "Numerique_Gouvernance",
                    "url_source": url_complete,
                    "raw_data": {"source": "MTNRA", "titre": titre, "url": url_complete},
                })

        if pages_echouees:
            logger.warning(f"MTNRA: {pages_echouees} page(s) définitivement inaccessible(s) sur {max_pages}.")

        logger.info(f"MTNRA: {len(alertes)} actualité(s) pertinente(s) collectée(s)")
        return alertes

    def _extraire_articles(self, soup: BeautifulSoup):
   
        resultats = []
        vus = set()

        liens = [
            a for a in soup.find_all("a", href=True)
            if re.match(r"^/fr/actualites/.+", a["href"])
        ]

        for a in liens:
            href = a["href"]
            if href in vus:
                continue
            titre = a.get_text(strip=True)
            if not titre or len(titre) < 10:
                continue
            vus.add(href)

            date_incident = None
            conteneur = a.find_parent(["div", "article", "li"])
            if conteneur:
                texte_conteneur = conteneur.get_text(" ", strip=True)
                match = re.search(r"\d{1,2}\s+\w+\s+\d{4}", texte_conteneur)
                if match:
                    date_incident = parse_date_fr(match.group(0))  # ✅ Utilise la fonction importée

            resultats.append((href, titre, date_incident))

        return resultats

    def save(self, alertes: List[Dict[str, Any]]) -> int:
        import psycopg2
        import json
        from config import DB_CONFIG

        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        total_nouvelles = 0
        try:
            for a in alertes:
                cur.execute("""
                    INSERT INTO sector_news (
                        source, source_ext_id, titre, description,
                        date_publication, categorie, url_source, pays, langue, raw_data
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (source_ext_id) DO NOTHING;
                """, (
                    self.source_name,
                    a["source_ext_id"],
                    a["titre"][:300],
                    (a.get("description") or "")[:1000],
                    a.get("date_publication"),
                    a.get("categorie", "Numerique_Gouvernance"),
                    a.get("url_source"),
                    self.pays,
                    self.langue,
                    json.dumps(a.get("raw_data", {}), default=str),
                ))
                if cur.rowcount > 0:
                    total_nouvelles += 1
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Erreur sauvegarde {self.source_name} (sector_news): {e}")
            raise
        finally:
            cur.close()
            conn.close()
        return total_nouvelles


# ✅ Fonction parse_date_fr supprimée (importée depuis classifiers.py)


if __name__ == "__main__":
    print("=" * 60)
    print("  TEST DU COLLECTEUR MTNRA (Transition Numérique)")
    print("=" * 60)

    collector = MTNRACollector()
    result = collector.run(max_pages=5)

    print("\n" + "=" * 60)
    print("  RÉSULTAT")
    print("=" * 60)
    print(f"  Source: {result.get('source')}")
    print(f"  Alertes trouvées: {result.get('alertes_trouvees', 0)}")
    print(f"  Nouvelles insérées: {result.get('nouvelles_inserees', 0)}")
    print(f"  Statut: {result.get('statut')}")
    print("=" * 60)