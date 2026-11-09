# ADR 6 : S3 Vectors et RAG écrit par l'équipe

**Décision.** Index dans S3 Vectors, avec découpage, filtrage et diversification écrits dans le projet, sans Knowledge Base.

**Raisons.** Sans serveur, faible coût pour un petit corpus, [disponible à Paris](https://aws.amazon.com/blogs/aws/amazon-s3-vectors-now-generally-available-with-increased-scale-and-performance). Le cours note ce que l'équipe fait elle-même.

**Limite.** Pas de recherche hybride native : à réévaluer si le jeu de référence montre un manque de rappel.
