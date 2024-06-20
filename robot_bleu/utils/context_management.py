import json


async def save_context(channel_id, context):
    with open(f"data/context_{channel_id}.txt", "w") as file:
        json.dump(context, file)


async def load_context(channel_id):
    try:
        with open(f"data/context_{channel_id}.txt", "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return []
