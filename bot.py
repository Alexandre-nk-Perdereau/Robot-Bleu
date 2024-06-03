import discord
from discord.ext import commands
import aiohttp
import json
import asyncio
import pyttsx3

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='$', intents=intents)
bot.channel_id = None
bot.listening_channels = {}
request_queue = asyncio.Queue()
voice_queues = {}

max_context_length = 8192 * 2

engine = pyttsx3.init()
voices = engine.getProperty('voices')
# Set default voice
engine.setProperty('voice', voices[0].id)

async def process_request_queue():
    while True:
        user_name, prompt, channel_id = await request_queue.get()
        try:
            await process_message(user_name, prompt, channel_id)
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
async def listen(ctx):
    channel_id = ctx.channel.id
    channel = bot.get_channel(channel_id)
    voice_channel = ctx.author.voice.channel if ctx.author.voice else None
    if channel:
        try:
            if channel.id not in bot.listening_channels:
                bot.listening_channels[channel.id] = {"messages": [], "mode": "streaming"}
                await ctx.send(f"Je vais maintenant écouter le salon {channel.mention}")

                if voice_channel:
                    vc = await voice_channel.connect()
                    bot.listening_channels[channel.id]['voice_client'] = vc
                    voice_queues[vc.channel.id] = asyncio.Queue()

            else:
                await ctx.send(f"J'écoute déjà le salon {channel.mention}")
        except Exception as e:
            await ctx.send(f"Une erreur inattendue est survenue: {str(e)}")
    else:
        await ctx.send("Erreur : Le canal spécifié n'a pas été trouvé.")

@bot.command(name='pause_listen')
async def pause_listen(ctx):
    channel_id = ctx.channel.id
    channel = bot.get_channel(channel_id)
    if channel:
        if channel.id in bot.listening_channels:
            vc = bot.listening_channels[channel.id].get('voice_client')
            if vc:
                await vc.disconnect()
                await clear_voice_queue(vc.channel.id)
            del bot.listening_channels[channel.id]
            await ctx.send(f"J'ai mis en pause l'écoute du salon {channel.mention}")
        else:
            await ctx.send(f"Je n'écoutais pas le salon {channel.mention}")
    else:
        await ctx.send("Erreur : Le canal spécifié n'a pas été trouvé.")

@bot.command(name='stop_listen')
async def stop_listen(ctx):
    channel_id = ctx.channel.id
    channel = bot.get_channel(channel_id)
    if channel:
        if channel.id in bot.listening_channels:
            vc = bot.listening_channels[channel.id].get('voice_client')
            if vc:
                await vc.disconnect()
                await clear_voice_queue(vc.channel.id)
            del bot.listening_channels[channel.id]
            await save_context(channel.id, [])
            await ctx.send(f"J'ai arrêté d'écouter le salon {channel.mention} et supprimé son contexte")
        else:
            await ctx.send(f"Je n'écoutais pas le salon {channel.mention}")
    else:
        await ctx.send("Erreur : Le canal spécifié n'a pas été trouvé.")

@bot.command(name='set_mode')
async def set_mode(ctx, mode: str):
    channel_id = ctx.channel.id
    channel = bot.get_channel(channel_id)
    if channel:
        if mode.lower() in ["streaming", "non-streaming"]:
            if channel.id in bot.listening_channels:
                bot.listening_channels[channel.id]["mode"] = mode.lower()
                await ctx.send(f"Le mode du salon {channel.mention} a été défini sur {mode.lower()}")
            else:
                await ctx.send(f"Je n'écoute pas le salon {channel.mention}")
        else:
            await ctx.send("Mode invalide. Utilisez 'streaming' ou 'non-streaming'.")
    else:
        await ctx.send("Erreur : Le canal spécifié n'a pas été trouvé.")

@bot.command(name='set_voice')
async def set_voice(ctx, voice_index: int):
    try:
        engine.setProperty('voice', voices[voice_index].id)
        await ctx.send(f"Voix définie sur : {voices[voice_index].name}")
    except IndexError:
        await ctx.send(f"Index de voix invalide. Veuillez choisir un index entre 0 et {len(voices) - 1}.")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if message.content.startswith(("!", "%", "$", "(ignore)")) or message.reference is not None:
        await bot.process_commands(message)
        return

    if message.channel.id in bot.listening_channels:
        await request_queue.put((message.author.name, message.content, message.channel.id))

    await bot.process_commands(message)

async def process_message(user_name, prompt, channel_id):
    mode = bot.listening_channels[channel_id].get("mode", "streaming")
    if mode == "streaming":
        await stream_response(user_name, prompt, channel_id)
    else:
        await generate_response(user_name, prompt, channel_id)

async def generate_response(user_name, prompt, channel_id):
    async with aiohttp.ClientSession() as session:
        bot.listening_channels[channel_id]["messages"].append({"role": "user", "content": f"{user_name}: {prompt}"})

        context_length = sum(len(message["content"]) for message in bot.listening_channels[channel_id]["messages"])

        while context_length > max_context_length:
            removed_message = bot.listening_channels[channel_id]["messages"].pop(0)
            context_length -= len(removed_message["content"])
    
        payload = {
            "model": "RobotBleu",
            "messages": bot.listening_channels[channel_id]["messages"],
            "stream": False
        }
        try:
            async with session.post('http://localhost:11434/api/chat', json=payload) as response:
                data = await response.json()
                bot.listening_channels[channel_id]["messages"].append(data['message'])
                await save_context(channel_id, bot.listening_channels[channel_id]["messages"])
                content = data.get('message', {}).get('content', "Je n'ai pas pu générer de réponse.")
                await queue_tts_response(content, channel_id)
                return content
        except Exception as e:
            print(f"Erreur lors de l'appel à Ollama : {e}")
            return f"Désolé, une erreur s'est produite lors de la génération de la réponse: {e}"

async def stream_response(user_name, prompt, channel_id):
    async with aiohttp.ClientSession() as session:
        bot.listening_channels[channel_id]["messages"].append({"role": "user", "content": f"{user_name}: {prompt}"})

        context_length = sum(len(message["content"]) for message in bot.listening_channels[channel_id]["messages"])

        while context_length > max_context_length:
            removed_message = bot.listening_channels[channel_id]["messages"].pop(0)
            context_length -= len(removed_message["content"])

        payload = {
            "model": "RobotBleu",
            "messages": bot.listening_channels[channel_id]["messages"],
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
                bot.listening_channels[channel_id]["messages"].append({"role": "assistant", "content": accumulated_response})
                await save_context(channel_id, bot.listening_channels[channel_id]["messages"])
                await queue_tts_response(accumulated_response, channel_id)

        except Exception as e:
            print(f"Erreur lors de l'appel à Ollama : {e}")
            await channel.send(f"Désolé, une erreur s'est produite lors de la génération de la réponse: {e}")

async def queue_tts_response(text, channel_id):
    vc = bot.listening_channels[channel_id].get('voice_client')
    if vc:
        queue = voice_queues[vc.channel.id]
        await queue.put(text)
        if queue.qsize() == 1:
            await process_voice_queue(vc)

async def process_voice_queue(vc):
    queue = voice_queues[vc.channel.id]
    while not queue.empty():
        text = await queue.get()
        engine.save_to_file(text, 'response.mp3')
        engine.runAndWait()
        vc.play(discord.FFmpegPCMAudio('response.mp3'))
        while vc.is_playing():
            await asyncio.sleep(1)
        queue.task_done()

async def clear_voice_queue(channel_id):
    if channel_id in voice_queues:
        queue = voice_queues[channel_id]
        while not queue.empty():
            queue.get_nowait()
            queue.task_done()

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
