import aiohttp
from discord.ext import commands
from robot_bleu.config import OLLAMA_HOST, OLLAMA_MODEL, MAX_CONTEXT_TOKEN_LENGTH, MAX_CONTEXT_CHAR_LENGTH, MODE

class ModelManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="refresh_model")
    async def refresh_model(self, ctx):
        if MODE != "ollama_mode":
            await ctx.send(f"Le mode actuel est {MODE}. La commande refresh_model n'est disponible qu'en mode Ollama.")
            return
        await destroy_model()
        await create_model()
        await ctx.send("Le modèle RobotBleu a été rafraîchi.")

    @commands.command(name="switch_ollama")
    async def switch_ollama(self, ctx, new_host: str = None, new_model: str = None, new_context_size: int = None):
        global OLLAMA_HOST, OLLAMA_MODEL, MAX_CONTEXT_TOKEN_LENGTH, MAX_CONTEXT_CHAR_LENGTH
        if MODE != "ollama_mode":
            await ctx.send(f"Le mode actuel est {MODE}. La commande switch_ollama n'est disponible qu'en mode Ollama.")
            return
        if new_host:
            OLLAMA_HOST = new_host
        if new_model:
            OLLAMA_MODEL = new_model
        if new_context_size:
            MAX_CONTEXT_TOKEN_LENGTH = new_context_size
            MAX_CONTEXT_CHAR_LENGTH = MAX_CONTEXT_TOKEN_LENGTH * 2
        await ctx.send(f"Configuration Ollama mise à jour. Host: {OLLAMA_HOST}, Modèle: {OLLAMA_MODEL}, Context Size in token: {MAX_CONTEXT_TOKEN_LENGTH}, Context Size in char: {MAX_CONTEXT_CHAR_LENGTH}")

    @commands.command(name="switch_mode")
    async def switch_mode(self, ctx, new_mode: str):
        global MODE
        if new_mode in ["ollama_mode", "groqCloud_mode", "cerebras_mode"]:
            old_mode = MODE
            MODE = new_mode
            await ctx.send(f"Mode de génération changé de {old_mode} à {new_mode}")
            if new_mode == "ollama_mode":
                await create_model()
            elif old_mode == "ollama_mode":
                await destroy_model()
        else:
            await ctx.send("Mode non reconnu. Utilisez 'ollama_mode', 'groqCloud_mode', ou 'cerebras_mode'.")

async def destroy_model():
    if MODE != "ollama_mode":
        print(f"Le mode actuel est {MODE}. Pas de destruction de modèle Ollama nécessaire.")
        return
    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(
                f"{OLLAMA_HOST}/api/delete", json={"name": OLLAMA_MODEL}
            ) as response:
                if response.status == 200:
                    print(f"Modèle {OLLAMA_MODEL} supprimé avec succès")
                elif response.status == 404:
                    print(f"Le modèle {OLLAMA_MODEL} n'existait pas")
                else:
                    print(
                        f"Erreur lors de la suppression du modèle : {response.status}"
                    )
    except Exception as e:
        print(f"Erreur lors de la suppression du modèle : {e}")

async def create_model():
    if MODE != "ollama_mode":
        print(f"Le mode actuel est {MODE}. Pas de création de modèle Ollama nécessaire.")
        return
    try:
        with open("Robot Bleu.txt", "r") as file:
            modelfile = file.read()
        async with aiohttp.ClientSession() as session:
            payload = {"name": OLLAMA_MODEL, "modelfile": modelfile, "stream": False}
            async with session.post(
                f"{OLLAMA_HOST}/api/create", json=payload
            ) as response:
                if response.status == 200:
                    print(f"Modèle {OLLAMA_MODEL} créé avec succès")
                else:
                    print(f"Erreur lors de la création du modèle : {response.status}")
    except Exception as e:
        print(f"Erreur lors de la création du modèle : {e}")

async def setup(bot):
    await bot.add_cog(ModelManagement(bot))