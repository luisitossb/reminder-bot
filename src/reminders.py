"""
Reminders Module
Handles one-time reminders
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
import discord
from discord import app_commands
from discord.ext import commands, tasks


# =============================================================================
# CONFIGURATION
# =============================================================================

REMINDERS_FILE = Path("./data/reminders.json")


class RemindersCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.reminders = []
        
        # Start the reminder check loop
        self.check_reminders.start()
    
    def cog_unload(self):
        self.check_reminders.cancel()
    
    # =========================================================================
    # UTILITY FUNCTIONS
    # =========================================================================
    
    def generate_id(self) -> str:
        """Generates a unique ID for reminders"""
        import random
        import time
        return f"{int(time.time()):x}{random.randint(0, 99999):05x}"
    
    def parse_time(self, time_str: str) -> datetime:
        """Parses user input like '10m', '2h', '3:30pm' into a datetime object"""
        now = datetime.now()
        
        # Relative time: "10m", "2h", "1d"
        relative_match = re.match(r'^(\d+)(m|min|h|hr|hour|d|day)s?$', time_str, re.IGNORECASE)
        if relative_match:
            amount = int(relative_match.group(1))
            unit = relative_match.group(2).lower()
            
            multipliers = {
                'm': timedelta(minutes=1),
                'min': timedelta(minutes=1),
                'h': timedelta(hours=1),
                'hr': timedelta(hours=1),
                'hour': timedelta(hours=1),
                'd': timedelta(days=1),
                'day': timedelta(days=1),
            }
            
            return now + (multipliers[unit] * amount)
        
        # Absolute time: "3:30pm", "15:30", "3pm"
        time_match = re.match(r'^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$', time_str, re.IGNORECASE)
        if time_match:
            hours = int(time_match.group(1))
            minutes = int(time_match.group(2) or 0)
            meridiem = (time_match.group(3) or '').lower()
            
            if meridiem == 'pm' and hours < 12:
                hours += 12
            if meridiem == 'am' and hours == 12:
                hours = 0
            
            target = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
            
            if target <= now:
                target += timedelta(days=1)
            
            return target
        
        return None
    
    def format_time(self, date: datetime) -> str:
        """Formats a datetime into readable time like '3:30 PM'"""
        return date.strftime("%-I:%M %p") if hasattr(date, 'strftime') else str(date)
    
    def format_date(self, date: datetime) -> str:
        """Formats a datetime into readable date+time"""
        now = datetime.now()
        tomorrow = now + timedelta(days=1)
        
        if date.date() == now.date():
            return f"Today at {self.format_time(date)}"
        elif date.date() == tomorrow.date():
            return f"Tomorrow at {self.format_time(date)}"
        else:
            return date.strftime("%a, %b %d at %-I:%M %p")
    
    # =========================================================================
    # FILE OPERATIONS
    # =========================================================================
    
    def load_reminders(self):
        """Load reminders from file"""
        try:
            if REMINDERS_FILE.exists():
                data = json.loads(REMINDERS_FILE.read_text())
                self.reminders = [
                    {**r, "time": datetime.fromisoformat(r["time"])}
                    for r in data
                ]
                print(f"📂 Loaded {len(self.reminders)} reminders")
        except Exception as e:
            print(f"Error loading reminders: {e}")
            self.reminders = []
    
    def save_reminders(self):
        """Save reminders to file"""
        try:
            REMINDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = [
                {**r, "time": r["time"].isoformat()}
                for r in self.reminders
            ]
            REMINDERS_FILE.write_text(json.dumps(data, indent=2))
        except Exception as e:
            print(f"Error saving reminders: {e}")
    
    def add_reminder(self, user_id: str, message: str, time: datetime) -> dict:
        """Add a new reminder"""
        reminder = {
            "id": self.generate_id(),
            "user_id": user_id,
            "message": message,
            "time": time,
            "created_at": datetime.now().isoformat(),
        }
        self.reminders.append(reminder)
        self.save_reminders()
        return reminder
    
    def cancel_reminder(self, reminder_id: str, user_id: str):
        """Cancel a reminder by ID"""
        for i, r in enumerate(self.reminders):
            if r["id"] == reminder_id and r["user_id"] == user_id:
                removed = self.reminders.pop(i)
                self.save_reminders()
                return removed
        return None
    
    def clear_reminders(self, user_id: str) -> int:
        """Clear all reminders for a user"""
        before = len(self.reminders)
        self.reminders = [r for r in self.reminders if r["user_id"] != user_id]
        cleared = before - len(self.reminders)
        self.save_reminders()
        return cleared
    
    def get_user_reminders(self, user_id: str) -> list:
        """Get reminders for a specific user"""
        user_reminders = [r for r in self.reminders if r["user_id"] == user_id]
        return sorted(user_reminders, key=lambda r: r["time"])
    
    # =========================================================================
    # REMINDER CHECK LOOP
    # =========================================================================
    
    @tasks.loop(seconds=1)
    async def check_reminders(self):
        """Check for due reminders"""
        now = datetime.now()
        due = [r for r in self.reminders if r["time"] <= now]
        
        for reminder in due:
            await self.send_reminder(reminder)
        
        if due:
            self.reminders = [r for r in self.reminders if r["time"] > now]
            self.save_reminders()
    
    @check_reminders.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()
    
    async def send_reminder(self, reminder: dict):
        """Send a reminder DM"""
        try:
            user = await self.bot.fetch_user(int(reminder["user_id"]))
            
            embed = discord.Embed(
                title="⏰ Reminder!",
                description=f"**{reminder['message']}**",
                color=0x5865f2,
                timestamp=datetime.now()
            )
            
            await user.send(embed=embed)
            print(f"✅ Sent reminder to {user}: {reminder['message']}")
        except discord.errors.Forbidden:
            print(f"Cannot DM user {reminder['user_id']} - DMs disabled")
        except Exception as e:
            print(f"Error sending reminder: {e}")
    
    # =========================================================================
    # SLASH COMMANDS
    # =========================================================================
    
    @app_commands.command(name="remind", description="Set a one-time reminder")
    @app_commands.describe(
        time="When to remind you (e.g., 10m, 2h, 3:30pm)",
        message="What to remind you about"
    )
    async def remind(self, interaction: discord.Interaction, time: str, message: str):
        parsed_time = self.parse_time(time)
        
        if not parsed_time:
            await interaction.response.send_message(
                "❌ Invalid time format. Use:\n• Relative: `10m`, `2h`, `1d`\n• Absolute: `3pm`, `3:30pm`, `15:30`",
                ephemeral=True
            )
            return
        
        reminder = self.add_reminder(str(interaction.user.id), message, parsed_time)
        
        embed = discord.Embed(
            title="✅ Reminder Set",
            description=f"**{message}**",
            color=0x57f287
        )
        embed.add_field(name="When", value=self.format_date(parsed_time), inline=True)
        embed.set_footer(text=f"ID: {reminder['id']}")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="reminders", description="List your active one-time reminders")
    async def reminders_list(self, interaction: discord.Interaction):
        user_reminders = self.get_user_reminders(str(interaction.user.id))
        
        if not user_reminders:
            await interaction.response.send_message(
                "📭 You have no active reminders.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="📋 Your Reminders",
            color=0x5865f2
        )
        
        for r in user_reminders[:10]:
            embed.add_field(
                name=self.format_date(r["time"]),
                value=f"{r['message']}\n`ID: {r['id']}`",
                inline=False
            )
        
        if len(user_reminders) > 10:
            embed.set_footer(text=f"And {len(user_reminders) - 10} more...")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="cancel", description="Cancel a one-time reminder")
    @app_commands.describe(id="The reminder ID to cancel")
    async def cancel(self, interaction: discord.Interaction, id: str):
        removed = self.cancel_reminder(id, str(interaction.user.id))
        
        if not removed:
            await interaction.response.send_message(
                "❌ Reminder not found or not yours.",
                ephemeral=True
            )
            return
        
        await interaction.response.send_message(f"🗑️ Cancelled reminder: **{removed['message']}**")
    
    @app_commands.command(name="clear", description="Clear all your one-time reminders")
    async def clear(self, interaction: discord.Interaction):
        cleared = self.clear_reminders(str(interaction.user.id))
        await interaction.response.send_message(f"🗑️ Cleared {cleared} reminder(s).")


async def setup(bot: commands.Bot):
    await bot.add_cog(RemindersCog(bot))
