resource "aws_bedrock_guardrail" "advice" {
  count                     = var.enable_guardrail ? 1 : 0
  name                      = var.project
  blocked_input_messaging   = "Requête refusée par les garde-fous."
  blocked_outputs_messaging = "Réponse refusée par les garde-fous."

  topic_policy_config {
    topics_config {
      name       = "conseil-investissement"
      type       = "DENY"
      definition = "Recommandation personnalisée d'acheter, de vendre ou de conserver un titre financier."
      examples   = ["Achetez cette action maintenant.", "Il faut vendre ce titre."]
    }
  }
}
