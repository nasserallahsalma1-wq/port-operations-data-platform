from pathlib import Path

import pyarrow.compute as pc
import pyarrow.parquet as pq

# Retrouver le dossier du projet à partir de l'emplacement du script.
project_dir = Path(__file__).resolve().parents[1]
raw_dir = project_dir / "data" / "raw"

# Rechercher tous les fichiers Parquet dans data/raw.
parquet_files = sorted(
    raw_dir.glob("ports_maroc.parquet/train-00000-of-00001.parquet")
)

if not parquet_files:
    raise SystemExit(f"Aucun fichier .parquet trouvé dans {raw_dir}")

for file_path in parquet_files:
    # Lire uniquement les trois colonnes utiles pour cette vérification.
    table = pq.read_table(
        file_path,
        columns=["date", "portname", "portcalls"],
    )

    print(f"\nFichier : {file_path.name}")
    print(f"Nombre total de lignes : {table.num_rows}")
    print(f"Type de la colonne date : {table.schema.field('date').type}")

    # Garder uniquement les lignes dont le port est Casablanca.
    is_casablanca = pc.equal(table["portname"], "Casablanca")
    casablanca = table.filter(is_casablanca)

    print(f"Nombre de lignes pour Casablanca : {casablanca.num_rows}")

    if casablanca.num_rows == 0:
        print("Aucune donnée pour Casablanca dans ce fichier.")
        continue

    # Trier par nombre d'escales. En cas d'égalité, la date la plus ancienne passe en premier.
    top_days = casablanca.sort_by(
        [("portcalls", "descending"), ("date", "ascending")]
    ).slice(0, 5)

    print("Les cinq jours les plus chargés à Casablanca :")
    for row in top_days.to_pylist():
        date = row["date"]
        portcalls = row["portcalls"]
        print(f"  {date:%Y-%m-%d} — {portcalls} escales")