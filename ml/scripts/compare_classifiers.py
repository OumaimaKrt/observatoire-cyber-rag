import os
import sys
import joblib
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix
)


# ============================================================
# CONFIGURATION
# ============================================================

# Le script est dans :
# observatoire_cyber/ml/scripts/
#
# On remonte :
# scripts -> ml -> observatoire_cyber

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)


# ============================================================
# CHEMINS
# ============================================================

DATA_FILE = os.path.join(
    BASE_DIR,
    "ml",
    "data",
    "ml",
    "classification_data.csv"
)

MODEL_FILE = os.path.join(
    BASE_DIR,
    "models",
    "threat_classifier",
    "best_threat_classifier.joblib"
)

RESULTS_DIR = os.path.join(
    BASE_DIR,
    "results",
    "classification"
)

COMPARISON_FILE = os.path.join(
    RESULTS_DIR,
    "rules_vs_ml_comparison.csv"
)

REPORT_FILE = os.path.join(
    RESULTS_DIR,
    "rules_vs_ml_report.txt"
)

ERRORS_FILE = os.path.join(
    RESULTS_DIR,
    "classification_disagreements.csv"
)


# ============================================================
# PARAMÈTRES
# ============================================================

# IMPORTANT :
# Ces paramètres doivent être IDENTIQUES à classify_threats.py

MIN_SAMPLES = 50
TEST_SIZE = 0.20
RANDOM_STATE = 42


# ============================================================
# IMPORT DU CLASSIFIER ACTUEL
# ============================================================

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    from utils.classifiers import classifier_cyber_complet

except ImportError as e:
    raise ImportError(
        "\nImpossible d'importer ton classifier actuel.\n"
        f"Chemin attendu : "
        f"{os.path.join(BASE_DIR, 'utils', 'classifiers.py')}\n"
        f"Erreur : {e}"
    )


# ============================================================
# CHARGEMENT DU DATASET
# ============================================================

def load_dataset():

    print("\n" + "=" * 70)
    print("COMPARAISON CLASSIFIER RÈGLES VS CLASSIFIER ML")
    print("=" * 70)

    print("\n[1] Chargement du dataset...")

    if not os.path.exists(DATA_FILE):
        raise FileNotFoundError(
            f"Dataset introuvable : {DATA_FILE}"
        )

    df = pd.read_csv(DATA_FILE)

    print(f"Dataset chargé : {len(df)} lignes")
    print(f"Colonnes : {list(df.columns)}")

    return df


# ============================================================
# PREPARATION DU DATASET
# ============================================================

def prepare_dataset(df):

    print("\n" + "-" * 70)
    print("[2] Préparation du jeu de test")
    print("-" * 70)

    # --------------------------------------------------------
    # Vérification des colonnes
    # --------------------------------------------------------

    required_columns = ["id", "texte", "label"]

    missing_columns = [
        col for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Colonnes manquantes dans le dataset : "
            f"{missing_columns}"
        )

    # --------------------------------------------------------
    # Nettoyage
    # --------------------------------------------------------

    df = df.dropna(
        subset=["texte", "label"]
    ).copy()

    df["texte"] = (
        df["texte"]
        .astype(str)
        .str.strip()
    )

    df["label"] = (
        df["label"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    # Même condition que classify_threats.py
    df = df[
        df["texte"].str.len() > 10
    ].copy()

    # --------------------------------------------------------
    # Même seuil que classify_threats.py
    # --------------------------------------------------------

    counts = df["label"].value_counts()

    valid_classes = (
        counts[counts >= MIN_SAMPLES]
        .index
        .tolist()
    )

    df = df[
        df["label"].isin(valid_classes)
    ].copy()

    # --------------------------------------------------------
    # Trier les classes pour garantir une représentation
    # stable
    # --------------------------------------------------------

    valid_classes = sorted(
        df["label"].unique().tolist()
    )

    # --------------------------------------------------------
    # Affichage
    # --------------------------------------------------------

    print(
        f"\nSeuil minimum : {MIN_SAMPLES} exemples"
    )

    print(
        f"Classes utilisées : {len(valid_classes)}"
    )

    print(
        f"Observations utilisées : {len(df)}"
    )

    print("\nClasses :")

    for label in valid_classes:
        print(
            f"  - {label}: "
            f"{(df['label'] == label).sum()} exemple(s)"
        )

    print("\nDistribution finale :")

    print(
        df["label"]
        .value_counts()
        .to_string()
    )

    return df, valid_classes


# ============================================================
# RECONSTRUCTION DU MÊME SPLIT TRAIN / TEST
# ============================================================

def create_test_set(
    df,
    valid_classes
):

    print("\n" + "-" * 70)
    print("[3] Reconstruction du même jeu de test")
    print("-" * 70)

    X = df["texte"]
    y = df["label"]

    (
        X_train,
        X_test,
        y_train,
        y_test
    ) = train_test_split(
        X,
        y,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y
    )

    # --------------------------------------------------------
    # Reconstruction du DataFrame de test
    # --------------------------------------------------------

    test_df = df.loc[
        X_test.index
    ].copy()

    test_df = test_df[
        [
            "id",
            "texte",
            "label"
        ]
    ].copy()

    print(
        f"\nTrain : {len(X_train)}"
    )

    print(
        f"Test  : {len(X_test)}"
    )

    print(
        "\nLe test est basé sur le même "
        "split stratifié que le modèle ML."
    )

    # --------------------------------------------------------
    # Vérification des proportions
    # --------------------------------------------------------

    print("\nDistribution du jeu de test :")

    print(
        test_df["label"]
        .value_counts()
        .sort_index()
        .to_string()
    )

    return test_df


# ============================================================
# CHARGEMENT DU MODELE ML
# ============================================================

def load_ml_model():

    print("\n" + "-" * 70)
    print("[4] Chargement du modèle ML")
    print("-" * 70)

    if not os.path.exists(MODEL_FILE):
        raise FileNotFoundError(
            f"Modèle ML introuvable : {MODEL_FILE}\n"
            "Lance d'abord classify_threats.py."
        )

    model = joblib.load(
        MODEL_FILE
    )

    print(
        f"Modèle chargé : {MODEL_FILE}"
    )

    # --------------------------------------------------------
    # Vérification des classes du modèle
    # --------------------------------------------------------

    if hasattr(model, "classes_"):

        model_classes = [
            str(c).upper()
            for c in model.classes_
        ]

        print(
            "\nClasses du modèle ML :"
        )

        for label in model_classes:
            print(f"  - {label}")

    return model


# ============================================================
# NORMALISATION DE LA PREDICTION DU CLASSIFIER
# ============================================================

def normalize_rule_prediction(prediction):

    if prediction is None:
        return "INCONNU"

    prediction = (
        str(prediction)
        .strip()
        .upper()
    )

    mapping = {

        "PIRATAGE":
            "PIRATAGE",

        "VULNERABILITE":
            "VULNERABILITE",

        "VULNERABILITÉ":
            "VULNERABILITE",

        "DDOS":
            "DDOS",

        "RANSOMWARE":
            "RANSOMWARE",

        "FUITE_DONNEES":
            "FUITE_DONNEES",

        "FUITE DE DONNEES":
            "FUITE_DONNEES",

        "CHEVAL_TROIE":
            "CHEVAL_TROIE",

        "CHEVAL_DE_TROIE":
            "CHEVAL_TROIE",

        "PHISHING":
            "PHISHING",

        "SPYWARE":
            "SPYWARE",

        "MALWARE":
            "MALWARE",

        "EXPLOITATION":
            "EXPLOITATION",

        "BOTNET":
            "BOTNET",

        "INCONNU":
            "INCONNU",

        "INCIDENT":
            "INCIDENT",

        "SPOOFING":
            "SPOOFING",

        "VIRUS":
            "VIRUS",

        "BLANCHIMENT":
            "BLANCHIMENT",

        "ESCROQUERIE":
            "ESCROQUERIE"
    }

    return mapping.get(
        prediction,
        prediction
    )


# ============================================================
# CLASSIFICATION AVEC LES REGLES
# ============================================================

def predict_with_rules(test_df):

    print("\n" + "-" * 70)
    print("[5] Classification avec le classifier actuel")
    print("-" * 70)

    predictions = []

    total = len(test_df)

    for i, (_, row) in enumerate(
        test_df.iterrows(),
        start=1
    ):

        texte = str(
            row["texte"]
        )

        try:

            # Le classifier actuel attend :
            # titre + description
            #
            # Le dataset contient déjà :
            # texte = titre + description
            #
            # On passe donc le texte complet
            # dans description.

            result = classifier_cyber_complet(
                titre="",
                description=texte
            )

            if isinstance(result, dict):

                prediction = result.get(
                    "type_menace",
                    "INCONNU"
                )

            else:

                prediction = "INCONNU"

        except Exception as e:

            print(
                f"\nErreur ligne {row['id']} : {e}"
            )

            prediction = "INCONNU"

        prediction = normalize_rule_prediction(
            prediction
        )

        predictions.append(
            prediction
        )

        if i % 250 == 0:

            print(
                f"  Progression : "
                f"{i}/{total}"
            )

    print(
        f"\nClassification terminée : "
        f"{total} textes"
    )

    return predictions


# ============================================================
# CLASSIFICATION AVEC LE MODELE ML
# ============================================================

def predict_with_ml(
    model,
    test_df
):

    print("\n" + "-" * 70)
    print("[6] Classification avec LinearSVC")
    print("-" * 70)

    predictions = model.predict(
        test_df["texte"]
    )

    predictions = [
        str(prediction).strip().upper()
        for prediction in predictions
    ]

    print(
        f"Prédictions ML terminées : "
        f"{len(predictions)}"
    )

    return predictions


# ============================================================
# EVALUATION
# ============================================================

def calculate_metrics(
    y_true,
    predictions,
    valid_classes,
    name
):

    # --------------------------------------------------------
    # Accuracy
    # --------------------------------------------------------

    accuracy = accuracy_score(
        y_true,
        predictions
    )

    # --------------------------------------------------------
    # Precision macro
    # --------------------------------------------------------

    precision = precision_score(
        y_true,
        predictions,
        labels=valid_classes,
        average="macro",
        zero_division=0
    )

    # --------------------------------------------------------
    # Recall macro
    # --------------------------------------------------------

    recall = recall_score(
        y_true,
        predictions,
        labels=valid_classes,
        average="macro",
        zero_division=0
    )

    # --------------------------------------------------------
    # Macro-F1
    # --------------------------------------------------------

    f1_macro = f1_score(
        y_true,
        predictions,
        labels=valid_classes,
        average="macro",
        zero_division=0
    )

    # --------------------------------------------------------
    # Weighted-F1
    # --------------------------------------------------------

    f1_weighted = f1_score(
        y_true,
        predictions,
        labels=valid_classes,
        average="weighted",
        zero_division=0
    )

    return {

        "methode": name,

        "accuracy": accuracy,

        "precision_macro": precision,

        "recall_macro": recall,

        "f1_macro": f1_macro,

        "f1_weighted": f1_weighted
    }


# ============================================================
# COMPARAISON
# ============================================================

def compare_results(
    test_df,
    rule_predictions,
    ml_predictions,
    valid_classes
):

    print("\n" + "=" * 70)
    print("COMPARAISON DES RESULTATS")
    print("=" * 70)

    y_true = test_df[
        "label"
    ].tolist()

    # --------------------------------------------------------
    # Métriques
    # --------------------------------------------------------

    rules_metrics = calculate_metrics(
        y_true,
        rule_predictions,
        valid_classes,
        "Classifier règles"
    )

    ml_metrics = calculate_metrics(
        y_true,
        ml_predictions,
        valid_classes,
        "LinearSVC"
    )

    comparison = pd.DataFrame([
        rules_metrics,
        ml_metrics
    ])

    print(
        "\n" +
        comparison.to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # Amélioration ML
    # --------------------------------------------------------

    improvement_accuracy = (
        ml_metrics["accuracy"]
        - rules_metrics["accuracy"]
    )

    improvement_f1 = (
        ml_metrics["f1_macro"]
        - rules_metrics["f1_macro"]
    )

    print("\n" + "-" * 70)
    print("AMELIORATION DU ML")
    print("-" * 70)

    print(
        f"\nAccuracy : "
        f"{improvement_accuracy:+.4f} "
        f"({improvement_accuracy * 100:+.2f} points)"
    )

    print(
        f"Macro-F1 : "
        f"{improvement_f1:+.4f} "
        f"({improvement_f1 * 100:+.2f} points)"
    )

    # --------------------------------------------------------
    # Accord
    # --------------------------------------------------------

    agreement = sum(
        r == m
        for r, m in zip(
            rule_predictions,
            ml_predictions
        )
    )

    agreement_rate = (
        agreement / len(test_df)
    )

    print(
        f"\nAccord règles / ML : "
        f"{agreement_rate:.4f} "
        f"({agreement_rate * 100:.2f} %)"
    )

    return (
        comparison,
        improvement_accuracy,
        improvement_f1,
        agreement_rate
    )


# ============================================================
# ANALYSE DES DESACCORDS
# ============================================================

def save_disagreements(
    test_df,
    rule_predictions,
    ml_predictions
):

    result_df = test_df.copy()

    result_df[
        "prediction_regles"
    ] = rule_predictions

    result_df[
        "prediction_ml"
    ] = ml_predictions

    result_df[
        "accord"
    ] = (
        result_df["prediction_regles"]
        ==
        result_df["prediction_ml"]
    )

    disagreements = result_df[
        ~result_df["accord"]
    ].copy()

    # --------------------------------------------------------
    # Sauvegarde
    # --------------------------------------------------------

    disagreements.to_csv(
        ERRORS_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    print("\n" + "-" * 70)
    print("DESACCORDS")
    print("-" * 70)

    print(
        f"\nNombre de désaccords : "
        f"{len(disagreements)}"
    )

    if len(disagreements) > 0:

        print(
            "\nTop des désaccords :"
        )

        print(
            disagreements[
                [
                    "id",
                    "label",
                    "prediction_regles",
                    "prediction_ml"
                ]
            ]
            .head(20)
            .to_string(index=False)
        )

    print(
        f"\nFichier sauvegardé : "
        f"{ERRORS_FILE}"
    )

    return disagreements


# ============================================================
# RAPPORT DETAILLE
# ============================================================

def save_report(
    comparison,
    improvement_accuracy,
    improvement_f1,
    agreement_rate,
    test_df,
    rule_predictions,
    ml_predictions,
    valid_classes
):

    y_true = test_df[
        "label"
    ].tolist()

    # --------------------------------------------------------
    # Rapports individuels
    # --------------------------------------------------------

    rules_report = classification_report(
        y_true,
        rule_predictions,
        labels=valid_classes,
        zero_division=0
    )

    ml_report = classification_report(
        y_true,
        ml_predictions,
        labels=valid_classes,
        zero_division=0
    )

    # --------------------------------------------------------
    # Matrices de confusion
    # --------------------------------------------------------

    rules_cm = confusion_matrix(
        y_true,
        rule_predictions,
        labels=valid_classes
    )

    ml_cm = confusion_matrix(
        y_true,
        ml_predictions,
        labels=valid_classes
    )

    # --------------------------------------------------------
    # Sauvegarde
    # --------------------------------------------------------

    with open(
        REPORT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            "COMPARAISON CLASSIFIER REGLES VS ML\n"
        )

        f.write(
            "=" * 70 + "\n\n"
        )

        # ----------------------------------------------------
        # Contexte
        # ----------------------------------------------------

        f.write(
            "CONTEXTE\n"
        )

        f.write(
            "-" * 70 + "\n"
        )

        f.write(
            f"Nombre de textes testés : "
            f"{len(test_df)}\n"
        )

        f.write(
            f"Seuil minimum par classe : "
            f"{MIN_SAMPLES}\n"
        )

        f.write(
            f"Nombre de classes : "
            f"{len(valid_classes)}\n"
        )

        f.write(
            "Méthode ML : TF-IDF + LinearSVC\n"
        )

        f.write(
            "Méthode règles : "
            "utils.classifiers.classifier_cyber_complet\n\n"
        )

        # ----------------------------------------------------
        # Classes
        # ----------------------------------------------------

        f.write(
            "CLASSES ÉVALUÉES\n"
        )

        f.write(
            "-" * 70 + "\n"
        )

        for label in valid_classes:
            f.write(
                f"- {label}\n"
            )

        f.write("\n")

        # ----------------------------------------------------
        # Comparaison
        # ----------------------------------------------------

        f.write(
            "COMPARAISON DES METRIQUES\n"
        )

        f.write(
            "-" * 70 + "\n"
        )

        f.write(
            comparison.to_string(
                index=False
            )
        )

        f.write(
            "\n\n"
        )

        # ----------------------------------------------------
        # Différences
        # ----------------------------------------------------

        f.write(
            "DIFFERENCE EN FAVEUR DU ML\n"
        )

        f.write(
            "-" * 70 + "\n"
        )

        f.write(
            f"Différence Accuracy : "
            f"{improvement_accuracy:+.4f}\n"
        )

        f.write(
            f"Différence Macro-F1 : "
            f"{improvement_f1:+.4f}\n"
        )

        f.write(
            f"Accord entre les deux systèmes : "
            f"{agreement_rate:.4f}\n\n"
        )

        # ----------------------------------------------------
        # Règles
        # ----------------------------------------------------

        f.write(
            "RAPPORT CLASSIFIER REGLES\n"
        )

        f.write(
            "-" * 70 + "\n"
        )

        f.write(
            rules_report
        )

        f.write(
            "\n\n"
        )

        # ----------------------------------------------------
        # ML
        # ----------------------------------------------------

        f.write(
            "RAPPORT LINEARSVC\n"
        )

        f.write(
            "-" * 70 + "\n"
        )

        f.write(
            ml_report
        )

        f.write(
            "\n\n"
        )

        # ----------------------------------------------------
        # Matrice règles
        # ----------------------------------------------------

        f.write(
            "MATRICE DE CONFUSION - REGLES\n"
        )

        f.write(
            "-" * 70 + "\n"
        )

        f.write(
            "Labels :\n"
        )

        f.write(
            str(valid_classes)
        )

        f.write(
            "\n\n"
        )

        f.write(
            str(rules_cm)
        )

        f.write(
            "\n\n"
        )

        # ----------------------------------------------------
        # Matrice ML
        # ----------------------------------------------------

        f.write(
            "MATRICE DE CONFUSION - LINEARSVC\n"
        )

        f.write(
            "-" * 70 + "\n"
        )

        f.write(
            "Labels :\n"
        )

        f.write(
            str(valid_classes)
        )

        f.write(
            "\n\n"
        )

        f.write(
            str(ml_cm)
        )

        f.write(
            "\n"
        )

    print(
        f"\nRapport détaillé sauvegardé : "
        f"{REPORT_FILE}"
    )


# ============================================================
# SAUVEGARDE COMPARAISON
# ============================================================

def save_comparison_csv(comparison):

    comparison.to_csv(
        COMPARISON_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    print(
        f"Comparaison sauvegardée : "
        f"{COMPARISON_FILE}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # Dossiers
    # --------------------------------------------------------

    os.makedirs(
        RESULTS_DIR,
        exist_ok=True
    )

    # --------------------------------------------------------
    # 1. Dataset
    # --------------------------------------------------------

    df = load_dataset()

    # --------------------------------------------------------
    # 2. Préparation
    # --------------------------------------------------------

    df, valid_classes = prepare_dataset(
        df
    )

    # --------------------------------------------------------
    # 3. Même split que le ML
    # --------------------------------------------------------

    test_df = create_test_set(
        df,
        valid_classes
    )

    # --------------------------------------------------------
    # 4. Modèle ML
    # --------------------------------------------------------

    ml_model = load_ml_model()

    # --------------------------------------------------------
    # Vérification supplémentaire
    # --------------------------------------------------------

    if hasattr(ml_model, "classes_"):

        model_classes = set(
            str(c).upper()
            for c in ml_model.classes_
        )

        dataset_classes = set(
            valid_classes
        )

        if model_classes != dataset_classes:

            print("\n" + "!" * 70)

            print(
                "ATTENTION : les classes du modèle ML "
                "ne correspondent pas exactement au dataset."
            )

            print(
                f"Classes modèle : "
                f"{sorted(model_classes)}"
            )

            print(
                f"Classes dataset : "
                f"{sorted(dataset_classes)}"
            )

            print("!" * 70)

    # --------------------------------------------------------
    # 5. Ancien classifier
    # --------------------------------------------------------

    rule_predictions = predict_with_rules(
        test_df
    )

    # --------------------------------------------------------
    # 6. ML
    # --------------------------------------------------------

    ml_predictions = predict_with_ml(
        ml_model,
        test_df
    )

    # --------------------------------------------------------
    # 7. Comparaison
    # --------------------------------------------------------

    (
        comparison,
        improvement_accuracy,
        improvement_f1,
        agreement_rate
    ) = compare_results(
        test_df,
        rule_predictions,
        ml_predictions,
        valid_classes
    )

    # --------------------------------------------------------
    # 8. Désaccords
    # --------------------------------------------------------

    save_disagreements(
        test_df,
        rule_predictions,
        ml_predictions
    )

    # --------------------------------------------------------
    # 9. Sauvegarde métriques
    # --------------------------------------------------------

    save_comparison_csv(
        comparison
    )

    # --------------------------------------------------------
    # 10. Rapport
    # --------------------------------------------------------

    save_report(
        comparison,
        improvement_accuracy,
        improvement_f1,
        agreement_rate,
        test_df,
        rule_predictions,
        ml_predictions,
        valid_classes
    )

    # --------------------------------------------------------
    # Résumé final
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("COMPARAISON TERMINEE")
    print("=" * 70)

    print(
        "\nRésultats principaux :"
    )

    print(
        comparison.to_string(
            index=False
        )
    )

    print(
        "\nDifférence Accuracy ML - règles : "
        f"{improvement_accuracy:+.4f}"
    )

    print(
        "Différence Macro-F1 ML - règles : "
        f"{improvement_f1:+.4f}"
    )

    print(
        "\nAccord entre les deux systèmes : "
        f"{agreement_rate * 100:.2f} %"
    )

    print(
        "\nFichiers générés :"
    )

    print(
        f"  - {COMPARISON_FILE}"
    )

    print(
        f"  - {REPORT_FILE}"
    )

    print(
        f"  - {ERRORS_FILE}"
    )

    print("\n" + "=" * 70)


# ============================================================
# EXECUTION
# ============================================================

if __name__ == "__main__":
    main()