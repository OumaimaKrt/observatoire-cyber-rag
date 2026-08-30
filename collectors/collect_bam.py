# collectors/collect_bam.py
import requests
import hashlib
from datetime import datetime
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from utils.http_retry import get_with_retry


import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collectors.base import BaseCollector
from utils.classifiers import (
    classifier_menace_texte_simple,
    map_niveau_risque_texte_simple,
    parse_date_fr,
    map_menace_to_official_simple,    
    map_secteur_to_official_simple,    
)
from utils.logger import get_logger

logger = get_logger("collect_bam")

BAM_COMMUNIQUES_URL = "https://www.bkam.ma/Communiques"
MOTS_FRAUDE = [
    "fraude", "frauduleu", "phishing", "hameçonnage", "hamecon",
    "usurpation", "faux sms", "faux e-mail", "faux email", "faux message",
    "arnaque", "piratage", "skimming", "contrefait", "contrefaçon",
    "cybersécurité", "cyberattaque", "cyber-attaque", "vol de données",
    "escroquerie", "cybercriminalité", "sécurité informatique",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "fr,fr-FR;q=0.9",
}


class BAMCollector(BaseCollector):
    """
    Collecteur Bank Al-Maghrib — communiqués de fraude/sécurité bancaire.
    Utilise le save() standard de BaseCollector → cyber_incidents.
    """
    source_name = "BAM_Maroc"
    langue = "fr"
    pays = "MA"

    def collect(self, max_pages: int = 3) -> List[Dict[str, Any]]:
        logger.info(f"Collecte BAM — {BAM_COMMUNIQUES_URL} ({max_pages} page(s))")
        alertes = []
        pages_echouees = 0

        for page in range(max_pages):
            offset = page * 20
            url_page = BAM_COMMUNIQUES_URL if offset == 0 else f"{BAM_COMMUNIQUES_URL}?limit=0&offset={offset}"

            # Chaque page est indépendante : un timeout/erreur réseau ────
            # sur UNE page ne doit pas interrompre le scan des pages suivantes
            # (sinon on perd tout l'historique restant pour un simple aléa
            # réseau, comme observé sur bkam.ma qui peut être lent par moments).
            liens = None
            for tentative in range(2):  # 1 essai + 1 retry
                try:
                    resp = get_with_retry(
                        url_page,
                        headers=HEADERS,
                        timeout=20,
                        tentatives=3,
                        backoff_seconds=3.0,
                        logger_prefix="BAM"
                    )
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, "html.parser")
                    liens = [
                        a for a in soup.find_all("a", href=True)
                        if a.get_text(strip=True) == "Lire la suite"
                        and "/Communiques/" in a["href"]
                        and "?" not in a["href"]
                    ]
                    break
                except requests.exceptions.RequestException as e:
                    if tentative == 0:
                        logger.warning(f"BAM page {page+1} — erreur ({e}), retry...")
                    else:
                        logger.warning(f"BAM page {page+1} — échec définitif ({e}), page ignorée.")
                        pages_echouees += 1

            if liens is None:
                continue  # cette page a échoué même après retry, on passe à la suivante

            if not liens:
                logger.warning(f"BAM page {page+1} — aucun communiqué trouvé, arrêt pagination.")
                break

            logger.info(f"BAM page {page+1} — {len(liens)} communiqué(s) trouvé(s)")
            logger.info(f"BAM page {page+1} — premier titre: {liens[0].get('title', '')[:80]}")

            for a in liens:
                href = a["href"]
                titre = a.get("title", "").strip() or href.rsplit("/", 1)[-1].replace("-", " ")

                texte_verif = titre.lower()
                if not any(mot in texte_verif for mot in MOTS_FRAUDE):
                    continue  # pas un communiqué fraude/sécurité, on ignore

                url_complete = href if href.startswith("http") else f"https://www.bkam.ma{href}"
                try:
                    alerte = self._construire_alerte(url_complete, titre)
                    if alerte:
                        alertes.append(alerte)
                except Exception as e:
                    logger.warning(f"BAM: erreur sur l'article {url_complete} ({e}), ignoré.")

        if pages_echouees:
            logger.warning(f"BAM: {pages_echouees} page(s) définitivement inaccessible(s) sur {max_pages}.")

        logger.info(f"BAM: {len(alertes)} alerte(s) fraude/sécurité collectée(s)")
        return alertes

    def _construire_alerte(self, url: str, titre: str) -> Dict[str, Any]:
        """Va chercher le détail de l'article pour la description et la date réelle."""
        description = ""
        date_incident = None
        nom_pdf = ""

        try:
            resp = get_with_retry(
                url,
                headers=HEADERS,
                timeout=15,
                tentatives=3,
                backoff_seconds=3.0,
                logger_prefix="BAM"
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Le corps de l'article est généralement dans la zone de contenu
            # principal ; on prend les paragraphes disponibles en fallback.
            paragraphes = [p.get_text(strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
            texte_complet = " ".join(paragraphes)
            description = texte_complet[:1000]
            date_incident = parse_date_fr(texte_complet)

            # Certains communiqués (notamment les archives) n'ont AUCUN texte
            # dans la page : le "contenu" est juste un lien de téléchargement
            # PDF dont le nom de fichier encode l'année, ex:
            # ".../communique_sms_2013.pdf". On cible spécifiquement ce lien
            # plutôt que de chercher un nombre à 4 chiffres dans tout le HTML
            # brut (qui contient des dizaines de faux positifs : IDs d'images,
            # de traductions, etc.)
            if not date_incident:
                lien_pdf = soup.find("a", href=lambda h: h and h.lower().endswith(".pdf"))
                if lien_pdf:
                    nom_pdf = lien_pdf["href"].rsplit("/", 1)[-1]

        except Exception as e:
            logger.warning(f"BAM: impossible de charger le détail de {url} ({e})")

        import re
        if not date_incident:
            # Fallback 1 : année présente dans l'URL 
            m = re.search(r"/(\d{4})/", url)
            if m:
                date_incident = datetime(int(m.group(1)), 1, 1)

        if not date_incident and nom_pdf:
            # Fallback 2 : année dans le nom du fichier PDF 
            m2 = re.search(r"(\d{4})", nom_pdf)
            if m2 and 2000 <= int(m2.group(1)) <= 2029:
                date_incident = datetime(int(m2.group(1)), 1, 1)

        if not date_incident:
            # Fallback 3 : une année à 4 chiffres plausible dans le titre
            m3 = re.search(r"\b(20[0-2]\d)\b", titre)
            if m3:
                date_incident = datetime(int(m3.group(1)), 1, 1)
            else:
                # Dernier recours : on ne connaît vraiment pas la date.
                # On ne met SURTOUT PAS datetime.utcnow() ici : ça ferait
                # croire qu'un communiqué est d'aujourd'hui alors qu'on
                # n'en sait rien. On logue plutôt le problème.
                logger.warning(f"BAM: date introuvable pour « {titre} » ({url}), date laissée à None.")

        # ─── CLASSIFICATION AVEC MAPPING OFFICIEL ──────────────────────────────
        texte_classif = f"{titre} {description}"
        type_menace = classifier_menace_texte_simple(texte_classif)
        severite = map_niveau_risque_texte_simple(texte_classif)

        # Mapper vers les codes officiels du guide CMRPI
        type_menace = map_menace_to_official_simple(type_menace)
        secteur = map_secteur_to_official_simple("Finance_Assurance")

        # Si le classifieur a retourné INCONNU, on garde le signal du filtre
        if type_menace == "INCONNU":
            if any(m in texte_classif.lower() for m in ["sms", "e-mail", "email", "message"]):
                type_menace = "PHISHING"
            else:
                type_menace = "ESCROQUERIE"

        return {
            "source_ext_id": hashlib.sha256(f"BAM|{url}".encode()).hexdigest()[:32],
            "titre": titre[:300],
            "description": description or titre,
            "date_incident": date_incident,
            "type_menace": type_menace,
            "secteur_cible": secteur,
            "severite": severite,
            "url_source": url,
            "raw_data": {"source": "BAM", "titre": titre, "url": url},
        }


if __name__ == "__main__":
    print("=" * 60)
    print("  TEST DU COLLECTEUR BANK AL-MAGHRIB (fraude/phishing)")
    print("=" * 60)

    collector = BAMCollector()
    result = collector.run(max_pages=59)

    print("\n" + "=" * 60)
    print("  RÉSULTAT")
    print("=" * 60)
    print(f"  Source: {result.get('source')}")
    print(f"  Alertes trouvées: {result.get('alertes_trouvees', 0)}")
    print(f"  Nouvelles insérées: {result.get('nouvelles_inserees', 0)}")
    print(f"  Statut: {result.get('statut')}")
    print("=" * 60)