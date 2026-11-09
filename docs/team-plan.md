# Plan d'équipe jusqu'à la soutenance blanche

Hypothèse : soutenance blanche autour du 18 novembre 2026. Rôles proposés, à adapter : **A** données et modèle, **B** LLM et RAG, **C** cloud et interface.

**Règle de l'équipe :** personne ne présente un module qu'il ne peut pas réexpliquer. Chaque membre relit au moins son domaine et la démo.

| Dates | A : données et modèle | B : LLM et RAG | C : cloud et interface |
| --- | --- | --- | --- |
| 4-5 nov. | Lire `forecasting/`, relancer `make evaluate` | Lire `llm/` et `rag/`, installer Ollama | Créer le dépôt GitHub, activer la CI, corriger ses erreurs |
| 6-7 nov. | Tester yfinance depuis AWS et sur des données récentes | Tester Bedrock : accès, sortie structurée, Nova Micro | Déployer le prototype EC2, créer l'alerte budget |
| 8-9 nov. | Lancer l'évaluation sur les données 2020-2026 | Collecter de vrais messages Hacker News ; demander l'accès Reddit | `terraform validate`, puis premier `apply` |
| 10-11 nov. | Comparer anciens et nouveaux résultats, analyser les erreurs | Annoter 50 cas réels, à deux pour mesurer l'accord | Passer l'API sur Lambda, publier le site sur CloudFront |
| 12-13 nov. | Rédiger les parties Données et Modèle | Lancer le benchmark et les injections réelles ; choisir le modèle | Tester avec 5 personnes hors de la classe, corriger |
| 14-15 nov. | Compléter le rapport avec les vrais résultats | Rédiger la partie LLM et RAG | Rédiger Architecture et Qualité ; enregistrer la vidéo |
| 16 nov. | Gel du code, relecture croisée du rapport | Gel du code, mise à jour d'ATTRIBUTIONS | Vérifier la démo en ligne |
| 17 nov. | Répétition chronométrée à trois, deux fois | Questions du jury : chacun répond sur une partie qui n'est pas la sienne | Répétition avec panne simulée |

## Si vous manquez de temps

Coupez dans cet ordre : Reddit, EDGAR, passage sur Lambda (EC2 reste), site statique (Streamlit reste), Terraform complet.

Ne coupez pas : un vrai LLM en démo, de vrais messages, le benchmark même réduit, le dépôt GitHub, le rapport, la répétition.
