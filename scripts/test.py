import sys
import os

# Ajouter la racine du projet
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from utils.classifiers import classifier_secteur_texte


tests = [
    "banking application vulnerability remote code execution",
    "hospital healthcare ransomware attack",
    "government website security breach",
    "telecom router vulnerability",
    "industrial control system malware",
]


for t in tests:
    secteur, confiance, mots = classifier_secteur_texte(t)

    print("=" * 60)
    print("Texte :", t)
    print("Secteur :", secteur)
    print("Confiance :", confiance)
    print("Mots :", mots)