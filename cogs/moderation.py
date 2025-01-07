# imports
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from helpers.checks import is_blacklisted, is_owner, load_blacklist
import asyncio
import json
import re
import yaml

# Load configuration data from a YAML file
def load_config():
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'Loaded Cog Moderation')

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return

        # Check for prohibited file extensions in attachments
        prohibited_extensions = ['.exe', '.bat', '.msi', '.vbs', '.sh', '.py', '.cmd', '.scr', '.java', '.c', '.cpp', '.cs', '.js']
        if any(attachment.filename.lower().endswith(tuple(prohibited_extensions)) for attachment in message.attachments):
            warning_msg = f"{message.author.mention}, your message was deleted due to an attachment with a prohibited file extension."
            await message.delete()
            await message.channel.send(warning_msg, delete_after=15)
            return

        # Check for people pinging others
        if message.mentions:
            if len(message.mentions) == 1 and message.mentions[0] == message.author:
                pass
            # this role id is allowed to ping others
            elif 1324991942576177307 in [role.id for role in message.author.roles]:
                pass
            # if people ping the bot itself
            elif self.bot.user in message.mentions:
                pass
            # if someone with role id 1231231 is pinged, send a message
            elif any(role.id == 1324991942576177307 for role in message.mentions[0].roles):
                await asyncio.sleep(1)
                warning_msg = "Please be patient and **avoid pinging staff unnecessarily**. Staff will respond when they have time and see the message."
                await message.reply(warning_msg, ephemeral=True)

        # Check for IP addresses (IPv4 format)
        ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
        if re.search(ip_pattern, message.content):
            warning_msg = f"{message.author.mention}, Your message was deleted due to the reason of containing an IP address."
            await message.delete()
            await message.channel.send(warning_msg, delete_after=15)
            return

    def save_blacklist(self, blacklist):
        with open('data/blacklist.json', 'w') as f:
            json.dump(blacklist, f)

    @commands.hybrid_command(name="blacklist")
    @is_owner()
    async def blacklist(self, ctx, user: discord.User):
        """
        Blacklist a user from using the bot.
        """
        try:
            blacklist = load_blacklist()
            if user.id not in blacklist:
                blacklist.append(user.id)
                self.save_blacklist(blacklist)
                await ctx.reply(f"{user.name} has been blacklisted.")
            else:
                try:
                    blacklist = load_blacklist()
                    if user.id in blacklist:
                        blacklist.remove(user.id)
                        self.save_blacklist(blacklist)
                        await ctx.reply(f"{user.name} has been removed from the blacklist.")
                    else:
                        await ctx.reply(f"Legacy Code, If i remove everything will break.")
                except Exception as e:
                    print(e)                
        except Exception as e:
            print(e)

async def setup(bot):
    await bot.add_cog(Moderation(bot))