# ADR 1 : prévoir la volatilité plutôt que la direction

**Contexte.** Le prototype prédisait la hausse du lendemain, avec une confiance tirée de la probabilité du modèle. Les notes du professeur posent la question « confiance ? » et évoquent une régression.

**Décision.** Le modèle principal prévoit la volatilité réalisée à 5 jours. Le classifieur de direction reste uniquement comme contre-preuve.

**Preuves.** Sur 30 titres : direction à 50,6 % contre 51,7 % pour « toujours hausse », AUC de 0,504. Volatilité : Ridge bat chaque baseline au test de Diebold-Mariano (p < 0,05).

**Conséquences.** Le produit ne répond plus à « faut-il s'attendre à une hausse ? ». Il répond à « à quel point cela risque-t-il de bouger ? ».
