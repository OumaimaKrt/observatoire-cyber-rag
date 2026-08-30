# collectors/collect_nvd.py
import requests
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any
from utils.http_retry import get_with_retry


import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collectors.base import BaseCollector
from config import NVD_API_URL, NVD_API_KEY, NVD_RESULTS_PER_PAGE, REQUEST_TIMEOUT, NVD_RATE_DELAY
from utils.classifiers import (
    classifier_menace_cve_simple,
    map_severite_cvss_simple,
    classifier_secteur_texte_simple,
    map_menace_to_official_simple,    
    map_secteur_to_official_simple,    
    map_severite_to_official_simple,   
)
from utils.logger import get_logger

logger = get_logger("collect_nvd")


class NVDCollector(BaseCollector):
    source_name = "NVD - NIST"
    langue = "en"
    pays = "US"

    def collect(self, nb_cve: int = 200, jours: int = 30) -> List[Dict[str, Any]]:
        logger.info(f"Collecte NVD — {nb_cve} CVE, {jours} jours")
        alertes = []
        
        headers = {"apiKey": NVD_API_KEY} if NVD_API_KEY else {}
        
        date_fin = datetime.utcnow()
        date_debut = date_fin - timedelta(days=jours)
        
        params = {
            "pubStartDate": date_debut.strftime("%Y-%m-%dT%H:%M:%S.000"),
            "pubEndDate": date_fin.strftime("%Y-%m-%dT%H:%M:%S.000"),
            "resultsPerPage": min(nb_cve, NVD_RESULTS_PER_PAGE),
            "startIndex": 0,
        }

        max_retries = 3
        
        while True:
            page = params["startIndex"] // NVD_RESULTS_PER_PAGE + 1
            logger.info(f"NVD — Page {page} (index {params['startIndex']})")
            
            retry_count = 0
            success = False
            data = None
            
            while retry_count < max_retries and not success:
                try:
                    resp = get_with_retry(
                        NVD_API_URL,
                        params=params,
                        headers=headers,
                        timeout=REQUEST_TIMEOUT,
                        tentatives=3,
                        backoff_seconds=5.0,
                        logger_prefix="NVD"
                    )
                    
                    if resp.status_code == 403:
                        logger.warning(f"NVD 403 — clé invalide ou rate limit, attente 30s...")
                        time.sleep(30)
                        retry_count += 1
                        continue
                    if resp.status_code == 503:
                        logger.warning(f"NVD 503 — serveur indisponible, attente 30s...")
                        time.sleep(30)
                        retry_count += 1
                        continue
                    
                    resp.raise_for_status()
                    data = resp.json()
                    success = True
                    
                except requests.exceptions.Timeout:
                    logger.warning(f"NVD timeout (tentative {retry_count+1}/{max_retries})")
                    time.sleep(10)
                    retry_count += 1
                    continue
                except requests.exceptions.RequestException as e:
                    logger.error(f"NVD erreur réseau: {e}")
                    retry_count += 1
                    time.sleep(10)
                    continue
            
            if not success:
                logger.error(f"NVD — Échec après {max_retries} tentatives, arrêt de la collecte")
                break
            
            for item in data.get("vulnerabilities", []):
                cve_data = item.get("cve", {})
                cve_id = cve_data.get("id", "")
                
                if not cve_id:
                    continue

                desc_en = ""
                for d in cve_data.get("descriptions", []):
                    if d.get("lang") == "en":
                        desc_en = d.get("value", "")
                        break

                
                desc_upper = desc_en.strip().upper()
                if desc_upper.startswith("** REJECT **") or desc_upper.startswith("** RESERVED **") or not desc_en.strip():
                    continue

                score_v3 = None
                metrics = cve_data.get("metrics", {})
                if "cvssMetricV31" in metrics:
                    score_v3 = metrics["cvssMetricV31"][0].get("cvssData", {}).get("baseScore")
                elif "cvssMetricV30" in metrics:
                    score_v3 = metrics["cvssMetricV30"][0].get("cvssData", {}).get("baseScore")

                # Classification initiale
                type_menace = classifier_menace_cve_simple(desc_en)
                severite = map_severite_cvss_simple(score_v3)
                secteur_cible = classifier_secteur_texte_simple(desc_en)
                
                # Mapper vers les codes officiels du guide CMRPI
                type_menace = map_menace_to_official_simple(type_menace)
                secteur_cible = map_secteur_to_official_simple(secteur_cible)
                severite = map_severite_to_official_simple(severite)
                
                # Si le secteur est INCONNU mais qu'il y a des mots-clés techniques
                if secteur_cible == "INCONNU":
                    texte_lower = desc_en.lower()
                    if "wordpress" in texte_lower or "plugin" in texte_lower or "woocommerce" in texte_lower:
                        secteur_cible = "COMMERCE"
                    elif "scada" in texte_lower or "plc" in texte_lower or "modbus" in texte_lower:
                        secteur_cible = "INDUSTRIE"
                    elif "payment" in texte_lower or "bank" in texte_lower or "financial" in texte_lower:
                        secteur_cible = "FINANCE"
                    elif "hospital" in texte_lower or "health" in texte_lower or "medical" in texte_lower:
                        secteur_cible = "SANTE"

                alertes.append({
                    "source_ext_id": cve_id,
                    "titre": cve_id,
                    "description": desc_en,
                    "date_incident": cve_data.get("published"),
                    "type_menace": type_menace,
                    "severite": severite,
                    "secteur_cible": secteur_cible,
                    "url_source": f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                    "score_cvss": score_v3,
                    "raw_data": cve_data,
                })

            params["startIndex"] += NVD_RESULTS_PER_PAGE
            if params["startIndex"] >= min(data.get("totalResults", 0), nb_cve):
                break
            time.sleep(NVD_RATE_DELAY)

        logger.info(f"NVD: {len(alertes)} alertes collectées")
        return alertes


# ─── Test indépendant ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    collector = NVDCollector()
    result = collector.run(nb_cve=50, jours=7)
    print(result)