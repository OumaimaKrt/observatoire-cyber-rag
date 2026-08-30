import os
import sys

import pandas as pd
import psycopg2


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

sys.path.append(BASE_DIR)

from config import DB_CONFIG


OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "ml"
)

OUTPUT_FILE = os.path.join(
    OUTPUT_DIR,
    "classification_data.csv"
)


# ============================================================
# CHARGEMENT
# ============================================================

def load_data():

    conn = psycopg2.connect(**DB_CONFIG)

    query = """
        SELECT
            id,
            titre,
            description,
            type_menace
        FROM cyber_incidents
        WHERE type_menace IS NOT NULL
          AND type_menace <> 'INCONNU'
    """

    df = pd.read_sql_query(query, conn)

    conn.close()

    return df


# ============================================================
# PREPARATION
# ============================================================

def prepare_data(df):

    print("\n" + "=" * 70)
    print("PREPARATION DU DATASET DE CLASSIFICATION")
    print("=" * 70)

    print(f"\nIncidents récupérés : {len(df)}")

    # --------------------------------------------------------
    # Nettoyage du titre et de la description
    # --------------------------------------------------------

    df["titre"] = df["titre"].fillna("").astype(str)
    df["description"] = df["description"].fillna("").astype(str)

    # --------------------------------------------------------
    # Création du texte
    # --------------------------------------------------------

    df["texte"] = (
        df["titre"].str.strip()
        + " "
        + df["description"].str.strip()
    ).str.strip()

    # --------------------------------------------------------
    # Suppression des textes vides
    # --------------------------------------------------------

    df = df[df["texte"].str.len() > 10].copy()

    print(f"Après suppression des textes vides : {len(df)}")

    # --------------------------------------------------------
    # Nettoyage du label
    # --------------------------------------------------------

    df["label"] = (
        df["type_menace"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    df = df[df["label"] != "INCONNU"].copy()

    # --------------------------------------------------------
    # Suppression des doublons
    # --------------------------------------------------------

    before = len(df)

    df = df.drop_duplicates(
        subset=["texte", "label"]
    ).copy()

    print(f"Doublons supprimés : {before - len(df)}")

    # --------------------------------------------------------
    # Dataset final
    # --------------------------------------------------------

    df = df[
        [
            "id",
            "texte",
            "label"
        ]
    ].copy()

    return df


# ============================================================
# STATISTIQUES
# ============================================================

def show_statistics(df):

    print("\n" + "-" * 70)
    print("DISTRIBUTION DES CLASSES")
    print("-" * 70)

    counts = df["label"].value_counts()

    percentages = (
        df["label"]
        .value_counts(normalize=True)
        .mul(100)
        .round(2)
    )

    stats = pd.DataFrame({
        "nombre": counts,
        "pourcentage": percentages
    })

    print(stats.to_string())

    print("\nNombre de classes :", df["label"].nunique())

    print("\nNombre total :", len(df))


# ============================================================
# SAUVEGARDE
# ============================================================

def save_data(df):

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )

    df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    print("\n" + "-" * 70)
    print("DATASET SAUVEGARDÉ")
    print("-" * 70)

    print(f"\nFichier : {OUTPUT_FILE}")
    print(f"Lignes  : {len(df)}")
    print(f"Colonnes: {len(df.columns)}")


# ============================================================
# MAIN
# ============================================================

def main():

    try:

        df = load_data()

        df = prepare_data(df)

        show_statistics(df)

        save_data(df)

        print("\n" + "=" * 70)
        print("PRÉPARATION TERMINÉE AVEC SUCCÈS")
        print("=" * 70)

    except Exception as e:

        print("\nERREUR :")
        print(e)

        raise


if __name__ == "__main__":
    main()