import discord
from discord.ext import commands
import yaml
import os
import json
import asyncio
from discord.ui import View, Button

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
        # ping_message = await ticket_channel.send(f"{support_role.mention} {user.mention} A new ticket has been created.")
        await asyncio.sleep(5)
        # await ping_message.delete()

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
                    f"This ticket will be closed in 12 hours unless there is further response."
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

    async def close_ticket(self, interaction: discord.Interaction, channel=None):
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
                file = discord.File(transcript, filename=f"{channel.name}.txt")
                await transcript_channel.send(file=file)
        if os.path.exists(transcript):
            os.remove(transcript)
        del self.ticket_data[str(channel.id)]
        self.save_ticket_data()
        await channel.delete(reason="Ticket closed automatically.")

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
                        f"> Please consider reviewing us on [Trust Pilot](https://www.trustpilot.com/review/zluqe.org).",
            color=discord.Color.green()
        )
        embed.set_footer(text="If you want to close this ticket now, please do /close")
        await ctx.send(embed=embed)
        resolved_name = f"resolved-{user.name}".lower()
        await channel.edit(name=resolved_name, reason=f"Ticket resolved by {ctx.author}")
        ticket_info["status"] = "resolved"
        self.save_ticket_data()
        self.bot.loop.create_task(self.track_resolved_ticket(channel))

    async def generate_transcript(self, channel: discord.TextChannel):
        messages = []
        async for message in channel.history(limit=None, oldest_first=True):
            timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
            author = message.author
            content = message.content
            if message.attachments:
                attachments = ", ".join([attachment.url for attachment in message.attachments])
                messages.append(f"[{timestamp}] {author}: {content} | Attachments: {attachments}")
            else:
                messages.append(f"[{timestamp}] {author}: {content}")
        transcript_path = os.path.join(self.transcript_dir, f"{channel.name}.txt")
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write("\n".join(messages))
        return transcript_path

    @commands.hybrid_command(name='close')
    @commands.has_permissions(manage_channels=True)
    async def close_ticket(self, ctx: commands.Context):
        """
        Closes the current ticket channel, generates a transcript, and sends it to the transcript channel and the user.
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

        # Generate the transcript
        transcript_path = await self.generate_transcript(channel)

        if not transcript_path or not os.path.exists(transcript_path):
            await ctx.send("Failed to generate the transcript.")
            return

        # Send the transcript to the transcript channel
        transcript_channel = self.bot.get_channel(self.config.get('transcript_channel_id'))
        if transcript_channel:
            try:
                with open(transcript_path, "rb") as transcript_file:
                    file = discord.File(transcript_file, filename=f"{channel.name}.txt")
                    await transcript_channel.send(content=f"Transcript for {channel.name}:", file=file)
            except discord.HTTPException:
                await ctx.send("Failed to send the transcript to the transcript channel.")

        # Send the transcript to the user
        try:
            with open(transcript_path, "rb") as transcript_file:
                file = discord.File(transcript_file, filename=f"{channel.name}.txt")
                await user.send(
                    f"Your ticket in {channel.guild.name} has been resolved. Thank you for reaching out! "
                    f"Here is a transcript of your ticket:",
                    file=file
                )
        except discord.Forbidden:
            await ctx.send(f"Could not DM {user.mention} the transcript.")
        except discord.HTTPException:
            await ctx.send("Failed to send the transcript to the user.")

        # Delete the transcript file after use
        if os.path.exists(transcript_path):
            os.remove(transcript_path)

        # Remove the ticket from tracking
        del self.ticket_data[str(channel.id)]
        self.save_ticket_data()

        # Delete the ticket channel
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
