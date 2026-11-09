# ADR 4 : le LLM ne calcule rien et sa sortie est vérifiée

**Décision.** Le LLM reçoit des faits calculés et des passages traités comme des données non fiables. Il répond en JSON. Le code rejette tout chiffre, source ou formulation hors règles, redemande une fois, puis publie un texte écrit par le code.

**Mesure.** Face à un modèle simulé entièrement détourné, 10 attaques sur 12 sont arrêtées : 5 à l'ingestion, 5 par le vérificateur.

**Limites connues.** Deux attaques passent : un conseil formulé sans mot interdit, et une rumeur classée « soutenue » avec un faux lien vers un vrai fait. Le code contrôle la forme, pas le sens : seul le jeu de référence annoté mesure le sens.
