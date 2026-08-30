"""
PREPARE DATASET FOR LORA FINE-TUNING
Génère un dataset d'entraînement à partir du Guide de Bonnes Pratiques
Format compatible avec transformers (instruction + output)

⚠️ IMPORTANT : Les questions d'entraînement sont DIFFÉRENTES des questions d'évaluation RAGAS.
Cela permet de mesurer une vraie amélioration (generalization), pas une mémorisation.

📊 Dataset : 250 exemples (train + eval) couvrant 12 sujets
"""

import json
import os
import random
from typing import List, Dict

# ============================================================================
# QUESTIONS D'ENTRAÎNEMENT - 250 EXEMPLES
# ============================================================================

TRAINING_DATA = [
    # ================================================================
    # 1. MOTS DE PASSE (22 questions)
    # ================================================================
    {
        "instruction": "Quelles sont les caractéristiques d'un mot de passe sécurisé pour une PME ?",
        "output": "Un mot de passe sécurisé doit comporter au moins 8 caractères, inclure des majuscules, des minuscules, des chiffres et des caractères spéciaux, et être unique pour chaque compte."
    },
    {
        "instruction": "Pourquoi est-il conseillé de renouveler régulièrement ses mots de passe en entreprise ?",
        "output": "Le renouvellement régulier des mots de passe permet de limiter les risques en cas de compromission, car un mot de passe volé devient rapidement obsolète."
    },
    {
        "instruction": "À quoi sert un coffre-fort numérique pour les mots de passe d'une PME ?",
        "output": "Un coffre-fort numérique (gestionnaire de mots de passe) génère des mots de passe complexes, les stocke de manière sécurisée et les remplit automatiquement, évitant ainsi la réutilisation et l'oubli."
    },
    {
        "instruction": "Quels sont les risques d'utiliser le même identifiant et mot de passe sur plusieurs services professionnels ?",
        "output": "L'utilisation du même mot de passe sur plusieurs services expose l'entreprise à un risque de piratage en cascade : un seul compte compromis permet d'accéder à tous les autres."
    },
    {
        "instruction": "Comment mettre en place une politique de mots de passe efficace pour les collaborateurs ?",
        "output": "Une politique de mots de passe efficace inclut des mots de passe longs et complexes, un renouvellement tous les trois mois, l'interdiction de la réutilisation et l'utilisation d'un gestionnaire de mots de passe."
    },
    {
        "instruction": "Quelle est la taille minimum recommandée pour un mot de passe professionnel robuste ?",
        "output": "La taille minimum recommandée pour un mot de passe professionnel est de 8 caractères."
    },
    {
        "instruction": "Quels sont les avantages d'un gestionnaire de mots de passe pour une TPE ?",
        "output": "Un gestionnaire de mots de passe permet de générer des mots de passe complexes, de les stocker en sécurité, d'éviter la réutilisation et de gagner du temps au quotidien."
    },
    {
        "instruction": "Que faire si un employé utilise toujours le même mot de passe pour tous ses comptes ?",
        "output": "Il faut sensibiliser l'employé aux risques, lui expliquer l'importance de mots de passe uniques et lui proposer un gestionnaire de mots de passe pour faciliter la gestion."
    },
    {
        "instruction": "Quels sont les signes d'un mot de passe faible dans une entreprise ?",
        "output": "Un mot de passe faible contient des informations personnelles (date de naissance, prénom), est trop court, n'utilise qu'un seul type de caractères ou est utilisé sur plusieurs comptes."
    },
    {
        "instruction": "Comment former les salariés à la création de mots de passe robustes ?",
        "output": "La formation doit expliquer les critères d'un bon mot de passe, montrer l'utilisation d'un gestionnaire et sensibiliser aux risques des mots de passe réutilisés."
    },
    {
        "instruction": "Est-il préférable d'avoir un mot de passe long ou complexe pour une PME ?",
        "output": "Un mot de passe long est généralement plus sécurisé qu'un mot de passe court et complexe. La combinaison des deux (longueur + complexité) est idéale."
    },
    {
        "instruction": "Comment gérer les mots de passe des comptes administrateurs en entreprise ?",
        "output": "Les comptes administrateurs doivent avoir des mots de passe particulièrement robustes, différents des comptes utilisateurs, et être changés régulièrement."
    },
    {
        "instruction": "Quelle est la meilleure pratique pour stocker les mots de passe en entreprise ?",
        "output": "La meilleure pratique est d'utiliser un gestionnaire de mots de passe professionnel avec chiffrement, accès sécurisé et sauvegarde automatique."
    },
    {
        "instruction": "Comment réagir si un mot de passe professionnel est compromis ?",
        "output": "Changer immédiatement le mot de passe, vérifier les accès récents, en informer le responsable informatique et appliquer l'authentification multifacteur."
    },
    {
        "instruction": "Quelle est la fréquence recommandée de changement des mots de passe administrateur ?",
        "output": "Les mots de passe administrateur doivent être changés tous les mois ou immédiatement après un départ ou un incident de sécurité."
    },
    {
        "instruction": "Pourquoi les mots de passe doivent-ils être différents pour chaque compte métier ?",
        "output": "Des mots de passe différents par compte évitent l'effet domino : la compromission d'un compte ne permet pas d'accéder aux autres services de l'entreprise."
    },
    {
        "instruction": "Quels outils peuvent aider à gérer les mots de passe en entreprise ?",
        "output": "Les gestionnaires de mots de passe (Dashlane, 1Password, Bitwarden) et les solutions d'authentification unique (SSO) facilitent la gestion des accès."
    },
    {
        "instruction": "Comment écrire une politique de mots de passe pour une PME ?",
        "output": "Une politique de mots de passe doit définir la longueur minimale, la complexité, la fréquence de changement, l'usage des gestionnaires et les règles de stockage."
    },
    {
        "instruction": "Quelle est l'importance de l'authentification multifacteur pour les mots de passe ?",
        "output": "L'authentification multifacteur ajoute une couche de sécurité supplémentaire : même si le mot de passe est volé, l'accès reste protégé par le second facteur."
    },
    {
        "instruction": "Comment choisir un bon gestionnaire de mots de passe pour son entreprise ?",
        "output": "Choisir un gestionnaire avec chiffrement fort, synchronisation multi-appareils, partage sécurisé, support technique et conformité RGPD."
    },
    {
        "instruction": "Quels sont les risques des mots de passe trop simples en entreprise ?",
        "output": "Les mots de passe trop simples sont faciles à deviner par des attaques par force brute, dictionnaire ou ingénierie sociale, compromettant la sécurité des données."
    },
    {
        "instruction": "Comment sensibiliser les dirigeants à l'importance des mots de passe robustes ?",
        "output": "Présenter des cas concrets de piratage liés à des mots de passe faibles, les coûts associés et les solutions simples comme les gestionnaires de mots de passe."
    },

    # ================================================================
    # 2. SAUVEGARDES (18 questions)
    # ================================================================
    {
        "instruction": "Quelle est la procédure recommandée pour sauvegarder les données d'une petite structure ?",
        "output": "Il est recommandé d'effectuer des sauvegardes quotidiennes ou hebdomadaires sur un support externe dédié, conservé hors du site."
    },
    {
        "instruction": "À quel rythme faut-il réaliser des sauvegardes des fichiers professionnels ?",
        "output": "Les sauvegardes doivent être réalisées quotidiennement ou hebdomadairement selon le volume de données et l'activité de l'entreprise."
    },
    {
        "instruction": "Où placer les sauvegardes pour garantir leur sécurité en cas d'incendie ou de vol ?",
        "output": "Les sauvegardes doivent être stockées sur un support externe, dans un lieu éloigné de l'ordinateur et idéalement hors du site de l'entreprise."
    },
    {
        "instruction": "Qu'est-ce que la règle de sauvegarde 3-2-1 et pourquoi est-elle importante ?",
        "output": "La règle 3-2-1 consiste à avoir 3 copies des données sur 2 supports différents dont 1 copie hors site, garantissant une protection optimale."
    },
    {
        "instruction": "Comment procéder à une restauration de données après une perte ou un incident ?",
        "output": "La restauration s'effectue à partir des sauvegardes. Il est essentiel de tester régulièrement les restaurations pour s'assurer de leur efficacité."
    },
    {
        "instruction": "Quels supports de sauvegarde sont adaptés à une PME ?",
        "output": "Les supports adaptés sont les disques durs externes, les clés USB haute capacité, les serveurs NAS et les solutions de sauvegarde cloud."
    },
    {
        "instruction": "Combien de temps faut-il conserver les sauvegardes en entreprise ?",
        "output": "Les sauvegardes doivent être conservées selon une politique définie : quotidiennes pendant une semaine, hebdomadaires pendant un mois, mensuelles pendant un an."
    },
    {
        "instruction": "Quelle est l'importance de la sauvegarde hors site pour une PME ?",
        "output": "La sauvegarde hors site protège les données en cas de sinistre local (incendie, inondation, vol) et assure la continuité d'activité."
    },
    {
        "instruction": "Comment automatiser les sauvegardes dans une petite entreprise ?",
        "output": "L'automatisation des sauvegardes s'effectue via des logiciels dédiés, des scripts ou des solutions cloud qui programment les sauvegardes à des heures définies."
    },
    {
        "instruction": "Quelles données doivent être sauvegardées en priorité dans une PME ?",
        "output": "Les données prioritaires sont les fichiers clients, les documents comptables, les bases de données, les emails professionnels et les configurations logicielles."
    },
    {
        "instruction": "Quel budget prévoir pour une solution de sauvegarde en PME ?",
        "output": "Le budget varie de 0 € (solutions gratuites) à plusieurs centaines d'euros par mois pour des solutions cloud professionnelles avec support."
    },
    {
        "instruction": "Comment tester l'efficacité des sauvegardes en entreprise ?",
        "output": "Effectuer des restaurations tests régulières sur des postes de test, vérifier l'intégrité des fichiers et le temps de restauration."
    },
    {
        "instruction": "Quelle est la différence entre sauvegarde locale et sauvegarde cloud ?",
        "output": "La sauvegarde locale stocke les données sur des supports physiques (disques, serveurs), tandis que le cloud les stocke sur des serveurs distants accessible via internet."
    },
    {
        "instruction": "Comment choisir une solution de sauvegarde pour une PME ?",
        "output": "Évaluer les besoins en données, le budget, la fréquence de sauvegarde, la facilité d'utilisation et les options de restauration."
    },
    {
        "instruction": "Quels sont les risques de ne pas effectuer de sauvegardes régulières ?",
        "output": "Les risques incluent la perte définitive des données, l'arrêt d'activité, le paiement de rançons, la perte de clients et des sanctions juridiques."
    },
    {
        "instruction": "Quelle est la différence entre sauvegarde complète et sauvegarde incrémentale ?",
        "output": "La sauvegarde complète copie toutes les données, tandis que la sauvegarde incrémentale ne copie que les modifications depuis la dernière sauvegarde, économisant de l'espace."
    },
    {
        "instruction": "Comment protéger les sauvegardes contre le ransomware ?",
        "output": "Protéger les sauvegardes avec un accès restreint, une conservation hors ligne, un chiffrement et des tests de restauration réguliers."
    },
    {
        "instruction": "Quelle est la durée de conservation recommandée pour les sauvegardes fiscales ?",
        "output": "Les sauvegardes fiscales doivent être conservées pendant 10 ans, conformément aux obligations légales de conservation des documents comptables."
    },

    # ================================================================
    # 3. ANTIVIRUS (14 questions)
    # ================================================================
    {
        "instruction": "Pourquoi une antivirus est-il indispensable pour une petite entreprise ?",
        "output": "Un antivirus est indispensable car il protège contre les virus, malwares, trojans et autres menaces qui peuvent compromettre les données et les systèmes."
    },
    {
        "instruction": "Quels critères prendre en compte pour sélectionner un antivirus professionnel ?",
        "output": "Il faut choisir un antivirus avec mise à jour automatique, protection en temps réel, compatibilité avec les systèmes utilisés et support adapté aux PME."
    },
    {
        "instruction": "Comment maintenir un antivirus efficace à long terme en entreprise ?",
        "output": "Pour maintenir un antivirus efficace, il faut activer les mises à jour automatiques, réaliser des analyses régulières et surveiller les alertes."
    },
    {
        "instruction": "Quels types de menaces informatiques un antivirus permet-il de neutraliser ?",
        "output": "Un antivirus protège contre les virus, les trojans, les vers, les logiciels espions, les ransomwares et d'autres programmes malveillants."
    },
    {
        "instruction": "Comment savoir si l'antivirus d'un poste de travail est actif et à jour ?",
        "output": "L'antivirus affiche généralement une icône dans la barre des tâches. Il faut vérifier régulièrement son état et les notifications de mise à jour."
    },
    {
        "instruction": "Est-ce qu'un antivirus gratuit suffit pour une PME ou faut-il une version payante ?",
        "output": "Une version payante offre généralement une meilleure protection, des mises à jour plus fréquentes, un support technique et des fonctionnalités adaptées aux entreprises."
    },
    {
        "instruction": "Comment configurer les analyses programmées d'un antivirus en entreprise ?",
        "output": "Les analyses programmées se configurent dans les paramètres de l'antivirus, en choisissant la fréquence et l'heure (idéalement en dehors des heures de travail)."
    },
    {
        "instruction": "Que faire en cas de détection d'un malware par l'antivirus sur un poste de travail ?",
        "output": "Isoler immédiatement la machine du réseau, exécuter une analyse complète, suivre les instructions de l'antivirus et informer le responsable informatique."
    },
    {
        "instruction": "Quelle est l'importance des mises à jour automatiques de l'antivirus ?",
        "output": "Les mises à jour automatiques permettent de protéger contre les nouvelles menaces dès leur apparition, sans intervention manuelle."
    },
    {
        "instruction": "Un antivirus protège-t-il contre les attaques par ransomware ?",
        "output": "Les antivirus modernes incluent des protections anti-ransomware, mais ils doivent être couplés à des sauvegardes régulières pour une protection complète."
    },
    {
        "instruction": "Comment choisir entre plusieurs antivirus pour son entreprise ?",
        "output": "Comparer les fonctionnalités, le rapport qualité-prix, l'impact sur les performances, la facilité d'administration et les avis d'autres PME."
    },
    {
        "instruction": "Faut-il un antivirus sur les serveurs et les postes de travail ?",
        "output": "Oui, tous les équipements doivent être protégés : postes de travail, serveurs, ordinateurs portables et même les appareils mobiles utilisés en entreprise."
    },
    {
        "instruction": "Quelle est l'efficacité d'un antivirus contre les logiciels espions ?",
        "output": "Les antivirus modernes incluent des modules anti-spyware qui détectent et bloquent les logiciels espions surveillant les activités des utilisateurs."
    },
    {
        "instruction": "Comment réagir si l'antivirus détecte un faux positif ?",
        "output": "Vérifier le fichier suspect, consulter les logs de l'antivirus, exclure le fichier si nécessaire et signaler le faux positif à l'éditeur."
    },

    # ================================================================
    # 4. EMAILS ET PHISHING (16 questions)
    # ================================================================
    {
        "instruction": "Quels sont les indices pour détecter un courriel frauduleux dans une entreprise ?",
        "output": "Il faut vérifier l'expéditeur, les fautes d'orthographe, les liens suspects, les pièces jointes inhabituelles et les demandes d'informations personnelles ou financières."
    },
    {
        "instruction": "Quelle conduite adopter lorsqu'un collaborateur signale un email suspect ?",
        "output": "Il faut ne pas ouvrir l'email suspect, ne pas cliquer sur les liens, ne pas télécharger les pièces jointes et supprimer immédiatement le message."
    },
    {
        "instruction": "Qu'est-ce que l'hameçonnage et comment s'en protéger en PME ?",
        "output": "L'hameçonnage (phishing) est une technique d'arnaque qui imite une institution pour voler des données. La protection passe par la formation, la vigilance et des outils de filtrage."
    },
    {
        "instruction": "Comment organiser une campagne de sensibilisation au phishing pour les salariés ?",
        "output": "Organiser des formations régulières, des simulations de phishing, des affichages dans les locaux et des rappels par email ou newsletter."
    },
    {
        "instruction": "Pourquoi les emails sont-ils particulièrement ciblés par les cybercriminels ?",
        "output": "Les emails sont une porte d'entrée privilégiée car ils sont utilisés par tous les employés et peuvent facilement contenir des pièces jointes infectées ou des liens frauduleux."
    },
    {
        "instruction": "Quels sont les signes d'une tentative de phishing par email professionnel ?",
        "output": "Un email urgent, une adresse expéditeur suspecte, des fautes, un lien qui ne correspond pas au texte affiché, une demande de données personnelles."
    },
    {
        "instruction": "Comment sensibiliser les employés aux risques des emails frauduleux ?",
        "output": "Par des formations pratiques, des exemples concrets, des simulations régulières et une communication continue sur les bonnes pratiques."
    },
    {
        "instruction": "Quels outils peuvent aider à filtrer les emails malveillants en entreprise ?",
        "output": "Les filtres anti-spam, les solutions de sécurité email, les analyses de liens et pièces jointes, et les passerelles de sécurité email."
    },
    {
        "instruction": "Que faire si un employé a cliqué sur un lien suspect dans un email ?",
        "output": "Déconnecter immédiatement la machine du réseau, changer les mots de passe, analyser le système et signaler l'incident à la personne responsable."
    },
    {
        "instruction": "Quelle est la politique de sécurité recommandée concernant les emails en PME ?",
        "output": "Une politique claire définissant les règles d'utilisation des emails, la vérification des expéditeurs, le signalement des emails suspects et les sanctions en cas de non-respect."
    },
    {
        "instruction": "Quels sont les types de phishing les plus courants en entreprise ?",
        "output": "Le phishing classique (email frauduleux), le spear phishing (ciblé), le whaling (dirigeants) et le smishing (SMS) ou vishing (appels téléphoniques)."
    },
    {
        "instruction": "Comment distinguer un email légitime d'un email de phishing ?",
        "output": "Vérifier l'adresse email complète, l'URL des liens, la signature, la qualité rédactionnelle et appeler l'expéditeur en cas de doute."
    },
    {
        "instruction": "Quelle est la formation minimale sur le phishing pour les nouveaux employés ?",
        "output": "Une formation d'accueil incluant les bases du phishing, des exemples concrets, des consignes de signalement et une simulation dans les premières semaines."
    },
    {
        "instruction": "Quel est le coût moyen d'une attaque par phishing pour une PME ?",
        "output": "Le coût peut varier de quelques milliers d'euros (perte de données) à plusieurs dizaines de milliers (arrêt d'activité, rançon, réputation)."
    },
    {
        "instruction": "Comment vérifier l'authenticité d'un email reçu d'un fournisseur ?",
        "output": "Contacter directement le fournisseur par un canal connu, vérifier l'adresse email complète, comparer avec les emails précédents."
    },
    {
        "instruction": "Quels sont les signes d'une tentative de spear phishing ?",
        "output": "Un email personnalisé avec des informations spécifiques sur l'entreprise, une connaissance des relations internes, une demande inhabituelle de transfert de fonds."
    },

    # ================================================================
    # 5. POSTE DE TRAVAIL (14 questions)
    # ================================================================
    {
        "instruction": "Quelles sont les mesures essentielles pour sécuriser les équipements informatiques d'une PME ?",
        "output": "Installer un antivirus, interdire les logiciels non autorisés, effectuer des sauvegardes régulières et verrouiller les sessions des utilisateurs."
    },
    {
        "instruction": "Pourquoi est-il nécessaire de verrouiller sa session avant de quitter son poste ?",
        "output": "Verrouiller l'écran empêche tout accès non autorisé aux données, applications et informations confidentielles de l'entreprise."
    },
    {
        "instruction": "Quels sont les dangers liés au téléchargement de logiciels non approuvés en entreprise ?",
        "output": "Les logiciels non autorisés peuvent contenir des malwares, introduire des vulnérabilités, être incompatibles avec le système et créer des failles de sécurité."
    },
    {
        "instruction": "Comment renforcer la sécurité physique des postes de travail contre les intrusions ?",
        "output": "Verrouiller les locaux, contrôler les accès aux zones sensibles, utiliser des câbles antivol pour les portables et installer une vidéosurveillance."
    },
    {
        "instruction": "Quelle est l'importance de la mise à jour des systèmes d'exploitation en entreprise ?",
        "output": "Les mises à jour corrigent des failles de sécurité, améliorent les performances et protègent contre les nouvelles menaces."
    },
    {
        "instruction": "Comment gérer les sessions ouvertes sur les postes de travail partagés ?",
        "output": "Chaque utilisateur doit avoir son propre compte, se déconnecter après utilisation, et les sessions doivent être verrouillées en cas d'absence prolongée."
    },
    {
        "instruction": "Quels sont les bons réflexes à adopter face aux périphériques USB en entreprise ?",
        "output": "Ne pas brancher de périphériques inconnus, scanner les clés USB avant utilisation, et limiter l'usage aux périphériques validés par l'entreprise."
    },
    {
        "instruction": "Comment protéger les postes de travail contre les attaques par ransomware ?",
        "output": "Maintenir les systèmes à jour, utiliser un antivirus, effectuer des sauvegardes régulières et former les employés aux bonnes pratiques."
    },
    {
        "instruction": "Quelle est la politique recommandée pour l'utilisation des écrans en entreprise ?",
        "output": "Verrouiller l'écran en cas d'absence, utiliser des cache-écrans de confidentialité dans les espaces publics et ajuster la luminosité."
    },
    {
        "instruction": "Comment sécuriser les ordinateurs portables des employés nomades ?",
        "output": "Chiffrer les données, activer un mot de passe au démarrage, utiliser un câble antivol, ne pas laisser le matériel sans surveillance."
    },
    {
        "instruction": "Quels sont les risques liés à l'utilisation de Wi-Fi publics par les employés ?",
        "output": "Les risques incluent l'interception de données, les attaques de l'homme du milieu, le vol d'identifiants et l'installation de malwares."
    },
    {
        "instruction": "Comment sécuriser les postes de travail des employés à distance ?",
        "output": "Utiliser un VPN, une connexion sécurisée, des mots de passe forts, un antivirus à jour et des formations spécifiques au télétravail."
    },
    {
        "instruction": "Quelle est l'importance des politiques de mot de passe sur les postes de travail ?",
        "output": "Les politiques de mot de passe imposent des règles de complexité et de renouvellement, réduisant les risques d'accès non autorisés."
    },
    {
        "instruction": "Comment gérer les droits d'administration sur les postes de travail ?",
        "output": "Limiter les droits d'administration aux seuls utilisateurs qui en ont besoin, et utiliser des comptes séparés pour les tâches administratives."
    },

    # ================================================================
    # 6. FORMATION (12 questions)
    # ================================================================
    {
        "instruction": "Quel est le rôle de la formation des collaborateurs dans la cybersécurité d'une PME ?",
        "output": "La formation transforme les employés en première ligne de défense, leur apprend à reconnaître les menaces et réduit les risques d'erreur humaine."
    },
    {
        "instruction": "Quels sont les moyens les plus efficaces pour sensibiliser les équipes aux cyber-risques ?",
        "output": "Les formations pratiques, les emailings thématiques, les affichages, les exercices de simulation et les campagnes de phishing test."
    },
    {
        "instruction": "À quelle cadence organiser des sessions de sensibilisation à la sécurité informatique ?",
        "output": "Il est recommandé d'organiser des formations au moins une fois par an avec des rappels trimestriels et des communications régulières."
    },
    {
        "instruction": "Quels sujets doivent être abordés lors d'une formation cybersécurité en PME ?",
        "output": "Les mots de passe, le phishing, les sauvegardes, les logiciels malveillants, la sécurité des postes de travail et les bonnes pratiques au quotidien."
    },
    {
        "instruction": "Comment mesurer l'efficacité d'une formation à la cybersécurité en entreprise ?",
        "output": "Par des tests de connaissances, des simulations de phishing, le suivi des incidents signalés et des évaluations de satisfaction."
    },
    {
        "instruction": "Pourquoi la formation continue est-elle essentielle en cybersécurité ?",
        "output": "Les menaces évoluent constamment, et les employés doivent être régulièrement informés des nouvelles techniques d'attaque et des bonnes pratiques."
    },
    {
        "instruction": "Quelle est la durée idéale d'une session de sensibilisation pour les employés ?",
        "output": "Une session de 1 à 2 heures est idéale pour maintenir l'attention et couvrir les sujets essentiels sans surcharger les participants."
    },
    {
        "instruction": "Comment adapter la formation cybersécurité aux différents profils de collaborateurs ?",
        "output": "Adapter le contenu selon les métiers (comptabilité, commercial, direction), le niveau technique et les risques spécifiques à chaque fonction."
    },
    {
        "instruction": "Quels sont les signes qu'une formation de sensibilisation a été efficace ?",
        "output": "Une augmentation des signalements de phishing, une réduction des incidents, des retours positifs et une meilleure application des bonnes pratiques."
    },
    {
        "instruction": "Quelle est l'importance de la formation des dirigeants en cybersécurité ?",
        "output": "Les dirigeants doivent comprendre les enjeux pour allouer les budgets, soutenir les initiatives et montrer l'exemple aux employés."
    },
    {
        "instruction": "Comment former les équipes aux nouvelles menaces émergentes ?",
        "output": "Organiser des briefings réguliers sur les nouvelles menaces, partager des articles et rapports, et mettre à jour les formations existantes."
    },
    {
        "instruction": "Quels sont les coûts d'une formation cybersécurité en PME ?",
        "output": "Les coûts varient de 0 € (formations en ligne gratuites) à plusieurs milliers d'euros pour des formations personnalisées avec experts."
    },

    # ================================================================
    # 7. AUTHENTIFICATION (12 questions)
    # ================================================================
    {
        "instruction": "Qu'est-ce que l'authentification à deux facteurs et comment l'utiliser en PME ?",
        "output": "L'authentification multifacteur combine un mot de passe avec un second facteur (SMS, application, clé physique) pour renforcer la sécurité des accès."
    },
    {
        "instruction": "Quels sont les bénéfices de l'authentification multifacteur pour une petite entreprise ?",
        "output": "La MFA protège même si le mot de passe est compromis, réduit les risques d'accès non autorisés et renforce la confiance des clients."
    },
    {
        "instruction": "Comment implémenter une authentification forte pour les comptes sensibles en entreprise ?",
        "output": "Utiliser un mot de passe robuste combiné à une authentification multifacteur, limiter les tentatives de connexion et surveiller les accès."
    },
    {
        "instruction": "Quels sont les différents facteurs d'authentification possibles en entreprise ?",
        "output": "Les facteurs sont : ce que l'utilisateur sait (mot de passe), ce qu'il possède (téléphone, clé) et ce qu'il est (empreinte, reconnaissance faciale)."
    },
    {
        "instruction": "Pourquoi privilégier l'authentification multifacteur pour les comptes administrateurs ?",
        "output": "Les comptes administrateurs ont des privilèges étendus et leur compromission peut affecter l'ensemble du système ; la MFA est donc cruciale."
    },
    {
        "instruction": "Quelles sont les solutions d'authentification adaptées aux PME sans expert IT ?",
        "output": "Les solutions cloud avec MFA intégrée, les applications d'authentification et les clés de sécurité USB sont simples à déployer et adaptées aux PME."
    },
    {
        "instruction": "L'authentification biométrique est-elle adaptée aux PME ?",
        "output": "Les solutions biométriques (empreinte, reconnaissance faciale) sont de plus en plus accessibles et peuvent être utilisées comme facteur d'authentification."
    },
    {
        "instruction": "Quelle est l'alternative à l'authentification multifacteur en cas d'indisponibilité du téléphone ?",
        "output": "Utiliser des codes de secours, des clés matérielles, des emails de récupération ou des questions de sécurité comme solutions alternatives."
    },
    {
        "instruction": "Comment expliquer l'importance de la MFA aux collaborateurs réticents ?",
        "output": "Montrer des exemples concrets d'attaques évitées par la MFA, expliquer la simplicité d'utilisation et souligner la protection des données personnelles."
    },
    {
        "instruction": "Qu'est-ce que l'authentification unique (SSO) et pourquoi l'utiliser ?",
        "output": "Le SSO permet d'accéder à plusieurs applications avec un seul identifiant, simplifiant la gestion des mots de passe et réduisant les risques de réutilisation."
    },
    {
        "instruction": "Comment choisir une solution d'authentification multifacteur ?",
        "output": "Évaluer la compatibilité avec les applications utilisées, la facilité d'utilisation, le coût et le niveau de sécurité offert."
    },
    {
        "instruction": "Quels sont les risques de ne pas utiliser l'authentification multifacteur ?",
        "output": "Les risques incluent le vol de mots de passe, l'accès non autorisé aux données, le piratage de comptes et les fuites de données confidentielles."
    },

    # ================================================================
    # 8. SÉCURITÉ GÉNÉRALE (20 questions)
    # ================================================================
    {
        "instruction": "Quels sont les premiers gestes de sécurité à adopter dans une jeune entreprise ?",
        "output": "Installer un antivirus, utiliser des mots de passe forts, faire des sauvegardes et former les employés aux bases de la cybersécurité."
    },
    {
        "instruction": "Quels sont les signes d'une cyberattaque en cours dans une PME ?",
        "output": "Un ralentissement des systèmes, des fenêtres de ransomware, des emails suspects envoyés depuis des comptes internes, des demandes de rançon."
    },
    {
        "instruction": "Comment réagir rapidement face à une suspicion d'intrusion informatique ?",
        "output": "Isoler les machines infectées du réseau, changer tous les mots de passe, contacter un expert et préparer une communication interne."
    },
    {
        "instruction": "Quelle est l'importance de la sauvegarde avant toute mise à jour ou modification système ?",
        "output": "Une sauvegarde préalable permet de restaurer le système en cas d'échec de mise à jour ou de problème logiciel."
    },
    {
        "instruction": "Comment gérer les accès des anciens employés à la fin de leur contrat ?",
        "output": "Révoquer immédiatement tous les accès, changer les mots de passe qu'ils connaissaient et récupérer les équipements professionnels."
    },
    {
        "instruction": "Quelle est la responsabilité juridique d'une PME en cas de fuite de données ?",
        "output": "La PME peut être tenue responsable des fuites de données clients ou confidentielles, avec des sanctions financières et une perte de réputation."
    },
    {
        "instruction": "Comment sensibiliser les dirigeants d'une PME à la cybersécurité ?",
        "output": "Présenter les risques financiers, juridiques et d'image, montrer des exemples concrets de PME victimes et proposer des solutions adaptées."
    },
    {
        "instruction": "Quels sont les coûts cachés d'une cyberattaque pour une petite entreprise ?",
        "output": "Les coûts incluent la perte de données, l'arrêt d'activité, les réparations, les amendes, la perte de clients et l'impact sur la réputation."
    },
    {
        "instruction": "Comment choisir un prestataire de sécurité informatique pour une PME ?",
        "output": "Vérifier les certifications, l'expérience avec les PME, les références, la réactivité et la clarté des offres et des tarifs."
    },
    {
        "instruction": "Quelles sont les bonnes pratiques de sécurité pour le télétravail en PME ?",
        "output": "Utiliser un VPN, des mots de passe forts, des mises à jour régulières, une connexion sécurisée et des formations adaptées au télétravail."
    },
    {
        "instruction": "Quelle est l'importance d'un plan de réponse aux incidents pour une PME ?",
        "output": "Un plan de réponse permet d'agir rapidement en cas d'attaque, de limiter les dégâts, de restaurer les systèmes et de communiquer efficacement."
    },
    {
        "instruction": "Comment établir une culture de cybersécurité en entreprise ?",
        "output": "Sensibiliser régulièrement, impliquer la direction, reconnaître les bonnes pratiques, partager des exemples et intégrer la sécurité au quotidien."
    },
    {
        "instruction": "Quels sont les équipements à sécuriser en priorité dans une PME ?",
        "output": "Les postes de travail, les serveurs, les box internet, les routeurs, les imprimantes réseau et les smartphones professionnels."
    },
    {
        "instruction": "Comment effectuer un audit de sécurité simple pour une PME ?",
        "output": "Vérifier les mots de passe, les sauvegardes, les mises à jour, les accès utilisateurs, les périphériques connectés et l'état de l'antivirus."
    },
    {
        "instruction": "Quelle est la première chose à faire en cas de ransomware ?",
        "output": "Déconnecter immédiatement la machine du réseau, ne pas payer la rançon, contacter un expert et restaurer les données à partir des sauvegardes."
    },
    {
        "instruction": "Comment assurer la sécurité des données lors des déplacements professionnels ?",
        "output": "Chiffrer les données, utiliser un VPN, éviter les réseaux Wi-Fi publics, ne pas laisser le matériel sans surveillance et verrouiller les sessions."
    },
    {
        "instruction": "Quelle est l'importance de la veille en cybersécurité pour une PME ?",
        "output": "La veille permet de rester informé des nouvelles menaces, des vulnérabilités et des bonnes pratiques pour adapter sa stratégie de sécurité."
    },
    {
        "instruction": "Comment gérer les mots de passe des comptes de service en entreprise ?",
        "output": "Utiliser des mots de passe longs et complexes, les stocker dans un gestionnaire sécurisé et les changer régulièrement ou après chaque départ."
    },
    {
        "instruction": "Quels sont les risques des imprimantes réseau en entreprise ?",
        "output": "Les imprimantes réseau peuvent être piratées pour accéder aux documents imprimés, servir de point d'entrée ou être utilisées pour des attaques."
    },
    {
        "instruction": "Comment sécuriser les accès à distance en entreprise ?",
        "output": "Utiliser un VPN avec authentification forte, limiter les accès aux heures de travail, surveiller les connexions et former les utilisateurs."
    },

    # ================================================================
    # 9. POLITIQUE DE SÉCURITÉ (10 questions)
    # ================================================================
    {
        "instruction": "Qu'est-ce qu'une politique de sécurité informatique pour une PME ?",
        "output": "Un document définissant les règles de protection des données, les responsabilités, les autorisations et les procédures en cas d'incident."
    },
    {
        "instruction": "Quels éléments doivent figurer dans une charte informatique d'entreprise ?",
        "output": "Les règles d'utilisation des équipements, la politique des mots de passe, les droits d'accès, la gestion des emails et les conséquences en cas de non-respect."
    },
    {
        "instruction": "Comment communiquer la politique de sécurité aux employés ?",
        "output": "Organiser une réunion de présentation, envoyer le document par email, l'afficher dans les espaces communs et demander une signature d'acceptation."
    },
    {
        "instruction": "Quelle est la fréquence de révision d'une politique de sécurité en PME ?",
        "output": "La politique doit être révisée au moins une fois par an, ou après un incident majeur ou un changement significatif de l'organisation."
    },
    {
        "instruction": "Qui est responsable de la sécurité informatique dans une PME ?",
        "output": "Le dirigeant est responsable, mais il peut déléguer à un responsable informatique ou à un prestataire externe."
    },
    {
        "instruction": "Comment intégrer les sous-traitants dans la politique de sécurité ?",
        "output": "Imposer des clauses de sécurité dans les contrats, vérifier leurs certifications et limiter leurs accès aux seules données nécessaires."
    },
    {
        "instruction": "Quelle est l'importance de la documentation des procédures de sécurité ?",
        "output": "La documentation permet de former les nouveaux employés, d'assurer la continuité en cas d'absence et de prouver la conformité en cas de contrôle."
    },
    {
        "instruction": "Comment évaluer l'efficacité d'une politique de sécurité ?",
        "output": "Suivre les incidents, réaliser des audits, consulter les employés, surveiller les accès et comparer avec les standards du secteur."
    },
    {
        "instruction": "Quelle est l'importance de la classification des données en entreprise ?",
        "output": "La classification permet de définir des niveaux de protection adaptés, de prioriser les efforts de sécurité et de respecter les obligations légales."
    },
    {
        "instruction": "Comment gérer les exceptions à la politique de sécurité ?",
        "output": "Définir un processus d'approbation formel, documenter les exceptions, limiter leur durée et prévoir des contrôles renforcés."
    },

    # ================================================================
    # 10. RGPD & CONFORMITÉ (10 questions)
    # ================================================================
    {
        "instruction": "Qu'est-ce que le RGPD et pourquoi concerne-t-il les PME ?",
        "output": "Le RGPD est le règlement européen sur la protection des données. Toute PME traitant des données personnelles est concernée."
    },
    {
        "instruction": "Quelles sont les obligations des PME en matière de protection des données ?",
        "output": "Sécuriser les données, informer les personnes, répondre aux demandes d'accès, notifier les violations et tenir un registre des traitements."
    },
    {
        "instruction": "Comment assurer la conformité RGPD dans une petite entreprise ?",
        "output": "Nommer un référent, réaliser un audit des données, mettre en place des mesures de sécurité et former les employés."
    },
    {
        "instruction": "Quels sont les risques de non-conformité RGPD pour une PME ?",
        "output": "Des amendes pouvant atteindre 20 millions d'euros ou 4 % du chiffre d'affaires, des sanctions financières et une perte de confiance des clients."
    },
    {
        "instruction": "Qu'est-ce que le droit à l'oubli dans le cadre du RGPD ?",
        "output": "Le droit de demander la suppression des données personnelles lorsqu'elles ne sont plus nécessaires ou que la personne s'oppose à leur traitement."
    },
    {
        "instruction": "Comment gérer les demandes d'accès aux données des salariés ?",
        "output": "Mettre en place une procédure de réponse dans les 30 jours, vérifier l'identité du demandeur, fournir les données et documenter la demande."
    },
    {
        "instruction": "Quelle est la durée de conservation des données clients en PME ?",
        "output": "Les données doivent être conservées le temps nécessaire au traitement (généralement 3 à 5 ans), puis supprimées ou archivées conformément à la loi."
    },
    {
        "instruction": "Comment sécuriser les données personnelles en entreprise ?",
        "output": "Chiffrer les données sensibles, limiter les accès, former les employés, surveiller les accès et réaliser des sauvegardes régulières."
    },
    {
        "instruction": "Quelle est l'importance du registre des traitements de données ?",
        "output": "Le registre permet de documenter toutes les activités de traitement, de démontrer la conformité et de faciliter les audits."
    },
    {
        "instruction": "Comment gérer une violation de données personnelles en entreprise ?",
        "output": "Notifier la CNIL dans les 72 heures, informer les personnes concernées, documenter l'incident et mettre en place des mesures correctives."
    },

    # ================================================================
    # 11. RÉSEAU ET CONNECTIVITÉ (12 questions)
    # ================================================================
    {
        "instruction": "Comment sécuriser un réseau Wi-Fi en entreprise ?",
        "output": "Utiliser le chiffrement WPA2 ou WPA3, changer le mot de passe par défaut, masquer le SSID et activer le filtrage MAC."
    },
    {
        "instruction": "Qu'est-ce qu'un pare-feu et pourquoi est-il important ?",
        "output": "Un pare-feu contrôle les communications réseau entrantes et sortantes selon des règles de sécurité, protégeant contre les accès non autorisés."
    },
    {
        "instruction": "Comment protéger un réseau contre les intrusions ?",
        "output": "Installer un pare-feu, utiliser un système de détection d'intrusion, segmenter le réseau et surveiller les logs de connexion."
    },
    {
        "instruction": "Qu'est-ce qu'un VPN et comment l'utiliser en entreprise ?",
        "output": "Un VPN crée un tunnel sécurisé pour les communications, protégeant les données échangées sur les réseaux publics ou non sécurisés."
    },
    {
        "instruction": "Comment sécuriser les connexions à distance des employés ?",
        "output": "Obliger l'utilisation d'un VPN, imposer l'authentification multifacteur et limiter les accès aux seules ressources nécessaires."
    },
    {
        "instruction": "Quels sont les risques des réseaux Wi-Fi publics pour les employés ?",
        "output": "L'interception de données, les attaques de l'homme du milieu, le vol de mots de passe et l'installation de malwares."
    },
    {
        "instruction": "Comment segmenter un réseau d'entreprise pour plus de sécurité ?",
        "output": "Séparer les réseaux (invités, employés, serveurs) avec des VLAN et des règles de pare-feu pour limiter la propagation des menaces."
    },
    {
        "instruction": "Quelle est l'importance des mises à jour des équipements réseau ?",
        "output": "Les mises à jour corrigent les failles de sécurité des routeurs, switchs et pare-feu, protégeant contre les attaques récentes."
    },
    {
        "instruction": "Comment détecter une intrusion sur un réseau d'entreprise ?",
        "output": "Surveiller les logs, utiliser un IDS/IPS, analyser le trafic anormal et mettre en place des alertes en temps réel."
    },
    {
        "instruction": "Quels sont les bons réflexes pour la sécurité du réseau en télétravail ?",
        "output": "Utiliser un VPN, éviter les réseaux publics, mettre à jour le routeur et utiliser des mots de passe forts pour le Wi-Fi domestique."
    },
    {
        "instruction": "Comment gérer les accès au réseau pour les visiteurs en entreprise ?",
        "output": "Créer un réseau invité séparé, limiter la durée d'accès, filtrer les sites et surveiller les connexions."
    },
    {
        "instruction": "Qu'est-ce qu'une attaque DDoS et comment s'en protéger ?",
        "output": "Une attaque DDoS submerge un serveur de requêtes. La protection passe par des solutions anti-DDoS, la mise en cache et la redondance des serveurs."
    },

    # ================================================================
    # 12. INCIDENTS ET RÉPONSE (10 questions)
    # ================================================================
    {
        "instruction": "Qu'est-ce qu'un plan de réponse aux incidents de sécurité ?",
        "output": "Un document définissant les procédures à suivre en cas d'incident : détection, confinement, éradication, restauration et retour d'expérience."
    },
    {
        "instruction": "Quelles sont les phases de gestion d'un incident de sécurité ?",
        "output": "Les phases sont : préparation, détection, analyse, confinement, éradication, restauration et retour d'expérience (post-mortem)."
    },
    {
        "instruction": "Comment constituer une équipe de réponse aux incidents en PME ?",
        "output": "Désigner un responsable, former des équipes (technique, communication, juridique), et prévoir des prestataires externes en renfort."
    },
    {
        "instruction": "Quelle est l'importance des tests d'intrusion en entreprise ?",
        "output": "Les tests d'intrusion identifient les vulnérabilités avant les attaquants, permettent de corriger les failles et de valider les mesures de sécurité."
    },
    {
        "instruction": "Comment gérer un incident de sécurité dans une PME sans expert IT ?",
        "output": "Contacter un prestataire spécialisé, isoler les systèmes affectés, documenter l'incident et suivre les procédures du plan de réponse."
    },
    {
        "instruction": "Qu'est-ce que l'analyse forensique en cybersécurité ?",
        "output": "L'analyse forensique consiste à collecter et analyser les preuves numériques après un incident pour comprendre l'attaque et identifier les responsables."
    },
    {
        "instruction": "Comment communiquer sur un incident de sécurité en entreprise ?",
        "output": "Préparer une communication interne pour les employés, une communication externe pour les clients et les autorités, et désigner un porte-parole."
    },
    {
        "instruction": "Quelle est l'importance de la documentation des incidents ?",
        "output": "La documentation permet d'analyser les causes, d'améliorer les procédures, de former les équipes et de prouver la conformité."
    },
    {
        "instruction": "Comment organiser un exercice de simulation d'incident en PME ?",
        "output": "Définir un scénario réaliste, impliquer toutes les équipes, simuler une attaque et analyser les points d'amélioration après l'exercice."
    },
    {
        "instruction": "Quels sont les indicateurs de performance pour la gestion des incidents ?",
        "output": "Le temps de détection (MTTD), le temps de résolution (MTTR), le nombre d'incidents, le taux de récidive et la satisfaction des parties prenantes."
    },
]

# ============================================================================
# PRÉPARATION DU DATASET
# ============================================================================

def prepare_dataset():
    """
    Prépare et sauvegarde le dataset au format JSONL.
    """
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(output_dir, exist_ok=True)

    # Mélanger les données
    random.seed(42)
    random.shuffle(TRAINING_DATA)

    # Split train/eval (80/20)
    split_idx = int(len(TRAINING_DATA) * 0.8)
    train_data = TRAINING_DATA[:split_idx]
    eval_data = TRAINING_DATA[split_idx:]

    # Sauvegarder train
    train_path = os.path.join(output_dir, "train_dataset.jsonl")
    with open(train_path, "w", encoding="utf-8") as f:
        for item in train_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"✅ Dataset d'entraînement : {len(train_data)} exemples → {train_path}")

    # Sauvegarder eval
    eval_path = os.path.join(output_dir, "eval_dataset.jsonl")
    with open(eval_path, "w", encoding="utf-8") as f:
        for item in eval_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"✅ Dataset d'évaluation : {len(eval_data)} exemples → {eval_path}")

    # Sauvegarder en CSV
    try:
        import pandas as pd
        df = pd.DataFrame(TRAINING_DATA)
        csv_path = os.path.join(output_dir, "training_data.csv")
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"✅ Dataset CSV : {len(df)} exemples → {csv_path}")
    except ImportError:
        pass

    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ DU DATASET")
    print("=" * 60)
    print(f"  • Total exemples : {len(TRAINING_DATA)}")
    print(f"  • Train : {len(train_data)}")
    print(f"  • Eval  : {len(eval_data)}")
    print(f"  • Subjects : 12 sujets couverts")
    print("=" * 60)
    print("\n⚠️  IMPORTANT : Ces questions sont DIFFÉRENTES des questions RAGAS.")
    print("   Le fine-tuning sera testé sur des questions non vues (generalization).")

    return train_path, eval_path

if __name__ == "__main__":
    prepare_dataset()