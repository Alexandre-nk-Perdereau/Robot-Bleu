import aiohttp
from discord.ext import commands


class ModelManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="refresh_model")
    async def refresh_model(self, ctx):
        await destroy_model()
        await create_model()
        await ctx.send("Le modèle RobotBleu a été rafraîchi.")


async def destroy_model():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(
                "http://localhost:11434/api/delete", json={"name": "RobotBleu"}
            ) as response:
                if response.status == 200:
                    print("Modèle RobotBleu supprimé avec succès")
                elif response.status == 404:
                    print("Le modèle RobotBleu n'existait pas")
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
            payload = {"name": "RobotBleu", "modelfile": modelfile, "stream": False}
            async with session.post(
                "http://localhost:11434/api/create", json=payload
            ) as response:
                if response.status == 200:
                    print("Modèle RobotBleu créé avec succès")
                else:
                    print(f"Erreur lors de la création du modèle : {response.status}")
    except Exception as e:
        print(f"Erreur lors de la création du modèle : {e}")


async def setup(bot):
    await bot.add_cog(ModelManagement(bot))
