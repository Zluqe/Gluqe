import discord
from discord.ext import commands, tasks
from datetime import datetime
from src.utils.files_loader import file_loader
import json

class BumpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bump_check.start()  # Start the background task after initialization
    
    # Load config.yml
    config = file_loader('./config.yml')
    
    CHANNELID = 1324979225098453032
    SERVERID = 1324888658016211005

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == 302050872383242240:  # Bump bot ID
            if message.embeds and 'Bump done! :thumbsup:' in message.embeds[0].description:
                try:
                    timedata = file_loader('./src/data/bumptime.json')
                    timedata["lastbump"] = str(datetime.utcnow())
                    with open(r'./src/data/bumptime.json', 'w') as file:
                        json.dump(timedata, file, indent=4)
                except Exception as e:
                    print(f"Failed to update bump time: {e}")

    @tasks.loop(minutes=1)
    async def bump_check(self):
        await self.bot.wait_until_ready()
        try:
            cache = file_loader('./src/data/bumptime.json')
            data = cache.get("lastbump", str(0))
            if data != str(0):
                last_bumped = datetime.strptime(data, '%Y-%m-%d %H:%M:%S.%f')
                now = datetime.utcnow()
                diff = now - last_bumped
                time_data = int(diff.total_seconds())
                if time_data > 7200:
                    cache["lastbump"] = str(0)
                    with open(r'./src/data/bumptime.json', 'w') as f:
                        json.dump(cache, f, indent=4)
                    channel = self.bot.get_channel(self.CHANNELID)
                    if channel:
                        embed = discord.Embed(
                            title="This Server can be bumped again!",
                            description=f"Type `/bump` to bump at https://disboard.org/server/{self.SERVERID}",
                            color=discord.Color.blurple()
                        )
                        await channel.send(content="<@&1925225>", embed=embed)
                    else:
                        print("Bump channel not found. Check CHANNELID.")
        except Exception as e:
            print(f"Error in bump_check: {e}")

    @bump_check.before_loop
    async def before_bump_check(self):
        await self.bot.wait_until_ready()

    def cog_unload(self):
        self.bump_check.cancel()


async def setup(bot):
    await bot.add_cog(BumpCog(bot))
