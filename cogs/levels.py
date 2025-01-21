import discord
from discord.ext import commands
from discord.ext.commands import CooldownMapping
import sqlite3
import math

class LevelSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect("data/levels.db")
        self.cursor = self.conn.cursor()
        self._create_tables()
        self.cooldowns = CooldownMapping.from_cooldown(1, 5, commands.BucketType.user)
        self.prize_interval = 10

    def _create_tables(self):
        """Create the tables"""
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS levels (
            user_id INTEGER PRIMARY KEY,
            level INTEGER NOT NULL,
            xp INTEGER NOT NULL
        )
        """)
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS prize_claims (
            user_id INTEGER NOT NULL,
            level INTEGER NOT NULL,
            claimed INTEGER NOT NULL,
            PRIMARY KEY (user_id, level)
        )
        """)
        self.conn.commit()

    def get_user_data(self, user_id):
        """user data from the database."""
        self.cursor.execute("SELECT level, xp FROM levels WHERE user_id = ?", (user_id,))
        result = self.cursor.fetchone()
        if result is None:
            self.cursor.execute("INSERT INTO levels (user_id, level, xp) VALUES (?, ?, ?)", (user_id, 0, 0))
            self.conn.commit()
            return 0, 0
        return result

    def update_user_data(self, user_id, level, xp):
        """Update user data"""
        self.cursor.execute("UPDATE levels SET level = ?, xp = ? WHERE user_id = ?", (level, xp, user_id))
        self.conn.commit()

    def calculate_xp_required(self, level):
        """Calculate the XP required for the next level."""
        return 5 * (level ** 2) + 50 * level + 100

    def has_claimed_prize(self, user_id, level):
        """Check if a user has claimed prize"""
        self.cursor.execute("SELECT claimed FROM prize_claims WHERE user_id = ? AND level = ?", (user_id, level))
        result = self.cursor.fetchone()
        return result is not None and result[0] == 1

    def set_prize_claimed(self, user_id, level):
        """Mark a prize as claimed"""
        self.cursor.execute("""
        INSERT OR REPLACE INTO prize_claims (user_id, level, claimed) VALUES (?, ?, ?)
        """, (user_id, level, 1))
        self.conn.commit()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # Cooldown
        bucket = self.cooldowns.get_bucket(message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            return

        user_id = message.author.id
        level, xp = self.get_user_data(user_id)
        xp += 8  # XP for sending a message
        xp_required = self.calculate_xp_required(level)

        if xp >= xp_required:
            level += 1
            xp -= xp_required

            # Notify leveled up
            await message.channel.send(f"🎉 {message.author.mention}, you have leveled up to: Level {level}!")

            # Notify prize redemption
            if level % self.prize_interval == 0:
                await message.channel.send(f"🎁 {message.author.mention}, you have reached Level {level}! You are able to claim a prize now. **Open a ticket**!")

            # Assign a role
            if level % 10 == 0:
                role_name = f"Level {level}"
                guild = message.guild
                role = discord.utils.get(guild.roles, name=role_name)
                if role is None:
                    role = await guild.create_role(name=role_name)
                await message.author.add_roles(role)

        self.update_user_data(user_id, level, xp)
        
    @commands.hybrid_command(name="prize")
    @commands.has_permissions(administrator=True)
    async def prize(self, ctx, option: str, member: discord.Member):
        """
        Check or mark prize claims for a user.
        """
        user_id = member.id
        user_level, _ = self.get_user_data(user_id)

        if option.lower() == "check":
            unclaimed = []
            for level in range(self.prize_interval, user_level + 1, self.prize_interval):
                if not self.has_claimed_prize(user_id, level):
                    unclaimed.append(level)

            if unclaimed:
                levels = ", ".join(map(str, unclaimed))
                await ctx.send(f"{member.mention} has not claimed prizes for levels: {levels}.")
            else:
                await ctx.send(f"{member.mention} has claimed all eligible prizes.")

        elif option.lower() == "claim":
            claimed = []
            for level in range(self.prize_interval, user_level + 1, self.prize_interval):
                if not self.has_claimed_prize(user_id, level):
                    self.set_prize_claimed(user_id, level)
                    claimed.append(level)

            if claimed:
                levels = ", ".join(map(str, claimed))
                await ctx.send(f"{member.mention} has now claimed prizes for levels: {levels}.")
            else:
                await ctx.send(f"{member.mention} had no unclaimed prizes to claim.")
        else:
            await ctx.send("Invalid option. Use `check` or `claim`.")

    @commands.hybrid_command(name="level")
    async def check_level(self, ctx, member: discord.Member = None):
        """Check the level of yourself or another user."""
        member = member or ctx.author
        level, xp = self.get_user_data(member.id)
        xp_required = self.calculate_xp_required(level)
        await ctx.send(f"{member.mention}, you are at Level {level} with {xp}/{xp_required} XP.")

async def setup(bot):
    await bot.add_cog(LevelSystem(bot))