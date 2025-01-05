import discord
from discord.ext import commands
import yaml
import os

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


# Load Cogs
async def load_cogs():
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f'Loaded cog: {filename}')
            except Exception as e:
                print(f'❌ Failed to load cog {filename}: {e}')


# On ready
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} - {bot.user.id}')
    print('------')


# Run bot
async def main():
    async with bot:
        await load_cogs()
        await bot.start(config['token'])


import asyncio
asyncio.run(main())