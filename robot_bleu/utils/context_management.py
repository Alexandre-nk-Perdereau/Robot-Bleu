import json

async def save_context(channel_id, context):
    with open(f"data/context_{channel_id}.txt", "w", encoding='utf-8') as file:
        json.dump(context, file, ensure_ascii=False)

async def load_context(channel_id):
    try:
        with open(f"data/context_{channel_id}.txt", "r", encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        return []