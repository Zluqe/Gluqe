import discord
from discord.ext import commands

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        # Get the 'welcome' channel by name
        channel = discord.utils.get(member.guild.text_channels, name='welcome')
        
        # If the 'welcome' channel doesn't exist, print an error message and return
        if channel is None:
            print(f"Welcome channel not found in guild: {member.guild.name}")
            return

        # Send the welcome message
        await channel.send(f'Welcome {member.mention}!')

# Setup function
async def setup(bot):
    await bot.add_cog(Welcome(bot))

