"""
Stats System Module
Handles XP, leveling, and stat card generation
"""

import json
from pathlib import Path
import discord
from discord import app_commands
from discord.ext import commands


# =============================================================================
# CONFIGURATION
# =============================================================================

STATS_FILE = Path("./data/stats.json")

ATTRIBUTES = [
    {"key": "strength", "name": "Strength", "emoji": "💪"},
    {"key": "intelligence", "name": "Intelligence", "emoji": "🧠"},
    {"key": "discipline", "name": "Discipline", "emoji": "⚡"},
    {"key": "vitality", "name": "Vitality", "emoji": "❤️"},
    {"key": "charisma", "name": "Charisma", "emoji": "✨"},
]


class StatsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    # =========================================================================
    # XP & LEVELING
    # =========================================================================
    
    def xp_for_level(self, level: int) -> int:
        """XP required for a specific level (flat 100 XP per level)"""
        return 100
    
    def get_overall_level(self, stats: dict) -> int:
        """Calculate overall character level (average of all attributes)"""
        levels = [a["level"] for a in stats["attributes"].values()]
        return sum(levels) // len(levels)
    
    def add_xp(self, stats: dict, attribute_key: str, amount: int) -> dict:
        """
        Add XP to an attribute and handle level ups
        Returns { leveled: bool, new_level: int, xp_gained: int }
        """
        attr = stats["attributes"].get(attribute_key)
        if not attr:
            return {"leveled": False, "new_level": 0, "xp_gained": 0}
        
        attr["xp"] += amount
        
        # Check for level up
        leveled = False
        while attr["xp"] >= self.xp_for_level(attr["level"]):
            attr["xp"] -= self.xp_for_level(attr["level"])
            attr["level"] += 1
            leveled = True
        
        return {"leveled": leveled, "new_level": attr["level"], "xp_gained": amount}
    
    def remove_xp(self, stats: dict, attribute_key: str, amount: int):
        """Remove XP from an attribute (for penalties)"""
        attr = stats["attributes"].get(attribute_key)
        if not attr:
            return
        
        attr["xp"] -= amount
        
        # Handle going below 0 XP
        while attr["xp"] < 0 and attr["level"] > 1:
            attr["level"] -= 1
            attr["xp"] += self.xp_for_level(attr["level"])
        
        # Floor at 0 XP, level 1
        if attr["xp"] < 0:
            attr["xp"] = 0
        if attr["level"] < 1:
            attr["level"] = 1
    
    # =========================================================================
    # STAT CARD DISPLAY
    # =========================================================================
    
    def create_progress_bar(self, current: int, max_val: int, length: int = 10) -> str:
        """Create a progress bar string"""
        filled = round((current / max_val) * length)
        empty = length - filled
        return "█" * filled + "░" * empty
    
    def generate_stat_card(self, stats: dict) -> str:
        """Generate the stat card as a string"""
        overall_level = self.get_overall_level(stats)
        
        card = ""
        card += "╔════════════════════════════════════╗\n"
        card += f"║  🎮 {stats['name'].upper():<15} Level {overall_level:>3} ║\n"
        card += "╠════════════════════════════════════╣\n"
        
        for attr in ATTRIBUTES:
            data = stats["attributes"][attr["key"]]
            xp_needed = self.xp_for_level(data["level"])
            bar = self.create_progress_bar(data["xp"], xp_needed)
            level_str = f"Lv{data['level']:>2}"
            
            card += f"║  {attr['emoji']} {attr['name']:<12} {level_str} {bar} ║\n"
        
        card += "╚════════════════════════════════════╝"
        
        return card
    
    # =========================================================================
    # FILE OPERATIONS
    # =========================================================================
    
    def create_default_stats(self, name: str = "Player") -> dict:
        """Create default stats for a new player"""
        default_stats = {
            "name": name,
            "created_at": str(discord.utils.utcnow()),
            "attributes": {}
        }
        
        for attr in ATTRIBUTES:
            default_stats["attributes"][attr["key"]] = {
                "level": 1,
                "xp": 0
            }
        
        return default_stats
    
    def load_stats(self) -> dict:
        """Load stats from file (or create default)"""
        try:
            if STATS_FILE.exists():
                data = json.loads(STATS_FILE.read_text())
                print("📊 Loaded stats")
                return data
        except Exception as e:
            print(f"Error loading stats: {e}")
        
        return self.create_default_stats()
    
    def save_stats(self, stats: dict):
        """Save stats to file"""
        try:
            STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATS_FILE.write_text(json.dumps(stats, indent=2))
        except Exception as e:
            print(f"Error saving stats: {e}")
    
    # =========================================================================
    # SLASH COMMANDS
    # =========================================================================
    
    @app_commands.command(name="stats", description="View your RPG stat card")
    async def stats_command(self, interaction: discord.Interaction):
        stat_card = self.generate_stat_card(self.bot.player_stats)
        
        embed = discord.Embed(
            title="🎮 Your Stats",
            description=f"```\n{stat_card}\n```",
            color=0x9b59b6
        )
        
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(StatsCog(bot))
