# collectors/collect_abuseipdb.py
# =============================================================================
# Collecteur AbuseIPDB - Récupère les IP malveillantes signalées
# =============================================================================
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.http_retry import get_with_retry

from dotenv import load_dotenv
load_dotenv()

import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any

from collectors.base import BaseCollector
from config import DB_CONFIG
from utils.logger import get_logger
from utils.classifiers import normaliser_menace, normaliser_secteur, normaliser_severite

logger = get_logger("collect_abuseipdb")

ABUSEIPDB_API_KEY = os.getenv("ABUSEIPDB_API_KEY", "")
ABUSEIPDB_API_URL = "https://api.abuseipdb.com/api/v2"


class AbuseIPDBCollector(BaseCollector):
    source_name = "AbuseIPDB"
    langue = "en"
    pays = "INT"

    def __init__(self, db_config: dict = None):
        super().__init__(db_config)
        self.api_key = ABUSEIPDB_API_KEY
        self.headers = {
            "Key": self.api_key,
            "Accept": "application/json"
        }

    def collect(self, **kwargs) -> List[Dict[str, Any]]:
        """Collecte les IP récemment signalées à AbuseIPDB."""
        if not self.api_key:
            logger.error("ABUSEIPDB_API_KEY non configurée")
            return self._get_demo_data()

        params = {
            "recent": "true",
            "days": 1,
            "limit": 100
        }

        try:
            response = get_with_retry(
                f"{ABUSEIPDB_API_URL}/blacklist",
                headers=self.headers,
                params=params,
                timeout=30,
                tentatives=3,
                backoff_seconds=3.0,
                logger_prefix="AbuseIPDB"
            )
            response.raise_for_status()
            data = response.json()

            if data.get("data") and len(data["data"]) > 0:
                logger.info(f"AbuseIPDB: {len(data['data'])} IP récupérées")
                return self._process_data(data["data"])
            else:
                logger.warning("AbuseIPDB: aucune IP récupérée")
                return self._get_demo_data()

        except requests.exceptions.RequestException as e:
            logger.error(f"AbuseIPDB: erreur requête - {e}")
            return self._get_demo_data()

    def _process_data(self, items: List[Dict]) -> List[Dict[str, Any]]:
        """Transforme les données AbuseIPDB en incidents normalisés."""
        alertes = []

        # Mapping des catégories AbuseIPDB vers les menaces du projet
        category_mapping = {
            1: "DNS", 2: "DNS",
            3: "Cheval_de_Troie", 4: "DDoS",
            5: "Phishing", 6: "Proxy",
            7: "Phishing", 8: "Proxy",
            9: "Spam", 10: "Spam",
            11: "Virus", 12: "Cheval_de_Troie",
            13: "Spoofing", 14: "Piratage",
            15: "Piratage", 16: "Piratage",
            17: "Piratage", 18: "Piratage",
            19: "Spam", 20: "Ransomware",
            21: "Spyware", 22: "Spyware",
            23: "Piratage"
        }

        for item in items:
            ip = item.get("ipAddress", "")
            if not ip:
                continue

            score = item.get("abuseConfidenceScore", 0)
            country_code = item.get("countryCode", "")
            last_reported = item.get("lastReportedAt", "")

            # Déterminer le type de menace en fonction du score et du pays
            if score >= 90:
                menace = "Piratage"
            elif score >= 70:
                menace = "Piratage"
            else:
                menace = "Piratage"

            # Niveau de sévérité basé sur le score de confiance
            if score >= 80:
                severite_brut = "CRITIQUE"
            elif score >= 50:
                severite_brut = "ELEVEE"
            elif score >= 20:
                severite_brut = "MOYENNE"
            else:
                severite_brut = "FAIBLE"

            # Normalisation
            type_menace = normaliser_menace(menace)
            severite = normaliser_severite(severite_brut)
            secteur_cible = normaliser_secteur("INCONNU")

            titre = f"IP malveillante détectée : {ip}"
            description = (
                f"IP: {ip} | Score de confiance: {score}% | "
                f"Pays: {country_code} | Dernier signalement: {last_reported}"
            )

            alertes.append({
                "source_ext_id": f"abuseipdb_{ip}",
                "titre": titre[:300],
                "description": description[:1000],
                "date_incident": datetime.now(),
                "type_menace": type_menace,
                "secteur_cible": secteur_cible,
                "severite": severite,
                "url_source": f"https://www.abuseipdb.com/check/{ip}",
                "score_cvss": None,
                "raw_data": {
                    "ip": ip,
                    "abuse_confidence_score": score,
                    "country_code": country_code,
                    "last_reported_at": last_reported
                }
            })

        logger.info(f"AbuseIPDB: {len(alertes)} alertes traitées")
        return alertes

    def _get_demo_data(self) -> List[Dict[str, Any]]:
        """Données de démonstration."""
        return [
            {
                "source_ext_id": "demo_abuseipdb_001",
                "titre": "IP malveillante détectée (démo)",
                "description": "Données de démonstration AbuseIPDB",
                "date_incident": datetime.now(),
                "type_menace": "PIRATAGE",
                "secteur_cible": "INCONNU",
                "severite": "ELEVEE",
                "url_source": "https://www.abuseipdb.com",
                "score_cvss": None,
                "raw_data": {"source": "demo"}
            }
        ]


if __name__ == "__main__":
    collector = AbuseIPDBCollector()
    result = collector.run()
    print(f"Résultat: {result}")