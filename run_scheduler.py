# run_scheduler.py
# =============================================================================
# Scheduler - Exécute le pipeline de collecte à intervalles réguliers
# =============================================================================
import schedule
import subprocess
import time
import os
import sys
from datetime import datetime

PROJECT_PATH = os.path.dirname(os.path.abspath(__file__))
PYTHON_PATH = sys.executable 

# Fichiers de logs
LOG_FILE = os.path.join(PROJECT_PATH, "scheduler.log")

def log(msg):
    """Écrit un message dans le log avec timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} - {msg}\n")
    print(f"{timestamp} - {msg}")

def run_pipeline():
    """Exécute le pipeline de collecte complet."""
    log("DÉBUT de la collecte complète")
    
    try:
        # Exécuter run_collection.py
        result = subprocess.run(
            [PYTHON_PATH, os.path.join(PROJECT_PATH, "pipelines", "run_collection.py")],
            capture_output=True,
            text=True,
            timeout=3600,  
            cwd=PROJECT_PATH
        )
        
        if result.returncode == 0:
            log("Collecte terminée avec succès")
            # Afficher les dernières lignes de la sortie
            lines = result.stdout.strip().split('\n')
            if lines:
                log(f" {lines[-1]}")
        else:
            log(f"Collecte échouée (code {result.returncode})")
            if result.stderr:
                log(f"Erreur: {result.stderr[:200]}")
                
    except subprocess.TimeoutExpired:
        log("Collecte trop longue (>1h), arrêt")
    except Exception as e:
        log(f"Erreur inattendue: {e}")

def generate_stats():
    """Génère les statistiques après chaque collecte."""
    log("Génération des statistiques")
    try:
        result = subprocess.run(
            [PYTHON_PATH, os.path.join(PROJECT_PATH, "scripts", "generate_stats.py")],
            capture_output=True,
            text=True,
            timeout=120, 
            cwd=PROJECT_PATH
        )
        
        if result.returncode == 0:
            log("Statistiques générées")
            # Extraire le total des incidents
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if "Total incidents" in line:
                    log(f"  {line.strip()}")
                    break
        else:
            log(f" Statistiques: warning (non bloquant)")
            
    except Exception as e:
        log(f"Erreur stats (non bloquante): {e}")

def export_historique():
    """Exporte l'historique après chaque collecte."""
    log("Export de l'historique")
    try:
        result = subprocess.run(
            [PYTHON_PATH, os.path.join(PROJECT_PATH, "scripts", "export_historique.py")],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=PROJECT_PATH
        )
        
        if result.returncode == 0:
            log("Historique exporté")
        else:
            log(f"Export historique: warning")
            
    except Exception as e:
        log(f"Erreur export: {e}")

def verify_stats():
    """Vérifie la cohérence des statistiques."""
    log("Vérification de cohérence")
    try:
        result = subprocess.run(
            [PYTHON_PATH, os.path.join(PROJECT_PATH, "scripts", "verify_stats.py")],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=PROJECT_PATH
        )
        
        if result.returncode == 0:
            log("Vérification OK")
        else:
            log(f"Vérification: warning")
            
    except Exception as e:
        log(f"Erreur vérification: {e}")

# ─── PLANIFICATION ──────────────────────────────────────────────────────────

# EXÉCUTION IMMÉDIATE AU DÉMARRAGE
log("=" * 60)
log("SCHEDULER DÉMARRÉ AVEC EXÉCUTION IMMÉDIATE")
log(f"Projet: {PROJECT_PATH}")
log(f"Python: {PYTHON_PATH}")
log("Collecte toutes les 6 heures")
log("=" * 60)

# Exécution immédiate
log("EXÉCUTION IMMÉDIATE...")
run_pipeline()
log("GÉNÉRATION STATS IMMÉDIATE...")
generate_stats()
log("EXPORT HISTORIQUE IMMÉDIAT...")
export_historique()
log("VÉRIFICATION IMMÉDIATE...")
verify_stats()

# Planification toutes les 6 heures
schedule.every(6).hours.do(run_pipeline)
schedule.every(6).hours.at(":05").do(generate_stats)
schedule.every(6).hours.at(":10").do(export_historique)
schedule.every(6).hours.at(":15").do(verify_stats)

# Planification quotidienne supplémentaire
schedule.every().day.at("08:00").do(run_pipeline)
schedule.every().day.at("08:05").do(generate_stats)
schedule.every().day.at("08:10").do(export_historique)
schedule.every().day.at("08:15").do(verify_stats)

schedule.every().day.at("23:00").do(run_pipeline)
schedule.every().day.at("23:05").do(generate_stats)
schedule.every().day.at("23:10").do(export_historique)
schedule.every().day.at("23:15").do(verify_stats)

# ─── AFFICHAGE ──────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print(" SCHEDULER OBSERVATOIRE CYBER")
print("=" * 60)
print(f" Projet: {PROJECT_PATH}")
print(f"Python: {PYTHON_PATH}")
print(" Collecte immédiate en cours...")
print(" Collecte automatique toutes les 6 heures")
print(" Stats générées après chaque collecte")
print(" Historique exporté après chaque collecte")
print("  Vérification après chaque collecte")
print("  Logs dans: scheduler.log")
print("  Appuyez sur Ctrl+C pour arrêter")
print("=" * 60 + "\n")

# ─── BOUCLE PRINCIPALE ──────────────────────────────────────────────────────

try:
    while True:
        schedule.run_pending()
        time.sleep(60)  # Vérifier toutes les minutes
except KeyboardInterrupt:
    log("Scheduler arrêté par l'utilisateur")
    print("\nArrêté.")