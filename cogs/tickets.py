import discord, datetime, yaml, os, json, asyncio, re, html
from discord.ext import commands
from typing import Optional
from discord.ui import View, Button
from discord import app_commands

class OpenTicketButton(Button):
    def __init__(self, cog):
        super().__init__(label="Open Ticket", style=discord.ButtonStyle.green, custom_id="open_ticket_button")
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("Ticket creation in progress...", ephemeral=True)
        await self.cog.create_ticket(interaction)

class CloseTicketButton(Button):
    def __init__(self, cog, user):
        super().__init__(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="close_ticket_button")
        self.cog = cog
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        if not (self.cog.is_support(interaction.user) or interaction.user == self.user):
            await interaction.response.send_message("You don't have permission to close this ticket.", ephemeral=True)
            return
        await interaction.response.send_message("Closing ticket...", ephemeral=True)
        await self.cog.close_ticket(interaction)

class TicketView(View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.add_item(OpenTicketButton(cog))

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = self.load_config()
        self.transcript_dir = "transcripts"
        self.ticket_data_file = "data/ticket.json"
        self.ticket_data = self.load_ticket_data()
        os.makedirs(self.transcript_dir, exist_ok=True)
        # Create background task for checking inactive tickets
        self.bg_task = self.bot.loop.create_task(self.check_inactive_tickets())

    def cog_unload(self):
        self.bg_task.cancel()

    async def check_inactive_tickets(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                current_time = datetime.datetime.now().timestamp()
                for channel_id in list(self.ticket_data.keys()):
                    data = self.ticket_data.get(channel_id, {})
                    if data.get('persist', False):
                        continue
                    channel = self.bot.get_channel(int(channel_id))
                    if not channel or not isinstance(channel, discord.TextChannel):
                        del self.ticket_data[channel_id]
                        self.save_ticket_data()
                        continue
                    if not (channel.name.startswith('ticket-') or channel.name.startswith('resolved-')):
                        continue
                    try:
                        messages = [message async for message in channel.history(limit=1)]
                        if messages:
                            last_activity = messages[0].created_at
                        else:
                            last_activity = channel.created_at
                        time_since_activity = current_time - last_activity.timestamp()
                        if time_since_activity >= 86400:  # 24 hours
                            if 'last_warning' not in data:
                                user = self.bot.get_user(data.get('user_id'))
                                if user:
                                    await channel.send(
                                        f"{user.mention}, this ticket has been inactive for 24 hours. "
                                        "It will be closed in 12 hours unless there is a response."
                                    )
                                data['last_warning'] = current_time
                                self.save_ticket_data()
                            else:
                                if current_time - data['last_warning'] >= 43200:  # 12 hours
                                    await self.close_ticket(None, channel)
                        else:
                            if 'last_warning' in data:
                                del data['last_warning']
                                self.save_ticket_data()
                    except discord.Forbidden:
                        continue
                await asyncio.sleep(3600)  # Check every hour
            except Exception as e:
                print(f"Error in inactivity check: {e}")
                await asyncio.sleep(60)

    def load_config(self):
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config.yml')
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            return config['tickets']
        except (FileNotFoundError, yaml.YAMLError):
            return {}

    def load_ticket_data(self):
        if not os.path.exists(self.ticket_data_file):
            return {}
        with open(self.ticket_data_file, "r") as f:
            return json.load(f)

    def save_ticket_data(self):
        with open(self.ticket_data_file, "w") as f:
            json.dump(self.ticket_data, f, indent=4)

    def is_support(self, user: discord.User) -> bool:
        guild = self.bot.guilds[0]
        support_role = guild.get_role(self.config.get('support_role_id'))
        return support_role in user.roles if support_role else False

    async def create_ticket(self, interaction: discord.Interaction):
        guild = interaction.guild
        user = interaction.user
        category = guild.get_channel(self.config.get('ticket_category_id'))
        if category is None:
            await interaction.followup.send("Ticket category not found. Please contact an administrator.", ephemeral=True)
            return
        channel_name = self.config.get('ticket_format', "ticket-{user}").format(user=user.name).lower()
        existing = discord.utils.get(guild.text_channels, name=channel_name)
        if existing:
            await interaction.followup.send(f"You already have an open ticket: {existing.mention}", ephemeral=True)
            return
        support_role = guild.get_role(self.config.get('support_role_id'))
        if support_role is None:
            await interaction.followup.send("Support role not found. Please contact an administrator.", ephemeral=True)
            return
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            support_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        try:
            ticket_channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"Ticket for {user} (ID: {user.id})"
            )
        except discord.HTTPException:
            await interaction.followup.send("Failed to create ticket channel. Please contact an administrator.", ephemeral=True)
            return
        close_button = CloseTicketButton(self, user)
        view = View()
        view.add_item(close_button)
        embed = discord.Embed(
            title="Support Ticket",
            description=f"Hello {user.mention}, a member of our support team will be with you shortly.\n\n"
                        f"To close this ticket, click the button below or use the `/close` command.",
            color=discord.Color.blue()
        )
        await ticket_channel.send(embed=embed, view=view)
        await interaction.followup.send(f"Your ticket has been created: {ticket_channel.mention}", ephemeral=True)
        ping_message = await ticket_channel.send(f"{support_role.mention} {user.mention} A new ticket has been created.")
        await asyncio.sleep(5)
        await ping_message.delete()

        # Save ticket data
        self.ticket_data[str(ticket_channel.id)] = {
            "user_id": user.id,
            "status": "open",
            "persist": False
        }
        self.save_ticket_data()
        self.bot.loop.create_task(self.track_ticket_activity(ticket_channel, user))

    async def track_ticket_activity(self, channel: discord.TextChannel, user: discord.Member):
        def check_response(message):
            return message.channel == channel and message.author != self.bot.user
        while self.ticket_data.get(str(channel.id), {}).get("persist") is False:
            try:
                await self.bot.wait_for('message', timeout=86400, check=check_response)
                continue
            except asyncio.TimeoutError:
                await channel.send(
                    f"{user.mention}, there has been no activity on this ticket for 24 hours. "
                    "This ticket will be closed in 12 hours unless there is further response."
                )
                try:
                    await self.bot.wait_for('message', timeout=43200, check=check_response)
                    continue
                except asyncio.TimeoutError:
                    await self.close_ticket(None, channel)
                    return

    async def track_resolved_ticket(self, channel: discord.TextChannel):
        await asyncio.sleep(86400)
        if self.ticket_data.get(str(channel.id), {}).get("persist") is False:
            await self.close_ticket(None, channel)

    @commands.hybrid_command(name='persist')
    @commands.has_permissions(manage_channels=True)
    async def persist_ticket(self, ctx: commands.Context):
        """
        Makes the current ticket channel persist, preventing it from closing automatically.
        """
        channel = ctx.channel
        if str(channel.id) in self.ticket_data:
            self.ticket_data[str(channel.id)]["persist"] = True
            self.save_ticket_data()
            await ctx.send("This ticket is now persisted and will not close automatically.")
        else:
            await ctx.send("This channel is not being tracked as a ticket.")

    async def generate_transcript(self, channel: discord.TextChannel):
        """
        Generates an HTML transcript of the channel messages using custom CSS formatting.
        Embeds are rendered to look as close as possible to Discord's native embed style.
        Code blocks and inline code are converted as follows:
          - Triple backticks produce a full-width code block with optional syntax highlighting.
          - Double backticks produce a smaller inline code block.
          - Single backticks produce a standard inline code block.
        Additionally, all other Discord markdown (headers, blockquotes, spoilers, bold, underline, strikethrough,
        and italic) is converted to HTML.
        """
        def apply_markdown_formatting(text: str) -> str:
            text = re.sub(r"^### (.+)$", r"<h3>\1</h3>", text, flags=re.MULTILINE)
            text = re.sub(r"^## (.+)$", r"<h2>\1</h2>", text, flags=re.MULTILINE)
            text = re.sub(r"^# (.+)$", r"<h1>\1</h1>", text, flags=re.MULTILINE)
            text = re.sub(r"^> (.+)$", r"<blockquote>\1</blockquote>", text, flags=re.MULTILINE)
            text = re.sub(r"\|\|(.*?)\|\|", r'<span class="spoiler">\1</span>', text)
            text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)
            text = re.sub(r"__(.*?)__", r"<u>\1</u>", text)
            text = re.sub(r"~~(.*?)~~", r"<del>\1</del>", text)
            text = re.sub(r"\*(.*?)\*", r"<em>\1</em>", text)
            text = re.sub(r"_(.*?)_", r"<em>\1</em>", text)
            return text

        def format_message_content(content: str) -> str:
            escaped = html.escape(content)
            def code_block_replacer(match):
                lang = match.group(1) or ""
                code = match.group(2)
                return f"<pre><code class='{'language-' + lang if lang else ''}'>{code}</code></pre>"
            formatted = re.sub(r"```(\w+)?\n(.*?)```", code_block_replacer, escaped, flags=re.DOTALL)
            formatted = re.sub(r"``([^`]+?)``", r"<code class='small-code'>\1</code>", formatted)
            formatted = re.sub(r"`([^`]+?)`", r"<code>\1</code>", formatted)
            parts = re.split(r"(<(?:pre|code)(?:\s[^>]+)?>.*?</(?:pre|code)>)", formatted, flags=re.DOTALL)
            for i, part in enumerate(parts):
                if not re.match(r"<(?:pre|code)(?:\s[^>]+)?>.*?</(?:pre|code)>", part, flags=re.DOTALL):
                    parts[i] = apply_markdown_formatting(part)
                    parts[i] = parts[i].replace("\n", "<br>")
            return "".join(parts)

        def format_embed(embed: discord.Embed) -> str:
            accent_color = f"#{embed.color.value:06x}" if embed.color and embed.color.value != 0 else "#5865F2"
            title = (embed.title or "").replace("**", "").replace("``", "")
            description = (embed.description or "").replace("**", "").replace("``", "")
            fields_html = ""
            if embed.fields:
                fields_html += '<div class="embed-fields">'
                for field in embed.fields:
                    field_name = field.name.replace("**", "").replace("``", "")
                    field_value = field.value.replace("**", "").replace("``", "")
                    fields_html += f"""
                    <div class="embed-field">
                      <div class="embed-field-name">{field_name}</div>
                      <div class="embed-field-value">{field_value}</div>
                    </div>
                    """
                fields_html += '</div>'
            image_html = ""
            if embed.image and embed.image.url:
                image_html = f"<img class='embed-image' src='{embed.image.url}' alt='Embed Image'>"
            footer = ""
            if embed.footer and embed.footer.text:
                footer_text = embed.footer.text.replace("**", "").replace("``", "")
                footer = f"<div class='embed-footer'>{footer_text}</div>"
            return f"""
            <div class="embed" style="border-left: 4px solid {accent_color};">
              {f'<div class="embed-title">{title}</div>' if title else ''}
              {f'<div class="embed-description">{description}</div>' if description else ''}
              {fields_html}
              {image_html}
              {footer}
            </div>
            """

        messages_html = []
        async for message in channel.history(limit=None, oldest_first=True):
            timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
            author = message.author
            content = format_message_content(message.content)
            avatar_url = author.avatar.url if author.avatar else ""
            embed_html = ""
            if message.embeds:
                for embed in message.embeds:
                    embed_html += format_embed(embed)
            message_html = f'''
        <div class="chatlog__message-group">
          <div class="chatlog__message">
            <div class="chatlog__message-aside">
              <img class="chatlog__avatar" src="{avatar_url}" alt="Avatar">
            </div>
            <div class="chatlog__message-primary">
              <div class="chatlog__header">
                <span class="chatlog__author">{author}</span>
                <span class="chatlog__timestamp">{timestamp}</span>
              </div>
              <div class="chatlog__content">
                {content}
                {embed_html}
              </div>
            </div>
          </div>
        </div>
            '''
            messages_html.append(message_html)

        html_template = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width">
  <title>Ticket Transcript - {channel.name}</title>
  <style>
    html, body {{
      margin: 0;
      padding: 0;
      background-color: #36393e;
      color: #dcddde;
      font-family: "gg sans", "Helvetica Neue", Helvetica, Arial, sans-serif;
      font-size: 17px;
      font-weight: 400;
      scroll-behavior: smooth;
    }}
    a {{
      color: #00aff4;
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
    img {{
      object-fit: contain;
      image-rendering: high-quality;
      image-rendering: -webkit-optimize-contrast;
    }}
    .chatlog {{
      padding: 1rem 0;
      width: 100%;
      border-top: 1px solid rgba(255, 255, 255, 0.1);
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }}
    .chatlog__message-group {{
      margin-bottom: 1rem;
    }}
    .chatlog__message {{
      display: grid;
      grid-template-columns: auto 1fr;
      padding: 0.15rem 0;
    }}
    .chatlog__message-aside {{
      grid-column: 1;
      width: 72px;
      padding: 0.15rem;
      text-align: center;
    }}
    .chatlog__avatar {{
      width: 40px;
      height: 40px;
      border-radius: 50%;
    }}
    .chatlog__message-primary {{
      grid-column: 2;
      min-width: 0;
    }}
    .chatlog__header {{
      margin-bottom: 0.1rem;
    }}
    .chatlog__author {{
      font-weight: 500;
      color: #ffffff;
    }}
    .chatlog__timestamp {{
      margin-left: 0.3rem;
      color: #a3a6aa;
      font-size: 0.75rem;
      font-weight: 500;
    }}
    .chatlog__content {{
      padding-right: 1rem;
      font-size: 0.95rem;
      word-wrap: break-word;
    }}
    /* Discord-like embed styling */
    .embed {{
      border-radius: 4px;
      background-color: #2F3136;
      padding: 10px;
      margin-top: 10px;
    }}
    .embed-title {{
      font-size: 1rem;
      font-weight: 600;
      color: #ffffff;
      margin-bottom: 5px;
    }}
    .embed-description {{
      font-size: 0.9rem;
      color: #dcddde;
      margin-bottom: 10px;
    }}
    .embed-fields {{
      display: flex;
      flex-wrap: wrap;
      margin-bottom: 10px;
    }}
    .embed-field {{
      flex: 1 1 45%;
      margin-bottom: 10px;
    }}
    .embed-field-name {{
      font-size: 0.85rem;
      font-weight: 600;
      color: #ffffff;
      margin-bottom: 2px;
    }}
    .embed-field-value {{
      font-size: 0.85rem;
      color: #dcddde;
    }}
    .embed-image {{
      width: 100%;
      max-width: 500px;
      border-radius: 4px;
      margin-top: 10px;
    }}
    .embed-footer {{
      font-size: 0.75rem;
      color: #72767d;
      margin-top: 10px;
      border-top: 1px solid #202225;
      padding-top: 5px;
    }}
    /* Code block styling */
    pre {{
      background-color: #2F3136;
      padding: 10px;
      border-radius: 4px;
      overflow-x: auto;
      margin-top: 10px;
      margin-bottom: 10px;
    }}
    code {{
      font-family: Consolas, "Courier New", Courier, monospace;
      font-size: 0.9rem;
      color: #dcddde;
    }}
    /* Smaller inline code styling for double backticks */
    code.small-code {{
      font-size: 0.8rem;
      padding: 2px 4px;
      background-color: #2F3136;
      border-radius: 3px;
    }}
    /* Spoiler styling */
    .spoiler {{
      background-color: #000;
      color: #000;
      border-radius: 3px;
      padding: 0 4px;
    }}
  </style>
</head>
<body>
  <div class="chatlog">
    {''.join(messages_html)}
  </div>
</body>
</html>
'''
        transcript_path = os.path.join(self.transcript_dir, f"{channel.name}.html")
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(html_template)
        return transcript_path

    async def close_ticket(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        if interaction:
            channel = interaction.channel
        ticket_info = self.ticket_data.get(str(channel.id))
        if not ticket_info:
            await channel.send("Could not determine the ticket creator.")
            return
        user = self.bot.get_user(ticket_info["user_id"])
        transcript = await self.generate_transcript(channel)
        if transcript:
            transcript_channel = self.bot.get_channel(self.config.get('transcript_channel_id'))
            if transcript_channel:
                try:
                    file = discord.File(transcript, filename=f"{channel.name}.html")
                    await transcript_channel.send(content=f"Transcript for {channel.name}:", file=file)
                except discord.HTTPException:
                    await channel.send("Failed to send the transcript to the transcript channel.")
        if os.path.exists(transcript):
            os.remove(transcript)
        del self.ticket_data[str(channel.id)]
        self.save_ticket_data()
        try:
            await channel.delete(reason="Ticket closed automatically.")
        except discord.HTTPException:
            await channel.send("Failed to delete the ticket channel.")

    @commands.hybrid_command(name='resolved')
    @commands.has_permissions(manage_channels=True)
    async def ticket_resolved(self, ctx: commands.Context):
        """
        Marks the current ticket as resolved.
        """
        channel = ctx.channel
        ticket_info = self.ticket_data.get(str(channel.id))
        if not ticket_info:
            await ctx.send("Could not determine the ticket creator.")
            return
        user = self.bot.get_user(ticket_info["user_id"])
        if channel.name.startswith("resolved-"):
            await ctx.send("This ticket is already resolved.")
            return
        embed = discord.Embed(
            title="Ticket Resolved",
            description=f"{user.mention}, your ticket has been resolved. Thank you for reaching out!\n\n"
                        "> Please consider reviewing us on [Trust Pilot](https://www.trustpilot.com/review/zluqe.org).",
            color=discord.Color.green()
        )
        embed.set_footer(text="If you want to close this ticket now, please do /close")
        await ctx.send(embed=embed)
        resolved_name = f"resolved-{user.name}".lower()
        await channel.edit(name=resolved_name, reason=f"Ticket resolved by {ctx.author}")
        ticket_info["status"] = "resolved"
        self.save_ticket_data()
        self.bot.loop.create_task(self.track_resolved_ticket(channel))

    @commands.hybrid_command(name='close')
    @commands.has_permissions(manage_channels=True)
    async def close_ticket_command(self, ctx: commands.Context):
        """
        Closes the current ticket channel.
        """
        channel = ctx.channel
        ticket_info = self.ticket_data.get(str(channel.id))
        if not ticket_info:
            await ctx.send("This channel is not being tracked as a ticket.")
            return
        user = self.bot.get_user(ticket_info["user_id"])
        if not user:
            await ctx.send("Could not determine the ticket creator.")
            return
        transcript_path = await self.generate_transcript(channel)
        if not transcript_path or not os.path.exists(transcript_path):
            await ctx.send("Failed to generate the transcript.")
            return
        transcript_channel = self.bot.get_channel(self.config.get('transcript_channel_id'))
        if transcript_channel:
            try:
                with open(transcript_path, "rb") as transcript_file:
                    file = discord.File(transcript_file, filename=f"{channel.name}.html")
                    await transcript_channel.send(content=f"Transcript for {channel.name}:", file=file)
            except discord.HTTPException:
                await ctx.send("Failed to send the transcript to the transcript channel.")
        try:
            with open(transcript_path, "rb") as transcript_file:
                file = discord.File(transcript_file, filename=f"{channel.name}.html")
                await user.send(
                    f"Your ticket in {channel.guild.name} has been resolved. Thank you for reaching out!",
                    file=file
                )
        except discord.Forbidden:
            await ctx.send(f"Could not DM {user.mention} the transcript.")
        except discord.HTTPException:
            await ctx.send("Failed to send the transcript to the user.")
        if os.path.exists(transcript_path):
            os.remove(transcript_path)
        del self.ticket_data[str(channel.id)]
        self.save_ticket_data()
        try:
            await channel.delete(reason=f"Ticket closed by {ctx.author}")
        except discord.HTTPException:
            await ctx.send("Failed to delete the ticket channel.")

    @commands.Cog.listener()
    async def on_ready(self):
        embed_channel = self.bot.get_channel(self.config.get('embed_channel_id'))
        if embed_channel:
            view = TicketView(self)
            self.bot.add_view(view)

    @commands.command(name='setup_tickets')
    @commands.has_permissions(administrator=True)
    async def setup_tickets(self, ctx: commands.Context):
        """
        Sets up the support ticket system by sending an embed message with a button to open a ticket.
        """
        embed_channel = self.bot.get_channel(self.config.get('embed_channel_id'))
        if not embed_channel:
            await ctx.send("Embed channel not found. Please check the channel ID in config.yml.")
            return
        embed = discord.Embed(
            title="Support Tickets",
            description="Click the button below to open a support ticket.",
            color=discord.Color.green()
        )
        view = TicketView(self)
        await embed_channel.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Tickets(bot))