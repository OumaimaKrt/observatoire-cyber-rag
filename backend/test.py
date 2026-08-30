# test_complet.py
import requests
import json
import time
from datetime import datetime

API_URL = "http://localhost:8000/api/chat/"
HEADERS = {"Content-Type": "application/json"}

# ============================================================================
# TOUTES LES QUESTIONS DE TEST
# ============================================================================

TEST_QUERIES = [
    # ========================================================================
    # 1. 🇫🇷 Tests de base - Recommandations
    # ========================================================================
    {"query": "comment proteger ma petite entreprise ?", "categorie": "recommandations"},
    {"query": "comment sécuriser mon réseau wifi ?", "categorie": "recommandations"},
    {"query": "que faire en cas de ransomware ?", "categorie": "recommandations"},
    {"query": "comment choisir un bon antivirus ?", "categorie": "recommandations"},
    {"query": "quelles sont les bonnes pratiques pour les mots de passe ?", "categorie": "recommandations"},
    {"query": "comment protéger mes données sensibles ?", "categorie": "recommandations"},
    {"query": "qu'est-ce que l'authentification multi-facteurs ?", "categorie": "recommandations"},
    {"query": "comment former mes employés à la cybersécurité ?", "categorie": "recommandations"},
    {"query": "quelle est la procédure à suivre après une attaque ?", "categorie": "recommandations"},
    {"query": "comment faire pour sécuriser mon entreprise ?", "categorie": "recommandations"},
    {"query": "quelles mesures de sécurité pour le télétravail ?", "categorie": "recommandations"},
    {"query": "comment sécuriser mes serveurs ?", "categorie": "recommandations"},
    {"query": "comment protéger mes smartphones d'entreprise ?", "categorie": "recommandations"},
    
    # ========================================================================
    # 2. 📊 Tests de politiques et procédures
    # ========================================================================
    {"query": "comment définir une politique de sécurité ?", "categorie": "politiques"},
    {"query": "quelle politique de sauvegarde adopter ?", "categorie": "politiques"},
    {"query": "comment gérer les accès utilisateurs ?", "categorie": "politiques"},
    {"query": "que dois-je faire pour me conformer au RGPD ?", "categorie": "politiques"},
    {"query": "quelle politique de sécurité adopter pour ma PME ?", "categorie": "politiques"},
    {"query": "comment mettre en place une politique de mot de passe ?", "categorie": "politiques"},
    {"query": "politique de sauvegarde pour les PME", "categorie": "politiques"},
    
    # ========================================================================
    # 3. 📈 Tests statistiques et incidents
    # ========================================================================
    {"query": "quels sont les types de menaces les plus fréquents ?", "categorie": "statistiques"},
    {"query": "quelle est la menace la plus dangereuse pour les PME ?", "categorie": "statistiques"},
    {"query": "combien d'attaques ransomware ont été recensées ?", "categorie": "statistiques"},
    {"query": "quel est le nombre d'attaques et comment s'en protéger ?", "categorie": "statistiques"},
    {"query": "quels secteurs sont les plus touchés par les cyberattaques ?", "categorie": "statistiques"},
    {"query": "quelle est l'évolution des attaques phishing ?", "categorie": "statistiques"},
    {"query": "le secteur bancaire est-il bien protégé ?", "categorie": "statistiques"},
    {"query": "les PME marocaines sont-elles bien préparées ?", "categorie": "statistiques"},
    
    # ========================================================================
    # 4. 🌍 Tests en anglais
    # ========================================================================
    {"query": "how to protect my small business from cyber attacks ?", "categorie": "anglais"},
    {"query": "what is the best practice for password security ?", "categorie": "anglais"},
    {"query": "how to secure remote work for employees ?", "categorie": "anglais"},
    {"query": "how to respond to a ransomware attack ?", "categorie": "anglais"},
    {"query": "what are the most common cyber threats for SMEs ?", "categorie": "anglais"},
    {"query": "how to secure my company network ?", "categorie": "anglais"},
    {"query": "what is the procedure after a cyber attack ?", "categorie": "anglais"},
    
    # ========================================================================
    # 5. ❌ Tests hors domaine
    # ========================================================================
    {"query": "quel est le meilleur restaurant à Casablanca ?", "categorie": "hors_domaine"},
    {"query": "qui a gagné le dernier match de foot ?", "categorie": "hors_domaine"},
    {"query": "comment faire un bon tajine ?", "categorie": "hors_domaine"},
    {"query": "quelle est la météo de demain ?", "categorie": "hors_domaine"},
    {"query": "comment changer une roue de voiture ?", "categorie": "hors_domaine"},
    {"query": "qui est le président du Maroc ?", "categorie": "hors_domaine"},
    {"query": "comment faire un gâteau au chocolat ?", "categorie": "hors_domaine"},
    
    # ========================================================================
    # 6. 📰 Tests d'actualités
    # ========================================================================
    {"query": "quelles sont les dernières actualités sur la cybersécurité ?", "categorie": "actualites"},
    {"query": "y a-t-il eu des attaques récentes au Maroc ?", "categorie": "actualites"},
    {"query": "quelles sont les nouvelles menaces détectées ?", "categorie": "actualites"},
    {"query": "des nouvelles de la cybersécurité cette semaine ?", "categorie": "actualites"},
    
    # ========================================================================
    # 7. 🔀 Tests mixtes
    # ========================================================================
    {"query": "actualités et statistiques sur les ransomware", "categorie": "mixte"},
    {"query": "comment se protéger et quelles sont les tendances actuelles ?", "categorie": "mixte"},
    {"query": "le phishing est-il en augmentation et comment l'éviter ?", "categorie": "mixte"},
    {"query": "quelles sont les menaces et comment s'en prémunir ?", "categorie": "mixte"},
]

# ============================================================================
# FONCTIONS DE TEST
# ============================================================================

def test_query(query_data):
    """Teste une requête et affiche le résultat."""
    query = query_data["query"]
    categorie = query_data.get("categorie", "non classé")
    
    print("\n" + "=" * 80)
    print(f"📝 [{categorie.upper()}] {query}")
    print("=" * 80)
    
    try:
        start = time.time()
        response = requests.post(
            API_URL,
            json={"query": query},
            headers=HEADERS,
            timeout=60
        )
        elapsed = time.time() - start
        
        if response.status_code == 200:
            result = response.json()
            answer = result.get("answer", "")
            sources = result.get("sources", [])
            
            print(f"✅ {len(answer)} caractères - {elapsed:.2f}s")
            print("-" * 80)
            
            # Tronquer l'affichage si trop long
            if len(answer) > 600:
                print(answer[:600] + "...\n[TRONQUÉ]")
            else:
                print(answer)
            
            print("-" * 80)
            
            if sources:
                print(f"📚 Sources: {', '.join(sources[:5])}")
            else:
                print("📚 Sources: Aucune")
            
            print("=" * 80)
            return True
            
        else:
            print(f"❌ Erreur HTTP {response.status_code}")
            print(response.text)
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Timeout (60s)")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ Connexion refusée - Serveur non accessible")
        return False
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

# ============================================================================
# EXÉCUTION
# ============================================================================

def main():
    """Exécute tous les tests."""
    print("🚀 DÉMARRAGE DES TESTS RAG")
    print("=" * 80)
    print(f"📊 {len(TEST_QUERIES)} requêtes à tester")
    print(f"⏰ Début: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 80)
    
    # Vérifier que le serveur est accessible
    try:
        requests.get("http://localhost:8000/admin/", timeout=2)
        print("✅ Serveur accessible")
    except:
        print("❌ Serveur non accessible! Assurez-vous que Django est lancé.")
        print("   python manage.py runserver")
        return
    
    # Statistiques
    stats = {
        "total": len(TEST_QUERIES),
        "success": 0,
        "fail": 0,
        "par_categorie": {}
    }
    
    # Exécuter les tests
    for query_data in TEST_QUERIES:
        categorie = query_data.get("categorie", "non classé")
        if categorie not in stats["par_categorie"]:
            stats["par_categorie"][categorie] = {"success": 0, "fail": 0}
        
        if test_query(query_data):
            stats["success"] += 1
            stats["par_categorie"][categorie]["success"] += 1
        else:
            stats["fail"] += 1
            stats["par_categorie"][categorie]["fail"] += 1
        
        time.sleep(0.5)  # Pause entre les requêtes
    
    # Résumé
    print("\n" + "=" * 80)
    print("📊 RÉSUMÉ DES TESTS")
    print("=" * 80)
    print(f"✅ Réussis: {stats['success']}")
    print(f"❌ Échecs: {stats['fail']}")
    print(f"📊 Total: {stats['total']}")
    print(f"🎯 Taux de réussite: {stats['success']/stats['total']*100:.1f}%")
    print("-" * 80)
    print("📈 Par catégorie:")
    for categorie, resultats in stats["par_categorie"].items():
        total_cat = resultats["success"] + resultats["fail"]
        taux = resultats["success"]/total_cat*100 if total_cat > 0 else 0
        print(f"  • {categorie}: {resultats['success']}/{total_cat} ({taux:.0f}%)")
    print("=" * 80)
    print(f"⏰ Fin: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 80)

if __name__ == "__main__":
    main()