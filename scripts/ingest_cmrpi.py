"""
============================================================================
scripts/ingest_cmrpi.py
============================================================================
INGESTION ROBUSTE DU GUIDE CMRPI DANS CHROMADB

Pipeline :
    PDF -> rendu haute résolution -> Tesseract OCR FR
        -> nettoyage OCR -> suppression en-têtes/pieds récurrents
        -> filtrage des pages inutiles (couverture, mentions légales)
        -> détection prudente des titres -> chunking respectant les mots
        -> BAAI/bge-m3 -> ChromaDB

Pourquoi OCR uniquement ?
    Le PDF possède un mapping texte interne défectueux. Une extraction
    native peut produire des caractères incohérents. L'OCR est donc la
    source principale afin d'éviter d'injecter du texte corrompu dans le RAG.

Correctifs appliqués sur cette version (suite à l'analyse qualité) :
    1. NETTOYAGE : les mots coupés en plein milieu ("nnaissances", "rêts",
       "ette thématique") ne venaient PAS de la pagination, mais du
       découpage `decouper_long_texte()` qui aplatissait le texte avec
       `re.sub(r"\\s+", " ", texte)` puis tranchait par index de caractère
       (`phrase[start:end]`) sans respecter les limites de mots. Corrigé :
       le découpage respecte désormais les lignes, puis les phrases, et en
       dernier recours coupe uniquement sur un espace.
    2. PAGES INUTILES : détection et exclusion des pages de couverture /
       mentions légales / code-barres ISBN qui polluaient les premiers
       chunks (ex: "9" 789954 * 996720 ... Dépôt légal ...").
    3. TITRES : l'heuristique "ligne courte sans article" produisait des
       faux titres ("travaux", "a contribution au développement du
       Maroc"...). Elle est supprimée ; seules les sections numérotées,
       les lignes en MAJUSCULES et une liste de mots-clés connus sont
       retenues comme titres.
    4. BENCHMARK RAG : ajout de métriques Recall@k / MRR avec des pages
       de référence, plutôt qu'un simple affichage des résultats.
============================================================================
"""

import os
import re
import statistics
import sys
import subprocess
import tempfile
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ============================================================================
# CONFIGURATION
# ============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

TESSERACT_DIR = Path(r"C:\Tesseract-OCR")
TESSERACT_CMD = TESSERACT_DIR / "tesseract.exe"

os.environ["TESSDATA_PREFIX"] = str(TESSERACT_DIR)
os.environ["PATH"] = str(TESSERACT_DIR) + os.pathsep + os.environ.get("PATH", "")

import chromadb
from chromadb.utils import embedding_functions

try:
    from rank_bm25 import BM25Okapi
    BM25_DISPONIBLE = True
except ImportError:
    # pip install rank_bm25 — dépendance légère (pure Python), utilisée
    # uniquement pour la recherche hybride du benchmark. Le script reste
    # fonctionnel sans elle (retombe sur la recherche vectorielle seule).
    BM25_DISPONIBLE = False

from utils.logger import get_logger

logger = get_logger("ingest_cmrpi")

# Chemins relatifs au projet, pas au dossier courant du terminal.
CHROMA_PATH = PROJECT_ROOT / "data" / "chroma_db"
PDF_PATH = PROJECT_ROOT / "data" / "Guide-de-bonnes-pratique.pdf"

COLLECTION_NAME = "cmrpi_guide"
EMBEDDING_MODEL = "BAAI/bge-m3"

# ============================================================================
# PARAMÈTRES OCR
# ============================================================================

OCR_ZOOM = 4.0
OCR_LANGUAGE = "fra"
OCR_OEM = "3"

# PSM 3 : mise en page automatique.
# PSM 6 : bloc uniforme, utile en fallback sur certaines pages.
OCR_PSM_PRIMARY = "3"
OCR_PSM_FALLBACK = "6"

# Une page sous ce seuil peut être normale (couverture/table des matières),
# mais elle mérite un contrôle ou un deuxième OCR.
MIN_PAGE_CHARS = 80
WEAK_PAGE_CHARS = 250

# ============================================================================
# PARAMÈTRES CHUNKING
# ============================================================================

CHUNK_SIZE = 500
CHUNK_OVERLAP = 80
MIN_CHUNK_CHARS = 80
BATCH_SIZE = 50

# ============================================================================
# QUALITÉ OCR
# ============================================================================

# Mots français fréquents permettant de distinguer un OCR plausible d'un
# résultat constitué majoritairement de symboles.
MOTS_FRANCAIS = {
    " le ", " la ", " les ", " de ", " des ", " du ", " un ", " une ",
    " et ", " est ", " pour ", " dans ", " que ", " qui ", " sur ",
    " avec ", " ce ", " ces ", " son ", " sont ", " par ", " au ",
    " aux ", " pas ", " entreprise ", " sécurité ",
    " système ", " données ", " information ", " mot ", " passe ",
}

# ============================================================================
# PAGES INUTILES (couverture, mentions légales, code-barres ISBN)
# ============================================================================

# Motifs typiques d'une page de couverture / verso juridique, qui n'apportent
# rien à un RAG de bonnes pratiques cybersécurité et polluent les tout
# premiers chunks (le plus souvent chunk_index 0 ou 1).
MOTIFS_PAGE_JURIDIQUE = [
    r"d[ée]p[ôo]t l[ée]gal",
    r"tous droits r[ée]serv[ée]s",
    r"toute reproduction",
    r"\bisbn\b",
    r"biblioth[èe]que nationale",
    r"©\s*copyright",
]

# Ligne "code-barres OCR" : suite de chiffres/espaces/symboles sans mots.
RE_LIGNE_CODE_BARRE = re.compile(r"^[\d\s\"'*\.\-]{8,}$")

# Fragments du titre du document lui-même : sur ce guide, le titre revient
# tel quel sur la couverture ET sur la page de titre intérieure (pages 1 et
# 3), sans mention légale détectable. Ces pages ne contiennent aucune
# information utile pour répondre à une question de cybersécurité, et leur
# fragment en MAJUSCULES ("COMMENT FAIRE FACE AUX") était en plus détecté à
# tort comme un titre de section, contaminant ensuite les chunks suivants
# via `titre_courant`.
TITRE_DOCUMENT_MOTS = {
    "petites et moyennes entreprises marocaines",
    "comment faire face aux menaces cybernetiques",
    "guide de bonnes pratiques",
}

# Nombre de pages, depuis le début du document, où l'on tolère la présence
# d'une page de titre/couverture. Au-delà, un texte court est plus
# probablement un intertitre de chapitre qu'une répétition du titre général.
PAGES_FRONT_MATTER_MAX = 5
FRONT_MATTER_MAX_CHARS = 400


def _normaliser_pour_comparaison(texte: str) -> str:
    cle = unicodedata.normalize("NFD", texte.lower())
    cle = "".join(c for c in cle if unicodedata.category(c) != "Mn")
    cle = re.sub(r"[^a-z0-9 ]+", " ", cle)
    return re.sub(r"\s+", " ", cle).strip()


def page_est_page_de_titre(texte: str, page_num: int) -> bool:
    """Détecte une page de titre/couverture répétant le titre du document.

    Complémentaire de `page_est_juridique_ou_couverture` : ici il n'y a pas
    forcément de mention légale, juste le titre du guide répété (couverture
    + page de titre intérieure), qui n'apporte rien au RAG.
    """
    if page_num > PAGES_FRONT_MATTER_MAX:
        return False

    if not texte or len(texte.strip()) >= FRONT_MATTER_MAX_CHARS:
        return False

    compact = " " + _normaliser_pour_comparaison(texte) + " "

    hits = sum(1 for mot in TITRE_DOCUMENT_MOTS if mot in compact)

    return hits >= 1


def page_est_juridique_ou_couverture(texte: str, page_num: int = 0) -> bool:
    """Détecte une page de couverture / mentions légales.

    Ces pages contiennent parfois des mots français valides (donc un bon
    score OCR) mais aucun contenu utile pour répondre à des questions de
    cybersécurité. On les repère par densité de motifs juridiques, ou par
    répétition du titre du document sur les toutes premières pages.
    """
    if not texte:
        return False

    if page_est_page_de_titre(texte, page_num):
        return True

    compact = " " + re.sub(r"\s+", " ", texte.lower()) + " "

    hits = sum(
        1 for motif in MOTIFS_PAGE_JURIDIQUE
        if re.search(motif, compact)
    )

    # Deux indices juridiques suffisent (ex: "dépôt légal" + "droits réservés").
    if hits >= 2:
        return True

    # Une seule ligne de contenu qui est un code-barres + peu de texte réel :
    # typiquement le 4e de couverture.
    lignes_utiles = [l for l in texte.splitlines() if l.strip()]
    lignes_code_barre = sum(
        1 for l in lignes_utiles if RE_LIGNE_CODE_BARRE.match(l.strip())
    )

    if lignes_code_barre and len(texte.strip()) < 300 and hits >= 1:
        return True

    return False


# Une page de sommaire (table des matières) est dense en numéros de section
# ("3.3.2", "2.6.6"...) mais quasiment vide de phrases pertinentes. Sans
# filtrage, ce type de page gagne artificiellement au score lexical BM25 :
# beaucoup de mots-clés du document y apparaissent condensés (ex: le mot
# "sauvegarde" dans l'intitulé "3.5.2 Stockage, sauvegarde et restauration
# des données"), ce qui la fait remonter en tête d'une recherche hybride
# sans qu'elle contienne la moindre réponse utile.
RE_NUMERO_SECTION = re.compile(r"\b\d+(?:\.\d+){1,4}\.?\b")
SEUIL_MARQUEURS_SOMMAIRE = 8


def page_est_sommaire(texte: str) -> bool:
    """Détecte une page de sommaire / table des matières."""
    if not texte:
        return False

    lignes = [l.strip() for l in texte.splitlines() if l.strip()]

    if lignes and _normaliser_pour_comparaison(lignes[0]) == "sommaire":
        return True

    nb_marqueurs = len(RE_NUMERO_SECTION.findall(texte))

    return nb_marqueurs >= SEUIL_MARQUEURS_SOMMAIRE


def filtrer_pages_inutiles(
    pages_data: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[int]]:
    """Retire les pages de couverture / mentions légales / sommaire avant le
    chunking.

    Ces pages restent visibles dans les logs (pour audit) mais ne génèrent
    plus de chunks, afin de ne pas polluer les premiers résultats du RAG.
    """
    pages_conservees = []
    pages_exclues = []

    for page in pages_data:
        texte = page.get("text", "")
        page_num = page.get("page_num", 0)

        if page_est_juridique_ou_couverture(texte, page_num) or page_est_sommaire(texte):
            pages_exclues.append(page["page_num"])
            continue

        pages_conservees.append(page)

    if pages_exclues:
        logger.info(
            f"🧹 {len(pages_exclues)} page(s) exclue(s) du chunking "
            f"(couverture / mentions légales / sommaire) : {pages_exclues}"
        )

    return pages_conservees, pages_exclues


# ============================================================================
# NETTOYAGE
# ============================================================================

def nettoyer_texte(texte: str) -> str:
    """Nettoyage conservateur du texte OCR."""
    if not texte:
        return ""

    texte = unicodedata.normalize("NFC", texte)

    # Caractères de contrôle, sauf retour ligne/tabulation.
    texte = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", texte)

    # Tirets OCR en fin de ligne : reconstituer le mot.
    texte = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", texte)

    # Espaces horizontaux.
    texte = re.sub(r"[ \t]+", " ", texte)

    # Lignes vides excessives.
    texte = re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", texte)

    # Supprimer les espaces au début/fin des lignes.
    texte = "\n".join(line.strip() for line in texte.splitlines())

    return texte.strip()


def normaliser_ligne(ligne: str) -> str:
    """Normalise une ligne pour comparer les en-têtes/pieds."""
    ligne = ligne.lower()
    ligne = unicodedata.normalize("NFD", ligne)
    ligne = "".join(c for c in ligne if unicodedata.category(c) != "Mn")
    ligne = re.sub(r"\d+", "#", ligne)
    ligne = re.sub(r"[^a-z0-9# ]+", " ", ligne)
    ligne = re.sub(r"\s+", " ", ligne)
    return ligne.strip()


def nettoyer_artefacts_ocr(texte: str) -> str:
    """Nettoie quelques artefacts typiques sans altérer le contenu."""
    if not texte:
        return ""

    lignes = []

    for line in texte.splitlines():
        line = line.strip()

        if not line:
            lignes.append("")
            continue

        # Ligne constituée presque uniquement de symboles.
        alnum = sum(ch.isalnum() for ch in line)
        non_space = sum(not ch.isspace() for ch in line)

        if non_space >= 8 and alnum / non_space < 0.35:
            continue

        lignes.append(line)

    return nettoyer_texte("\n".join(lignes))


# ============================================================================
# QUALITÉ OCR
# ============================================================================

def score_ocr(texte: str) -> float:
    """Score heuristique 0..1.

    Il ne prétend pas mesurer la précision OCR réelle ; il sert à décider
    si une page mérite un deuxième passage.
    """
    if not texte:
        return 0.0

    compact = re.sub(r"\s+", " ", texte.lower())
    chars = [c for c in compact if not c.isspace()]

    if not chars:
        return 0.0

    lettres = sum(c.isalpha() for c in chars)
    chiffres = sum(c.isdigit() for c in chars)
    alnum = lettres + chiffres

    ratio_alnum = alnum / len(chars)

    mots = re.findall(r"\b[\wÀ-ÿ'-]{2,}\b", compact)

    # Présence de mots fréquents.
    freq_hits = sum(1 for mot in MOTS_FRANCAIS if mot in f" {compact} ")

    # Caractère répété anormalement.
    repeated_penalty = 0.0

    if chars:
        _, count = Counter(chars).most_common(1)[0]
        ratio = count / len(chars)

        if ratio > 0.15:
            repeated_penalty = min(0.5, ratio)

    length_score = min(1.0, len(compact) / 1000.0)
    alpha_score = min(1.0, ratio_alnum / 0.75)
    french_score = min(1.0, freq_hits / 5.0)

    score = (
        0.25 * length_score
        + 0.35 * alpha_score
        + 0.30 * french_score
        + 0.10 * min(1.0, len(mots) / 80.0)
        - repeated_penalty
    )

    return max(0.0, min(1.0, score))


def page_ocr_exploitable(texte: str) -> bool:
    """Détermine si une page OCR contient suffisamment de texte plausible."""
    if not texte or len(texte.strip()) < MIN_PAGE_CHARS:
        return False

    return score_ocr(texte) >= 0.22


# ============================================================================
# TESSERACT
# ============================================================================

def verifier_tesseract() -> bool:
    """Vérifie Tesseract et le modèle français."""
    if not TESSERACT_CMD.exists():
        logger.error(f"Tesseract introuvable : {TESSERACT_CMD}")
        return False

    try:
        env = os.environ.copy()
        env["TESSDATA_PREFIX"] = str(TESSERACT_DIR)

        result = subprocess.run(
            [str(TESSERACT_CMD), "--list-langs"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            cwd=str(TESSERACT_DIR),
            env=env,
            check=False,
        )

        if "fra" not in result.stdout.split():
            logger.error("Le modèle français 'fra' n'est pas disponible.")
            logger.error(f"Langues détectées : {result.stdout}")
            return False

        logger.info("✅ Tesseract disponible avec le français")
        return True

    except Exception as exc:
        logger.error(f"Erreur vérification Tesseract : {exc}")
        return False


def executer_tesseract(image_path: str, psm: str) -> str:
    """Applique Tesseract à une image et retourne le texte."""
    base = tempfile.NamedTemporaryFile(delete=False).name
    txt_path = base + ".txt"

    try:
        env = os.environ.copy()
        env["TESSDATA_PREFIX"] = str(TESSERACT_DIR)

        cmd = [
            str(TESSERACT_CMD),
            image_path,
            base,
            "-l", OCR_LANGUAGE,
            "--oem", OCR_OEM,
            "--psm", psm,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            cwd=str(TESSERACT_DIR),
            env=env,
            check=False,
        )

        if result.returncode != 0:
            logger.warning(f"Tesseract PSM {psm} a échoué : {result.stderr.strip()}")
            return ""

        if not os.path.exists(txt_path):
            return ""

        with open(txt_path, "r", encoding="utf-8", errors="replace") as file:
            return nettoyer_texte(file.read())

    finally:
        for path in (txt_path, base):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass


# ============================================================================
# OCR PDF
# ============================================================================

def ocr_page(page, page_number: int) -> Tuple[str, str, float]:
    """OCR d'une page déjà chargée.

    Retourne : (texte, méthode, score)
    """
    tmp_png = None

    try:
        import fitz

        matrix = fitz.Matrix(OCR_ZOOM, OCR_ZOOM)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_png = tmp.name

        pixmap.save(tmp_png)

        # Premier passage.
        texte_1 = executer_tesseract(tmp_png, OCR_PSM_PRIMARY)
        texte_1 = nettoyer_artefacts_ocr(texte_1)
        score_1 = score_ocr(texte_1)

        # Si le résultat est faible, deuxième stratégie.
        if len(texte_1) < WEAK_PAGE_CHARS or score_1 < 0.30:
            texte_2 = executer_tesseract(tmp_png, OCR_PSM_FALLBACK)
            texte_2 = nettoyer_artefacts_ocr(texte_2)
            score_2 = score_ocr(texte_2)

            if score_2 > score_1 or len(texte_2) > len(texte_1):
                return texte_2, f"ocr_psm_{OCR_PSM_FALLBACK}", score_2

        return texte_1, f"ocr_psm_{OCR_PSM_PRIMARY}", score_1

    except Exception as exc:
        logger.error(f"Erreur OCR page {page_number}: {exc}")
        return "", "ocr_error", 0.0

    finally:
        if tmp_png:
            try:
                if os.path.exists(tmp_png):
                    os.remove(tmp_png)
            except OSError:
                pass


def extraire_texte_ocr(pdf_path: Path) -> List[Dict[str, Any]]:
    """OCR de toutes les pages du PDF avec une seule ouverture du document."""
    try:
        import fitz
    except ImportError:
        logger.error("PyMuPDF n'est pas installé. Installez : pip install pymupdf")
        return []

    pages_data: List[Dict[str, Any]] = []

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        logger.error(f"Impossible d'ouvrir le PDF : {exc}")
        return []

    nb_pages = len(doc)
    logger.info(f"📄 PDF : {nb_pages} pages")

    for page_index in range(nb_pages):
        page_number = page_index + 1
        logger.info(f"🔄 OCR page {page_number}/{nb_pages}...")

        texte, methode, qualite = ocr_page(doc.load_page(page_index), page_number)
        longueur = len(texte)

        if longueur < MIN_PAGE_CHARS:
            logger.warning(
                f"⚠️ Page {page_number}: texte OCR très court "
                f"({longueur} caractères, score={qualite:.2f})"
            )

            # On conserve certaines pages courtes (couverture, sommaire)
            # si elles contiennent quand même du texte lisible.
            if longueur == 0:
                continue

        pages_data.append(
            {
                "page_num": page_number,
                "text": texte,
                "source": "ocr",
                "ocr_method": methode,
                "ocr_score": round(qualite, 4),
            }
        )

        logger.info(
            f"   ✅ Page {page_number}: {longueur} caractères "
            f"| {methode} | qualité={qualite:.2f}"
        )

    doc.close()

    logger.info(f"📊 {len(pages_data)}/{nb_pages} pages avec contenu OCR")

    return pages_data


# ============================================================================
# EN-TÊTES / PIEDS DE PAGE
# ============================================================================

def detecter_lignes_recurrentes(pages_data: List[Dict[str, Any]]) -> set:
    """Détecte les lignes répétées sur plusieurs pages.

    Utile pour supprimer le pied de page du type :
    'Les petites et moyennes entreprises marocaines ...'
    """
    compteur: Counter = Counter()

    for page in pages_data:
        lignes_uniques = set()

        for line in page["text"].splitlines():
            line = line.strip()

            if 10 <= len(line) <= 180:
                normalisee = normaliser_ligne(line)

                if normalisee:
                    lignes_uniques.add(normalisee)

        for line in lignes_uniques:
            compteur[line] += 1

    nb_pages = len(pages_data)

    # Une ligne répétée sur au moins 25% des pages et au minimum 4 fois.
    seuil = max(4, int(nb_pages * 0.25))

    recurrentes = {line for line, count in compteur.items() if count >= seuil}

    logger.info(f"🧹 {len(recurrentes)} lignes récurrentes détectées (seuil={seuil} pages)")

    return recurrentes


def supprimer_lignes_recurrentes(texte: str, recurrentes: set) -> str:
    """Supprime uniquement les lignes détectées comme récurrentes."""
    if not recurrentes:
        return texte

    lignes = []

    for line in texte.splitlines():
        normalisee = normaliser_ligne(line)

        if normalisee and normalisee in recurrentes:
            continue

        lignes.append(line)

    return nettoyer_texte("\n".join(lignes))


# ============================================================================
# TITRES
# ============================================================================

# Titres connus qui n'ont pas de forme numérotée ni MAJUSCULE fiable dans
# ce document, mais reviennent régulièrement dans ce type de guide.
TITRES_CONNUS = {
    "preambule", "introduction", "sommaire", "glossaire", "conclusion",
    "annexe", "annexes", "avant-propos", "bibliographie", "references",
    "presentation de l'ausim", "presentation du cmrpi",
}


def _cle_titre_connu(ligne: str) -> str:
    cle = unicodedata.normalize("NFD", ligne.lower())
    cle = "".join(c for c in cle if unicodedata.category(c) != "Mn")
    cle = re.sub(r"[^a-z0-9' ]+", "", cle).strip()
    return cle


def ligne_est_titre(ligne: str) -> bool:
    """Détection prudente d'un titre.

    Version resserrée : l'ancienne heuristique "ligne courte sans article"
    générait trop de faux positifs sur des fragments de listes à puces
    OCRisées (ex: "travaux", "a contribution au développement du Maroc").
    Elle est retirée. Seules 3 formes fiables sont retenues :
      1. Une section numérotée ("3.2.1 Sécurité des données").
      2. Une ligne très majoritairement en MAJUSCULES, assez longue pour
         ne pas être un sigle ou un artefact OCR isolé.
      3. Un titre connu du guide (préambule, sommaire, glossaire, etc.).
    """
    ligne = ligne.strip()

    if len(ligne) < 5 or len(ligne) > 120:
        return False

    mots = ligne.split()

    if len(mots) > 12:
        return False

    if ligne.endswith((".", ",", ";", ":", "?", "!")):
        return False

    lettres = [c for c in ligne if c.isalpha()]

    if len(lettres) < 5:
        return False

    # 1. Titre numéroté : "3.2.1 Sécurité des données".
    if re.match(r"^\d+(?:\.\d+)*\.?\s+\S+", ligne):
        return True

    # 2. Titre en MAJUSCULES — seuil de longueur relevé pour éviter les
    #    sigles OCR isolés (ex: "SI", "PME" seuls sur une ligne).
    if len(lettres) >= 10:
        upper_ratio = sum(c.isupper() for c in lettres) / len(lettres)

        if upper_ratio >= 0.85:
            return True

    # 3. Titre connu du guide (liste fermée, pas d'heuristique floue).
    if _cle_titre_connu(ligne) in TITRES_CONNUS:
        return True

    return False


def detecter_titres_ocr(texte: str) -> List[str]:
    """Retourne les lignes plausibles comme titres."""
    return [line.strip() for line in texte.splitlines() if ligne_est_titre(line.strip())]


# ============================================================================
# CHUNKING
# ============================================================================

# Terminateurs de phrase / d'item de liste utilisés pour éviter de fabriquer
# une "phrase" unique de plusieurs milliers de caractères à partir d'une
# liste à puces sans ponctuation forte (fréquent dans ce guide : "« item »").
RE_SEPARATEUR_PHRASE = re.compile(r"(?<=[.!?;:])\s+")


def decouper_long_texte(texte: str, chunk_size: int, overlap: int) -> List[str]:
    """Découpe un texte long SANS jamais couper un mot en deux.

    Stratégie en cascade, du plus fiable au filet de sécurité :
      1. Découpe par ligne d'origine (une ligne = souvent un item de liste
         ou une phrase dans ce document OCRisé). C'est la correction
         principale : l'ancienne version aplatissait tout le texte en une
         seule ligne AVANT de découper, ce qui transformait les listes à
         puces en une phrase géante coupée ensuite par index de caractère.
      2. Si une ligne dépasse encore chunk_size, découpe par phrase/segment
         (sur . ! ? ; :).
      3. En dernier recours (segment toujours trop long : URL, mot composé
         OCR anormalement long...), découpe sur le dernier espace avant la
         limite — jamais au milieu d'un mot.
    """
    texte = texte.strip()

    if not texte:
        return []

    # Ne normaliser que les espaces horizontaux : on garde les retours
    # ligne, qui portent l'information de structure (items de liste).
    texte_norm = re.sub(r"[ \t]+", " ", texte)

    unites: List[str] = []

    for ligne in texte_norm.splitlines():
        ligne = ligne.strip()

        if not ligne:
            continue

        if len(ligne) <= chunk_size:
            unites.append(ligne)
            continue

        for segment in RE_SEPARATEUR_PHRASE.split(ligne):
            segment = segment.strip()

            if segment:
                unites.append(segment)

    if not unites:
        return []

    chunks: List[str] = []
    current = ""

    def _couper_sur_mot(segment: str) -> List[str]:
        """Filet de sécurité : découpe un segment trop long sur des espaces."""
        morceaux = []
        start = 0
        n = len(segment)

        while start < n:
            end = min(start + chunk_size, n)

            if end < n:
                espace = segment.rfind(" ", start, end)

                if espace > start:
                    end = espace

            morceau = segment[start:end].strip()

            if morceau:
                morceaux.append(morceau)

            if end >= n:
                break

            nouveau_start = max(start + 1, end - overlap)
            # Ne jamais redémarrer au milieu d'un mot : avancer jusqu'au
            # prochain espace si nécessaire.
            espace_suivant = segment.find(" ", nouveau_start)

            if 0 <= espace_suivant < end:
                nouveau_start = espace_suivant + 1

            start = nouveau_start

        return morceaux

    for unite in unites:
        if len(unite) > chunk_size:
            if current:
                chunks.append(current.strip())
                current = ""

            chunks.extend(_couper_sur_mot(unite))
            continue

        if not current:
            current = unite
            continue

        candidat = f"{current} {unite}"

        if len(candidat) <= chunk_size:
            current = candidat
            continue

        chunks.append(current.strip())

        overlap_text = current[-overlap:].strip() if overlap > 0 else ""

        # Ne jamais démarrer le chunk suivant au milieu d'un mot : si la
        # fenêtre d'overlap commence en plein mot, on saute au prochain
        # espace.
        if overlap_text and " " in overlap_text:
            overlap_text = overlap_text[overlap_text.index(" ") + 1:]
        elif overlap_text:
            overlap_text = ""

        current = f"{overlap_text} {unite}".strip() if overlap_text else unite

    if current.strip():
        chunks.append(current.strip())

    return chunks


def construire_chunks(
    pages_data: List[Dict[str, Any]],
    recurrentes: set,
) -> List[Dict[str, Any]]:
    """Construit les chunks finaux.

    Les titres restent des métadonnées ; on n'injecte pas de faux titres
    générés par l'OCR comme documents séparés.
    """
    chunks: List[Dict[str, Any]] = []
    chunk_index = 0
    titre_courant = ""
    niveau_courant = ""

    for page_data in pages_data:
        page_num = page_data["page_num"]
        source = page_data.get("source", "ocr")

        texte = supprimer_lignes_recurrentes(page_data.get("text", ""), recurrentes)
        texte = nettoyer_texte(texte)

        if len(texte) < MIN_CHUNK_CHARS:
            continue

        lignes = texte.splitlines()

        # Conserver les paragraphes, sans perdre les titres.
        blocs: List[str] = []
        bloc_courant: List[str] = []

        for line in lignes:
            line = line.strip()

            if not line:
                if bloc_courant:
                    blocs.append("\n".join(bloc_courant))
                    bloc_courant = []
                continue

            if ligne_est_titre(line):
                if bloc_courant:
                    blocs.append("\n".join(bloc_courant))
                    bloc_courant = []

                blocs.append(f"__TITLE__{line}")
            else:
                bloc_courant.append(line)

        if bloc_courant:
            blocs.append("\n".join(bloc_courant))

        current_text = ""

        def ajouter_chunk(texte_chunk: str) -> None:
            nonlocal chunk_index

            texte_chunk = re.sub(r"\s+", " ", texte_chunk).strip()

            if len(texte_chunk) < MIN_CHUNK_CHARS:
                return

            chunks.append(
                {
                    "text": texte_chunk,
                    "page_num": int(page_num),
                    "chunk_index": int(chunk_index),
                    "source": source,
                    "type": "paragraph",
                    "titre": titre_courant,
                    "niveau": niveau_courant,
                    "source_name": "Guide CMRPI",
                    "ocr_method": page_data.get("ocr_method", "ocr"),
                    "ocr_score": float(page_data.get("ocr_score", 0.0)),
                }
            )

            chunk_index += 1

        for bloc in blocs:
            if bloc.startswith("__TITLE__"):
                # Le titre devient le contexte des chunks suivants.
                titre = bloc.replace("__TITLE__", "", 1).strip()

                if titre:
                    titre_courant = titre
                    niveau_courant = (
                        "h1"
                        if re.match(r"^\d+\.\s+", titre) or titre.isupper()
                        else "h2"
                    )

                continue

            bloc = bloc.strip()

            if not bloc:
                continue

            if not current_text:
                current_text = bloc
                continue

            candidat = f"{current_text} {bloc}"

            if len(candidat) <= CHUNK_SIZE:
                current_text = candidat
                continue

            ajouter_chunk(current_text)

            overlap_text = current_text[-CHUNK_OVERLAP:].strip() if CHUNK_OVERLAP > 0 else ""

            if overlap_text and " " in overlap_text:
                overlap_text = overlap_text[overlap_text.index(" ") + 1:]
            elif overlap_text:
                overlap_text = ""

            current_text = f"{overlap_text} {bloc}".strip() if overlap_text else bloc

            # Si le nouveau bloc (potentiellement une longue liste à puces)
            # est encore trop long, le découper proprement mot par mot.
            if len(current_text) > CHUNK_SIZE:
                morceaux = decouper_long_texte(current_text, CHUNK_SIZE, CHUNK_OVERLAP)
                current_text = ""

                for morceau in morceaux[:-1]:
                    ajouter_chunk(morceau)

                if morceaux:
                    current_text = morceaux[-1]

        ajouter_chunk(current_text)
        current_text = ""

    logger.info(f"📦 {len(chunks)} chunks créés")

    return chunks


# ============================================================================
# CHROMADB
# ============================================================================

def creer_collection_chroma(client, embedding_fn):
    """Supprime puis recrée la collection CMRPI."""
    try:
        noms = {c.name for c in client.list_collections()}

        if COLLECTION_NAME in noms:
            logger.info(f"🗑️ Suppression de '{COLLECTION_NAME}'")
            client.delete_collection(COLLECTION_NAME)

    except Exception as exc:
        logger.warning(f"Erreur suppression collection : {exc}")

    return client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={
            "description": "Guide CMRPI - Bonnes pratiques de cybersécurité pour PME",
            "embedding_model": EMBEDDING_MODEL,
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
            "extraction": "Tesseract OCR français",
        },
    )


def creer_embedding_function():
    """Crée la fonction d'embedding BAAI/bge-m3."""
    logger.info(f"🧠 Chargement embeddings : {EMBEDDING_MODEL}")

    return embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)


# ============================================================================
# RAPPORT QUALITÉ
# ============================================================================

def afficher_qualite_ocr(pages_data: List[Dict[str, Any]]) -> None:
    """Affiche un résumé simple de la qualité OCR."""
    if not pages_data:
        return

    scores = [p["ocr_score"] for p in pages_data]

    faibles = [
        p for p in pages_data
        if (p["ocr_score"] < 0.25 or len(p["text"]) < WEAK_PAGE_CHARS)
    ]

    total_chars = sum(len(p["text"]) for p in pages_data)

    logger.info("📊 QUALITÉ OCR")
    logger.info(f"   Pages analysées : {len(pages_data)}")
    logger.info(f"   Caractères totaux : {total_chars}")
    logger.info(f"   Score moyen : {sum(scores) / len(scores):.2f}")
    logger.info(f"   Pages potentiellement faibles : {len(faibles)}")

    if faibles:
        pages = ", ".join(str(p["page_num"]) for p in faibles[:20])
        logger.info(f"   Pages à contrôler : {pages}")


def afficher_apercu(pages_data: List[Dict[str, Any]], nombre_pages: int = 3) -> None:
    """Affiche un aperçu du texte OCR."""
    print("\n" + "=" * 80)
    print("APERÇU DU TEXTE OCR")
    print("=" * 80)

    for page_data in pages_data[:nombre_pages]:
        print(
            f"\n--- PAGE {page_data['page_num']} "
            f"| {page_data.get('ocr_method', 'ocr')} "
            f"| score={page_data.get('ocr_score', 0):.2f} ---"
        )
        print(page_data["text"][:1800])

    print("\n" + "=" * 80)


# ============================================================================
# INGESTION
# ============================================================================

def ingerer_cmrpi() -> bool:
    """Pipeline complet d'ingestion."""
    if not PDF_PATH.exists():
        logger.error(f"❌ PDF non trouvé : {PDF_PATH}")
        return False

    if not verifier_tesseract():
        return False

    logger.info(f"📄 Lecture OCR du PDF : {PDF_PATH}")

    # 1. OCR.
    pages_data = extraire_texte_ocr(PDF_PATH)

    if not pages_data:
        logger.error("❌ Aucun texte OCR extrait.")
        return False

    afficher_qualite_ocr(pages_data)

    total_chars = sum(len(p["text"]) for p in pages_data)
    logger.info(f"📝 {total_chars} caractères extraits")

    # 2. Détection des lignes récurrentes (sur TOUTES les pages, y compris
    #    celles qui seront ensuite exclues, pour ne pas fausser le seuil).
    recurrentes = detecter_lignes_recurrentes(pages_data)

    # 3. Filtrage des pages inutiles (couverture, mentions légales).
    pages_data, pages_exclues = filtrer_pages_inutiles(pages_data)

    if not pages_data:
        logger.error("❌ Toutes les pages ont été filtrées, rien à ingérer.")
        return False

    # 4. Aperçu après OCR + filtrage.
    afficher_apercu(pages_data, nombre_pages=3)

    # 5. Chunking.
    chunks = construire_chunks(pages_data, recurrentes)

    if not chunks:
        logger.error("❌ Aucun chunk créé.")
        return False

    # 6. ChromaDB.
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    logger.info("💾 Initialisation ChromaDB...")

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    embedding_fn = creer_embedding_function()
    collection = creer_collection_chroma(client, embedding_fn)

    # 7. Ingestion par batch.
    logger.info(f"📤 Ingestion de {len(chunks)} chunks...")

    total_added = 0
    batch_errors = 0

    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        batch_number = i // BATCH_SIZE + 1

        documents = [c["text"] for c in batch]
        ids = [f"cmrpi_chunk_{c['chunk_index']}" for c in batch]

        metadatas = [
            {
                "source": "CMRPI",
                "source_name": c["source_name"],
                "page": int(c["page_num"]),
                "chunk_index": int(c["chunk_index"]),
                "type": c["type"],
                "source_type": c["source"],
                "titre": c["titre"],
                "niveau": c["niveau"],
                "ocr_method": c["ocr_method"],
                "ocr_score": float(c["ocr_score"]),
            }
            for c in batch
        ]

        try:
            collection.add(documents=documents, ids=ids, metadatas=metadatas)
            total_added += len(batch)

            logger.info(
                f"   Batch {batch_number}: {len(batch)} ajoutés "
                f"({total_added}/{len(chunks)})"
            )

        except Exception as exc:
            batch_errors += 1
            logger.error(f"❌ Erreur batch {batch_number}: {exc}")

    # 8. Vérification stricte.
    count = collection.count()

    logger.info(f"✅ {count} documents présents dans ChromaDB")
    logger.info(f"📁 Base : {CHROMA_PATH}")

    if batch_errors > 0:
        logger.error(f"❌ {batch_errors} batch(s) ont échoué.")
        return False

    if count != len(chunks):
        logger.error(
            f"❌ Incohérence : {count} dans ChromaDB contre {len(chunks)} chunks attendus."
        )
        return False

    # 9. Échantillon.
    try:
        sample = collection.get(limit=min(5, count), include=["documents", "metadatas"])

        print("\n" + "=" * 80)
        print("VÉRIFICATION CHROMADB")
        print("=" * 80)

        documents = sample.get("documents", []) or []
        metadatas = sample.get("metadatas", []) or []

        for index, document in enumerate(documents):
            meta = metadatas[index] if index < len(metadatas) else {}

            print(f"\n--- DOCUMENT {index + 1} ---")
            print(f"Page       : {meta.get('page', '?')}")
            print(f"Type       : {meta.get('type', '?')}")
            print(f"Titre      : {meta.get('titre', '')[:100]}")
            print(f"OCR        : {meta.get('ocr_method', '?')}")
            print(f"Score OCR  : {meta.get('ocr_score', '?')}")
            print(f"\n{document[:700]}")

        print("\n" + "=" * 80)

    except Exception as exc:
        logger.warning(f"Erreur échantillon ChromaDB : {exc}")

    return True


# ============================================================================
# RECHERCHE HYBRIDE (BM25 lexical + vectoriel, fusion par "sauvetage")
# ============================================================================
#
# Pourquoi hybride : sur "Comment sauvegarder et protéger les données d'une
# PME ?", la recherche vectorielle seule renvoyait des pages générales sur
# la "protection des données" (16, 17, 5, 8) au lieu des pages contenant
# littéralement "sauvegarder" / "sauvegardes" (39, 48). L'embedding bge-m3
# capture le thème général mais dilue le terme précis dans le voisinage
# sémantique plus large "sécurité/protection". BM25, score purement lexical,
# retrouve directement les chunks contenant le mot exact.
#
# Trois versions testées avant celle-ci, chacune corrigeant un défaut de
# la précédente :
#   1. BM25 brut : "sauvegarder" (requête) ne matche pas "sauvegardes"
#      (texte) — tokens différents. -> racinisation naïve (troncature à
#      6 caractères) pour absorber pluriels/conjugaisons.
#   2. Fusion par rang (RRF) : favorise le CONSENSUS entre les deux
#      classements, donc continuait à privilégier p16/p17 (présents dans
#      les deux) plutôt que p39/p48 (absents du vectoriel, donc sans
#      contribution RRF). -> remplacée par un score normalisé pondéré.
#   3. Fusion par score pondéré (alpha=0.4, tout mélanger) : testée en
#      conditions réelles, elle a DÉGRADÉ le benchmark global (Recall@5
#      77,8%→72,2%, MRR 0,75→0,68), car elle perturbait aussi les
#      requêtes déjà correctes en vectoriel pur, et a même fait remonter
#      un chunk de sommaire/table des matières (page 7, dense en
#      numéros de section donc artificiellement fort en BM25) au rang 1
#      pour la question sauvegarde. -> remplacée par une fusion de
#      "sauvetage" : le classement vectoriel reste la référence ; le
#      lexical n'intervient que pour insérer un match dont le score
#      BM25 est un outlier statistique (z-score élevé sur l'ensemble du
#      corpus) et absent du top vectoriel — un signal de terme exact
#      rare et fort, pas un simple chevauchement de vocabulaire courant.
#      Les requêtes où le vectoriel est déjà bon ne sont donc jamais
#      perturbées (aucun outlier lexical à sauver).
#
# En complément, les pages de sommaire (table des matières, très denses en
# numéros de section) sont désormais exclues du corpus (voir
# `page_est_sommaire`), pour éviter qu'elles ne gagnent artificiellement au
# score lexical sans apporter de réponse utile.

RE_TOKEN = re.compile(r"[a-zà-ÿ0-9]+")

STOPWORDS_FR = {
    "le", "la", "les", "de", "des", "du", "un", "une", "et", "est", "pour",
    "dans", "que", "qui", "sur", "avec", "ce", "ces", "cet", "cette", "son",
    "sa", "ses", "sont", "par", "au", "aux", "pas", "en", "il", "elle",
    "ils", "elles", "on", "se", "leur", "leurs", "ne", "plus", "ou", "mais",
    "donc", "or", "ni", "car", "à", "d", "l", "qu", "s", "n", "être",
    "avoir", "comment", "quelles", "quels", "quelle", "quel",
    # Adjectifs génériques (taille/qualité). Vu sur le run réel : "petite"
    # déclenchait un sauvetage à tort (z=4.61) — non pas parce que c'est un
    # terme spécifique, mais parce que le guide dit "PME" plutôt que
    # "petite entreprise", le rendant artificiellement rare dans le corpus.
    # L'IDF confondait "peu fréquent dans CE corpus" avec "spécifique au
    # sujet de la question" — deux choses différentes pour un adjectif
    # générique.
    "petit", "petite", "petits", "petites", "grand", "grande", "grands",
    "grandes", "bon", "bonne", "bons", "bonnes", "simple", "simples",
    "mon", "ma", "mes", "votre", "vos",
}

# Longueur de troncature pour la racinisation naïve. "sauvegarder",
# "sauvegardes", "sauvegardé" partagent tous le préfixe "sauveg".
LONGUEUR_RACINE = 6

# Longueur minimale d'un token pour être retenu. Relevée de 1 à 3 après le
# run réel : "Wi-Fi" éclatait sur le tiret en deux fragments "wi" + "fi",
# et "fi" (2 caractères) déclenchait un sauvetage par pur hasard (z=8.04) —
# un token aussi court n'est jamais un signal fiable, quelle que soit sa
# rareté statistique.
LONGUEUR_MIN_TOKEN = 3

# Un score BM25 élevé ne suffit plus à lui seul : le run réel (317 chunks)
# a montré qu'un chunk "hub" — dense en vocabulaire du domaine sans être
# spécifique à aucune question précise (ex: la préface, qui mentionne
# "sécurité", "entreprise", "cybersécurité", "sauvegarder" en un seul
# paragraphe résumant tout le guide) — devenait un outlier statistique
# pour de nombreuses requêtes différentes, se faisant "sauver" à tort et
# reléguant des réponses déjà correctes du rang 1 au rang 3 (MRR
# 0,750 → 0,583 sur le run réel, alors que le Recall ne gagnait que
# +2,78 points). Un score global élevé peut venir de la SOMME de
# plusieurs termes courants du domaine, pas d'un terme réellement rare.
#
# Un sauvetage n'est donc plus validé uniquement par son z-score : il doit
# EN PLUS contenir au moins un terme de la requête suffisamment rare dans
# le corpus (IDF proche du maximum) — un vrai signal de correspondance
# lexicale exacte et spécifique, pas un cumul de mots-clés génériques.

# z-score minimal pour qu'un score BM25 soit considéré comme un outlier.
# Relevé de 1.5 à 3.0 après le run réel : sur un corpus de 300+ chunks, le
# calibrage fait sur un corpus jouet de 13 documents ne se généralisait
# pas (trop permissif en conditions réelles).
SEUIL_Z_SCORE_SAUVETAGE = 3.0

# Un token de la requête est jugé "spécifique" (donc digne de déclencher un
# sauvetage) si son IDF atteint au moins cette fraction de l'IDF maximum
# observé dans le corpus — càd un terme parmi les plus rares du corpus,
# pas un mot du domaine qui revient dans la moitié des chunks.
SEUIL_RATIO_IDF_SPECIFIQUE = 0.75

# Nombre maximum de documents lexicaux insérés en tête du classement
# vectoriel. Réduit de 2 à 1 : on ne veut corriger que le raté le plus
# franc du vectoriel, pas réordonner plusieurs positions.
NB_SAUVETAGES_MAX = 1


def racine(mot: str, longueur: int = LONGUEUR_RACINE) -> str:
    """Racinisation naïve par troncature (pas de vraie lemmatisation FR)."""
    return mot[:longueur] if len(mot) > longueur else mot


def tokeniser(texte: str) -> List[str]:
    """Tokenisation pour BM25 : minuscules, sans accents, mots composés à
    trait d'union fusionnés ("Wi-Fi" -> "wifi", "anti-virus" -> "antivirus"
    — cohérent avec les variantes sans tiret déjà présentes dans le guide),
    sans stopwords, racinisé.
    """
    texte = unicodedata.normalize("NFD", texte.lower())
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    texte = texte.replace("-", "")
    mots = RE_TOKEN.findall(texte)
    return [
        racine(m) for m in mots
        if len(m) >= LONGUEUR_MIN_TOKEN and m not in STOPWORDS_FR
    ]


def charger_corpus(collection) -> Dict[str, List[Any]]:
    """Charge tout le corpus (ids, textes, métadonnées, tokens) pour l'index lexical."""
    donnees = collection.get(include=["documents", "metadatas"])
    documents = donnees.get("documents", [])

    return {
        "ids": donnees.get("ids", []),
        "documents": documents,
        "metadatas": donnees.get("metadatas", []),
        # Tokens pré-calculés une fois : réutilisés pour vérifier qu'un
        # sauvetage partage bien un terme spécifique avec la requête,
        # sans re-tokeniser tout le corpus à chaque recherche.
        "tokens": [set(tokeniser(doc)) for doc in documents],
    }


def construire_index_bm25(corpus: Dict[str, List[Any]]):
    """Construit un index BM25 sur l'ensemble du corpus (une fois par run)."""
    if not BM25_DISPONIBLE:
        return None

    corpus_tokenise = [tokeniser(doc) for doc in corpus["documents"]]

    return BM25Okapi(corpus_tokenise)


def tokens_specifiques_de_la_requete(
    tokens_requete: List[str],
    bm25,
    seuil_ratio: float = SEUIL_RATIO_IDF_SPECIFIQUE,
) -> set:
    """Termes de la requête assez rares dans le corpus pour signaler une
    correspondance lexicale exacte fiable (par opposition aux mots du
    domaine — "sécurité", "entreprise" — présents dans la moitié des chunks).
    """
    idfs = getattr(bm25, "idf", None)

    if not idfs:
        return set()

    idf_max = max(idfs.values())

    if idf_max <= 0:
        return set()

    seuil = idf_max * seuil_ratio

    return {t for t in tokens_requete if idfs.get(t, 0.0) >= seuil}


def trouver_sauvetages_lexicaux(
    ids: List[str],
    scores_bm25_corpus: List[float],
    corpus_tokens: List[set],
    tokens_specifiques: set,
    ids_deja_presents: set,
    seuil_z: float = SEUIL_Z_SCORE_SAUVETAGE,
    nb_max: int = NB_SAUVETAGES_MAX,
) -> List[Dict[str, Any]]:
    """Identifie les documents dont le score BM25 est un outlier statistique
    ET qui contiennent au moins un terme spécifique (rare) de la requête.

    Retourne une liste de diagnostics {doc_id, z, terme} pour traçabilité —
    y compris dans les logs, pour calibrer le seuil sur de vraies données
    plutôt que sur un corpus jouet.
    """
    if not scores_bm25_corpus or not tokens_specifiques:
        return []

    moyenne = statistics.mean(scores_bm25_corpus)
    ecart_type = statistics.pstdev(scores_bm25_corpus)

    if ecart_type < 1e-9:
        return []

    candidats = sorted(
        range(len(ids)),
        key=lambda i: scores_bm25_corpus[i],
        reverse=True,
    )

    sauvetages: List[Dict[str, Any]] = []

    for i in candidats:
        doc_id = ids[i]

        if doc_id in ids_deja_presents:
            continue

        z = (scores_bm25_corpus[i] - moyenne) / ecart_type

        if z < seuil_z:
            break  # candidats triés par score décroissant : plus rien à sauver

        termes_partages = tokens_specifiques & corpus_tokens[i]

        if not termes_partages:
            # Score élevé mais aucun terme rare partagé : probablement un
            # "hub" générique (cumul de mots-clés courants), pas un match
            # lexical exact. On l'ignore et on continue d'examiner les
            # candidats suivants (moins bien scorés mais peut-être plus
            # spécifiques).
            continue

        sauvetages.append({"id": doc_id, "z": z, "terme": sorted(termes_partages)[0]})

        if len(sauvetages) >= nb_max:
            break

    return sauvetages


# ============================================================================
# EXPANSION DE REQUÊTE (ciblée, pas statistique)
# ============================================================================
#
# Pour "Comment sauvegarder et protéger les données d'une PME ?", ni le
# vectoriel ni le sauvetage lexical (même avec z-score + spécificité IDF)
# ne parviennent à isoler les pages 39/48 : "sauvegarder" est trop répandu
# dans le corpus (pages 4, 5, 39, 48...) pour être un outlier statistique,
# et l'embedding bge-m3 le noie dans son voisinage sémantique général
# "sécurité/protection des données". Plutôt que de continuer à chercher un
# seuil statistique universel — chassé sur plusieurs itérations sans
# résultat concluant pour CE cas précis — le problème est ciblé
# directement : quelques familles de termes où la formulation de la
# requête et celle du texte source divergent assez pour tromper
# l'embedding sont explicitées manuellement.
#
# Volontairement restreint à une poignée d'entrées connues plutôt qu'un
# thésaurus général : chaque entrée doit être justifiée par un cas observé
# sur le benchmark, pas ajoutée de façon préventive. N'affecte QUE le texte
# envoyé à l'embedding pour la recherche vectorielle — la requête telle que
# tapée par l'utilisateur, le score lexical BM25 (déjà couvert par la
# racinisation) et l'affichage ne changent pas.
EXPANSIONS_REQUETE: Dict[str, str] = {
    "sauvegarder": "sauvegarde sauvegardes restauration stockage",
    "sauvegarde": "sauvegarder sauvegardes restauration stockage",
}


def etendre_requete(query: str) -> str:
    """Ajoute des termes de renfort à la requête vectorielle si un mot
    déclencheur connu y figure. Retourne la requête inchangée sinon.
    """
    mots = re.findall(r"[a-zà-ÿ]+", query.lower())
    ajouts: List[str] = []

    for mot in mots:
        mot_normalise = unicodedata.normalize("NFD", mot)
        mot_normalise = "".join(c for c in mot_normalise if unicodedata.category(c) != "Mn")

        if mot_normalise in EXPANSIONS_REQUETE and mot_normalise not in ajouts:
            ajouts.append(EXPANSIONS_REQUETE[mot_normalise])

    if not ajouts:
        return query

    return query + " " + " ".join(ajouts)


def rechercher(
    query: str,
    collection,
    corpus: Dict[str, List[Any]],
    bm25,
    k: int = 5,
    k_candidats: int = 20,
    methode: str = "hybride",
    diagnostics: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Recherche vectorielle, lexicale (BM25) ou hybride (vectoriel + sauvetage lexical).

    methode : "vectoriel" | "lexical" | "hybride"
    Si `diagnostics` est fourni (liste), les sauvetages effectués y sont
    ajoutés (doc_id, page, z-score, terme déclencheur) pour audit/calibrage.
    """
    ids = corpus["ids"]
    documents = corpus["documents"]
    metadatas = corpus["metadatas"]
    id_vers_index = {doc_id: i for i, doc_id in enumerate(ids)}

    classement_vectoriel: List[str] = []
    distances_par_id: Dict[str, float] = {}

    if methode in ("vectoriel", "hybride"):
        n_vector = min(k_candidats, len(ids)) or 1

        resultats = collection.query(
            query_texts=[etendre_requete(query)],
            n_results=n_vector,
            include=["distances"],
        )

        classement_vectoriel = resultats.get("ids", [[]])[0]

        for doc_id, dist in zip(classement_vectoriel, resultats.get("distances", [[]])[0]):
            distances_par_id[doc_id] = dist

    if methode == "vectoriel" or bm25 is None:
        classement_final = classement_vectoriel

    elif methode == "lexical":
        scores_bm25 = bm25.get_scores(tokeniser(query))
        ordre = sorted(range(len(ids)), key=lambda i: scores_bm25[i], reverse=True)
        classement_final = [ids[i] for i in ordre[:k_candidats]]

    else:  # hybride
        tokens_requete = tokeniser(query)
        scores_bm25 = bm25.get_scores(tokens_requete)
        tokens_specifiques = tokens_specifiques_de_la_requete(tokens_requete, bm25)

        sauvetages = trouver_sauvetages_lexicaux(
            ids,
            list(scores_bm25),
            corpus.get("tokens", [set()] * len(ids)),
            tokens_specifiques,
            set(classement_vectoriel[:k]),
        )

        ids_sauves = [s["id"] for s in sauvetages]

        if diagnostics is not None:
            for s in sauvetages:
                idx = id_vers_index.get(s["id"])
                page = metadatas[idx].get("page") if idx is not None else "?"
                diagnostics.append({**s, "page": page})

        # Les sauvetages passent devant, le reste du classement vectoriel suit.
        classement_final = ids_sauves + [
            d for d in classement_vectoriel if d not in ids_sauves
        ]

    resultats_formates = []

    for doc_id in classement_final[:k]:
        idx = id_vers_index.get(doc_id)

        if idx is None:
            continue

        resultats_formates.append(
            {
                "id": doc_id,
                "document": documents[idx],
                "metadata": metadatas[idx],
                "distance": distances_par_id.get(doc_id),
            }
        )

    return resultats_formates


# ============================================================================
# TEST RAG + BENCHMARK (Precision@k / Recall@k / MRR)
# ============================================================================

def tester_rag(
    query: str,
    collection,
    corpus: Dict[str, List[Any]],
    bm25,
    n_results: int = 5,
    methode: str = "hybride",
) -> None:
    """Affiche les résultats bruts d'une recherche (vectorielle/lexicale/hybride)."""
    print("\n" + "=" * 80)
    print(f"TEST RECHERCHE RAG [{methode}]")
    print("=" * 80)
    print(f"Question : {query}")

    resultats = rechercher(query, collection, corpus, bm25, k=n_results, methode=methode)

    if not resultats:
        print("❌ Aucun résultat.")
        return

    for i, r in enumerate(resultats, 1):
        meta = r["metadata"]

        print("\n" + "-" * 75)
        print(f"Résultat {i}")
        print(f"Page     : {meta.get('page', '?')}")
        print(f"Titre    : {meta.get('titre', '')}")
        print(f"Type     : {meta.get('type', '?')}")

        if r["distance"] is not None:
            print(f"Distance : {r['distance']:.4f}")

        print(f"\n{r['document'][:1000]}")


# Jeu de questions avec page(s) de référence attendue(s), pour un vrai
# benchmark de récupération plutôt qu'une simple inspection visuelle.
# Format : (question, {pages attendues (une correspondance suffit)})
QUESTIONS_BENCHMARK: List[Tuple[str, set]] = [
    ("Comment protéger ma petite entreprise ?", {8}),
    ("Quelles sont les bonnes pratiques pour les mots de passe ?", {38, 17, 48}),
    ("Comment sauvegarder et protéger les données d'une PME ?", {39, 48}),
    ("Comment sensibiliser les employés à la cybersécurité ?", {11, 17}),
    ("Quelles mesures prendre contre les virus et les logiciels malveillants ?", {34, 28}),
    ("Comment sécuriser le Wi-Fi de mon entreprise ?", {31}),
]


def precision_a_k(pages_trouvees: List[int], pages_attendues: set, k: int) -> float:
    """Fraction des k résultats retournés qui sont pertinents."""
    top_k = pages_trouvees[:k]

    if not top_k:
        return 0.0

    pertinents = sum(1 for p in top_k if p in pages_attendues)

    return pertinents / len(top_k)


def rappel_a_k(pages_trouvees: List[int], pages_attendues: set, k: int) -> float:
    """Fraction des pages pertinentes attendues effectivement retrouvées dans le top-k."""
    if not pages_attendues:
        return 0.0

    trouvees = set(pages_trouvees[:k]) & pages_attendues

    return len(trouvees) / len(pages_attendues)


def rang_reciproque(pages_trouvees: List[int], pages_attendues: set) -> float:
    """1 / rang du premier résultat pertinent, 0 si aucun."""
    for i, p in enumerate(pages_trouvees, start=1):
        if p in pages_attendues:
            return 1.0 / i

    return 0.0


def evaluer_recuperation(
    questions: Optional[List[Tuple[str, set]]] = None,
    k: int = 5,
) -> None:
    """Compare recherche vectorielle seule vs hybride (vectoriel + sauvetage
    lexical BM25 sous condition de spécificité IDF) sur Precision@k,
    Recall@k, MRR et Hit-rate@k — question par question, puis en moyenne
    globale (macro-average) sur tout le jeu de questions.
    """
    questions = questions or QUESTIONS_BENCHMARK

    print("\n" + "=" * 80)
    print(f"BENCHMARK RAG — vectoriel vs hybride — k={k}")
    print("=" * 80)

    try:
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        embedding_fn = creer_embedding_function()
        collection = client.get_collection(name=COLLECTION_NAME, embedding_function=embedding_fn)
        count = collection.count()

    except Exception as exc:
        print(f"❌ Impossible de charger la collection : {exc}")
        return

    if count == 0:
        print("❌ Collection vide.")
        return

    corpus = charger_corpus(collection)
    bm25 = construire_index_bm25(corpus)

    if bm25 is None:
        print(
            "⚠️ 'rank_bm25' n'est pas installé (pip install rank_bm25) : "
            "seule la recherche vectorielle sera évaluée.\n"
        )
        methodes = ["vectoriel"]
    else:
        methodes = ["vectoriel", "hybride"]

    resultats_par_methode: Dict[str, List[Dict[str, float]]] = {m: [] for m in methodes}

    for question, pages_attendues in questions:
        print(f"\nQ: {question}")
        print(f"   Pages attendues : {sorted(pages_attendues)}")

        for methode in methodes:
            diagnostics: List[Dict[str, Any]] = [] if methode == "hybride" else None  # type: ignore[assignment]

            resultats = rechercher(
                question, collection, corpus, bm25, k=k, methode=methode, diagnostics=diagnostics
            )
            pages_trouvees = [int(r["metadata"].get("page", -1)) for r in resultats]

            p = precision_a_k(pages_trouvees, pages_attendues, k)
            r = rappel_a_k(pages_trouvees, pages_attendues, k)
            rr = rang_reciproque(pages_trouvees, pages_attendues)

            resultats_par_methode[methode].append({"precision": p, "recall": r, "rr": rr})

            marqueur = "✅" if rr > 0 else "❌"
            rang_affiche = int(round(1 / rr)) if rr else "-"

            print(
                f"   [{methode:10s}] pages={pages_trouvees}  "
                f"P@{k}={p:.2f}  R@{k}={r:.2f}  {marqueur} rang={rang_affiche}"
            )

            if diagnostics:
                for d in diagnostics:
                    print(
                        f"      ↳ sauvetage page {d['page']} (terme='{d['terme']}', z={d['z']:.2f})"
                    )

    nb_questions = len(questions) or 1

    print("\n" + "-" * 80)
    print(f"RÉSUMÉ GLOBAL (moyenne macro sur {nb_questions} questions)")
    print("-" * 80)
    print(
        f"{'Méthode':12s} {'Precision@' + str(k):>13s} {'Recall@' + str(k):>11s} "
        f"{'MRR':>8s} {'Hit-rate@' + str(k):>13s}"
    )

    metriques_globales: Dict[str, Dict[str, float]] = {}

    for methode in methodes:
        lignes = resultats_par_methode[methode]
        precision_moy = sum(l["precision"] for l in lignes) / nb_questions
        recall_moy = sum(l["recall"] for l in lignes) / nb_questions
        mrr_moy = sum(l["rr"] for l in lignes) / nb_questions
        hit_rate = sum(1 for l in lignes if l["rr"] > 0) / nb_questions

        metriques_globales[methode] = {
            "precision": precision_moy,
            "recall": recall_moy,
            "mrr": mrr_moy,
            "hit_rate": hit_rate,
        }

        print(
            f"{methode:12s} {precision_moy:13.2%} {recall_moy:11.2%} "
            f"{mrr_moy:8.3f} {hit_rate:13.2%}"
        )

    if "hybride" in metriques_globales and "vectoriel" in metriques_globales:
        delta_mrr = metriques_globales["hybride"]["mrr"] - metriques_globales["vectoriel"]["mrr"]
        delta_recall = metriques_globales["hybride"]["recall"] - metriques_globales["vectoriel"]["recall"]

        print(f"\nΔ MRR (hybride - vectoriel)      : {delta_mrr:+.3f}")
        print(f"Δ Recall@{k} (hybride - vectoriel) : {delta_recall:+.2%}")

    print("=" * 80)


def tester_plusieurs_questions(methode: str = "hybride") -> None:
    """Affiche les résultats bruts pour plusieurs requêtes représentatives."""
    try:
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        embedding_fn = creer_embedding_function()
        collection = client.get_collection(name=COLLECTION_NAME, embedding_function=embedding_fn)
    except Exception as exc:
        print(f"❌ Impossible de charger la collection : {exc}")
        return

    corpus = charger_corpus(collection)
    bm25 = construire_index_bm25(corpus)

    if methode == "hybride" and bm25 is None:
        methode = "vectoriel"

    for question, _ in QUESTIONS_BENCHMARK:
        tester_rag(question, collection, corpus, bm25, n_results=3, methode=methode)


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:
    print("\n" + "=" * 80)
    print(" INGESTION GUIDE CMRPI - OCR FRANÇAIS + BAAI/bge-m3")
    print("=" * 80)
    print(f"PDF          : {PDF_PATH}")
    print(f"Collection   : {COLLECTION_NAME}")
    print(f"Chunk size   : {CHUNK_SIZE}")
    print(f"Overlap      : {CHUNK_OVERLAP}")
    print(f"OCR          : Tesseract / {OCR_LANGUAGE}")
    print(f"PSM          : {OCR_PSM_PRIMARY} -> fallback {OCR_PSM_FALLBACK}")
    print(f"Embedding    : {EMBEDDING_MODEL}")
    print("=" * 80)

    success = ingerer_cmrpi()

    if not success:
        print("\n❌ INGESTION ÉCHOUÉE")
        return

    print("\n" + "=" * 80)
    print(" TEST DU RAG")
    print("=" * 80)

    tester_plusieurs_questions()
    evaluer_recuperation(k=5)

    print("\n" + "=" * 80)
    print(" ✅ INGESTION ET TESTS TERMINÉS")
    print("=" * 80)


if __name__ == "__main__":
    main()