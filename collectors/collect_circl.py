# collectors/collect_circl.py
import requests
import re
import hashlib
from datetime import datetime
from typing import List, Dict, Any

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collectors.base import BaseCollector
from config import CIRCL_API_URL, REQUEST_TIMEOUT
from utils.classifiers import (
    classifier_menace_texte_simple,
    map_severite_cvss_simple,
    map_menace_to_official_simple,     
    map_secteur_to_official_simple,   
    map_severite_to_official_simple,  
)
from utils.http_retry import get_with_retry
from utils.logger import get_logger

logger = get_logger("collect_circl")


def extraire_titre_description(item: Dict[str, Any]) -> tuple:
    
    vulns_csaf = item.get("vulnerabilities")
    est_csaf = isinstance(item.get("document"), dict) and isinstance(vulns_csaf, list)

    titre = item.get("summary", "") or (item.get("document") or {}).get("title", "")
    details = item.get("details", "")

    if not details:
        containers_desc = item.get("containers", {}) or {}
        sources_descriptions = [containers_desc.get("cna", {}) or {}]
        sources_descriptions += containers_desc.get("adp", []) or []
        for bloc in sources_descriptions:
            for desc_entry in bloc.get("descriptions", []) or []:
                if desc_entry.get("lang", "en").startswith("en") and desc_entry.get("value"):
                    details = desc_entry["value"]
                    break
            if details:
                break

    if not details and est_csaf:
        for note in (item.get("document") or {}).get("notes", []) or []:
            if note.get("category") in ("summary", "description", "general"):
                details = note.get("text", "")
                break

    if not titre and details:
        titre = details[:200] + "..."

    description = details if details else titre
    return titre, description


class CIRCLCollector(BaseCollector):

    source_name = "CIRCL CVE Search"
    langue = "en"
    pays = "LU"

    def collect(self, nb_cve: int = 50) -> List[Dict[str, Any]]:
        """
        Collecte les vulnérabilités depuis l'API CIRCL au format OSV.
        """
        logger.info(f"Collecte CIRCL — {nb_cve} entrées")
        alertes = []
        
        try:
            
            resp = get_with_retry(
                CIRCL_API_URL,
                timeout=REQUEST_TIMEOUT,
                tentatives=3,
                backoff_seconds=3.0,
                logger_prefix="CIRCL",
            )
            if resp is None:
                logger.error("CIRCL: échec réseau après plusieurs tentatives")
                return self._get_demo_data()
            resp.raise_for_status()
            data = resp.json()
            
            if not isinstance(data, list):
                logger.warning("CIRCL: format de réponse inattendu (pas une liste)")
                return self._get_demo_data()
            
            logger.info(f"CIRCL: {len(data)} entrées récupérées")
            
            # Limiter le nombre
            items = data[:nb_cve]
            nb_ignores_sans_id = 0
            premier_item_ignore_brut = None

            for item in items:
                
                vulns_csaf = item.get("vulnerabilities")
                est_csaf = isinstance(item.get("document"), dict) and isinstance(vulns_csaf, list)

                csaf_cve = ""
                if isinstance(vulns_csaf, list) and vulns_csaf:
                    csaf_cve = vulns_csaf[0].get("cve", "") or ""

                # ─── Extraction de l'ID ──────────────────────────────────────
                # NOTE : l'API CIRCL a changé de format plusieurs fois (ancien
                # cve-search -> OSV -> CVE JSON 5.0 -> CSAF, tous mélangés
                # dans le même flux /api/last). On essaie les emplacements
                # connus plutôt que de supposer un seul format, pour ne pas
                # silencieusement tout jeter si le format a encore changé.
                vuln_id = (
                    item.get("id")
                    or (item.get("cveMetadata") or {}).get("cveId")
                    or item.get("cve_id")
                    or csaf_cve
                    or (item.get("document") or {}).get("tracking", {}).get("id", "")
                    or ""
                )
                if not vuln_id:
                    nb_ignores_sans_id += 1
                    if premier_item_ignore_brut is None:
                        premier_item_ignore_brut = list(item.keys())
                    continue
                
                # ─── Extraction du titre/description ────────────────────────
                titre, description = extraire_titre_description(item)
                
                # ─── Date de publication ─────────────────────────────────────
                date_incident = datetime.now()
                date_pub = item.get("published")
                if date_pub:
                    try:
                        date_incident = datetime.fromisoformat(date_pub.replace("Z", "+00:00"))
                    except Exception:
                        try:
                            date_incident = datetime.fromisoformat(date_pub.replace("Z", "+00:00"))
                        except Exception:
                            pass
                
                # ─── Niveau de sévérité ──────────────────────────────────────
                severite = "INCONNUE"
                score_cvss = None
                
                # Chercher la sévérité dans affected
                for affected in item.get("affected", []):
                    ecoss = affected.get("ecosystem_specific", {})
                    sev = ecoss.get("severity")
                    if sev:
                        if sev.upper() == "CRITICAL":
                            score_cvss = 9.0
                            severite = "CRITIQUE"
                        elif sev.upper() == "HIGH":
                            score_cvss = 7.5
                            severite = "ELEVEE"
                        elif sev.upper() == "MEDIUM":
                            score_cvss = 5.0
                            severite = "MOYENNE"
                        elif sev.upper() == "LOW":
                            score_cvss = 2.5
                            severite = "FAIBLE"
                        break
                
                # Chercher dans database_specific (format OSV)
                if severite == "INCONNUE":
                    for affected in item.get("affected", []):
                        db_spec = affected.get("database_specific", {})
                        cvss = db_spec.get("cvss")
                        if cvss and isinstance(cvss, dict):
                            score = cvss.get("score")
                            if score:
                                score_cvss = float(score)
                                severite = map_severite_cvss_simple(score_cvss)
                                break

                # Chercher dans containers.adp/cna.metrics (format CVE JSON 5.0)
                if severite == "INCONNUE":
                    containers = item.get("containers", {})
                    for bloc in list(containers.get("adp", [])) + [containers.get("cna", {})]:
                        for metric in bloc.get("metrics", []):
                            cvss_data = metric.get("cvssV3_1") or metric.get("cvssV3_0") or metric.get("cvssV3")
                            if cvss_data and cvss_data.get("baseScore") is not None:
                                score_cvss = float(cvss_data["baseScore"])
                                severite = map_severite_cvss_simple(score_cvss)
                                break
                        if severite != "INCONNUE":
                            break

                # Chercher dans vulnerabilities[].scores (format CSAF)
                if severite == "INCONNUE" and isinstance(vulns_csaf, list):
                    for v in vulns_csaf:
                        for score_entry in v.get("scores", []) or []:
                            cvss3 = score_entry.get("cvss_v3") or {}
                            base = cvss3.get("baseScore")
                            if base is not None:
                                score_cvss = float(base)
                                severite = map_severite_cvss_simple(score_cvss)
                                break
                        if severite != "INCONNUE":
                            break

                # ─── Classification de la menace ────────────────────────────
                texte_complet = f"{titre} {description}"
                type_menace = classifier_menace_texte_simple(texte_complet)
                
                # Si "Inconnu" mais que c'est une vulnérabilité, mettre "Piratage"
                if type_menace == "Inconnu" and ("vulnerab" in texte_complet.lower() or 
                                                   "overflow" in texte_complet.lower() or
                                                   "memory" in texte_complet.lower()):
                    type_menace = "Piratage"
               
                secteur = "Inconnu"
                for affected in item.get("affected", []):
                    pkg = affected.get("package", {})
                    eco = pkg.get("ecosystem", "")
                    if "wordpress" in eco or "plugin" in eco:
                        secteur = "Commerce_Retail"
                        break
                    elif "crates" in eco or "npm" in eco or "pypi" in eco or "maven" in eco or "java" in eco:
                        secteur = "IT_Telecom"
                        break
                
                # ─── MAPPING VERS LES CODES OFFICIELS DU GUIDE CMRPI ────────
                type_menace = map_menace_to_official_simple(type_menace)
                secteur = map_secteur_to_official_simple(secteur)
                
                # Mapper la sévérité vers les codes officiels
                severite = map_severite_to_official_simple(severite)
                
                # ─── URL source ──────────────────────────────────────────────
                url_source = f"https://vulnerability.circl.lu/vuln/{vuln_id}"
                
                refs = item.get("references", [])
                for ref in refs:
                    if ref.get("type") == "WEB" and ref.get("url"):
                        url_source = ref["url"]
                        break
                
                # ─── Création de l'alerte ────────────────────────────────────
                source_ext_id = vuln_id
                
                alertes.append({
                    "source_ext_id": source_ext_id,
                    "titre": titre[:300] if titre else vuln_id,
                    "description": description[:1000] if description else f"Vulnérabilité {vuln_id}",
                    "date_incident": date_incident,
                    "type_menace": type_menace,
                    "severite": severite,
                    "secteur_cible": secteur,
                    "url_source": url_source,
                    "score_cvss": score_cvss,
                    "raw_data": item,
                })

            if nb_ignores_sans_id:
                logger.warning(
                    f"CIRCL: {nb_ignores_sans_id}/{len(items)} item(s) ignoré(s) — "
                    f"aucun ID reconnu dans les formats supportés (OSV / CVE JSON 5.0 / "
                    f"cve-search). Clés du premier item ignoré : {premier_item_ignore_brut}. "
                    f"Si ce nombre est élevé, l'API a probablement encore changé de format "
                    f"— comparer ces clés avec ce que le code sait lire (id, cveMetadata.cveId, cve_id)."
                )

        except requests.exceptions.Timeout:
            logger.error("CIRCL: timeout")
            return self._get_demo_data()
        except requests.exceptions.RequestException as e:
            logger.error(f"CIRCL erreur réseau: {e}")
            return self._get_demo_data()
        except Exception as e:
            logger.error(f"CIRCL erreur: {e}")
            return self._get_demo_data()
        
        if not alertes:
            logger.warning("CIRCL: aucune alerte valide trouvée, utilisation des données démo")
            return self._get_demo_data()
        
        logger.info(f"CIRCL: {len(alertes)} alertes collectées")
        return alertes
    
    def _get_demo_data(self) -> List[Dict[str, Any]]:
        """Données de démonstration avec codes officiels."""
        return [
            {
                "source_ext_id": "OSV-2026-521",
                "titre": "OSV-2026-521: UNKNOWN READ in assimp",
                "description": "OSS-Fuzz report: UNKNOWN READ in unsigned long Assimp::StreamReader<true, true>::Get<unsigned long>",
                "date_incident": datetime(2026, 4, 4),
                "type_menace": "PIRATAGE",
                "severite": "MOYENNE",
                "secteur_cible": "TELECOM",
                "url_source": "https://bugs.chromium.org/p/oss-fuzz/issues/detail?id=499121788",
                "score_cvss": 5.0,
                "raw_data": {"source": "demo"},
            },
            {
                "source_ext_id": "RUSTSEC-2026-0198",
                "titre": "RUSTSEC-2026-0198: error-stack memory corruption",
                "description": "`Report::frames_mut` allows aliased mutable references causing undefined behavior.",
                "date_incident": datetime(2026, 7, 3),
                "type_menace": "PIRATAGE",
                "severite": "ELEVEE",
                "secteur_cible": "TELECOM",
                "url_source": "https://rustsec.org/advisories/RUSTSEC-2026-0198.html",
                "score_cvss": 7.5,
                "raw_data": {"source": "demo"},
            },
            {
                "source_ext_id": "OSV-2024-679",
                "titre": "OSV-2024-679: Heap-buffer-overflow in kimageformats",
                "description": "Heap-buffer-overflow WRITE 1 in readImage4v2",
                "date_incident": datetime(2024, 7, 25),
                "type_menace": "PIRATAGE",
                "severite": "ELEVEE",
                "secteur_cible": "TELECOM",
                "url_source": "https://bugs.chromium.org/p/oss-fuzz/issues/detail?id=70554",
                "score_cvss": 7.5,
                "raw_data": {"source": "demo"},
            },
        ]


if __name__ == "__main__":
    print("=" * 60)
    print("  TEST DU COLLECTEUR CIRCL (Format OSV)")
    print("=" * 60)
    
    collector = CIRCLCollector()
    result = collector.run(nb_cve=20)
    
    print("\n" + "=" * 60)
    print("  RÉSULTAT")
    print("=" * 60)
    print(f"  Source: {result.get('source')}")
    print(f"  Alertes trouvées: {result.get('alertes_trouvees', 0)}")
    print(f"  Nouvelles insérées: {result.get('nouvelles_inserees', 0)}")
    print(f"  Statut: {result.get('statut')}")
    print("=" * 60)