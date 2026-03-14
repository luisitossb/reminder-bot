"""
Claptrap Reminder Bot
Main entry point - imports modules and runs the bot
"""

# =============================================================================
# IMPORTS
# =============================================================================

import os
import asyncio
from datetime import datetime
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

# Import our modules
from src.stats import StatsCog
from src.notion import NotionCog
from src.reminders import RemindersCog
from src.scheduler import SchedulerCog

# Load environment variables
load_dotenv()


# =============================================================================
# BOT SETUP
# =============================================================================

class ClaptrapBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.dm_messages = True
        
        super().__init__(command_prefix="!", intents=intents)
        
        # Shared state between cogs
        self.player_stats = None
        self.last_notion_states = {}
        self.xp_granted_today = {}
    
    async def setup_hook(self):
        """Called when the bot is starting up"""
        # Add cogs
        await self.add_cog(StatsCog(self))
        await self.add_cog(NotionCog(self))
        await self.add_cog(RemindersCog(self))
        await self.add_cog(SchedulerCog(self))
        
        # Sync slash commands to guild (instant) instead of global (up to 1 hour)
        guild_id = os.getenv("DISCORD_GUILD_ID")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print("✅ Slash commands registered (guild)!")
        else:
            await self.tree.sync()
            print("✅ Slash commands registered (global)!")


bot = ClaptrapBot()


# =============================================================================
# BOT STARTUP
# =============================================================================

@bot.event
async def on_ready():
    print(f"🤖 {bot.user} is online!")
    
    # Load stats
    stats_cog = bot.get_cog('StatsCog')
    if stats_cog:
        bot.player_stats = stats_cog.load_stats()
        bot.player_stats['name'] = "Luis"  # Set your name
        stats_cog.save_stats(bot.player_stats)
    
    # Initialize Notion state tracking
    notion_cog = bot.get_cog('NotionCog')
    if notion_cog:
        await notion_cog.initialize_notion_states()
    
    # Load reminders
    reminders_cog = bot.get_cog('RemindersCog')
    if reminders_cog:
        reminders_cog.load_reminders()


# =============================================================================
# ERROR HANDLING
# =============================================================================

@bot.event
async def on_error(event, *args, **kwargs):
    print(f"Error in {event}: {args}")


# =============================================================================
# START THE BOT
# =============================================================================

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ No DISCORD_TOKEN in .env file!")
        exit(1)
    
    print("🚀 Starting bot...")
    bot.run(token)
