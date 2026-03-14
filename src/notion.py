"""
Notion Integration Module
Handles all Notion API calls for quests/checkboxes
"""

import os

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

from src.stats import ATTRIBUTES

# =============================================================================
# CONFIGURATION
# =============================================================================

NOTION_VERSION = "2022-06-28"

# XP amounts
BASE_XP = 25
HALF_XP = 12

# Your Daily Check-In checkboxes from Notion
# Each item has: id, text, group, and stats (list of { stat, xp })
NOTION_CHECKBOXES = [
    # Morning Quests 🌅
    {
        "id": "24f2140f-29f3-80b9-a864-c3c7e1ac05f4",
        "text": "Medication 💊",
        "group": "Morning Quests 🌅",
        "stats": [{"stat": "intelligence", "xp": BASE_XP}],
    },
    {
        "id": "20c2140f-29f3-815a-9f5f-c304f1368f87",
        "text": "Workout 🏃🏽‍♂️",
        "group": "Morning Quests 🌅",
        "stats": [
            {"stat": "strength", "xp": BASE_XP},
            {"stat": "discipline", "xp": HALF_XP},
        ],
    },
    {
        "id": "20c2140f-29f3-8058-bf9d-e6a350523e44",
        "text": "Shower 🚿",
        "group": "Morning Quests 🌅",
        "stats": [{"stat": "charisma", "xp": BASE_XP}],
    },
    {
        "id": "2142140f-29f3-8003-9c78-d120e747f96a",
        "text": "Small Meal + Multivitamin 🍴",
        "group": "Morning Quests 🌅",
        "stats": [{"stat": "vitality", "xp": BASE_XP}],
    },
    {
        "id": "20c2140f-29f3-817f-8a8b-e7e1ac9d780a",
        "text": "Brush Teeth 🪥",
        "group": "Morning Quests 🌅",
        "stats": [{"stat": "charisma", "xp": BASE_XP}],
    },
    # Night Quests 🌙
    {
        "id": "26d2140f-29f3-8058-b9ea-f50065fbeb25",
        "text": "Brush Teeth 🪥",
        "group": "Night Quests 🌙",
        "stats": [{"stat": "charisma", "xp": BASE_XP}],
    },
    {
        "id": "2f72140f-29f3-80f1-add1-db51941b092f",
        "text": "Skin Medication 🧴",
        "group": "Night Quests 🌙",
        "stats": [{"stat": "vitality", "xp": BASE_XP}],
    },
]


class NotionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.notion_secret = os.getenv("NOTION_SECRET")

        # Start polling loop
        self.poll_notion.start()

    def cog_unload(self):
        self.poll_notion.cancel()

    # =========================================================================
    # API HELPERS
    # =========================================================================

    async def notion_fetch(
        self, endpoint: str, method: str = "GET", body: dict = None
    ) -> dict:
        """Helper to make Notion API requests"""
        headers = {
            "Authorization": f"Bearer {self.notion_secret}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION,
        }

        url = f"https://api.notion.com/v1{endpoint}"

        async with aiohttp.ClientSession() as session:
            if method == "GET":
                async with session.get(url, headers=headers) as response:
                    return await response.json()
            elif method == "PATCH":
                async with session.patch(url, headers=headers, json=body) as response:
                    return await response.json()

    async def get_notion_block(self, block_id: str) -> dict:
        """Get a Notion block's current state"""
        return await self.notion_fetch(f"/blocks/{block_id}")

    async def set_notion_checked(self, block_id: str, checked: bool) -> dict:
        """Set a Notion to-do checkbox state"""
        return await self.notion_fetch(
            f"/blocks/{block_id}", "PATCH", {"to_do": {"checked": checked}}
        )

    async def get_all_notion_states(self) -> list:
        """Get all Notion checkbox states"""
        states = []
        for item in NOTION_CHECKBOXES:
            try:
                block = await self.get_notion_block(item["id"])
                if block.get("type") == "to_do":
                    states.append({**item, "checked": block["to_do"]["checked"]})
            except Exception as e:
                print(f"Error fetching {item['text']}: {e}")
                states.append({**item, "checked": False, "error": True})
        return states

    async def reset_all_notion_checkboxes(self):
        """Reset all Notion checkboxes to unchecked"""
        print("🔄 Resetting all Notion checkboxes...")
        for item in NOTION_CHECKBOXES:
            try:
                await self.set_notion_checked(item["id"], False)
                print(f"  ⬜ Reset: {item['text']}")
            except Exception as e:
                print(f"  ❌ Failed to reset {item['text']}: {e}")
        print("✅ Notion checkboxes reset!")

    def find_checkbox(self, query: str):
        """Find a checkbox by number or name"""
        # Try as number
        try:
            num = int(query)
            if 1 <= num <= len(NOTION_CHECKBOXES):
                return NOTION_CHECKBOXES[num - 1]
        except ValueError:
            pass

        # Try as name
        query_lower = query.lower()
        for item in NOTION_CHECKBOXES:
            if query_lower in item["text"].lower():
                return item
        return None

    # =========================================================================
    # NOTION POLLING
    # =========================================================================

    async def initialize_notion_states(self):
        """Initialize the last known Notion states"""
        try:
            states = await self.get_all_notion_states()
            for item in states:
                self.bot.last_notion_states[item["id"]] = item["checked"]
                # If already checked on startup, assume XP was already granted today
                if item["checked"]:
                    self.bot.xp_granted_today[item["id"]] = True
            print("📋 Initialized Notion state tracking")
        except Exception as e:
            print(f"Error initializing Notion states: {e}")

    @tasks.loop(seconds=3)
    async def poll_notion(self):
        """Check Notion for changes and grant XP for newly checked quests"""
        if not self.bot.player_stats:
            return

        try:
            current_states = await self.get_all_notion_states()

            for item in current_states:
                was_checked = self.bot.last_notion_states.get(item["id"], False)
                is_checked = item["checked"]

                # If it went from unchecked to checked, grant XP
                if not was_checked and is_checked:
                    print(f"📋 Detected Notion check: {item['text']}")

                    # Check if we already granted XP for this quest today
                    if self.bot.xp_granted_today.get(item["id"]):
                        print(
                            f"⏭️ Skipping XP for {item['text']} - already granted today"
                        )
                    elif item.get("stats"):
                        xp_gains = []
                        stats_cog = self.bot.get_cog("StatsCog")

                        for stat_info in item["stats"]:
                            result = stats_cog.add_xp(
                                self.bot.player_stats,
                                stat_info["stat"],
                                stat_info["xp"],
                            )
                            attr = next(
                                a for a in ATTRIBUTES if a["key"] == stat_info["stat"]
                            )
                            xp_gains.append(f"{attr['emoji']} +{stat_info['xp']} XP")

                            if result["leveled"]:
                                xp_gains.append(
                                    f"🎉 {attr['name']} leveled up to {result['new_level']}!"
                                )

                        stats_cog.save_stats(self.bot.player_stats)

                        # Mark this quest as XP granted for today
                        self.bot.xp_granted_today[item["id"]] = True

                        # DM the user about the XP gain
                        try:
                            user_id = os.getenv("YOUR_USER_ID")
                            if user_id:
                                user = await self.bot.fetch_user(int(user_id))
                                await user.send(
                                    f"✅ **{item['text']}** completed!\n"
                                    + "\n".join(xp_gains)
                                )
                        except Exception as e:
                            print(f"Error sending XP DM: {e}")

                # Update last known state
                self.bot.last_notion_states[item["id"]] = is_checked

        except Exception as e:
            print(f"Error polling Notion: {e}")

    @poll_notion.before_loop
    async def before_poll(self):
        await self.bot.wait_until_ready()

    # =========================================================================
    # SLASH COMMANDS
    # =========================================================================

    @app_commands.command(
        name="quests", description="View your Notion Daily Check-In status"
    )
    async def quests(self, interaction: discord.Interaction):
        await interaction.response.defer()

        states = await self.get_all_notion_states()

        embed = discord.Embed(title="📋 Daily Check-In", color=0x5865F2)

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
        embed.set_footer(
            text=f"{completed}/{len(states)} completed • Use /check <number> to complete"
        )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="check", description="Check off a quest in Notion")
    @app_commands.describe(quest="Quest name or number (e.g., 'medication' or '1')")
    async def check(self, interaction: discord.Interaction, quest: str):
        item = self.find_checkbox(quest.lower())

        if not item:
            await interaction.response.send_message(
                "❌ Quest not found. Use `/quests` to see the list.", ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            await self.set_notion_checked(item["id"], True)

            # Grant XP for completing the quest
            xp_message = ""
            if item.get("stats"):
                xp_gains = []
                stats_cog = self.bot.get_cog("StatsCog")

                for stat_info in item["stats"]:
                    result = stats_cog.add_xp(
                        self.bot.player_stats, stat_info["stat"], stat_info["xp"]
                    )
                    attr = next(a for a in ATTRIBUTES if a["key"] == stat_info["stat"])
                    xp_gains.append(f"{attr['emoji']} +{stat_info['xp']} XP")

                    if result["leveled"]:
                        xp_gains.append(
                            f"🎉 **{attr['name']} leveled up to {result['new_level']}!**"
                        )

                stats_cog.save_stats(self.bot.player_stats)
                xp_message = "\n" + "\n".join(xp_gains)

            await interaction.followup.send(
                f"✅ Checked off: **{item['text']}**{xp_message}"
            )

        except Exception as e:
            await interaction.followup.send(f"❌ Failed to update Notion: {e}")

    @app_commands.command(name="uncheck", description="Uncheck a quest in Notion")
    @app_commands.describe(quest="Quest name or number (e.g., 'medication' or '1')")
    async def uncheck(self, interaction: discord.Interaction, quest: str):
        item = self.find_checkbox(quest.lower())

        if not item:
            await interaction.response.send_message(
                "❌ Quest not found. Use `/quests` to see the list.", ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            await self.set_notion_checked(item["id"], False)
            await interaction.followup.send(f"⬜ Unchecked: **{item['text']}**")
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to update Notion: {e}")

    @app_commands.command(
        name="resetquests", description="Reset all Notion quests to unchecked"
    )
    async def resetquests(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.reset_all_notion_checkboxes()
        await interaction.followup.send("🔄 All quests have been reset to unchecked!")


async def setup(bot: commands.Bot):
    await bot.add_cog(NotionCog(bot))
