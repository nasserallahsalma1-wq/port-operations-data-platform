from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Trafic portuaire au Maroc", layout="wide")
st.title("Trafic portuaire au Maroc")

# Retrouver le CSV à partir de l'emplacement de app.py.
project_dir = Path(__file__).resolve().parents[1]
csv_path = project_dir / "data" / "processed" / "escales_mensuelles.csv"

if not csv_path.is_file():
    st.error("CSV introuvable. Lance d’abord le script d’analyse mensuelle.")
    st.stop()

data = pd.read_csv(csv_path, parse_dates=["mois"])

if data.empty:
    st.warning("Le fichier CSV ne contient aucune donnée.")
    st.stop()

# Préparer l'année du filtre et le contrôle de couverture des données.
data["annee"] = data["mois"].dt.year
data["jours_du_mois"] = data["mois"].dt.days_in_month
data["mois_incomplet"] = data["jours_observes"] < data["jours_du_mois"]

st.sidebar.header("Filtres")
years = sorted(data["annee"].unique(), reverse=True)
year = st.sidebar.selectbox("Année", years)

year_data = data.loc[data["annee"] == year]
ports = sorted(year_data["portname"].unique())

preferred_ports = ["Casablanca", "Tangier-Mediterranean", "Jorf Lasfar"]
default_ports = [port for port in preferred_ports if port in ports]

selected_ports = st.sidebar.multiselect(
    "Ports à comparer",
    options=ports,
    default=default_ports or ports[:1],
)

if not selected_ports:
    st.info("Sélectionne au moins un port dans la barre latérale.")
    st.stop()

filtered = year_data.loc[year_data["portname"].isin(selected_ports)]

# Calculer les indicateurs sur les ports et l'année sélectionnés.
total_escales = int(filtered["total_escales"].sum())
jours_observes = int(filtered["jours_observes"].sum())

total_col, ports_col, average_col = st.columns(3)
total_col.metric("Total des escales", f"{total_escales:,}".replace(",", " "))
ports_col.metric("Ports sélectionnés", filtered["portname"].nunique())
average_col.metric(
    "Escales par port et par jour observé",
    f"{total_escales / jours_observes:.2f}" if jours_observes else "—",
)

st.subheader("Évolution mensuelle des escales")
st.line_chart(
    filtered.sort_values("mois"),
    x="mois",
    y="total_escales",
    color="portname",
)

if filtered["mois_incomplet"].any():
    st.caption(
        "Certains mois contiennent des jours manquants. "
        "Consulte le tableau pour vérifier leur couverture avant de comparer les totaux."
    )

st.subheader("Détail par port et par mois")

details = filtered.sort_values(
    ["mois", "portname"], ascending=[False, True]
).copy()
details["mois"] = details["mois"].dt.strftime("%Y-%m")
details["couverture"] = (
    details["jours_observes"].astype(str)
    + " / "
    + details["jours_du_mois"].astype(str)
)

st.dataframe(
    details[
        ["portname", "mois", "total_escales", "escales_moyennes_par_jour", "couverture"]
    ].rename(
        columns={
            "portname": "Port",
            "mois": "Mois",
            "total_escales": "Total des escales",
            "escales_moyennes_par_jour": "Escales par jour observé",
            "couverture": "Jours observés / jours du mois",
        }
    ),
    hide_index=True,
)

st.caption("Source des données · IMF PortWatch")