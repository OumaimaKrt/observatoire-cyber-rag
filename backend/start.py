# start.py - Script de lancement corrigé
import os
import sys
import django

# Configurer Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'observatoire_cyber.settings')

# Initialiser Django
django.setup()

# Maintenant on peut importer les URLs
print("✅ Django initialisé")

from django.core.management import execute_from_command_line

if __name__ == "__main__":
    print("🚀 Lancement du serveur...")
    execute_from_command_line(['manage.py', 'runserver', '8000'])