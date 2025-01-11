# cogs/selfroles.py

import discord
from discord.ext import commands
import yaml
import asyncio
import logging

# Configure logging for the cog
logger = logging.getLogger('selfroles')
logger.setLevel(logging.DEBUG)  # Set to DEBUG for detailed logs
handler = logging.StreamHandler()
formatter = logging.Formatter('[%(asctime)s] %(levelname)s:%(name)s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Load config
with open('config.yml', 'r') as f:
    config = yaml.safe_load(f)

class SelfRoleButton(discord.ui.Button):
    def __init__(self, role_id: int, label: str, style: discord.ButtonStyle):
        # Ensure unique custom_id by including role_id
        super().__init__(
            label=label,
            style=style,
            custom_id=f'selfrole_button_{role_id}'  # Unique custom_id
        )
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        logger.debug(f"Button clicked: {self.custom_id} by {interaction.user}")
        role = interaction.guild.get_role(self.role_id)
        if role is None:
            await interaction.response.send_message("Role not found.", ephemeral=True)
            logger.warning(f"Role ID {self.role_id} not found in guild {interaction.guild.id}")
            return

        if role in interaction.user.roles:
            try:
                await interaction.user.remove_roles(role)
                await interaction.response.send_message(f"Removed **{role.name}** role.", ephemeral=True)
                logger.info(f"Removed role {role.name} from user {interaction.user}")
            except discord.HTTPException as e:
                await interaction.response.send_message("Failed to remove role.", ephemeral=True)
                logger.error(f"Failed to remove role {role.name} from user {interaction.user}: {e}")
        else:
            try:
                await interaction.user.add_roles(role)
                await interaction.response.send_message(f"Added **{role.name}** role.", ephemeral=True)
                logger.info(f"Added role {role.name} to user {interaction.user}")
            except discord.HTTPException as e:
                await interaction.response.send_message("Failed to add role.", ephemeral=True)
                logger.error(f"Failed to add role {role.name} to user {interaction.user}: {e}")

class SelfRoleView(discord.ui.View):
    def __init__(self, roles: list, timeout: float = None):
        super().__init__(timeout=timeout)  # Set timeout=None for persistence
        for role in roles:
            button = SelfRoleButton(
                role_id=role['role_id'],
                label=role['name'],
                style=discord.ButtonStyle.primary
            )
            self.add_item(button)

class Selfroles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='sendselfroles')
    @commands.has_permissions(administrator=True)
    async def send_selfroles(self, ctx: commands.Context):
        """Sends the self-role message with buttons."""
        channel_id = config['selfroles']['message_channel_id']
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            await ctx.send("Channel not found.")
            logger.error(f"Channel ID {channel_id} not found.")
            return

        roles = config['selfroles']['roles']
        view = SelfRoleView(roles=roles, timeout=None)  # Ensure timeout=None

        if config['selfroles']['message_id'] == 0:
            try:
                # nice embed
                embed=discord.Embed(title="Get your roles!", description="Get self roles to make your experince better.", color=0x3d6bf5)
                embed.set_author(name="Zluqe | Free Bot Hosting", url="https://zluqe.org", icon_url="https://raw.githubusercontent.com/Zluqe/logo/refs/heads/main/z.png")
                embed.set_thumbnail(url="https://raw.githubusercontent.com/Zluqe/logo/refs/heads/main/z.png")
                embed.add_field(name="📢 Announcments", value="> Get daily announcments for random things, important things, or just to have some fun", inline=False)
                embed.add_field(name="🆕 Updates", value="> Get update notifcations everytime a Zluqe resource gets an update!", inline=False)
                embed.add_field(name="🎉 Giveaways", value="> Get pinged for giveaways that will happen in the server, from more resources to nitro!", inline=False)
                embed.add_field(name="⬆️ Bump Pings", value="> Get reminded to bump the discord every 2 hours-- Doing so will result in you getting more resources on the panel!", inline=False)
                embed.set_footer(text="Zluqe | Free Discord Bot Hosting.")
                message = await channel.send(embed=embed, view=view)
                # Update config with the new message ID
                config['selfroles']['message_id'] = message.id
                with open('config.yml', 'w') as f:
                    yaml.dump(config, f)
                await ctx.send(f"Self-role message sent in {channel.mention}.")
                logger.info(f"Sent new self-role message in channel {channel_id} with message ID {message.id}")
            except discord.HTTPException as e:
                await ctx.send("Failed to send self-role message.")
                logger.error(f"Failed to send self-role message: {e}")
        else:
            try:
                message = await channel.fetch_message(config['selfroles']['message_id'])
                embed=discord.Embed(title="Get your roles!", description="Get self roles to make your experince better.", color=0x3d6bf5)
                embed.set_author(name="Zluqe | Free Bot Hosting", url="https://zluqe.org", icon_url="https://raw.githubusercontent.com/Zluqe/logo/refs/heads/main/z.png")
                embed.set_thumbnail(url="https://raw.githubusercontent.com/Zluqe/logo/refs/heads/main/z.png")
                embed.add_field(name="📢 Announcments", value="> Get daily announcments for random things, important things, or just to have some fun", inline=False)
                embed.add_field(name="🆕 Updates", value="> Get update notifcations everytime a Zluqe resource gets an update!", inline=False)
                embed.add_field(name="🎉 Giveaways", value="> Get pinged for giveaways that will happen in the server, from more resources to nitro!", inline=False)
                embed.add_field(name="⬆️ Bump Pings", value="> Get reminded to bump the discord every 2 hours-- Doing so will result in you getting more resources on the panel!", inline=False)
                embed.set_footer(text="Zluqe | Free Discord Bot Hosting.")
                message = await channel.send(embed=embed, view=view)
                await ctx.send("Self-role message updated.")
                logger.info(f"Updated existing self-role message with ID {config['selfroles']['message_id']}")
            except discord.NotFound:
                embed=discord.Embed(title="Get your roles!", description="Get self roles to make your experince better.", color=0x3d6bf5)
                embed.set_author(name="Zluqe | Free Bot Hosting", url="https://zluqe.org", icon_url="https://raw.githubusercontent.com/Zluqe/logo/refs/heads/main/z.png")
                embed.set_thumbnail(url="https://raw.githubusercontent.com/Zluqe/logo/refs/heads/main/z.png")
                embed.add_field(name="📢 Announcments", value="> Get daily announcments for random things, important things, or just to have some fun", inline=False)
                embed.add_field(name="🆕 Updates", value="> Get update notifcations everytime a Zluqe resource gets an update!", inline=False)
                embed.add_field(name="🎉 Giveaways", value="> Get pinged for giveaways that will happen in the server, from more resources to nitro!", inline=False)
                embed.add_field(name="⬆️ Bump Pings", value="> Get reminded to bump the discord every 2 hours-- Doing so will result in you getting more resources on the panel!", inline=False)
                embed.set_footer(text="Zluqe | Free Discord Bot Hosting.")
                message = await channel.send(embed=embed, view=view)
                config['selfroles']['message_id'] = message.id
                with open('config.yml', 'w') as f:
                    yaml.dump(config, f)
                await ctx.send(f"Self-role message sent in {channel.mention}.")
                logger.warning("Previous self-role message not found. Sent a new message.")
            except discord.HTTPException as e:
                await ctx.send("Failed to update self-role message.")
                logger.error(f"Failed to update self-role message: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f'{self.__class__.__name__} cog loaded.')
        # Register the persistent view when the bot is ready
        await self.register_persistent_view()

    async def register_persistent_view(self):
        message_id = config['selfroles'].get('message_id', 0)
        channel_id = config['selfroles'].get('message_channel_id')
        if message_id and channel_id:
            channel = self.bot.get_channel(channel_id)
            if channel:
                try:
                    message = await channel.fetch_message(message_id)
                    # Recreate the view with the roles
                    view = SelfRoleView(roles=config['selfroles']['roles'], timeout=None)
                    self.bot.add_view(view, message_id=message_id)
                    logger.info("Persistent SelfRoleView has been re-registered.")
                except discord.NotFound:
                    logger.error("Self-role message not found. You might need to resend it using the command.")
                except discord.HTTPException as e:
                    logger.error(f"HTTPException while fetching self-role message: {e}")
            else:
                logger.error("Self-role channel not found. Please check your config.")
        else:
            logger.warning("Self-role message ID or channel ID not set in config.")

async def setup(bot):
    await bot.add_cog(Selfroles(bot))
