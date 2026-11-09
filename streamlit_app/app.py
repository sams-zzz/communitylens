"""Interface Streamlit, version prototype du schéma initial, déployée avec Docker sur EC2."""

import os

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8000")
TIMEOUT = 60


def get_json(path: str):
    """Appelle l'API et renvoie le JSON."""
    response = requests.get(f"{API_URL}{path}", timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def corridor(history: pd.DataFrame) -> go.Figure:
    """Trace l'intervalle annoncé, la prévision et la volatilité observée."""
    figure = go.Figure()
    figure.add_scatter(x=history["date"], y=history["high"], line={"width": 0}, showlegend=False)
    figure.add_scatter(
        x=history["date"], y=history["low"], fill="tonexty", line={"width": 0}, name="Intervalle"
    )
    figure.add_scatter(x=history["date"], y=history["predicted"], name="Prévision")
    figure.add_scatter(x=history["date"], y=history["realized"], mode="markers", name="Observée")
    figure.update_layout(yaxis_title="Volatilité annualisée (%)", height=380)
    return figure


st.set_page_config(page_title="CommunityLens", layout="wide")
st.title("CommunityLens")
st.caption("Outil pédagogique. Il ne donne aucun conseil d'investissement.")

try:
    tickers = get_json("/v1/tickers")
except requests.RequestException:
    st.error(f"L'API ne répond pas à {API_URL}. Démarrez-la, puis rechargez la page.")
    st.stop()

labels = {f"{item['company']} ({item['ticker']})": item["ticker"] for item in tickers}
choice = st.selectbox("Titre", sorted(labels))
ticker = labels[choice]
analysis = get_json(f"/v1/tickers/{ticker}/analysis")
forecast = analysis["forecast"]

columns = st.columns(3)
columns[0].metric("Volatilité prévue à 5 jours", f"{forecast['volatility_pct']} %")
columns[1].metric(
    f"Intervalle à {forecast['level_pct']} %", f"{forecast['low_pct']} à {forecast['high_pct']} %"
)
columns[2].metric("Couverture observée", f"{forecast['coverage_60d_pct']} %")
st.plotly_chart(corridor(pd.DataFrame(get_json(f"/v1/tickers/{ticker}/history"))))

st.subheader("Ce que dit la communauté")
st.write(analysis["explanation"]["summary"])
for claim in analysis["explanation"]["claims"]:
    st.markdown(f"**{claim['status']}** : {claim['text']}")
st.caption(analysis["explanation"]["limits"])
