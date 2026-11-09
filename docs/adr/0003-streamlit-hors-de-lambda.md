# ADR 3 : Streamlit hors de Lambda

**Contexte.** Les notes évoquent Docker sur EC2, puis Lambda avec Web Adapter, API et site statique.

**Décision.** FastAPI tourne sur Lambda via le Web Adapter. Le site public est statique. Streamlit reste sur EC2, comme prototype et outil interne.

**Raison.** Streamlit repose sur des WebSockets ; [un essai sur Lambda avec Web Adapter a échoué pour cette raison](https://zenn.dev/ncdc/articles/71d49bced3b69d). La même image d'API tourne sur EC2 et sur Lambda.

**À vérifier.** Un test d'une soirée peut confirmer cette limite.
