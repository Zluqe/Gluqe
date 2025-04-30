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
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    @commands.hybrid_command(name='zluqet')
    async def zluqet(self, ctx, message_id: str):
        """
        Upload a text file or the message content to Zluqet.
        """
        if ctx.author.id in self.optout:
            return
        try:
            message = await ctx.fetch_message(message_id)
        except Exception as e:
            logging.error(f"Failed to fetch message: {e}")
            return await ctx.send("Could not fetch message. Please check the message ID.")
        text_content = None
        truncated = False
        max_length = 25_000

        if message.attachments:
            attachment = message.attachments[0]
            file_type, _ = mimetypes.guess_type(attachment.filename)
            ext = attachment.filename.lower().rsplit('.', 1)[-1]
            valid_text_exts = {"txt","log","json","yml","yaml","css","py","js","sh","config","conf"}

            if (file_type and file_type.startswith("text")) or (ext in valid_text_exts):
                try:
                    raw = await attachment.read(use_cached=False)
                    text_content = raw.decode('latin-1', errors='replace')
                except Exception as e:
                    logging.error(f"Failed to read attachment: {e}")
                    return await ctx.send("Failed to read the attached file as text.")
            else:
                return await ctx.send("Invalid file type. Only text files are supported.")
        elif message.content and message.content.strip():
            text_content = message.content
        else:
            return await ctx.send("No attachments or text content found to upload.")
        if len(text_content) > max_length:
            text_content = text_content[: max_length - 1]
            truncated = True
        try:
            async with aiohttp.ClientSession() as session:
                post_url = "https://paste.zluqe.org/api/documents"
                async with session.post(post_url, data=text_content) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        key = data.get("key")
                        if key:
                            url = f"https://paste.zluqe.org/{key}"
                            desc = url + ("\n*(Content truncated.)*" if truncated else "")
                            embed = discord.Embed(
                                title="Uploaded to Zluqet",
                                description=desc,
                                color=0x1D83D4
                            )
                            await ctx.send(embed=embed)
                            logging.info(f"Zluqet upload by {ctx.author} ({ctx.author.id}): {url}")
                            return
                    text = await resp.text()
                    logging.error(f"Zluqet API error {resp.status}: {text}")
                    await ctx.send("Failed to upload to Zluqet; the service returned an error.")
        except Exception as e:
            logging.error(f"Error posting to Zluqet: {e}")
            await ctx.send("An unexpected error occurred while uploading.")
    
async def setup(bot: commands.Bot):
    await bot.add_cog(Zluqet(bot))
