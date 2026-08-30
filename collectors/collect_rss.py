# collectors/collect_rss.py

import feedparser
import re
import hashlib
import requests
from datetime import datetime
from typing import List, Dict, Any
from utils.http_retry import get_with_retry

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collectors.base import BaseCollector
from config import RSS_SOURCES
from utils.classifiers import (
    classifier_menace_texte_simple,
    map_niveau_risque_texte_simple,
    est_pertinent_cyber,
    map_menace_to_official_simple,
    map_secteur_to_official_simple,
    map_severite_to_official_simple,
)
from utils.logger import get_logger

logger = get_logger("collect_rss")

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


class RSSCollector(BaseCollector):

    
    def __init__(self, db_config: dict, source_config: dict):
        super().__init__(db_config)
        self.source_name = source_config.get("nom", "RSS_Unknown")
        self.feed_url = source_config.get("url", "")
        self.langue = source_config.get("langue", "en")
        self.pays = source_config.get("pays", "US")
        self.generaliste = source_config.get("generaliste", False)
        self.seuil_pertinence = source_config.get("seuil_pertinence", 0.3)

    def _fetch_feed(self):
        try:
            resp = get_with_retry(
                url,
                headers=HEADERS,
                timeout=15,
                tentatives=3,
                backoff_seconds=3.0,
                logger_prefix="BAM"
            )
            response.raise_for_status()
            return feedparser.parse(response.content)
        except requests.RequestException as e:
            logger.warning(
                f"RSS {self.source_name}: échec requête HTTP directe ({e}), "
                "repli sur feedparser.parse(url)"
            )
            return feedparser.parse(self.feed_url)

    # NOUVELLE MÉTHODE POUR CISA
    def _get_cisa_description(self, entry: feedparser.FeedParserDict) -> str:
        """
        Extrait la description d'un article CISA.
        Le flux CISA a parfois 'summary' vide mais du contenu dans 'content' ou 'title'.
        """
        # 1. Essayer summary
        summary = entry.get("summary", "")
        if summary and len(summary) > 20:
            # Nettoyer le HTML
            return re.sub(r'<[^>]+>', ' ', summary).strip()
        
        # 2. Essayer content
        content = entry.get("content", [])
        if content and len(content) > 0:
            content_text = content[0].get("value", "")
            # Nettoyer le HTML
            if content_text:
                return re.sub(r'<[^>]+>', ' ', content_text).strip()
        
        # 3. Essayer description
        description = entry.get("description", "")
        if description and len(description) > 20:
            return re.sub(r'<[^>]+>', ' ', description).strip()
        
        # 4. Utiliser le titre comme description
        title = entry.get("title", "")
        if title:
            return title
        
        return ""

    def collect(self, max_articles: int = 20) -> List[Dict[str, Any]]:
        logger.info(f"Collecte RSS {self.source_name} — {self.feed_url}")
        alertes = []
        
        try:
            feed = self._fetch_feed()

            if feed is None or (feed.bozo and not feed.entries):
                logger.warning(f"RSS {self.source_name}: erreur de parsing")
                return []
            
            entries = feed.entries[:max_articles]
            logger.info(f"RSS {self.source_name}: {len(entries)} articles récupérés")

            nb_rejetes = 0

            for entry in entries:
                titre = entry.get("title", "")
                
                # Cas spécifique pour CISA
                if self.source_name == "CISA_USA":
                    description_raw = self._get_cisa_description(entry)
                else:
                    description_raw = entry.get("summary", entry.get("description", ""))
                
                description = re.sub(r'<[^>]+>', '', description_raw)
                lien = entry.get("link", "")
                
                date_pub = entry.get("published_parsed")
                if date_pub:
                    try:
                        date_incident = datetime(*date_pub[:6])
                    except Exception:
                        date_incident = datetime.now()
                else:
                    date_incident = datetime.now()
                
                texte_complet = f"{titre} {description}"

                # Exception pour CISA : on garde toujours (les articles CISA sont toujours pertinents)
                if self.generaliste and self.source_name != "CISA_USA":
                    pertinent, confiance, mots = est_pertinent_cyber(
                        texte_complet, seuil_confiance=self.seuil_pertinence
                    )
                    if not pertinent:
                        nb_rejetes += 1
                        logger.debug(
                            f"RSS {self.source_name}: article écarté (hors-sujet) — {titre[:80]!r}"
                        )
                        continue
                elif self.source_name == "CISA_USA":
                    logger.debug(f"RSS CISA_USA: article gardé (source prioritaire) — {titre[:80]!r}")

                type_menace = classifier_menace_texte_simple(texte_complet)
                severite = map_niveau_risque_texte_simple(texte_complet)
                
                type_menace = map_menace_to_official_simple(type_menace)
                secteur = map_secteur_to_official_simple("Inconnu")
                severite = map_severite_to_official_simple(severite)
                
                if secteur == "INCONNU":
                    texte_lower = texte_complet.lower()
                    if "bank" in texte_lower or "financial" in texte_lower or "finance" in texte_lower:
                        secteur = "FINANCE"
                    elif "retail" in texte_lower or "e-commerce" in texte_lower or "commerce" in texte_lower:
                        secteur = "COMMERCE"
                    elif "industrial" in texte_lower or "manufacturing" in texte_lower or "scada" in texte_lower:
                        secteur = "INDUSTRIE"
                    elif "health" in texte_lower or "medical" in texte_lower or "hospital" in texte_lower:
                        secteur = "SANTE"
                    elif "telecom" in texte_lower or "opérateur télécom" in texte_lower or "réseau mobile" in texte_lower:
                        secteur = "TELECOM"
                
                source_ext_id = hashlib.sha256(f"{self.source_name}|{lien}".encode()).hexdigest()[:32]
                
                alertes.append({
                    "source_ext_id": source_ext_id,
                    "titre": titre[:300],
                    "description": description[:1000] if description else titre[:500],
                    "date_incident": date_incident,
                    "type_menace": type_menace,
                    "severite": severite,
                    "secteur_cible": secteur,
                    "url_source": lien,
                    "raw_data": {
                        "feed": self.feed_url,
                        "source": self.source_name,
                        "entry": entry,
                    },
                })

            if self.generaliste and nb_rejetes and self.source_name != "CISA_USA":
                logger.info(
                    f"RSS {self.source_name}: {nb_rejetes} article(s) écarté(s) "
                    f"comme hors-sujet (sur {len(entries)} récupérés)"
                )
                
        except Exception as e:
            logger.error(f"RSS {self.source_name} erreur: {e}")
            return []
        
        if not alertes:
            if self.generaliste and nb_rejetes:
                logger.info(
                    f"RSS {self.source_name}: aucun article pertinent dans ce lot "
                    f"({nb_rejetes} écarté(s)), pas de données insérées"
                )
                return []
            logger.warning(f"RSS {self.source_name}: aucune alerte collectée")
            return []
        
        logger.info(f"RSS {self.source_name}: {len(alertes)} alertes collectées")
        return alertes


def get_all_rss_collectors(db_config: dict) -> List[RSSCollector]:
    collectors = []
    for source_config in RSS_SOURCES:
        collectors.append(RSSCollector(db_config, source_config))
    return collectors


if __name__ == "__main__":
    print("=" * 60)
    print("  TEST DES COLLECTEURS RSS")
    print("=" * 60)
    
    from config import DB_CONFIG
    
    collectors = get_all_rss_collectors(DB_CONFIG)
    
    for collector in collectors:
        print(f"\n--- {collector.source_name} ---")
        result = collector.run(max_articles=5)
        print(f"  Alertes: {result.get('alertes_trouvees', 0)}")
        print(f"  Nouvelles: {result.get('nouvelles_inserees', 0)}")
        print(f"  Statut: {result.get('statut')}")