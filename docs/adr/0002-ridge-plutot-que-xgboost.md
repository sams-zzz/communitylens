# ADR 2 : Ridge plutôt que XGBoost

**Décision.** Ridge sert en production.

**Preuves.** Erreur plus faible sur 23 titres sur 30 ; différence significative (p = 0,012). Contributions exactes par feature. Pas de dépendance lourde : XGBoost installe 84 Mo et, selon le paquet, 345 Mo de bibliothèques NVIDIA.

**Limite.** Les hyperparamètres de XGBoost n'ont pas été optimisés : un réglage fin pourrait réduire l'écart.
