# ============================================================================
# response_builder.py
# VERSION OPTIMISÉE - AVEC SUPPORT ABSTENTION + STATS
# ============================================================================

import re
import hashlib


# ============================================================================
# DÉDUPLICATION
# ============================================================================

def deduplicate_documents(documents: list) -> list:
    """Supprime les documents identiques ou quasi identiques."""

    seen = set()
    unique_docs = []

    for doc in documents:
        if not isinstance(doc, dict):
            continue

        text = doc.get("texte", "") or ""

        text_hash = hashlib.sha256(
            text[:300].encode("utf-8", errors="ignore")
        ).hexdigest()

        if text_hash not in seen:
            seen.add(text_hash)
            unique_docs.append(doc)

    return unique_docs


# ============================================================================
# CORRECTION ORTHOGRAPHIQUE
# ============================================================================

def corriger_orthographe(texte: str) -> str:
    """Corrige quelques erreurs fréquentes dans les textes extraits."""

    if not texte:
        return texte

    corrections = {
        r'\beentreprise\b': 'entreprise',
        r'\béégalement\b': 'égalément',
        r'\bmrocines\b': 'marocaines',
        r'\bfire fce\b': 'faire face',
        r'\bcyberntiques\b': 'cybernétiques',
        r'\bprtique\b': 'pratique',
        r'\bcomptitiit\b': 'compétitivité',
        r'\bcroissnce\b': 'croissance',
        r'\bresponsbilit\b': 'responsabilité',
        r'\bcybercriminlit\b': 'cybercriminalité',
        r'\bmleillnces\b': 'malveillances',
        r'\bisnt\b': 'visant',
        r'\beûet\b': 'effet',
        r'\binnonts\b': 'innovants',
        r'\btrnsformtion\b': 'transformation',
        r'\bresponsble\b': 'responsable',
        r'\bcpcit\b': 'capacité',
        r'\bconsere\b': 'conserver',
        r'\btendre\b': 'étendre',
        r'\bmrch\b': 'marché',
        r'\btude\b': 'étude',
        r'\btablissit\b': 'établissait',
        r'\binnotion\b': 'innovation',
        r'\bcrucile\b': 'cruciale',
        r'\bstoppent\b': 'stoppent',
        r'\bproets\b': 'projets',
        r'\bcuse\b': 'cause',
        r'\bimportnt\b': 'important',
        r'\bhuts\b': 'hauts',
        r'\bdirients\b': 'dirigeants',
        r'\bctiits\b': 'activités',
        r'\beiller\b': 'veiller',
        r'\bprticiption\b': 'participation',
        r'\bdprt\b': 'départ',
        r'\bmce\b': 'même',
        r'\bnsure\b': 'assurer',
        r'\bte\b': 'été',
        r'\bscurit\b': 'sécurité',
        r'\bsystme\b': 'système',
        r'\bdonées\b': 'données',
        r'\bproccupations\b': 'préoccupations',
        r'\bessentcial\b': 'essentiel',
        r'\bntreprise\b': 'entreprise',
        r'\bffaut\b': 'Il faut',
        r'\bgalement\b': 'également',
        r'\bsse\b': 'vaste',
        r'\bcoffteuses\b': 'coûteuses',
        r'\bmettre en ure\b': 'mettre en œuvre',
        r'\bppliquer\b': 'appliquer',
        r'\bextraterritorialité\b': 'sécurité',
        r'\buridiques\b': 'juridiques',
        r'\bthmtique\b': 'thématique',
        r'\bprsenttion\b': 'présentation',
        r'\bassocition\b': 'association',
        r'\butilisteurs\b': 'utilisateurs',
        r'\binstititionnels\b': 'institutionnels',
        r'\btchnologies\b': 'technologies',
        r'\bnumriques\b': 'numériques',
        r'\binformtiques\b': 'informatiques',
        r'\bconnaissnce\b': 'connaissance',
        r'\bexperince\b': 'expérience',
        r'\boprationnels\b': 'opérationnels',
        r'\bsensibilistion\b': 'sensibilisation',
        r'\bproblmtique\b': 'problématique',
        r'\bperspectie\b': 'perspective',
        r'\bweborphie\b': 'bibliographie',
        r'\binterntionux\b': 'internationaux',
        r'\bcertinement\b': 'certainement',
        r'\bucun\b': 'aucun',
        r'\brfrence\b': 'référence',
        r'\bdomine\b': 'domaine',
        r'\bausi\b': 'aussi',
        r'\bs\'exercercer\b': "s'exercer",
        r'\bs\'exer\b': "s'exercer",
        r'\bconfidentieles\b': 'confidentielles',
        r'\bfourniseurs\b': 'fournisseurs',
        r'\bcaractre\b': 'caractère',
        r'\bproprit\b': 'propriété',
    }

    for pattern, replacement in corrections.items():
        texte = re.sub(pattern, replacement, texte, flags=re.IGNORECASE)

    return texte


# ============================================================================
# NETTOYAGE DES ARTEFACTS
# ============================================================================

def nettoyer_artefacts_avance(texte: str) -> str:
    """Nettoie les artefacts du texte."""

    if not texte:
        return texte

    texte = str(texte)

    _PATTERNS_AUTO_COMMENTAIRE = [
        r"[^.!?]*\bje n['’]ai (pas )?invent[ée]?\b[^.!?]*[.!?]",
        r"[^.!?]*\btoutes? mes informations proviennent (directement )?du contexte\b[^.!?]*[.!?]",
        r"[^.!?]*\bla r[ée]ponse est naturelle et adapt[ée]e\b[^.!?]*[.!?]",
        r"[^.!?]*\bsans ajouter d['’]informations non demand[ée]es\b[^.!?]*[.!?]",
        r"[^.!?]*\bqui r[ée]pond [àa] la question pos[ée]e par l['’]utilisateur\b[^.!?]*[.!?]",
        r"[^.!?]*\bje n['’]ai pas r[ée]p[ée]t[ée] la question\b[^.!?]*[.!?]",
        r"[^.!?]*\bje n'ai fait (aucune|que des?)?\s*généralisation\b[^.!?]*[.!?]",
        r"[^.!?]*\btoutes mes affirmations sont (directement )?soutenues\b[^.!?]*[.!?]",
        r"[^.!?]*\bje ne (généralise|cite) pas\b[^.!?]*[.!?]",
    ]

    for pattern in _PATTERNS_AUTO_COMMENTAIRE:
        texte = re.sub(pattern, '', texte, flags=re.IGNORECASE | re.DOTALL)

    texte = re.sub(
        r'^\s*"?Question\s*:?"?\s*.{0,300}?R[ée]ponse\s*:?\s*',
        '',
        texte,
        flags=re.IGNORECASE | re.DOTALL
    )

    texte = re.sub(
        r'^\s*R[ée]ponse\s*:\s*',
        '',
        texte,
        flags=re.IGNORECASE
    )

    texte = re.sub(
        r'\s*QUESTION\s+DE\s+L\'?UTILISATEUR\s*:.*$',
        '',
        texte,
        flags=re.IGNORECASE | re.DOTALL
    )

    texte = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', ' ', texte)
    texte = re.sub(r'\s+', ' ', texte)
    texte = re.sub(r'\b[Pp]age\s*\d+\b', '', texte)
    texte = re.sub(r'\b[Pp]\.\s*\d+\b', '', texte)
    texte = re.sub(r'\([Pp]age\s*\d+\)', '', texte)
    texte = re.sub(r'[Ll]oi\s+n°\s*[0-9-]+', '', texte)
    texte = re.sub(r'[Pp]romulguée[^)]*\)', '', texte)
    texte = re.sub(r'(.)\1{4,}', r'\1\1', texte)
    texte = re.sub(r'^[•\-\s]+', '', texte)
    texte = re.sub(r'^[0-9]+[\.\)]\s*', '', texte)
    texte = re.sub(r'(?m)^[ \t]*•[ \t]*$\n?', '', texte)
    texte = re.sub(r'\n{3,}', '\n\n', texte)

    if texte.startswith(','):
        texte = texte[1:].strip()
    if texte.startswith('il'):
        texte = 'Il' + texte[2:]

    return texte.strip()


# ============================================================================
# NETTOYAGE DES RÉFÉRENCES LLM
# ============================================================================

def nettoyer_references_llm(texte: str) -> str:
    """Supprime les références de sources ajoutées directement par le LLM."""

    if not texte:
        return texte

    texte = re.sub(r'\s*\(\s*Guide\s+CMRPI\b[^)]*\)', '', texte, flags=re.IGNORECASE)
    texte = re.sub(r'\s*\(?\s*page\s+interne\s*:?\s*\d*\s*\)?', '', texte, flags=re.IGNORECASE)
    texte = re.sub(r'\s*,?\s*page\s*:?\s*\d+\b', '', texte, flags=re.IGNORECASE)
    texte = re.sub(r'\n*\*?\s*Sources?\s*:\s*Guide\s+CMRPI[^*\n]*\*?', '', texte, flags=re.IGNORECASE)
    texte = re.sub(r'\n*\*?\s*Sources consultées\s*\*?[^-]*?(?=\n---|\Z)', '', texte, flags=re.IGNORECASE)
    texte = re.sub(r'\s*\[(?:source|sources|\d+)\]', '', texte, flags=re.IGNORECASE)
    texte = re.sub(r'\bselon\s+le\s+Guide\s+CMRPI\b', '', texte, flags=re.IGNORECASE)
    texte = re.sub(r"\bd['’]après\s+le\s+Guide\s+CMRPI\b", '', texte, flags=re.IGNORECASE)
    texte = re.sub(r'\bbas[ée]\s+sur\s+le\s+Guide\s+CMRPI\b', '', texte, flags=re.IGNORECASE)
    texte = re.sub(r'Guide\s+CMRPI\s*\(\)', '', texte, flags=re.IGNORECASE)
    texte = re.sub(r'Guide\s+CMRPI\s*\(Contenu\)', '', texte, flags=re.IGNORECASE)
    texte = re.sub(r'\(\)', '', texte)

    return texte.strip()


# ============================================================================
# SOURCES AFFICHÉES
# ============================================================================

def construire_sources_affichees(*groupes_items) -> list:
    """Construit la liste finale des sources."""

    pages_guide = []
    autres = []
    vues = set()

    for items in groupes_items:
        if not items:
            continue

        for item in items:
            if not isinstance(item, dict):
                continue

            meta = item.get("meta", {}) or {}

            source_name = str(meta.get("source_name", "") or "").strip()
            source = str(meta.get("source", "") or "").strip()
            page = str(meta.get("page", "") or "").strip()

            if source_name.lower() == "guide cmrpi" or source.upper() == "CMRPI":
                if page.isdigit():
                    if page not in pages_guide:
                        pages_guide.append(page)
                else:
                    if "Guide CMRPI" not in vues:
                        vues.add("Guide CMRPI")
                        autres.append("Guide CMRPI")
            else:
                label = ""
                if source:
                    label = source
                elif meta.get("type_menace"):
                    label = f"Incident : {meta['type_menace']}"

                if label and label not in vues:
                    vues.add(label)
                    autres.append(label)

    resultat = []

    if pages_guide:
        pages_triees = sorted(pages_guide, key=lambda p: int(p))
        resultat.append(f"Guide CMRPI (pages {', '.join(pages_triees)})")
    elif "Guide CMRPI" in vues:
        resultat.append("Guide CMRPI")

    resultat.extend(autres)
    resultat = list(dict.fromkeys(resultat))

    return resultat


# ============================================================================
# MODE DE RÉPONSE
# ============================================================================

def _mode_reponse(query: str) -> str:
    """Détermine le type principal de réponse attendu."""

    q = str(query or '').lower().strip()

    news_terms = (
        'actualité', 'actualités', 'récent', 'récente', 'récentes',
        'dernière', 'dernières', 'dernier', 'récemment', "aujourd'hui",
        'cette semaine', 'ce mois', 'annonce', 'alerte', 'presse'
    )

    stat_terms = (
        'combien', 'nombre', 'total', 'proportion', 'pourcentage',
        'part', 'fréquent', 'fréquente', 'fréquents', 'plus fréquent',
        'principal', 'principaux', 'classement', 'statistique', 'statistiques',
        'tendance', 'évolution', 'augmentation', 'diminution', 'compare', 'comparer'
    )

    guide_terms = (
        'protéger', 'protection', 'sécuriser', 'sécurité', 'prévenir',
        'prévention', 'recommandation', 'recommandations', 'conseil',
        'conseils', 'bonne pratique', 'bonnes pratiques', 'mesure',
        'mesures', 'antivirus', 'mot de passe', 'mots de passe',
        'sauvegarde', 'wifi', 'wi-fi', 'pare-feu', 'firewall',
        'mise à jour', 'mises à jour', 'guide cmrpi'
    )

    has_news = any(x in q for x in news_terms)
    has_stats = any(x in q for x in stat_terms)
    has_guide = any(x in q for x in guide_terms)

    if has_news and (has_stats or has_guide):
        return 'mixte'
    if has_news:
        return 'news'
    if has_stats and has_guide:
        return 'mixte'
    if has_stats:
        return 'stats'
    if has_guide:
        return 'guide'
    return 'general'


# ============================================================================
# CONSTRUCTION DE LA RÉPONSE FINALE
# ============================================================================

def build_unified_response(reponse_fusionnee: dict, lang: str = "fr") -> str:
    """Construit la réponse finale propre avec support de l'abstention."""

    if not reponse_fusionnee:
        return "Je n'ai trouvé aucune information sur cette question dans les documents disponibles."

    if reponse_fusionnee.get('is_abstention'):
        message = reponse_fusionnee.get('synthese_llm')
        if message:
            return message.strip()
        return "Je ne peux pas répondre à cette question car elle ne relève pas du périmètre de l'Observatoire Cyber."

    if reponse_fusionnee.get('no_answer'):
        return reponse_fusionnee.get(
            'message',
            "Je n'ai trouvé aucune information sur cette question dans les documents disponibles."
        )

    query = reponse_fusionnee.get('query', '')
    mode = _mode_reponse(query)
    recommandations = reponse_fusionnee.get('recommandations') or []
    statistiques = reponse_fusionnee.get('statistiques') or []
    actualites = reponse_fusionnee.get('actualites') or []
    synthese_llm = reponse_fusionnee.get('synthese_llm')

    sources = construire_sources_affichees(
        recommandations[:5],
        statistiques[:5],
        actualites[:3]
    )

    sources = list(dict.fromkeys(src for src in sources if src))[:5]
    reponse_fusionnee["sources_affichees"] = sources

    lines = []

    stats_postgres = reponse_fusionnee.get('stats_postgres') or reponse_fusionnee.get('statistiques_postgres')

    a_du_contenu_guide = bool(synthese_llm) or bool(recommandations)

    if stats_postgres and not a_du_contenu_guide:
        lines.append(stats_postgres)

        if sources:
            lines.append('')
            lines.append('**Sources :**')
            lines.extend(f'• {src}' for src in sources)

        result = '\n'.join(lines)
        return result

    if synthese_llm:
        texte = nettoyer_artefacts_avance(synthese_llm)
        texte = nettoyer_references_llm(texte)

        texte = re.sub(r'Guide\s+CMRPI\s*\(\)', '', texte, flags=re.IGNORECASE)
        texte = re.sub(r'\(\)', '', texte)
        texte = re.sub(r'^,\s*', '', texte)
        texte = re.sub(r'[\s]*\n?[ \t]*•[ \t]*$', '', texte)

        texte = corriger_orthographe(texte).strip()

        if texte and len(texte) >= 10:
            lines.append(texte)
        else:
            synthese_llm = None

    if not synthese_llm:
        if mode == 'stats' and statistiques:
            lines.append('**Statistiques observées**')
            vus = set()

            for item in statistiques[:5]:
                meta = item.get('meta', {}) or {}
                typ = str(meta.get('type_menace', '') or '').strip().upper()

                if not typ or typ in {'INCONNU', 'INCONNUE', 'UNKNOWN'} or typ in vus:
                    continue

                vus.add(typ)
                nombre = meta.get('nombre', '')
                lines.append(f'- **{typ}** : {nombre} cas' if nombre != '' else f'- **{typ}**')

        elif mode == 'news' and actualites:
            lines.append('**Actualités récentes**')

            for item in actualites[:3]:
                meta = item.get('meta', {}) or {}
                source = meta.get('source') or meta.get('source_name') or ''
                date = meta.get('date_publication') or ''
                texte = nettoyer_artefacts_avance(str(item.get('texte', ''))[:250])

                if texte:
                    suffix = f' ({date})' if date else ''
                    prefix = f'**{source}**{suffix}: ' if source else ''
                    lines.append(f'- {prefix}{texte}')

        elif recommandations:
            lines.append('**Recommandations**')

            for item in recommandations[:4]:
                texte = item.get('texte', '') if isinstance(item, dict) else str(item)
                texte = corriger_orthographe(nettoyer_artefacts_avance(texte))

                if len(texte) > 350:
                    texte = texte[:350] + '...'

                if texte:
                    lines.append(f'- {texte}')

        elif statistiques:
            lines.append('**Statistiques observées**')

            for item in statistiques[:5]:
                meta = item.get('meta', {}) or {}
                typ = str(meta.get('type_menace', '') or '').strip().upper()
                nombre = meta.get('nombre', '')

                if typ and typ not in {'INCONNU', 'INCONNUE', 'UNKNOWN'}:
                    lines.append(f'- **{typ}** : {nombre} cas' if nombre != '' else f'- **{typ}**')

        elif actualites:
            lines.append('**Actualités récentes**')

            for item in actualites[:3]:
                texte = nettoyer_artefacts_avance(str(item.get('texte', ''))[:250])

                if texte:
                    lines.append(f'- {texte}')

        else:
            return "Je n'ai trouvé aucune information sur cette question dans les documents disponibles."

    if stats_postgres and a_du_contenu_guide:
        lines.append('')
        lines.append(stats_postgres)

    result = '\n'.join(lines)

    # Nettoyage final
    result = re.sub(r'📚\s*Sources\s*:.*?(?=\n\n|\n\*|$)', '', result, flags=re.DOTALL)
    result = re.sub(r'(\*\*Sources :\*\*.*?)(?=\*\*Sources :\*\*)', r'\1', result, flags=re.DOTALL)
    result = re.sub(r'Sources\s*:\s*\n(?:•[^\n]*\n)*', '', result, flags=re.IGNORECASE)
    result = re.sub(r'\n(?:•[^\n]*\n)+', '', result)
    result = re.sub(r'\*\*Sources :\*\*\s*\n\s*$', '', result)
    result = re.sub(r'\*\*Sources :\*\*\s*\n(?:•[^\n]*\n)*', '', result)
    result = re.sub(r'\n\s*•\s*\n', '\n', result)
    result = re.sub(r'Guide\s+CMRPI\s*\(Contenu\)', '', result, flags=re.IGNORECASE)
    result = re.sub(r'Guide\s+CMRPI\s*\([^)]*\)', '', result, flags=re.IGNORECASE)
    result = re.sub(r'\bselon\s+le\s+Guide\s+CMRPI\b', '', result, flags=re.IGNORECASE)
    result = re.sub(r'\s*\(?\s*page\s+interne\s*:?\s*\d*\s*\)?', '', result, flags=re.IGNORECASE)
    result = re.sub(r'\s*\(?Document\s+\d+\)?', '', result, flags=re.IGNORECASE)
    result = re.sub(r'\s*Source\s*:\s*Document\s+\d+', '', result, flags=re.IGNORECASE)
    result = re.sub(r'^,\s*', '', result)
    result = re.sub(r'\n,\s*', '\n', result)
    result = re.sub(r'\(\)', '', result)
    result = re.sub(r'\n{3,}', '\n\n', result)

    if result.startswith(','):
        result = result[1:].strip()
    if result.startswith('il'):
        result = 'Il' + result[2:]

    result = result.strip()

    print('=' * 60)
    print('📝 RÉPONSE GÉNÉRÉE')
    print('=' * 60)
    print(f'Longueur: {len(result)} caractères')
    print(result[:700] + '...' if len(result) > 700 else result)
    print('=' * 60)

    return result