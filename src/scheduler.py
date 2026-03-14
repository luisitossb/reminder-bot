"""
Scheduler Module
Handles all timed events (midnight reset, quest reminders, nudges)
"""

import os
from datetime import datetime, timedelta
import discord
from discord import app_commands
from discord.ext import commands, tasks


# =============================================================================
# CONFIGURATION
# =============================================================================

# Times to send quest reminders (24-hour format)
QUEST_REMINDER_TIMES = [
    {"hour": 8, "minute": 0, "label": "Morning"},
    {"hour": 21, "minute": 0, "label": "Evening"},
]

# Nudge times for incomplete tasks
NUDGE_TIMES = [
    # Morning (7am, 8am, 9am)
    {"hour": 7, "minute": 0},
    {"hour": 8, "minute": 0},
    {"hour": 9, "minute": 0},
    # Afternoon (12pm, 1pm, 2pm)
    {"hour": 12, "minute": 0},
    {"hour": 13, "minute": 0},
    {"hour": 14, "minute": 0},
    # Evening (7pm, 8pm, 9pm)
    {"hour": 19, "minute": 0},
    {"hour": 20, "minute": 0},
    {"hour": 21, "minute": 0},
]


def format_nudge_time(hour: int, minute: int) -> str:
    """Format hour/minute to readable time like '7:00 AM'"""
    period = "PM" if hour >= 12 else "AM"
    display_hour = hour % 12 or 12
    return f"{display_hour}:{minute:02d} {period}"


class SchedulerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.your_user_id = os.getenv("YOUR_USER_ID")
        
        # Start all scheduled tasks
        self.midnight_reset.start()
        self.quest_reminders.start()
        self.nudge_check.start()
    
    def cog_unload(self):
        self.midnight_reset.cancel()
        self.quest_reminders.cancel()
        self.nudge_check.cancel()
    
    # =========================================================================
    # HELPER FUNCTIONS
    # =========================================================================
    
    def get_seconds_until(self, hour: int, minute: int) -> float:
        """Get seconds until a specific time today (or tomorrow if passed)"""
        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if target <= now:
            target += timedelta(days=1)
        
        return (target - now).total_seconds()
    
    async def get_user(self):
        """Get the configured user"""
        if self.your_user_id:
            return await self.bot.fetch_user(int(self.your_user_id))
        return None
    
    # =========================================================================
    # MIDNIGHT RESET
    # =========================================================================
    
    @tasks.loop(hours=24)
    async def midnight_reset(self):
        """Reset quests at midnight"""
        notion_cog = self.bot.get_cog('NotionCog')
        if notion_cog:
            await notion_cog.reset_all_notion_checkboxes()
            # Reset tracked states
            self.bot.last_notion_states = {}
            self.bot.xp_granted_today = {}
            print("🕛 Midnight reset complete!")
    
    @midnight_reset.before_loop
    async def before_midnight(self):
        await self.bot.wait_until_ready()
        # Wait until midnight
        seconds = self.get_seconds_until(0, 0)
        print(f"🕛 Scheduled midnight reset in {seconds/3600:.1f} hours")
        await discord.utils.sleep_until(datetime.now() + timedelta(seconds=seconds))
    
    # =========================================================================
    # QUEST REMINDERS
    # =========================================================================
    
    @tasks.loop(minutes=1)
    async def quest_reminders(self):
        """Check if it's time to send quest reminders"""
        now = datetime.now()
        
        for reminder in QUEST_REMINDER_TIMES:
            if now.hour == reminder["hour"] and now.minute == reminder["minute"]:
                await self.send_quests_dm(reminder["label"])
    
    @quest_reminders.before_loop
    async def before_quest_reminders(self):
        await self.bot.wait_until_ready()
        # Log scheduled times
        for reminder in QUEST_REMINDER_TIMES:
            print(f"⏰ Scheduled {reminder['label']} quest reminder for {format_nudge_time(reminder['hour'], reminder['minute'])}")
    
    async def send_quests_dm(self, label: str = "Daily"):
        """Send a quest checklist DM"""
        try:
            user = await self.get_user()
            if not user:
                return
            
            notion_cog = self.bot.get_cog('NotionCog')
            if not notion_cog:
                return
            
            states = await notion_cog.get_all_notion_states()
            
            embed = discord.Embed(
                title=f"📋 {label} Check-In",
                color=0x5865f2,
                timestamp=datetime.now()
            )
            
            # Group by category
            groups = {}
            for item in states:
                group = item["group"]
                if group not in groups:
                    groups[group] = []
                groups[group].append(item)
            
            quest_number = 1
            for group_name, items in groups.items():
                lines = []
                for item in items:
                    check = "✅" if item["checked"] else "⬜"
                    lines.append(f"{check} `{quest_number}` {item['text']}")
                    quest_number += 1
                embed.add_field(name=group_name, value="\n".join(lines), inline=False)
            
            completed = sum(1 for s in states if s["checked"])
            embed.set_footer(text=f"{completed}/{len(states)} completed • Use /check <number> to complete")
            
            await user.send(embed=embed)
            print(f"✅ Sent {label} quest checklist to user")
            
        except Exception as e:
            print(f"Error sending quest DM: {e}")
    
    # =========================================================================
    # NUDGES
    # =========================================================================
    
    @tasks.loop(minutes=1)
    async def nudge_check(self):
        """Check if it's time to send a nudge"""
        now = datetime.now()
        
        for nudge in NUDGE_TIMES:
            if now.hour == nudge["hour"] and now.minute == nudge["minute"]:
                await self.send_nudge_dm()
    
    @nudge_check.before_loop
    async def before_nudge(self):
        await self.bot.wait_until_ready()
        print(f"📢 Scheduled {len(NUDGE_TIMES)} daily nudges")
    
    async def send_nudge_dm(self):
        """Send a nudge DM showing incomplete quests only"""
        try:
            user = await self.get_user()
            if not user:
                return
            
            notion_cog = self.bot.get_cog('NotionCog')
            if not notion_cog:
                return
            
            states = await notion_cog.get_all_notion_states()
            
            # Filter to incomplete quests only
            incomplete = [s for s in states if not s["checked"]]
            
            # Don't nudge if everything is done!
            if not incomplete:
                print("📢 Nudge skipped - all quests complete!")
                return
            
            embed = discord.Embed(
                title="📢 Incomplete Quests",
                description=f"You have **{len(incomplete)}** quest(s) remaining!",
                color=0xe74c3c,  # Red for urgency
                timestamp=datetime.now()
            )
            
            # Group by category
            groups = {}
            for item in incomplete:
                group = item["group"]
                if group not in groups:
                    groups[group] = []
                groups[group].append(item)
            
            # Find original index for each incomplete quest
            for group_name, items in groups.items():
                lines = []
                for item in items:
                    original_index = next(i for i, s in enumerate(states) if s["id"] == item["id"]) + 1
                    lines.append(f"⬜ `{original_index}` {item['text']}")
                embed.add_field(name=group_name, value="\n".join(lines), inline=False)
            
            embed.set_footer(text="Use /check <number> to complete")
            
            await user.send(embed=embed)
            print(f"📢 Sent nudge - {len(incomplete)} incomplete quests")
            
        except Exception as e:
            print(f"Error sending nudge DM: {e}")
    
    # =========================================================================
    # SLASH COMMANDS
    # =========================================================================
    
    @app_commands.command(name="nudges", description="View your nudge schedule")
    async def nudges(self, interaction: discord.Interaction):
        morning = [n for n in NUDGE_TIMES if 5 <= n["hour"] < 12]
        afternoon = [n for n in NUDGE_TIMES if 12 <= n["hour"] < 17]
        evening = [n for n in NUDGE_TIMES if n["hour"] >= 17]
        
        morning_str = ", ".join(format_nudge_time(n["hour"], n["minute"]) for n in morning) or "None"
        afternoon_str = ", ".join(format_nudge_time(n["hour"], n["minute"]) for n in afternoon) or "None"
        evening_str = ", ".join(format_nudge_time(n["hour"], n["minute"]) for n in evening) or "None"
        
        embed = discord.Embed(
            title="📢 Nudge Schedule",
            description=f"You have **{len(NUDGE_TIMES)}** nudges scheduled daily.",
            color=0xf39c12
        )
        embed.add_field(name="🌅 Morning", value=morning_str, inline=False)
        embed.add_field(name="☀️ Afternoon", value=afternoon_str, inline=False)
        embed.add_field(name="🌙 Evening", value=evening_str, inline=False)
        embed.set_footer(text="Edit nudge times in src/scheduler.py")
        
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(SchedulerCog(bot))
