import discord
from discord.ext import commands
import yaml
from src.modules.loader import load_cogs
from src.modules.launcher import setup_events, start

# Load config
with open('config.yml', 'r') as f:
    config = yaml.safe_load(f)

# Intents (required for newer versions of discord.py)
intents = discord.Intents.default()
intents.typing = False
intents.presences = False
intents.messages = True

# Create bot
bot = commands.Bot(command_prefix=config['prefix'], intents=intents)
bot.remove_command('help')


# Run bot
async def main():
    async with bot:
        await load_cogs(bot)
        await setup_events(bot)
        await start(bot, config['token'])


import asyncio
asyncio.run(main())