import discord, math, random, asyncio
import aiosqlite
from discord.ext import commands
from discord.ext.commands import CooldownMapping

class LevelSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = None
        self.cooldowns = CooldownMapping.from_cooldown(1, 5, commands.BucketType.user)
        self.prize_interval = 10

    async def init_db(self):
        self.db = await aiosqlite.connect("data/levels.db")
        await self._create_tables()

    async def _create_tables(self):
        """Create the tables if they don't exist."""
        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS levels (
            user_id INTEGER PRIMARY KEY,
            level INTEGER NOT NULL,
            xp INTEGER NOT NULL
        )
        """)
        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS prize_claims (
            user_id INTEGER NOT NULL,
            level INTEGER NOT NULL,
            claimed INTEGER NOT NULL,
            PRIMARY KEY (user_id, level)
        )
        """)
        await self.db.commit()

    async def get_user_data(self, user_id):
        """Fetch user data from the database."""
        async with self.db.execute("SELECT level, xp FROM levels WHERE user_id = ?", (user_id,)) as cursor:
            result = await cursor.fetchone()
        if result is None:
            await self.db.execute("INSERT INTO levels (user_id, level, xp) VALUES (?, ?, ?)", (user_id, 0, 0))
            await self.db.commit()
            return 0, 0
        return result

    async def update_user_data(self, user_id, level, xp):
        """Update user data in the database."""
        await self.db.execute("UPDATE levels SET level = ?, xp = ? WHERE user_id = ?", (level, xp, user_id))
        await self.db.commit()

    def calculate_xp_required(self, level):
        """Calculate the XP required for the next level."""
        return 5 * (level ** 2) + 50 * level + 100

    async def has_claimed_prize(self, user_id, level):
        """Check if a user has claimed the prize for a given level."""
        async with self.db.execute("SELECT claimed FROM prize_claims WHERE user_id = ? AND level = ?", (user_id, level)) as cursor:
            result = await cursor.fetchone()
        return result is not None and result[0] == 1

    async def set_prize_claimed(self, user_id, level):
        """Mark a prize as claimed for a given level."""
        await self.db.execute("""
        INSERT OR REPLACE INTO prize_claims (user_id, level, claimed) VALUES (?, ?, ?)
        """, (user_id, level, 1))
        await self.db.commit()

    @commands.Cog.listener()
    async def on_ready(self):
        """Initialize the database on bot ready."""
        # Ensure the data directory exists
        import os
        if not os.path.exists("data"):
            os.makedirs("data")
        if self.db is None:
            await self.init_db()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # Cooldown check
        bucket = self.cooldowns.get_bucket(message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            return

        user_id = message.author.id
        level, xp = await self.get_user_data(user_id)
        xp += 8  # XP for sending a message
        xp_required = self.calculate_xp_required(level)

        if xp >= xp_required:
            level += 1
            xp -= xp_required

            # Notify level up
            await message.channel.send(f"🎉 {message.author.mention}, you have leveled up to: Level {level}!")

            # Notify prize redemption if applicable
            if level % self.prize_interval == 0:
                await message.channel.send(
                    f"🎁 {message.author.mention}, you have reached Level {level}! You are able to claim a prize now. **Open a ticket**!"
                )

            # Assign a role 
            if level % 5 == 0:
                role_name = f"Level {level}"
                guild = message.guild
                role = discord.utils.get(guild.roles, name=role_name)
                if role is None:
                    role = await guild.create_role(name=role_name)
                await message.author.add_roles(role)

        await self.update_user_data(user_id, level, xp)

    @commands.hybrid_command(name="prize")
    @commands.has_permissions(administrator=True)
    async def prize(self, ctx, option: str, member: discord.Member):
        """
        Check or mark prize claims for a user.
        Usage: prize check|claim @member
        """
        user_id = member.id
        user_level, _ = await self.get_user_data(user_id)

        if option.lower() == "check":
            unclaimed = []
            for lvl in range(self.prize_interval, user_level + 1, self.prize_interval):
                if not await self.has_claimed_prize(user_id, lvl):
                    unclaimed.append(lvl)

            if unclaimed:
                levels = ", ".join(map(str, unclaimed))
                await ctx.send(f"{member.mention} has not claimed prizes for levels: {levels}.")
            else:
                await ctx.send(f"{member.mention} has claimed all eligible prizes.")

        elif option.lower() == "claim":
            claimed = []
            for lvl in range(self.prize_interval, user_level + 1, self.prize_interval):
                if not await self.has_claimed_prize(user_id, lvl):
                    await self.set_prize_claimed(user_id, lvl)
                    claimed.append(lvl)

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
        level, xp = await self.get_user_data(member.id)
        xp_required = self.calculate_xp_required(level)
        await ctx.send(f"{member.mention}, you are at Level {level} with {xp}/{xp_required} XP.")

    @commands.hybrid_command(name="leaderboard")
    async def leaderboard(self, ctx):
        """Display the top 10 users by level and XP who are in the server."""
        async with self.db.execute("SELECT user_id, level, xp FROM levels ORDER BY level DESC, xp DESC") as cursor:
            records = await cursor.fetchall()

        server_records = [record for record in records if ctx.guild.get_member(record[0])]
        top_ten = server_records[:10]

        if not top_ten:
            await ctx.send("No leaderboard data available.")
            return

        embed = discord.Embed(title="Leaderboard", color=discord.Color.blurple())
        for index, (user_id, level, xp) in enumerate(top_ten, start=1):
            member = ctx.guild.get_member(user_id)
            embed.add_field(
                name=f"{index}. {member.display_name}",
                value=f"Level: ```{level}```",
                inline=True
            )
        embed.set_footer(text="Keep leveling up!")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(LevelSystem(bot))