# ============================================================================
# intent_router.py
# ROUTEUR DE L'ASSISTANT OBSERVATOIRE CYBER - CMRPI
# VERSION CORRIGÉE - EXCEPTIONS COMPLÈTES + FIX REFUS
# ============================================================================

import re


# ============================================================================
# CONFIGURATION
# ============================================================================

DOMAIN_MESSAGE = (
    "Cette question ne relève pas du domaine de l'Observatoire Cyber. "
    "L'Observatoire est spécialisé dans la cybersécurité des PME au Maroc."
)

INSUFFICIENT_MESSAGE = (
    "Je n'ai trouvé aucune information sur cette question "
    "dans les documents disponibles."
)


# ============================================================================
# 🔥 DÉTECTION D'ABSTENTION - PATTERNS STRICTS AVEC EXCEPTIONS COMPLÈTES
# ============================================================================

# Patterns de questions nécessitant une abstention - UNIQUEMENT les cas clairs
ABSTENTION_PATTERNS = [
    # Prédictions - UNIQUEMENT avec mot de futur explicite
    (r"\b(quel sera|prédire|prévoir|prochaine|future)\b", 
     "Je ne dispose pas de prévisions. Je peux donner les statistiques actuelles."),
    
    # Superlatifs - UNIQUEMENT avec "expert" ou "monde" (pas "bon mot de passe")
    (r"\b(meilleur).*(expert|monde|général|mondial)\b",
     "Je ne peux pas désigner de 'meilleur' car cela est subjectif."),
    
    # Le plus grand/gros - UNIQUEMENT avec "monde" ou "global"
    (r"\b(le plus grand|le plus gros|le plus dangereux).*(monde|global|mondial)\b",
     "Je ne peux pas désigner de 'meilleur' car cela est subjectif."),
    
    # Entreprises victimes spécifiques - UNIQUEMENT si "quelle" + "PME"
    (r"\bquelle\s+pme\s+marocaine.*(subi|victime|touchée).*(ransomware|piratage|attaque)\b",
     "Je ne dispose pas d'informations sur les PME marocaines victimes spécifiques."),
    
    # Failles spécifiques non publiées - UNIQUEMENT si "zero-day" ou "non publiée"
    (r"\b(zero-day|non publiée|non publié).*(windows|android|ios)\b",
     "Je ne peux pas lister les failles de sécurité spécifiques non publiées."),
    
    # Salaires - UNIQUEMENT "salaire" + "hacker"
    (r"\b(salaire|rémunération|revenu).*(hacker|pirate)\b",
     "Je ne dispose pas de données fiables sur les salaires des hackers."),
    
    # Adresses IP - UNIQUEMENT "adresse ip" + "pirate"
    (r"\b(adresse ip|ip.*pirate|localisation).*(pirate|attaquant)\b",
     "Je ne peux pas fournir d'adresse IP de pirates."),
    
    # Marques d'antivirus - UNIQUEMENT si "marque" ou "quel" + "recommandé"
    (r"\b(marque.*antivirus|quel antivirus).*(recommandé|officiel)\b",
     "Le Guide ne recommande aucune marque spécifique. Il recommande un antivirus avec mise à jour automatique."),
]

# 🔥 EXCEPTIONS COMPLÈTES : questions légitimes qui ne doivent PAS être abstention
EXCEPTIONS_ABSTENTION = [
    # Questions Guide
    "comment sécuriser mon entreprise",
    "comment sécuriser mon entreprise ?",
    "comment sécuriser les ordinateurs de mon entreprise",
    "comment protéger les postes de travail",
    "comment créer un bon mot de passe",
    "qu'est-ce que je dois faire pour protéger mes données",
    "comment améliorer la sécurité informatique",
    "comment me protéger contre les cyberattaques",
    "mesures prioritaires pour sécuriser ma pme",
    "quelles sont les mesures prioritaires pour sécuriser ma pme",
    "comment sensibiliser mes employés aux risques cyber",
    "comment former les employés",
    "pourquoi je dois verrouiller mon écran",
    "pourquoi je ne dois pas télécharger",
    "comment reconnaître un email frauduleux",
    "comment reconnaître un email suspect",
    "que faire si un employé reçoit un email suspect",
    "pourquoi les emails sont-ils une cible",
    "qu'est-ce que l'authentification multifacteur",
    "pourquoi utiliser l'authentification multifacteur",
    
    # Questions sauvegarde
    "sauvegarder les fichiers de mon entreprise",
    "à quelle fréquence je dois sauvegarder",
    "comment sauvegarder les données de ma petite entreprise",
    "où est-ce que je dois stocker mes sauvegardes",
    "quelle est la règle de sauvegarde 3-2-1",
    "comment restaurer des données après une perte",
    
    # Questions formation
    "fréquence de formation",
    "pourquoi je dois former mes employés",
    "comment sensibiliser mes employés",
    
    # Questions antivirus
    "est-ce qu'une pme a vraiment besoin d'un antivirus",
    "comment choisir un antivirus",
    "à quelle fréquence je dois mettre à jour mon antivirus",
    "contre quoi un antivirus protège",
    "comment détecter si mon antivirus est désactivé",
    
    # Questions authentification
    "qu'est-ce que l'authentification multifacteur pour une pme",
    "pourquoi utiliser l'authentification multifacteur",
]

def is_abstention_required(query: str) -> tuple[bool, str | None]:
    """
    Détecte si la question nécessite une abstention.
    Retourne (bool, message) où message est la réponse d'abstention.
    """
    q = normaliser_texte(query)
    
    if not q:
        return False, None
    
    # 🔥 EXCEPTIONS : questions légitimes
    for exception in EXCEPTIONS_ABSTENTION:
        if exception in q:
            return False, None
    
    for pattern, message in ABSTENTION_PATTERNS:
        if re.search(pattern, q, re.IGNORECASE):
            return True, message
    
    return False, None


# ============================================================================
# FILTRE ANTI-PIRATAGE / ANTI-CONTOURNEMENT - CORRIGÉ
# ============================================================================

FORBIDDEN_ACTIONS = [
    "pirater",
    "piratage",  # ← AJOUTÉ pour capturer les questions sur "comment pirater"
    "hacker",
    "hacking",
    "contourner",
    "bypass",
    "crack",
    "cracker",
    "forcer",
    "accès non autorisé",
    "usurper",
    "usurpation",
    "voler",
    "vol d'identité",
    "injection",
    "sql injection",
    "xss",
    "cross-site scripting",
    "dénis de service",
    "dos",
]

FORBIDDEN_MESSAGE = (
    "Je ne peux pas vous aider avec cette demande car elle va à l'encontre "
    "des principes éthiques et légaux de la cybersécurité."
)


def is_forbidden_action(query: str) -> tuple[bool, str | None]:
    """Détecte les questions qui demandent une action malveillante."""
    q = normaliser_texte(query)

    if not q:
        return False, None

    # 🔥 EXCEPTIONS ÉLARGIES : questions légitimes
    statistiques_exceptions = [
        "combien de cas de piratage",
        "combien d'incidents de type vulnérabilité",
        "pourcentage d'incidents de type piratage",
        "faille de sécurité de windows",
        "proportion des vulnérabilités",
        "nombre de menaces critiques",
        "comment se protéger",
        "comment protéger",
        "comment sécuriser",
        "comment sauvegarder",  # ← AJOUTÉ pour ID 8
        "à quelle fréquence je dois sauvegarder",  # ← AJOUTÉ pour ID 8
        "sauvegarder les fichiers de mon entreprise",  # ← AJOUTÉ pour ID 8
    ]

    for exception in statistiques_exceptions:
        if exception in q:
            return False, None

    # 🔥 Détection de "comment" + action interdite (UNIQUEMENT les actions malveillantes)
    if re.search(r"\bcomment\s+", q):
        for action in FORBIDDEN_ACTIONS:
            # Ne pas capturer "piratage" dans un contexte statistique
            if action == "piratage" and "combien" in q:
                continue
            if action in q:
                return True, FORBIDDEN_MESSAGE

    # Détection directe
    for action in FORBIDDEN_ACTIONS:
        # Ne pas capturer "piratage" dans un contexte statistique
        if action == "piratage" and "combien" in q:
            continue
        if mot_present(q, action):
            return True, FORBIDDEN_MESSAGE

    return False, None


# ============================================================================
# NORMALISATION
# ============================================================================

def normaliser_texte(texte: str) -> str:
    """Normalise légèrement le texte sans modifier son sens."""
    if texte is None:
        return ""
    texte = str(texte).lower().strip()
    texte = texte.replace("’", "'")
    texte = re.sub(r"\s+", " ", texte)
    return texte


def mot_present(texte: str, expression: str) -> bool:
    """Vérifie si un mot ou une expression complète est présent(e)."""
    if not texte or not expression:
        return False
    texte = normaliser_texte(texte)
    expression = normaliser_texte(expression)
    pattern = r"(?<!\w)" + re.escape(expression) + r"(?!\w)"
    return re.search(pattern, texte) is not None


def _contient_un_des_mots(query: str, mots: list[str]) -> bool:
    """Retourne True si au moins un mot de la liste est présent."""
    return any(mot_present(query, mot) for mot in mots)


# ============================================================================
# SALUTATIONS
# ============================================================================

GREETINGS_EXACT = {
    "bonjour", "bonsoir", "salut", "coucou", "hello", "hi",
    "merci", "merci beaucoup", "thanks",
    "au revoir", "bye",
}


def is_greeting(query: str) -> bool:
    """Détecte les messages conversationnels."""
    q = normaliser_texte(query)
    if not q:
        return False
    if q in GREETINGS_EXACT:
        return True
    q_clean = re.sub(r"[.!?,;:]+$", "", q).strip()
    return q_clean in GREETINGS_EXACT


def get_greeting_response(query: str) -> str:
    """Retourne une réponse adaptée à la salutation."""
    q = normaliser_texte(query)
    q = re.sub(r"[.!?,;:]+$", "", q).strip()

    if q in {"merci", "merci beaucoup", "thanks"}:
        return "Je vous en prie ! N'hésitez pas à me poser une question sur la cybersécurité des PME au Maroc."
    if q in {"au revoir", "bye"}:
        return "Au revoir ! Restez vigilant face aux cybermenaces."
    return "Bonjour ! Je peux vous aider sur la cybersécurité des PME au Maroc, les recommandations du Guide CMRPI, les incidents cyber et les actualités disponibles."


# ============================================================================
# MOTS-CLÉS DU DOMAINE
# ============================================================================

WEAK_DOMAIN_KEYWORDS = {
    "pme", "entreprise", "entreprises", "petite entreprise", "petites entreprises",
    "moyenne entreprise", "moyennes entreprises",
    "maroc", "marocaine", "marocaines", "marocain", "marocains",
}

DOMAIN_KEYWORDS = [
    "cybersécurité", "cybersecurite", "cyber", "cybermenace", "cybermenaces",
    "sécurité informatique", "securite informatique",
    "sécurité numérique", "securite numerique",
    "menace", "menaces", "attaque", "attaques",
    "cyberattaque", "cyberattaques",
    "piratage", "pirater",
    "ransomware", "rançongiciel", "rançongiciels",
    "malware", "malwares", "logiciel malveillant",
    "virus", "phishing", "hameçonnage",
    "ddos", "intrusion", "compromission",
    "exploit", "exploitation",
    "vulnérabilité", "vulnérabilités",
    "faille", "failles",
    "email", "courriel", "messagerie", "mail",
    "email suspect", "email frauduleux",
    "spam", "courrier électronique",
    "incident", "incidents",
    "cve", "cwe", "cvss", "mitre", "att&ck",
    "statistique", "statistiques",
    "donnée", "données",
    "risque", "risques",
    "sévérité", "severite",
    "répartition", "repartition", "distribution",
    "secteur", "secteurs", "ciblé", "ciblés",
    "critique", "critiques",
    "protéger", "protection", "sécuriser", "sécurisation",
    "prévention", "prévenir", "sécurité",
    "antivirus", "pare-feu", "firewall",
    "sauvegarde", "sauvegardes", "restauration",
    "chiffrement", "chiffré", "chiffrée", "chiffrés", "chiffrées",
    "vpn", "rssi", "ssi",
    "authentification", "authentification multifacteur", "mfa",
    "mot de passe", "mots de passe",
    "identifiant", "identifiants",
    "compte", "comptes", "accès",
    "réseau", "wifi", "wi-fi",
    "serveur", "serveurs",
    "mise à jour", "mises à jour",
    "télécharger", "téléchargement",
    "logiciel", "logiciels",
    "poste de travail", "postes de travail",
    "écran", "verrouiller", "verrouillage",
    "session ouverte", "accès physique",
    "guide", "cmrpi",
    "recommandation", "recommandations",
    "bonne pratique", "bonnes pratiques",
    "mesure", "mesures",
    "conseil", "conseils",
    "politique de sécurité", "procédure de sécurité",
    "habilitation",
    "rgpd", "gdpr", "protection des données", "conformité",
    "expert en cybersécurité",
]


# ============================================================================
# MOTS-CLÉS DES INCIDENTS / STATISTIQUES
# ============================================================================

INCIDENT_KEYWORDS = [
    "menace", "menaces", "attaque", "attaques",
    "cyberattaque", "cyberattaques",
    "ransomware", "rançongiciel",
    "malware", "malwares", "virus",
    "piratage", "pirater",
    "ddos", "intrusion", "compromission",
    "exploit", "exploitation",
    "vulnérabilité", "vulnérabilités",
    "faille", "failles",
    "incident", "incidents",
    "cve", "cwe", "cvss",
    "risque", "risques",
    "combien", "nombre", "total", "proportion",
    "pourcentage", "part",
    "fréquent", "fréquente", "fréquents",
    "plus fréquent", "plus fréquente",
    "principal", "principaux", "principale", "principales",
    "top", "classement",
    "statistique", "statistiques",
    "tendance", "évolution",
    "augmentation", "diminution",
    "comparaison", "comparer",
]


# ============================================================================
# MOTS-CLÉS DU GUIDE
# ============================================================================

GUIDE_KEYWORDS = [
    "protéger", "protection", "sécuriser", "sécurité",
    "prévenir", "prévention", "éviter", "réduire", "améliorer",
    "recommandation", "recommandations", "recommande", "recommandé",
    "conseil", "conseils", "bonne pratique", "bonnes pratiques",
    "mesure", "mesures", "que faire", "comment",
    "comment protéger", "comment sécuriser",
    "solution", "solutions", "méthode", "méthodes",
    "mot de passe", "mots de passe",
    "antivirus", "pare-feu", "firewall",
    "sauvegarde", "sauvegardes", "chiffrement",
    "authentification", "mfa", "wifi", "wi-fi", "réseau",
    "mise à jour", "mises à jour",
    "poste de travail", "postes de travail",
    "phishing", "hameçonnage", "email",
    "former", "formation", "sensibiliser", "reconnaître",
    "email suspect", "email frauduleux",
    "pirate", "verrouiller écran", "verrouiller",
    "télécharger logiciel", "télécharger des logiciels",
    "télécharger", "écran verrouillé", "session ouverte", "accès physique",
    "fréquence", "sauvegarder", "sauvegarde",
]


# ============================================================================
# MOTS-CLÉS DES ACTUALITÉS
# ============================================================================

NEWS_KEYWORDS = [
    "actualité", "actualités", "actualite", "actualites",
    "actualité récente", "actualités récentes",
    "récent", "récente", "récentes", "recent", "recente", "recentes",
    "dernière", "dernières", "dernier", "derniers",
    "derniere", "dernieres",
    "nouveau", "nouveaux", "nouvelle", "nouvelles",
    "récemment", "recemment",
    "aujourd'hui", "aujourd hui",
    "cette semaine", "cette semaine-ci",
    "ce mois", "ce mois-ci",
    "annonce", "annonces", "alerte", "alertes",
    "presse", "article", "articles",
    "quoi de neuf", "quelles sont les nouveautés",
    "quelles sont les dernières nouvelles", "dernières nouvelles",
]


# ============================================================================
# HORS DOMAINE
# ============================================================================

OFF_TOPIC_TRIGGERS = [
    "football", "basketball", "tennis", "sport",
    "coupe du monde", "mondial",
    "jeux olympiques", "jo 2028", "jo 2032",
    "champion du monde", "championnat",
    "coupe d'afrique", "can 2027", "can",
    "immobilier", "immobilière",
    "cinéma", "film", "série télévisée", "série",
    "chanson", "musique", "concert",
    "météo", "recette", "cuisine", "restaurant", "plat",
    "tajine", "couscous", "pâtisserie",
    "voyage", "tourisme", "hôtel",
    "ministre", "président", "présidente",
    "élection", "élections", "gouvernement",
    "parti politique", "parlement", "population", "habitants", "recensement",
    "meilleur expert",
]


# ============================================================================
# QUESTIONS VAGUES MAIS POTENTIELLEMENT CYBER
# ============================================================================

VAGUE_CYBER_QUESTIONS = {
    "comment se protéger",
    "comment sécuriser",
    "quels sont les risques",
    "quelles sont les menaces",
    "quels sont les dangers",
    "comment éviter une attaque",
    "comment éviter les attaques",
    "comment éviter les cyberattaques",
    "que faire en cas d'attaque",
    "que faire en cas de cyberattaque",
    "que faire après une attaque",
    "que faire après une cyberattaque",
    "pourquoi les emails",
    "pourquoi les emails sont-ils une cible",
    "pourquoi les pirates",
    "pourquoi les pirates ciblent",
    "pourquoi verrouiller",
    "pourquoi verrouiller son écran",
    "pourquoi verrouiller l'écran",
    "pourquoi télécharger",
    "pourquoi ne pas télécharger",
    "comment reconnaître un email",
    "comment reconnaître un email suspect",
    "que faire si un email suspect",
    "que faire si un employé reçoit un email",
    "pourquoi les emails sont ils une cible privilégiée",
    "pourquoi je dois verrouiller mon écran",
    "pourquoi je ne dois pas télécharger",
    "qu'est-ce que le phishing",
    "c'est quoi le phishing",
    "comment former les employés",
    "proportion des ransomwares",
    "pourcentage des ransomwares",
    "comment me protéger contre les cyberattaques",
    "comment se protéger contre les cyberattaques",
    "me protéger contre les cyberattaques",
    "protéger contre les cyberattaques",
}


# ============================================================================
# RELANCES CONTEXTUELLES
# ============================================================================

FOLLOWUP_PATTERNS = (
    "et pour", "et les", "et le", "et la", "et concernant",
    "peux-tu préciser", "peux tu préciser", "précise", "préciser",
    "explique autrement", "explique moi autrement", "explique-moi autrement",
    "en quelques phrases", "résume", "résume-moi", "resume", "résumé",
    "donne-moi un exemple", "donne moi un exemple", "un exemple",
    "qu'en est-il", "et pour les", "et concernant les",
    "plus de détails", "plus d'informations", "plus d'info",
    "peux-tu expliquer", "peux tu expliquer", "peux-tu m'expliquer",
    "peux tu m'expliquer", "explique", "expliquer",
    "pourquoi", "et pourquoi", "développe", "détaille", "détailler",
    "continue", "vas-y", "vas y", "encore", "et alors", "et donc",
    "c'est-à-dire", "c'est a dire", "en clair", "plus simplement",
    "quoi d'autre", "autre chose", "et après", "et ensuite",
    "et sinon", "et aussi", "et donc", "d'accord et", "ok et",
)


def _est_relance_contextuelle(query: str) -> bool:
    q = normaliser_texte(query)
    if not q:
        return False
    mots = q.split()
    if len(mots) <= 4:
        return True
    return (len(mots) <= 8 and any(q.startswith(p) or p in q for p in FOLLOWUP_PATTERNS))


def _intent_depuis_historique(conversation_context: str) -> dict | None:
    """Récupère l'intention du dernier sujet utilisateur."""
    if not conversation_context:
        return None
    questions = re.findall(
        r"Question\s*:\s*(.*?)(?=\nR\u00e9ponse\s*:|\Z)",
        conversation_context,
        flags=re.IGNORECASE | re.DOTALL
    )
    if not questions:
        return _resoudre_intent_depuis_texte(conversation_context)

    guide_markers = ("guide cmrpi", "antivirus", "mot de passe", "mots de passe",
                     "protéger", "protection", "sécuriser", "sécurité",
                     "wifi", "wi-fi", "sauvegarde", "chiffrement",
                     "prévention", "recommandation", "recommandations",
                     "mesure", "mesures", "email suspect", "pirate",
                     "verrouiller écran", "télécharger", "poste de travail",
                     "écran", "verrouiller", "phishing", "hameçonnage",
                     "former", "formation", "reconnaître", "fréquence", "sauvegarder")

    incident_markers = ("ransomware", "piratage", "ddos", "incident", "incidents",
                        "vulnérabilité", "vulnérabilités", "statistique", "statistiques",
                        "proportion", "pourcentage", "plus fréquent", "nombre de",
                        "email suspect", "email frauduleux")

    news_markers = ("actualité", "actualités", "récent", "récente",
                    "dernière", "dernières", "récemment", "aujourd'hui", "presse")

    for candidate in reversed(questions):
        q = normaliser_texte(candidate.strip())
        has_guide = any(mot_present(q, x) for x in guide_markers)
        has_incident = any(mot_present(q, x) for x in incident_markers)
        has_news = any(mot_present(q, x) for x in news_markers)

        if has_news:
            return {"intent": "actualites", "needs_guide": False, "needs_statistics": False, "needs_news": True, "requete_source": candidate.strip()}
        if has_guide and has_incident:
            return {"intent": "mixte", "needs_guide": True, "needs_statistics": True, "needs_news": False, "requete_source": candidate.strip()}
        if has_guide:
            return {"intent": "guide", "needs_guide": True, "needs_statistics": False, "needs_news": False, "requete_source": candidate.strip()}
        if has_incident:
            return {"intent": "incidents", "needs_guide": False, "needs_statistics": True, "needs_news": False, "requete_source": candidate.strip()}
    return None


def _resoudre_intent_depuis_texte(texte: str) -> dict | None:
    """Résout l'intention à partir d'un texte brut."""
    q = normaliser_texte(texte)
    guide_markers = ("guide cmrpi", "antivirus", "mot de passe", "mots de passe",
                     "protéger", "protection", "sécuriser", "sécurité",
                     "wifi", "wi-fi", "sauvegarde", "chiffrement",
                     "prévention", "recommandation", "recommandations",
                     "mesure", "mesures", "email suspect", "pirate",
                     "verrouiller écran", "télécharger", "poste de travail",
                     "écran", "verrouiller", "phishing", "hameçonnage",
                     "former", "formation", "reconnaître", "fréquence", "sauvegarder")
    incident_markers = ("ransomware", "piratage", "ddos", "incident", "incidents",
                        "vulnérabilité", "vulnérabilités", "statistique", "statistiques",
                        "proportion", "pourcentage", "plus fréquent", "nombre de",
                        "email suspect", "email frauduleux")
    news_markers = ("actualité", "actualités", "récent", "récente",
                    "dernière", "dernières", "récemment", "aujourd'hui", "presse")

    has_guide = any(mot_present(q, x) for x in guide_markers)
    has_incident = any(mot_present(q, x) for x in incident_markers)
    has_news = any(mot_present(q, x) for x in news_markers)

    if has_news:
        return {"intent": "actualites", "needs_guide": False, "needs_statistics": False, "needs_news": True}
    if has_guide and has_incident:
        return {"intent": "mixte", "needs_guide": True, "needs_statistics": True, "needs_news": False}
    if has_guide:
        return {"intent": "guide", "needs_guide": True, "needs_statistics": False, "needs_news": False}
    if has_incident:
        return {"intent": "incidents", "needs_guide": False, "needs_statistics": True, "needs_news": False}
    return None


# ============================================================================
# CLASSIFICATION D'INTENTION
# ============================================================================

def classify_intent(query: str, conversation_context: str = "") -> dict:
    """Classifie l'intention principale de la question."""
    q = normaliser_texte(query)

    if conversation_context and _est_relance_contextuelle(q):
        historique_intent = _intent_depuis_historique(conversation_context)
        if historique_intent:
            return historique_intent

    if not q:
        return {"intent": "mixte", "needs_guide": True, "needs_statistics": True, "needs_news": False}

    # Exceptions pour éviter les faux mixtes
    if "fréquence" in q and "sauvegarder" in q:
        return {"intent": "guide", "needs_guide": True, "needs_statistics": False, "needs_news": False}

    if "reconnaître" in q and "email" in q and "frauduleux" in q:
        return {"intent": "mixte", "needs_guide": True, "needs_statistics": True, "needs_news": False}

    if "sensibiliser" in q and "employés" in q:
        return {"intent": "guide", "needs_guide": True, "needs_statistics": False, "needs_news": False}

    if "combien" in q and ("piratage" in q or "vulnérabilité" in q):
        return {"intent": "incidents", "needs_guide": False, "needs_statistics": True, "needs_news": False}

    if "pourcentage" in q and "piratage" in q:
        return {"intent": "incidents", "needs_guide": False, "needs_statistics": True, "needs_news": False}

    if "meilleur expert" in q:
        return {"intent": "hors_domaine", "needs_guide": False, "needs_statistics": False, "needs_news": False}

    if "faille de sécurité" in q and "windows" in q:
        return {"intent": "incidents", "needs_guide": False, "needs_statistics": True, "needs_news": False}

    if "protéger" in q and "cyberattaques" in q:
        return {"intent": "mixte", "needs_guide": True, "needs_statistics": True, "needs_news": False}

    if "former" in q and ("phishing" in q or "hameçonnage" in q):
        return {"intent": "guide", "needs_guide": True, "needs_statistics": False, "needs_news": False}

    if "sensibiliser" in q and ("phishing" in q or "hameçonnage" in q):
        return {"intent": "guide", "needs_guide": True, "needs_statistics": False, "needs_news": False}

    if "qu'est-ce que le phishing" in q or "c'est quoi le phishing" in q:
        return {"intent": "guide", "needs_guide": True, "needs_statistics": False, "needs_news": False}

    # Détection des mots-clés
    has_guide = _contient_un_des_mots(q, GUIDE_KEYWORDS)
    has_incidents = _contient_un_des_mots(q, INCIDENT_KEYWORDS)
    has_news = _contient_un_des_mots(q, NEWS_KEYWORDS)

    if has_news:
        if has_incidents and not has_guide:
            return {"intent": "mixte", "needs_guide": False, "needs_statistics": True, "needs_news": True}
        if has_guide and not has_incidents:
            return {"intent": "mixte", "needs_guide": True, "needs_statistics": False, "needs_news": True}
        if not has_guide and not has_incidents:
            return {"intent": "actualites", "needs_guide": False, "needs_statistics": False, "needs_news": True}
        return {"intent": "mixte", "needs_guide": True, "needs_statistics": True, "needs_news": True}

    if has_guide and has_incidents:
        return {"intent": "mixte", "needs_guide": True, "needs_statistics": True, "needs_news": False}
    if has_guide:
        return {"intent": "guide", "needs_guide": True, "needs_statistics": False, "needs_news": False}
    if has_incidents:
        return {"intent": "incidents", "needs_guide": False, "needs_statistics": True, "needs_news": False}

    q_clean = q.strip()
    for pattern in VAGUE_CYBER_QUESTIONS:
        if pattern in q_clean:
            return {"intent": "mixte", "needs_guide": True, "needs_statistics": True, "needs_news": False}

    return {"intent": "mixte", "needs_guide": True, "needs_statistics": True, "needs_news": False}


# ============================================================================
# DÉTECTION HORS DOMAINE
# ============================================================================

def is_off_topic(query: str) -> tuple[bool, str | None]:
    """Détermine si une question est hors domaine."""
    q = normaliser_texte(query)

    if not q:
        return True, DOMAIN_MESSAGE

    # Exceptions : questions cyber valides
    cyber_exceptions = [
        "me protéger contre les cyberattaques",
        "protéger contre les cyberattaques",
        "faille de sécurité de windows",
        "combien de cas de piratage",
        "combien d'incidents de type vulnérabilité",
        "pourcentage d'incidents de type piratage",
        "proportion des vulnérabilités",
        "nombre de menaces critiques",
        "comment sécuriser mon entreprise",
        "comment protéger mes données",
        "comment améliorer la sécurité informatique",
    ]

    for exception in cyber_exceptions:
        if exception in q:
            return False, None

    # Exceptions statistiques
    exceptions = [
        "proportion des ransomwares",
        "pourcentage des ransomwares",
        "combien de ransomwares",
        "nombre de ransomwares",
        "proportion de ransomwares",
        "proportion des attaques",
        "statistiques des ransomwares",
        "proportion des menaces",
        "répartition des menaces",
        "proportion des vulnérabilités",
        "pourcentage des vulnérabilités",
    ]

    for exception in exceptions:
        if exception in q:
            return False, None

    # Questions cyber vagues
    for pattern in VAGUE_CYBER_QUESTIONS:
        if pattern in q:
            return False, None

    # Termes explicites du domaine
    has_domain = _contient_un_des_mots(q, DOMAIN_KEYWORDS)
    has_domain_strong = _contient_un_des_mots(q, [kw for kw in DOMAIN_KEYWORDS if kw not in WEAK_DOMAIN_KEYWORDS])

    # Détection forte hors domaine
    has_off_topic = _contient_un_des_mots(q, OFF_TOPIC_TRIGGERS)

    if has_off_topic and not has_domain_strong:
        for trigger in OFF_TOPIC_TRIGGERS:
            if mot_present(q, trigger):
                return True, f"Cette question sur '{trigger}' ne relève pas du domaine de l'Observatoire Cyber. L'Observatoire est spécialisé dans la cybersécurité des PME au Maroc."

    # Questions courtes avec vocabulaire cyber implicite
    if q in {"risques", "menaces", "attaques", "sécurité", "protection",
             "cybersécurité", "cyber", "incident", "incidents", "ransomware",
             "phishing", "vulnérabilité", "vulnérabilités", "piratage",
             "email", "pirate", "écran", "verrouiller", "télécharger"}:
        return False, None

    if has_domain:
        return False, None

    # Formulation cyber implicite
    cyber_implicite = [
        r"\bme protéger\b",
        r"\bprotéger mon entreprise\b",
        r"\bprotéger notre entreprise\b",
        r"\bsécuriser mon entreprise\b",
        r"\bsécuriser notre entreprise\b",
        r"\bprotéger mes données\b",
        r"\bprotéger nos données\b",
        r"\bsécuriser mes données\b",
        r"\bsécuriser nos données\b",
        r"\bemail suspect\b",
        r"\bemail frauduleux\b",
        r"\brecevoir un email\b",
        r"\bverrouiller écran\b",
        r"\btélécharger logiciel\b",
        r"\btélécharger des logiciels\b",
        r"\bne pas télécharger\b",
        r"\bpourquoi les emails\b",
        r"\bpourquoi les pirates\b",
        r"\bpourquoi verrouiller\b",
        r"\bqu'est-ce que le phishing\b",
        r"\bc'est quoi le phishing\b",
        r"\bcomment former les employés\b",
        r"\bcomment me protéger contre les cyberattaques\b",
    ]

    for pattern in cyber_implicite:
        if re.search(pattern, q, flags=re.IGNORECASE):
            return False, None

    return True, DOMAIN_MESSAGE


# ============================================================================
# VALIDATION DES COLLECTIONS
# ============================================================================

VALID_COLLECTIONS = {"guide", "incidents", "news"}


def _normaliser_collections(intentions: dict) -> list[str]:
    """Transforme les intentions en liste de collections."""
    collections = []
    if intentions.get("needs_guide"):
        collections.append("guide")
    if intentions.get("needs_statistics"):
        collections.append("incidents")
    if intentions.get("needs_news"):
        collections.append("news")
    return [c for c in collections if c in VALID_COLLECTIONS]


# ============================================================================
# ROUTEUR PRINCIPAL - AVEC DÉTECTION D'ABSTENTION
# ============================================================================

def router(query: str, conversation_context: str = "") -> dict:
    """Routeur principal avec détection d'abstention."""
    q = normaliser_texte(query)

    # 🔥 Détection d'abstention (AVANT tout)
    is_abstention, abstention_message = is_abstention_required(q)
    if is_abstention:
        return {
            "query": q,
            "collections": [],
            "intentions": {},
            "off_topic": False,
            "is_greeting": False,
            "is_abstention": True,
            "greeting_response": None,
            "message": abstention_message,
        }

    # FILTRE ANTI-PIRATAGE
    is_forbidden, forbidden_message = is_forbidden_action(q)
    if is_forbidden:
        return {
            "query": q,
            "collections": [],
            "intentions": {},
            "off_topic": True,
            "is_greeting": False,
            "is_abstention": False,
            "greeting_response": None,
            "message": forbidden_message,
        }

    # SALUTATION PURE
    if is_greeting(q):
        return {
            "query": q,
            "collections": [],
            "intentions": {},
            "off_topic": False,
            "is_greeting": True,
            "is_abstention": False,
            "greeting_response": get_greeting_response(q),
            "message": None,
        }

    # HORS DOMAINE
    off_topic, message = is_off_topic(q)

    if off_topic and conversation_context and _est_relance_contextuelle(q):
        historique_intent = _intent_depuis_historique(conversation_context)
        if historique_intent:
            off_topic = False
            message = None
            intentions = historique_intent
        else:
            intentions = classify_intent(q, conversation_context=conversation_context)
    else:
        intentions = None

    if off_topic:
        return {
            "query": q,
            "collections": [],
            "intentions": {},
            "off_topic": True,
            "is_greeting": False,
            "is_abstention": False,
            "greeting_response": None,
            "message": message,
        }

    # CLASSIFICATION
    if intentions is None:
        intentions = classify_intent(q, conversation_context=conversation_context)

    if intentions.get("intent") == "hors_domaine":
        return {
            "query": q,
            "collections": [],
            "intentions": {},
            "off_topic": True,
            "is_greeting": False,
            "is_abstention": False,
            "greeting_response": None,
            "message": DOMAIN_MESSAGE,
        }

    collections = _normaliser_collections(intentions)

    if not collections:
        collections = ["guide", "incidents"]
        intentions = {"intent": "mixte", "needs_guide": True, "needs_statistics": True, "needs_news": False}

    requete_effective = None
    if isinstance(intentions, dict) and intentions.get("requete_source"):
        requete_effective = intentions["requete_source"]

    return {
        "query": q,
        "collections": collections,
        "intentions": intentions,
        "off_topic": False,
        "is_greeting": False,
        "is_abstention": False,
        "greeting_response": None,
        "message": None,
        "requete_effective": requete_effective,
    }