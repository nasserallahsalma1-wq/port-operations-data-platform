import csv
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from pyspark.sql import SparkSession, functions as F

project_dir = Path(__file__).resolve().parents[1]

source = (
    project_dir / "data" / "raw" / "ports_maroc.parquet"
    / "train-00000-of-00001.parquet"
)

if not source.is_file():
    raise SystemExit(f"Fichier source introuvable : {source}")

processed_dir = project_dir / "data" / "processed"
processed_dir.mkdir(parents=True, exist_ok=True)
prepared_file = processed_dir / "ports_journaliers.parquet"

# Convertir le timestamp UTC en date journalière.
table = pq.read_table(
    source, columns=["date", "portid", "portname", "portcalls"]
)
date_index = table.schema.get_field_index("date")
daily_dates = (
    table["date"]
    .cast(pa.int64())
    .cast(pa.timestamp("ns"))
    .cast(pa.date32())
)
table = table.set_column(date_index, "date", daily_dates)
pq.write_table(table, prepared_file)

spark = (
    SparkSession.builder
    .appName("Analyse mensuelle des ports marocains")
    .master("local[2]")
    .config("spark.sql.shuffle.partitions", "4")
    .getOrCreate()
)

try:
    ports = spark.read.parquet(prepared_file.as_uri())

    # Écarter les lignes dont les données essentielles sont invalides.
    valid = ports.dropna(
        subset=["date", "portid", "portname", "portcalls"]
    ).filter(F.col("portcalls") >= 0)

    # Supprimer les doublons exacts sur les quatre colonnes utilisées.
    unique_rows = valid.dropDuplicates()

    print(f"Lignes lues : {ports.count()}")
    print(f"Lignes invalides : {ports.count() - valid.count()}")
    print(f"Doublons exacts : {valid.count() - unique_rows.count()}")

    # Après déduplication, une seule ligne doit rester par port et par jour.
    conflicts = (
        unique_rows.groupBy("portid", "date")
        .count()
        .filter(F.col("count") > 1)
    )

    if conflicts.take(1):
        conflicts.show(10, truncate=False)
        raise SystemExit("Plusieurs valeurs existent pour un même port et une même date.")

    monthly = (
        unique_rows.withColumn("mois", F.trunc("date", "month"))
        .groupBy("portid", "portname", "mois")
        .agg(
            F.sum("portcalls").alias("total_escales"),
            F.count("*").alias("jours_observes"),
            F.round(F.avg("portcalls"), 2).alias("escales_moyennes_par_jour"),
        )
        .orderBy("mois", "portid")
    )

    print("\nDerniers mois disponibles pour Casablanca")
    (
        monthly.filter(F.col("portid") == "port220")
        .orderBy(F.col("mois").desc())
        .show(6, truncate=False)
    )

    output = processed_dir / "escales_mensuelles.csv"
    with output.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(monthly.columns)
        writer.writerows(monthly.toLocalIterator())

    print(f"CSV créé : {output}")

finally:
    spark.stop()