# collectors/base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
import psycopg2
import json
import hashlib
import re
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DB_CONFIG
from utils.logger import get_logger
from utils.pertinence_pme import evaluer_pertinence_pme
from utils.classifiers import (
    classifier_cyber_complet,
    normaliser_menace,
    normaliser_secteur,
    normaliser_severite,
)

logger = get_logger("base_collector")


class BaseCollector(ABC):
    source_name: str = "UNKNOWN_SOURCE"
    langue: str = "fr"
    pays: str = "MA"

    def __init__(self, db_config: Optional[dict] = None):
        self.db_config = db_config or DB_CONFIG

    # ─── CORRECTION ENCODAGE ────────────────────────────────────────────────
    
    def fix_encoding(self, text: str) -> str:
        """
        Corrige les problèmes d'encodage courants.
        """
        if not text or not isinstance(text, str):
            return text
        
        replacements = {
            # Latin-1 / UTF-8 mojibake
            'Ã©': 'é',
            'Ã¨': 'è',
            'Ãª': 'ê',
            'Ã«': 'ë',
            'Ã ': 'à',
            'Ã¢': 'â',
            'Ã¤': 'ä',
            'Ã´': 'ô',
            'Ã¶': 'ö',
            'Ã»': 'û',
            'Ã¼': 'ü',
            'Ã¯': 'ï',
            'Ã®': 'î',
            'Ã§': 'ç',
            'Ã¹': 'ù',
            'Ã‰': 'É',
            'Ãˆ': 'È',
            'ÃŠ': 'Ê',
            'Ã€': 'À',
            'Ã‡': 'Ç',
            'Ã”': 'Ô',
            'Ã›': 'Û',
            'Å“': 'œ',
            'Å’': 'Œ',
            # Curly quotes / apostrophes
            'â€™': "'",
            'â€œ': '"',
            'â€': '"',
            'â€\x9d': '"',
            'â€¦': '...',
            'â€”': '—',
            'â€“': '–',
            # Supplémentaires
            '\ufffd': ' ',
            '\u00b4': "'",
            '\u2026': '...',
            '\xa0': ' ',
            '\x0c': ' ',
            '\xad': '-',
            '\u2122': 'TM',
            '\u00a9': '(c)',
            '\u00ae': '(R)',
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Supprimer les caractères de contrôle
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', ' ', text)
        # Normaliser les espaces
        text = re.sub(r'\s+', ' ', text)
        # Nettoyer les espaces en début/fin
        text = text.strip()
        
        return text
    
    def clean_field(self, value: str) -> str:
        """
        Nettoie un champ texte (encodage + nettoyage).
        """
        if not value or not isinstance(value, str):
            return value
        return self.fix_encoding(value)

    @abstractmethod
    def collect(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Méthode principale de collecte.
        Doit retourner une liste d'alertes normalisées.
        """
        pass

    def normalize(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalise une alerte brute au format standard.
        Avec correction d'encodage sur les champs texte.
        Utilise classifier_cyber_complet pour une classification complète.
        """
        # CORRECTION ENCODAGE
        titre = self.clean_field(raw.get("titre", ""))
        description = self.clean_field(raw.get("description", raw.get("resume", "")))

        # Pertinence PME calculée automatiquement pour TOUTES les sources
        niveau_pme, technos_pme = evaluer_pertinence_pme(f"{titre} {description}")

        # Classification complète avec classifier_cyber_complet
        try:
            result = classifier_cyber_complet(
                titre=titre,
                description=description,
                raw_data=raw.get("raw_data", {}),
                score_cvss=raw.get("score_cvss")
            )
        except Exception as e:
            logger.warning(f"Erreur classification pour {self.source_name}: {e}")
            # Fallback avec valeurs par défaut
            result = {
                "type_menace": "INCONNU",
                "secteur_cible": "INCONNU",
                "severite": "INCONNU",
                "confiance_menace": 0.0,
                "confiance_secteur": 0.0,
                "confiance_severite": 0.0,
                "confiance_globale": 0.0,
                "niveau_confiance": "FAIBLE",
                "risque": 0,
                "acteur_menace": "",
                "preuves": {"menace": [], "secteur": [], "severite": []},
            }

        return {
            "source": self.source_name,
            "source_ext_id": raw.get("source_ext_id", ""),
            "titre": titre,
            "description": description,
            "date_incident": raw.get("date_incident", datetime.now()),
            "type_menace": result.get("type_menace", "INCONNU"),
            "secteur_cible": result.get("secteur_cible", "INCONNU"),
            "severite": result.get("severite", "INCONNU"),
            "url_source": raw.get("url_source", ""),
            "langue": self.langue,
            "pays": self.pays,
            "score_cvss": raw.get("score_cvss"),
            "pertinence_pme": niveau_pme,
            "technologies_detectees": technos_pme,
            "raw_data": raw.get("raw_data", {}),
            "confiance_type": result.get("confiance_menace", 0.0),
            "confiance_secteur": result.get("confiance_secteur", 0.0),
            "confiance_severite": result.get("confiance_severite", 0.0),
            "confiance_globale": result.get("confiance_globale", 0.0),
            "niveau_confiance_type": result.get("niveau_confiance", "FAIBLE"),
            "niveau_confiance_secteur": result.get("niveau_confiance", "FAIBLE"),
            "niveau_confiance_severite": result.get("niveau_confiance", "FAIBLE"),
            "risque": result.get("risque", 0),
            "acteur_menace": result.get("acteur_menace", ""),
            "preuves_menace": result.get("preuves", {}).get("menace", []),
            "preuves_secteur": result.get("preuves", {}).get("secteur", []),
            "preuves_severite": result.get("preuves", {}).get("severite", []),
        }

    def stable_id(self, alerte: Dict[str, Any]) -> str:
        """Génère un ID déterministe pour le dédoublonnage."""
        base = f"{self.source_name}|{alerte.get('titre', '')}|{alerte.get('url_source', '')}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()[:32]

    def save(self, alertes: List[Dict[str, Any]]) -> int:
        """
        Sauvegarde les alertes en base (cyber_incidents).
        Retourne le nombre d'alertes réellement nouvelles.
        Avec correction d'encodage via normalize()
        """
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        total_nouvelles = 0

        try:
            # Récupérer l'ID de la source dans sources_donnees
            cur.execute("SELECT id FROM sources_donnees WHERE nom = %s", (self.source_name,))
            row = cur.fetchone()
            source_id = row[0] if row else None
            
            if source_id is None:
                logger.warning(f"⚠️ Source '{self.source_name}' non trouvée dans sources_donnees")
                logger.warning(f"   → Les incidents seront insérés avec source_id NULL")

            for alerte in alertes:
                # normalize() applique déjà clean_field() sur titre et description
                alerte_norm = self.normalize(alerte)
                
                alerte_id = self.stable_id(alerte_norm)
                source_ext_id = alerte_norm.get("source_ext_id") or alerte_id

                cur.execute("""
                    INSERT INTO cyber_incidents (
                        source_id, source, source_ext_id, titre, description,
                        date_incident, type_menace, secteur_cible,
                        severite, url_source, langue, pays,
                        score_cvss, pertinence_pme, technologies_detectees, raw_data,
                        confiance_type, confiance_secteur, confiance_severite, confiance_globale,
                        niveau_confiance_type, niveau_confiance_secteur, niveau_confiance_severite,
                        risque, acteur_menace,
                        preuves_menace, preuves_secteur, preuves_severite
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_ext_id) DO NOTHING;
                """, (
                    source_id,
                    self.source_name,
                    source_ext_id,
                    alerte_norm["titre"][:300] if alerte_norm["titre"] else "",
                    alerte_norm["description"][:1000] if alerte_norm["description"] else "",
                    alerte_norm["date_incident"],
                    alerte_norm["type_menace"],
                    alerte_norm["secteur_cible"],
                    alerte_norm["severite"],
                    alerte_norm["url_source"],
                    alerte_norm["langue"],
                    alerte_norm["pays"],
                    alerte_norm.get("score_cvss"),
                    alerte_norm.get("pertinence_pme", "INCONNUE"),
                    alerte_norm.get("technologies_detectees", []),
                    json.dumps(alerte_norm["raw_data"], default=str),
                    # NOUVELLES COLONNES
                    alerte_norm.get("confiance_type", 0.0),
                    alerte_norm.get("confiance_secteur", 0.0),
                    alerte_norm.get("confiance_severite", 0.0),
                    alerte_norm.get("confiance_globale", 0.0),
                    alerte_norm.get("niveau_confiance_type", "FAIBLE"),
                    alerte_norm.get("niveau_confiance_secteur", "FAIBLE"),
                    alerte_norm.get("niveau_confiance_severite", "FAIBLE"),
                    alerte_norm.get("risque", 0),
                    alerte_norm.get("acteur_menace", ""),
                    alerte_norm.get("preuves_menace", []),
                    alerte_norm.get("preuves_secteur", []),
                    alerte_norm.get("preuves_severite", []),
                ))

                if cur.rowcount > 0:
                    total_nouvelles += 1

            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Erreur sauvegarde {self.source_name}: {e}")
            raise e
        finally:
            cur.close()
            conn.close()

        return total_nouvelles

    def _finaliser_historique(
        self,
        hist_id: Optional[int],
        statut: str,
        alertes_trouvees: Optional[int] = None,
        nouvelles_inserees: Optional[int] = None,
        duree_secondes: Optional[float] = None,
        erreur: Optional[str] = None,
    ) -> None:

        if not hist_id:
            return
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        try:
            cur.execute("""
                UPDATE historique_collecte
                SET date_fin = %s, statut = %s, erreur = %s,
                    alertes_trouvees = COALESCE(%s, alertes_trouvees),
                    nouvelles_inserees = COALESCE(%s, nouvelles_inserees),
                    duree_secondes = COALESCE(%s, duree_secondes)
                WHERE id = %s;
            """, (datetime.now(), statut, erreur, alertes_trouvees, nouvelles_inserees, duree_secondes, hist_id))

            if statut == "SUCCES" and nouvelles_inserees is not None:
                cur.execute("""
                    UPDATE sources_donnees
                    SET derniere_collecte = %s, nb_incidents = nb_incidents + %s
                    WHERE nom = %s;
                """, (datetime.now(), nouvelles_inserees, self.source_name))

            conn.commit()
        except Exception as e:
            logger.warning(f"Erreur mise à jour historique ({statut}): {e}")
        finally:
            cur.close()
            conn.close()

    def run(self, **kwargs) -> dict:
        """
        Exécute la collecte, sauvegarde et retourne des métriques.
        """
        debut = datetime.now()

        # Insérer le début de la collecte dans historique_collecte
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO historique_collecte (source, date_debut, statut)
                VALUES (%s, %s, 'EN_COURS')
                RETURNING id;
            """, (self.source_name, debut))
            hist_id = cur.fetchone()[0]
            conn.commit()
        except Exception as e:
            logger.warning(f"Impossible d'insérer dans historique_collecte: {e}")
            hist_id = None
        finally:
            cur.close()
            conn.close()

        try:
            try:
                alertes = self.collect(**kwargs)
                nouvelles = self.save(alertes)
                fin = datetime.now()
                duree = (fin - debut).total_seconds()

                logger.info(f" {self.source_name}: {len(alertes)} trouvées, {nouvelles} nouvelles")

                self._finaliser_historique(
                    hist_id, statut="SUCCES",
                    alertes_trouvees=len(alertes), nouvelles_inserees=nouvelles, duree_secondes=duree,
                )

                return {
                    "source": self.source_name,
                    "alertes_trouvees": len(alertes),
                    "nouvelles_inserees": nouvelles,
                    "duree_secondes": duree,
                    "statut": "SUCCES",
                    "historique_id": hist_id,
                }
            except Exception as e:
                logger.error(f" {self.source_name}: {e}")
                self._finaliser_historique(hist_id, statut="ECHEC", erreur=str(e))
                return {
                    "source": self.source_name,
                    "statut": "ECHEC",
                    "erreur": str(e),
                    "historique_id": hist_id,
                }
        except BaseException:
            
            self._finaliser_historique(hist_id, statut="ECHEC", erreur="Interrompu (Ctrl+C ou signal système)")
            raise