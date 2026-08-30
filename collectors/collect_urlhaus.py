# collectors/collect_urlhaus.py
# =============================================================================
# Collecteur URLhaus — URLs malveillantes actives (IOC)
#
# Contrairement à NVD/CIRCL (vulnérabilités logicielles, CVE), URLhaus donne
# des indicateurs de compromission ACTIFS : des URLs concrètement utilisées
# en ce moment pour distribuer du malware. Axe complémentaire, pas redondant.
# =============================================================================
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import hashlib
from datetime import datetime
from typing import List, Dict, Any

from collectors.base import BaseCollector
from config import URLHAUS_API_URL, URLHAUS_API_KEY, REQUEST_TIMEOUT
from utils.classifiers import (
    classifier_menace_texte_simple,
    classifier_secteur_texte_simple,
    normaliser_menace,
    normaliser_secteur,
    normaliser_severite
)
from utils.http_retry import get_with_retry
from utils.logger import get_logger

logger = get_logger("collect_urlhaus")


class URLhausCollector(BaseCollector):
    source_name = "URLhaus"
    langue = "en"
    pays = "INT"

    def collect(self, max_urls: int = 50) -> List[Dict[str, Any]]:
        logger.info(f"Collecte URLhaus — max {max_urls} URLs récentes")

        if not URLHAUS_API_KEY:
            logger.error(
                "URLHAUS_API_KEY non configurée — clé gratuite à obtenir sur "
                "https://auth.abuse.ch/ (variable d'environnement URLHAUS_API_KEY)"
            )
            return self._get_demo_data()

        headers = {"Auth-Key": URLHAUS_API_KEY}
        url = URLHAUS_API_URL.format(limit=max_urls)

        resp = get_with_retry(
            url,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
            tentatives=3,
            backoff_seconds=3.0,
            logger_prefix="URLhaus",
        )
        if resp is None:
            logger.error("URLhaus: échec réseau après plusieurs tentatives")
            return self._get_demo_data()

        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError:
            if resp.status_code == 401:
                logger.error("URLhaus: 401 -- Auth-Key invalide ou expirée")
            else:
                logger.error(f"URLhaus: erreur HTTP {resp.status_code}")
            return self._get_demo_data()

        try:
            data = resp.json()
        except ValueError as e:
            logger.error(f"URLhaus: réponse JSON invalide: {e}")
            return self._get_demo_data()

        if data.get("query_status") != "ok":
            statut = data.get("query_status")
            if statut == "no_results":
                logger.info("URLhaus: aucune nouvelle URL (query_status=no_results)")
                return []
            logger.warning(f"URLhaus: query_status inattendu = {statut!r}")
            return self._get_demo_data()

        alertes = []
        for item in data.get("urls", []):
            url_id = item.get("id", "")
            if not url_id:
                continue

            url_malveillante = item.get("url", "")
            statut_url = item.get("url_status", "unknown")
            threat = item.get("threat", "malware_download")
            tags = item.get("tags") or []
            host = item.get("host", "")

            if url_malveillante:
                titre = f"URL malveillante détectée : {url_malveillante}"
            elif host:
                titre = f"URL malveillante détectée : {host}"
            else:
                titre = f"URLhaus #{url_id}"

            tags_txt = ", ".join(tags) if tags else "aucun tag"
            description = (
                f"URL: {url_malveillante} | Statut: {statut_url} | "
                f"Menace: {threat} | Tags: {tags_txt}"
            )

            date_str = item.get("date_added", "")
            date_incident = None
            if date_str:
                try:
                    date_incident = datetime.strptime(
                        date_str.replace(" UTC", ""), "%Y-%m-%d %H:%M:%S"
                    )
                except ValueError:
                    logger.warning(f"URLhaus #{url_id}: date non parsable ({date_str!r})")

            # CLASSIFICATION AVEC NORMALISATION
            texte_complet = f"{titre} {tags_txt} {threat}"
            
            # Classification brute
            type_menace_brut = classifier_menace_texte_simple(texte_complet)
            secteur_brut = classifier_secteur_texte_simple(texte_complet)
            
            # NORMALISATION FORCÉE
            type_menace = normaliser_menace(type_menace_brut)
            secteur_cible = normaliser_secteur(secteur_brut)

            # Sévérité
            if statut_url == "online":
                severite_brut = "ELEVEE"
            elif statut_url == "offline":
                severite_brut = "MOYENNE"
            else:
                severite_brut = "INCONNUE"
            
            # Normalisation de la sévérité
            severite = normaliser_severite(severite_brut)

            source_ext_id = f"urlhaus_{url_id}"

            alertes.append({
                "source_ext_id": source_ext_id,
                "titre": titre[:300],
                "description": description[:1000],
                "date_incident": date_incident,
                "type_menace": type_menace,        
                "severite": severite,               
                "secteur_cible": secteur_cible,   
                "url_source": item.get("urlhaus_reference", ""),
                "raw_data": item,
            })

        if not alertes:
            logger.warning("URLhaus: aucune alerte exploitable, utilisation des données démo")
            return self._get_demo_data()

        logger.info(f"URLhaus: {len(alertes)} alertes collectées")
        return alertes

    def _get_demo_data(self) -> List[Dict[str, Any]]:
        """Données de démonstration pour cette source."""
        return [
            {
                "source_ext_id": "demo_urlhaus_001",
                "titre": "URL malveillante détectée : example-malicious.com",
                "description": (
                    "URL: http://example-malicious.com/payload.exe | Statut: online | "
                    "Menace: malware_download | Tags: emotet, exe"
                ),
                "date_incident": datetime.now(),
                "type_menace": "CHEVAL_TROIE",      # Normalisé
                "severite": "ELEVEE",               # Normalisé
                "secteur_cible": "INCONNU",         # Normalisé
                "url_source": "https://urlhaus.abuse.ch/url/000000/",
                "raw_data": {"source": "demo"},
            },
        ]


# ─── Test indépendant ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    collector = URLhausCollector({})
    result = collector.run(max_urls=20)
    print(result)