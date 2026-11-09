# Attributions

Le cours demande de déclarer ce qui n'a pas été fait par l'équipe. Ce fichier doit rester exact : **mettez-le à jour avant le rendu**.

## Assistants IA

Le code, les tests, l'infrastructure, la documentation et les premiers brouillons du rapport et des slides de ce dépôt ont été générés avec l'assistant Claude (Anthropic), à partir d'un plan établi avec lui, en novembre 2026.

Le document `TP_Financial_AI_Analyst.md` et le premier prototype ont été préparés par un membre de l'équipe. *Précisez ici si un assistant IA a servi à les écrire.*

**À compléter par l'équipe :** ce que chaque membre a relu, modifié, exécuté et mesuré lui-même.

| Membre | Parties relues et maîtrisées | Modifications et mesures personnelles |
| --- | --- | --- |
| *à compléter* | | |
| *à compléter* | | |
| *à compléter* | | |

## Données

| Source | Usage | Remarque |
| --- | --- | --- |
| [plotly/datasets, all_stocks_5yr.csv](https://github.com/plotly/datasets) | Évaluation et démo | Prix de 2013 à 2018 |
| Yahoo Finance via yfinance | Production | Non affilié à Yahoo ; vérifier les conditions d'usage |
| Hacker News via Algolia | Production | Pseudonymes non conservés |
| SEC EDGAR | Production | User-Agent déclaré obligatoire |
| Reddit | Optionnel | À activer seulement après accord explicite de Reddit |
| `evaluation_data/demo_posts.jsonl` | Démo | **Messages fictifs**, écrits pour la démo |

## Composants principaux

FastAPI, Pydantic, scikit-learn, XGBoost, pandas, NumPy, yfinance, boto3, Streamlit, Plotly, pytest, moto, Terraform, AWS Lambda Web Adapter.

## Idées reprises

- Modèle HAR, baseline : Corsi (2009).
- Test de Diebold et Mariano (1995).
- Intervalles conformes adaptatifs : Gibbs et Candès (2021).
