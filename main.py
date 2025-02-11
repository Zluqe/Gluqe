import discord, random, os, yaml, asyncio
from discord.ext import commands
from discord import app_commands

# Load config
with open('config.yml', 'r') as f:
    config = yaml.safe_load(f)

# Intents
intents = discord.Intents.all()

# Create bot
bot = commands.Bot(command_prefix=config['gluqe']['prefix'], intents=intents)
bot.remove_command('help')

# Background task to rotate activities
async def rotate_activity():
    await bot.wait_until_ready()  # Ensure the bot is fully ready before starting the task
    while not bot.is_closed():
        random_activity = random.choice(config['gluqe'].get('activity', ["No activities found"]))
        await bot.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name=random_activity)
        )
        await asyncio.sleep(15)  # Wait for 15 seconds before changing again

# On ready
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} - {bot.user.id}')
    print(f'Version: {discord.__version__}')
    try:
        # Sync commands with Discord
        # guild = discord.Object(id=config['server']['id'])
        # bot.tree.copy_global_to(guild=guild)
        # synced = await bot.tree.sync(guild=guild)
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} commands')
    except Exception as e:
        print(f'Failed to sync commands: {e}')
    print('------')
    bot.loop.create_task(rotate_activity())
    
# Load Cogs
async def load_cogs():
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f'Loaded cog: {filename}')
            except Exception as e:
                print(f'Failed to load cog {filename}: {e}')
    
# Run bot
async def main():
    async with bot:
        await load_cogs()
        await bot.start(config['gluqe']['token'])


import asyncio
asyncio.run(main())