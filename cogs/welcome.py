# imports
import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ext.commands import Context
import random
import yaml
import asyncio

# Load config
with open('config.yml', 'r') as f:
    config = yaml.safe_load(f)

class Buttons(discord.ui.View):
    def __init__(self, *, timeout = None):
        super().__init__(timeout=timeout)
    async def blurple_button(self,button:discord.ui.Button,interaction:discord.Interaction):
        button.disabled = False
        await interaction.response.send_message("Test")

class Welcome(commands.Cog):
    def __init__(self, bot):
    	self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        try:
            role = member.guild.get_role(config['roles']['join_role'])
            if role:
                await member.add_roles(role)
            channel = member.guild.get_channel(config['channels']['welcome'])
            if channel:
                embed = discord.Embed(
                    title=f"Welcome to {member.guild.name}!",
                    description=f"Welcome {member.mention} to Zluqe, we hope you enjoy your stay here!",
                    color=config['colors']['welcome']
                )
                embed.set_thumbnail(url=member.avatar.url)
                embed.set_footer(text="The first host to put the community first.")
                view=Buttons()
                view.add_item(discord.ui.Button(label="Our Website",style=discord.ButtonStyle.link,url="https://zluqe.org/"))
                view.add_item(discord.ui.Button(label="Our Panel",style=discord.ButtonStyle.link,url="https://panel.zluqe.org/"))
                view.add_item(discord.ui.Button(label="Terms of Service",style=discord.ButtonStyle.link,url="https://zluqe.org/tos"))
                await channel.send(embed=embed, view=view)
                await channel.send(f"{member.mention}", delete_after=0.01)
        except Exception as e:
            print(f"Failed: {e}")

async def setup(bot):
    await bot.add_cog(Welcome(bot))