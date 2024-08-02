import aiohttp
from discord.ext import commands
from robot_bleu.config import OLLAMA_HOST, OLLAMA_MODEL, OLLAMA_CONTEXT_SIZE

class ModelManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="refresh_model")
    async def refresh_model(self, ctx):
        await destroy_model()
        await create_model()
        await ctx.send("Le modèle RobotBleu a été rafraîchi.")

    @commands.command(name="switch_ollama")
    async def switch_ollama(self, ctx, new_host: str = None, new_model: str = None, new_context_size: int = None):
        global OLLAMA_HOST, OLLAMA_MODEL, OLLAMA_CONTEXT_SIZE
        
        if new_host:
            OLLAMA_HOST = new_host
        if new_model:
            OLLAMA_MODEL = new_model
        if new_context_size:
            OLLAMA_CONTEXT_SIZE = new_context_size
        
        await ctx.send(f"Configuration Ollama mise à jour. Host: {OLLAMA_HOST}, Modèle: {OLLAMA_MODEL}, Context Size: {OLLAMA_CONTEXT_SIZE}")

async def destroy_model():
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
