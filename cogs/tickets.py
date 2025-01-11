# cogs/tickets.py

import discord
from discord.ext import commands
from discord.ui import View, Button
import yaml
import os
import asyncio

class OpenTicketButton(Button):
    def __init__(self, cog):
        super().__init__(
            label="Open Ticket",
            style=discord.ButtonStyle.green,
            custom_id="open_ticket_button"  # Unique identifier for persistence
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("Ticket creation in progress...", ephemeral=True)
        await self.cog.create_ticket(interaction)

class CloseTicketButton(Button):
    def __init__(self, cog, user):
        super().__init__(
            label="Close Ticket",
            style=discord.ButtonStyle.red,
            custom_id="close_ticket_button"  # Unique identifier for persistence
        )
        self.cog = cog
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        # Check if the user has permission to close the ticket
        if not (self.cog.is_support(interaction.user) or interaction.user == self.user):
            await interaction.response.send_message("You don't have permission to close this ticket.", ephemeral=True)
            return

        await interaction.response.send_message("Closing ticket...", ephemeral=True)
        await self.cog.close_ticket(interaction)

class TicketView(View):
    def __init__(self, cog):
        super().__init__(timeout=None)  # Persistent view
        self.add_item(OpenTicketButton(cog))

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = self.load_config()
        self.transcript_dir = "transcripts"
        os.makedirs(self.transcript_dir, exist_ok=True)

    def load_config(self):
        """
        Loads the configuration from config.yml.
        """
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config.yml')
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            return config['tickets']
        except FileNotFoundError:
            print(f"Configuration file not found at {config_path}.")
            return {}
        except yaml.YAMLError as e:
            print(f"Error parsing config.yml: {e}")
            return {}

    def is_support(self, user: discord.User) -> bool:
        """
        Checks if a user has the support role.
        """
        guild = self.bot.guilds[0]  # Assumes the bot is only in one guild
        support_role = guild.get_role(self.config.get('support_role_id'))
        return support_role in user.roles if support_role else False

    async def create_ticket(self, interaction: discord.Interaction):
        guild = interaction.guild
        user = interaction.user

        # Fetch the category where tickets are created
        category = guild.get_channel(self.config.get('ticket_category_id'))
        if category is None:
            await interaction.followup.send("Ticket category not found. Please contact an administrator.", ephemeral=True)
            return

        # Define ticket channel name
        channel_name = self.config.get('ticket_format', "ticket-{user}").format(user=user.name).lower()

        # Check if user already has an open ticket
        existing = discord.utils.get(guild.text_channels, name=channel_name)
        if existing:
            await interaction.followup.send(f"You already have an open ticket: {existing.mention}", ephemeral=True)
            return

        # Set permissions
        support_role = guild.get_role(self.config.get('support_role_id'))
        if support_role is None:
            await interaction.followup.send("Support role not found. Please contact an administrator.", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            support_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        # Create the ticket channel
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

        # Send a welcome message in the ticket channel
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

        # Notify the user
        await interaction.followup.send(f"Your ticket has been created: {ticket_channel.mention}", ephemeral=True)

        # Ping the support role and the user, then delete the ping message
        ping_message = await ticket_channel.send(f"{support_role.mention} {user.mention} A new ticket has been created.")
        await asyncio.sleep(5)  # Wait for 5 seconds before deleting
        await ping_message.delete()

    async def close_ticket(self, interaction: discord.Interaction):
        channel = interaction.channel
        user = self.get_ticket_creator(channel)

        if user is None:
            await interaction.followup.send("Could not determine the ticket creator.", ephemeral=True)
            return

        # Generate transcript manually
        transcript = await self.generate_transcript(channel)

        if not transcript:
            await interaction.followup.send("Failed to generate transcript.", ephemeral=True)
            return

        # Fetch the transcript channel
        transcript_channel = self.bot.get_channel(self.config.get('transcript_channel_id'))
        if transcript_channel is None:
            await interaction.followup.send("Transcript channel not found. Please contact an administrator.", ephemeral=True)
            return

        # Send the transcript
        try:
            file = discord.File(transcript, filename=f"{channel.name}.txt")
            await transcript_channel.send(file=file)
        except discord.HTTPException:
            await interaction.followup.send("Failed to send transcript.", ephemeral=True)
            return
        finally:
            # Clean up the temporary transcript file
            if os.path.exists(transcript):
                os.remove(transcript)

        # Delete the ticket channel
        try:
            await channel.delete(reason=f"Ticket closed by {interaction.user}")
        except discord.HTTPException:
            await interaction.followup.send("Failed to delete the ticket channel.", ephemeral=True)

    def get_ticket_creator(self, channel: discord.TextChannel) -> discord.User:
        """
        Retrieves the ticket creator from the channel topic.
        """
        if channel.topic:
            try:
                # Assuming the topic is in the format: "Ticket for {user} (ID: {user.id})"
                start = channel.topic.index("Ticket for ") + len("Ticket for ")
                end = channel.topic.index(" (ID:")
                username = channel.topic[start:end]
                # Fetch the user by username
                for member in channel.guild.members:
                    if member.name == username:
                        return member
            except ValueError:
                return None
        return None

    async def generate_transcript(self, channel: discord.TextChannel) -> str:
        """
        Generates a transcript of the given channel and saves it as a text file.
        Returns the path to the transcript file.
        """
        messages = []
        try:
            # Fetch all messages in the channel
            async for message in channel.history(limit=None, oldest_first=True):
                timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
                author = message.author
                content = message.content
                # Format message content (including attachments if needed)
                if message.attachments:
                    attachments = ", ".join([attachment.url for attachment in message.attachments])
                    messages.append(f"[{timestamp}] {author}: {content} | Attachments: {attachments}")
                else:
                    messages.append(f"[{timestamp}] {author}: {content}")
        except discord.HTTPException:
            return None

        # Create transcript content
        transcript_content = "\n".join(messages)

        # Define transcript file path
        transcript_path = os.path.join(self.transcript_dir, f"{channel.name}.txt")

        # Write the transcript to a file
        try:
            with open(transcript_path, "w", encoding="utf-8") as f:
                f.write(transcript_content)
            return transcript_path
        except IOError:
            return None

    @commands.hybrid_command(name='close')
    @commands.has_permissions(manage_channels=True)
    async def close_ticket_command(self, ctx: commands.Context):
        """
        Closes the current ticket channel via command.
        """
        channel = ctx.channel
        user = self.get_ticket_creator(channel)

        if user is None:
            await ctx.send("Could not determine the ticket creator.")
            return

        # Generate transcript manually
        transcript = await self.generate_transcript(channel)

        if not transcript:
            await ctx.send("Failed to generate transcript.")
            return

        # Fetch the transcript channel
        transcript_channel = self.bot.get_channel(self.config.get('transcript_channel_id'))
        if transcript_channel is None:
            await ctx.send("Transcript channel not found. Please contact an administrator.")
            return

        # Send the transcript
        try:
            file = discord.File(transcript, filename=f"{channel.name}.txt")
            await transcript_channel.send(file=file)
        except discord.HTTPException:
            await ctx.send("Failed to send transcript.")
            return
        finally:
            # Clean up the temporary transcript file
            if os.path.exists(transcript):
                os.remove(transcript)

        # Delete the ticket channel
        try:
            await channel.delete(reason=f"Ticket closed by {ctx.author}")
        except discord.HTTPException:
            await ctx.send("Failed to delete the ticket channel.")

    @commands.command(name='setup_tickets')
    @commands.has_permissions(administrator=True)
    async def setup_tickets(self, ctx: commands.Context):
        """
        Sends the ticket creation embed with the Open Ticket button.
        """
        embed_channel = self.bot.get_channel(self.config.get('embed_channel_id'))
        if embed_channel is None:
            await ctx.send("Embed channel not found. Please check the channel ID in config.yml.")
            return

        embed = discord.Embed(
            title="Support Tickets",
            description="Click the button below to open a support ticket.",
            color=discord.Color.green()
        )
        view = TicketView(self)

        try:
            await embed_channel.send(embed=embed, view=view)
            await ctx.send(f"Ticket creation embed sent to {embed_channel.mention}.")
        except discord.HTTPException:
            await ctx.send("Failed to send ticket creation embed.")

    @commands.Cog.listener()
    async def on_ready(self):
        # Register the persistent OpenTicketButton view
        embed_channel = self.bot.get_channel(self.config.get('embed_channel_id'))
        if embed_channel:
            view = TicketView(self)
            self.bot.add_view(view)  # Registers the view globally
        else:
            pass  # Embed channel not found; handle accordingly if needed

async def setup(bot):
    await bot.add_cog(Tickets(bot))