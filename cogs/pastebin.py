import discord, aiohttp, mimetypes, json, logging
from discord.ext import commands

class Pastebin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.optout = set()
        try:
            with open('data/optout.json', 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    self.optout = set(data)
        except FileNotFoundError:
            pass
        except json.JSONDecodeError:
            pass

    @commands.hybrid_command(name='optout')
    async def optout(self, ctx):
        """
        Toggle opt-out status:
        - If you are not in the list, you'll be added (opted out).
        - If you are in the list, you'll be removed (opted in).
        """
        if ctx.author.id in self.optout:
            self.optout.remove(ctx.author.id)
            message = (
                "You have been opted **out**. I will **not** automatically upload "
                "your text file attachments to a pastebin."
            )
        else:
            self.optout.add(ctx.author.id)
            message = (
                "You have been opted **back in**. I will automatically upload your "
                "future text file attachments to a pastebin."
            )
        
        with open('data/optout.json', 'w') as f:
            json.dump(list(self.optout), f)
        
        await ctx.send(message)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        
        if message.author.id not in self.optout:
            return
        
        if not message.attachments:
            return
        
        attachment = message.attachments[0]
        
        file_type, _ = mimetypes.guess_type(attachment.filename)
        file_ext = attachment.filename.lower().split('.')[-1]
        
        valid_text_exts = [
            "txt", "log", "json", "yml", "yaml", "css",
            "py", "js", "sh", "config", "conf"
        ]
        
        if (file_type and file_type.startswith("text")) or (file_ext in valid_text_exts):
            try:
                file_bytes = await attachment.read(use_cached=False)
                text_content = file_bytes.decode('Latin-1', errors='replace')
                
                truncated = False
                max_length = 100000
                if len(text_content) > max_length:
                    text_content = text_content[:max_length - 1]
                    truncated = True
                
                async with aiohttp.ClientSession() as session:
                    post_url = "https://bin.birdflop.com/documents"
                    async with session.post(post_url, data=text_content) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            key = data.get("key")
                            
                            if key:
                                link = f"https://bin.birdflop.com/{key}"
                                embed_desc = f"{link}\nRequested by {message.author.mention}"
                                if truncated:
                                    embed_desc += "\n*(File was truncated because it was too long.)*"
                                
                                embed = discord.Embed(
                                    title="Uploaded to a Pastebin",
                                    description=embed_desc,
                                    color=0x1D83D4
                                )
                                
                                await message.channel.send(embed=embed)
                                logging.info(
                                    f"File uploaded by {message.author} ({message.author.id}): {link}"
                                )
            except Exception as e:
                logging.error(f"Failed to process attachment: {e}")
                
    @commands.hybrid_command(name='pastebin')
    async def pastebin(self, ctx, message_id: str):
        """
        Upload a text file to a pastebin.
        """
        
        message = await ctx.fetch_message(message_id)
        
        if not message.attachments:
            return await ctx.send("No attachments found.")
        
        attachment = message.attachments[0]
        
        file_type, _ = mimetypes.guess_type(attachment.filename)
        file_ext = attachment.filename.lower().split('.')[-1]
        
        valid_text_exts = [
            "txt", "log", "json", "yml", "yaml", "css",
            "py", "js", "sh", "config", "conf"
        ]
        
        if (file_type and file_type.startswith("text")) or (file_ext in valid_text_exts):
            try:
                file_bytes = await attachment.read(use_cached=False)
                text_content = file_bytes.decode('Latin-1', errors='replace')
                
                truncated = False
                max_length = 100000
                if len(text_content) > max_length:
                    text_content = text_content[:max_length - 1]
                    truncated = True
                
                async with aiohttp.ClientSession() as session:
                    post_url = "https://bin.birdflop.com/documents"
                    async with session.post(post_url, data=text_content) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            key = data.get("key")
                            
                            if key:
                                link = f"https://bin.birdflop.com/{key}"
                                embed_desc = f"{link}\nRequested by {ctx.author.mention}"
                                if truncated:
                                    embed_desc += "\n*(File was truncated because it was too long.)*"
                                
                                embed = discord.Embed(
                                    title="Uploaded to a Pastebin",
                                    description=embed_desc,
                                    color=0x1D83D4
                                )
                                
                                await ctx.send(embed=embed)
                                logging.info(
                                    f"File uploaded by {ctx.author} ({ctx.author.id}): {link}"
                                )
            except Exception as e:
                logging.error(f"Failed to process attachment: {e}")
                ctx.send("Failed to process attachment. Is it a valid text file?")
        else:
            await ctx.send("Invalid file type. Only text files are supported.")

async def setup(bot: commands.Bot):
    await bot.add_cog(Pastebin(bot))
