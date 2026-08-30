# test_server.py
import os
import sys

# Ajouter le chemin
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Définir les settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'observatoire_cyber.settings')

# Tester l'import
try:
    from django.conf import settings
    print(f"✅ Settings chargés: DEBUG={settings.DEBUG}")
    print(f"✅ Database: {settings.DATABASES['default']['NAME']}")
except Exception as e:
    print(f"❌ Erreur: {e}")
    import traceback
    traceback.print_exc()