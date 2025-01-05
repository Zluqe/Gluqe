import discord
from discord.ext import commands, tasks
from datetime import datetime
import json
import asyncio
import yaml


class BumpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bump_check.start()  # Start the background task after initialization
    
    # Load config.yml
    with open('config.yml', 'r') as f:
        config = yaml.safe_load(f)
    
    CHANNELID = 1324979225098453032
    SERVERID = 1324888658016211005

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == 302050872383242240:  # Bump bot ID
            if message.embeds and 'Bump done! :thumbsup:' in message.embeds[0].description:
                try:
                    with open(r'src/data/bumptime.json', 'r') as file:
                        timedata = json.load(file)
                    timedata["lastbump"] = str(datetime.utcnow())
                    with open(r'src/data/bumptime.json', 'w') as file:
                        json.dump(timedata, file, indent=4)
                except Exception as e:
                    print(f"Failed to update bump time: {e}")

    @tasks.loop(minutes=1)
    async def bump_check(self):
        await self.bot.wait_until_ready()
        try:
            with open(r'src/data/bumptime.json', 'r') as f:
                cache = json.load(f)
            data = cache.get("lastbump", str(0))
            if data != str(0):
                last_bumped = datetime.strptime(data, '%Y-%m-%d %H:%M:%S.%f')
                now = datetime.utcnow()
                diff = now - last_bumped
                time_data = int(diff.total_seconds())
                if time_data > 7200:
                    cache["lastbump"] = str(0)
                    with open(r'src/data/bumptime.json', 'w') as f:
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