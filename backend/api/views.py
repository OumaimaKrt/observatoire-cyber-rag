# ============================================================================
# backend/api/views.py
# VERSION CORRIGÉE - UTILISE stats_for_llm + SUPPORT MIXTE
# ============================================================================

from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
import psycopg2
import sys
import os
import json
import traceback
import uuid
from datetime import datetime, date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from config import DB_CONFIG
except ImportError:
    DB_CONFIG = {
        "host": "localhost",
        "port": 5432,
        "database": "observatoire_cyber",
        "user": "postgres",
        "password": "postgres",
    }


# ============================================================================
# UTILITAIRES POSTGRESQL
# ============================================================================

def _est_question_statistique(query: str, route: dict | None = None) -> bool:
    """Détermine si PostgreSQL doit être consulté.

    Une question Guide seule ne déclenche jamais SQL. Une question MIXTE peut
    utiliser SQL en complément du Guide lorsque sa formulation demande une
    fréquence, une proportion, un nombre ou une tendance.
    """
    q = str(query or "").lower().strip()
    explicit = (
        "combien", "nombre", "total", "proportion", "pourcentage", "quelle part",
        "plus fréquent", "plus fréquente", "plus fréquents", "plus fréquentes",
        "menace la plus fréquente", "répartition", "distribution", "classement",
        "statistique", "statistiques", "tendance", "évolution", "augmentation",
        "diminution", "compare", "comparer", "recensé", "recensés",
        "combien d'incidents"
    )
    if not any(x in q for x in explicit):
        return False

    intent = ((route or {}).get("intentions") or {}).get("intent", "")
    if intent == "guide":
        return False

    # Pour une question mixte, SQL enrichit le contexte mais ne doit pas
    # court-circuiter le RAG.
    return intent in {"incidents", "mixte", "actualites"} or intent == ""


def format_sql_results(result: dict, lang: str = "fr") -> str:
    """Formatage déterministe des résultats SQL."""
    if not result or not result.get("success"):
        return ""
    data = result.get("data") or []
    label = result.get("label", "")
    kind = result.get("result_kind", "")
    if not data:
        return ""

    lines = [f"**{label}** :"] if label else []
    for row in data:
        row = tuple(row)
        if kind == "threat_distribution" and len(row) >= 3:
            lines.append(f"- {row[0]} : {row[1]} ({row[2]}%)")
        elif kind == "threat_type" and len(row) >= 4:
            lines.append(f"- {row[0]} : {row[1]} incidents (dont {row[2]} critiques ; {row[3]}% du total connu)")
        elif kind == "overview" and len(row) >= 4:
            lines.extend([f"- Total : {row[0]}", f"- Incidents avec type connu : {row[1]}", f"- Critiques : {row[2]}", f"- Élevés : {row[3]}"])
        elif kind == "severity" and len(row) >= 2:
            lines.append(f"- {row[0]} : {row[1]}")
        elif len(row) == 1:
            lines.append(f"- {row[0]}")
        elif len(row) == 2:
            lines.append(f"- {row[0]} : {row[1]}")
        else:
            lines.append("- " + ", ".join(str(x) for x in row))
    return "\n".join(lines)


# ============================================================================
# FONCTION DE SÉRIALISATION SÉCURISÉE POUR RAGAS
# ============================================================================

def serialiser_donnees_sql(data_rows: list) -> list:
    """
    Convertit les données SQL en format sérialisable JSON.

    Gère :
    - datetime → ISO 8601
    - date → ISO 8601
    - Decimal → float
    - Autres types → str
    """
    if not data_rows:
        return []

    resultats = []

    for row in data_rows:
        if isinstance(row, (list, tuple)):
            clean_row = []
            for item in row:
                if item is None:
                    clean_row.append(None)
                elif isinstance(item, (datetime, date)):
                    clean_row.append(item.isoformat())
                elif isinstance(item, Decimal):
                    clean_row.append(float(item))
                elif isinstance(item, (int, float, bool, str)):
                    clean_row.append(item)
                else:
                    clean_row.append(str(item))
            resultats.append(tuple(clean_row))
        else:
            resultats.append(str(row))

    return resultats


# ============================================================================
# CONVERSATION MEMORY
# ============================================================================

conversation_memory = {}

def get_conversation_context(session_id: str) -> str:
    if session_id not in conversation_memory:
        return ""
    memory = conversation_memory[session_id]
    derniers = memory[-3:]
    if not derniers:
        return ""

    context = "Historique de la conversation (du plus ancien au plus récent) :\n\n"

    for i, item in enumerate(derniers):
        est_le_plus_recent = (i == len(derniers) - 1)
        etiquette = (
            "➡️ ÉCHANGE LE PLUS RÉCENT (c'est très probablement celui "
            "auquel la question actuelle fait référence si elle est "
            "vague ou demande une clarification/un résumé)"
            if est_le_plus_recent
            else "Échange précédent"
        )
        context += f"[{etiquette}]\n"
        context += f"Question : {item['query']}\n"
        context += f"Réponse : {item['response'][:500]}\n\n"

    return context

def add_to_memory(session_id: str, query: str, response: str):
    if session_id not in conversation_memory:
        conversation_memory[session_id] = []
    conversation_memory[session_id].append({"query": query, "response": response})
    if len(conversation_memory[session_id]) > 3:
        conversation_memory[session_id].pop(0)


# ============================================================================
# VALIDATION DES RÉPONSES
# ============================================================================

def validate_response_simple(response: str, context: list) -> tuple:
    if not response or len(response.strip()) < 20:
        return False, "Réponse trop courte ou vide"

    forbidden_brands = ['bitdefender', 'norton', 'mcafee', 'symantec', 'avast', 'kaspersky']
    response_lower = response.lower()
    context_text = " ".join(context).lower() if context else ""

    for brand in forbidden_brands:
        if brand in response_lower and brand not in context_text:
            return False, f"Marque '{brand}' non trouvée dans le contexte"

    return True, ""


# ============================================================================
# FILTRES MÉTADONNÉES
# ============================================================================

def build_metadata_filters(query: str) -> dict:
    filters = {}
    query_lower = query.lower()

    sectors = {
        'FINANCE': ['finance', 'banque', 'assurance', 'fintech', 'bank'],
        'SANTE': ['sante', 'hôpital', 'medical', 'pharmacie', 'health'],
        'INDUSTRIE': ['industrie', 'manufacture', 'usine', 'factory'],
        'TELECOM': ['telecom', 'internet', 'mobile', 'network'],
        'COMMERCE': ['commerce', 'retail', 'distribution'],
    }

    for sector, keywords in sectors.items():
        if any(kw in query_lower for kw in keywords):
            filters['secteur_cible'] = sector
            break

    if any(kw in query_lower for kw in ['ransomware', 'ransom', 'lockbit']):
        filters['type_menace'] = 'RANSOMWARE'
    elif any(kw in query_lower for kw in ['phishing', 'spear']):
        filters['type_menace'] = 'PHISHING'
    elif any(kw in query_lower for kw in ['ddos', 'dos']):
        filters['type_menace'] = 'DDOS'

    return filters


# ============================================================================
# CHATBOT RAG - ENDPOINT PRINCIPAL
# ============================================================================

@csrf_exempt
def chat(request):
    """Endpoint pour le chatbot RAG (sans streaming)."""
    print("=" * 60)
    print("CHAT REQUEST RECEIVED")
    print(f"Method: {request.method}")
    print(f"Body: {request.body}")
    print("=" * 60)

    query = ''

    if request.method == 'GET':
        query = request.GET.get('query', '')
        print(f"GET query: {query}")
    else:
        try:
            body_str = request.body.decode('utf-8')
            print(f"Body string: {body_str}")

            if body_str:
                data = json.loads(body_str)
                query = data.get('query', '')
                print(f"Parsed query: {query}")
            else:
                print("Empty body")
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")

    if not query:
        print("Query is empty, returning error")
        return JsonResponse({'error': 'Query is required'}, status=400)

    try:
        print(f"Processing query: {query}")

        from scripts.rag_fusion import fusionner_reponses
        from scripts.response_builder import build_unified_response
        from scripts.intent_router import router
        from scripts.language_detector import detect_language

        import rag_core
        app = rag_core
        print("RAG core loaded successfully")

        lang = detect_language(query)
        print(f"Detected language: {lang}")

        session_id = request.META.get('HTTP_X_SESSION_ID') or f"anon-{uuid.uuid4()}"
        conversation_context = get_conversation_context(session_id)

        route = router(query, conversation_context=conversation_context)
        print(f"Route: {route}")

        # ================================================================
        # SALUTATIONS
        # ================================================================

        if route.get("is_greeting", False):
            return JsonResponse({
                'query': query,
                'response': route.get(
                    "greeting_response",
                    "Bonjour ! Comment puis-je vous aider ?"
                ),
                'sources': [],
                'language': lang,
                'is_greeting': True,
            })

        if route.get("off_topic", False):
            return JsonResponse({
                'query': query,
                'response': route.get("message", "Cette question ne relève pas du domaine de l'Observatoire Cyber."),
                'sources': [],
                'language': lang,
                'off_topic': True,
            })

        # ================================================================
        # 🔥 DÉTECTION DES QUESTIONS STATISTIQUES → POSTGRESQL
        # ================================================================

        stats_result = None
        est_statistique = _est_question_statistique(query, route)

        if est_statistique:
            try:
                from scripts.agent_orchestrator import SQLAgent
                conn = psycopg2.connect(**DB_CONFIG)
                sql_agent = SQLAgent(conn)
                stats_result = sql_agent.execute(query)
                conn.close()
                print(f"📊 Statistiques SQL: {stats_result}")
            except Exception as e:
                print(f"⚠️ Erreur SQL: {e}")
                stats_result = None

        intent_courante = ((route.get("intentions") or {}).get("intent", ""))

        # ================================================================
        # 🔥 CAS 1: QUESTION PUREMENT STATISTIQUE (incidents uniquement)
        # ================================================================

        if (
            stats_result
            and stats_result.get("success")
            and stats_result.get("data")
            and intent_courante == "incidents"
        ):
            # 🔥 Utiliser stats_for_llm si disponible, sinon format_sql_results
            if stats_result.get("stats_for_llm"):
                reponse_texte = stats_result["stats_for_llm"]
            else:
                reponse_texte = format_sql_results(stats_result, lang)

            if reponse_texte:
                add_to_memory(session_id, query, reponse_texte)

                reponse_json = {
                    'query': query,
                    'response': reponse_texte,
                    'sources': ["Données PostgreSQL - Observatoire Cyber"],
                    'language': lang,
                    'is_statistics': True,
                    'status': 'success'
                }

                # 🔥 Sérialisation sécurisée pour RAGAS
                debug_contexts = (
                    request.GET.get('debug_contexts') == '1'
                    or request.META.get('HTTP_X_DEBUG_CONTEXTS') == '1'
                )

                if debug_contexts:
                    try:
                        data_rows = stats_result.get("data", [])
                        serialisable = serialiser_donnees_sql(data_rows)
                        reponse_json['retrieved_contexts'] = [
                            json.dumps(serialisable, ensure_ascii=False)
                        ]
                        print(f"🔍 STATS: contexte sérialisé pour RAGAS ({len(serialisable)} lignes)")
                    except Exception as e:
                        print(f"⚠️ Erreur sérialisation des stats: {e}")
                        reponse_json['retrieved_contexts'] = [reponse_texte]

                return JsonResponse(reponse_json)

        # ================================================================
        # 🔥 CAS 2: QUESTION MIXTE (guide + incidents) ou AUTRE
        # → PASSER par le LLM pour une réponse naturelle
        # ================================================================

        print(f"🔄 Question mixte ou générale - passage par RAG complet")

        collections = app.init_chroma_collections()
        print("ChromaDB collections initialized")

        if conversation_context:
            print(f"Conversation context: {conversation_context[:100]}...")

        requete_recherche = route.get("requete_effective") or query
        if requete_recherche != query:
            print(f"Requête reformulée pour la recherche : {requete_recherche!r}")

        filters = build_metadata_filters(query)
        print(f"Filtres: {filters}")

        resultats = {}
        for name in route["collections"]:
            if collections.get(name) is not None:
                resultats[name] = app.query_collection(
                    collections[name],
                    requete_recherche,
                    n_results=10,
                    filters=filters
                )
                print(f"Collection '{name}' queried")
            else:
                resultats[name] = {'documents': [], 'metadatas': [], 'distances': []}
                print(f"Collection '{name}' not found")

        print("Fusionning responses...")

        reponse_fusionnee = fusionner_reponses(
            resultats,
            query,
            lang,
            app.generate_llm_answer_simple,
            stats_result=stats_result,
            conversation_context=conversation_context,
            intent=intent_courante
        )
        print("Responses fused")

        reponse_texte = build_unified_response(reponse_fusionnee, lang)
        print("Response built")

        # ================================================================
        # 🔥 EXTRACTION DES CONTEXTES AVEC FALLBACK
        # ================================================================

        context_docs = []
        total_docs = 0

        for name, results in resultats.items():
            if results.get('documents') and results['documents'][0]:
                docs = results['documents'][0][:5]
                context_docs.extend(docs)
                total_docs += len(docs)
                print(f"📄 Collection '{name}': {len(docs)} documents")

        print(f"🔍 Total documents extraits de ChromaDB: {total_docs}")

        if not context_docs:
            print("⚠️ Aucun document dans resultats, fallback vers les sources")
            sources = (
                reponse_fusionnee.get('sources_affichees', [])
                or reponse_fusionnee.get('sources', [])
            )
            if sources:
                sources_filtered = [str(s) for s in sources if s and str(s).strip()]
                if sources_filtered:
                    context_docs = sources_filtered
                    print(f"⚠️ Fallback sources : {len(context_docs)} éléments")
                else:
                    print("⚠️ Sources vides après filtrage")
            else:
                print("⚠️ Aucune source disponible")

        if not context_docs:
            context_docs = ["Aucun contexte disponible pour cette question."]
            print("⚠️ Fallback final : aucun contexte disponible")

        print(f"✅ Total contextes exposés : {len(context_docs)}")
        if context_docs and context_docs[0]:
            print(f"📝 Premier contexte: {context_docs[0][:100]}...")

        # ================================================================
        # VALIDATION
        # ================================================================

        is_valid, validation_msg = validate_response_simple(reponse_texte, context_docs)

        if not is_valid:
            reponse_texte = "Je n'ai trouvé aucune information fiable sur cette question dans les documents disponibles."
            print(f"⚠️ Réponse invalidée: {validation_msg}")
        else:
            print(f"✅ Réponse valide ({len(reponse_texte)} caractères)")

        add_to_memory(session_id, query, reponse_texte)

        reponse_json = {
            'query': query,
            'response': reponse_texte,
            'sources': reponse_fusionnee.get('sources_affichees', list(reponse_fusionnee.get('sources', []))),
            'language': lang,
            'has_recommendations': len(reponse_fusionnee.get('recommandations', [])) > 0,
            'has_statistics': len(reponse_fusionnee.get('statistiques', [])) > 0,
            'has_news': len(reponse_fusionnee.get('actualites', [])) > 0,
            'status': 'success'
        }

        debug_contexts = (
            request.GET.get('debug_contexts') == '1'
            or request.META.get('HTTP_X_DEBUG_CONTEXTS') == '1'
        )

        if debug_contexts:
            reponse_json['retrieved_contexts'] = context_docs
            reponse_json['retrieved_sources'] = reponse_fusionnee.get('sources_affichees', [])
            print(f"🔍 DEBUG MODE : {len(context_docs)} contextes exposés, {len(reponse_json['retrieved_sources'])} sources")

            if context_docs:
                sample = context_docs[0][:200] if len(context_docs) > 0 else "Vide"
                print(f"📝 Exemple contexte exposé: {sample}...")

        return JsonResponse(reponse_json)

    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()
        return JsonResponse({
            'error': str(e),
            'response': f"Erreur RAG: {str(e)}",
            'sources': [],
            'status': 'error'
        }, status=500)


# ============================================================================
# CHATBOT RAG - STREAMING
# ============================================================================

@csrf_exempt
def chat_stream(request):
    """🔥 Endpoint avec streaming pour les réponses en temps réel."""
    print("=" * 60)
    print("CHAT STREAM REQUEST RECEIVED")
    print("=" * 60)

    query = ''
    session_id = f"anon-{uuid.uuid4()}"

    if request.method == 'POST':
        try:
            body_str = request.body.decode('utf-8')
            if body_str:
                data = json.loads(body_str)
                query = data.get('query', '')
                session_id = data.get('session_id') or session_id
        except:
            pass

    if not query:
        return JsonResponse({'error': 'Query is required'}, status=400)

    def generate():
        try:
            from scripts.rag_fusion import fusionner_reponses
            from scripts.intent_router import router
            from scripts.language_detector import detect_language
            from scripts.response_builder import build_unified_response, corriger_orthographe
            from scripts.agent_orchestrator import SQLAgent, format_sql_results

            import rag_core
            app = rag_core

            lang = detect_language(query)
            conversation_context = get_conversation_context(session_id)
            route = router(query, conversation_context=conversation_context)
            print(f"Route: {route}")

            # Salutations
            if route.get("is_greeting", False):
                greeting = route.get(
                    "greeting_response",
                    "Bonjour ! Comment puis-je vous aider ?"
                )
                yield json.dumps({
                    'type': 'sources',
                    'content': []
                }) + '\n'
                for word in greeting.split(' '):
                    yield json.dumps({
                        'type': 'token',
                        'content': word + ' '
                    }) + '\n'
                yield json.dumps({
                    'type': 'done',
                    'sources': []
                }) + '\n'
                return

            if route.get("off_topic", False):
                yield json.dumps({
                    'type': 'error',
                    'content': route.get("message", "Hors domaine")
                }) + '\n'
                return

            # 🔥 DÉTECTION STATISTIQUES
            stats_result = None
            est_statistique = _est_question_statistique(query, route)

            if est_statistique:
                try:
                    conn = psycopg2.connect(**DB_CONFIG)
                    sql_agent = SQLAgent(conn)
                    stats_result = sql_agent.execute(query)
                    conn.close()
                    print(f"📊 Statistiques SQL: {stats_result}")
                except Exception as e:
                    print(f"⚠️ Erreur SQL: {e}")
                    stats_result = None

            intent_courante = ((route.get("intentions") or {}).get("intent", ""))

            # 🔥 Pour les questions purement statistiques, réponse directe
            if (
                stats_result
                and stats_result.get("success")
                and stats_result.get("data")
                and intent_courante == "incidents"
            ):
                if stats_result.get("stats_for_llm"):
                    reponse_texte = stats_result["stats_for_llm"]
                else:
                    reponse_texte = format_sql_results(stats_result, lang)

                if reponse_texte:
                    yield json.dumps({
                        'type': 'sources',
                        'content': ["Données PostgreSQL - Observatoire Cyber"]
                    }) + '\n'
                    for word in reponse_texte.split(' '):
                        yield json.dumps({
                            'type': 'token',
                            'content': word + ' '
                        }) + '\n'
                    yield json.dumps({
                        'type': 'done',
                        'sources': ["Données PostgreSQL - Observatoire Cyber"]
                    }) + '\n'
                    return

            # RAG classique pour les questions mixtes
            collections = app.init_chroma_collections()

            filters = build_metadata_filters(query)
            requete_recherche = route.get("requete_effective") or query

            resultats = {}
            for name in route["collections"]:
                if collections.get(name) is not None:
                    resultats[name] = app.query_collection(
                        collections[name],
                        requete_recherche,
                        n_results=10,
                        filters=filters
                    )
                    print(f"Collection '{name}' queried")

            reponse_fusionnee = fusionner_reponses(
                resultats,
                query,
                lang,
                app.generate_llm_answer_simple,
                stats_result=stats_result,
                conversation_context=conversation_context,
                intent=intent_courante
            )

            reponse_texte = build_unified_response(reponse_fusionnee, lang)
            reponse_texte = corriger_orthographe(reponse_texte)

            sources = reponse_fusionnee.get(
                'sources_affichees',
                list(reponse_fusionnee.get('sources', []))
            )

            yield json.dumps({
                'type': 'sources',
                'content': sources
            }) + '\n'

            context_docs = []
            for results in resultats.values():
                if results.get('documents'):
                    context_docs.extend(results['documents'][0])

            is_valid, _ = validate_response_simple(reponse_texte, context_docs)
            if not is_valid:
                reponse_texte = "Je n'ai trouvé aucune information fiable sur cette question dans les documents disponibles."

            tokens = reponse_texte.split(' ')
            total_tokens = len(tokens)
            for i, token in enumerate(tokens):
                yield json.dumps({
                    'type': 'token',
                    'content': token + ' ',
                    'progress': (i + 1) / total_tokens
                }) + '\n'

            yield json.dumps({
                'type': 'done',
                'sources': sources
            }) + '\n'

            add_to_memory(session_id, query, reponse_texte)

        except Exception as e:
            print(f"❌ Erreur streaming: {e}")
            traceback.print_exc()
            yield json.dumps({
                'type': 'error',
                'content': f"Erreur: {str(e)}"
            }) + '\n'

    return StreamingHttpResponse(
        generate(),
        content_type='application/x-ndjson'
    )


# ============================================================================
# DASHBOARD STATISTIQUES
# ============================================================================

def get_dashboard_stats(request):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM cyber_incidents")
        total_incidents = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(DISTINCT type_menace)
            FROM cyber_incidents
            WHERE type_menace != 'INCONNU' AND type_menace != ''
        """)
        active_threats = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*)
            FROM cyber_incidents
            WHERE severite = 'CRITIQUE'
        """)
        critical_alerts = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(DISTINCT secteur_cible)
            FROM cyber_incidents
            WHERE secteur_cible != 'INCONNU' AND secteur_cible != ''
        """)
        sectors_affected = cur.fetchone()[0]

        cur.execute("""
            SELECT type_menace, COUNT(*) as nb,
                   ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM cyber_incidents), 1) as pct
            FROM cyber_incidents
            WHERE type_menace != 'INCONNU' AND type_menace != ''
            GROUP BY type_menace
            ORDER BY nb DESC
            LIMIT 5
        """)
        top_types = [{'type': row[0], 'count': row[1], 'pct': row[2]} for row in cur.fetchall()]

        cur.execute("""
            SELECT secteur_cible, COUNT(*) as nb,
                   ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM cyber_incidents), 1) as pct
            FROM cyber_incidents
            WHERE secteur_cible != 'INCONNU' AND secteur_cible != ''
            GROUP BY secteur_cible
            ORDER BY nb DESC
            LIMIT 5
        """)
        top_sectors = [{'secteur': row[0], 'count': row[1], 'pct': row[2]} for row in cur.fetchall()]

        cur.execute("""
            SELECT DATE(created_at) as date, COUNT(*) as incidents
            FROM cyber_incidents
            WHERE created_at >= NOW() - INTERVAL '30 days'
            GROUP BY DATE(created_at)
            ORDER BY date
        """)
        timeline = [{'date': row[0].strftime('%d/%m'), 'incidents': row[1]} for row in cur.fetchall()]

        cur.close()
        conn.close()

        return JsonResponse({
            'total_incidents': total_incidents,
            'active_threats': active_threats,
            'critical_alerts': critical_alerts,
            'sectors_affected': sectors_affected,
            'top_types': top_types,
            'top_sectors': top_sectors,
            'timeline': timeline,
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# INCIDENTS
# ============================================================================

def get_incidents(request):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        type_filter = request.GET.get('type', '')
        secteur_filter = request.GET.get('secteur', '')
        limit = int(request.GET.get('limit', 50))
        offset = int(request.GET.get('offset', 0))

        query = """
            SELECT id, titre, type_menace, secteur_cible, severite, source, created_at
            FROM cyber_incidents
            WHERE 1=1
        """
        params = []

        if type_filter:
            query += " AND type_menace = %s"
            params.append(type_filter)

        if secteur_filter:
            query += " AND secteur_cible = %s"
            params.append(secteur_filter)

        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        cur.execute(query, params)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        cur.close()
        conn.close()

        incidents = []
        for row in rows:
            incident = dict(zip(columns, row))
            if incident.get('created_at'):
                incident['created_at'] = incident['created_at'].isoformat()
            incidents.append(incident)

        return JsonResponse(incidents, safe=False)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# SECTEURS ET TYPES
# ============================================================================

def get_sectors(request):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT secteur_cible
            FROM cyber_incidents
            WHERE secteur_cible != 'INCONNU' AND secteur_cible != ''
            ORDER BY secteur_cible
        """)
        sectors = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return JsonResponse(sectors, safe=False)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def get_types(request):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT type_menace
            FROM cyber_incidents
            WHERE type_menace != 'INCONNU' AND type_menace != ''
            ORDER BY type_menace
        """)
        types = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return JsonResponse(types, safe=False)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# RAPPORT SECTEUR
# ============================================================================

def get_sector_report(request, secteur):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        cur.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN severite = 'CRITIQUE' THEN 1 END) as critiques,
                COUNT(CASE WHEN type_menace = 'RANSOMWARE' THEN 1 END) as ransomwares,
                COUNT(CASE WHEN type_menace = 'PHISHING' THEN 1 END) as phishing
            FROM cyber_incidents
            WHERE secteur_cible = %s
        """, (secteur.upper(),))
        stats = cur.fetchone()

        cur.execute("""
            SELECT type_menace, COUNT(*) as nb
            FROM cyber_incidents
            WHERE secteur_cible = %s AND type_menace != 'INCONNU'
            GROUP BY type_menace
            ORDER BY nb DESC
            LIMIT 5
        """, (secteur.upper(),))
        top_menaces = [{'type': row[0], 'count': row[1]} for row in cur.fetchall()]

        cur.close()
        conn.close()

        return JsonResponse({
            'secteur': secteur,
            'total_incidents': stats[0] or 0,
            'critiques': stats[1] or 0,
            'ransomwares': stats[2] or 0,
            'phishing': stats[3] or 0,
            'top_menaces': top_menaces,
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# TESTS ET STATUS
# ============================================================================

@csrf_exempt
def chat_test(request):
    return JsonResponse({
        'status': 'ok',
        'response': 'Test de réponse du RAG',
        'sources': ['Guide CMRPI (page test)'],
        'language': 'fr',
    })


def status(request):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        db_status = "connected"
    except:
        db_status = "disconnected"

    return JsonResponse({
        'status': 'running',
        'database': db_status,
        'rag': 'active',
        'collections': ['cmrpi_guide', 'cyber_incidents', 'sector_news']
    })