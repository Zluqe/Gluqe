import discord, aiohttp, mimetypes, json, logging
from discord.ext import commands
from discord import app_commands

class Zluqet(commands.Cog):
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

    @commands.hybrid_command(name='zluqet')
    async def zluqet(self, ctx, message_id: str):
        """
        Upload a text file to a Zluqet.
        """
        if ctx.author.id in self.optout:
            pass

        try:
            message = await ctx.fetch_message(message_id)
        except Exception as e:
            logging.error(f"Failed to fetch message: {e}")
            return await ctx.send("Could not fetch message. Please check the message ID.")

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
                max_length = 25000
                if len(text_content) > max_length:
                    text_content = text_content[:max_length - 1]
                    truncated = True

                async with aiohttp.ClientSession() as session:
                    post_url = "https://paste.zluqe.org/api/documents"
                    async with session.post(post_url, data=text_content) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            key = data.get("key")
                            if key:
                                link = f"https://paste.zluqe.org/{key}"
                                embed_desc = f"{link}"
                                if truncated:
                                    embed_desc += "\n*(File was truncated because it was too long.)*"
                                
                                embed = discord.Embed(
                                    title="Uploaded to Zluqet",
                                    description=embed_desc,
                                    color=0x1D83D4
                                )
                                await ctx.send(embed=embed)
                                logging.info(
                                    f"File uploaded by {ctx.author} ({ctx.author.id}): {link}"
                                )
                                return
                        else:
                            error_text = await resp.text()
                            logging.error(f"Failed to upload paste: {resp.status} {error_text}")
                            await ctx.send("Failed to upload paste. The Zluqet returned an error.")
            except Exception as e:
                logging.error(f"Failed to process attachment: {e}")
                await ctx.send("Failed to process attachment. Is it a valid text file?")
        else:
            await ctx.send("Invalid file type. Only text files are supported.")

async def setup(bot: commands.Bot):
    await bot.add_cog(Zluqet(bot))
