# collectors/base_news.py
# =============================================================================
# Classe de base pour les collecteurs de news sectorielles
# =============================================================================
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import psycopg2
import json
import hashlib
import re
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collectors.base import BaseCollector
from config import DB_CONFIG
from utils.logger import get_logger
from utils.classifiers import (
    classifier_cyber_complet,
    normaliser_menace,
    normaliser_secteur,
    normaliser_severite,
)

logger = get_logger("base_news_collector")


class BaseNewsCollector(BaseCollector):
    """
    Classe de base pour les collecteurs de news sectorielles.
    AVEC FILTRAGE CYBERSÉCURITÉ INTÉGRÉ.
    """
    
    categorie_defaut: str = "Inconnu"
    
    # --- MOTS-CLÉS CYBER POUR FILTRAGE ---
    CYBER_KEYWORDS = [
        # Mots-clés forts (obligatoires pour garder l'article)
        "cyber", "sécurité", "securite", "cybersécurité", "cybersecurite",
        "cyberattaque", "piratage", "hacker", "ransomware", "phishing", 
        "hameçonnage", "malware", "virus", "vulnérabilité", "vulnerabilite",
        "faille", "exploit", "zero-day", "CVE", "backdoor", "porte dérobée",
        "DGSSI", "maCERT", "CNDP", "ANRT", "RGPD", "CNPD",
        "menace", "attaque", "intrusion", "espionnage",
        "sécurité informatique", "protection des données",
        "ausimètre", "baromètre de la cybersécurité",
        "cloud sécurisé", "données personnelles",
    ]
    
    # --- MOTS-CLÉS D'EXCLUSION ---
    EXCLUSION_KEYWORDS = [
        "football", "mondial", "coupe du monde", "joueur", "équipe", "fifa",
        "roi", "trône", "accession au trône",
        "viande", "ovine", "consommation", "prix",
        "météo", "chaleur", "pluie", "température",
        "mariage", "naissance", "décès", "hommage",
        "sport", "culture", "cinéma", "musique", "artiste", "chanteur",
        "protocole", "cérémonie", "visite officielle",
        "élection", "politique", "parti", "partis politiques",
        "jour férié", "gta", "jeux vidéo",
    ]
    
    def __init__(self, db_config: dict, filter_cyber: bool = True):
        """
        Initialise le collecteur.
        
        Args:
            db_config: Configuration de la base de données
            filter_cyber: Si True, filtre les articles non cyber
        """
        super().__init__(db_config)
        self.filter_cyber = filter_cyber
        logger.info(f"Initialisation de {self.source_name} (filtrage: {filter_cyber})")
    
    # ─── FILTRAGE CYBER ────────────────────────────────────────────────────────
    
    def is_cyber_article(self, titre: str, description: str = "") -> Tuple[bool, str]:
        """
        Vérifie si un article est pertinent pour la cybersécurité.
        
        Returns:
            (est_pertinent, raison)
        """
        texte = f"{titre} {description}".lower()
        
        # 1. Vérifier les exclusions (prioritaires)
        for excl in self.EXCLUSION_KEYWORDS:
            if excl in texte:
                return False, f"EXCLU: {excl}"
        
        # 2. Vérifier les mots-clés cyber
        for mot in self.CYBER_KEYWORDS:
            if mot in texte:
                return True, f"GARDÉ: {mot}"
        
        # 3. Vérifier les sources marocaines de cybersécurité
        sources_cyber = ["dgssi", "macert", "cndp", "anrt", "ausimètre"]
        for src in sources_cyber:
            if src in texte:
                return True, f"GARDÉ: source {src}"
        
        return False, "REJETÉ: aucun mot-clé"
    
    def filter_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filtre les articles pour ne garder que ceux pertinents pour la cybersécurité.
        """
        if not self.filter_cyber:
            logger.info(f"{self.source_name}: Filtrage désactivé, tous les articles sont conservés")
            return articles
        
        kept = []
        rejected = []
        
        for article in articles:
            titre = article.get("titre", "")
            description = article.get("description", "")
            
            pertinent, raison = self.is_cyber_article(titre, description)
            
            if pertinent:
                kept.append(article)
            else:
                rejected.append(article)
        
        if rejected:
            logger.info(f"{self.source_name}: {len(rejected)} article(s) rejeté(s) (hors cybersécurité)")
        
        if kept:
            logger.info(f"{self.source_name}: {len(kept)} article(s) gardé(s)")
        
        return kept
    
    # ─── CORRECTION ENCODAGE ────────────────────────────────────────────────
    
    def fix_encoding(self, text: str) -> str:
        """
        Corrige les problèmes d'encodage courants.
        """
        if not text or not isinstance(text, str):
            return text
        
        replacements = {
            # Latin-1 / UTF-8 mojibake
            'Ã©': 'é', 'Ã¨': 'è', 'Ãª': 'ê', 'Ã«': 'ë',
            'Ã ': 'à', 'Ã¢': 'â', 'Ã¤': 'ä', 'Ã´': 'ô',
            'Ã¶': 'ö', 'Ã»': 'û', 'Ã¼': 'ü', 'Ã¯': 'ï',
            'Ã®': 'î', 'Ã§': 'ç', 'Ã¹': 'ù',
            'Ã‰': 'É', 'Ãˆ': 'È', 'ÃŠ': 'Ê', 'Ã€': 'À',
            'Ã‡': 'Ç', 'Ã”': 'Ô', 'Ã›': 'Û',
            'Å“': 'œ', 'Å’': 'Œ',
            # Curly quotes
            'â€™': "'", 'â€œ': '"', 'â€': '"',
            'â€\x9d': '"', 'â€¦': '...',
            # Supplémentaires
            '\ufffd': ' ', '\u00b4': "'", '\u2026': '...',
            '\xa0': ' ', '\x0c': ' ', '\xad': '-',
            '\u2122': 'TM', '\u00a9': '(c)', '\u00ae': '(R)',
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Supprimer les caractères de contrôle
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', ' ', text)
        # Normaliser les espaces
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    def clean_field(self, value: str) -> str:
        if not value or not isinstance(value, str):
            return value
        return self.fix_encoding(value)
    
    # ─── NORMALISATION ──────────────────────────────────────────────────────
    
    def normalize(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        titre = self.clean_field(raw.get("titre", ""))
        description = self.clean_field(raw.get("description", ""))

        try:
            result = classifier_cyber_complet(
                titre=titre,
                description=description,
                raw_data=raw.get("raw_data", {})
            )
        except Exception as e:
            logger.warning(f"Erreur classification pour {self.source_name}: {e}")
            result = {
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
            "date_publication": raw.get("date_publication", datetime.now()),
            "categorie": raw.get("categorie", self.categorie_defaut),
            "url_source": raw.get("url_source", ""),
            "langue": self.langue,
            "pays": self.pays,
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
        base = f"{self.source_name}|{alerte.get('titre', '')}|{alerte.get('url_source', '')}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()[:32]
    
    # ─── SAUVEGARDE ─────────────────────────────────────────────────────────
    
    def save_sector_news(self, articles: List[Dict[str, Any]]) -> int:
        """
        Sauvegarde les articles dans sector_news.
        AVEC FILTRAGE PRÉALABLE.
        """
        # FILTRAGE INTÉGRÉ
        articles = self.filter_articles(articles)
        
        if not articles:
            logger.info(f"{self.source_name}: Aucun article pertinent à sauvegarder")
            return 0
        
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        total_nouvelles = 0
        
        try:
            for article in articles:
                norm = self.normalize(article)
                stable = self.stable_id(norm)
                
                cur.execute("""
                    INSERT INTO sector_news (
                        source, source_ext_id, titre, description,
                        date_publication, categorie, url_source,
                        langue, pays, raw_data, created_at,
                        confiance_type, confiance_secteur, confiance_severite, confiance_globale,
                        niveau_confiance_type, niveau_confiance_secteur, niveau_confiance_severite,
                        risque, acteur_menace,
                        preuves_menace, preuves_secteur, preuves_severite
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(),
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_ext_id) DO NOTHING;
                """, (
                    self.source_name,
                    norm.get("source_ext_id") or stable,
                    norm["titre"][:300] if norm["titre"] else "",
                    (norm["description"] or "")[:1000],
                    norm["date_publication"],
                    norm["categorie"],
                    norm["url_source"],
                    norm["langue"],
                    norm["pays"],
                    json.dumps(norm["raw_data"], default=str),
                    norm.get("confiance_type", 0.0),
                    norm.get("confiance_secteur", 0.0),
                    norm.get("confiance_severite", 0.0),
                    norm.get("confiance_globale", 0.0),
                    norm.get("niveau_confiance_type", "FAIBLE"),
                    norm.get("niveau_confiance_secteur", "FAIBLE"),
                    norm.get("niveau_confiance_severite", "FAIBLE"),
                    norm.get("risque", 0),
                    norm.get("acteur_menace", ""),
                    norm.get("preuves_menace", []),
                    norm.get("preuves_secteur", []),
                    norm.get("preuves_severite", []),
                ))
                
                if cur.rowcount > 0:
                    total_nouvelles += 1
            
            conn.commit()
            logger.info(f"{self.source_name}: {total_nouvelles} nouveaux articles pertinents")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Erreur sauvegarde pour {self.source_name}: {e}")
            raise e
        finally:
            cur.close()
            conn.close()
        
        return total_nouvelles
    
    def run(self, **kwargs) -> Dict[str, Any]:
        """Exécute la collecte complète."""
        try:
            logger.info(f"📡 Collecte {self.source_name}...")
            articles = self.collect(**kwargs)
            
            if not articles:
                return {
                    "source": self.source_name,
                    "statut": "SUCCES",
                    "nouvelles_inserees": 0,
                    "total_trouves": 0
                }
            
            nouvelles = self.save_sector_news(articles)
            
            return {
                "source": self.source_name,
                "statut": "SUCCES",
                "nouvelles_inserees": nouvelles,
                "total_trouves": len(articles)
            }
            
        except Exception as e:
            logger.error(f"❌ Échec collecte {self.source_name}: {e}")
            return {
                "source": self.source_name,
                "statut": "ECHEC",
                "erreur": str(e)
            }