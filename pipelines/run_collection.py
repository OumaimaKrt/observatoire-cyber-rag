# pipelines/run_collection.py
# =============================================================================
# Pipeline complet - Execute tous les collecteurs
# =============================================================================
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DB_CONFIG
from utils.logger import get_logger

logger = get_logger("pipeline")

# Importer tous les collecteurs
from collectors.collect_nvd import NVDCollector
from collectors.collect_circl import CIRCLCollector
from collectors.collect_dgssi import DGSSICollector
from collectors.collect_rss import get_all_rss_collectors
from collectors.collect_otx import OTXCollector
from collectors.collect_exploitdb import ExploitDBCollector
from collectors.collect_bam import BAMCollector
from collectors.collect_urlhaus import URLhausCollector

# Collecteurs contexte sectoriel (sector_news)
from collectors.collect_anrt import ANRTCollector
from collectors.collect_hcp import HCPCollector
from collectors.collect_cndp import CNDPCollector
from collectors.collect_mtnra import MTNRACollector
from collectors.collect_challenge import ChallengeCollector
from collectors.collect_le360_tech import Le360Collector
from collectors.collect_leconomiste import LEconomisteCollector
from collectors.collect_medias24 import Medias24Collector
from collectors.collect_telquel import TelquelCollector
from collectors.collect_abuseipdb import AbuseIPDBCollector



def run_all_collectors():
    """Execute tous les collecteurs et affiche un rapport."""
    
    # Liste des collecteurs cyber_incidents
    collectors = [
        NVDCollector(DB_CONFIG),
        CIRCLCollector(DB_CONFIG),
        DGSSICollector(DB_CONFIG),
        OTXCollector(DB_CONFIG),
        ExploitDBCollector(DB_CONFIG),
        BAMCollector(DB_CONFIG),
        URLhausCollector(DB_CONFIG),
        AbuseIPDBCollector(DB_CONFIG)
    ]
    
    collectors.extend(get_all_rss_collectors(DB_CONFIG))
    
    # Collecteurs contexte sectoriel
    sector_collectors = [
        ANRTCollector(DB_CONFIG),
        HCPCollector(DB_CONFIG),
        CNDPCollector(DB_CONFIG),
        MTNRACollector(DB_CONFIG),
        ChallengeCollector(DB_CONFIG),
        Le360Collector(DB_CONFIG),
        LEconomisteCollector(DB_CONFIG),
        Medias24Collector(DB_CONFIG),
        TelquelCollector(DB_CONFIG),
    ]

    total_nouvelles = 0
    rapports = []
    sector_rapports = []

    # Executer les collecteurs cyber_incidents
    print("\n" + "=" * 60)
    print("  START COLLECTORS (cyber_incidents)")
    print("=" * 60)
    
    for collector in collectors:
        logger.info(f"=== Starting: {collector.source_name} ===")
        try:
            rapport = collector.run()
            rapports.append(rapport)
            total_nouvelles += rapport.get("nouvelles_inserees", 0)
            logger.info(f"OK {collector.source_name}: {rapport.get('nouvelles_inserees', 0)} new")
        except Exception as e:
            rapports.append({
                "source": collector.source_name,
                "statut": "ECHEC",
                "erreur": str(e),
            })
            logger.error(f"ERROR {collector.source_name}: {e}")

    # Executer les collecteurs sector_news
    print("\n" + "=" * 60)
    print("  START COLLECTORS (sector_news)")
    print("=" * 60)
    
    for collector in sector_collectors:
        logger.info(f"=== Starting: {collector.source_name} ===")
        try:
            if hasattr(collector, 'run'):
                rapport = collector.run()
            else:
                alertes = collector.collect()
                rapport = {"source": collector.source_name, "nouvelles_inserees": len(alertes) if alertes else 0}
            sector_rapports.append(rapport)
            logger.info(f"OK {collector.source_name}: {rapport.get('nouvelles_inserees', 0)} new")
        except Exception as e:
            sector_rapports.append({
                "source": collector.source_name,
                "statut": "ECHEC",
                "erreur": str(e),
            })
            logger.error(f"ERROR {collector.source_name}: {e}")

    # Rapport final
    print("\n" + "=" * 60)
    print("  REPORT")
    print("=" * 60)
    
    total_sector = sum(r.get('nouvelles_inserees', 0) for r in sector_rapports if r.get('statut') != "ECHEC")
    print(f"TOTAL cyber_incidents: {total_nouvelles}")
    print(f"TOTAL sector_news: {total_sector}")
    print(f"TOTAL GENERAL: {total_nouvelles + total_sector}")
    print("=" * 60)
    
    return True


# POINT D'ENTREE - TOUJOURS RENVOYER 0
if __name__ == "__main__":
    try:
        run_all_collectors()
        print("\nOK Pipeline completed")
        sys.exit(0)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(0)