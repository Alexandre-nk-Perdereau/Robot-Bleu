import asyncio
import aiohttp
import json
import os
from robot_bleu.cogs.tts import TTS
from robot_bleu.config import MODE, GROQCLOUD_TOKEN, GROQCLOUD_MODEL, OLLAMA_HOST, OLLAMA_MODEL, MAX_CONTEXT_CHAR_LENGTH, CEREBRAS_API_KEY, CEREBRAS_MODEL
from robot_bleu.utils.context_management import save_context
import re

request_queue = asyncio.Queue()
voice_queues = {}

robot_bleu_path = os.path.join(os.path.dirname(__file__), "..", "..", "Robot Bleu.txt")

def extract_system_message(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            system_message_match = re.search(r'SYSTEM\s*(.*?)(?=\n\n|\Z)', content, re.DOTALL)
            if system_message_match:
                return system_message_match.group(1).strip()
            else:
                print("Aucun message système trouvé dans le fichier.")
                return None
    except FileNotFoundError:
        print(f"Le fichier {file_path} n'a pas été trouvé.")
        return None
    except Exception as e:
        print(f"Une erreur s'est produite lors de la lecture du fichier : {e}")
        return None

system_message = extract_system_message(robot_bleu_path)
print(system_message)

async def process_request_queue(bot):
    while True:
        prompt, channel_id = await request_queue.get()
        try:
            await process_message(prompt, channel_id, bot)
        except Exception as e:
            print(f"Erreur lors du traitement de la requête : {e}")
        finally:
            request_queue.task_done()

async def process_message(prompt, channel_id, bot):
    mode = bot.listening_channels[channel_id].get("mode", "streaming")
    channel = bot.get_channel(channel_id)
    if not channel:
        print(f"Erreur : le canal spécifié n'a pas été trouvé. ID: {channel_id}")
        return
    
    if mode == "streaming":
        if MODE == "ollama_mode":
            await stream_ollama_response(prompt, channel_id, bot)
        elif MODE == "cerebras_mode":
            await stream_cerebras_response(prompt, channel_id, bot)
        else:
            content = await generate_response(prompt, channel_id, bot)
            await send_response(channel, content)
    else:
        content = await generate_response(prompt, channel_id, bot)
        await send_response(channel, content)

async def send_response(channel, content):
    if content:
        chunks = [content[i:i+2000] for i in range(0, len(content), 2000)]
        for chunk in chunks:
            await channel.send(chunk.encode('utf-8').decode('utf-8'))

async def generate_response(prompt, channel_id, bot):
    if MODE == "ollama_mode":
        return await generate_ollama_response(prompt, channel_id, bot)
    elif MODE == "groqCloud_mode":
        return await generate_groq_response(prompt, channel_id, bot)
    elif MODE == "cerebras_mode":
        return await generate_cerebras_response(prompt, channel_id, bot)
    else:
        return "Mode non reconnu"

async def generate_ollama_response(prompt, channel_id, bot):
    async with aiohttp.ClientSession() as session:
        bot.listening_channels[channel_id]["messages"].append(
            {"role": "user", "content": prompt}
        )
        context_length = sum(
            len(message["content"])
            for message in bot.listening_channels[channel_id]["messages"]
        )
        while context_length > MAX_CONTEXT_CHAR_LENGTH:
            removed_message = bot.listening_channels[channel_id]["messages"].pop(0)
            context_length -= len(removed_message["content"])
        payload = {
            "model": OLLAMA_MODEL,
            "messages": bot.listening_channels[channel_id]["messages"],
            "stream": False,
        }
        try:
            async with session.post(
                f"{OLLAMA_HOST}/api/chat", json=payload
            ) as response:
                data = await response.json()
                bot.listening_channels[channel_id]["messages"].append(data["message"])
                await save_context(
                    channel_id, bot.listening_channels[channel_id]["messages"]
                )
                content = data.get("message", {}).get(
                    "content", "Je n'ai pas pu générer de réponse."
                )
                await queue_tts_response(content, channel_id, bot)
                return content
        except Exception as e:
            print(f"Erreur lors de l'appel à Ollama : {e}")
            return f"Désolé, une erreur s'est produite lors de la génération de la réponse: {e}"

async def generate_groq_response(prompt, channel_id, bot):
    async with aiohttp.ClientSession() as session:
        if "messages" not in bot.listening_channels[channel_id]:
            bot.listening_channels[channel_id]["messages"] = []
        bot.listening_channels[channel_id]["messages"].append(
            {"role": "user", "content": prompt}
        )
        context_length = sum(
            len(message["content"])
            for message in bot.listening_channels[channel_id]["messages"]
        )
        while context_length > MAX_CONTEXT_CHAR_LENGTH:
            removed_message = bot.listening_channels[channel_id]["messages"].pop(0)
            context_length -= len(removed_message["content"])
        payload = {
            "model": GROQCLOUD_MODEL,
            "messages": [{"role": "system", "content": system_message}] + bot.listening_channels[channel_id]["messages"],
            "temperature": 0.7,
            "max_tokens": 1000,
        }
        headers = {
            "Authorization": f"Bearer {GROQCLOUD_TOKEN}",
            "Content-Type": "application/json"
        }
        try:
            async with session.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json=payload,
                headers=headers
            ) as response:
                data = await response.json()
                content = data["choices"][0]["message"]["content"]
                bot.listening_channels[channel_id]["messages"].append(
                    {"role": "assistant", "content": content}
                )
                await save_context(
                    channel_id, bot.listening_channels[channel_id]["messages"]
                )
                await queue_tts_response(content, channel_id, bot)
                return content
        except Exception as e:
            print(f"Erreur lors de l'appel à Groq Cloud : {e}")
            return f"Désolé, une erreur s'est produite lors de la génération de la réponse: {e}"

async def generate_cerebras_response(prompt, channel_id, bot):
    async with aiohttp.ClientSession() as session:
        if "messages" not in bot.listening_channels[channel_id]:
            bot.listening_channels[channel_id]["messages"] = []
        bot.listening_channels[channel_id]["messages"].append(
            {"role": "user", "content": prompt}
        )
        context_length = sum(
            len(message["content"])
            for message in bot.listening_channels[channel_id]["messages"]
        )
        while context_length > MAX_CONTEXT_CHAR_LENGTH:
            removed_message = bot.listening_channels[channel_id]["messages"].pop(0)
            context_length -= len(removed_message["content"])
        payload = {
            "model": CEREBRAS_MODEL,
            "messages": [{"role": "system", "content": system_message}] + bot.listening_channels[channel_id]["messages"],
            "temperature": 0.7,
            "max_tokens": -1,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {CEREBRAS_API_KEY}",
            "Content-Type": "application/json"
        }
        try:
            async with session.post(
                "https://api.cerebras.ai/v1/chat/completions",
                json=payload,
                headers=headers
            ) as response:
                data = await response.json()
                content = data["choices"][0]["message"]["content"]
                bot.listening_channels[channel_id]["messages"].append(
                    {"role": "assistant", "content": content}
                )
                await save_context(
                    channel_id, bot.listening_channels[channel_id]["messages"]
                )
                await queue_tts_response(content, channel_id, bot)
                return content
        except Exception as e:
            print(f"Erreur lors de l'appel à Cerebras : {e}")
            return f"Désolé, une erreur s'est produite lors de la génération de la réponse: {e}"

async def stream_ollama_response(prompt, channel_id, bot):
    async with aiohttp.ClientSession() as session:
        bot.listening_channels[channel_id]["messages"].append(
            {"role": "user", "content": prompt}
        )
        context_length = sum(
            len(message["content"])
            for message in bot.listening_channels[channel_id]["messages"]
        )
        while context_length > MAX_CONTEXT_CHAR_LENGTH:
            removed_message = bot.listening_channels[channel_id]["messages"].pop(0)
            context_length -= len(removed_message["content"])
        payload = {
            "model": OLLAMA_MODEL,
            "messages": bot.listening_channels[channel_id]["messages"],
            "stream": True,
        }
        channel = bot.get_channel(channel_id)
        if not channel:
            print(f"Erreur : le canal spécifié n'a pas été trouvé. ID: {channel_id}")
            return
        try:
            current_message = await channel.send("Génération de la réponse en cours...")
            message_content = ""
            accumulated_response = ""
            async with session.post(
                f"{OLLAMA_HOST}/api/chat", json=payload
            ) as response:
                buffer = ""
                async for line in response.content:
                    if line:
                        data = json.loads(line)
                        if "message" in data:
                            content = data["message"].get("content", "")
                            if content:
                                accumulated_response += content
                                buffer += content
                                if len(buffer) >= 200:
                                    message_content += buffer
                                    if len(message_content) > 2000:
                                        await current_message.edit(
                                            content=message_content[:2000]
                                        )
                                        current_message = await channel.send(
                                            message_content[2000:]
                                        )
                                        message_content = message_content[2000:]
                                    else:
                                        await current_message.edit(
                                            content=message_content
                                        )
                                    buffer = ""
                if buffer:
                    message_content += buffer
                    if len(message_content) > 2000:
                        await current_message.edit(content=message_content[:2000])
                        await channel.send(message_content[2000:])
                    else:
                        await current_message.edit(content=message_content)
            if accumulated_response:
                bot.listening_channels[channel_id]["messages"].append(
                    {"role": "assistant", "content": accumulated_response}
                )
                await save_context(
                    channel_id, bot.listening_channels[channel_id]["messages"]
                )
                await queue_tts_response(accumulated_response, channel_id, bot)
        except Exception as e:
            print(f"Erreur lors de l'appel à Ollama : {e}")
            await channel.send(
                f"Désolé, une erreur s'est produite lors de la génération de la réponse: {e}"
            )

async def stream_cerebras_response(prompt, channel_id, bot):
    async with aiohttp.ClientSession() as session:
        bot.listening_channels[channel_id]["messages"].append(
            {"role": "user", "content": prompt}
        )
        context_length = sum(
            len(message["content"])
            for message in bot.listening_channels[channel_id]["messages"]
        )
        while context_length > MAX_CONTEXT_CHAR_LENGTH:
            removed_message = bot.listening_channels[channel_id]["messages"].pop(0)
            context_length -= len(removed_message["content"])
        payload = {
            "model": CEREBRAS_MODEL,
            "messages": [{"role": "system", "content": system_message}] + bot.listening_channels[channel_id]["messages"],
            "temperature": 0.7,
            "max_tokens": -1,
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {CEREBRAS_API_KEY}",
            "Content-Type": "application/json"
        }
        channel = bot.get_channel(channel_id)
        if not channel:
            print(f"Erreur : le canal spécifié n'a pas été trouvé. ID: {channel_id}")
            return
        try:
            current_message = await channel.send("Génération de la réponse en cours...")
            message_content = ""
            accumulated_response = ""
            buffer = ""
            async with session.post(
                "https://api.cerebras.ai/v1/chat/completions",
                json=payload,
                headers=headers
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Status code: {response.status}, Response: {error_text}")
                
                async for line in response.content:
                    if line:
                        line = line.decode('utf-8').strip()
                        if line.startswith("data: "):
                            try:
                                data = json.loads(line[6:])  # Skip "data: " prefix
                                if "choices" in data and len(data["choices"]) > 0:
                                    content = data["choices"][0].get("delta", {}).get("content", "")
                                    if content:
                                        accumulated_response += content
                                        buffer += content
                                        if len(buffer) >= 500:
                                            message_content += buffer
                                            if len(message_content) > 2000:
                                                await current_message.edit(content=message_content[:2000])
                                                current_message = await channel.send(message_content[2000:])
                                                message_content = message_content[2000:]
                                            else:
                                                await current_message.edit(content=message_content)
                                            buffer = ""
                            except json.JSONDecodeError as json_err:
                                print(f"Erreur de décodage JSON: {json_err}")
                                print(f"Ligne problématique: {line}")
                                continue

                if buffer:
                    message_content += buffer
                    if len(message_content) > 2000:
                        await current_message.edit(content=message_content[:2000])
                        await channel.send(message_content[2000:])
                    else:
                        await current_message.edit(content=message_content)
            
            if accumulated_response:
                bot.listening_channels[channel_id]["messages"].append(
                    {"role": "assistant", "content": accumulated_response}
                )
                await save_context(
                    channel_id, bot.listening_channels[channel_id]["messages"]
                )
                await queue_tts_response(accumulated_response, channel_id, bot)
            else:
                await channel.send("Désolé, je n'ai pas pu générer de réponse.")
        
        except Exception as e:
            print(f"Erreur lors de l'appel à Cerebras : {e}")
            await channel.send(
                f"Désolé, une erreur s'est produite lors de la génération de la réponse: {str(e)}"
            )

async def queue_tts_response(text, channel_id, bot):
    vc = bot.listening_channels[channel_id].get("voice_client")
    if vc:
        queue = voice_queues[vc.channel.id]
        tts_mode = bot.listening_channels[channel_id].get("tts_mode", "elevenlabs")
        elevenlabs_voice_id = bot.listening_channels[channel_id].get("elevenlabs_voice_id")
        await queue.put((text, tts_mode, elevenlabs_voice_id))
        if queue.qsize() == 1:
            await process_voice_queue(vc)

async def process_voice_queue(vc):
    queue = voice_queues[vc.channel.id]
    while not queue.empty():
        text, tts_mode, elevenlabs_voice_id = await queue.get()
        if tts_mode == "elevenlabs":
            success = await TTS.elevenlabs_tts(vc, text, voice_id=elevenlabs_voice_id)
            if not success:
                await TTS.basic_tts(vc, text)
        else:
            await TTS.basic_tts(vc, text)
        queue.task_done()

async def clear_voice_queue(channel_id):
    if channel_id in voice_queues:
        queue = voice_queues[channel_id]
        while not queue.empty():
            queue.get_nowait()
            queue.task_done()