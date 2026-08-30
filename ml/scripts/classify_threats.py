import os

import joblib
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay
)


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

DATA_FILE = os.path.join(
    BASE_DIR,
    "ml",
    "data",
    "ml",
    "classification_data.csv"
)

MODEL_DIR = os.path.join(
    BASE_DIR,
    "models",
    "threat_classifier"
)

RESULTS_DIR = os.path.join(
    BASE_DIR,
    "results",
    "classification"
)

# Nombre minimum d'exemples par classe
MIN_SAMPLES = 50

# Taille du jeu de test
TEST_SIZE = 0.20

# Reproductibilité
RANDOM_STATE = 42

# Valeurs de C testées pour LinearSVC
SVC_C_VALUES = [0.5, 1.0, 2.0, 5.0]


# ============================================================
# CHARGEMENT DU DATASET
# ============================================================

def load_dataset():

    print("\n" + "=" * 70)
    print("CLASSIFICATION ML DES MENACES CYBER")
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
    print("[2] Préparation du dataset")
    print("-" * 70)

    # --------------------------------------------------------
    # Vérification des colonnes
    # --------------------------------------------------------

    required_columns = [
        "id",
        "texte",
        "label"
    ]

    missing = [
        col
        for col in required_columns
        if col not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Colonnes manquantes : {missing}"
        )

    # --------------------------------------------------------
    # Suppression des valeurs invalides
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

    # Suppression des textes trop courts
    df = df[
        df["texte"].str.len() > 10
    ].copy()

    # --------------------------------------------------------
    # Distribution initiale
    # --------------------------------------------------------

    print("\nDistribution initiale :")

    initial_counts = df["label"].value_counts()

    print(
        initial_counts.to_string()
    )

    # --------------------------------------------------------
    # Suppression des classes trop rares
    # --------------------------------------------------------

    valid_classes = (
        initial_counts[
            initial_counts >= MIN_SAMPLES
        ]
        .index
        .tolist()
    )

    removed_classes = (
        initial_counts[
            initial_counts < MIN_SAMPLES
        ]
    )

    print(
        f"\nSeuil minimum : {MIN_SAMPLES} exemples"
    )

    if len(removed_classes) > 0:

        print(
            "\nClasses exclues de l'entraînement :"
        )

        for label, count in removed_classes.items():

            print(
                f"  - {label}: {count} exemple(s)"
            )

    df = df[
        df["label"].isin(valid_classes)
    ].copy()

    print(
        f"\nNombre de classes utilisées : "
        f"{df['label'].nunique()}"
    )

    print(
        f"Nombre d'observations utilisées : "
        f"{len(df)}"
    )

    print("\nDistribution finale :")

    print(
        df["label"]
        .value_counts()
        .to_string()
    )

    return df


# ============================================================
# SEPARATION TRAIN / TEST
# ============================================================

def split_data(df):

    print("\n" + "-" * 70)
    print("[3] Séparation train / test")
    print("-" * 70)

    X = df["texte"]
    y = df["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y
    )

    print(
        f"Train : {len(X_train)} observations"
    )

    print(
        f"Test  : {len(X_test)} observations"
    )

    print(
        f"Ratio : {int((1 - TEST_SIZE) * 100)} / "
        f"{int(TEST_SIZE * 100)}"
    )

    return (
        X_train,
        X_test,
        y_train,
        y_test
    )


# ============================================================
# CREATION DES MODELES
# ============================================================

def create_models():

    models = {}

    # --------------------------------------------------------
    # Paramètres TF-IDF communs
    # --------------------------------------------------------

    tfidf_params = {
        "lowercase": True,
        "strip_accents": "unicode",
        "ngram_range": (1, 2),
        "min_df": 2,
        "max_df": 0.95,
        "sublinear_tf": True
    }

    # ========================================================
    # LOGISTIC REGRESSION
    # ========================================================

    models["LogisticRegression"] = Pipeline([
        (
            "tfidf",
            TfidfVectorizer(
                **tfidf_params
            )
        ),
        (
            "classifier",
            LogisticRegression(
                max_iter=2000,
                class_weight="balanced"
            )
        )
    ])

    # ========================================================
    # LINEAR SVC
    # Test de plusieurs valeurs de C
    # ========================================================

    for c in SVC_C_VALUES:

        model_name = f"LinearSVC_C{c}"

        models[model_name] = Pipeline([
            (
                "tfidf",
                TfidfVectorizer(
                    **tfidf_params
                )
            ),
            (
                "classifier",
                LinearSVC(
                    C=c,
                    class_weight="balanced"
                )
            )
        ])

    return models


# ============================================================
# EVALUATION D'UN MODELE
# ============================================================

def evaluate_model(
    name,
    model,
    X_train,
    X_test,
    y_train,
    y_test
):

    print("\n" + "-" * 70)
    print(f"ENTRAÎNEMENT : {name}")
    print("-" * 70)

    # --------------------------------------------------------
    # Entraînement
    # --------------------------------------------------------

    model.fit(
        X_train,
        y_train
    )

    # --------------------------------------------------------
    # Prédictions
    # --------------------------------------------------------

    predictions = model.predict(
        X_test
    )

    # --------------------------------------------------------
    # Métriques
    # --------------------------------------------------------

    accuracy = accuracy_score(
        y_test,
        predictions
    )

    precision = precision_score(
        y_test,
        predictions,
        average="macro",
        zero_division=0
    )

    recall = recall_score(
        y_test,
        predictions,
        average="macro",
        zero_division=0
    )

    macro_f1 = f1_score(
        y_test,
        predictions,
        average="macro",
        zero_division=0
    )

    weighted_f1 = f1_score(
        y_test,
        predictions,
        average="weighted",
        zero_division=0
    )

    # --------------------------------------------------------
    # Affichage des métriques
    # --------------------------------------------------------

    print(
        f"\nAccuracy    : {accuracy:.4f}"
    )

    print(
        f"Precision   : {precision:.4f}"
    )

    print(
        f"Recall      : {recall:.4f}"
    )

    print(
        f"Macro-F1    : {macro_f1:.4f}"
    )

    print(
        f"Weighted-F1 : {weighted_f1:.4f}"
    )

    # --------------------------------------------------------
    # Distribution des prédictions
    # --------------------------------------------------------

    print("\nDistribution des prédictions :")

    prediction_distribution = (
        pd.Series(predictions)
        .value_counts()
    )

    print(
        prediction_distribution.to_string()
    )

    # --------------------------------------------------------
    # Rapport de classification
    # --------------------------------------------------------

    print("\nRapport de classification :")

    report = classification_report(
        y_test,
        predictions,
        zero_division=0
    )

    print(report)

    return {
        "model": name,
        "accuracy": accuracy,
        "precision_macro": precision,
        "recall_macro": recall,
        "f1_macro": macro_f1,
        "f1_weighted": weighted_f1,
        "predictions": predictions,
        "report": report,
        "trained_model": model
    }


# ============================================================
# SAUVEGARDE DES RAPPORTS INDIVIDUELS
# ============================================================

def save_model_report(result):

    os.makedirs(
        RESULTS_DIR,
        exist_ok=True
    )

    model_name = result["model"]

    report_file = os.path.join(
        RESULTS_DIR,
        f"classification_report_{model_name}.txt"
    )

    with open(
        report_file,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            "CLASSIFICATION ML DES MENACES CYBER\n"
        )

        f.write(
            "=" * 70 + "\n\n"
        )

        f.write(
            f"Modèle : {model_name}\n\n"
        )

        f.write(
            f"Accuracy    : "
            f"{result['accuracy']:.4f}\n"
        )

        f.write(
            f"Precision   : "
            f"{result['precision_macro']:.4f}\n"
        )

        f.write(
            f"Recall      : "
            f"{result['recall_macro']:.4f}\n"
        )

        f.write(
            f"Macro-F1    : "
            f"{result['f1_macro']:.4f}\n"
        )

        f.write(
            f"Weighted-F1 : "
            f"{result['f1_weighted']:.4f}\n\n"
        )

        f.write(
            "RAPPORT DE CLASSIFICATION\n"
        )

        f.write(
            "-" * 70 + "\n"
        )

        f.write(
            result["report"]
        )

    print(
        f"Rapport sauvegardé : {report_file}"
    )


# ============================================================
# MATRICE DE CONFUSION
# ============================================================

def save_confusion_matrix(
    model,
    X_test,
    y_test,
    model_name
):

    predictions = model.predict(
        X_test
    )

    labels = sorted(
        y_test.unique()
    )

    cm = confusion_matrix(
        y_test,
        predictions,
        labels=labels
    )

    fig, ax = plt.subplots(
        figsize=(12, 10)
    )

    display = ConfusionMatrixDisplay(
        confusion_matrix=cm,
        display_labels=labels
    )

    display.plot(
        ax=ax,
        xticks_rotation=45
    )

    ax.set_title(
        f"Matrice de confusion - {model_name}"
    )

    plt.tight_layout()

    output_file = os.path.join(
        RESULTS_DIR,
        f"confusion_matrix_{model_name}.png"
    )

    plt.savefig(
        output_file,
        dpi=200,
        bbox_inches="tight"
    )

    plt.close()

    print(
        f"\nMatrice sauvegardée : {output_file}"
    )


# ============================================================
# COMPARAISON DES MODELES
# ============================================================

def save_comparison(results):

    comparison = []

    for result in results:

        comparison.append({
            "modele": result["model"],
            "accuracy": result["accuracy"],
            "precision_macro": result["precision_macro"],
            "recall_macro": result["recall_macro"],
            "f1_macro": result["f1_macro"],
            "f1_weighted": result["f1_weighted"]
        })

    comparison_df = pd.DataFrame(
        comparison
    )

    # --------------------------------------------------------
    # Tri selon Macro-F1
    # --------------------------------------------------------

    comparison_df = comparison_df.sort_values(
        "f1_macro",
        ascending=False
    )

    # --------------------------------------------------------
    # Sauvegarde CSV
    # --------------------------------------------------------

    output_file = os.path.join(
        RESULTS_DIR,
        "model_comparison.csv"
    )

    comparison_df.to_csv(
        output_file,
        index=False,
        encoding="utf-8-sig"
    )

    # --------------------------------------------------------
    # Affichage
    # --------------------------------------------------------

    print("\n" + "-" * 70)
    print("COMPARAISON DES MODÈLES")
    print("-" * 70)

    print(
        comparison_df.to_string(
            index=False
        )
    )

    print(
        f"\nComparaison sauvegardée : {output_file}"
    )

    return comparison_df


# ============================================================
# SAUVEGARDE DU MEILLEUR MODELE ML
# ============================================================

def save_best_model(result):

    os.makedirs(
        MODEL_DIR,
        exist_ok=True
    )

    model = result["trained_model"]

    model_file = os.path.join(
        MODEL_DIR,
        "best_threat_classifier.joblib"
    )

    joblib.dump(
        model,
        model_file
    )

    print(
        f"\nMeilleur modèle ML sauvegardé : "
        f"{model_file}"
    )

    # --------------------------------------------------------
    # Rapport principal du meilleur modèle
    # --------------------------------------------------------

    report_file = os.path.join(
        RESULTS_DIR,
        "classification_report.txt"
    )

    with open(
        report_file,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            "CLASSIFICATION ML DES MENACES CYBER\n"
        )

        f.write(
            "=" * 70 + "\n\n"
        )

        f.write(
            f"Modèle sélectionné : "
            f"{result['model']}\n\n"
        )

        f.write(
            f"Accuracy    : "
            f"{result['accuracy']:.4f}\n"
        )

        f.write(
            f"Precision   : "
            f"{result['precision_macro']:.4f}\n"
        )

        f.write(
            f"Recall      : "
            f"{result['recall_macro']:.4f}\n"
        )

        f.write(
            f"Macro-F1    : "
            f"{result['f1_macro']:.4f}\n"
        )

        f.write(
            f"Weighted-F1 : "
            f"{result['f1_weighted']:.4f}\n\n"
        )

        f.write(
            "RAPPORT DE CLASSIFICATION\n"
        )

        f.write(
            "-" * 70 + "\n"
        )

        f.write(
            result["report"]
        )

    print(
        f"Rapport principal sauvegardé : "
        f"{report_file}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # Création des dossiers
    # --------------------------------------------------------

    os.makedirs(
        MODEL_DIR,
        exist_ok=True
    )

    os.makedirs(
        RESULTS_DIR,
        exist_ok=True
    )

    # --------------------------------------------------------
    # 1. Chargement
    # --------------------------------------------------------

    df = load_dataset()

    # --------------------------------------------------------
    # 2. Préparation
    # --------------------------------------------------------

    df = prepare_dataset(
        df
    )

    # --------------------------------------------------------
    # 3. Split
    # --------------------------------------------------------

    (
        X_train,
        X_test,
        y_train,
        y_test
    ) = split_data(
        df
    )

    # --------------------------------------------------------
    # 4. Création des modèles
    # --------------------------------------------------------

    models = create_models()

    print("\n" + "=" * 70)
    print("MODÈLES À ÉVALUER")
    print("=" * 70)

    for name in models.keys():
        print(f"  - {name}")

    # --------------------------------------------------------
    # 5. Entraînement + évaluation
    # --------------------------------------------------------

    results = []

    for name, model in models.items():

        result = evaluate_model(
            name,
            model,
            X_train,
            X_test,
            y_train,
            y_test
        )

        results.append(
            result
        )

        # Sauvegarder le rapport individuel
        save_model_report(
            result
        )

    # --------------------------------------------------------
    # 6. Comparaison
    # --------------------------------------------------------

    comparison = save_comparison(
        results
    )

    # --------------------------------------------------------
    # 7. Sélection du meilleur modèle
    # --------------------------------------------------------

    best_name = comparison.iloc[0]["modele"]

    best_result = next(
        result
        for result in results
        if result["model"] == best_name
    )

    print("\n" + "=" * 70)
    print("MEILLEUR MODÈLE ML")
    print("=" * 70)

    print(
        f"\nModèle : {best_name}"
    )

    print(
        f"Accuracy : "
        f"{best_result['accuracy']:.4f}"
    )

    print(
        f"Macro-F1 : "
        f"{best_result['f1_macro']:.4f}"
    )

    print(
        f"Weighted-F1 : "
        f"{best_result['f1_weighted']:.4f}"
    )

    # --------------------------------------------------------
    # 8. Matrice de confusion
    # --------------------------------------------------------

    save_confusion_matrix(
        best_result["trained_model"],
        X_test,
        y_test,
        best_name
    )

    # --------------------------------------------------------
    # 9. Sauvegarde du meilleur modèle
    # --------------------------------------------------------

    save_best_model(
        best_result
    )

    # --------------------------------------------------------
    # 10. Résumé final
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("CLASSIFICATION TERMINÉE")
    print("=" * 70)

    print(
        "\nLes modèles ont été comparés selon le Macro-F1."
    )

    print(
        f"Meilleur modèle ML : {best_name}"
    )

    print(
        f"Macro-F1 : "
        f"{best_result['f1_macro']:.4f}"
    )

    print(
        "\nRésultats disponibles dans :"
    )

    print(
        f"  {RESULTS_DIR}"
    )

    print(
        "\nModèle disponible dans :"
    )

    print(
        f"  {MODEL_DIR}"
    )


# ============================================================
# EXECUTION
# ============================================================

if __name__ == "__main__":
    main()