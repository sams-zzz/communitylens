# Guide de déploiement

Rien de ce guide n'a encore été exécuté sur un vrai compte AWS. Attendez-vous à quelques corrections au premier passage, notamment sur les ressources S3 Vectors dans Terraform.

## Avant de commencer

1. Vérifiez la date de fin de votre plan AWS : le plan gratuit [peut suspendre le compte](https://aws.amazon.com/free/free-tier-faqs/) à son terme. Demandez aussi à votre professeur si l'école fournit un compte.
2. Vérifiez dans la console Bedrock que Nova Micro et Titan Text Embeddings V2 sont utilisables depuis Paris.
3. Créez un bucket pour l'état Terraform.

## Étape 1 : prototype sur EC2

Le moyen le plus rapide d'avoir une démo en ligne et de tester Yahoo Finance depuis AWS.

```bash
cd infra/terraform
terraform init -backend-config="bucket=VOTRE_BUCKET" -backend-config="key=communitylens.tfstate" -backend-config="region=eu-west-3"
terraform apply -var enable_ec2=true -var ec2_ingress_cidr=VOTRE_IP/32
```

Connectez-vous à l'instance par Session Manager, puis :

```bash
git clone VOTRE_DEPOT && cd communitylens
python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[job]"
python -c "from communitylens.ingestion.prices import download_prices; print(download_prices(['AAPL'])[0].tail())"
make demo
sudo docker compose up -d --build
```

La dernière commande Python est le test le plus important : elle montre si Yahoo Finance répond depuis AWS. **Si elle échoue**, exécutez le job depuis un poste de l'équipe, puis envoyez le fichier Parquet dans S3.

## Étape 2 : serverless

```bash
# 1. Créer ECR et le stockage, sans les fonctions
terraform apply

# 2. Publier les images
aws ecr get-login-password | docker login --username AWS --password-stdin COMPTE.dkr.ecr.eu-west-3.amazonaws.com
docker build --provenance=false -f docker/api.Dockerfile -t COMPTE.dkr.ecr.eu-west-3.amazonaws.com/communitylens-api:v1 .
docker build --provenance=false -f docker/job.Dockerfile -t COMPTE.dkr.ecr.eu-west-3.amazonaws.com/communitylens-job:v1 .
docker push COMPTE.dkr.ecr.eu-west-3.amazonaws.com/communitylens-api:v1
docker push COMPTE.dkr.ecr.eu-west-3.amazonaws.com/communitylens-job:v1

# 3. Créer les fonctions, l'API et CloudFront
terraform apply -var image_tag=v1 -var budget_email=VOUS@example.org

# 4. Publier le site et les résultats
aws s3 sync ../../frontend "s3://$(terraform output -raw site_bucket)" --delete
aws s3 cp ../../results/forecast_eval.json "s3://$(terraform output -raw data_bucket)/serving/metrics.json"

# 5. Lancer le job une première fois
aws lambda invoke --function-name "$(terraform output -raw job_function)" --cli-read-timeout 900 /dev/stdout
```

Ensuite, `github_repository` crée le rôle OIDC et le workflow `Déploiement` prend le relais. Renseignez les variables GitHub `AWS_DEPLOY_ROLE`, `TF_STATE_BUCKET` et `BUDGET_EMAIL`.

## Coûts à surveiller

Créez l'alerte budget dès le premier jour. Détruisez ce qui ne sert plus avec `terraform destroy`, en particulier l'instance EC2.

## Avant la soutenance

- [ ] Lancer le job la veille et vérifier la date affichée
- [ ] Ouvrir une fois chaque titre de la démo pour remplir le cache
- [ ] Préparer la vidéo de secours
- [ ] Vérifier que la version en ligne n'affiche pas le bandeau de démo

## Scan de sécurité de l'infrastructure

`checkov` signale 41 points sur 211 contrôles. La plupart relèvent d'exigences d'entreprise jugées disproportionnées ici : clés KMS dédiées, WAF, VPC, conservation d'un an. Le rôle de déploiement GitHub utilise `AdministratorAccess`, limité à la branche `main` : c'est un compromis assumé, à justifier devant le jury.
