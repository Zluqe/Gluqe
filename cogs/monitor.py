import discord
from discord.ext import commands
import sqlite3
import yaml
import os
import random
import time
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

def load_config():
    with open('config.yml', 'r') as f:
        return yaml.safe_load(f)

class CreditDropMonitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        if not os.path.exists("data"):
            os.makedirs("data")
        
        self.conn = sqlite3.connect("data/monitor_status.db")
        self.cursor = self.conn.cursor()
        self._create_table()
        self.announcement_channel_id = 1324991765970817134

    def _create_table(self):
        """
        Create (or update) the table to store eligible user IDs along with:
          - offline_since: when they went offline (if applicable),
          - qualified_since: when they last qualified with the required status,
          - last_status: the text of the qualifying custom status.
        """
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS credit_drop (
                user_id INTEGER PRIMARY KEY,
                offline_since INTEGER,
                qualified_since INTEGER,
                last_status TEXT
            )
        """)
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_qualified_since ON credit_drop(qualified_since)")
        self.conn.commit()

    def get_qualifying_status(self, member: discord.Member) -> str:
        """
        Return the custom status text if the member's activities include a custom
        status containing "Zluqe.org | Free Bot Hosting". Otherwise return None.
        """
        if not member.activities:
            return None
        for activity in member.activities:
            if isinstance(activity, discord.CustomActivity):
                if activity.name and "Zluqe.org | Free Bot Hosting" in activity.name:
                    return activity.name
        return None

    def qualifies(self, member: discord.Member) -> bool:
        """
        Determines if the member qualifies by having the required custom status.
        """
        return self.get_qualifying_status(member) is not None

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        """
        Update the credit drop database on presence changes.

        For members that qualify:
          - If the member is new or if their qualifying custom status text has changed,
            update (or insert) the record with qualified_since set to the current time.
          - Also update offline_since (set to current time if the member is offline,
            or reset it to NULL if online).
        For members that no longer qualify:
          - If offline, only remove them if they've been offline for more than 3 days.
          - If online, remove them immediately.
        """
        user_id = after.id
        current_time = int(time.time())
        qualifies = self.qualifies(after)
        current_status = self.get_qualifying_status(after) if qualifies else None

        if qualifies:
            if after.status == discord.Status.offline:
                self.cursor.execute("SELECT offline_since, qualified_since, last_status FROM credit_drop WHERE user_id = ?", (user_id,))
                row = self.cursor.fetchone()
                if row is None or row[0] is None:
                    offline_since = current_time
                else:
                    offline_since = row[0]
            else:
                offline_since = None

            self.cursor.execute("SELECT qualified_since, last_status FROM credit_drop WHERE user_id = ?", (user_id,))
            row = self.cursor.fetchone()
            if row is None:
                self.cursor.execute(
                    "INSERT INTO credit_drop (user_id, offline_since, qualified_since, last_status) VALUES (?, ?, ?, ?)",
                    (user_id, offline_since, current_time, current_status)
                )
            else:
                old_qualified_since, old_status = row
                if old_status != current_status:
                    qualified_since = current_time
                else:
                    qualified_since = old_qualified_since
                self.cursor.execute(
                    "UPDATE credit_drop SET offline_since = ?, qualified_since = ?, last_status = ? WHERE user_id = ?",
                    (offline_since, qualified_since, current_status, user_id)
                )
            self.conn.commit()
        else:
            if after.status == discord.Status.offline:
                self.cursor.execute("SELECT offline_since FROM credit_drop WHERE user_id = ?", (user_id,))
                row = self.cursor.fetchone()
                if row is not None:
                    offline_since = row[0]
                    if offline_since is None:
                        offline_since = current_time
                        self.cursor.execute("UPDATE credit_drop SET offline_since = ? WHERE user_id = ?", (offline_since, user_id))
                        self.conn.commit()
                    else:
                        if current_time - offline_since >= 259200:
                            self.cursor.execute("DELETE FROM credit_drop WHERE user_id = ?", (user_id,))
                            self.conn.commit()
                            print(f"Removed {after} after being offline > 3 days and not qualifying.")
            else:
                self.cursor.execute("DELETE FROM credit_drop WHERE user_id = ?", (user_id,))
                self.conn.commit()

    @commands.Cog.listener()
    async def on_ready(self):
        """
        On bot ready, scan through all members in the announcement channel's guild and update the database.
        Then start the scheduling task for the monthly credit drop.
        This version processes members in batches to avoid blocking the event loop.
        """
        channel = self.bot.get_channel(self.announcement_channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(self.announcement_channel_id)
            except Exception as e:
                print(f"Failed to fetch channel with id {self.announcement_channel_id}: {e}")
                return

        guild = channel.guild
        current_time = int(time.time())
        members = guild.members
        total = len(members)
        print(f"Updating credit drop database for {total} members.")

        for i, member in enumerate(members):
            user_id = member.id
            if self.qualifies(member):
                current_status = self.get_qualifying_status(member)
                if member.status == discord.Status.offline:
                    self.cursor.execute("SELECT offline_since FROM credit_drop WHERE user_id = ?", (user_id,))
                    row = self.cursor.fetchone()
                    if row is None or row[0] is None:
                        offline_since = current_time
                    else:
                        offline_since = row[0]
                else:
                    offline_since = None
                self.cursor.execute("SELECT qualified_since, last_status FROM credit_drop WHERE user_id = ?", (user_id,))
                row = self.cursor.fetchone()
                if row is None:
                    self.cursor.execute(
                        "INSERT INTO credit_drop (user_id, offline_since, qualified_since, last_status) VALUES (?, ?, ?, ?)",
                        (user_id, offline_since, current_time, current_status)
                    )
                else:
                    old_qualified_since, old_status = row
                    if old_status != current_status:
                        self.cursor.execute(
                            "UPDATE credit_drop SET offline_since = ?, qualified_since = ?, last_status = ? WHERE user_id = ?",
                            (offline_since, current_time, current_status, user_id)
                        )
                    else:
                        self.cursor.execute(
                            "UPDATE credit_drop SET offline_since = ? WHERE user_id = ?",
                            (offline_since, user_id)
                        )
            else:
                if member.status == discord.Status.offline:
                    self.cursor.execute("SELECT offline_since FROM credit_drop WHERE user_id = ?", (user_id,))
                    row = self.cursor.fetchone()
                    if row is not None:
                        if row[0] is None:
                            self.cursor.execute("UPDATE credit_drop SET offline_since = ? WHERE user_id = ?", (current_time, user_id))
                        else:
                            if current_time - row[0] >= 259200:
                                self.cursor.execute("DELETE FROM credit_drop WHERE user_id = ?", (user_id,))
                else:
                    self.cursor.execute("DELETE FROM credit_drop WHERE user_id = ?", (user_id,))
            if i % 100 == 0:
                await asyncio.sleep(0)
        self.conn.commit()
        print("Initial credit drop database updated on ready.")

        asyncio.create_task(self.schedule_credit_drop())

    async def schedule_credit_drop(self):
        """
        Schedule the monthly credit drop using CST.
        The drop is set for midnight on the 1st day of each month (Central Time).
        This function calculates the delay until the scheduled time, sleeps until then,
        and then performs the credit drop. It repeats indefinitely.
        """
        while True:
            now = datetime.now(ZoneInfo("America/Chicago"))
            drop_day = 1
            drop_hour = 0
            drop_minute = 0
            drop_second = 0

            year = now.year
            month = now.month
            scheduled = datetime(year, month, drop_day, drop_hour, drop_minute, drop_second, tzinfo=ZoneInfo("America/Chicago"))

            if now >= scheduled:
                if month == 12:
                    year += 1
                    month = 1
                else:
                    month += 1
                scheduled = datetime(year, month, drop_day, drop_hour, drop_minute, drop_second, tzinfo=ZoneInfo("America/Chicago"))

            delay = (scheduled - now).total_seconds()
            print(f"Next credit drop scheduled at {scheduled} CST. Waiting {delay:.0f} seconds.")
            await asyncio.sleep(delay)
            await self.perform_credit_drop()

    async def perform_credit_drop(self):
        """
        Execute the credit drop:
          - Query the database for eligible users (only those with qualified_since at least 7 days old),
            letting SQL do the filtering.
          - Randomly select one user.
          - Generate a random credit amount between 250 and 850.
          - Announce the winner in the designated channel.
        """
        channel = self.bot.get_channel(self.announcement_channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(self.announcement_channel_id)
            except Exception as e:
                print(f"Failed to fetch channel with id {self.announcement_channel_id}: {e}")
                return

        current_time = int(time.time())
        seven_days = 7 * 24 * 60 * 60

        self.cursor.execute(
            "SELECT user_id FROM credit_drop WHERE qualified_since IS NOT NULL AND (? - qualified_since) >= ?",
            (current_time, seven_days)
        )
        rows = self.cursor.fetchall()
        if not rows:
            print("No eligible users after filtering for recent status changes.")
            return

        eligible_users = [row[0] for row in rows]
        chosen_user_id = random.choice(eligible_users)
        member = channel.guild.get_member(chosen_user_id)
        if member is None:
            print("Chosen user not found in the guild.")
            return

        credits = random.randint(250, 850)
        message = (
            "🎉 **Credit Drop Announcement!** 🎉\n\n" +
            f"{member.mention}, you have won **{credits} credits**!\n" +
            "Please open a ticket to claim your credits."
        )
        await channel.send(message)
        print(f"Credit drop announcement sent to {member} for {credits} credits.")

async def setup(bot):
    await bot.add_cog(CreditDropMonitor(bot))