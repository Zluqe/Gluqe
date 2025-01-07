import discord
from discord.ext import commands
import json
import yaml

# Load configuration data from a YAML file
def load_config():
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)

# Load blacklist data from a JSON file
def load_blacklist():
    try:
        with open('data/blacklist.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def is_blacklisted():
    async def predicate(ctx):
        blacklist = load_blacklist()
        if ctx.author.id in blacklist:
            await ctx.send("You are blacklisted and cannot use this command.", ephemeral=True)
            return False
        return True
    return commands.check(predicate)

# Check if the user is the owner of the bot
def is_owner():
    async def predicate(ctx):
        if ctx.author.id in config['gluqe']['owner']:
            pass
        else:
            await ctx.send("You can not run this command due to restrictions set in place by the bot developer.", ephemeral=True)
            return False
        return True
    return commands.check(predicate)