from discord.ext import commands
from robot_bleu.config import COMMAND_PREFIX, INTENTS, DISCORD_TOKEN, MODE
from robot_bleu.cogs.model_management import create_model

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=INTENTS)

@bot.event
async def on_ready():
    print(f"Bot connecté en tant que {bot.user.name}")
    await setup_bot()

async def setup_bot():
    await bot.load_extension("robot_bleu.cogs.listener")
    await bot.load_extension("robot_bleu.cogs.tts")
    await bot.load_extension("robot_bleu.cogs.model_management")
    
    if MODE == "ollama_mode":
        await create_model()
    else:
        print(f"Mode actuel : {MODE}. Pas de création de modèle Ollama nécessaire.")

def start():
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    start()