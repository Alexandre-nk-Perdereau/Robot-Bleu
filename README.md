# Robot Bleu

Bot Discord conversationnel agentique utilisant un serveur LLM local (vLLM, OpenAI-compatible).

## Fonctionnement

Le bot collecte les événements Discord (messages, réactions) et les traite périodiquement via le LLM. À chaque tick, l'agent décide d'agir ou non : envoyer un message, réagir avec un emoji, chercher sur le web, ou ne rien faire.

## Installation

```bash
uv sync
cp .env.example .env  # configurer les variables
uv run robot-bleu
```

## Configuration (.env)

| Variable | Description |
|---|---|
| `DISCORD_TOKEN` | Token du bot Discord |
| `OPENAI_COMPATIBLE` | Adresse du serveur LLM (ex: `192.168.1.14:8000`) |
| `LLM_MODEL` | Modèle servi par vLLM |
| `LLM_MAX_TOKENS` | Max tokens de sortie par requête |
| `AGENT_TICK_INTERVAL` | Intervalle entre chaque tick (secondes) |
| `DEFAULT_PERSONA` | Persona par défaut du bot |

## Commandes Discord

| Commande | Description |
|---|---|
| `/bleu_on` | Activer le bot (mode server ou channel) |
| `/bleu_off` | Désactiver le bot |
| `/bleu_status` | Voir le statut |
| `/bleu_persona` | Changer le persona |
| `/bleu_clear` | Effacer l'historique |
| `/bleu_history` | Consulter l'historique |
