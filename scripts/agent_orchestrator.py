# ============================================================================
# agent_orchestrator.py
# Agent SQL - Exécute des requêtes sur PostgreSQL
# VERSION FINALE CORRIGÉE - AVEC STATISTIQUES AGRÉGÉES + FORMAT LLM
# ============================================================================

import re
import psycopg2


class SQLAgent:
    """
    Agent SQL - Exécute des requêtes sur PostgreSQL.
    """
    
    def __init__(self, db_conn):
        self.db = db_conn
    
    # ========================================================================
    # STATISTIQUES AGRÉGÉES
    # ========================================================================
    
    def get_total_incidents(self) -> dict:
        """Retourne le total des incidents par type de menace."""
        sql = """
            SELECT 
                type_menace,
                COUNT(*) as nb,
                ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM cyber_incidents WHERE type_menace != 'INCONNU'), 1) as pourcentage
            FROM cyber_incidents
            WHERE type_menace != 'INCONNU'
            GROUP BY type_menace
            ORDER BY nb DESC
        """
        try:
            cur = self.db.cursor()
            cur.execute(sql)
            results = cur.fetchall()
            cur.close()
            
            return {
                "success": True,
                "data": results,
                "label": "Répartition des incidents par type de menace",
                "result_kind": "threat_distribution"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "data": None}
    
    def get_total_count(self) -> dict:
        """Retourne le nombre total d'incidents."""
        sql = """
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN type_menace != 'INCONNU' THEN 1 END) as total_connus,
                COUNT(CASE WHEN severite = 'CRITIQUE' THEN 1 END) as nb_critiques,
                COUNT(CASE WHEN severite = 'ÉLEVÉE' THEN 1 END) as nb_eleves
            FROM cyber_incidents
        """
        try:
            cur = self.db.cursor()
            cur.execute(sql)
            results = cur.fetchall()
            cur.close()
            
            return {
                "success": True,
                "data": results,
                "label": "Vue d'ensemble des incidents",
                "result_kind": "overview"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "data": None}
    
    def get_incidents_by_severity(self) -> dict:
        """Retourne les incidents par sévérité."""
        sql = """
            SELECT 
                severite,
                COUNT(*) as nb
            FROM cyber_incidents
            WHERE severite != 'INCONNUE'
            GROUP BY severite
            ORDER BY 
                CASE severite
                    WHEN 'CRITIQUE' THEN 1
                    WHEN 'ÉLEVÉE' THEN 2
                    WHEN 'MOYENNE' THEN 3
                    WHEN 'FAIBLE' THEN 4
                    ELSE 5
                END
        """
        try:
            cur = self.db.cursor()
            cur.execute(sql)
            results = cur.fetchall()
            cur.close()
            
            return {
                "success": True,
                "data": results,
                "label": "Distribution des sévérités",
                "result_kind": "severity"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "data": None}
    
    def get_incidents_by_sector(self, secteur: str = None) -> dict:
        """Retourne les incidents par secteur cible."""
        sql = """
            SELECT 
                secteur_cible,
                COUNT(*) as nb,
                ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM cyber_incidents WHERE secteur_cible != 'INCONNU'), 1) as pourcentage
            FROM cyber_incidents
            WHERE secteur_cible != 'INCONNU'
        """
        if secteur:
            sql += f" AND secteur_cible = '{secteur.upper()}'"
        sql += " GROUP BY secteur_cible ORDER BY nb DESC"
        
        try:
            cur = self.db.cursor()
            cur.execute(sql)
            results = cur.fetchall()
            cur.close()
            
            return {
                "success": True,
                "data": results,
                "label": "Incidents par secteur cible"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "data": None}
    
    def get_incidents_by_source(self) -> dict:
        """Retourne les incidents par source."""
        sql = """
            SELECT 
                source,
                COUNT(*) as nb
            FROM cyber_incidents
            WHERE source != 'INCONNU' AND source != ''
            GROUP BY source
            ORDER BY nb DESC
            LIMIT 10
        """
        try:
            cur = self.db.cursor()
            cur.execute(sql)
            results = cur.fetchall()
            cur.close()
            
            return {
                "success": True,
                "data": results,
                "label": "Top 10 des sources d'incidents"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "data": None}
    
    # ========================================================================
    # DÉTECTION DES TYPES SPÉCIFIQUES
    # ========================================================================
    
    def get_incidents_by_type(self, type_menace: str) -> dict:
        """Retourne les incidents pour un type de menace spécifique."""
        sql = """
            SELECT 
                type_menace,
                COUNT(*) as total,
                COUNT(CASE WHEN severite = 'CRITIQUE' THEN 1 END) as critiques,
                ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM cyber_incidents WHERE type_menace != 'INCONNU'), 1) as pourcentage
            FROM cyber_incidents
            WHERE type_menace = %s
            GROUP BY type_menace
        """
        try:
            cur = self.db.cursor()
            cur.execute(sql, (type_menace.upper(),))
            results = cur.fetchall()
            cur.close()
            
            types_labels = {
                'PIRATAGE': 'Incidents de piratage',
                'RANSOMWARE': 'Incidents de ransomware',
                'PHISHING': 'Incidents de phishing',
                'DDOS': 'Incidents DDoS',
                'VULNERABILITE': 'Incidents de vulnérabilité',
                'CHEVAL_TROIE': 'Incidents de cheval de Troie',
                'SPYWARE': 'Incidents de spyware',
                'VIRUS': 'Incidents de virus',
                'BLANCHIMENT': 'Incidents de blanchiment',
                'ESCROQUERIE': 'Incidents d\'escroquerie',
                'SPOOFING': 'Incidents de spoofing',
                'FUITE_DONNEES': 'Incidents de fuite de données',
                'INCIDENT': 'Incidents divers',
            }
            
            label = types_labels.get(type_menace.upper(), f"Incidents de {type_menace.lower()}")
            
            return {
                "success": True,
                "data": results,
                "label": label,
                "result_kind": "threat_type"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "data": None}
    
    # ========================================================================
    # 🔥 FORMATAGE DES STATISTIQUES POUR LE LLM
    # ========================================================================
    
    def format_stats_for_llm(self, result: dict) -> str:
        """
        Formate les résultats SQL en texte CLAIR pour que le LLM les utilise.
        🔥 CRITIQUE : Les chiffres sont présentés de manière explicite.
        """
        if not result or not result.get("success"):
            return ""
        
        data = result.get("data") or []
        if not data:
            return ""
        
        kind = result.get("result_kind", "")
        label = result.get("label", "Statistiques")
        
        lines = [f"📊 {label} :"]
        
        if kind == "threat_type":
            # Format: (type, total, critiques, pourcentage)
            for row in data:
                if len(row) >= 4:
                    type_menace = row[0]
                    total = row[1]
                    critiques = row[2]
                    pct = row[3]
                    lines.append(f"  • {type_menace} : {total} incidents (dont {critiques} critiques) — {pct}% du total")
                elif len(row) >= 3:
                    type_menace = row[0]
                    total = row[1]
                    pct = row[2]
                    lines.append(f"  • {type_menace} : {total} incidents — {pct}% du total")
        
        elif kind == "overview":
            # Format: (total, connus, critiques, eleves)
            row = data[0]
            if len(row) >= 4:
                lines.append(f"  • Total d'incidents : {row[0]}")
                lines.append(f"  • Incidents avec type connu : {row[1]}")
                lines.append(f"  • Incidents CRITIQUES : {row[2]}")
                lines.append(f"  • Incidents ÉLEVÉS : {row[3]}")
            elif len(row) >= 3:
                lines.append(f"  • Total : {row[0]}")
                lines.append(f"  • Critiques : {row[2]}")
        
        elif kind == "threat_distribution":
            # Format: (type, count, percentage)
            for row in data:
                if len(row) >= 3:
                    type_menace = row[0]
                    count = row[1]
                    pct = row[2]
                    lines.append(f"  • {type_menace} : {count} incidents ({pct}%)")
        
        elif kind == "severity":
            # Format: (severite, count)
            for row in data:
                if len(row) >= 2:
                    lines.append(f"  • {row[0]} : {row[1]} incidents")
        
        else:
            # Format générique (fallback)
            for row in data:
                if len(row) == 1:
                    lines.append(f"  • {row[0]}")
                elif len(row) == 2:
                    lines.append(f"  • {row[0]} : {row[1]}")
                elif len(row) == 3:
                    lines.append(f"  • {row[0]} : {row[1]} ({row[2]}%)")
                else:
                    lines.append(f"  • {row[0]} : {row[1]} ({row[2]}%)")
        
        return "\n".join(lines)
    
    # ========================================================================
    # EXÉCUTION PRINCIPALE - CORRIGÉE
    # ========================================================================
    
    def execute(self, query: str) -> dict:
        """
        Exécute une requête SQL avec détection améliorée.
        🔥 MODIFIÉ : Ajoute 'stats_for_llm' au résultat avec result_kind correct.
        """
        try:
            cur = self.db.cursor()
            query_lower = query.lower()
            
            # ================================================================
            # 🔥 DÉTECTION DES QUESTIONS STATISTIQUES AGRÉGÉES
            # ================================================================
            
            # "total" + "incident" → vue d'ensemble
            if "total" in query_lower and "incident" in query_lower:
                result = self.get_total_count()
                if result.get("success") and result.get("data"):
                    result["stats_for_llm"] = self.format_stats_for_llm(result)
                return result
            
            # "distribution" ou "sévérité" → distribution des sévérités
            if "distribution" in query_lower or "sévérité" in query_lower or "severite" in query_lower:
                result = self.get_incidents_by_severity()
                if result.get("success") and result.get("data"):
                    result["stats_for_llm"] = self.format_stats_for_llm(result)
                return result
            
            # "répartition" ou "type de menace" → répartition par type
            if "répartition" in query_lower or "type de menace" in query_lower:
                result = self.get_total_incidents()
                if result.get("success") and result.get("data"):
                    result["stats_for_llm"] = self.format_stats_for_llm(result)
                return result
            
            # "le plus fréquent" / "menace la plus fréquente" → distribution complète
            if any(marker in query_lower for marker in (
                "plus fréquent", "plus fréquente", "plus fréquents",
                "plus fréquentes", "menace la plus fréquente",
                "type de menace est le plus"
            )):
                result = self.get_total_incidents()
                if result.get("success") and result.get("data"):
                    result["stats_for_llm"] = self.format_stats_for_llm(result)
                return result

            # "secteur" → incidents par secteur
            if "secteur" in query_lower:
                result = self.get_incidents_by_sector()
                if result.get("success") and result.get("data"):
                    result["stats_for_llm"] = self.format_stats_for_llm(result)
                return result
            
            # "source" → incidents par source
            if "source" in query_lower and "incident" in query_lower:
                result = self.get_incidents_by_source()
                if result.get("success") and result.get("data"):
                    result["stats_for_llm"] = self.format_stats_for_llm(result)
                return result
            
            # ================================================================
            # 🔥 DÉTECTION PRÉCISE DES TYPES DE MENACES
            # ================================================================
            
            # PIRATAGE
            if any(kw in query_lower for kw in ["piratage", "piratages"]):
                result = self.get_incidents_by_type("PIRATAGE")
                if result.get("success") and result.get("data"):
                    result["stats_for_llm"] = self.format_stats_for_llm(result)
                return result
            
            # RANSOMWARE
            elif "ransomware" in query_lower:
                result = self.get_incidents_by_type("RANSOMWARE")
                if result.get("success") and result.get("data"):
                    result["stats_for_llm"] = self.format_stats_for_llm(result)
                return result
            
            # PHISHING
            elif "phishing" in query_lower:
                result = self.get_incidents_by_type("PHISHING")
                if result.get("success") and result.get("data"):
                    result["stats_for_llm"] = self.format_stats_for_llm(result)
                return result
            
            # DDOS
            elif "ddos" in query_lower:
                result = self.get_incidents_by_type("DDOS")
                if result.get("success") and result.get("data"):
                    result["stats_for_llm"] = self.format_stats_for_llm(result)
                return result
            
            # VULNÉRABILITÉ
            elif any(kw in query_lower for kw in ["vulnérabilité", "vulnérabilités"]):
                result = self.get_incidents_by_type("VULNERABILITE")
                if result.get("success") and result.get("data"):
                    result["stats_for_llm"] = self.format_stats_for_llm(result)
                return result
            
            # CHEVAL_TROIE
            elif any(kw in query_lower for kw in ["cheval_troie", "cheval de troie"]):
                result = self.get_incidents_by_type("CHEVAL_TROIE")
                if result.get("success") and result.get("data"):
                    result["stats_for_llm"] = self.format_stats_for_llm(result)
                return result
            
            # SPYWARE
            elif "spyware" in query_lower:
                result = self.get_incidents_by_type("SPYWARE")
                if result.get("success") and result.get("data"):
                    result["stats_for_llm"] = self.format_stats_for_llm(result)
                return result
            
            # VIRUS
            elif "virus" in query_lower:
                result = self.get_incidents_by_type("VIRUS")
                if result.get("success") and result.get("data"):
                    result["stats_for_llm"] = self.format_stats_for_llm(result)
                return result
            
            # BLANCHIMENT
            elif "blanchiment" in query_lower:
                result = self.get_incidents_by_type("BLANCHIMENT")
                if result.get("success") and result.get("data"):
                    result["stats_for_llm"] = self.format_stats_for_llm(result)
                return result
            
            # ESCROQUERIE
            elif "escroquerie" in query_lower:
                result = self.get_incidents_by_type("ESCROQUERIE")
                if result.get("success") and result.get("data"):
                    result["stats_for_llm"] = self.format_stats_for_llm(result)
                return result
            
            # SPOOFING
            elif "spoofing" in query_lower:
                result = self.get_incidents_by_type("SPOOFING")
                if result.get("success") and result.get("data"):
                    result["stats_for_llm"] = self.format_stats_for_llm(result)
                return result
            
            # FUITE_DONNEES
            elif "fuite" in query_lower and "données" in query_lower:
                result = self.get_incidents_by_type("FUITE_DONNEES")
                if result.get("success") and result.get("data"):
                    result["stats_for_llm"] = self.format_stats_for_llm(result)
                return result
            
            # TOP / CLASSEMENT
            elif any(kw in query_lower for kw in ["top", "classement", "malware", "malwares"]):
                sql = """
                    SELECT type_menace, COUNT(*) as nb,
                           ROUND(AVG(CASE WHEN severite = 'CRITIQUE' THEN 1.0 ELSE 0.0 END) * 100, 1) as pct_critique
                    FROM cyber_incidents
                    WHERE type_menace != 'INCONNU'
                    GROUP BY type_menace
                    ORDER BY nb DESC
                    LIMIT 5
                """
                label = "Top 5 des menaces"
                result_kind = "threat_distribution"
            
            # SECTEURS
            elif any(kw in query_lower for kw in ["secteur", "secteurs"]) and "cibl" in query_lower:
                sql = """
                    SELECT secteur_cible, COUNT(*) as nb,
                           ROUND(AVG(CASE WHEN severite = 'CRITIQUE' THEN 1.0 ELSE 0.0 END) * 100, 1) as pct_critique
                    FROM cyber_incidents
                    WHERE secteur_cible != 'INCONNU'
                    GROUP BY secteur_cible
                    ORDER BY nb DESC
                    LIMIT 5
                """
                label = "Top 5 des secteurs ciblés"
                result_kind = "threat_distribution"
            
            # SÉVÉRITÉ
            elif "severite" in query_lower or "sévérité" in query_lower:
                sql = """
                    SELECT severite, COUNT(*) as nb
                    FROM cyber_incidents
                    WHERE severite != 'INCONNUE'
                    GROUP BY severite
                    ORDER BY 
                        CASE severite
                            WHEN 'CRITIQUE' THEN 1
                            WHEN 'ÉLEVÉE' THEN 2
                            WHEN 'MOYENNE' THEN 3
                            WHEN 'FAIBLE' THEN 4
                            ELSE 5
                        END
                """
                label = "Distribution des sévérités"
                result_kind = "severity"
            
            else:
                # Vue d'ensemble par défaut
                sql = """
                    SELECT 
                        COUNT(*) as total,
                        COUNT(CASE WHEN type_menace != 'INCONNU' THEN 1 END) as total_connus,
                        COUNT(CASE WHEN severite = 'CRITIQUE' THEN 1 END) as nb_critiques,
                        COUNT(CASE WHEN severite = 'ÉLEVÉE' THEN 1 END) as nb_eleves
                    FROM cyber_incidents
                """
                label = "Vue d'ensemble des incidents"
                result_kind = "overview"
            
            cur.execute(sql)
            results = cur.fetchall()
            cur.close()
            
            # 🔥 Construction du résultat avec result_kind correct
            result = {
                "success": True, 
                "data": results, 
                "label": label,
                "query": sql,
                "result_kind": result_kind
            }
            
            # Ajouter le format LLM
            if results:
                result["stats_for_llm"] = self.format_stats_for_llm(result)
            
            return result
            
        except Exception as e:
            return {"success": False, "error": str(e), "data": None}


# ============================================================================
# FORMATAGE DES RÉSULTATS SQL
# ============================================================================

def format_sql_results(result: dict, lang: str = "fr") -> str:
    """Formate les résultats SQL selon leur structure réelle.

    Les colonnes sont déterminées par ``result_kind`` afin d'éviter de
    deviner le sens d'une valeur comme 64.5 (pourcentage) ou 1008 (nombre).
    """
    if not result or not result.get("success"):
        return ""

    data = result.get("data") or []
    label = result.get("label", "")
    kind = result.get("result_kind", "")

    if not data:
        return ""

    lines = [f"**{label}** :"] if label else []

    for row in data:
        row = tuple(row) if not isinstance(row, (list, tuple)) else row

        if kind == "threat_distribution" and len(row) >= 3:
            type_menace, total, pourcentage = row[:3]
            lines.append(f"- {type_menace} : {total} ({pourcentage}%)")
            continue

        if kind == "threat_type" and len(row) >= 4:
            type_menace, total, critiques, pourcentage = row[:4]
            lines.append(
                f"- {type_menace} : {total} incidents "
                f"(dont {critiques} critiques ; {pourcentage}% du total connu)"
            )
            continue

        if kind == "overview" and len(row) >= 4:
            total, connus, critiques, eleves = row[:4]
            lines.extend([
                f"- Total : {total}",
                f"- Incidents avec type connu : {connus}",
                f"- Critiques : {critiques}",
                f"- Élevés : {eleves}",
            ])
            continue

        if kind == "severity" and len(row) >= 2:
            lines.append(f"- {row[0]} : {row[1]}")
            continue

        if len(row) == 1:
            lines.append(f"- {row[0]}")
        elif len(row) == 2:
            lines.append(f"- {row[0]} : {row[1]}")
        elif len(row) == 3:
            lines.append(f"- {row[0]} : {row[1]} ({row[2]}%)")
        else:
            lines.append("- " + ", ".join(str(x) for x in row))

    return "\n".join(lines)