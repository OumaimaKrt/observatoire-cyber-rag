#!/usr/bin/env python
# run_debug.py - Script pour déboguer Django

import os
import sys
import traceback

# Ajouter le chemin
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configurer Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'observatoire_cyber.settings')

print("=" * 60)
print("🔍 DEBUG DJANGO")
print("=" * 60)

try:
    # Tester l'import des settings
    print("1. Import des settings...")
    from django.conf import settings
    print(f"   ✅ DEBUG: {settings.DEBUG}")
    print(f"   ✅ Database: {settings.DATABASES['default']['NAME']}")
    print(f"   ✅ Installed apps: {settings.INSTALLED_APPS}")
    
    # Tester l'import des vues
    print("\n2. Import des vues...")
    import api.views
    print("   ✅ api.views importé")
    
    # Tester les URLs
    print("\n3. Import des URLs...")
    import observatoire_cyber.urls
    print("   ✅ URLs importées")
    
    # Lancer le serveur
    print("\n4. Lancement du serveur...")
    from django.core.management import execute_from_command_line
    execute_from_command_line(['manage.py', 'runserver', '8000', '--noreload'])
    
except Exception as e:
    print(f"\n❌ ERREUR: {e}")
    print("\n" + "=" * 60)
    print("DÉTAIL DE L'ERREUR:")
    print("=" * 60)
    traceback.print_exc()