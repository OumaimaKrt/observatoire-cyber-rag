# collectors/collect_otx.py
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import requests
import hashlib
from datetime import datetime
from typing import List, Dict, Any

from collectors.base import BaseCollector
from config import OTX_API_KEY
from utils.classifiers import (
    classifier_menace_texte_simple,
    map_niveau_risque_texte_simple,
    map_menace_to_official_simple,     
    map_secteur_to_official_simple,    
    map_severite_to_official_simple,  
)
from utils.http_retry import get_with_retry
from utils.logger import get_logger

logger = get_logger("collect_otx")

OTX_SOURCE_NAME = "AlienVault_OTX"
OTX_API_URL = "https://otx.alienvault.com/api/v1/pulses/subscribed"


class OTXCollector(BaseCollector):
    source_name = OTX_SOURCE_NAME
    langue = "en"
    pays = "US"

    def collect(self, max_pulses: int = 50) -> List[Dict[str, Any]]:
        logger.info(f"Collecte OTX — max {max_pulses} pulses")
        alertes = []

        if not OTX_API_KEY:
            logger.warning("OTX: clé API manquante")
            return self._get_demo_data()

        try:
            headers = {"X-OTX-API-KEY": OTX_API_KEY}
           
            resp = get_with_retry(
                OTX_API_URL,
                headers=headers,
                timeout=45,
                tentatives=3,
                backoff_seconds=3.0,
                logger_prefix="OTX",
            )
            if resp is None:
                logger.error("OTX: échec réseau après plusieurs tentatives")
                return self._get_demo_data()
            resp.raise_for_status()
            data = resp.json()

            pulses = data.get("results", [])[:max_pulses]
            logger.info(f"OTX: {len(pulses)} pulses récupérés")

            for pulse in pulses:
                titre = pulse.get("name", "")
                description = pulse.get("description", "")
                tags = pulse.get("tags", [])
                
                indicators = pulse.get("indicators", [])
                indicator_types = list(set(i.get("type", "") for i in indicators[:5]))
                
                created = pulse.get("created")
                if created:
                    if isinstance(created, (int, float)):
                        date_incident = datetime.fromtimestamp(created)
                    elif isinstance(created, str):
                        try:
                            date_incident = datetime.fromisoformat(created.replace("Z", "+00:00"))
                        except:
                            date_incident = datetime.now()
                    else:
                        date_incident = datetime.now()
                else:
                    date_incident = datetime.now()
                
                # Classification initiale
                texte_complet = f"{titre} {description} {' '.join(tags)}".lower()
                type_menace = classifier_menace_texte_simple(texte_complet)
                severite = map_niveau_risque_texte_simple(texte_complet)
                
                # Mapper vers les codes officiels du guide CMRPI
                type_menace = map_menace_to_official_simple(type_menace)
                secteur = map_secteur_to_official_simple("Inconnu")
                severite = map_severite_to_official_simple(severite)
                
                # Détection du secteur à partir des tags et de la description
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
                    elif "telecom" in texte_lower or "mobile network" in texte_lower or "isp " in texte_lower:
                        secteur = "TELECOM"
                
                source_ext_id = hashlib.sha256(f"OTX|{pulse.get('id', '')}".encode()).hexdigest()[:32]
                
                alertes.append({
                    "source_ext_id": source_ext_id,
                    "titre": titre[:300],
                    "description": f"{description[:500]} | Tags: {', '.join(tags[:5])} | IoCs: {', '.join(indicator_types)}",
                    "date_incident": date_incident,
                    "type_menace": type_menace,
                    "severite": severite,
                    "secteur_cible": secteur,
                    "url_source": f"https://otx.alienvault.com/pulse/{pulse.get('id', '')}",
                    "raw_data": pulse,
                })

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                logger.error("OTX: 403 Forbidden - Vérifiez votre clé API")
            elif e.response.status_code == 401:
                logger.error("OTX: 401 Unauthorized - Clé API invalide")
            else:
                logger.error(f"OTX: HTTP {e.response.status_code}")
            return self._get_demo_data()
        except requests.exceptions.RequestException as e:
            logger.error(f"OTX erreur réseau: {e}")
            return self._get_demo_data()
        except Exception as e:
            logger.error(f"OTX erreur: {e}")
            return self._get_demo_data()

        if not alertes:
            logger.warning("OTX: aucune alerte collectée")
            return self._get_demo_data()
        
        return alertes

    def _get_demo_data(self) -> List[Dict[str, Any]]:
        """Données de démonstration avec codes officiels."""
        logger.info("OTX: utilisation des données de démonstration")
        return [
            {
                "source_ext_id": "demo_otx_001",
                "titre": "OTX Pulse - Ransomware Activity in North Africa",
                "description": "Increased ransomware activity targeting SMEs in Morocco and Algeria.",
                "date_incident": datetime(2026, 6, 15),
                "type_menace": "RANSOMWARE",
                "severite": "ELEVEE",
                "secteur_cible": "INCONNU",
                "url_source": "https://otx.alienvault.com/pulse/demo",
                "raw_data": {"source": "demo"},
            },
            {
                "source_ext_id": "demo_otx_002",
                "titre": "OTX Pulse - Phishing Campaign Targeting Moroccan Banks",
                "description": "Phishing campaign targeting financial institutions in Morocco.",
                "date_incident": datetime(2026, 6, 10),
                "type_menace": "PHISHING",
                "severite": "ELEVEE",
                "secteur_cible": "FINANCE",
                "url_source": "https://otx.alienvault.com/pulse/demo",
                "raw_data": {"source": "demo"},
            },
        ]


if __name__ == "__main__":
    print("=" * 60)
    print("  TEST DU COLLECTEUR ALIENVAULT OTX")
    print("=" * 60)
    
    collector = OTXCollector()
    result = collector.run(max_pulses=10)
    
    print("\n" + "=" * 60)
    print("  RÉSULTAT")
    print("=" * 60)
    print(f"  Source: {result.get('source')}")
    print(f"  Alertes trouvées: {result.get('alertes_trouvees', 0)}")
    print(f"  Nouvelles insérées: {result.get('nouvelles_inserees', 0)}")
    print(f"  Statut: {result.get('statut')}")
    if result.get('erreur'):
        print(f"  Erreur: {result.get('erreur')}")
    print("=" * 60)