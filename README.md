# Claptrap Reminder Bot (Python)

A productivity Discord bot that integrates with Notion for daily quest tracking, includes an RPG-style XP/leveling system, and sends scheduled reminders.

## Features

- ⏰ **Reminders** - Set one-time reminders with natural time parsing (`10m`, `2h`, `3:30pm`)
- 📋 **Notion Quests** - Track daily tasks from your Notion page with checkbox sync
- 🎮 **RPG Stats** - Earn XP and level up attributes by completing quests
- 📢 **Nudges** - Automatic reminders throughout the day for incomplete tasks
- 🕛 **Midnight Reset** - Quests automatically reset at midnight

## Setup Instructions

### Step 1: Install Dependencies

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
```

**Windows:**
- Install Python 3.10+ from https://python.org (check "Add Python to PATH")

**macOS:**
```bash
brew install python3
```

### Step 2: Set Up the Bot

```bash
# Create virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables

1. Copy `.env.example` to `.env`
2. Fill in your values:

```
DISCORD_TOKEN=your_bot_token
DISCORD_CLIENT_ID=your_client_id
DISCORD_GUILD_ID=your_server_id
YOUR_USER_ID=your_discord_user_id
NOTION_SECRET=your_notion_integration_secret
```

### Step 4: Configure Notion Checkboxes

Edit `src/notion.py` and update `NOTION_CHECKBOXES` with your own Notion block IDs. Each checkbox needs:
- `id` - The Notion block ID (get this from the block's URL or API)
- `text` - Display name
- `group` - Category name
- `stats` - List of `{stat, xp}` for XP rewards

### Step 5: Run the Bot

```bash
# Make sure venv is activated
python bot.py
```

## Commands

### Reminders
| Command | Description |
|---------|-------------|
| `/remind <time> <message>` | Set a reminder (e.g., `/remind 10m Take a break`) |
| `/reminders` | List your active reminders |
| `/cancel <id>` | Cancel a specific reminder |
| `/clear` | Clear all your reminders |

### Quests
| Command | Description |
|---------|-------------|
| `/quests` | View your daily quest checklist |
| `/check <quest>` | Mark a quest complete (by number or name) |
| `/uncheck <quest>` | Unmark a quest |
| `/resetquests` | Reset all quests to unchecked |

### Stats & Settings
| Command | Description |
|---------|-------------|
| `/stats` | View your RPG stat card |
| `/nudges` | View your nudge schedule |

## Project Structure

```
claptrap-python/
├── bot.py              # Main bot file
├── .env                # Your tokens (create from .env.example)
├── .env.example        # Example environment file
├── requirements.txt    # Python dependencies
├── data/
│   ├── stats.json      # Your XP/level data
│   └── reminders.json  # Active reminders
└── src/
    ├── __init__.py
    ├── stats.py        # XP and leveling system
    ├── notion.py       # Notion API integration
    ├── reminders.py    # One-time reminders
    └── scheduler.py    # Scheduled tasks (nudges, resets)
```

## Getting API Keys

### Discord Bot Token
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to "Bot" section and create a bot
4. Copy the token
5. Enable "Message Content Intent" under Privileged Gateway Intents

### Notion Integration
1. Go to [Notion Integrations](https://www.notion.so/my-integrations)
2. Create a new integration
3. Copy the "Internal Integration Secret"
4. Share your Notion page with the integration

## Customization

### Change Nudge Times
Edit `NUDGE_TIMES` in `src/scheduler.py`

### Change Quest Reminder Times
Edit `QUEST_REMINDER_TIMES` in `src/scheduler.py`

### Add/Remove Quests
Edit `NOTION_CHECKBOXES` in `src/notion.py`

### Change XP Values
Edit `BASE_XP` and `HALF_XP` in `src/notion.py`

## License

MIT
