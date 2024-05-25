import discord
from discord.ext import commands
import aiohttp
import json
import re
import asyncio


intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='$', intents=intents)
bot.channel_id = None
bot.listening_channels = {}
request_queue = asyncio.Queue()

max_context_length = 8192 * 2

async def process_request_queue():
    while True:
        user_name, prompt, channel_id = await request_queue.get()
        try:
            await stream_response(user_name, prompt, channel_id)
        except Exception as e:
            print(f"Erreur lors du traitement de la requête : {e}")
        finally:
            request_queue.task_done()

@bot.event
async def on_ready():
    print(f'Bot connecté en tant que {bot.user.name}')
    for channel_id in bot.listening_channels:
        bot.listening_channels[channel_id] = await load_context(channel_id)
    await create_model()
    bot.loop.create_task(process_request_queue())

@bot.command(name='listen')
async def listen(ctx, url: str):
    print(f"Commande listen déclenchée avec l'URL: {url}")
    match = re.search(r"https://discord\.com/channels/\d+/(?P<channel_id>\d+)", url)
    if match:
        channel_id = int(match.group('channel_id'))
        print(f"ID du canal extrait: {channel_id}")
        channel = bot.get_channel(channel_id)
        if channel:
            print(f"Canal récupéré: {channel.name}")
            try:
                if channel.id not in bot.listening_channels:
                    bot.listening_channels[channel.id] = []
                    await ctx.send(f"Je vais maintenant écouter le salon {channel.mention}")
                else:
                    await ctx.send(f"J'écoute déjà le salon {channel.mention}")
            except Exception as e:
                await ctx.send(f"Une erreur inattendue est survenue: {str(e)}")
        else:
            await ctx.send("Erreur : Le canal spécifié n'a pas été trouvé. Veuillez vérifier le lien.")
    else:
        await ctx.send("L'URL fournie ne semble pas être un lien de canal Discord valide. Assurez-vous que le format est correct.")



@bot.command(name='pause_listen')
async def pause_listen(ctx, url: str):
    match = re.search(r"https://discord\.com/channels/\d+/(?P<channel_id>\d+)", url)
    if match:
        channel_id = int(match.group('channel_id'))
        channel = bot.get_channel(channel_id)
        if channel:
            if channel.id in bot.listening_channels:
                del bot.listening_channels[channel.id]
                await ctx.send(f"J'ai mis en pause l'écoute du salon {channel.mention}")
            else:
                await ctx.send(f"Je n'écoutais pas le salon {channel.mention}")
        else:
            await ctx.send("Erreur : Le canal spécifié n'a pas été trouvé. Veuillez vérifier le lien.")
    else:
        await ctx.send("L'URL fournie ne semble pas être un lien de canal Discord valide. Assurez-vous que le format est correct.")

@bot.command(name='stop_listen')
async def stop_listen(ctx, url: str):
    match = re.search(r"https://discord\.com/channels/\d+/(?P<channel_id>\d+)", url)
    if match:
        channel_id = int(match.group('channel_id'))
        channel = bot.get_channel(channel_id)
        if channel:
            if channel.id in bot.listening_channels:
                del bot.listening_channels[channel.id]
                await save_context(channel.id, [])
                await ctx.send(f"J'ai arrêté d'écouter le salon {channel.mention} et supprimé son contexte")
            else:
                await ctx.send(f"Je n'écoutais pas le salon {channel.mention}")
        else:
            await ctx.send("Erreur : Le canal spécifié n'a pas été trouvé. Veuillez vérifier le lien.")
    else:
        await ctx.send("L'URL fournie ne semble pas être un lien de canal Discord valide. Assurez-vous que le format est correct.")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if message.content.startswith(("!", "%", "$", "(ignore)")) or message.reference is not None:
        await bot.process_commands(message)
        return

    if message.channel.id in bot.listening_channels:
        # Envoi du message à l'API d'Ollama
        await request_queue.put((message.author.name, message.content, message.channel.id))
        # response = await generate_response(message.author.name, message.content, message.channel.id)
        # if response != '':
        #     # Envoi de la réponse dans le salon Discord
        #     await message.channel.send(response)

    await bot.process_commands(message)

async def generate_response(user_name, prompt, channel_id):
    async with aiohttp.ClientSession() as session:
        bot.listening_channels[channel_id].append({"role": "user", "content": f"{user_name}: {prompt}"})

        context_length = sum(len(message["content"]) for message in bot.listening_channels[channel_id])

        while context_length > max_context_length:
            removed_message = bot.listening_channels[channel_id].pop(0)
            context_length -= len(removed_message["content"])
    
        payload = {
            "model": "RobotBleu",
            "messages": bot.listening_channels[channel_id],
            "stream": False
        }
        try:
            async with session.post('http://localhost:11434/api/chat', json=payload) as response:
                data = await response.json()
                bot.listening_channels[channel_id].append(data['message'])
                await save_context(channel_id, bot.listening_channels[channel_id])
                return data.get('message', {}).get('content', "Je n'ai pas pu générer de réponse.")
        except Exception as e:
            print(f"Erreur lors de l'appel à Ollama : {e}")
            return f"Désolé, une erreur s'est produite lors de la génération de la réponse: {e}"
        
async def stream_response(user_name, prompt, channel_id):
    async with aiohttp.ClientSession() as session:
        bot.listening_channels[channel_id].append({"role": "user", "content": f"{user_name}: {prompt}"})

        context_length = sum(len(message["content"]) for message in bot.listening_channels[channel_id])

        while context_length > max_context_length:
            removed_message = bot.listening_channels[channel_id].pop(0)
            context_length -= len(removed_message["content"])

        payload = {
            "model": "RobotBleu",
            "messages": bot.listening_channels[channel_id],
            "stream": True
        }
        
        channel = bot.get_channel(channel_id)
        if not channel:
            print(f"Erreur : le canal spécifié n'a pas été trouvé. ID: {channel_id}")
            return
        
        try:
            current_message = await channel.send("Génération de la réponse en cours...")
            message_content = ""
            accumulated_response = ""

            async with session.post('http://localhost:11434/api/chat', json=payload) as response:
                buffer = ""
                async for line in response.content:
                    if line:
                        data = json.loads(line)
                        if 'message' in data:
                            content = data['message'].get('content', '')
                            if content:
                                accumulated_response += content
                                buffer += content

                                # limit the calls to discord api
                                if len(buffer) >= 200:
                                    message_content += buffer
                                    if len(message_content) > 2000:
                                        await current_message.edit(content=message_content[:2000])
                                        current_message = await channel.send(message_content[2000:])
                                        message_content = message_content[2000:]
                                    else:
                                        await current_message.edit(content=message_content)
                                    buffer = ""

                if buffer:
                    message_content += buffer
                    if len(message_content) > 2000:
                        await current_message.edit(content=message_content[:2000])
                        await channel.send(message_content[2000:])
                    else:
                        await current_message.edit(content=message_content)

            if accumulated_response:
                bot.listening_channels[channel_id].append({"role": "assistant", "content": accumulated_response})
                await save_context(channel_id, bot.listening_channels[channel_id])

        except Exception as e:
            print(f"Erreur lors de l'appel à Ollama : {e}")
            await channel.send(f"Désolé, une erreur s'est produite lors de la génération de la réponse: {e}")

        
async def save_context(channel_id, context):
    with open(f"context_{channel_id}.txt", "w") as file:
        file.write(json.dumps(context))
    return

async def load_context(channel_id):
    try:
        with open(f"context_{channel_id}.txt", "r") as file:
            return json.loads(file.read())
    except FileNotFoundError:
        return []

async def destroy_model():
    try:
        async with aiohttp.ClientSession() as session:
            # Supprimer le modèle existant s'il existe
            async with session.delete('http://localhost:11434/api/delete', json={"name": "RobotBleu"}) as response:
                if response.status == 200:
                    print("Modèle RobotBleu supprimé avec succès")
                elif response.status == 404:
                    print("Le modèle RobotBleu n'existait pas")
                else:
                    print(f"Erreur lors de la suppression du modèle : {response.status}")

            # Créer le nouveau modèle
    except Exception as e:
        print(f"Erreur lors de la création du modèle : {e}")
    return

async def create_model():
    try:
        with open("Robot Bleu.txt", "r") as file:
            modelfile = file.read()
        async with aiohttp.ClientSession() as session:
            payload = {
                "name": "RobotBleu",
                "modelfile": modelfile,
                "stream": False
            }
            async with session.post('http://localhost:11434/api/create', json=payload) as response:
                if response.status == 200:
                    print("Modèle RobotBleu créé avec succès")
                else:
                    print(f"Erreur lors de la création du modèle : {response.status}")
    except Exception as e:
        print(f"Erreur lors de la création du modèle : {e}")
    return
    
@bot.command(name='refresh_model')
async def refresh_model(ctx):
    await destroy_model()
    await create_model()
    await ctx.send("Le modèle RobotBleu a été rafraîchi.")

with open('token.txt', 'r') as file:
    token = file.read().strip()

bot.run(token)

